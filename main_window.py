import sys
from PySide2.QtWidgets import QApplication, QMainWindow, QDialog
from PySide2.QtCore import QFile
from ui_rtt2uart import Ui_dialog


class MainWindow(QDialog):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = Ui_dialog()
        self.ui.setupUi(self)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())
