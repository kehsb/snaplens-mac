"""Snaplens for macOS: capture region -> OCR (zh/en/th) -> translate to Thai, painted over the capture in place.
QR codes in the capture are read and explained.
This file starts it; the code is in snaplens/, by domain: ocr/, qr/, ui/, system/ (config.py: VERSION and paths)."""
import os
import sys

from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from snaplens.config import BUNDLE, FROZEN, QUIET
from snaplens.system import autostart, mac
from snaplens.ui.assets import setup_app
from snaplens.ui.main import Main
from snaplens.ui.native import install_edit_menu

OLD = "smartshot"  # 0.17 and before listened here: a copy run by hand (dev.sh) defers to it, as it did then


def running(why, name=BUNDLE):  # one's running already: told why this one started (b"show", b"startup") -> True
    hello = QLocalSocket()
    hello.connectToServer(name)
    if not hello.waitForConnected(500):
        return False
    hello.write(why + b"\n")
    hello.waitForBytesWritten(200)
    return True


def listen(parent, show, name=BUNDLE):  # the running one: a copy started again is heard as it comes, nothing waited for
    door = QLocalServer(parent)

    def knock():
        while door.hasPendingConnections():
            s = door.nextPendingConnection()
            s.readyRead.connect(lambda s=s: heard(s))
            s.disconnected.connect(s.deleteLater)
            heard(s)  # what came with the connection

    def heard(s):  # "show": started by hand, show(); "startup": by launchd at login (or a registering), nothing
        if s.canReadLine():
            if s.readLine().data().strip() == b"show":
                show()
            s.disconnectFromServer()
    door.newConnection.connect(knock)
    QLocalServer.removeServer(name)  # a socket file left by a crash: nobody answered on it before
    door.listen(name)
    return door


if __name__ == "__main__":
    app = QApplication(sys.argv)
    if running(b"startup" if QUIET else b"show") or not QUIET and running(b"show", OLD):  # no second icon and
        os._exit(0)  # hotkey; by hand, that one shows its settings (0.17's on any knock: not at login)
    if FROZEN and "--startup" in sys.argv and mac.relaunch("--login"):  # launchd's job at login: the switch off
        os._exit(0)  # (unregistering) would kill it, and the app with it. So LaunchServices opens the app, the job ends
    app.setQuitOnLastWindowClosed(False)
    mac.accessory()  # no Dock icon: it lives in the menu bar
    install_edit_menu()  # ⌘C ⌘A in native text: the QR card's selectable labels
    setup_app(app)
    m = Main()  # no window: it starts in the menu bar
    door = listen(m, m.show_settings)
    autostart.carry()  # 0.17's login item, and an update's new executable: after listen, as registering starts a
    autostart.renew()  # second copy at once
    os._exit(app.exec())  # skip teardown: a running OCR/translate QThread would abort the interpreter on exit
