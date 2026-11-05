import dataclasses
import socket
import threading
import unittest
from unittest.mock import patch

from rtt2uart import Bridge, BridgeConfig, BridgeState
from tests.fakes import Channel, wait_until


class BridgeTests(unittest.TestCase):
    def make_bridge(self):
        self.serial = Channel()
        self.endpoint = Channel()
        self.bridge = Bridge(serial_factory=lambda config: self.serial,
                             transport_factory=lambda config: self.endpoint,
                             cleanup_timeout=0.05)
        self.addCleanup(self.cleanup_bridge, self.bridge, self.serial, self.endpoint)
        return self.bridge

    def finish(self):
        self.cleanup_bridge(self.bridge, self.serial, self.endpoint)

    @staticmethod
    def cleanup_bridge(bridge, serial_channel, endpoint):
        for resource in (serial_channel, endpoint):
            resource.open_gate.set()
            resource.close_gate.set()
            resource.read_gate.set()
            resource.close_error = None
        bridge.stop()
        wait_until(lambda: bridge.snapshot.can_start)

    def state(self, state):
        wait_until(lambda: self.bridge.snapshot.state == state)

    def test_async_start_frozen_config_transfer_stop_and_restart(self):
        bridge = self.make_bridge()
        self.endpoint.open_gate.clear()
        config = BridgeConfig(port="COM4", auto_reconnect=False)
        starting = bridge.start(config)
        self.assertEqual(starting.state, BridgeState.STARTING)
        self.assertFalse(starting.can_start)
        self.assertEqual(config.endpoint_host, "localhost")
        self.assertEqual(config.endpoint_port, 19021)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            config.port = "COM5"
        self.assertTrue(self.endpoint.opened.wait(1))
        self.assertEqual(bridge.snapshot.state, BridgeState.STARTING)
        self.endpoint.open_gate.set()
        self.state(BridgeState.ENDPOINT_CONNECTED)
        self.serial.incoming.put(b"\x00\xffcommand\r\n")
        self.endpoint.incoming.put(b"\xff\x00reply\n")
        wait_until(lambda: self.endpoint.output == b"\x00\xffcommand\r\n")
        wait_until(lambda: self.serial.output == b"\xff\x00reply\n")
        bridge.stop()
        self.state(BridgeState.STOPPED)
        self.assertTrue(self.serial.closed.is_set())
        self.assertTrue(self.endpoint.closed.is_set())
        bridge.start(config)
        self.state(BridgeState.ENDPOINT_CONNECTED)

    def test_stop_fences_late_connection_and_reports_incomplete_until_exit(self):
        bridge = self.make_bridge()
        self.endpoint.open_gate.clear()
        bridge.start(BridgeConfig(port="COM4", auto_reconnect=False))
        self.assertTrue(self.endpoint.opened.wait(1))
        bridge.stop()
        bridge.stop()
        self.state(BridgeState.STOP_INCOMPLETE)
        with self.assertRaises(RuntimeError):
            bridge.start(BridgeConfig(port="COM5", auto_reconnect=False))
        self.serial.incoming.put(b"must not forward")
        self.endpoint.open_gate.set()
        self.state(BridgeState.STOPPED)
        self.assertEqual(self.endpoint.output, b"")
        self.assertTrue(self.endpoint.closed.is_set())
        self.assertTrue(self.serial.closed.is_set())

    def test_failed_close_keeps_restart_locked_and_can_later_complete(self):
        bridge = self.make_bridge()
        self.endpoint.close_error = "close unavailable"
        bridge.start(BridgeConfig(port="COM4", auto_reconnect=False))
        self.state(BridgeState.ENDPOINT_CONNECTED)
        bridge.stop()
        self.state(BridgeState.STOP_INCOMPLETE)
        self.assertIn("close unavailable", bridge.snapshot.cleanup_error)
        self.assertFalse(bridge.snapshot.can_start)
        self.assertTrue(self.serial.closed.wait(1))
        self.endpoint.close_error = None
        bridge.stop()
        self.state(BridgeState.STOPPED)
        self.assertTrue(self.endpoint.closed.is_set())

    def test_partial_startup_failures_release_resources_and_allow_manual_retry(self):
        for failing_resource, expected in (("serial", "Serial open"),
                                           ("endpoint", "Endpoint connect")):
            with self.subTest(stage=failing_resource):
                bridge = self.make_bridge()
                getattr(self, failing_resource).open_error = "access denied"
                bridge.start(BridgeConfig(port="COM4", auto_reconnect=False))
                self.state(BridgeState.FAILED)
                self.assertIn(expected, bridge.snapshot.reason)
                self.assertIn("access denied", bridge.snapshot.reason)
                self.assertTrue(self.serial.closed.is_set())
                if failing_resource == "endpoint":
                    self.assertTrue(self.endpoint.closed.is_set())
                else:
                    self.assertFalse(self.endpoint.opened.is_set())
                getattr(self, failing_resource).open_error = None
                bridge.start(BridgeConfig(port="COM4", auto_reconnect=False))
                self.state(BridgeState.ENDPOINT_CONNECTED)
                self.finish()

    def test_runtime_failures_are_terminal_and_retain_actionable_reason(self):
        cases = (("endpoint", "read", b"", "Endpoint read"),
                 ("endpoint", "read", OSError("read failed"), "Endpoint read"),
                 ("serial", "read", OSError("port lost"), "Serial read"),
                 ("endpoint", "write", "send failed", "Endpoint write"),
                 ("serial", "write", "port lost", "Serial write"))
        for source, operation, failure, expected in cases:
            with self.subTest(source=source, operation=operation):
                bridge = self.make_bridge()
                bridge.start(BridgeConfig(port="COM4", auto_reconnect=False))
                self.state(BridgeState.ENDPOINT_CONNECTED)
                channel = getattr(self, source)
                if operation == "read":
                    channel.incoming.put(failure)
                else:
                    channel.write_error = failure
                    peer = self.serial if source == "endpoint" else self.endpoint
                    peer.incoming.put(b"command")
                self.state(BridgeState.FAILED)
                self.assertIn(expected, bridge.snapshot.reason)
                self.assertTrue(self.serial.closed.is_set())
                self.assertTrue(self.endpoint.closed.is_set())

    def test_short_writes_preserve_order_and_zero_progress_fails_without_replay(self):
        bridge = self.make_bridge()
        self.serial.write_limit = 2
        self.endpoint.write_limit = 1
        bridge.start(BridgeConfig(port="COM4", auto_reconnect=False))
        self.state(BridgeState.ENDPOINT_CONNECTED)
        self.serial.incoming.put(b"abcdef")
        self.endpoint.incoming.put(b"123456")
        wait_until(lambda: self.endpoint.output == b"abcdef")
        wait_until(lambda: self.serial.output == b"123456")
        self.endpoint.write_limit = 0
        self.serial.incoming.put(b"do not replay")
        self.state(BridgeState.FAILED)
        self.assertIn("delivery may be partial", bridge.snapshot.reason)
        self.assertEqual(self.endpoint.output, b"abcdef")

    def test_cleanup_deadline_also_applies_to_terminal_failure(self):
        bridge = self.make_bridge()
        self.serial.close_gate.clear()
        self.endpoint.open_error = "connection refused"
        bridge.start(BridgeConfig(port="COM4", auto_reconnect=False))
        self.state(BridgeState.STOP_INCOMPLETE)
        self.assertIn("connection refused", bridge.snapshot.reason)
        self.assertFalse(bridge.snapshot.can_start)
        self.serial.close_gate.set()
        self.state(BridgeState.FAILED)

    def test_stop_during_blocked_read_does_not_forward_late_bytes(self):
        bridge = self.make_bridge()
        self.endpoint.read_gate.clear()
        self.endpoint.incoming.put(b"late bytes")
        bridge.start(BridgeConfig(port="COM4", auto_reconnect=False))
        self.assertTrue(self.endpoint.read_entered.wait(1))
        bridge.stop()
        self.state(BridgeState.STOP_INCOMPLETE)
        self.assertFalse(self.endpoint.closed.is_set())
        self.endpoint.read_gate.set()
        self.state(BridgeState.STOPPED)
        self.assertEqual(self.serial.output, b"")

    def test_real_tcp_endpoint_preserves_bytes_and_eof_ends_run(self):
        bridge = self.make_bridge()
        listener = socket.socket()
        self.addCleanup(listener.close)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(1)
        bridge = self.bridge = Bridge(serial_factory=lambda config: self.serial)
        self.addCleanup(self.cleanup_bridge, bridge, self.serial, self.endpoint)
        bridge.start(BridgeConfig(port="COM4", auto_reconnect=False, endpoint_host="127.0.0.1",
                                  endpoint_port=listener.getsockname()[1]))
        peer, _ = listener.accept()
        self.addCleanup(peer.close)
        peer.settimeout(1)
        self.state(BridgeState.ENDPOINT_CONNECTED)
        peer.sendall(b"\x00\xffreply\r\n")
        wait_until(lambda: self.serial.output == b"\x00\xffreply\r\n")
        self.serial.incoming.put(b"\xff\x00command\n")
        data = b""
        while len(data) < 10:
            data += peer.recv(1024)
        self.assertEqual(data, b"\xff\x00command\n")
        peer.shutdown(socket.SHUT_RDWR)
        peer.close()
        self.state(BridgeState.FAILED)
        self.assertIn("Endpoint closed", bridge.snapshot.reason)
        self.assertTrue(self.serial.closed.is_set())

    def test_thread_exhaustion_rolls_back_and_allows_manual_retry(self):
        for available_threads in (0, 1):
            with self.subTest(available_threads=available_threads):
                bridge = self.make_bridge()
                original_start = threading.Thread.start
                remaining = available_threads

                def limited_start(thread):
                    nonlocal remaining
                    if remaining == 0:
                        raise RuntimeError("cannot start new thread")
                    remaining -= 1
                    original_start(thread)

                with patch.object(threading.Thread, "start", limited_start):
                    bridge.start(BridgeConfig(port="COM4", auto_reconnect=False))
                    self.state(BridgeState.FAILED)
                    self.assertIn("cannot start new thread", bridge.snapshot.reason)
                bridge.start(BridgeConfig(port="COM4", auto_reconnect=False))
                self.state(BridgeState.ENDPOINT_CONNECTED)
                self.finish()


if __name__ == "__main__":
    unittest.main()
