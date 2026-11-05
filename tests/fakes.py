"""Controlled external I/O boundaries; tests drive the public bridge API."""
from contextlib import contextmanager
from functools import wraps
import queue
import threading
import time


class Clock:
    """Time advances only when the test asks; no real retry sleeps."""
    def __init__(self):
        self.now = 0.0
        self.lock = threading.Lock()

    def __call__(self):
        with self.lock:
            return self.now

    def advance(self, seconds):
        with self.lock:
            self.now += seconds


class Channel:
    def __init__(self):
        self.incoming = queue.Queue()
        self.output = bytearray()
        self.opened = threading.Event()
        self.closed = threading.Event()
        self.open_gate = threading.Event()
        self.open_gate.set()
        self.close_gate = threading.Event()
        self.close_gate.set()
        self.read_gate = threading.Event()
        self.read_gate.set()
        self.read_entered = threading.Event()
        self.open_error = None
        self.write_error = None
        self.close_error = None
        self.write_limit = 1024

    def open(self):
        self.opened.set()
        self.open_gate.wait()
        if self.open_error:
            raise OSError(self.open_error)

    def read(self):
        self.read_entered.set()
        self.read_gate.wait()
        try:
            value = self.incoming.get(timeout=0.005)
        except queue.Empty:
            return None
        if isinstance(value, Exception):
            raise value
        return value

    def write(self, data):
        if self.write_error:
            raise OSError(self.write_error)
        size = min(len(data), self.write_limit)
        self.output.extend(data[:size])
        return size

    def close(self):
        self.close_gate.wait()
        if self.close_error:
            raise OSError(self.close_error)
        self.closed.set()


def wait_until(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("Timed out waiting for observable behavior")
        threading.Event().wait(0.001)


def native(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self.operation(method.__name__):
            return method(self, *args, **kwargs)
    return call


class Probe:
    """pylink 1.2.0 boundary; no DLL or Target is needed."""
    def __init__(self):
        self.actual_serial = 123456
        self._lock = None
        self._open_refcount = 0
        self.native_open = False
        self.gates = {}
        self.entered = {}
        self.errors = {}
        self.native_lock = threading.Lock()
        self.concurrent_calls = []
        self.target_available = True
        self.up_count = 1
        self.down_count = 1
        self.buffer_size = 1024
        self.interface_accepted = True
        self.write_limit = 1024
        self.write_results = queue.Queue()
        self.requested_serial = None
        self.interface = None
        self.connection = None
        self.resets = []
        self.opened_event = threading.Event()
        self.closed = threading.Event()
        self.input = queue.Queue()
        self.output = bytearray()
        self.rtt_active = False

    @contextmanager
    def operation(self, name):
        if not self.native_lock.acquire(blocking=False):
            self.concurrent_calls.append(name)
            raise AssertionError('Concurrent native call: ' + name)
        try:
            self.entered.setdefault(name, threading.Event()).set()
            if name in self.gates:
                self.gates[name].wait()
            if name in self.errors:
                raise self.errors[name]
            yield
        finally:
            self.native_lock.release()

    @property
    @native
    def serial_number(self):
        return self.actual_serial

    def block(self, name):
        self.gates[name] = threading.Event()
        self.entered[name] = threading.Event()

    @native
    def open(self, serial_no=None):
        self._open_refcount = 1
        self.native_open = True
        self.requested_serial = serial_no
        self.opened_event.set()

    @native
    def set_tif(self, interface):
        self.interface = interface
        return self.interface_accepted

    @native
    def connect(self, chip_name, speed='auto', verbose=False):
        self.connection = (chip_name, speed)

    @native
    def opened(self):
        return self.native_open

    @native
    def connected(self):
        return True

    @native
    def target_connected(self):
        return self.target_available

    @native
    def reset(self, ms=0, halt=True):
        self.resets.append((ms, halt))

    @native
    def rtt_start(self, block_address=None):
        self.rtt_active = True

    @native
    def rtt_get_num_up_buffers(self):
        return self.up_count

    @native
    def rtt_get_num_down_buffers(self):
        return self.down_count

    @native
    def rtt_get_buf_descriptor(self, buffer_index, up):
        from pylink.structs import JLinkRTTerminalBufDesc
        return JLinkRTTerminalBufDesc(BufferIndex=buffer_index, Direction=0 if up else 1,
                                     SizeOfBuffer=self.buffer_size)

    @native
    def rtt_read(self, buffer_index, num_bytes):
        assert buffer_index == 0
        try:
            return list(self.input.get_nowait())
        except queue.Empty:
            return []

    @native
    def rtt_write(self, buffer_index, data):
        assert buffer_index == 0
        try:
            result = self.write_results.get_nowait()
        except queue.Empty:
            result = min(len(data), self.write_limit)
        if isinstance(result, Exception):
            raise result
        self.output.extend(data[:result])
        return result

    @native
    def rtt_stop(self):
        self.rtt_active = False

    @native
    def close(self):
        self.native_open = False
        self._open_refcount = 0
        self.closed.set()
