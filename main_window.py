import sys
from PySide6.QtWidgets import QApplication, QDialog, QHeaderView, QAbstractItemView, QLabel
from PySide6 import QtCore
from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QLocalSocket, QLocalServer
from ui_rtt2uart import Ui_dialog
from ui_sel_device import Ui_Dialog
import rc_icons

import serial.tools.list_ports
import serial
import pylink
from rtt2uart import Bridge, BridgeConfig, BridgeState, USBConfig
import logging
import pickle
import os
from device_catalog import DeviceCatalog

logging.basicConfig(level=logging.NOTSET,
                    format='%(asctime)s - [%(levelname)s] (%(filename)s:%(lineno)d) - %(message)s')
logger = logging.getLogger(__name__)

# pylink supports up to 12000 kHz (15000 kHz and above since release v0.7.0).
speed_list = [5, 10, 20, 30, 50, 100, 200, 300, 400, 500, 600, 750,
              900, 1000, 1334, 1600, 2000, 2667, 3200, 4000, 4800, 5334, 6000, 8000, 9600, 12000,
              15000, 20000, 25000, 30000, 40000, 50000]

baudrate_list = [50, 75, 110, 134, 150, 200, 300, 600, 1200, 1800, 2400, 4800,
                 9600, 19200, 38400, 57600, 115200, 230400, 460800, 500000, 576000, 921600]


class DeviceTableModel(QtCore.QAbstractTableModel):
    def __init__(self, deice_list, header):
        super(DeviceTableModel, self).__init__()

        self.mylist = deice_list
        self.header = header

    def rowCount(self, parent):
        return len(self.mylist)

    def columnCount(self, parent):
        return len(self.header)

    def data(self, index, role):
        if not index.isValid():
            return None
        elif role != QtCore.Qt.DisplayRole:
            return None

        return self.mylist[index.row()][index.column()]

        return None

    def headerData(self, col, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self.header[col]
        return None


class DeviceSeleteDialog(QDialog):
    def __init__(self, catalog, parent=None):
        super(DeviceSeleteDialog, self).__init__(parent)
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowIcon(QIcon(":/swap_horiz_16px.ico"))
        self._catalog = catalog
        self._target = None
        self._last_catalog = None
        self.devices_list = ()
        self.ui.tableView.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.ui.tableView.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.ui.tableView.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ui.tableView.clicked.connect(self.reflash_selete_device)
        self.ui.pushButton_retry.clicked.connect(self._retry_catalog)
        self._catalog_timer = QtCore.QTimer(self)
        self._catalog_timer.setInterval(20)
        self._catalog_timer.timeout.connect(self._render_catalog)
        self._catalog_timer.start()
        self._render_catalog()

    def _retry_catalog(self):
        self._catalog.prepare(retry=True)
        self._render_catalog()

    def _render_catalog(self):
        result = self._catalog.snapshot
        if result is self._last_catalog:
            return
        self._last_catalog = result
        self._target = None
        self.ui.label_sel_dev.clear()
        self.devices_list = result.records
        self._model = DeviceTableModel(self.devices_list, [
            "Manufacturer", "Device", "Core", "NumCores", "Flash Size", "RAM Size"])
        self.ui.tableView.setModel(self._model)
        for column, width in enumerate((100, 280, 140, 70, 70, 70)):
            self.ui.tableView.setColumnWidth(column, width)
        loading = result.state == 'loading'
        self.ui.tableView.setEnabled(bool(result.records) and not loading)
        self.ui.pushButton_retry.setEnabled(not loading)
        if loading:
            message = 'Loading Target device list...'
        elif result.state == 'fallback':
            message = 'Unverified fallback device list. ' + result.reason
        elif result.state == 'error':
            message = 'Device list unavailable. ' + result.reason
        else:
            message = 'Device list ready (source matched). Target support is checked on connection.'
        self.ui.label_catalog_status.setText(message)
        self.ui.label_catalog_status.setToolTip(message)

    def done(self, result):
        self._catalog_timer.stop()
        super().done(result)

    def reflash_selete_device(self):
        index = self.ui.tableView.currentIndex()
        if index.isValid() and self.ui.tableView.isEnabled():
            self._target = self.devices_list[index.row()][1]
            self.ui.label_sel_dev.setText(self._target)

    def get_target_device(self):
        return self._target


class MainWindow(QDialog):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = Ui_dialog()
        self.ui.setupUi(self)

        self.setWindowIcon(QIcon(":/swap_horiz_16px.ico"))

        self.setting_file_path = os.path.join(os.getcwd(), "settings")

        self.target_device = None
        self._bridge = Bridge()
        self._close_pending = False
        self._last_snapshot = self._bridge.snapshot
        self.setFixedSize(402, 445)
        self.status_label = QLabel("Stopped", self)
        self.status_label.setGeometry(10, 350, 382, 85)
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        self._status_timer = QtCore.QTimer(self)
        self._status_timer.setInterval(20)
        self._status_timer.timeout.connect(self._poll_bridge)
        self._status_timer.start()
        # Select USB by default.
        self.ui.radioButton_usb.setChecked(True)
        self.usb_selete_slot()

        self.ui.comboBox_Interface.addItem("JTAG")
        self.ui.comboBox_Interface.addItem("SWD")
        self.ui.comboBox_Interface.addItem("cJTAG")
        self.ui.comboBox_Interface.addItem("FINE")

        for i in range(len(speed_list)):
            self.ui.comboBox_Speed.addItem(str(speed_list[i]) + " kHz")

        for i in range(len(baudrate_list)):
            self.ui.comboBox_baudrate.addItem(str(baudrate_list[i]))

        self.port_scan()

        self.settings = {'device': [], 'device_index': 0, 'interface': 0,
                         'speed': 0, 'port': 0, 'buadrate': 0}

        # Load the previous configuration if it exists.
        if os.path.exists(self.setting_file_path) == True:
            with open(self.setting_file_path, 'rb') as f:
                self.settings = pickle.load(f)

            f.close()

            # Apply the saved configuration.
            if len(self.settings['device']):
                self.ui.comboBox_Device.addItems(self.settings['device'])
                self.target_device = self.settings['device'][self.settings['device_index']]
            self.ui.comboBox_Device.setCurrentIndex(
                self.settings['device_index'])
            self.ui.comboBox_Interface.setCurrentIndex(
                self.settings['interface'])
            self.ui.comboBox_Speed.setCurrentIndex(self.settings['speed'])
            self.ui.comboBox_Port.setCurrentIndex(self.settings['port'])
            self.ui.comboBox_baudrate.setCurrentIndex(
                self.settings['buadrate'])
        else:
            logger.info('Setting file not exist', exc_info=True)
            self.ui.comboBox_Interface.setCurrentIndex(1)
            self.settings['interface'] = 1
            self.ui.comboBox_Speed.setCurrentIndex(19)
            self.settings['speed'] = 19
            self.ui.comboBox_baudrate.setCurrentIndex(16)
            self.settings['buadrate'] = 16

        # Connect signals to slots.
        self.ui.pushButton_Start.clicked.connect(self.start)
        self.ui.pushButton_scan.clicked.connect(self.port_scan)
        self.ui.pushButton_Selete_Device.clicked.connect(
            self.target_device_selete)
        self.ui.comboBox_Device.currentIndexChanged.connect(
            self.device_change_slot)
        self.ui.comboBox_Interface.currentIndexChanged.connect(
            self.interface_change_slot)
        self.ui.comboBox_Speed.currentIndexChanged.connect(
            self.speed_change_slot)
        self.ui.comboBox_Port.currentIndexChanged.connect(
            self.port_change_slot)
        self.ui.comboBox_baudrate.currentIndexChanged.connect(
            self.buadrate_change_slot)
        self.ui.checkBox_serialno.stateChanged.connect(
            self.serial_no_change_slot)
        self.ui.radioButton_usb.clicked.connect(self.usb_selete_slot)
        self.ui.radioButton_existing.clicked.connect(
            self.existing_session_selete_slot)

        self._catalog = DeviceCatalog()
        self._catalog.prepare()

    def reject(self):
        # QDialog's Escape key must obey the same cleanup contract as window close.
        self.close()

    def closeEvent(self, e):
        self._catalog.close(wait=False)
        if not self._bridge.snapshot.can_start or self._catalog.busy:
            self._close_pending = True
            self._bridge.stop()
            self._render_bridge(self._bridge.snapshot)
            e.ignore()
            return

        # Save the current configuration.
        with open(self.setting_file_path, 'wb') as f:
            pickle.dump(self.settings, f)

        f.close()

        self._status_timer.stop()
        e.accept()

    def port_scan(self):
        port_list = list(serial.tools.list_ports.comports())
        self.ui.comboBox_Port.clear()
        port_list.sort()
        for port in port_list:
            try:
                s = serial.Serial(port[0])
                s.close()
                self.ui.comboBox_Port.addItem(port[0])
            except (OSError, serial.SerialException):
                pass

    def start(self):
        if not self._bridge.snapshot.can_start:
            self._bridge.stop()
            self._render_bridge(self._bridge.snapshot)
            return
        try:
            usb = None
            if self.ui.radioButton_usb.isChecked():
                interfaces = {'JTAG': pylink.enums.JLinkInterfaces.JTAG,
                              'SWD': pylink.enums.JLinkInterfaces.SWD,
                              'FINE': pylink.enums.JLinkInterfaces.FINE}
                selected = self.ui.comboBox_Interface.currentText()
                if selected not in interfaces:
                    raise ValueError(f'{selected} is not supported by pylink 1.2.0')
                serial_number = (int(self.ui.lineEdit_serialno.text())
                                 if self.ui.checkBox_serialno.isChecked() else None)
                usb = USBConfig(target=self.target_device or '',
                                interface=interfaces[selected],
                                speed=speed_list[self.ui.comboBox_Speed.currentIndex()],
                                serial_number=serial_number,
                                startup_reset=self.ui.checkBox_resettarget.isChecked())
            config = BridgeConfig(port=self.ui.comboBox_Port.currentText(),
                                  baudrate=int(self.ui.comboBox_baudrate.currentText()),
                                  auto_reconnect=self.ui.checkBox__auto.isChecked(), usb=usb)
            self._render_bridge(self._bridge.start(config))
        except (ValueError, RuntimeError) as error:
            self.status_label.setText(str(error))
            self.ui.pushButton_Start.setChecked(False)

    def _poll_bridge(self):
        snapshot = self._bridge.snapshot
        if snapshot != self._last_snapshot:
            self._render_bridge(snapshot)
        if self._close_pending and snapshot.can_start and not self._catalog.busy:
            self.close()

    def _render_bridge(self, snapshot):
        # Called only by GUI slots/QTimer; no background code touches widgets.
        self._last_snapshot = snapshot
        active = not snapshot.can_start
        self.status_label.setText("\n".join(filter(None, (
            snapshot.state.value,
            f"USB probe: {snapshot.probe_serial_number}" if snapshot.probe_serial_number else "",
            snapshot.reason, snapshot.cleanup_error,
            f"Observed discarded input: {snapshot.discarded_bytes} bytes"))))
        self.status_label.setToolTip(self.status_label.text())
        self.ui.pushButton_Start.setText("Stop" if active else "Start")
        self.ui.pushButton_Start.setChecked(active)
        self.ui.pushButton_Start.setEnabled(
            snapshot.state not in (BridgeState.STOPPING, BridgeState.STOP_INCOMPLETE))
        for control in (self.ui.radioButton_usb, self.ui.radioButton_existing,
                        self.ui.checkBox_serialno,
                        self.ui.lineEdit_serialno, self.ui.comboBox_Port,
                        self.ui.comboBox_baudrate, self.ui.pushButton_scan):
            control.setEnabled(not active)
        self.ui.checkBox__auto.setEnabled(not active)
        target_enabled = not active and self.ui.radioButton_usb.isChecked()
        for control in (self.ui.comboBox_Device, self.ui.pushButton_Selete_Device,
                        self.ui.comboBox_Interface, self.ui.comboBox_Speed,
                        self.ui.checkBox_resettarget):
            control.setEnabled(target_enabled)

    def target_device_selete(self):
        device_ui = DeviceSeleteDialog(self._catalog, self)
        accepted = device_ui.exec() == QDialog.Accepted
        target = device_ui.get_target_device() if accepted else None
        device_ui.deleteLater()
        if not target:
            return
        self.target_device = target

        if self.target_device not in self.settings['device']:
            self.settings['device'].append(self.target_device)
            self.ui.comboBox_Device.addItem(self.target_device)
        self.ui.comboBox_Device.setCurrentIndex(
            self.settings['device'].index(self.target_device))

    def device_change_slot(self, index):
        self.settings['device_index'] = index
        self.target_device = self.ui.comboBox_Device.currentText()

    def interface_change_slot(self, index):
        self.settings['interface'] = index

    def speed_change_slot(self, index):
        self.settings['speed'] = index

    def port_change_slot(self, index):
        self.settings['port'] = index

    def buadrate_change_slot(self, index):
        self.settings['buadrate'] = index

    def serial_no_change_slot(self):
        if self.ui.checkBox_serialno.isChecked():
            self.ui.lineEdit_serialno.setVisible(True)
        else:
            self.ui.lineEdit_serialno.setVisible(False)

    def usb_selete_slot(self):

        self.ui.checkBox__auto.setVisible(True)
        self.ui.checkBox__auto.setChecked(False)
        self.ui.checkBox__auto.setEnabled(True)
        self.ui.checkBox__auto.setToolTip("Reconnect only to the original USB probe without repeating startup reset")
        self.ui.lineEdit_ip.setVisible(False)
        self.ui.checkBox_serialno.setVisible(True)
        self.serial_no_change_slot()
        # Re-enable Target controls for USB mode.
        self.ui.comboBox_Device.setEnabled(True)
        self.ui.pushButton_Selete_Device.setEnabled(True)
        self.ui.comboBox_Interface.setEnabled(True)
        self.ui.comboBox_Speed.setEnabled(True)
        self.ui.checkBox_resettarget.setEnabled(True)

    def existing_session_selete_slot(self):

        self.ui.checkBox_serialno.setVisible(False)
        self.ui.lineEdit_serialno.setVisible(False)
        self.ui.lineEdit_ip.setVisible(False)
        self.ui.checkBox__auto.setVisible(True)
        self.ui.checkBox__auto.setChecked(True)
        self.ui.checkBox__auto.setEnabled(True)
        self.ui.checkBox__auto.setToolTip("")
        # Disable Target controls that do not apply to Existing Session mode.
        self.ui.comboBox_Device.setEnabled(False)
        self.ui.pushButton_Selete_Device.setEnabled(False)
        self.ui.comboBox_Interface.setEnabled(False)
        self.ui.comboBox_Speed.setEnabled(False)
        self.ui.checkBox_resettarget.setEnabled(False)
        self.ui.checkBox_resettarget.setChecked(False)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    serverName = 'myuniqueservername'
    lsocket = QLocalSocket()
    lsocket.connectToServer(serverName)

    # A successful connection means another application instance is already running.
    if lsocket.waitForConnected(200) == False:

        # No instance is running; create the local server.
        localServer = QLocalServer()
        localServer.listen(serverName)

        try:
            window = MainWindow()
            window.setWindowTitle("RTT2UART Control Panel V2.0.0")
            window.show()

            sys.exit(app.exec())
        finally:
            localServer.close()
