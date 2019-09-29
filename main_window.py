import sys
from PySide2.QtWidgets import QApplication, QMainWindow, QDialog, QHeaderView, QAbstractItemView, QMessageBox
from PySide2.QtCore import QFile, QAbstractTableModel
from PySide2 import QtGui
from PySide2 import QtCore
from PySide2.QtGui import QFont
from ui_rtt2uart import Ui_dialog
from ui_sel_device import Ui_Dialog

import serial.tools.list_ports
import serial
import ctypes.util as ctypes_util
import sys
import xml.etree.ElementTree as ET
import pylink
from rtt2uart import rtt_to_serial
import logging

logging.basicConfig(level=logging.NOTSET,
                    format='%(asctime)s - [%(levelname)s] (%(filename)s:%(lineno)d) - %(message)s')
logger = logging.getLogger(__name__)

speed_list = [5, 10, 20, 30, 50, 100, 200, 300, 400, 500, 600, 750,
              900, 1000, 1334, 1600, 2000, 2667, 3200, 4000, 4800, 5334, 6000, 8000, 9600, 12000, 15000, 20000, 25000, 30000, 40000, 50000]

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

        if 0 == index.column():
            return self.mylist[index.row()]['Vendor']
        if 1 == index.column():
            return self.mylist[index.row()]['Name']

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

        self._target = None

        filepath = self.get_jlink_devices_list_file()
        if filepath != '':
            self.devices_list = self.parse_jlink_devices_list_file(filepath)

        if len(self.devices_list):

            # 从headdata中取出数据，放入到模型中
            headdata = ["Manufacturer", "Device"]

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

        return path

    def parse_jlink_devices_list_file(self, path):
        parsefile = open(path, 'r')

        tree = ET.ElementTree(file=parsefile)

        jlink_devices_list = []

        for tag in tree.findall('Device'):
            for chipinfo in tag:
                if 'Vendor' in chipinfo.attrib.keys():
                    jlink_devices_list.append(chipinfo.attrib)

        parsefile.close()

        return jlink_devices_list

    def reflash_selete_device(self):
        index = self.ui.tableView.currentIndex()
        self._target = self.devices_list[index.row()]['Name']
        self.ui.label_sel_dev.setText(self._target)

    def get_target_device(self):
        return self._target


class MainWindow(QDialog):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = Ui_dialog()
        self.ui.setupUi(self)

        self.start_state = False
        self.target_device = None
        self.rtt2uart = None

        self.ui.comboBox_Interface.addItem("JTAG")
        self.ui.comboBox_Interface.addItem("SWD")
        self.ui.comboBox_Interface.addItem("cJTAG")
        self.ui.comboBox_Interface.addItem("FINE")

        for i in range(len(speed_list)):
            self.ui.comboBox_Speed.addItem(str(speed_list[i]) + " kHz")

        for i in range(len(baudrate_list)):
            self.ui.comboBox_baudrate.addItem(str(baudrate_list[i]))

        self.port_scan()

        self.ui.pushButton_Start.clicked.connect(self.start)
        self.ui.pushButton_scan.clicked.connect(self.port_scan)
        self.ui.pushButton_Selete_Device.clicked.connect(
            self.target_device_selete)

        # 禁止调整窗口大小时点击关闭按钮没有反应
        # self.setFixedSize(self.width(), self.height())

    def __del__(self):
        if self.rtt2uart is not None:
            self.rtt2uart.stop()

    def port_scan(self):
        # 检测所有串口，将信息存储在字典中
        self.com_dict = {}
        port_list = list(serial.tools.list_ports.comports())
        self.ui.comboBox_Port.clear()
        for port in port_list:
            self.com_dict["%s" % port[0]] = "%s" % port[1]
            self.ui.comboBox_Port.addItem(port[0])

    def start(self):
        if self.start_state == False:
            try:
                if self.target_device is not None:
                    self.rtt2uart = rtt_to_serial(self.target_device, self.ui.comboBox_Port.currentText(
                    ), self.ui.comboBox_baudrate.currentText())
                    self.rtt2uart.start()
                else:
                    msgBox = QMessageBox()
                    msgBox.setIcon(QMessageBox.Warning)
                    msgBox.setText("Please selete the target device!")
                    msgBox.setWindowTitle('Error')
                    msgBox.exec_()
            except serial.SerialException:
                logger.error('Start rtt2uart failed', exc_info=True)
                msgBox = QMessageBox()
                msgBox.setIcon(QMessageBox.Warning)
                msgBox.setText("Open serial port failed!")
                msgBox.setWindowTitle('Error')
                msgBox.exec_()
                pass
            else:
                self.start_state = True
                self.ui.pushButton_Start.setText("Stop")
        else:
            try:
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
        self.ui.comboBox_Device.addItem(self.target_device)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())
