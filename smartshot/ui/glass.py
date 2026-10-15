"""The canvas's own glass, painted by Qt (design/liquid-glass/HANDOFF.md): the size tag and the magnifier's label
over the capture frosted, and their shadows. The chrome is native (native.glass)."""
from functools import lru_cache

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPixmap

from smartshot.system import mac


def chrome():  # background, border of glass drawn opaque (Reduce transparency on)
    return ("#1C1F26", "#333844") if mac.dark() else ("#F4F5F8", "#D5D8DE")


def qimage(bgr):  # BGR ndarray -> QImage that owns its pixels
    bgr = np.ascontiguousarray(bgr)
    h, w, _ = bgr.shape
    return QImage(bgr.data, w, h, 3 * w, QImage.Format_BGR888).copy()


# kind -> fill, edge, lit top edge; dark glass is the default on a capture
GLASS = {"bar": ((28, 30, 36, .38), (255, 255, 255, .16), (255, 255, 255, .32))}
GLASS_LIGHT = {"bar": ((255, 255, 255, .55), (255, 255, 255, .8), (255, 255, 255, 1))}
DIM = QColor(6, 8, 12, 107)  # the capture around the selection: CSS rgba(6,8,12,.42)


def rgba(r, g, b, a=1.0):
    return QColor(r, g, b, round(a * 255))


def glass(kind):  # -> fill, edge, lit edge (QColor)
    return [rgba(*c) for c in (GLASS if mac.dark() else GLASS_LIGHT)[kind]]


def ink(a=1.0):  # text and icons on glass: white on dark, #1C1F26 on light; a: secondary .68, faint .5
    return rgba(255, 255, 255, a) if mac.dark() else rgba(28, 31, 38, a)


def clear():  # glass shows what's behind it, unless Accessibility > Display > Reduce transparency is on
    return not mac.reduce_transparency()


def paint_glass(p, r, kind, radius, under=None):
    """A glass surface on r (QRectF): under(p, r) paints what's behind it, frosted (None: opaque glass), then the
    glass's fill, a 1px lit top edge inside and a 1px border (opaque glass: chrome()'s), in a rounded rect."""
    fill, edge, lit = glass(kind)
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
