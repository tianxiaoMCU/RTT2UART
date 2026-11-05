"""Recovery acceptance through the public GUI-to-bridge seam."""
import unittest
import socket

from rtt2uart import Bridge, BridgeConfig, BridgeState
from tests.fakes import Channel, Clock, wait_until


class ScriptedWrites(Channel):
    def __init__(self, results):
        super().__init__()
        self.results = iter(results)

    def write(self, data):
        result = next(self.results, len(data))
        if isinstance(result, Exception):
            raise result
        self.output.extend(data[:result])
        return result


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.serial = Channel()
        self.endpoints = [Channel() for _ in range(8)]
        self.attempts = []

        def connect(config):
            endpoint = self.endpoints[len(self.attempts)]
            self.attempts.append((self.clock(), config))
            return endpoint

        self.bridge = Bridge(serial_factory=lambda config: self.serial,
                             transport_factory=connect, clock=self.clock,
                             cleanup_timeout=0.05)
        self.addCleanup(self.finish)

    def finish(self):
        self.bridge.stop()
        for channel in [self.serial, *self.endpoints]:
            channel.open_gate.set()
            channel.close_gate.set()
            channel.read_gate.set()
            channel.close_error = None
        wait_until(lambda: self.bridge.snapshot.can_start)

    def state(self, state):
        wait_until(lambda: self.bridge.snapshot.state == state)

    def start(self):
        config = BridgeConfig(port="COM4")
        self.assertTrue(config.auto_reconnect)
        self.bridge.start(config)
        self.state(BridgeState.ENDPOINT_CONNECTED)
        return config

    def test_delayed_reconnect_drains_host_input_and_forwards_only_new_bytes(self):
        config = self.start()
        self.endpoints[1].open_gate.clear()
        self.endpoints[0].incoming.put(b"")
        self.state(BridgeState.RECONNECTING)
        self.serial.incoming.put(b"outage")
        wait_until(lambda: self.bridge.snapshot.discarded_bytes == 6)
        self.clock.advance(1)
        self.assertTrue(self.endpoints[1].opened.wait(1))
        self.serial.incoming.put(b"slow connect")
        wait_until(lambda: self.bridge.snapshot.discarded_bytes == 18)
        self.assertFalse(self.serial.closed.is_set())
        self.assertIs(self.attempts[1][1], config)
        self.endpoints[1].open_gate.set()
        self.state(BridgeState.ENDPOINT_CONNECTED)
        self.assertEqual(self.bridge.snapshot.discarded_bytes, 18)
        self.serial.incoming.put(b"new\x00\xff")
        self.endpoints[1].incoming.put(b"reply\xff\x00")
        wait_until(lambda: self.endpoints[1].output == b"new\x00\xff")
        wait_until(lambda: self.serial.output == b"reply\xff\x00")
        self.assertEqual(self.endpoints[0].output, b"")

    def test_retry_schedule_is_unlimited_and_resets_after_recovery(self):
        self.start()
        for channel in self.endpoints[1:4]:
            channel.open_error = "refused"
        self.endpoints[0].incoming.put(b"")
        self.state(BridgeState.RECONNECTING)
        for index, (delay, expected) in enumerate(((1, 1), (2, 3), (5, 8), (5, 13)), 1):
            # Receiving the marker proves the serial owner is processing this
            # recovery phase. Time does not advance unless this test moves it.
            count = self.bridge.snapshot.discarded_bytes
            self.serial.incoming.put(b"x")
            wait_until(lambda: self.bridge.snapshot.discarded_bytes == count + 1)
            self.clock.advance(delay - 0.01)
            self.serial.incoming.put(b"y")
            wait_until(lambda: self.bridge.snapshot.discarded_bytes == count + 2)
            self.assertEqual(len(self.attempts), index)
            self.clock.advance(0.01)
            self.assertTrue(self.endpoints[index].opened.wait(1))
            self.assertAlmostEqual(self.attempts[index][0], expected)
            if index < 4:
                wait_until(lambda: self.endpoints[index].closed.is_set())
        self.state(BridgeState.ENDPOINT_CONNECTED)
        self.endpoints[4].incoming.put(OSError("read failed"))
        self.state(BridgeState.RECONNECTING)
        count = self.bridge.snapshot.discarded_bytes
        self.serial.incoming.put(b"next outage")
        wait_until(lambda: self.bridge.snapshot.discarded_bytes == count + 11)
        self.clock.advance(1)
        self.state(BridgeState.ENDPOINT_CONNECTED)
        self.assertEqual(self.attempts[5][0], 14)

    def test_first_start_failure_is_terminal_even_when_recovery_is_enabled(self):
        self.endpoints[0].open_error = "refused"
        self.bridge.start(BridgeConfig(port="COM4"))
        self.state(BridgeState.FAILED)
        self.clock.advance(100)
        self.assertEqual(len(self.attempts), 1)
        self.assertTrue(self.serial.closed.is_set())
        self.assertTrue(self.endpoints[0].closed.is_set())
        self.assertIn("refused", self.bridge.snapshot.reason)

    def test_stop_during_wait_never_attempts_another_connection(self):
        self.start()
        self.endpoints[0].incoming.put(b"")
        self.state(BridgeState.RECONNECTING)
        self.bridge.stop()
        self.bridge.stop()
        self.state(BridgeState.STOPPED)
        self.clock.advance(100)
        self.assertEqual(len(self.attempts), 1)
        self.assertTrue(self.serial.closed.is_set())

    def test_stop_during_connect_cleans_late_result_without_forwarding(self):
        self.start()
        self.endpoints[1].open_gate.clear()
        self.endpoints[0].incoming.put(b"")
        self.state(BridgeState.RECONNECTING)
        self.serial.incoming.put(b"x")
        wait_until(lambda: self.bridge.snapshot.discarded_bytes == 1)
        self.clock.advance(1)
        self.assertTrue(self.endpoints[1].opened.wait(1))
        self.bridge.stop()
        self.bridge.stop()
        self.state(BridgeState.STOP_INCOMPLETE)
        with self.assertRaises(RuntimeError):
            self.bridge.start(BridgeConfig(port="COM5"))
        self.endpoints[1].incoming.put(b"late reply")
        self.serial.incoming.put(b"late command")
        self.assertFalse(self.endpoints[1].closed.is_set())
        self.endpoints[1].open_gate.set()
        self.state(BridgeState.STOPPED)
        self.assertTrue(self.endpoints[1].closed.is_set())
        self.assertTrue(self.serial.closed.is_set())
        self.assertEqual(self.endpoints[1].output, b"")
        self.assertEqual(self.serial.output, b"")

    def test_short_writes_and_transient_zero_progress_preserve_order(self):
        self.endpoints[0] = ScriptedWrites([1, 0, 2, 0, 1])
        self.start()
        self.serial.incoming.put(b"abcdef\x00\xff")
        wait_until(lambda: self.endpoints[0].output == b"abcdef\x00\xff")
        self.assertEqual(self.bridge.snapshot.state, BridgeState.ENDPOINT_CONNECTED)
        self.assertEqual(self.bridge.snapshot.discarded_bytes, 0)

    def test_uncertain_partial_send_is_never_replayed_or_counted_as_definite_loss(self):
        self.endpoints[0] = ScriptedWrites([2, OSError("send failed")])
        self.start()
        self.serial.incoming.put(b"command")
        self.state(BridgeState.RECONNECTING)
        self.assertEqual(self.endpoints[0].output, b"co")
        self.assertIn("delivery may be partial", self.bridge.snapshot.reason)
        self.assertEqual(self.bridge.snapshot.discarded_bytes, 0)
        self.serial.incoming.put(b"discard")
        wait_until(lambda: self.bridge.snapshot.discarded_bytes == 7)
        self.clock.advance(1)
        self.state(BridgeState.ENDPOINT_CONNECTED)
        self.serial.incoming.put(b"fresh")
        wait_until(lambda: self.endpoints[1].output == b"fresh")
        self.assertEqual(self.bridge.snapshot.discarded_bytes, 7)

    def test_repeated_zero_progress_is_bounded_and_recoverable(self):
        self.endpoints[0].write_limit = 0
        self.start()
        self.serial.incoming.put(b"uncertain")
        self.state(BridgeState.RECONNECTING)
        self.assertIn("no valid progress", self.bridge.snapshot.reason)
        self.serial.incoming.put(b"x")
        wait_until(lambda: self.bridge.snapshot.discarded_bytes == 1)
        self.clock.advance(1)
        self.state(BridgeState.ENDPOINT_CONNECTED)
        self.serial.incoming.put(b"fresh")
        wait_until(lambda: self.endpoints[1].output == b"fresh")
        self.assertEqual(self.endpoints[0].output, b"")

    def delayed_connect_with_blocked_serial_read(self):
        self.start()
        self.endpoints[1].open_gate.clear()
        self.endpoints[0].incoming.put(b"")
        self.state(BridgeState.RECONNECTING)
        self.serial.incoming.put(b"x")
        wait_until(lambda: self.bridge.snapshot.discarded_bytes == 1)
        self.clock.advance(1)
        self.assertTrue(self.endpoints[1].opened.wait(1))
        self.serial.read_gate.clear()
        self.serial.read_entered.clear()
        self.assertTrue(self.serial.read_entered.wait(1))

    def test_inflight_read_and_pending_input_are_discarded_before_recovery_handoff(self):
        self.delayed_connect_with_blocked_serial_read()
        self.serial.incoming.put(b"in flight")
        self.serial.incoming.put(b"queued")
        self.endpoints[1].open_gate.set()
        self.assertEqual(self.bridge.snapshot.state, BridgeState.RECONNECTING)
        self.serial.read_gate.set()
        self.state(BridgeState.ENDPOINT_CONNECTED)
        self.assertEqual(self.bridge.snapshot.discarded_bytes, 16)
        self.serial.incoming.put(b"fresh")
        wait_until(lambda: self.endpoints[1].output == b"fresh")

    def test_stop_during_blocked_handoff_rejects_late_input(self):
        self.delayed_connect_with_blocked_serial_read()
        self.endpoints[1].open_gate.set()
        self.bridge.stop()
        self.state(BridgeState.STOP_INCOMPLETE)
        self.serial.incoming.put(b"late")
        self.serial.read_gate.set()
        self.state(BridgeState.STOPPED)
        self.assertEqual(self.endpoints[1].output, b"")
        self.assertTrue(self.endpoints[1].closed.is_set())

    def test_serial_failure_during_wait_or_connect_is_terminal(self):
        for connecting in (False, True):
            with self.subTest(connecting=connecting):
                self.start()
                self.endpoints[1].open_gate.clear()
                self.endpoints[0].incoming.put(b"")
                self.state(BridgeState.RECONNECTING)
                if connecting:
                    count = self.bridge.snapshot.discarded_bytes
                    self.serial.incoming.put(b"x")
                    wait_until(lambda: self.bridge.snapshot.discarded_bytes == count + 1)
                    self.clock.advance(1)
                    self.assertTrue(self.endpoints[1].opened.wait(1))
                self.serial.incoming.put(OSError("serial removed"))
                if connecting:
                    self.state(BridgeState.STOP_INCOMPLETE)
                    self.assertIn("Serial read", self.bridge.snapshot.reason)
                    self.endpoints[1].open_gate.set()
                self.state(BridgeState.FAILED)
                self.assertIn("serial removed", self.bridge.snapshot.reason)
                self.assertTrue(self.serial.closed.is_set())
                self.assertEqual(len(self.attempts), 2 if connecting else 1)
                if not connecting:
                    # New controlled run for the second scenario.
                    self.finish()
                    self.setUp()

    def test_failed_endpoint_cleanup_during_recovery_inhibits_restart(self):
        self.start()
        self.endpoints[0].close_error = "close failed"
        self.endpoints[0].incoming.put(b"")
        self.state(BridgeState.STOP_INCOMPLETE)
        self.assertIn("close failed", self.bridge.snapshot.cleanup_error)
        with self.assertRaises(RuntimeError):
            self.bridge.start(BridgeConfig(port="COM5"))
        self.assertTrue(self.serial.closed.wait(1))
        self.endpoints[0].close_error = None
        self.bridge.stop()
        self.state(BridgeState.STOPPED)
        self.assertEqual(len(self.attempts), 1)

    def test_real_tcp_adapter_reconnects_without_replaying_outage_input(self):
        listener = socket.socket()
        self.addCleanup(listener.close)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(1)
        self.bridge = Bridge(serial_factory=lambda config: self.serial,
                             clock=self.clock, cleanup_timeout=0.05)
        self.bridge.start(BridgeConfig(port="COM4", endpoint_host="127.0.0.1",
                                       endpoint_port=listener.getsockname()[1]))
        peer, _ = listener.accept()
        self.addCleanup(peer.close)
        self.state(BridgeState.ENDPOINT_CONNECTED)
        peer.shutdown(socket.SHUT_RDWR)
        peer.close()
        self.state(BridgeState.RECONNECTING)
        self.serial.incoming.put(b"old")
        wait_until(lambda: self.bridge.snapshot.discarded_bytes == 3)
        self.clock.advance(1)
        restored, _ = listener.accept()
        self.addCleanup(restored.close)
        restored.settimeout(1)
        self.state(BridgeState.ENDPOINT_CONNECTED)
        self.serial.incoming.put(b"new\x00\xff")
        received = b""
        while len(received) < 5:
            received += restored.recv(1024)
        self.assertEqual(received, b"new\x00\xff")
        restored.sendall(b"reply\xff\x00")
        wait_until(lambda: self.serial.output == b"reply\xff\x00")


if __name__ == "__main__":
    unittest.main()
