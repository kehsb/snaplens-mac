"""The design's bundled fonts and line icons, the app and tray icons."""
import glob
import os
from functools import lru_cache

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon
from PySide6.QtSvg import QSvgRenderer
from qfluentwidgets import setFontFamilies

from smartshot.config import ASSETS, FONTS, MONO, UI_FONTS


def font(px, bold=False):  # Thai needs a font with Thai glyphs, else tofu boxes
    f = QFont()
    f.setFamilies(FONTS)
    f.setPixelSize(px)
    f.setBold(bold)
    return f


def setup_app(app):  # the design's fonts, bundled (a family that won't load falls back to the next), and the app's icon
    for f in glob.glob(os.path.join(ASSETS, "fonts", "*.ttf")):
        QFontDatabase.addApplicationFont(f)
    setFontFamilies(UI_FONTS)  # qfluentwidgets' labels, buttons, menus
    f = app.font()
    f.setFamilies(UI_FONTS)
    app.setFont(f)
    app.setWindowIcon(QIcon(os.path.join(ASSETS, "icons", "app-256.png")))


def ui_font(px, weight=QFont.Normal, mono=False):
    f = QFont()
    f.setFamilies(MONO if mono else UI_FONTS)
    f.setPixelSize(px)
    f.setWeight(weight)
    return f


def tray_icon():  # a template image: the menu bar draws it in its own colour
    icon = QIcon()
    for s in (16, 20, 24, 32):
        icon.addFile(os.path.join(ASSETS, "icons", f"tray-light-{s}.png"))
    icon.setIsMask(True)
    return icon


# design/liquid-glass/source/Icon.dc.html: strokes of 1.75 on a 24 grid
GLYPHS = {
    "select": "M4 8V5.5A1.5 1.5 0 0 1 5.5 4H8M16 4h2.5A1.5 1.5 0 0 1 20 5.5V8M20 16v2.5a1.5 1.5 0 0 1-1.5 1.5H16M8 20H5.5A1.5 1.5 0 0 1 4 18.5V16M9 9h6M12 9v7",
    "pen": "M4 20l1-4L15.5 5.5a2.1 2.1 0 0 1 3 3L8 19l-4 1zM14 7l3 3",
    "marker": "M4 20h7M8 17l-2-2L15.5 5.5a2.1 2.1 0 0 1 3 3L9 18zM6 15l-2 2v3h3l1-1",
    "rect": "M5.5 6h13A1.5 1.5 0 0 1 20 7.5v9a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 16.5v-9A1.5 1.5 0 0 1 5.5 6z",
    "arrow": "M5 19L19 5M10 5h9v9",
    "text": "M5 7V5h14v2M12 5v14M9 19h6",
    "mosaic": "M4 4h5v5H4zM9 9h6v6H9zM15 4h5v5h-5zM4 15h5v5H4zM15 15h5v5h-5z",
    "undo": "M9 14L4 9l5-5M4 9h10.5a5.5 5.5 0 0 1 0 11H11",
    "translate": "M4 6h9M8.5 4v2M6 6c.8 3.6 3 6.2 6.5 7.6M11 6c-.8 3.6-3 6.2-6.5 7.6M13 20l3.5-8.5L20 20M14.2 17.2h4.6",
    "copy": "M9 9h10v11H9zM15 9V4H5v11h4M12 13h4M12 16h3",
    "image": "M5 5h14a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zM4 16l5-5 4 4 2.5-2.5L20 17M15.5 9.5h.01",
    "save": "M12 4v11M7.5 10.5L12 15l4.5-4.5M5 20h14",
    "close": "M6 6l12 12M18 6L6 18",
    "minus": "M6 12h12",
    "check": "M5 12.5l4.5 4.5L19 7.5",
    "x": "M7 7l10 10M17 7L7 17",
    "question": "M9.5 9.2a2.6 2.6 0 1 1 3.7 2.4c-.7.3-1.2 1-1.2 1.8v.6M12 17.5v.1",
    "history": "M4.5 12a7.5 7.5 0 1 0 2.2-5.3M4 4v4h4M12 8.5V12l2.8 1.8",
    "search": "M10.5 4a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13zM20 20l-4.8-4.8",
    "refresh": "M19.5 10A7.5 7.5 0 0 0 5.6 7.5M5 4v3.5h3.5M4.5 14a7.5 7.5 0 0 0 13.9 2.5M19 20v-3.5h-3.5",
    "qr": "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h2.5v2.5H14zM17.5 17.5H20V20h-2.5zM14 20h1M20 14v1",
    "chevron": "M7 10l5 5 5-5",
    "chevronRight": "M10 7l5 5-5 5",
    "sliders": "M4 7h9M17 7h3M4 17h3M11 17h9M15 5v4M9 15v4",
    "power": "M12 4v7M7.2 6.8a7 7 0 1 0 9.6 0",
    "key": "M14.5 9.5a4 4 0 1 1-8 0 4 4 0 0 1 8 0zM13.4 12.3L20 19v1h-2v-1.5h-1.5V17H15",
    "keyboard": "M4 7h16a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1zM7 10h.01M10 10h.01M13 10h.01M16 10h.01M8 14h8",
    "exit": "M14 4h4.5A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5H14M10 8l-4 4 4 4M6 12h9",
    "capture": "M4 9V5.5A1.5 1.5 0 0 1 5.5 4H9M15 4h3.5A1.5 1.5 0 0 1 20 5.5V9M20 15v3.5a1.5 1.5 0 0 1-1.5 1.5H15M9 20H5.5A1.5 1.5 0 0 1 4 18.5V15",
    "camera": "M4 8.5A1.5 1.5 0 0 1 5.5 7H8l1.5-2h5L16 7h2.5A1.5 1.5 0 0 1 20 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5zM12 10a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
    "lang": "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM3.5 12h17M12 3.5c2.3 2.4 3.4 5.2 3.4 8.5S14.3 18.1 12 20.5M12 3.5C9.7 5.9 8.6 8.7 8.6 12s1.1 6.1 3.4 8.5",
    "spark": "M12 4v4M12 16v4M4 12h4M16 12h4M6.5 6.5l2.5 2.5M15 15l2.5 2.5M17.5 6.5L15 9M9 15l-2.5 2.5",
    "shield": "M12 3.5l7 2.8v5.2c0 4.3-2.9 7.6-7 9-4.1-1.4-7-4.7-7-9V6.3zM8.8 12.2l2.2 2.2 4.2-4.4",
    "clock": "M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16zM12 8v4.2l2.8 1.8",
    "eye": "M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12zM12 9.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z",
}


@lru_cache(256)
def glyph_svg(name, argb, stroke):
    c = QColor(argb)
    return QSvgRenderer(QByteArray(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c.name()}" '
        f'stroke-opacity="{c.alphaF():.3f}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">'
        f'<path d="{GLYPHS[name]}"/></svg>'.encode()))


@lru_cache(1)
def app_svg():  # the app's icon, at any size
    return QSvgRenderer(os.path.join(ASSETS, "icons", "app.svg"))
