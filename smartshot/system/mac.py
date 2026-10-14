"""The app's part of macOS, from AppKit, Quartz and Carbon: the menu bar app, windows over everything, the screens'
pixels, the transparency setting and the capture hotkey. The capture hotkey is Carbon's RegisterEventHotKey: no Accessibility or Input Monitoring permission, and
the chord goes to us alone. Screen captures need Screen Recording (System Settings > Privacy & Security)."""
import ctypes
from contextlib import contextmanager

import AppKit
import numpy as np
import Quartz
from PySide6.QtCore import QRect


def accessory():  # no Dock icon or app menu: it lives in the menu bar (the bundle says so too: LSUIElement)
    AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)


def activate():  # bring the app forward, so its window takes the keys (an accessory app isn't, by a click on it)
    AppKit.NSApp.activateIgnoringOtherApps_(True)


def let_go():  # nothing of ours left on screen: the app that was in front before is again
    AppKit.NSApp.hide_(None)


def reduce_transparency():  # Accessibility > Display > Reduce transparency: glass drawn opaque
    return bool(AppKit.NSWorkspace.sharedWorkspace().accessibilityDisplayShouldReduceTransparency())


def nswindow(w):
    import objc
    return objc.objc_object(c_void_p=ctypes.c_void_p(int(w.winId()))).window()


def cover(w):
    """w over the menu bar and the Dock, on every Space and over full-screen apps; under menus, popovers and tooltips
    (the capture's own: its chrome is native). Not Qt's showFullScreen: on a Mac that's a Space of its own, slid in."""
    n = nswindow(w)
    n.setLevel_(AppKit.NSPopUpMenuWindowLevel - 1)  # 100: over the menu bar (24), the Dock (20), status items (25)
    n.setCollectionBehavior_(AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
                             | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary)
    n.setHasShadow_(False)


@contextmanager
def under_dialogs(w):  # w lowered while a file dialog is up: one at w's level (over the menu bar) would be under it
    n = nswindow(w)
    level = n.level()
    n.setLevel_(AppKit.NSNormalWindowLevel)
    try:
        yield
    finally:
        n.setLevel_(level)
        n.makeKeyAndOrderFront_(None)


def can_capture():  # Screen Recording granted: without it a capture is the desktop picture, no windows
    return bool(Quartz.CGPreflightScreenCaptureAccess())


def ask_capture():  # the system's own prompt the first time (it opens System Settings); after that, just the answer
    return bool(Quartz.CGRequestScreenCaptureAccess())


def screens():
    """-> [(geometry in points, as Qt places screens, BGR ndarray at the display's pixels: 2x on Retina)]. Not mss:
    it grabs at points, half a Retina display's pixels, and OCR reads small Thai far worse at that."""
    err, ids, n = Quartz.CGGetActiveDisplayList(16, None, None)
    out = []
    for d in ids[:n]:
        b, img = Quartz.CGDisplayBounds(d), Quartz.CGDisplayCreateImage(d)
        if img is None:
            continue
        w, h, row = Quartz.CGImageGetWidth(img), Quartz.CGImageGetHeight(img), Quartz.CGImageGetBytesPerRow(img)
        px = np.frombuffer(Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(img)), np.uint8)
        bgr = px[:h * row].reshape(h, row)[:, :w * 4].reshape(h, w, 4)[:, :, :3].copy()  # BGRA, rows padded
        out.append((QRect(int(b.origin.x), int(b.origin.y), int(b.size.width), int(b.size.height)), bgr))
    return out


# --- the capture hotkey: names <-> virtual key codes, by position on the keyboard (Carbon's kVK_*): the S key is "s" under a Thai layout too
KEYS = {0: "a", 1: "s", 2: "d", 3: "f", 4: "h", 5: "g", 6: "z", 7: "x", 8: "c", 9: "v", 11: "b", 12: "q", 13: "w",
        14: "e", 15: "r", 16: "y", 17: "t", 18: "1", 19: "2", 20: "3", 21: "4", 22: "6", 23: "5", 24: "=", 25: "9",
        26: "7", 27: "-", 28: "8", 29: "0", 30: "]", 31: "o", 32: "u", 33: "[", 34: "i", 35: "p", 36: "enter", 37: "l",
        38: "j", 39: "'", 40: "k", 41: ";", 42: "\\", 43: ",", 44: "/", 45: "n", 46: "m", 47: ".", 48: "tab", 49: "space",
        50: "`", 51: "backspace", 53: "esc", 65: "num .", 67: "num *", 69: "num plus", 71: "clear", 75: "num /",
        76: "num enter", 78: "num -", 81: "num =", 82: "num 0", 83: "num 1", 84: "num 2", 85: "num 3", 86: "num 4",
        87: "num 5", 88: "num 6", 89: "num 7", 91: "num 8", 92: "num 9", 64: "f17", 79: "f18", 80: "f19", 90: "f20",
        96: "f5", 97: "f6", 98: "f7", 99: "f3", 100: "f8", 101: "f9", 103: "f11", 105: "f13", 106: "f16", 107: "f14",
        109: "f10", 111: "f12", 113: "f15", 114: "help", 115: "home", 116: "page up", 117: "delete", 118: "f4",
        119: "end", 120: "f2", 121: "page down", 122: "f1", 123: "left", 124: "right", 125: "down", 126: "up",
        54: "cmd", 55: "cmd", 56: "shift", 60: "shift", 58: "alt", 61: "alt", 59: "ctrl", 62: "ctrl"}
CODES = {name: code for code, name in KEYS.items()}
MASKS = {"cmd": 1 << 8, "shift": 1 << 9, "alt": 1 << 11, "ctrl": 1 << 12}  # Carbon's cmdKey, shiftKey, optionKey, controlKey


class _Spec(ctypes.Structure):
    _fields_ = [("eventClass", ctypes.c_uint32), ("eventKind", ctypes.c_uint32)]


class _HotKeyID(ctypes.Structure):
    _fields_ = [("signature", ctypes.c_uint32), ("id", ctypes.c_uint32)]


_Handler = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
_carbon = ctypes.CDLL("/System/Library/Frameworks/Carbon.framework/Carbon")
_carbon.GetApplicationEventTarget.restype = ctypes.c_void_p
_carbon.InstallEventHandler.argtypes = [ctypes.c_void_p, _Handler, ctypes.c_uint32, ctypes.POINTER(_Spec),
                                        ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
_carbon.RegisterEventHotKey.argtypes = [ctypes.c_uint32, ctypes.c_uint32, _HotKeyID, ctypes.c_void_p, ctypes.c_uint32,
                                        ctypes.POINTER(ctypes.c_void_p)]
_carbon.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]


class Hotkey:
    """One global chord ("ctrl+alt+s") calling fn on the main thread while bound; bind() again replaces it."""

    def __init__(self, fn):
        self.fn, self.ref = fn, None
        self.handler = _Handler(lambda *_: self.fn() or 0)  # kept: Carbon holds only the pointer
        spec = _Spec(int.from_bytes(b"keyb", "big"), 5)  # kEventClassKeyboard, kEventHotKeyPressed
        _carbon.InstallEventHandler(_carbon.GetApplicationEventTarget(), self.handler, 1, ctypes.byref(spec), None, None)

    def bind(self, chord):  # -> False: no such key, or the system or another app has the chord
        self.unbind()
        *mods, key = chord.split("+")
        if key not in CODES or any(m not in MASKS for m in mods):
            return False
        ref = ctypes.c_void_p()
        hid = _HotKeyID(int.from_bytes(b"snap", "big"), 1)
        mask = sum(MASKS[m] for m in set(mods))
        if _carbon.RegisterEventHotKey(CODES[key], mask, hid, _carbon.GetApplicationEventTarget(), 0, ctypes.byref(ref)):
            return False
        self.ref = ref
        return True

    def unbind(self):
        if self.ref:
            _carbon.UnregisterEventHotKey(self.ref)
            self.ref = None
