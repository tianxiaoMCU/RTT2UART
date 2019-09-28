# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file '.\rtt2uart.ui',
# licensing of '.\rtt2uart.ui' applies.
#
# Created: Sat Sep 28 18:02:06 2019
#      by: pyside2-uic  running on PySide2 5.13.1
#
# WARNING! All changes made in this file will be lost!

from PySide2 import QtCore, QtGui, QtWidgets


class Ui_dialog(object):
    def setupUi(self, dialog):
        dialog.setObjectName("dialog")
        dialog.resize(402, 300)
        dialog.setMinimumSize(QtCore.QSize(0, 0))
        dialog.setMaximumSize(QtCore.QSize(16777215, 16777215))
        dialog.setSizeGripEnabled(False)
        self.pushButton_Start = QtWidgets.QPushButton(dialog)
        self.pushButton_Start.setGeometry(QtCore.QRect(160, 252, 81, 41))
        font = QtGui.QFont()
        font.setFamily("寰蒋闆呴粦")
        font.setPointSize(13)
        font.setWeight(75)
        font.setUnderline(False)
        font.setStrikeOut(False)
        font.setBold(True)
        self.pushButton_Start.setFont(font)
        self.pushButton_Start.setCheckable(True)
        self.pushButton_Start.setAutoRepeat(True)
        self.pushButton_Start.setObjectName("pushButton_Start")
        self.line = QtWidgets.QFrame(dialog)
        self.line.setEnabled(True)
        self.line.setGeometry(QtCore.QRect(10, 150, 381, 20))
        self.line.setFrameShape(QtWidgets.QFrame.HLine)
        self.line.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.line.setObjectName("line")
        self.groupBox = QtWidgets.QGroupBox(dialog)
        self.groupBox.setGeometry(QtCore.QRect(10, 90, 381, 51))
        self.groupBox.setObjectName("groupBox")
        self.comboBox_Interface = QtWidgets.QComboBox(self.groupBox)
        self.comboBox_Interface.setGeometry(QtCore.QRect(10, 20, 241, 22))
        self.comboBox_Interface.setObjectName("comboBox_Interface")
        self.comboBox_Speed = QtWidgets.QComboBox(self.groupBox)
        self.comboBox_Speed.setGeometry(QtCore.QRect(260, 20, 111, 22))
        self.comboBox_Speed.setCurrentText("")
        self.comboBox_Speed.setObjectName("comboBox_Speed")
        self.groupBox_2 = QtWidgets.QGroupBox(dialog)
        self.groupBox_2.setGeometry(QtCore.QRect(10, 10, 381, 51))
        self.groupBox_2.setObjectName("groupBox_2")
        self.comboBox_Device = QtWidgets.QComboBox(self.groupBox_2)
        self.comboBox_Device.setGeometry(QtCore.QRect(10, 20, 321, 22))
        self.comboBox_Device.setObjectName("comboBox_Device")
        self.pushButton_Selete_Device = QtWidgets.QPushButton(self.groupBox_2)
        self.pushButton_Selete_Device.setGeometry(
            QtCore.QRect(340, 20, 31, 23))
        self.pushButton_Selete_Device.setObjectName("pushButton_Selete_Device")
        self.groupBox_UART = QtWidgets.QGroupBox(dialog)
        self.groupBox_UART.setGeometry(QtCore.QRect(10, 170, 381, 51))
        self.groupBox_UART.setObjectName("groupBox_UART")
        self.comboBox_Port = QtWidgets.QComboBox(self.groupBox_UART)
        self.comboBox_Port.setGeometry(QtCore.QRect(50, 20, 81, 22))
        self.comboBox_Port.setObjectName("comboBox_Port")
        self.label = QtWidgets.QLabel(self.groupBox_UART)
        self.label.setGeometry(QtCore.QRect(13, 20, 31, 20))
        self.label.setObjectName("label")
        self.label_2 = QtWidgets.QLabel(self.groupBox_UART)
        self.label_2.setGeometry(QtCore.QRect(150, 20, 61, 21))
        self.label_2.setObjectName("label_2")
        self.comboBox_baudrate = QtWidgets.QComboBox(self.groupBox_UART)
        self.comboBox_baudrate.setGeometry(QtCore.QRect(218, 20, 71, 22))
        self.comboBox_baudrate.setObjectName("comboBox_baudrate")
        self.pushButton_scan = QtWidgets.QPushButton(self.groupBox_UART)
        self.pushButton_scan.setGeometry(QtCore.QRect(314, 20, 61, 23))
        self.pushButton_scan.setObjectName("pushButton_scan")

        self.retranslateUi(dialog)
        QtCore.QMetaObject.connectSlotsByName(dialog)

    def retranslateUi(self, dialog):
        dialog.setWindowTitle(QtWidgets.QApplication.translate(
            "dialog", "RTT2UART Control Panel", None, -1))
        self.pushButton_Start.setText(
            QtWidgets.QApplication.translate("dialog", "Start", None, -1))
        self.groupBox.setTitle(QtWidgets.QApplication.translate(
            "dialog", "Target Interface And Speed", None, -1))
        self.groupBox_2.setTitle(QtWidgets.QApplication.translate(
            "dialog", "Specify Target Device", None, -1))
        self.pushButton_Selete_Device.setText(
            QtWidgets.QApplication.translate("dialog", "...", None, -1))
        self.groupBox_UART.setTitle(QtWidgets.QApplication.translate(
            "dialog", "UART Config", None, -1))
        self.label.setText(QtWidgets.QApplication.translate(
            "dialog", "Port:", None, -1))
        self.label_2.setText(QtWidgets.QApplication.translate(
            "dialog", "Baud rate:", None, -1))
        self.pushButton_scan.setText(
            QtWidgets.QApplication.translate("dialog", "Scan", None, -1))
