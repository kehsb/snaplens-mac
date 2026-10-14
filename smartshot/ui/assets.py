"""Fonts for what Qt still paints (text drawn into the image; the canvas's tag and badges), the badges' line icons,
the app's icon."""
import os
from functools import lru_cache

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon
from PySide6.QtSvg import QSvgRenderer

from smartshot.config import ASSETS, FONTS


def font(px, bold=False):  # Thai needs a font with Thai glyphs, else tofu boxes
    f = QFont()
    f.setFamilies(FONTS)
    f.setPixelSize(px)
    f.setBold(bold)
    return f


def setup_app(app):  # the app's icon (from source: Python's otherwise), on its alerts too
    app.setWindowIcon(QIcon(os.path.join(ASSETS, "icons", "app-256.png")))


def ui_font(px, weight=QFont.Normal, mono=False):  # the system's: SF (and its Thai), or Menlo for numbers
    f = QFontDatabase.systemFont(QFontDatabase.FixedFont if mono else QFontDatabase.GeneralFont)
    f.setPixelSize(px)
    f.setWeight(weight)
    return f


# the QR badges' glyphs on the image (slipcard.model's marks), design/liquid-glass/source/Icon.dc.html: strokes of
# 1.75 on a 24 grid
GLYPHS = {
    "check": "M5 12.5l4.5 4.5L19 7.5",
    "x": "M7 7l10 10M17 7L7 17",
    "question": "M9.5 9.2a2.6 2.6 0 1 1 3.7 2.4c-.7.3-1.2 1-1.2 1.8v.6M12 17.5v.1",
    "history": "M4.5 12a7.5 7.5 0 1 0 2.2-5.3M4 4v4h4M12 8.5V12l2.8 1.8",
    "search": "M10.5 4a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13zM20 20l-4.8-4.8",
    "qr": "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h2.5v2.5H14zM17.5 17.5H20V20h-2.5zM14 20h1M20 14v1",
    "key": "M14.5 9.5a4 4 0 1 1-8 0 4 4 0 0 1 8 0zM13.4 12.3L20 19v1h-2v-1.5h-1.5V17H15",
}


@lru_cache(256)
def glyph_svg(name, argb, stroke):
    c = QColor(argb)
    return QSvgRenderer(QByteArray(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c.name()}" '
        f'stroke-opacity="{c.alphaF():.3f}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">'
        f'<path d="{GLYPHS[name]}"/></svg>'.encode()))
