"""Liquid Glass painting (design/liquid-glass/HANDOFF.md): colours, glass surfaces, shadows, frost."""
from functools import lru_cache

import cv2
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap
from qfluentwidgets import isDarkTheme

from smartshot.system import mac
from smartshot.ui.assets import ui_font


def chrome():  # background, border of glass drawn opaque (receipts; Reduce transparency on)
    return ("#1C1F26", "#333844") if isDarkTheme() else ("#F4F5F8", "#D5D8DE")


def field_qss(radius, pad):  # a text box on glass (in QSS: a palette's placeholder colour is overridden)
    return (f"QLineEdit{{background:{"#4d000000" if isDarkTheme() else "#ccffffff"};border:1px solid {ink(.14).name(QColor.HexArgb)};border-radius:{radius}px;"
            f"padding:0 {pad}px;color:{ink().name(QColor.HexArgb)};placeholder-text-color:{ink(.4).name(QColor.HexArgb)}}}")


def qimage(bgr):  # BGR ndarray -> QImage that owns its pixels
    bgr = np.ascontiguousarray(bgr)
    h, w, _ = bgr.shape
    return QImage(bgr.data, w, h, 3 * w, QImage.Format_BGR888).copy()


# --- Liquid Glass (design/liquid-glass/HANDOFF.md): glass surfaces, fonts, line icons
# kind -> fill, edge, lit top edge, shadow (dy, blur, colour); dark glass is the default on a capture
GLASS = {"bar": ((28, 30, 36, .38), (255, 255, 255, .16), (255, 255, 255, .32), (16, 40, (0, 0, 0, .35))),
         "card": ((28, 30, 36, .42), (255, 255, 255, .18), (255, 255, 255, .34), (24, 64, (0, 0, 0, .42))),
         "tint": ((76, 194, 255, .42), (160, 224, 255, .45), (255, 255, 255, .5), (16, 40, (0, 0, 0, .35))),
         "menu": ((20, 22, 28, .45), (255, 255, 255, .18), (255, 255, 255, .32), (20, 50, (0, 0, 0, .4))),
         "tip": ((20, 22, 28, .6), (255, 255, 255, .18), (255, 255, 255, .3), (10, 24, (0, 0, 0, .35))),
         "toast": ((20, 22, 28, .5), (255, 255, 255, .18), (255, 255, 255, .35), (12, 30, (0, 0, 0, .3))),
         "alarm": ((255, 70, 70, .32), (255, 170, 170, .4), (255, 255, 255, .35), (12, 30, (0, 0, 0, .3)))}
GLASS_LIGHT = {"bar": ((255, 255, 255, .55), (255, 255, 255, .8), (255, 255, 255, 1), (14, 36, (20, 30, 60, .16))),
               "card": ((255, 255, 255, .55), (255, 255, 255, .8), (255, 255, 255, 1), (24, 60, (20, 30, 60, .18))),
               "tint": ((47, 155, 224, .85), (255, 255, 255, .6), (255, 255, 255, .6), (14, 36, (20, 30, 60, .18))),
               "menu": ((255, 255, 255, .55), (255, 255, 255, .8), (255, 255, 255, 1), (20, 50, (20, 30, 60, .18))),
               "tip": ((255, 255, 255, .7), (255, 255, 255, .8), (255, 255, 255, 1), (10, 24, (20, 30, 60, .16))),
               "toast": ((255, 255, 255, .6), (255, 255, 255, .8), (255, 255, 255, 1), (12, 30, (20, 30, 60, .16))),
               "alarm": ((255, 70, 70, .18), (255, 120, 120, .5), (255, 255, 255, .8), (12, 30, (20, 30, 60, .16)))}
DIM = QColor(6, 8, 12, 107)  # the capture around the selection: CSS rgba(6,8,12,.42)


def rgba(r, g, b, a=1.0):
    return QColor(r, g, b, round(a * 255))


def glass(kind):  # -> fill, edge, lit edge (QColor), shadow (dy, blur, rgba)
    fill, edge, lit, drop = (GLASS if isDarkTheme() else GLASS_LIGHT)[kind]
    return rgba(*fill), rgba(*edge), rgba(*lit), drop


def ink(a=1.0):  # text and icons on glass: white on dark, #1C1F26 on light; a: secondary .68, faint .5
    return rgba(255, 255, 255, a) if isDarkTheme() else rgba(28, 31, 38, a)


def themed(dark, light):  # a colour the boards give each theme its own of (light: G8's), rgba tuples
    return rgba(*(dark if isDarkTheme() else light))


def clear():  # glass shows what's behind it, unless Accessibility > Display > Reduce transparency is on
    return not mac.reduce_transparency()


def paint_glass(p, r, kind, radius, under=None):
    """A glass surface on r (QRectF): under(p, r) paints what's behind it, frosted (None: opaque glass), then the
    glass's fill, a 1px lit top edge inside and a 1px border (opaque glass: chrome()'s), in a rounded rect."""
    fill, edge, lit, _ = glass(kind)
    p.save()
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    shape = QPainterPath()
    shape.addRoundedRect(r, radius, radius)
    p.setClipPath(shape)
    if under:
        p.save()
        under(p, r)
        p.restore()
    else:
        p.fillRect(r, QColor(chrome()[0]))
    p.fillRect(r, fill)
    rim(p, r.adjusted(1, 1, -1, -1), radius - 1, lit)
    p.setClipping(False)
    p.setPen(QPen(edge if under else QColor(chrome()[1]), 1))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(r.adjusted(.5, .5, -.5, -.5), radius - .5, radius - .5)
    p.restore()


def rim(p, r, radius, color):  # CSS box-shadow: inset 0 1px 0 color: the top edge lit
    inner = QPainterPath()
    inner.addRoundedRect(r, radius, radius)
    p.fillPath(inner - inner.translated(0, 1), color)


def wash(p, r, radius, a, lit=0.0, tint=False):  # a white wash on glass (a button hovered, pressed, picked), its top
    path = QPainterPath()  # edge lit; light glass (not tint's): picked, white and edged (G8's tool); else a dark wash
    path.addRoundedRect(r, radius, radius)
    if isDarkTheme() or tint:
        p.fillPath(path, rgba(255, 255, 255, a))
        if lit:
            rim(p, r, radius, rgba(255, 255, 255, lit))
    elif lit:
        p.fillPath(path, QColor(Qt.white))
        edge = QPainterPath()
        edge.addRoundedRect(r.adjusted(.5, .5, -.5, -.5), radius - .5, radius - .5)
        p.strokePath(edge, QPen(rgba(28, 31, 38, .12), 1))
    else:
        p.fillPath(path, ink(a))


def ink_dot(p, c, d, color, ring):  # a colour dot of diameter d centred on c, shadowed; ring: in a 2px white ring
    o = d + 4 if ring else d      # (the toolbar's), else its top edge lit (the popover's)
    p.drawImage(QPointF(c.x() - o / 2 - 6, c.y() - o / 2 - 4), shadow(o, o, o // 2, 6, (0, 0, 0, .35 if ring else .3)))
    r = QRectF(c.x() - d / 2, c.y() - d / 2, d, d)
    p.setPen(Qt.NoPen)
    if ring:
        p.setBrush(rgba(255, 255, 255, .85))
        p.drawEllipse(r.adjusted(-2, -2, 2, 2))
    p.setBrush(QColor(color))
    p.drawEllipse(r)
    if not ring:
        rim(p, r, d / 2, rgba(255, 255, 255, .45))


@lru_cache(32)
def shadow(w, h, radius, blur, color):  # CSS box-shadow of a w x h rounded rect, unshifted: an image blur px bigger each side
    m = np.zeros((h + 2 * blur, w + 2 * blur), np.float32)
    x0, y0, x1, y1, r = blur, blur, blur + w - 1, blur + h - 1, min(radius, w // 2, h // 2)
    cv2.rectangle(m, (x0 + r, y0), (x1 - r, y1), 1, -1)
    cv2.rectangle(m, (x0, y0 + r), (x1, y1 - r), 1, -1)
    for c in ((x0 + r, y0 + r), (x1 - r, y0 + r), (x0 + r, y1 - r), (x1 - r, y1 - r)):
        cv2.circle(m, c, r, 1, -1)
    a = cv2.GaussianBlur(m, (0, 0), blur / 2) * color[3]  # CSS blur radius = 2 sigma
    bgra = np.dstack([a * color[2], a * color[1], a * color[0], a * 255]).astype(np.uint8)  # premultiplied
    return QImage(bgra.data, bgra.shape[1], bgra.shape[0], 4 * bgra.shape[1], QImage.Format_ARGB32_Premultiplied).copy()


# ponytail: blurred at full size on the UI thread (~50 ms for 1080p, once per selection); 9-slice it if 4K drags lag
frame_shadow = lru_cache(1)(shadow.__wrapped__)  # the selection's, as big as it: only the latest kept


def frost(bgr, size, blur):  # what glass shows of bgr (seen at size): CSS blur(px) saturate(1.7), at a quarter size
    small = cv2.resize(bgr, (max(size.width() // 4, 1), max(size.height() // 4, 1)), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(cv2.GaussianBlur(small, (0, 0), blur / 4), cv2.COLOR_BGR2HSV)  # (it's drawn scaled up)
    hsv[..., 1] = np.minimum(hsv[..., 1] * 1.7, 255)
    return QPixmap.fromImage(qimage(cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)))


def write(p, r, text, px, a=1.0, weight=QFont.Normal, mono=False, align=Qt.AlignLeft):  # a line in r, centred up and down
    p.setFont(ui_font(px, weight, mono))
    p.setPen(ink(a))
    p.drawText(r, align | Qt.AlignVCenter, text)


def focus_ring(p, w, r, radius):  # on w if it has the focus by the keyboard (Tab), not by activation or a click
    if w.hasFocus() and w.window().testAttribute(Qt.WA_KeyboardFocusChange):
        p.setPen(QPen(ink(.85), 2))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(1, 1, -1, -1), radius - 1, radius - 1)
