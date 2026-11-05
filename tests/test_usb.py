"""USB lifecycle tests at the common bridge seam, with controlled native I/O."""
import os
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from pylink import JLink as PinnedJLink
from pylink.jlock import JLock as PinnedLock

from rtt2uart import Bridge, BridgeConfig, BridgeState, USBConfig
from tests.fakes import Channel, Clock, Probe, wait_until


class USBTests(unittest.TestCase):
    def setUp(self):
        self.configure_probe = lambda probe: None
        self.clock = Clock()
        self.serials = []
        self.probes = []
        def serial_factory(config):
            serial = Channel()
            self.serials.append(serial)
            return serial
        def probe_factory():
            probe = Probe()
            self.configure_probe(probe)
            self.probes.append(probe)
            return probe
        context = patch('pylink.JLink', side_effect=probe_factory)
        context.start()
        self.addCleanup(context.stop)
        # No USB run may fall back to the external TCP listener.
        context = patch('socket.socket', side_effect=AssertionError('USB used TCP'))
        context.start()
        self.addCleanup(context.stop)
        self.bridge = Bridge(serial_factory=serial_factory, cleanup_timeout=0.05,
                             clock=self.clock)
        self.addCleanup(self.finish)

    def finish(self):
        self.bridge.stop()
        for serial in self.serials:
            serial.read_gate.set()
        for probe in self.probes:
            for gate in probe.gates.values():
                gate.set()
            probe.errors.clear()
        self.bridge.stop()
        wait_until(lambda: self.bridge.snapshot.can_start)

    def state(self, state):
        wait_until(lambda: self.bridge.snapshot.state == state)

    def test_owned_usb_start_transfer_stop_and_manual_restart(self):
        config = BridgeConfig(port='COM4', usb=USBConfig(target='STM32F407VG',
                                                        interface=1, speed=4000))
        self.assertEqual(self.bridge.start(config).state, BridgeState.STARTING)
        self.state(BridgeState.RUNNING)
        self.assertEqual(self.bridge.snapshot.probe_serial_number, 123456)
        probe, serial = self.probes[-1], self.serials[-1]
        self.assertIsNone(probe.requested_serial)
        self.assertEqual(probe.connection, ('STM32F407VG', 4000))
        self.assertEqual(probe.interface, 1)
        self.assertEqual(probe.resets, [])
        serial.incoming.put(b'\x00cmd\xff')
        probe.input.put(b'\xffreply\x00')
        wait_until(lambda: probe.output == b'\x00cmd\xff')
        wait_until(lambda: serial.output == b'\xffreply\x00')
        self.bridge.stop()
        self.state(BridgeState.STOPPED)
        self.assertTrue(probe.closed.is_set())
        self.assertFalse(probe.rtt_active)
        self.assertTrue(serial.closed.is_set())
        self.bridge.start(config)
        self.state(BridgeState.RUNNING)
        self.assertEqual(len(self.probes), 2)
        self.assertEqual(self.probes[-1].output, b'')

    def test_recovery_pins_observed_probe_preserves_settings_and_does_not_reset(self):
        config = BridgeConfig(port='COM4', auto_reconnect=True, usb=USBConfig(
            target='STM32F407VG', interface=0, speed=1000, startup_reset=True))
        self.bridge.start(config)
        self.state(BridgeState.RUNNING)
        original, serial = self.probes[-1], self.serials[-1]
        self.assertIsNone(original.requested_serial)
        self.assertEqual(original.resets, [(0, False)])
        original.target_available = False
        self.state(BridgeState.RECONNECTING)
        serial.incoming.put(b'old')
        wait_until(lambda: self.bridge.snapshot.discarded_bytes == 3)
        self.clock.advance(1)
        self.state(BridgeState.RUNNING)
        recovered = self.probes[-1]
        self.assertIsNot(recovered, original)
        self.assertEqual(recovered.requested_serial, 123456)
        self.assertEqual(self.bridge.snapshot.probe_serial_number, 123456)
        self.assertEqual(recovered.connection, ('STM32F407VG', 1000))
        self.assertEqual(recovered.interface, 0)
        self.assertEqual(recovered.resets, [])
        self.assertTrue(recovered.rtt_active)
        self.assertTrue(original.closed.is_set())
        self.assertEqual(len(self.serials), 1)
        self.assertFalse(serial.closed.is_set())
        self.assertIsNone(config.usb.serial_number)
        self.assertTrue(config.usb.startup_reset)
        serial.incoming.put(b'new\x00\xff')
        recovered.input.put(b'reply\xff\x00')
        wait_until(lambda: recovered.output == b'new\x00\xff')
        wait_until(lambda: serial.output == b'reply\xff\x00')
        self.finish()
        self.assertEqual(recovered.concurrent_calls, [])
        self.assertTrue(recovered.closed.is_set())

    def start_recoverable(self):
        config = BridgeConfig(port='COM4', auto_reconnect=True, usb=USBConfig(
            target='STM32F407VG', startup_reset=True))
        self.bridge.start(config)
        self.state(BridgeState.RUNNING)
        return config

    def lose_transport(self):
        self.probes[-1].errors['rtt_read'] = OSError('probe disconnected')
        self.state(BridgeState.RECONNECTING)
        self.discard_marker()

    def discard_marker(self):
        count = self.bridge.snapshot.discarded_bytes
        self.serials[-1].incoming.put(b'x')
        wait_until(lambda: self.bridge.snapshot.discarded_bytes == count + 1)

    def test_other_probe_never_forwards_and_retry_schedule_restarts_each_outage(self):
        self.start_recoverable()
        attempt_times = []
        def configure(probe):
            attempt_times.append(self.clock())
            if len(attempt_times) <= 3:
                # Even if a native implementation returns the other probe,
                # the production adapter must reject its observed identity.
                probe.actual_serial = 987654
        self.configure_probe = configure
        self.lose_transport()
        for index, delay in enumerate((1, 2, 5, 5), 1):
            self.clock.advance(delay - 0.01)
            self.discard_marker()
            self.assertEqual(len(attempt_times), index - 1)
            self.clock.advance(0.01)
            wait_until(lambda: len(self.probes) == index + 1)
            if index < 4:
                wait_until(lambda: 'identity mismatch' in self.bridge.snapshot.reason)
                self.discard_marker()
                other = self.probes[-1]
                self.assertEqual(other.requested_serial, 123456)
                self.assertTrue(other.closed.is_set())
                self.assertEqual(other.output, b'')
                self.assertIsNone(other.connection)
                self.assertEqual(self.bridge.snapshot.state, BridgeState.RECONNECTING)
                self.assertEqual(self.bridge.snapshot.probe_serial_number, 123456)
        self.state(BridgeState.RUNNING)
        self.assertEqual(attempt_times, [1, 3, 8, 13])
        self.lose_transport()
        self.clock.advance(1)
        self.state(BridgeState.RUNNING)
        self.assertEqual(attempt_times, [1, 3, 8, 13, 14])
        self.assertTrue(all(p.requested_serial == 123456 for p in self.probes[1:]))
        self.assertTrue(all(p.resets == [] for p in self.probes[1:]))
        self.assertEqual(len(self.serials), 1)

    def test_slow_native_recovery_discards_inflight_read_before_new_forwarding(self):
        self.start_recoverable()
        self.configure_probe = lambda probe: probe.block('connect')
        self.lose_transport()
        self.clock.advance(1)
        wait_until(lambda: len(self.probes) == 2 and self.probes[-1].entered['connect'].is_set())
        recovered, serial = self.probes[-1], self.serials[-1]
        self.discard_marker()
        self.assertFalse(serial.closed.is_set())
        count = self.bridge.snapshot.discarded_bytes
        serial.read_gate.clear()
        serial.read_entered.clear()
        self.assertTrue(serial.read_entered.wait(1))
        serial.incoming.put(b'inflight')
        recovered.gates['connect'].set()
        wait_until(lambda: 'rtt_get_buf_descriptor' in recovered.entered)
        self.assertEqual(self.bridge.snapshot.state, BridgeState.RECONNECTING)
        serial.read_gate.set()
        self.state(BridgeState.RUNNING)
        self.assertEqual(self.bridge.snapshot.discarded_bytes, count + 8)
        self.assertEqual(recovered.output, b'')
        serial.incoming.put(b'new')
        wait_until(lambda: recovered.output == b'new')
        self.assertEqual(recovered.concurrent_calls, [])

    def test_recovery_requires_target_and_both_usable_rtt_channels(self):
        for field, value, operation in [
                ('target_available', False, 'target_connected'),
                ('up_count', 0, 'rtt_get_num_up_buffers'),
                ('down_count', 0, 'rtt_get_num_down_buffers'),
                ('buffer_size', 1, 'rtt_get_buf_descriptor')]:
            with self.subTest(field=field):
                self.configure_probe = lambda probe: None
                self.start_recoverable()
                before = len(self.probes)
                self.configure_probe = lambda probe: setattr(probe, field, value)
                self.lose_transport()
                self.clock.advance(1)
                wait_until(lambda: len(self.probes) > before and operation in self.probes[-1].entered)
                self.assertEqual(self.bridge.snapshot.state, BridgeState.RECONNECTING)
                self.discard_marker()
                if field != 'target_available':
                    self.clock.advance(3)
                wait_until(lambda: self.probes[-1].closed.is_set())
                wait_until(lambda: 'USB reconnect:' in self.bridge.snapshot.reason)
                self.assertEqual(self.probes[-1].output, b'')
                self.assertEqual(self.probes[-1].resets, [])
                self.configure_probe = lambda probe: None
                self.discard_marker()
                self.clock.advance(2)
                self.state(BridgeState.RUNNING)
                self.finish()

    def test_stop_cancels_usb_retry_wait_and_all_delayed_native_stages(self):
        for operation in [None, 'open', 'connect', 'rtt_get_buf_descriptor']:
            with self.subTest(operation=operation):
                self.configure_probe = lambda probe: None
                config = self.start_recoverable()
                before = len(self.probes)
                if operation:
                    self.configure_probe = lambda probe: probe.block(operation)
                self.lose_transport()
                if operation:
                    self.clock.advance(1)
                    wait_until(lambda: len(self.probes) > before and
                               self.probes[-1].entered[operation].is_set())
                    self.discard_marker()
                self.bridge.stop()
                self.bridge.stop()
                if operation:
                    self.state(BridgeState.STOP_INCOMPLETE)
                    with self.assertRaises(RuntimeError):
                        self.bridge.start(config)
                    self.assertFalse(self.probes[-1].closed.is_set())
                    self.probes[-1].gates[operation].set()
                self.state(BridgeState.STOPPED)
                self.clock.advance(100)
                self.assertEqual(len(self.probes), before + bool(operation))
                self.assertTrue(self.probes[-1].closed.is_set())
                self.assertEqual(self.probes[-1].output, b'')
                self.assertEqual(self.probes[-1].concurrent_calls, [])
                self.assertTrue(self.serials[-1].closed.is_set())
                if operation:
                    self.assertEqual(self.probes[-1].resets, [])

    def test_native_close_during_recovery_keeps_draining_before_and_after_attempt(self):
        for failed_attempt in (False, True):
            with self.subTest(failed_attempt=failed_attempt):
                self.configure_probe = lambda probe: None
                config = self.start_recoverable()
                before = len(self.probes)
                if failed_attempt:
                    def configure(probe):
                        probe.target_available = False
                        probe.block('close')
                    self.configure_probe = configure
                else:
                    self.probes[-1].block('close')
                self.probes[-1].errors['rtt_read'] = OSError('probe disconnected')
                self.state(BridgeState.RECONNECTING)
                if failed_attempt:
                    self.discard_marker()
                    self.clock.advance(1)
                    wait_until(lambda: len(self.probes) > before)
                closing = self.probes[-1]
                wait_until(lambda: closing.entered['close'].is_set())
                self.discard_marker()
                self.assertFalse(self.serials[-1].closed.is_set())
                self.bridge.stop()
                self.state(BridgeState.STOP_INCOMPLETE)
                with self.assertRaises(RuntimeError):
                    self.bridge.start(config)
                self.assertEqual(closing.concurrent_calls, [])
                closing.gates['close'].set()
                self.state(BridgeState.STOPPED)
                self.assertTrue(closing.closed.is_set())
                self.assertEqual(closing.concurrent_calls, [])
                self.assertEqual(len(self.probes), before + failed_attempt)

    def test_recovery_cleanup_failure_prevents_restart_and_retries_only_release(self):
        config = self.start_recoverable()
        self.configure_probe = lambda probe: probe.block('connect')
        self.lose_transport()
        self.clock.advance(1)
        wait_until(lambda: len(self.probes) == 2 and self.probes[-1].entered['connect'].is_set())
        recovered = self.probes[-1]
        recovered.errors['close'] = OSError('native close failed')
        self.bridge.stop()
        recovered.gates['connect'].set()
        self.state(BridgeState.STOP_INCOMPLETE)
        wait_until(lambda: 'native close failed' in self.bridge.snapshot.cleanup_error)
        with self.assertRaises(RuntimeError):
            self.bridge.start(config)
        self.assertEqual(recovered.concurrent_calls, [])
        self.assertEqual(recovered.output, b'')
        recovered.errors.clear()
        self.bridge.stop()
        self.state(BridgeState.STOPPED)
        self.assertTrue(recovered.closed.is_set())
        self.assertEqual(len(self.probes), 2)

    def test_enabled_recovery_keeps_startup_and_serial_failures_terminal(self):
        for failure in ['startup', 'serial_read', 'serial_write', 'recovery_serial_read']:
            with self.subTest(failure=failure):
                self.configure_probe = lambda probe: None
                if failure == 'startup':
                    self.configure_probe = lambda probe: probe.errors.update(
                        {'open': OSError('initial open failed')})
                    self.bridge.start(BridgeConfig(port='COM4', auto_reconnect=True,
                                      usb=USBConfig(target='STM32F407VG')))
                else:
                    self.start_recoverable()
                    if failure == 'recovery_serial_read':
                        self.configure_probe = lambda probe: probe.block('connect')
                        before = len(self.probes)
                        self.lose_transport()
                        self.clock.advance(1)
                        wait_until(lambda: len(self.probes) > before and
                                   self.probes[-1].entered['connect'].is_set())
                    if failure == 'serial_write':
                        self.serials[-1].write_error = 'serial lost'
                        self.probes[-1].input.put(b'reply')
                    else:
                        self.serials[-1].incoming.put(OSError('serial lost'))
                    if failure == 'recovery_serial_read':
                        self.state(BridgeState.STOP_INCOMPLETE)
                        self.probes[-1].gates['connect'].set()
                self.state(BridgeState.FAILED)
                self.assertIn('initial open failed' if failure == 'startup' else 'Serial',
                              self.bridge.snapshot.reason)
                before = len(self.probes)
                self.clock.advance(100)
                self.assertEqual(len(self.probes), before)
                self.assertTrue(self.serials[-1].closed.is_set())
                self.assertTrue(self.probes[-1].closed.is_set())

    def test_recovery_abandons_uncertain_tail_and_bounded_zero_progress(self):
        self.start_recoverable()
        probe, serial = self.probes[-1], self.serials[-1]
        probe.write_limit = 2
        probe.write_results.put(0)
        probe.write_results.put(1)
        serial.incoming.put(b'abcdef')
        wait_until(lambda: probe.output == b'abcdef')
        probe.write_results.put(2)
        probe.write_results.put(OSError('uncertain delivery'))
        serial.incoming.put(b'command')
        self.state(BridgeState.RECONNECTING)
        self.assertEqual(probe.output, b'abcdefco')
        self.assertIn('delivery may be partial', self.bridge.snapshot.reason)
        self.assertEqual(self.bridge.snapshot.discarded_bytes, 0)
        self.discard_marker()
        self.clock.advance(1)
        self.state(BridgeState.RUNNING)
        recovered = self.probes[-1]
        self.assertEqual(recovered.output, b'')
        recovered.write_limit = 0
        serial.incoming.put(b'never replay')
        self.state(BridgeState.RECONNECTING)
        self.assertIn('no valid progress', self.bridge.snapshot.reason)
        self.discard_marker()
        self.clock.advance(1)
        self.state(BridgeState.RUNNING)
        serial.incoming.put(b'new')
        wait_until(lambda: self.probes[-1].output == b'new')
        self.assertEqual(recovered.output, b'')

    def test_identity_must_be_usable_and_match_explicit_selection(self):
        for actual, requested in [(0, None), (None, None), ('123456', None),
                                  (True, None), (123456, 987654)]:
            with self.subTest(actual=actual, requested=requested):
                self.configure_probe = lambda probe: setattr(probe, 'actual_serial', actual)
                self.bridge.start(BridgeConfig(port='COM4', usb=USBConfig(
                    target='STM32F407VG', serial_number=requested)))
                self.state(BridgeState.FAILED)
                probe = self.probes[-1]
                self.assertTrue(probe.closed.is_set())
                self.assertTrue(self.serials[-1].closed.is_set())
                self.assertIsNone(probe.connection)
                self.assertEqual(probe.requested_serial, requested)
                self.assertIn('identity', self.bridge.snapshot.reason)


    def test_stop_during_native_startup_waits_without_late_reset_or_forwarding(self):
        for operation in ['open', 'set_tif', 'connect', 'rtt_start',
                          'rtt_get_buf_descriptor']:
            with self.subTest(operation=operation):
                self.configure_probe = lambda probe: probe.block(operation)
                config = BridgeConfig(port='COM4', usb=USBConfig(
                    target='STM32F407VG', startup_reset=True))
                previous_count = len(self.probes)
                self.bridge.start(config)
                wait_until(lambda: len(self.probes) > previous_count and operation in self.probes[-1].entered
                           and self.probes[-1].entered[operation].is_set())
                probe = self.probes[-1]
                self.bridge.stop()
                self.bridge.stop()
                self.state(BridgeState.STOP_INCOMPLETE)
                with self.assertRaises(RuntimeError):
                    self.bridge.start(config)
                self.assertFalse(probe.closed.is_set())
                self.serials[-1].incoming.put(b'late input')
                probe.gates[operation].set()
                self.state(BridgeState.STOPPED)
                self.assertTrue(probe.closed.is_set())
                self.assertEqual(probe.concurrent_calls, [])
                self.assertEqual(probe.output, b'')
                if operation in ['open', 'set_tif', 'connect']:
                    self.assertEqual(probe.resets, [])


    def test_pinned_wrapper_partial_open_releases_native_handle_and_selection_lock(self):
        # Exercise the installed 1.2.0 wrapper, replacing only its DLL/lock boundary.
        dll = Mock()
        native_open = False
        def open_native(*args):
            nonlocal native_open
            native_open = True
        def close_native():
            nonlocal native_open
            native_open = False
        dll.JLINKARM_OpenEx.side_effect = open_native
        dll.JLINKARM_Close.side_effect = close_native
        dll.JLINKARM_IsOpen.side_effect = lambda: native_open
        dll.JLINKARM_EMU_SelectByUSBSN.return_value = 0
        dll.JLINK_SetHookUnsecureDialog.side_effect = OSError('post-open hook failed')
        library = Mock()
        library.dll.return_value = dll
        probe = PinnedJLink(lib=library)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        lock = PinnedLock(123456)
        lock.path = os.path.join(directory.name, 'probe.lck')
        with patch('pylink.JLink', return_value=probe), \
                patch('pylink.jlink.jlock.JLock', return_value=lock):
            self.bridge.start(BridgeConfig(port='COM4', usb=USBConfig(
                target='STM32F407VG', serial_number=123456)))
            self.state(BridgeState.FAILED)
            self.assertFalse(native_open)
            self.assertFalse(lock.acquired)
            self.assertIn('post-open hook failed', self.bridge.snapshot.reason)


    def test_waits_for_rtt_discovery_before_running_and_bounds_not_ready(self):
        self.configure_probe = lambda probe: setattr(probe, 'down_count', 0)
        config = BridgeConfig(port='COM4', usb=USBConfig(target='STM32F407VG'))
        self.bridge.start(config)
        wait_until(lambda: self.probes and 'rtt_get_num_down_buffers' in self.probes[-1].entered)
        self.assertEqual(self.bridge.snapshot.state, BridgeState.STARTING)
        self.probes[-1].down_count = 1
        self.state(BridgeState.RUNNING)
        self.finish()
        count = len(self.probes)
        self.bridge.start(config)
        wait_until(lambda: len(self.probes) > count and 'rtt_get_num_down_buffers' in self.probes[-1].entered)
        self.clock.advance(3)
        self.state(BridgeState.FAILED)
        self.assertIn('RTT channel 0', self.bridge.snapshot.reason)
        self.assertTrue(self.probes[-1].closed.is_set())


    def test_startup_failures_release_every_acquired_resource(self):
        operations = ['open', 'serial_number', 'set_tif', 'connect', 'reset',
                      'target_connected', 'rtt_start', 'rtt_get_num_up_buffers',
                      'rtt_get_num_down_buffers', 'rtt_get_buf_descriptor']
        for operation in operations:
            with self.subTest(operation=operation):
                self.configure_probe = lambda probe: probe.errors.update(
                    {operation: OSError('failure at ' + operation)})
                self.bridge.start(BridgeConfig(port='COM4', usb=USBConfig(
                    target='STM32F407VG', startup_reset=True)))
                self.state(BridgeState.FAILED)
                self.assertIn('failure at ' + operation, self.bridge.snapshot.reason)
                self.assertTrue(self.probes[-1].closed.is_set())
                self.assertTrue(self.serials[-1].closed.is_set())
                self.assertEqual(self.probes[-1].output, b'')
                self.assertEqual(self.probes[-1].concurrent_calls, [])

    def test_incomplete_target_and_channel_descriptors_never_run(self):
        for field, value in [('target_available', False), ('interface_accepted', False),
                             ('up_count', 0), ('down_count', 0), ('buffer_size', 0),
                             ('buffer_size', 1)]:
            with self.subTest(field=field, value=value):
                self.configure_probe = lambda probe: setattr(probe, field, value)
                previous_count = len(self.probes)
                self.bridge.start(BridgeConfig(port='COM4', usb=USBConfig(target='STM32F407VG')))
                wait_until(lambda: len(self.probes) > previous_count)
                if field in ('up_count', 'down_count', 'buffer_size'):
                    method = {'up_count': 'rtt_get_num_up_buffers',
                              'down_count': 'rtt_get_num_down_buffers',
                              'buffer_size': 'rtt_get_buf_descriptor'}[field]
                    wait_until(lambda: method in self.probes[-1].entered)
                    self.assertEqual(self.bridge.snapshot.state, BridgeState.STARTING)
                    self.clock.advance(3)
                self.state(BridgeState.FAILED)
                self.assertTrue(self.probes[-1].closed.is_set())
                self.assertTrue(self.serials[-1].closed.is_set())

    def test_runtime_usb_and_serial_failures_are_terminal(self):
        cases = ['target_lost', 'channel_lost', 'rtt_read', 'rtt_write',
                 'serial_read', 'serial_write']
        for operation in cases:
            with self.subTest(operation=operation):
                self.bridge.start(BridgeConfig(port='COM4', usb=USBConfig(target='STM32F407VG')))
                self.state(BridgeState.RUNNING)
                probe, serial = self.probes[-1], self.serials[-1]
                if operation == 'target_lost':
                    probe.target_available = False
                elif operation == 'channel_lost':
                    probe.buffer_size = 0
                elif operation == 'serial_read':
                    serial.incoming.put(OSError('serial lost'))
                elif operation == 'serial_write':
                    serial.write_error = 'serial lost'
                    probe.input.put(b'reply')
                else:
                    probe.errors[operation] = OSError('USB lost')
                    serial.incoming.put(b'command')
                self.state(BridgeState.FAILED)
                self.assertTrue(probe.closed.is_set())
                self.assertTrue(serial.closed.is_set())
                self.assertIn('Serial' if operation.startswith('serial') else 'USB RTT',
                              self.bridge.snapshot.reason)

    def test_short_and_zero_writes_preserve_order_and_never_replay_uncertain_tail(self):
        self.configure_probe = lambda probe: setattr(probe, 'write_limit', 2)
        config = BridgeConfig(port='COM4', usb=USBConfig(target='STM32F407VG'))
        self.bridge.start(config)
        self.state(BridgeState.RUNNING)
        probe, serial = self.probes[-1], self.serials[-1]
        probe.write_results.put(0)
        probe.write_results.put(1)
        serial.incoming.put(b'abcdef')
        probe.input.put(b'123456')
        serial.write_limit = 2
        wait_until(lambda: probe.output == b'abcdef')
        wait_until(lambda: serial.output == b'123456')
        probe.write_results.put(2)
        probe.write_results.put(OSError('uncertain delivery'))
        serial.incoming.put(b'command')
        self.state(BridgeState.FAILED)
        self.assertEqual(probe.output, b'abcdefco')
        self.assertIn('delivery may be partial', self.bridge.snapshot.reason)
        self.bridge.start(config)
        self.state(BridgeState.RUNNING)
        self.assertEqual(self.probes[-1].output, b'')
        self.probes[-1].write_limit = 0
        self.serials[-1].incoming.put(b'do not replay')
        self.state(BridgeState.FAILED)
        self.assertIn('no valid progress', self.bridge.snapshot.reason)
        self.assertEqual(self.probes[-1].output, b'')

    def test_explicit_selection_and_initial_reset_are_honored(self):
        self.bridge.start(BridgeConfig(port='COM4', usb=USBConfig(
            target='STM32F407VG', serial_number=123456, interface=0, speed=1000,
            startup_reset=True)))
        self.state(BridgeState.RUNNING)
        probe = self.probes[-1]
        self.assertEqual(probe.requested_serial, 123456)
        self.assertEqual(probe.resets, [(0, False)])
        self.assertEqual(probe.interface, 0)
        self.assertEqual(probe.connection, ('STM32F407VG', 1000))
        self.finish()
        self.assertEqual(probe.resets, [(0, False)])

    def test_failed_close_keeps_restart_locked_until_release(self):
        config = BridgeConfig(port='COM4', usb=USBConfig(target='STM32F407VG'))
        self.bridge.start(config)
        self.state(BridgeState.RUNNING)
        probe = self.probes[-1]
        probe.errors['close'] = OSError('native close failed')
        self.bridge.stop()
        self.state(BridgeState.STOP_INCOMPLETE)
        with self.assertRaises(RuntimeError):
            self.bridge.start(config)
        self.assertTrue(self.serials[-1].closed.wait(1))
        self.assertIn('native close failed', self.bridge.snapshot.cleanup_error)
        probe.errors.clear()
        self.bridge.stop()
        self.state(BridgeState.STOPPED)
        self.assertTrue(probe.closed.is_set())
        self.assertEqual(probe.concurrent_calls, [])

    def test_stop_after_blocked_rtt_read_never_forwards_late_bytes(self):
        self.configure_probe = lambda probe: probe.block('rtt_read')
        self.bridge.start(BridgeConfig(port='COM4', usb=USBConfig(target='STM32F407VG')))
        wait_until(lambda: self.probes and self.probes[-1].entered['rtt_read'].is_set())
        probe = self.probes[-1]
        probe.input.put(b'late')
        self.bridge.stop()
        self.state(BridgeState.STOP_INCOMPLETE)
        probe.gates['rtt_read'].set()
        self.state(BridgeState.STOPPED)
        self.assertEqual(self.serials[-1].output, b'')
        self.assertEqual(probe.concurrent_calls, [])

    def test_usb_recovery_defaults_off_and_invalid_selection_never_opens(self):
        self.assertFalse(BridgeConfig(port='COM4', usb=USBConfig(target='part')).auto_reconnect)
        self.assertTrue(BridgeConfig(port='COM4').auto_reconnect)
        for fields in [dict(target=''), dict(target='part', serial_number=0),
                       dict(target='part', interface=None), dict(target='part', speed=0)]:
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                USBConfig(**fields)
        self.assertEqual(self.serials, [])
        self.assertEqual(self.probes, [])


    def test_lockfile_delete_retry_never_closes_an_already_released_descriptor(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        lock = PinnedLock(123456)
        lock.path = os.path.join(directory.name, 'probe.lck')
        self.assertTrue(lock.acquire())
        descriptor = lock.fd
        self.configure_probe = lambda probe: setattr(probe, '_lock', lock)
        config = BridgeConfig(port='COM4', usb=USBConfig(target='STM32F407VG'))
        self.bridge.start(config)
        self.state(BridgeState.RUNNING)
        allow_remove = threading.Event()
        original_remove = os.remove
        def delayed_remove(path):
            if path == lock.path and not allow_remove.is_set():
                raise PermissionError('lockfile temporarily busy')
            return original_remove(path)
        closes = []
        original_close = os.close
        def checked_close(fd):
            closes.append(fd)
            if closes.count(fd) > 1:
                raise OSError('descriptor already closed')
            original_close(fd)
        with patch('os.remove', side_effect=delayed_remove), patch('os.close', side_effect=checked_close):
            self.bridge.stop()
            self.state(BridgeState.STOP_INCOMPLETE)
            with self.assertRaises(RuntimeError):
                self.bridge.start(config)
            allow_remove.set()
            self.bridge.stop()
            self.state(BridgeState.STOPPED)
            self.assertEqual(closes.count(descriptor), 1)
        self.assertFalse(os.path.exists(lock.path))
        self.assertFalse(lock.acquired)


    def test_unacquired_selection_lock_is_not_removed_on_failed_open(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        lock = PinnedLock(123456)
        lock.path = os.path.join(directory.name, 'other-process.lck')
        with open(lock.path, 'w') as file:
            file.write('other owner')
        def configure(probe):
            probe._lock = lock
            probe.errors['open'] = OSError('probe already owned')
        self.configure_probe = configure
        self.bridge.start(BridgeConfig(port='COM4', usb=USBConfig(
            target='STM32F407VG', serial_number=123456)))
        self.state(BridgeState.FAILED)
        with open(lock.path) as file:
            self.assertEqual(file.read(), 'other owner')
        self.assertFalse(lock.acquired)



if __name__ == '__main__':
    unittest.main()
