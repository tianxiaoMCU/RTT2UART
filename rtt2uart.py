"""Qt-independent lifecycle owner for USB and Existing Session RTT bridges."""
from dataclasses import dataclass, replace
from enum import Enum
import socket
import threading
import time
from typing import Callable, Protocol

from usb_transport import USBChannel, USBConfig


class BridgeState(Enum):
    STOPPED = "Stopped"
    STARTING = "Starting"
    ENDPOINT_CONNECTED = "Endpoint connected — Target state unverified"
    RUNNING = "Running"
    RECONNECTING = "Reconnecting"
    STOPPING = "Stopping"
    STOP_INCOMPLETE = "Stop incomplete"
    FAILED = "Failed"


@dataclass(frozen=True)
class BridgeConfig:
    port: str
    baudrate: int = 115200
    endpoint_host: str = "localhost"
    endpoint_port: int = 19021
    auto_reconnect: bool | None = None
    usb: USBConfig | None = None

    def __post_init__(self) -> None:
        if self.auto_reconnect is None:
            object.__setattr__(self, "auto_reconnect", self.usb is None)


@dataclass(frozen=True)
class BridgeSnapshot:
    state: BridgeState = BridgeState.STOPPED
    reason: str = ""
    cleanup_error: str = ""
    discarded_bytes: int = 0
    probe_serial_number: int | None = None

    @property
    def can_start(self) -> bool:
        return self.state in (BridgeState.STOPPED, BridgeState.FAILED)


class _Channel(Protocol):
    """Owned I/O boundary. None is idle; endpoint b'' is EOF."""
    def open(self) -> None: ...
    def read(self) -> bytes | None: ...
    def write(self, data: bytes) -> int: ...
    def close(self) -> None: ...


class _SerialChannel:
    def __init__(self, config: BridgeConfig):
        import serial
        self._serial = serial.Serial(port=None, baudrate=config.baudrate,
                                     timeout=0.01, write_timeout=1.0)
        self._serial.port = config.port

    def open(self) -> None:
        self._serial.open()

    def read(self) -> bytes:
        return self._serial.read(min(self._serial.in_waiting, 1024) or 1)

    def write(self, data: bytes) -> int:
        written = self._serial.write(data)
        return written if written is not None else 0

    def close(self) -> None:
        self._serial.close()


class _EndpointChannel:
    def __init__(self, config: BridgeConfig):
        self._address = (config.endpoint_host, config.endpoint_port)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def open(self) -> None:
        self._socket.settimeout(3.0)
        self._socket.connect(self._address)
        self._socket.settimeout(0.01)

    def read(self) -> bytes | None:
        try:
            return self._socket.recv(1024)
        except socket.timeout:
            return None

    def write(self, data: bytes) -> int:
        return self._socket.send(data)

    def close(self) -> None:
        self._socket.close()


class Bridge:
    """Start/stop are nonblocking; snapshot is safe to read on the GUI loop.

    Factories create unopened, owned resources. Even failed open() calls are
    followed by close(). One worker owns forwarding and serial I/O. A temporary
    transport worker opens or retires recovery endpoints while that worker
    drains serial input; it is joined before transport ownership transfers.
    """
    def __init__(self, *, serial_factory: Callable[[BridgeConfig], _Channel] = _SerialChannel,
                 transport_factory: Callable[[BridgeConfig], _Channel] | None = None,
                 cleanup_timeout: float = 4.0,
                 clock: Callable[[], float] = time.monotonic):
        self._serial_factory = serial_factory
        self._transport_factory = transport_factory
        self._cleanup_timeout = cleanup_timeout
        self._clock = clock
        self._lock = threading.RLock()
        self._snapshot = BridgeSnapshot()
        self._cancel = threading.Event()
        self._cleanup_wakeup = threading.Event()
        self._user_stop = False

    @property
    def snapshot(self) -> BridgeSnapshot:
        with self._lock:
            return self._snapshot

    def start(self, config: BridgeConfig) -> BridgeSnapshot:
        with self._lock:
            if not self._snapshot.can_start:
                raise RuntimeError("Previous run has not finished cleanup")
            if not config.port or config.baudrate <= 0:
                raise ValueError("Select a serial port and a positive baud rate")
            self._cancel = threading.Event()
            self._cleanup_wakeup = threading.Event()
            self._user_stop = False
            self._snapshot = starting = BridgeSnapshot(BridgeState.STARTING)
            try:
                # Establish the observer before any I/O can acquire resources.
                threading.Thread(target=self._supervise, args=(config,),
                                 name="bridge-cleanup").start()
            except Exception as error:
                self._snapshot = BridgeSnapshot(BridgeState.FAILED,
                                                f"Lifecycle startup: {error}")
                return self._snapshot
            return starting

    def stop(self) -> None:
        with self._lock:
            if self._snapshot.can_start:
                return
            self._user_stop = True
            self._cancel.set()
            self._cleanup_wakeup.set()
            if self._snapshot.state != BridgeState.STOP_INCOMPLETE:
                self._snapshot = replace(self._snapshot, state=BridgeState.STOPPING)

    def _fail(self, error: Exception) -> None:
        with self._lock:
            if not self._cancel.is_set():
                self._snapshot = replace(self._snapshot, state=BridgeState.STOPPING,
                                         reason=str(error))
            self._cancel.set()

    def _supervise(self, config: BridgeConfig) -> None:
        try:
            worker = threading.Thread(target=self._run, args=(config,), name="bridge-io")
            worker.start()
        except Exception as error:
            self._fail(RuntimeError(f"I/O worker startup: {error}"))
            self._complete()
            return
        self._cancel.wait()
        worker.join(self._cleanup_timeout)
        if worker.is_alive():
            with self._lock:
                self._snapshot = replace(
                    self._snapshot, state=BridgeState.STOP_INCOMPLETE,
                    cleanup_error=self._snapshot.cleanup_error or
                    "Cleanup is still pending; waiting for the owned operation to return")
        worker.join()
        self._complete()

    def _complete(self) -> None:
        with self._lock:
            state = BridgeState.STOPPED if self._user_stop else BridgeState.FAILED
            self._snapshot = replace(self._snapshot, state=state, cleanup_error="")

    def _run(self, config: BridgeConfig) -> None:
        resources: list[_Channel] = []
        stage = "Serial open"
        try:
            serial_channel = self._serial_factory(config)
            resources.append(serial_channel)
            serial_channel.open()
            if self._cancel.is_set():
                return
            stage = "USB connect/readiness" if config.usb else "Endpoint connect"
            endpoint = self._make_transport(config)
            resources.append(endpoint)
            try:
                endpoint.open()
            finally:
                if isinstance(endpoint, USBChannel):
                    with self._lock:
                        self._snapshot = replace(self._snapshot,
                                                 probe_serial_number=endpoint.serial_number)
            with self._lock:
                if self._cancel.is_set():
                    return
                self._snapshot = replace(self._snapshot, state=(
                    BridgeState.RUNNING if config.usb else BridgeState.ENDPOINT_CONNECTED))
            while not self._cancel.is_set():
                stage = "USB RTT read" if config.usb else "Endpoint read"
                try:
                    received = endpoint.read()
                    if received == b"":
                        raise ConnectionError("Endpoint closed the connection")
                except Exception as error:
                    endpoint = self._recover(config, serial_channel, endpoint,
                                             resources, f"{stage}: {error}")
                    continue
                stage = "Serial write (delivery may be partial)"
                if received:
                    self._write(serial_channel, received)
                if self._cancel.is_set():
                    break
                stage = "Serial read"
                received = serial_channel.read()
                stage = (("USB RTT write" if config.usb else "Endpoint write")
                         + " (delivery may be partial)")
                if received:
                    try:
                        self._write(endpoint, received)
                    except Exception as error:
                        # Never carry a partially accepted or uncertain tail to
                        # the next connection. It is not a definite discard.
                        endpoint = self._recover(config, serial_channel, endpoint,
                                                 resources, f"{stage}: {error}")
        except Exception as error:
            self._fail(RuntimeError(f"{stage}: {error}"))
        finally:
            self._close_resources(list(reversed(resources)))

    def _make_transport(self, config: BridgeConfig) -> _Channel:
        if self._transport_factory is not None:
            return self._transport_factory(config)
        if config.usb is not None:
            return USBChannel(config.usb, self._cancel, self._clock)
        return _EndpointChannel(config)

    def _close_resources(self, pending: list[_Channel]) -> None:
        while pending:
            for resource in pending[:]:
                try:
                    resource.close()
                except Exception as error:
                    with self._lock:
                        self._snapshot = replace(
                            self._snapshot, state=BridgeState.STOP_INCOMPLETE,
                            cleanup_error=f"Resource close failed: {error}")
                else:
                    pending.remove(resource)
            if pending:
                self._cleanup_wakeup.wait(0.25)
                self._cleanup_wakeup.clear()

    def _discard(self, serial_channel: _Channel) -> bool:
        """Read on the serial owner; count only bytes definitely not forwarded."""
        try:
            data = serial_channel.read()
        except Exception as error:
            self._fail(RuntimeError(f"Serial read during recovery: {error}"))
            raise
        if data:
            with self._lock:
                self._snapshot = replace(
                    self._snapshot,
                    discarded_bytes=self._snapshot.discarded_bytes + len(data))
        return bool(data)

    def _discard_during(self, serial_channel: _Channel,
                        operation: Callable[[], None]) -> Exception | None:
        """Lend exclusive transport ownership while the serial owner drains."""
        errors: list[Exception] = []
        done = threading.Event()

        def execute() -> None:
            try:
                operation()
            except Exception as error:
                errors.append(error)
            finally:
                done.set()

        connector = threading.Thread(target=execute, name="bridge-recovery")
        connector.start()
        try:
            while not done.is_set() and not self._cancel.is_set():
                if not self._discard(serial_channel):
                    self._cancel.wait(0.005)
        finally:
            # Stop invalidates immediately; native calls cannot be interrupted
            # by concurrent close/reset. The observer bounds cleanup waiting.
            connector.join()
        return errors[0] if errors else None

    def _retire_transport(self, serial_channel: _Channel, endpoint: _Channel,
                          resources: list[_Channel]) -> None:
        error = self._discard_during(serial_channel, endpoint.close)
        if error is not None:
            raise error
        resources.remove(endpoint)

    def _recover(self, config: BridgeConfig, serial_channel: _Channel,
                 endpoint: _Channel, resources: list[_Channel], reason: str) -> _Channel:
        if not config.auto_reconnect:
            raise ConnectionError(reason)
        if config.usb is not None:
            identity = self.snapshot.probe_serial_number
            if identity is None:
                raise ConnectionError("Cannot recover USB without the original probe identity")
            # Recovery retains the run settings, but can never select another
            # probe or repeat the user's explicit initial reset.
            config = replace(config, usb=replace(config.usb, serial_number=identity,
                                                 startup_reset=False))
        with self._lock:
            if self._cancel.is_set():
                return endpoint
            deadline = self._clock() + 1.0
            self._snapshot = replace(self._snapshot, state=BridgeState.RECONNECTING,
                                     reason=reason)
        # No forwarding worker or queued read survives this boundary: the same
        # serial owner enters recovery only after its current I/O has returned.
        self._retire_transport(serial_channel, endpoint, resources)
        attempt = 0
        while not self._cancel.is_set():
            while self._clock() < deadline and not self._cancel.is_set():
                if not self._discard(serial_channel):
                    self._cancel.wait(0.005)
            if self._cancel.is_set():
                break
            endpoint = self._make_transport(config)
            resources.append(endpoint)
            error = self._discard_during(serial_channel, endpoint.open)
            if self._cancel.is_set():
                break
            if error is not None:
                self._retire_transport(serial_channel, endpoint, resources)
                attempt += 1
                deadline = self._clock() + (1.0, 2.0, 5.0)[min(attempt, 2)]
                with self._lock:
                    self._snapshot = replace(self._snapshot,
                                             reason=f"{'USB' if config.usb else 'Endpoint'} reconnect: {error}")
                continue
            # Drain through idle after connect completes, including any read
            # already in flight. There is no application queue to replay.
            while not self._cancel.is_set() and self._discard(serial_channel):
                pass
            with self._lock:
                if not self._cancel.is_set():
                    self._snapshot = replace(self._snapshot,
                                             state=(BridgeState.RUNNING if config.usb
                                                    else BridgeState.ENDPOINT_CONNECTED),
                                             reason="")
            return endpoint
        return endpoint

    def _write(self, channel: _Channel, data: bytes) -> None:
        offset = 0
        stalled = 0
        while offset < len(data) and not self._cancel.is_set():
            written = channel.write(data[offset:])
            if written < 0 or written > len(data) - offset:
                raise OSError("Write made no valid progress; delivery may be partial")
            if written == 0:
                stalled += 1
                if stalled >= 3:
                    raise OSError("Write made no valid progress; delivery may be partial")
                self._cancel.wait(0.01)
                continue
            stalled = 0
            offset += written
