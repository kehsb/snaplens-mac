"""Snaplens for macOS (internally still smartshot: its settings, login item and single-instance name): capture region -> OCR (zh/en/th) -> translate to Thai, painted over the capture in place.
QR codes in the capture are read and explained.
This file starts it; the code is in smartshot/, by domain: ocr/, qr/, ui/, system/ (config.py: VERSION and paths)."""
import os
import sys

from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from smartshot.system import mac
from smartshot.ui.assets import setup_app
from smartshot.ui.main import Main
from smartshot.ui.native import install_edit_menu


if __name__ == "__main__":
    app = QApplication(sys.argv)
    hello = QLocalSocket()
    hello.connectToServer("smartshot")
    if hello.waitForConnected(500):  # already running: that one shows its settings, no second icon and hotkey
        os._exit(0)
    app.setQuitOnLastWindowClosed(False)
    mac.accessory()  # no Dock icon: it lives in the menu bar
    install_edit_menu()  # ⌘C ⌘A in native text: the QR card's selectable labels
    setup_app(app)
    m = Main()  # no window: it starts in the menu bar
    door = QLocalServer(m)

    def knock():  # started again: show this one
        door.nextPendingConnection().deleteLater()
        m.show_settings()
    door.newConnection.connect(knock)
    QLocalServer.removeServer("smartshot")  # a socket file left by a crash: nobody answered on it above
    door.listen("smartshot")
    os._exit(app.exec())  # skip teardown: a running OCR/translate QThread would abort the interpreter on exit
