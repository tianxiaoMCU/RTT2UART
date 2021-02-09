from pickle import NONE
import sys
from PySide2.QtWidgets import QApplication, QMainWindow, QDialog, QHeaderView, QAbstractItemView, QMessageBox, QSystemTrayIcon, QMenu, QAction
from PySide2.QtCore import QFile, QAbstractTableModel
from PySide2 import QtGui
from PySide2 import QtCore
from PySide2.QtGui import QFont, QIcon
from PySide2.QtNetwork import QLocalSocket, QLocalServer
from ui_rtt2uart import Ui_dialog
from ui_sel_device import Ui_Dialog
import rc_icons

import serial.tools.list_ports
import serial
import ctypes.util as ctypes_util
import xml.etree.ElementTree as ET
import pylink
from rtt2uart import rtt_to_serial
import logging
import pickle
import os

logging.basicConfig(level=logging.NOTSET,
                    format='%(asctime)s - [%(levelname)s] (%(filename)s:%(lineno)d) - %(message)s')
logger = logging.getLogger(__name__)

# pylink支持的最大速率是12000kHz（Release v0.7.0开始支持15000及以上速率）
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
    def __init__(self):
        super(DeviceSeleteDialog, self).__init__()
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        self.setWindowIcon(QIcon(":/swap_horiz_16px.ico"))

        self._target = None

        filepath = self.get_jlink_devices_list_file()
        if filepath != '':
            self.devices_list = self.parse_jlink_devices_list_file(filepath)

        if len(self.devices_list):

            # 从headdata中取出数据，放入到模型中
            headdata = ["Manufacturer", "Device", "Core",
                        "NumCores", "Flash Size", "RAM Size"]

            # 生成一个模型，用来给tableview
            model = DeviceTableModel(self.devices_list, headdata)

            self.ui.tableView.setModel(model)
            # set font
            # font = QFont("Courier New", 9)
            # self.ui.tableView.setFont(font)
            # set column width to fit contents (set font first!)
            self.ui.tableView.resizeColumnsToContents()
            self.ui.tableView.resizeRowsToContents()
            self.ui.tableView.setSelectionBehavior(
                QAbstractItemView.SelectRows)

            self.ui.tableView.clicked.connect(self.reflash_selete_device)

    def get_jlink_devices_list_file(self):
        '''
        lib_jlink = pylink.Library()

        path = ctypes_util.find_library(lib_jlink._sdk)

        if path is None:
            # Couldn't find it the standard way.  Fallback to the non-standard
            # way of finding the J-Link library.  These methods are operating
            # system specific.
            if lib_jlink._windows or lib_jlink._cygwin:
                path = next(lib_jlink.find_library_windows(), None)
            elif sys.platform.startswith('linux'):
                path = next(lib_jlink.find_library_linux(), None)
            elif sys.platform.startswith('darwin'):
                path = next(lib_jlink.find_library_darwin(), None)

            if path is not None:
                path = path.replace(
                    lib_jlink.get_appropriate_windows_sdk_name()+".dll", "JLinkDevices.xml")
            else:
                path = ''
        else:
            path = ''
        '''
        if os.path.exists(r'JLinkDevicesBuildIn.xml') == True:
            return os.path.abspath('JLinkDevicesBuildIn.xml')
        else:
            raise Exception("Can not find device database !")

    def parse_jlink_devices_list_file(self, path):
        parsefile = open(path, 'r')

        tree = ET.ElementTree(file=parsefile)

        jlink_devices_list = []

        for VendorInfo in tree.findall('VendorInfo'):
            for DeviceInfo in VendorInfo.findall('DeviceInfo'):
                device_item = []

                # get Manufacturer
                device_item.append(VendorInfo.attrib['Name'])
                # get Device
                device_item.append(DeviceInfo.attrib['Name'])
                # get Core
                device_item.append(DeviceInfo.attrib['Core'])
                # get NumCores
                # now fix 1
                device_item.append('1')
                # get Flash Size
                flash_size = 0
                for FlashBankInfo in DeviceInfo.findall('FlashBankInfo'):
                    flash_size += int(FlashBankInfo.attrib['Size'], 16)

                flash_size = flash_size // 1024
                if flash_size < 1024:
                    device_item.append(str(flash_size)+' KB')
                else:
                    flash_size = flash_size // 1024
                    device_item.append(str(flash_size)+' MB')
                # get RAM Size
                ram_size = 0
                if 'WorkRAMSize' in DeviceInfo.attrib.keys():
                    ram_size += int(DeviceInfo.attrib['WorkRAMSize'], 16)

                device_item.append(str(ram_size//1024)+' KB')

                # add item to list
                jlink_devices_list.append(device_item)

        parsefile.close()

        return jlink_devices_list

    def reflash_selete_device(self):
        index = self.ui.tableView.currentIndex()
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

        self.start_state = False
        self.target_device = None
        self.rtt2uart = None
        self.connect_type = None
        # 默认Existing Session方式接入使能Auto reconnect
        self.ui.checkBox__auto.setChecked(True)
        # 默认选择'USB'方式接入
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

        # 检查是否存在上次配置，存在则加载
        if os.path.exists(self.setting_file_path) == True:
            with open(self.setting_file_path, 'rb') as f:
                self.settings = pickle.load(f)

            f.close()

            # 应用上次配置
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

        # 信号-槽
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

    def closeEvent(self, e):
        if self.rtt2uart is not None and self.start_state == True:
            self.rtt2uart.stop()

        # 保存当前配置
        with open(self.setting_file_path, 'wb') as f:
            pickle.dump(self.settings, f)

        f.close()

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
        if self.start_state == False:
            logger.debug('click start button')
            try:
                device_interface = None
                # USB或者TCP/IP方式接入需要选择配置
                if not self.ui.radioButton_existing.isChecked():
                    if self.target_device is not None:
                        selete_interface = self.ui.comboBox_Interface.currentText()
                        if (selete_interface == 'JTAG'):
                            device_interface = pylink.enums.JLinkInterfaces.JTAG
                        elif (selete_interface == 'SWD'):
                            device_interface = pylink.enums.JLinkInterfaces.SWD
                        elif (selete_interface == 'cJTAG'):
                            device_interface = None
                        elif (selete_interface == 'FINE'):
                            device_interface = pylink.enums.JLinkInterfaces.FINE
                        else:
                            device_interface = pylink.enums.JLinkInterfaces.SWD

                        # 启动后不能再进行配置
                        self.ui.comboBox_Device.setEnabled(False)
                        self.ui.pushButton_Selete_Device.setEnabled(False)
                        self.ui.comboBox_Interface.setEnabled(False)
                        self.ui.comboBox_Speed.setEnabled(False)
                        self.ui.comboBox_Port.setEnabled(False)
                        self.ui.comboBox_baudrate.setEnabled(False)
                        self.ui.pushButton_scan.setEnabled(False)

                    else:
                        raise Exception("Please selete the target device !")

                # 获取接入方式的参数
                if self.ui.radioButton_usb.isChecked() and self.ui.checkBox_serialno.isChecked():
                    connect_para = self.ui.lineEdit_serialno.text()
                elif self.ui.radioButton_tcpip.isChecked():
                    connect_para = self.ui.lineEdit_ip.text()
                elif self.ui.radioButton_existing.isChecked():
                    connect_para = self.ui.checkBox__auto.isChecked()
                else:
                    connect_para = None

                self.rtt2uart = rtt_to_serial(self.connect_type, connect_para, self.target_device, self.ui.comboBox_Port.currentText(
                ), self.ui.comboBox_baudrate.currentText(), device_interface, speed_list[self.ui.comboBox_Speed.currentIndex()], self.ui.checkBox_resettarget.isChecked())

                self.rtt2uart.start()

            except Exception as errors:
                QMessageBox.critical(self, "Errors", str(errors))
            else:
                self.start_state = True
                self.ui.pushButton_Start.setText("Stop")
        else:
            logger.debug('click stop button')
            try:
                # Existing方式不需要选择配置，继续禁用，不恢复
                if self.ui.radioButton_existing.isChecked() == False:
                    # 停止后才能再次配置
                    self.ui.comboBox_Device.setEnabled(True)
                    self.ui.pushButton_Selete_Device.setEnabled(True)
                    self.ui.comboBox_Interface.setEnabled(True)
                    self.ui.comboBox_Speed.setEnabled(True)
                    self.ui.comboBox_Port.setEnabled(True)
                    self.ui.comboBox_baudrate.setEnabled(True)
                    self.ui.pushButton_scan.setEnabled(True)

                self.rtt2uart.stop()

                self.start_state = False
                self.ui.pushButton_Start.setText("Start")
            except:
                logger.error('Stop rtt2uart failed', exc_info=True)
                pass

    def target_device_selete(self):
        device_ui = DeviceSeleteDialog()
        device_ui.exec_()
        self.target_device = device_ui.get_target_device()

        if self.target_device not in self.settings['device']:
            self.settings['device'].append(self.target_device)
            self.ui.comboBox_Device.addItem(self.target_device)
            self.ui.comboBox_Device.setCurrentIndex(
                len(self.settings['device']) - 1)

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
        self.connect_type = 'USB'

        self.ui.checkBox__auto.setVisible(False)
        self.ui.lineEdit_ip.setVisible(False)
        self.ui.checkBox_serialno.setVisible(True)
        self.serial_no_change_slot()
        # 通过usb方式接入，以下功能需要选择，恢复使用
        self.ui.comboBox_Device.setEnabled(True)
        self.ui.pushButton_Selete_Device.setEnabled(True)
        self.ui.comboBox_Interface.setEnabled(True)
        self.ui.comboBox_Speed.setEnabled(True)
        self.ui.checkBox_resettarget.setEnabled(True)

    def existing_session_selete_slot(self):
        self.connect_type = 'EXISTING'

        self.ui.checkBox_serialno.setVisible(False)
        self.ui.lineEdit_serialno.setVisible(False)
        self.ui.lineEdit_ip.setVisible(False)
        self.ui.checkBox__auto.setVisible(True)
        # 通过existing_session方式接入时，以下功能无效，禁止使用
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

    # 如果连接成功，表明server已经存在，当前已有实例在运行
    if lsocket.waitForConnected(200) == False:

        # 没有实例运行，创建服务器
        localServer = QLocalServer()
        localServer.listen(serverName)

        try:
            window = MainWindow()
            window.setWindowTitle("RTT2UART Control Panel V1.5.0")
            window.show()

            sys.exit(app.exec_())
        finally:
            localServer.close()
