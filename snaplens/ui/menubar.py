"""The app's icon in the menu bar and its menu: แคปหน้าจอ (with the capture keys), ภาษาที่อ่าน (the next capture's
reading mode), ตั้งค่า…, ออกจาก Snaplens. An NSStatusItem with a native NSMenu, built afresh each time it opens."""
import os

import AppKit
import objc
from Foundation import NSMakeSize, NSObject
from PySide6.QtWidgets import QApplication

from snaplens.config import ASSETS, TITLE
from snaplens.ui.native import menu, reported
from snaplens.ui.settings import FLAGS

# system/mac.py's key names -> the character a menu shows them by (a letter, a digit or a sign is itself)
KEYS = {"esc": "\x1b", "enter": "\r", "num enter": AppKit.NSEnterCharacter, "backspace": AppKit.NSBackspaceCharacter,
        "delete": AppKit.NSDeleteFunctionKey, "clear": AppKit.NSClearLineFunctionKey, "help": AppKit.NSHelpFunctionKey,
        "home": AppKit.NSHomeFunctionKey, "end": AppKit.NSEndFunctionKey, "page up": AppKit.NSPageUpFunctionKey,
        "page down": AppKit.NSPageDownFunctionKey, "up": AppKit.NSUpArrowFunctionKey,
        "down": AppKit.NSDownArrowFunctionKey, "left": AppKit.NSLeftArrowFunctionKey,
        "right": AppKit.NSRightArrowFunctionKey, **{f"f{n}": chr(ord(AppKit.NSF1FunctionKey) + n - 1) for n in range(1, 21)}}


def shortcut(hotkey):  # "ctrl+alt+s" -> ("s", ⌃⌥) for a menu row; None: a menu can't show that key (the keypad's)
    *mods, key = hotkey.split("+")
    key = KEYS.get(key) or (key if len(key) == 1 else None)
    return (key, sum(FLAGS[m] for m in mods)) if key else None


class _MenuBarDelegate(NSObject):  # the menu's: it's filled as it opens
    def initWithFn_(self, fn):
        self = objc.super(_MenuBarDelegate, self).init()
        self.fn = fn
        return self

    def menuNeedsUpdate_(self, m):
        reported(self.fn, m)


class MenuBar:
    """main: Main (its key, mode and MODE_NAMES, keys(), and capture, pick_mode, show_settings for the rows)."""

    def __init__(self, main):
        self.main, self.keep = main, []
        self.item = AppKit.NSStatusBar.systemStatusBar().statusItemWithLength_(AppKit.NSVariableStatusItemLength)
        icon = AppKit.NSImage.alloc().initWithContentsOfFile_(os.path.join(ASSETS, "icons", "tray-light-32.png"))
        icon.setSize_(NSMakeSize(18, 18))
        icon.setTemplate_(True)  # the menu bar draws it in its own colour
        icon.setAccessibilityDescription_("Snaplens")
        self.item.button().setImage_(icon)
        self.menu = AppKit.NSMenu.alloc().initWithTitle_("Snaplens")
        self.delegate = _MenuBarDelegate.alloc().initWithFn_(self.fill)
        self.menu.setDelegate_(self.delegate)
        self.item.setMenu_(self.menu)  # a click opens it

    def fill(self, m):  # the rows, from how things are now: the capture keys, the reading mode
        main, cmd = self.main, FLAGS["cmd"]
        modes = [(None, name, None, i == main.mode, lambda i=i: main.pick_mode(i)) for i, name in enumerate(main.MODE_NAMES)]
        self.keep = []  # the last opening's targets: their rows are gone
        fresh = menu([("viewfinder", "แคปหน้าจอ", shortcut(main.key), False, main.capture),
                     ("globe", "ภาษาที่อ่าน", None, False, modes), None,
                     ("gearshape", "ตั้งค่า…", (",", cmd), False, main.show_settings),
                     ("power", "ออกจาก Snaplens", ("q", cmd), False, QApplication.quit)], self.keep)
        items = fresh.itemArray()
        fresh.removeAllItems()  # an item is in one menu at a time
        m.setItemArray_(items)

    def refresh(self):  # the icon's tooltip: the capture keys may have changed
        self.item.button().setToolTip_(f"{TITLE}\nกด {self.main.keys()} เพื่อแคป")

    def close(self):  # out of a capture's shot: the hotkey pressed while the menu is open
        self.menu.cancelTrackingWithoutAnimation()

    def remove(self):  # on quit: no ghost icon left in the menu bar
        AppKit.NSStatusBar.systemStatusBar().removeStatusItem_(self.item)
