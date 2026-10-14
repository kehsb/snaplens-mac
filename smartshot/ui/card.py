"""The QR card's pieces: verdict colours and marks, plain-text labels."""
import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QLabel

from smartshot.slip.thunder import NO_KEY, THUNDER_ERRORS
from smartshot.ui.assets import ui_font
from smartshot.ui.glass import ink, rgba


# --- the QR card's pieces
# verdict -> the card's head disc: fill, line (design: these colours are for verdicts, nowhere else)
TONES = {"ok": ((52, 199, 120, .55), (140, 240, 180, .5)), "warn": ((255, 170, 40, .55), (255, 214, 140, .5)),
         "bad": ((255, 70, 70, .55), (255, 160, 160, .5)), "info": ((76, 194, 255, .5), (170, 228, 255, .5)),
         "none": ((255, 255, 255, .16), (255, 255, 255, .25))}
MARKS = {"✓": ("check", (52, 199, 120, .7)), "✗": ("x", (255, 70, 70, .75)), "?": ("question", (255, 255, 255, .16))}
TONES_LIGHT = {"ok": ((31, 162, 94), (31, 162, 94)), "warn": ((224, 138, 0), (224, 138, 0)),  # G8's (light glass)
               "bad": ((229, 72, 77), (229, 72, 77)), "info": ((47, 155, 224), (47, 155, 224)),
               "none": ((122, 130, 148), (122, 130, 148))}
MARKS_LIGHT = {"✓": ("check", (31, 162, 94)), "✗": ("x", (229, 72, 77)), "?": ("question", (122, 130, 148, .6))}
KEYLESS = (NO_KEY, THUNDER_ERRORS["INVALID_API_KEY"])  # answers the card asks for a key on
MONEY = re.compile(r"(?<![\d.,])\d{1,3}(?:,?\d{3})*\.\d\d(?!\d)")  # 123.45, 1,234.56; not part of a longer number
# wrap points in runs of 28+ (links; Thai, which Qt can't break here), not amid Thai marks; refs stay clean to paste
BREAK = re.compile(r"\S{20,}?(?<![\u0e40-\u0e44])(?=[^\s\u0e30-\u0e3a\u0e45\u0e47-\u0e4e]\S{7})")


def lab(text, px=14, a=1.0, weight=QFont.Normal, mono=False, sel=False, color=None):  # plain text only: QR and Thunder strings are untrusted
    w = QLabel(BREAK.sub("\\g<0>\u200b", text if len(text) <= 400 else text[:400] + "…"))
    w.setTextFormat(Qt.PlainText)
    w.setWordWrap(True)
    w.setTextInteractionFlags(Qt.TextSelectableByMouse if sel else Qt.NoTextInteraction)
    w.setFont(ui_font(px, weight, mono))
    w.setStyleSheet(f"color:{(color or ink(a)).name(QColor.HexArgb)}")
    return w


def tone_ink(tone):  # a verdict's colour, solid: its code's box and badge on the image ("none": grey, seen on white too)
    return QColor("#8a8a8a") if tone == "none" else rgba(*TONES[tone][0][:3])
