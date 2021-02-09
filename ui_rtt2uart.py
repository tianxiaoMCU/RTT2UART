# -*- coding: utf-8 -*-

################################################################################
# Form generated from reading UI file 'rtt2uart.ui'
##
# Created by: Qt User Interface Compiler version 5.15.2
##
# WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *


class Ui_dialog(object):
    def setupUi(self, dialog):
        if not dialog.objectName():
            dialog.setObjectName(u"dialog")
        dialog.resize(402, 345)
        dialog.setMinimumSize(QSize(402, 300))
        dialog.setMaximumSize(QSize(402, 345))
        dialog.setSizeGripEnabled(False)
        self.pushButton_Start = QPushButton(dialog)
        self.pushButton_Start.setObjectName(u"pushButton_Start")
        self.pushButton_Start.setGeometry(QRect(160, 300, 81, 41))
        font = QFont()
        font.setFamily(u"\u5fae\u8f6f\u96c5\u9ed1")
        font.setPointSize(13)
        font.setBold(True)
        font.setUnderline(False)
        font.setWeight(75)
        font.setStrikeOut(False)
        self.pushButton_Start.setFont(font)
        self.pushButton_Start.setCheckable(True)
        self.pushButton_Start.setAutoRepeat(True)
        self.line = QFrame(dialog)
        self.line.setObjectName(u"line")
        self.line.setEnabled(True)
        self.line.setGeometry(QRect(10, 225, 381, 16))
        self.line.setFrameShape(QFrame.HLine)
        self.line.setFrameShadow(QFrame.Sunken)
        self.groupBox = QGroupBox(dialog)
        self.groupBox.setObjectName(u"groupBox")
        self.groupBox.setGeometry(QRect(10, 150, 381, 51))
        self.comboBox_Interface = QComboBox(self.groupBox)
        self.comboBox_Interface.setObjectName(u"comboBox_Interface")
        self.comboBox_Interface.setGeometry(QRect(10, 20, 241, 22))
        self.comboBox_Speed = QComboBox(self.groupBox)
        self.comboBox_Speed.setObjectName(u"comboBox_Speed")
        self.comboBox_Speed.setGeometry(QRect(260, 20, 111, 22))
        self.groupBox_2 = QGroupBox(dialog)
        self.groupBox_2.setObjectName(u"groupBox_2")
        self.groupBox_2.setGeometry(QRect(10, 90, 381, 51))
        self.comboBox_Device = QComboBox(self.groupBox_2)
        self.comboBox_Device.setObjectName(u"comboBox_Device")
        self.comboBox_Device.setGeometry(QRect(10, 20, 321, 22))
        self.pushButton_Selete_Device = QPushButton(self.groupBox_2)
        self.pushButton_Selete_Device.setObjectName(
            u"pushButton_Selete_Device")
        self.pushButton_Selete_Device.setGeometry(QRect(340, 20, 31, 23))
        self.groupBox_UART = QGroupBox(dialog)
        self.groupBox_UART.setObjectName(u"groupBox_UART")
        self.groupBox_UART.setGeometry(QRect(10, 238, 381, 51))
        self.comboBox_Port = QComboBox(self.groupBox_UART)
        self.comboBox_Port.setObjectName(u"comboBox_Port")
        self.comboBox_Port.setGeometry(QRect(50, 20, 81, 22))
        self.label = QLabel(self.groupBox_UART)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(13, 20, 31, 20))
        self.label_2 = QLabel(self.groupBox_UART)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setGeometry(QRect(150, 20, 61, 21))
        self.comboBox_baudrate = QComboBox(self.groupBox_UART)
        self.comboBox_baudrate.setObjectName(u"comboBox_baudrate")
        self.comboBox_baudrate.setGeometry(QRect(218, 20, 71, 22))
        self.pushButton_scan = QPushButton(self.groupBox_UART)
        self.pushButton_scan.setObjectName(u"pushButton_scan")
        self.pushButton_scan.setGeometry(QRect(314, 20, 61, 23))
        self.checkBox_resettarget = QCheckBox(dialog)
        self.checkBox_resettarget.setObjectName(u"checkBox_resettarget")
        self.checkBox_resettarget.setGeometry(QRect(20, 210, 91, 16))
        self.groupBox_3 = QGroupBox(dialog)
        self.groupBox_3.setObjectName(u"groupBox_3")
        self.groupBox_3.setGeometry(QRect(10, 0, 381, 81))
        self.radioButton_usb = QRadioButton(self.groupBox_3)
        self.radioButton_usb.setObjectName(u"radioButton_usb")
        self.radioButton_usb.setGeometry(QRect(10, 20, 89, 16))
        self.radioButton_existing = QRadioButton(self.groupBox_3)
        self.radioButton_existing.setObjectName(u"radioButton_existing")
        self.radioButton_existing.setGeometry(QRect(10, 60, 121, 16))
        self.radioButton_tcpip = QRadioButton(self.groupBox_3)
        self.radioButton_tcpip.setObjectName(u"radioButton_tcpip")
        self.radioButton_tcpip.setEnabled(False)
        self.radioButton_tcpip.setGeometry(QRect(10, 40, 89, 16))
        self.checkBox_serialno = QCheckBox(self.groupBox_3)
        self.checkBox_serialno.setObjectName(u"checkBox_serialno")
        self.checkBox_serialno.setGeometry(QRect(150, 20, 81, 16))
        self.lineEdit_serialno = QLineEdit(self.groupBox_3)
        self.lineEdit_serialno.setObjectName(u"lineEdit_serialno")
        self.lineEdit_serialno.setGeometry(QRect(240, 18, 131, 20))
        self.lineEdit_ip = QLineEdit(self.groupBox_3)
        self.lineEdit_ip.setObjectName(u"lineEdit_ip")
        self.lineEdit_ip.setEnabled(False)
        self.lineEdit_ip.setGeometry(QRect(150, 40, 221, 20))
        self.checkBox__auto = QCheckBox(self.groupBox_3)
        self.checkBox__auto.setObjectName(u"checkBox__auto")
        self.checkBox__auto.setGeometry(QRect(150, 60, 111, 16))

        self.retranslateUi(dialog)

        QMetaObject.connectSlotsByName(dialog)
    # setupUi

    def retranslateUi(self, dialog):
        dialog.setWindowTitle(QCoreApplication.translate(
            "dialog", u"RTT2UART Control Panel", None))
        self.pushButton_Start.setText(
            QCoreApplication.translate("dialog", u"Start", None))
        self.groupBox.setTitle(QCoreApplication.translate(
            "dialog", u"Target Interface And Speed", None))
        self.comboBox_Speed.setCurrentText("")
        self.groupBox_2.setTitle(QCoreApplication.translate(
            "dialog", u"Specify Target Device", None))
        self.pushButton_Selete_Device.setText(
            QCoreApplication.translate("dialog", u"...", None))
        self.groupBox_UART.setTitle(
            QCoreApplication.translate("dialog", u"UART Config", None))
        self.label.setText(QCoreApplication.translate(
            "dialog", u"Port:", None))
        self.label_2.setText(QCoreApplication.translate(
            "dialog", u"Baud rate:", None))
        self.pushButton_scan.setText(
            QCoreApplication.translate("dialog", u"Scan", None))
        self.checkBox_resettarget.setText(
            QCoreApplication.translate("dialog", u"Reset target", None))
        self.groupBox_3.setTitle(QCoreApplication.translate(
            "dialog", u"Connection to J-Link", None))
        self.radioButton_usb.setText(
            QCoreApplication.translate("dialog", u"USB", None))
        self.radioButton_existing.setText(
            QCoreApplication.translate("dialog", u"Existing Session", None))
        self.radioButton_tcpip.setText(
            QCoreApplication.translate("dialog", u"TCP/IP", None))
        self.checkBox_serialno.setText(
            QCoreApplication.translate("dialog", u"Serial NO", None))
        self.checkBox__auto.setText(QCoreApplication.translate(
            "dialog", u"Auto Reconnect", None))
    # retranslateUi
