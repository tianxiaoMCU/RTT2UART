"""Owned USB direct RTT using the pinned pylink_square 1.2.0 contract."""
from dataclasses import dataclass
import os
import threading
import time
from typing import Any, Callable


@dataclass(frozen=True)
class USBConfig:
    target: str
    interface: int = 1
    speed: int = 4000
    serial_number: int | None = None
    startup_reset: bool = False

    def __post_init__(self) -> None:
        if not self.target.strip():
            raise ValueError("Select a Target device")
        if type(self.interface) is not int or self.interface not in (0, 1, 3, 4, 5, 6):
            raise ValueError("Select a supported debug interface")
        if type(self.speed) is not int or self.speed <= 0:
            raise ValueError("Select a positive debug speed in kHz")
        if self.serial_number is not None and (type(self.serial_number) is not int
                                              or self.serial_number <= 0):
            raise ValueError("USB probe serial number must be a positive integer")


class USBChannel:
    """All methods are called sequentially by the bridge I/O owner."""
    def __init__(self, config: USBConfig, cancel: threading.Event,
                 clock: Callable[[], float] = time.monotonic):
        self._config = config
        self._cancel = cancel
        self._clock = clock
        self._probe: Any = None
        self._probe_lock: Any = None
        self._lock_path: str | None = None
        self._rtt_started = False
        self.serial_number: int | None = None

    def _check_cancelled(self) -> None:
        if self._cancel.is_set():
            raise InterruptedError("USB operation cancelled")

    def _call(self, operation: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        self._check_cancelled()
        result = operation(*args, **kwargs)
        self._check_cancelled()
        return result

    def open(self) -> None:
        import pylink  # type: ignore[import-untyped]
        self._check_cancelled()
        self._probe = pylink.JLink()
        self._call(self._probe.open, serial_no=self._config.serial_number)
        actual = self._probe.serial_number
        self._check_cancelled()
        if type(actual) is not int or actual <= 0:
            raise ConnectionError("USB probe identity is unavailable or invalid")
        self.serial_number = actual
        if self._config.serial_number is not None and actual != self._config.serial_number:
            raise ConnectionError(
                f"USB probe identity mismatch: requested {self._config.serial_number}, got {actual}")
        self._prepare_target()
        if self._config.startup_reset:
            self._call(self._probe.reset, halt=False)
        self._rtt_started = True
        self._call(self._probe.rtt_start)
        self._wait_ready()

    def _prepare_target(self) -> None:
        if not self._call(self._probe.set_tif, self._config.interface):
            raise ConnectionError("Target debug interface selection failed")
        self._call(self._probe.connect, self._config.target, speed=self._config.speed)

    def _wait_ready(self) -> None:
        from pylink.errors import JLinkRTTException  # type: ignore[import-untyped]
        deadline = self._clock() + 3.0
        while True:
            self._check_target()
            try:
                self._check_channels()
                return
            except (ConnectionError, JLinkRTTException) as error:
                if self._clock() >= deadline:
                    raise ConnectionError(f"RTT channel 0 readiness timed out: {error}") from error
                self._cancel.wait(0.01)

    def _check_target(self) -> None:
        if not self._call(self._probe.target_connected):
            raise ConnectionError("Target debug connection is unavailable")

    def _check_channels(self) -> None:
        if (self._call(self._probe.rtt_get_num_up_buffers) < 1 or
                self._call(self._probe.rtt_get_num_down_buffers) < 1):
            raise ConnectionError("RTT channel 0 is unavailable")
        for up in (True, False):
            descriptor = self._call(self._probe.rtt_get_buf_descriptor, 0, up)
            if (descriptor.BufferIndex != 0 or descriptor.Direction != (0 if up else 1)
                    or descriptor.SizeOfBuffer < 2):
                raise ConnectionError("RTT channel 0 descriptor is unusable")

    def read(self) -> bytes | None:
        self._check_target()
        self._check_channels()
        data = bytes(self._call(self._probe.rtt_read, 0, 1024))
        return data or None

    def write(self, data: bytes) -> int:
        return int(self._call(self._probe.rtt_write, 0, list(data)))

    def close(self) -> None:
        if self._probe is None:
            return
        try:
            if self._rtt_started:
                try:
                    self._probe.rtt_stop()
                except Exception:
                    # Closing the owned session also ends its RTT processing.
                    # A successful verified close is sufficient for release.
                    pass
                self._rtt_started = False
        finally:
            self._close_probe()

    def _close_probe(self) -> None:
        # Pinned 1.2.0 increments its refcount only at the end of open() and
        # decrements before native close. Repair that guard after partial open
        # or failed close, only when the DLL confirms it is still open. Never
        # issue a concurrent or blind native close. Keep the lock alive across
        # wrapper close so release is explicit, checked and retryable.
        if self._probe_lock is None:
            self._probe_lock = self._probe._lock
        if self._probe.opened() and self._probe._open_refcount == 0:
            self._probe._open_refcount = 1
        self._probe.close()
        if self._probe.opened():
            raise OSError("USB probe close is incomplete")
        if self._probe_lock is not None:
            # JLock.release() in 1.2.0 closes fd before deleting the file, but
            # clears acquired only afterwards. A failed unlink would make its
            # next release close the same (possibly reused) fd. Track each step
            # here; never remove a lock this run did not acquire.
            if self._probe_lock.acquired:
                os.close(self._probe_lock.fd)
                self._probe_lock.fd = None
                self._probe_lock.acquired = False
                self._lock_path = self._probe_lock.path
            if self._lock_path is not None:
                try:
                    os.remove(self._lock_path)
                except FileNotFoundError:
                    pass
                self._lock_path = None
            self._probe_lock = None
            self._probe._lock = None
        self._probe = None
