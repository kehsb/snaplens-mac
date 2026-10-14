"""The app: its menu bar icon and menu, the capture hotkey, the settings it keeps and the captures it opens."""
import sys
import time

from PySide6.QtCore import QObject, QSettings, QTimer, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from smartshot.config import HOTKEY, TITLE, TRAY
from smartshot.ocr.engine import warmup
from smartshot.slip.thunder import thunder_key
from smartshot.system import mac
from smartshot.system.hotkey import keyname
from smartshot.task import Task
from smartshot.ui.assets import tray_icon
from smartshot.ui.floater import Floater, Notice, float_menu
from smartshot.ui.overlay import Overlay
from smartshot.ui.settings import SettingsWindow


class Main(QObject):
    """The app lives in the menu bar: the hotkey or a click on its icon captures, the right button opens its menu,
    and the menu opens the settings (SettingsWindow, which reads what's here and calls back to change it)."""
    hotkey = Signal()
    MODES = ["auto", "ch", "th"]  # the OCR's reading modes, and their names
    MODE_NAMES = ["อัตโนมัติ", "จีน+อังกฤษ", "ไทย"]

    def __init__(self):
        super().__init__()
        self.settings = QSettings("smartshot", "smartshot")  # ~/Library/Preferences/com.smartshot.smartshot.plist
        self.key, self.mode, self.warmed = self.settings.value("hotkey", HOTKEY), 0, False
        self.overlays, self.was_visible, self.hinted, self.shooting = [], False, False, False
        self.hotkey.connect(self.capture)
        self.tray = QSystemTrayIcon(tray_icon(), self)
        self.tray.activated.connect(self.tray_click)
        self.tray.show()
        QApplication.instance().aboutToQuit.connect(self.tray.hide)  # no ghost icon left in the menu bar
        self.carbon = mac.Hotkey(self.hotkey.emit)
        self.panel = SettingsWindow(self)
        self.bind_keys()
        self.refresh()
        self.warm = Task(warmup)
        self.warm.done.connect(self.ready)
        self.warm.start()

    def ready(self, _):
        self.warmed = True
        self.refresh()
        if "--startup" not in sys.argv:  # started by hand and no window opens: say where it went
            self.notify("พร้อมแล้ว", f"กด {self.keys()} หรือคลิกไอคอนที่{TRAY}เพื่อแคป")

    def keys(self):  # the capture keys, for people
        return keyname(self.key)

    def states(self):  # how things stand, for the settings' sidebar: (title, line, green)
        return [("พร้อมใช้งาน", "โมเดลอ่านข้อความโหลดแล้ว", True) if self.warmed else
                ("กำลังเตรียม", "กำลังโหลดโมเดลอ่านข้อความ…", False),
                ("ตรวจสลิปได้", "มี Thunder API key แล้ว", True) if thunder_key() else
                ("ยังตรวจสลิปไม่ได้", "ใส่ Thunder API key ทางขวา", False),
                (f"รออยู่ที่{TRAY}", "ปิดหน้าต่างนี้ได้", False)]

    def refresh(self):  # what the settings and the menu bar icon say
        self.tray.setToolTip(f"{TITLE}\nกด {self.keys()} หรือคลิกเพื่อแคป")
        self.panel.refresh()

    def pick_mode(self, i):  # the next capture's reading mode, from the icon's menu or the settings
        self.mode = i
        self.panel.refresh()

    def bind_keys(self):  # the capture keys from the settings, afresh
        if not self.carbon.bind(self.key):  # the system or another app has it
            self.key = HOTKEY
            self.carbon.bind(HOTKEY)

    def set_key(self, k):  # the capture keys (key_rule passed them), bound now
        self.key = k
        self.settings.setValue("hotkey", k)
        self.bind_keys()
        self.refresh()

    def show_settings(self):
        self.panel.show()

    def hint_tray(self):  # the first time the settings close: where the app still is
        if not self.hinted:
            self.hinted = True
            self.notify(f"ยังทำงานอยู่ที่{TRAY}", f"กด {self.keys()} หรือคลิกไอคอนเพื่อแคป")

    def notify(self, title, text):  # G4's notice under the menu bar; one at a time
        for w in list(Floater.up):
            if n := w.findChild(Notice):
                n.hide()
        Notice(title, text)

    def tray_click(self, why):  # a click captures, the right button opens the menu
        if why == QSystemTrayIcon.Trigger:
            self.capture()
        elif why == QSystemTrayIcon.Context:
            c, icon = QCursor.pos(), self.tray.geometry()
            self.tray_menu(c if icon.isEmpty() or icon.contains(c) else icon.topLeft())

    def tray_menu(self, at):  # G4's glass menu, under the menu bar at at
        return float_menu([("capture", "แคปหน้าจอ", keyname(self.key), False, self.capture),
                           ("lang", "ภาษาที่อ่าน", self.MODE_NAMES[self.mode], "chevronRight", lambda: self.lang_menu(at)),
                           ("sliders", "ตั้งค่า", "", False, self.show_settings), None,
                           ("exit", "ออกจากแอป", "", False, QApplication.quit)], at)

    def lang_menu(self, at):  # the menu's language row: the next capture's reading mode
        m = float_menu([(None, n, "", i == self.mode, lambda i=i: self.pick_mode(i)) for i, n in enumerate(self.MODE_NAMES)],
                       at, "ภาษาที่อ่าน")
        m.born = time.monotonic()
        return m

    def capture(self):
        if self.overlays or self.shooting:  # already capturing (hotkey pressed twice)
            return
        if not mac.can_capture():  # it would be the desktop picture alone: ask, and say where it's granted
            if not mac.ask_capture():
                return self.notify("ต้องอนุญาตให้บันทึกหน้าจอก่อน", "เปิด Snaplens ใน การตั้งค่าระบบ > ความเป็นส่วนตัวและความปลอดภัย"
                                   " > การบันทึกหน้าจอ แล้วเปิดแอปใหม่")
        self.was_visible = self.panel.visible()
        self.panel.hide()
        self.shooting = True  # the hide reaches the screen only once the event loop turns: then grab
        QTimer.singleShot(200, self.shoot)

    def shoot(self):  # every display, each under an overlay of its own
        self.shooting = False
        for geo, shot in mac.screens():
            o = Overlay(shot, geo, self.MODES[self.mode])
            o.started.connect(lambda o=o: [x.reset() for x in self.overlays if x is not o])
            o.closed.connect(self.end_capture)
            self.overlays.append(o)
            o.show()
            mac.cover(o)  # after show: Qt sets the level as it shows a window
        here = next((o for o in self.overlays if o.geometry().contains(QCursor.pos())), self.overlays[0])
        mac.activate()
        here.raise_()
        here.activateWindow()  # keyboard (Esc) goes to the screen under the cursor

    def end_capture(self):
        for o in self.overlays:
            o.close()
            o.deleteLater()
        self.overlays = []
        if self.was_visible:  # back to how it was before the capture
            self.panel.show()
        else:
            mac.let_go()
