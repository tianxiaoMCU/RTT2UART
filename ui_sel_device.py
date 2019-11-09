# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file '.\sel_device.ui',
# licensing of '.\sel_device.ui' applies.
#
# Created: Sat Nov  9 10:31:38 2019
#      by: pyside2-uic  running on PySide2 5.13.2
#
# WARNING! All changes made in this file will be lost!

from PySide2 import QtCore, QtGui, QtWidgets


class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(779, 385)
        Dialog.setMinimumSize(QtCore.QSize(779, 385))
        Dialog.setMaximumSize(QtCore.QSize(779, 385))
        self.buttonBox = QtWidgets.QDialogButtonBox(Dialog)
        self.buttonBox.setGeometry(QtCore.QRect(430, 350, 341, 32))
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(
            QtWidgets.QDialogButtonBox.Cancel | QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.label = QtWidgets.QLabel(Dialog)
        self.label.setGeometry(QtCore.QRect(10, 10, 91, 16))
        self.label.setObjectName("label")
        self.label_sel_dev = QtWidgets.QLabel(Dialog)
        self.label_sel_dev.setGeometry(QtCore.QRect(110, 10, 161, 16))
        self.label_sel_dev.setText("")
        self.label_sel_dev.setObjectName("label_sel_dev")
        self.tableView = QtWidgets.QTableView(Dialog)
        self.tableView.setGeometry(QtCore.QRect(10, 30, 761, 311))
        self.tableView.setObjectName("tableView")
        self.line = QtWidgets.QFrame(Dialog)
        self.line.setGeometry(QtCore.QRect(10, 340, 761, 16))
        self.line.setFrameShape(QtWidgets.QFrame.HLine)
        self.line.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.line.setObjectName("line")

        self.retranslateUi(Dialog)
        QtCore.QObject.connect(
            self.buttonBox, QtCore.SIGNAL("accepted()"), Dialog.accept)
        QtCore.QObject.connect(
            self.buttonBox, QtCore.SIGNAL("rejected()"), Dialog.reject)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QtWidgets.QApplication.translate(
            "Dialog", "Target Device Settings", None, -1))
        self.label.setText(QtWidgets.QApplication.translate(
            "Dialog", "Seleted Device:", None, -1))
