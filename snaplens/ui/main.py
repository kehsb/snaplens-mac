"""The app: its menu bar icon and menu, the capture hotkey, the settings it keeps and the captures it opens."""
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication

from snaplens.config import HOTKEY, QUIET, TRAY
from snaplens.ocr.engine import warmup
from snaplens.slip.thunder import thunder_key
from snaplens.system import mac
from snaplens.system.hotkey import keyname
from snaplens.system.prefs import prefs
from snaplens.task import Task
from snaplens.ui.chrome import KeyMonitor
from snaplens.ui.menubar import MenuBar
from snaplens.ui.notify import notify
from snaplens.ui.overlay import Overlay
from snaplens.ui.settings import SettingsWindow


class Main(QObject):
    """The app lives in the menu bar: the hotkey captures, and a click on its icon opens its menu (MenuBar: capture,
    the reading mode, the settings, quit). The settings (SettingsWindow) read what's here and call back to change it."""
    hotkey = Signal()
    MODES = ["auto", "ch", "th"]  # the OCR's reading modes, and their names
    MODE_NAMES = ["อัตโนมัติ", "จีน+อังกฤษ", "ไทย"]

    def __init__(self):
        super().__init__()
        self.settings = prefs()  # ~/Library/Preferences/io.github.kehsb.snaplens.plist
        self.key, self.mode, self.warmed = self.settings.value("hotkey", HOTKEY), 0, False
        self.overlays, self.was_visible, self.hinted, self.shooting, self.monitor = [], False, False, False, None
        self.hotkey.connect(self.capture)
        self.bar = MenuBar(self)
        QApplication.instance().aboutToQuit.connect(self.bar.remove)  # no ghost icon left in the menu bar
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
        if not QUIET:  # started by hand and no window opens: say where it went
            notify("พร้อมแล้ว", f"กด {self.keys()} หรือเลือก แคปหน้าจอ จากไอคอนที่{TRAY}")

    def keys(self):  # the capture keys, for people
        return keyname(self.key)

    def states(self):  # how things stand, for the settings' sidebar: (title, line, green)
        return [("พร้อมใช้งาน", "โมเดลอ่านข้อความโหลดแล้ว", True) if self.warmed else
                ("กำลังเตรียม", "กำลังโหลดโมเดลอ่านข้อความ…", False),
                ("ตรวจสลิปได้", "มี Thunder API key แล้ว", True) if thunder_key() else
                ("ยังตรวจสลิปไม่ได้", "ใส่ Thunder API key ทางขวา", False),
                (f"รออยู่ที่{TRAY}", "ปิดหน้าต่างนี้ได้", False)]

    def refresh(self):  # what the settings and the menu bar icon say
        self.bar.refresh()
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
            notify(f"ยังทำงานอยู่ที่{TRAY}", f"กด {self.keys()} หรือเลือก แคปหน้าจอ จากไอคอน")

    def capture(self):
        if self.overlays or self.shooting:  # already capturing (hotkey pressed twice)
            return
        self.bar.close()  # the hotkey pressed with the icon's menu open: not in the shot
        if not mac.can_capture():  # it would be the desktop picture alone: ask, and say where it's granted
            if not mac.ask_capture():
                return notify("ต้องอนุญาตให้บันทึกหน้าจอก่อน", "เปิด Snaplens ใน การตั้งค่าระบบ > ความเป็นส่วนตัวและความปลอดภัย"
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
        if not self.overlays:  # no display could be grabbed: back as it was, no key monitor left behind
            return self.end_capture()
        self.monitor = KeyMonitor(self.overlays)  # the capture's keys while a native view (the card's) has them
        here = next((o for o in self.overlays if o.geometry().contains(QCursor.pos())), self.overlays[0])
        mac.activate()
        here.raise_()
        here.activateWindow()  # keyboard (Esc) goes to the screen under the cursor

    def end_capture(self):
        if self.monitor:
            self.monitor.remove()
            self.monitor = None
        for o in self.overlays:
            o.close()
            o.deleteLater()
        self.overlays = []
        if self.was_visible:  # back to how it was before the capture
            self.panel.show()
        else:
            mac.let_go()
