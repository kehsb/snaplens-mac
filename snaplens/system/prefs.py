"""The settings the app keeps (the capture keys): QSettings in the bundle id's domain,
~/Library/Preferences/io.github.kehsb.snaplens.plist, the built app's own (NSUserDefaults') and python app.py's alike."""
import os
import plistlib

from PySide6.QtCore import QSettings

NEW = ("kehsb.github.io", "snaplens")  # a dotted organization is reversed: io.github.kehsb.snaplens
OLD = ("smartshot", "smartshot")  # 0.17 and before: com.smartshot.smartshot.plist
APPS = ("/Applications", "~/Applications")  # where 0.17 may still be installed, MacOS/smartshot its executable


def prefs():
    s = alone(QSettings(*NEW))
    carry(QSettings(*OLD), s, keep=installed())
    return s


def installed():  # 0.17 not replaced yet (python app.py, a build run from dist/ or the DMG): it reads the old domain
    return any(os.path.exists(os.path.expanduser(f"{d}/Snaplens.app/Contents/MacOS/smartshot")) for d in APPS)


def alone(s):  # s's own domain only: a Mac's falls back to the global one (AppleLanguages and all)
    s.setFallbacksEnabled(False)
    return s


def carry(old, new, keep=False):  # once: old's hotkey into new (unless new has its own), then old emptied and its
    old, new = alone(old), alone(new)  # file gone; keep: left as it is, 0.17 still uses it
    if not old.allKeys():
        return
    if old.contains("hotkey") and not new.contains("hotkey"):
        new.setValue("hotkey", old.value("hotkey"))
        new.sync()
        if new.status() != QSettings.NoError or new.value("hotkey") != old.value("hotkey"):
            return  # not kept: the old one stays, tried again next start
    if keep:
        return
    path = old.fileName()
    old.clear()
    old.sync()
    try:
        with open(path, "rb") as f:
            left = plistlib.load(f)
    except (OSError, plistlib.InvalidFileException):
        return  # gone already (cfprefsd removes an emptied domain's file)
    if not left:
        os.remove(path)
