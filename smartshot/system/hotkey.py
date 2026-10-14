"""The capture hotkey: names and which chords are allowed. Bound by Carbon (system/mac.py); the modifiers are ctrl,
alt (Option), shift and cmd."""
import re

SIGNS = {"ctrl": "⌃", "alt": "⌥", "shift": "⇧", "cmd": "⌘"}
MODS = tuple(SIGNS)
MAIN_MODS = {"ctrl", "cmd"}  # one of these: not plain typing (⌥S types ß)


def keyname(hotkey):  # "ctrl+alt+s" -> "⌃+⌥+S"
    return "+".join(SIGNS.get(p, p.title()) for p in hotkey.split("+"))


def chord(names):  # held keys -> "ctrl+shift+x": modifiers first, in MODS' order
    return "+".join(sorted(dict.fromkeys(names), key=lambda n: MODS.index(n) if n in MODS else len(MODS)))


def key_rule(k):  # why the chord k can't be the capture keys, "" if it can: none that would eat every app's typing
    parts, name = k.split("+"), keyname(k).replace("+", " + ")
    keys = [x for x in parts if x not in MODS]
    mods = set(parts) - set(keys)
    if not keys:
        return f"{name} ยังไม่ครบ: ต้องมีปุ่มอื่นคู่ด้วย"
    if "tab" in keys:  # ⌘Tab, ⌃Tab: how one goes to another app or tab
        return f"{name} ใช้สลับหน้าต่างอยู่แล้ว"
    if not (MAIN_MODS & mods or all(re.fullmatch(r"f\d+", x) for x in keys)):
        return f"{name} ใช้ไม่ได้ จะทับการพิมพ์ปกติ"
    if "space" in keys and MAIN_MODS & mods:  # Spotlight, the input source
        return f"{name} ระบบใช้อยู่แล้ว"
    if mods == {"cmd"}:  # ⌘ and a key: some app's menu has it (⌘C, ⌘S, ⌘Q...)
        return f"{name} ชนกับคีย์ลัดในเมนูของแอปอื่น: เพิ่ม ⌃ ⌥ หรือ ⇧"
    return ""
