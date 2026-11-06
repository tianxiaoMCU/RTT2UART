"""Real Qt event-loop integration with controlled external I/O, no hardware."""
import os
import pickle
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QThread, QTimer
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QLabel

from main_window import MainWindow, DeviceSeleteDialog
from device_catalog import CatalogSnapshot, DeviceCatalog
from tests.test_device_catalog import FIXTURE
from rtt2uart import Bridge, BridgeState
from tests.fakes import Channel, Clock, Probe, wait_until


class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        previous = os.getcwd()
        os.chdir(self.directory.name)
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(os.chdir, previous)
        self.serial = Channel()
        self.endpoint = Channel()
        self.clock = Clock()
        self.bridge = Bridge(serial_factory=lambda config: self.serial,
                             transport_factory=lambda config: self.endpoint,
                             cleanup_timeout=0.05, clock=self.clock)
        self.probe = Mock()
        self.probe._library._path = None
        self.catalog = Mock()
        self.catalog.snapshot = CatalogSnapshot('fallback', (
            ('Test', 'STM32F407VG', 'Cortex-M4', '1', '1 MB', '128 KB'),
            ('Test', 'STM32F103C8', 'Cortex-M3', '1', '64 KB', '0 KB')), 'Controlled missing tools')
        self.catalog.busy = False
        for target, value in (("main_window.DeviceCatalog", Mock(return_value=self.catalog)),
                              ("main_window.pylink.JLink", Mock(return_value=self.probe)),
                              ("main_window.serial.tools.list_ports.comports", Mock(return_value=[])),
                              ("main_window.Bridge", Mock(return_value=self.bridge))):
            context = patch(target, value)
            context.start()
            self.addCleanup(context.stop)
        self.window = MainWindow()
        self.window.ui.comboBox_Port.addItem("COM4")
        self.window.ui.radioButton_existing.click()
        self.assertTrue(self.window.ui.checkBox__auto.isChecked())
        self.window.ui.checkBox__auto.setChecked(False)
        self.window.show()
        self.addCleanup(self.finish)

    def pump_until(self, predicate):
        def check():
            self.app.processEvents()
            return predicate()
        wait_until(check)

    def finish(self):
        self.endpoint.open_gate.set()
        self.serial.close_gate.set()
        self.bridge.stop()
        self.pump_until(lambda: self.bridge.snapshot.can_start)
        self.dispose_window()

    def dispose_window(self):
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def click_start(self):
        self.window.ui.pushButton_Start.click()

    def test_start_transfer_stop_restart_and_failed_start_recovery(self):
        self.endpoint.open_gate.clear()
        self.click_start()
        self.assertIn("Starting", self.window.status_label.text())
        self.assertFalse(self.window.ui.comboBox_Port.isEnabled())
        self.assertFalse(self.window.ui.checkBox__auto.isEnabled())
        self.assertFalse(self.window.ui.radioButton_usb.isEnabled())
        heartbeat = []
        QTimer.singleShot(0, lambda: heartbeat.append(QThread.currentThread()))
        self.pump_until(lambda: bool(heartbeat))
        self.assertEqual(heartbeat[0], self.app.thread())
        self.endpoint.open_gate.set()
        self.pump_until(lambda: "Target state unverified" in self.window.status_label.text())
        self.serial.incoming.put(b"\x00cmd\xff")
        self.endpoint.incoming.put(b"\xffreply\x00")
        self.pump_until(lambda: self.endpoint.output == b"\x00cmd\xff")
        self.pump_until(lambda: self.serial.output == b"\xffreply\x00")
        self.click_start()
        self.pump_until(lambda: self.window.ui.pushButton_Start.text() == "Start")
        self.endpoint.open_error = "connection refused"
        self.click_start()
        self.pump_until(lambda: "connection refused" in self.window.status_label.text())
        self.assertTrue(self.window.ui.comboBox_Port.isEnabled())
        self.endpoint.open_error = None
        self.click_start()
        self.pump_until(lambda: "Target state unverified" in self.window.status_label.text())
        for method in ("open", "connect", "reset", "rtt_stop", "close"):
            getattr(self.probe, method).assert_not_called()

    def test_window_close_waits_for_late_connection_cleanup(self):
        self.endpoint.open_gate.clear()
        self.click_start()
        self.assertTrue(self.endpoint.opened.wait(1))
        self.window.close()
        self.assertTrue(self.window.isVisible())
        self.pump_until(lambda: "Stop incomplete" in self.window.status_label.text())
        self.assertFalse(self.window.ui.comboBox_Port.isEnabled())
        self.assertFalse(self.window.ui.pushButton_Start.isEnabled())
        self.endpoint.open_gate.set()
        self.pump_until(lambda: not self.window.isVisible())
        self.assertTrue(self.serial.closed.is_set())
        self.assertTrue(self.endpoint.closed.is_set())
        self.assertEqual(self.endpoint.output, b"")
        self.assertTrue(os.path.exists("settings"))

    def use_usb(self):
        self.usb_probe = Probe()
        context = patch('pylink.JLink', side_effect=lambda: self.usb_probe)
        context.start()
        self.addCleanup(context.stop)
        self.bridge = Bridge(serial_factory=lambda config: self.serial, cleanup_timeout=0.05,
                             clock=self.clock)
        self.window._bridge = self.bridge
        self.window.ui.radioButton_usb.click()
        self.window.ui.comboBox_Device.addItem('STM32F407VG')
        self.window.ui.comboBox_Interface.setCurrentText('SWD')
        self.window.ui.comboBox_Speed.setCurrentText('4000 kHz')
        def release():
            for gate in self.usb_probe.gates.values():
                gate.set()
            self.usb_probe.errors.clear()
        self.addCleanup(release)

    def test_usb_uses_common_lifecycle_identity_and_per_mode_defaults(self):
        self.use_usb()
        self.assertFalse(self.window.ui.checkBox__auto.isChecked())
        self.assertTrue(self.window.ui.checkBox__auto.isEnabled())
        self.usb_probe.block('connect')
        self.click_start()
        self.assertIn('Starting', self.window.status_label.text())
        for control in [self.window.ui.comboBox_Device, self.window.ui.checkBox_resettarget,
                        self.window.ui.comboBox_Speed, self.window.ui.radioButton_existing]:
            self.assertFalse(control.isEnabled())
        heartbeat = []
        QTimer.singleShot(0, lambda: heartbeat.append(True))
        self.pump_until(lambda: heartbeat)
        self.usb_probe.gates['connect'].set()
        self.pump_until(lambda: 'Running' in self.window.status_label.text())
        self.assertIn('123456', self.window.status_label.text())
        self.serial.incoming.put(b'cmd')
        self.usb_probe.input.put(b'reply')
        self.pump_until(lambda: self.usb_probe.output == b'cmd')
        self.pump_until(lambda: self.serial.output == b'reply')
        self.click_start()
        self.pump_until(lambda: self.window.ui.pushButton_Start.text() == 'Start')
        self.assertTrue(self.usb_probe.closed.is_set())
        self.window.ui.radioButton_existing.click()
        self.assertTrue(self.window.ui.checkBox__auto.isChecked())
        self.assertTrue(self.window.ui.checkBox__auto.isEnabled())

    def test_visible_usb_recovery_retains_probe_discards_and_mode_defaults(self):
        self.use_usb()
        self.window.ui.checkBox__auto.setChecked(True)
        self.window.ui.checkBox_resettarget.setChecked(True)
        self.click_start()
        self.pump_until(lambda: 'Running' in self.window.status_label.text())
        original = self.usb_probe
        self.assertEqual(original.resets, [(0, False)])
        self.usb_probe = Probe()
        self.usb_probe.block('connect')
        original.target_available = False
        self.pump_until(lambda: 'Reconnecting' in self.window.status_label.text())
        self.assertIn('123456', self.window.status_label.text())
        self.serial.incoming.put(b'old')
        self.pump_until(lambda: 'Observed discarded input: 3 bytes' in self.window.status_label.text())
        self.clock.advance(1)
        self.pump_until(lambda: self.usb_probe.entered['connect'].is_set())
        self.serial.incoming.put(b'during connect')
        self.pump_until(lambda: 'Observed discarded input: 17 bytes' in self.window.status_label.text())
        self.assertFalse(self.window.ui.checkBox__auto.isEnabled())
        self.assertFalse(self.window.ui.radioButton_existing.isEnabled())
        self.assertFalse(self.serial.closed.is_set())
        self.usb_probe.gates['connect'].set()
        self.pump_until(lambda: 'Running' in self.window.status_label.text())
        self.assertEqual(self.usb_probe.requested_serial, 123456)
        self.assertEqual(self.usb_probe.resets, [])
        self.serial.incoming.put(b'new')
        self.pump_until(lambda: self.usb_probe.output == b'new')
        self.click_start()
        self.pump_until(lambda: self.window.ui.pushButton_Start.text() == 'Start')
        self.assertTrue(self.window.ui.checkBox__auto.isEnabled())
        self.assertTrue(self.window.ui.checkBox__auto.isChecked())
        self.window.ui.radioButton_existing.click()
        self.assertTrue(self.window.ui.checkBox__auto.isChecked())
        self.window.ui.radioButton_usb.click()
        self.assertFalse(self.window.ui.checkBox__auto.isChecked())
        self.assertTrue(self.window.ui.checkBox__auto.isEnabled())

    def test_visible_usb_cancel_and_window_close_wait_for_delayed_recovery(self):
        self.use_usb()
        self.window.ui.checkBox__auto.setChecked(True)
        self.click_start()
        self.pump_until(lambda: 'Running' in self.window.status_label.text())
        original = self.usb_probe
        self.usb_probe = Probe()
        self.usb_probe.block('connect')
        original.target_available = False
        self.pump_until(lambda: 'Reconnecting' in self.window.status_label.text())
        self.serial.incoming.put(b'x')
        self.pump_until(lambda: self.bridge.snapshot.discarded_bytes == 1)
        self.clock.advance(1)
        self.pump_until(lambda: self.usb_probe.entered['connect'].is_set())
        self.click_start()
        self.assertIn('Stopping', self.window.status_label.text())
        self.window.close()
        self.pump_until(lambda: 'Stop incomplete' in self.window.status_label.text())
        self.assertTrue(self.window.isVisible())
        self.assertFalse(self.window.ui.pushButton_Start.isEnabled())
        self.assertFalse(self.window.ui.checkBox__auto.isEnabled())
        heartbeat = []
        QTimer.singleShot(0, lambda: heartbeat.append(True))
        self.pump_until(lambda: heartbeat)
        self.usb_probe.gates['connect'].set()
        self.pump_until(lambda: not self.window.isVisible())
        self.assertEqual(self.usb_probe.output, b'')
        self.assertEqual(self.usb_probe.concurrent_calls, [])
        self.assertTrue(self.usb_probe.closed.is_set())
        self.assertTrue(self.serial.closed.is_set())
        self.assertEqual(self.bridge.snapshot.state, BridgeState.STOPPED)

    def test_usb_window_close_during_native_connect_defers_until_cleanup(self):
        self.use_usb()
        self.usb_probe.block('connect')
        self.click_start()
        self.pump_until(lambda: self.usb_probe.entered['connect'].is_set())
        self.window.close()
        self.pump_until(lambda: 'Stop incomplete' in self.window.status_label.text())
        self.assertTrue(self.window.isVisible())
        self.assertFalse(self.window.ui.pushButton_Start.isEnabled())
        self.usb_probe.gates['connect'].set()
        self.pump_until(lambda: not self.window.isVisible())
        self.assertTrue(self.usb_probe.closed.is_set())
        self.assertEqual(self.usb_probe.concurrent_calls, [])
        self.assertEqual(self.usb_probe.output, b'')

    def test_usb_failure_is_visible_then_manual_restart_works(self):
        self.use_usb()
        self.usb_probe.target_available = False
        self.click_start()
        self.pump_until(lambda: 'Failed' in self.window.status_label.text())
        self.assertIn('Target debug', self.window.status_label.text())
        self.assertTrue(self.window.ui.comboBox_Device.isEnabled())
        self.usb_probe.target_available = True
        self.click_start()
        self.pump_until(lambda: 'Running' in self.window.status_label.text())

    def test_visible_recovery_discards_and_reconnects_through_real_bridge(self):
        self.window.ui.checkBox__auto.setChecked(True)
        self.click_start()
        self.pump_until(lambda: "Target state unverified" in self.window.status_label.text())
        previous = self.endpoint
        self.endpoint = Channel()
        self.endpoint.open_gate.clear()
        previous.incoming.put(b"")
        self.pump_until(lambda: "Reconnecting" in self.window.status_label.text())
        self.serial.incoming.put(b"old")
        self.pump_until(lambda: "Observed discarded input: 3 bytes" in self.window.status_label.text())
        self.clock.advance(1)
        self.pump_until(lambda: self.endpoint.opened.is_set())
        self.serial.incoming.put(b"during connect")
        self.pump_until(lambda: "Observed discarded input: 17 bytes" in self.window.status_label.text())
        self.assertFalse(self.window.ui.checkBox__auto.isEnabled())
        self.assertFalse(self.serial.closed.is_set())
        self.endpoint.open_gate.set()
        self.pump_until(lambda: "Target state unverified" in self.window.status_label.text())
        self.serial.incoming.put(b"new")
        self.pump_until(lambda: self.endpoint.output == b"new")
        self.assertEqual(previous.output, b"")
        for method in ("open", "connect", "reset", "rtt_stop", "close"):
            getattr(self.probe, method).assert_not_called()

    def test_close_during_delayed_reconnect_uses_same_stop_and_cleanup(self):
        self.window.ui.checkBox__auto.setChecked(True)
        self.click_start()
        self.pump_until(lambda: "Target state unverified" in self.window.status_label.text())
        previous = self.endpoint
        self.endpoint = Channel()
        self.endpoint.open_gate.clear()
        previous.incoming.put(b"")
        self.pump_until(lambda: "Reconnecting" in self.window.status_label.text())
        self.serial.incoming.put(b"x")
        self.pump_until(lambda: self.bridge.snapshot.discarded_bytes == 1)
        self.clock.advance(1)
        self.pump_until(lambda: self.endpoint.opened.is_set())
        self.click_start()
        self.window.close()
        self.pump_until(lambda: "Stop incomplete" in self.window.status_label.text())
        self.assertTrue(self.window.isVisible())
        self.assertFalse(self.window.ui.pushButton_Start.isEnabled())
        self.endpoint.open_gate.set()
        self.pump_until(lambda: not self.window.isVisible())
        self.assertEqual(self.endpoint.output, b"")
        self.assertTrue(self.endpoint.closed.is_set())
        self.assertTrue(self.serial.closed.is_set())
    def test_escape_during_stopping_waits_for_resource_release(self):
        self.click_start()
        self.pump_until(lambda: "Target state unverified" in self.window.status_label.text())
        self.serial.close_gate.clear()
        self.click_start()
        self.window.reject()
        self.assertTrue(self.window.isVisible())
        self.pump_until(lambda: "Stop incomplete" in self.window.status_label.text())
        self.serial.close_gate.set()
        self.pump_until(lambda: not self.window.isVisible())
        self.assertTrue(self.serial.closed.is_set())

    def choose_catalog_target(self, row=0, accept=True):
        def choose():
            dialog = self.app.activeModalWidget()
            if row is not None:
                index = dialog.ui.tableView.model().index(row, 0)
                dialog.ui.tableView.setCurrentIndex(index)
                dialog.ui.tableView.clicked.emit(index)
            button = QDialogButtonBox.Ok if accept else QDialogButtonBox.Cancel
            dialog.ui.buttonBox.button(button).click()
        QTimer.singleShot(0, choose)
        self.window.ui.pushButton_Selete_Device.click()

    def test_legacy_history_selection_survives_catalog_reselection_and_restart(self):
        self.dispose_window()
        legacy = {'device': ['STM32F407VG', 'STM32F103C8'], 'device_index': 1,
                  'interface': 1, 'speed': 10, 'port': 1, 'buadrate': 12}
        Path('settings').write_bytes(pickle.dumps(legacy, protocol=4))
        with patch('main_window.serial.tools.list_ports.comports',
                   return_value=[('COM4',), ('COM5',)]), patch('main_window.serial.Serial'):
            self.window = MainWindow()
        self.window.show()
        self.assertEqual(self.window.ui.comboBox_Device.currentText(), 'STM32F103C8')
        self.choose_catalog_target(row=0)
        self.assertEqual(self.window.ui.comboBox_Device.currentText(), 'STM32F407VG')
        self.dispose_window()
        with patch('main_window.serial.tools.list_ports.comports',
                   return_value=[('COM4',), ('COM5',)]), patch('main_window.serial.Serial'):
            self.window = MainWindow()
        self.assertEqual(self.window.ui.comboBox_Device.currentText(), 'STM32F407VG')
        self.assertEqual(self.window.ui.comboBox_Device.count(), 2)
        self.assertEqual(self.window.ui.comboBox_Interface.currentText(), 'SWD')
        self.assertEqual(self.window.ui.comboBox_Speed.currentText(), '600 kHz')
        self.assertEqual(self.window.ui.comboBox_baudrate.currentText(), '9600')
        self.assertEqual(self.window.ui.comboBox_Port.currentText(), 'COM5')
        self.assertFalse(self.window.windowIcon().pixmap(16, 16).isNull())
        self.assertFalse(self.window.ui.checkBox__auto.isChecked())
        self.assertEqual(set(pickle.loads(Path('settings').read_bytes())), set(legacy))

    def test_cancelled_or_empty_catalog_choice_keeps_saved_target(self):
        self.window.ui.radioButton_usb.click()
        self.choose_catalog_target(row=0)
        for row, accept in ((1, False), (None, False), (None, True)):
            with self.subTest(row=row, accept=accept):
                self.choose_catalog_target(row=row, accept=accept)
                self.assertEqual(self.window.ui.comboBox_Device.currentText(), 'STM32F407VG')
                self.assertEqual(self.window.ui.comboBox_Device.count(), 1)
                self.dispose_window()
                self.window = MainWindow()
                self.window.show()
                self.assertEqual(self.window.ui.comboBox_Device.currentText(), 'STM32F407VG')
                self.assertEqual(self.window.ui.comboBox_Device.count(), 1)

    def test_catalog_loading_same_dialog_completion_retry_and_gui_thread(self):
        self.catalog.snapshot = CatalogSnapshot()
        dialog = DeviceSeleteDialog(self.catalog, self.window)
        dialog.show()
        self.assertIn('Loading', dialog.ui.label_catalog_status.text())
        self.assertFalse(dialog.ui.tableView.isEnabled())
        self.assertFalse(dialog.ui.pushButton_retry.isEnabled())
        self.assertIsNone(dialog.get_target_device())
        saved = self.window.settings.copy()
        calls = []
        original = QLabel.setText
        def observe(label, text):
            if label is dialog.ui.label_catalog_status:
                calls.append(QThread.currentThread())
            return original(label, text)
        with patch.object(QLabel, 'setText', observe):
            self.catalog.snapshot = CatalogSnapshot('fallback', (
                ('Test', 'NEW', 'Core', '1', '0 KB', '0 KB'),), 'Commander timeout')
            self.pump_until(lambda: dialog.ui.tableView.isEnabled())
        self.assertEqual(dialog.ui.tableView.model().rowCount(None), 1)
        self.assertIn('Unverified', dialog.ui.label_catalog_status.text())
        self.assertIn('Commander timeout', dialog.ui.label_catalog_status.text())
        self.assertTrue(all(thread == self.app.thread() for thread in calls))
        self.assertEqual(self.window.settings, saved)
        dialog.ui.pushButton_retry.click()
        self.catalog.prepare.assert_called_with(retry=True)
        dialog.close()
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.catalog.snapshot = CatalogSnapshot('error', reason='No usable list')
        other = DeviceSeleteDialog(self.catalog, self.window)
        self.addCleanup(other.close)
        self.assertFalse(other.ui.tableView.isEnabled())
        self.assertIn('No usable list', other.ui.label_catalog_status.text())
        self.assertTrue(other.ui.pushButton_retry.isEnabled())

    def test_real_catalog_task_shared_across_dialogs_does_not_block_bridge_or_close(self):
        entered, release = threading.Event(), threading.Event()
        calls = []
        def missing():
            calls.append(True)
            entered.set()
            release.wait(2)
            raise OSError('Controlled missing library')
        catalog = DeviceCatalog(cache_dir=Path(self.directory.name) / 'cache',
                                baseline=FIXTURE, resolve_source=missing)
        self.addCleanup(catalog.close)
        self.addCleanup(release.set)
        self.window._catalog = catalog
        catalog.prepare()
        self.assertTrue(entered.wait(1))
        first = DeviceSeleteDialog(catalog, self.window)
        first.show()
        first.close()
        first.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        second = DeviceSeleteDialog(catalog, self.window)
        second.show()
        self.assertIn('Loading', second.ui.label_catalog_status.text())
        self.click_start()
        self.pump_until(lambda: 'Target state unverified' in self.window.status_label.text())
        release.set()
        self.pump_until(lambda: second.ui.tableView.isEnabled())
        self.assertIn('Controlled missing library', second.ui.label_catalog_status.text())
        self.assertEqual(second.ui.tableView.model().rowCount(None), 2)
        self.assertEqual(len(calls), 1)
        second.close()
        self.click_start()
        self.pump_until(lambda: self.bridge.snapshot.can_start)
        self.window.close()
        self.pump_until(lambda: not self.window.isVisible())
        self.assertFalse(catalog.busy)

    def test_background_lifecycle_and_discard_text_are_delivered_on_gui_thread(self):
        calls = []
        set_text = QLabel.setText
        def observe(label, text):
            if label is self.window.status_label:
                calls.append((text, QThread.currentThread()))
            return set_text(label, text)
        with patch.object(QLabel, 'setText', observe):
            self.window.ui.checkBox__auto.setChecked(True)
            self.click_start()
            self.pump_until(lambda: 'Target state unverified' in self.window.status_label.text())
            self.endpoint.incoming.put(b'')
            self.pump_until(lambda: 'Reconnecting' in self.window.status_label.text())
            self.serial.incoming.put(b'old')
            self.pump_until(lambda: 'Observed discarded input: 3 bytes' in self.window.status_label.text())
            self.click_start()
            self.pump_until(lambda: 'Stopped' in self.window.status_label.text())
        self.assertTrue(any('Target state unverified' in text for text, _ in calls))
        self.assertTrue(any('Observed discarded input: 3 bytes' in text for text, _ in calls))
        self.assertTrue(all(thread == self.app.thread() for _, thread in calls))

    def test_existing_saved_settings_round_trip(self):
        self.window.settings['device'] = ['STM32F407VG']
        self.window.ui.comboBox_Device.addItem('STM32F407VG')
        self.window.ui.comboBox_baudrate.setCurrentIndex(12)
        self.window.ui.comboBox_Speed.setCurrentIndex(10)
        expected = self.window.settings.copy()
        self.dispose_window()
        self.window = MainWindow()
        self.assertEqual(self.window.settings, expected)
        self.assertEqual(self.window.ui.comboBox_Device.currentText(), 'STM32F407VG')
        self.assertEqual(self.window.ui.comboBox_baudrate.currentText(), '9600')
        self.assertEqual(self.window.ui.comboBox_Speed.currentText(), '600 kHz')
        self.assertFalse(self.window.ui.checkBox__auto.isChecked())


if __name__ == "__main__":
    unittest.main()
