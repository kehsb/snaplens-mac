"""The installer's window (dmg.py): background.png and background@2x.png here, drawn once with Qt, off screen.
.venv/bin/python assets/dmg/background.py
A mid-tone slate, so Finder's icon names read in black (Light) and in white (Dark) alike: ~4:1 either way. The app's
dashed capture frame around the two icons, its icon and name at the top, an arrow from the app to Applications."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # no window, no Dock icon

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (QColor, QFont, QGuiApplication, QImage, QLinearGradient,  # noqa: E402
                           QPainter, QPainterPath, QPen, QRadialGradient)

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 600, 420  # dmg.py's window is 600 x 440 with its title bar: a little to spare at the bottom
APP, APPS, ROW = 160, 440, 200  # the icons' centres (dmg.py's icon_locations), 128 pt each
WHITE = QColor(255, 255, 255)


def tone(c, a):
    c = QColor(c)
    c.setAlphaF(a)
    return c


def draw(p):
    sky = QLinearGradient(0, 0, 0, H)
    sky.setColorAt(0, QColor("#6b7f9e"))
    sky.setColorAt(1, QColor("#53658a"))
    p.fillRect(QRectF(0, 0, W, H), sky)
    glow = QRadialGradient(QPointF(W / 2, -40), 420)  # light from above, as on a Mac's wallpaper
    glow.setColorAt(0, tone(WHITE, .14))
    glow.setColorAt(1, tone(WHITE, 0))
    p.fillRect(QRectF(0, 0, W, H), glow)

    frame = QPen(tone("#9fdcff", .45), 2, Qt.CustomDashLine, Qt.RoundCap)  # the icon's dashed capture region
    frame.setDashPattern([5, 4])
    p.setPen(frame)
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(56, 104, W - 112, 216), 22, 22)

    logo = QImage(os.path.join(HERE, "..", "icons", "app-256.png"))
    name = QFont([".AppleSystemUIFont", "Helvetica Neue"])
    name.setPixelSize(22)
    name.setWeight(QFont.DemiBold)
    p.setFont(name)
    width = p.fontMetrics().horizontalAdvance("Snaplens")
    x = (W - 30 - 10 - width) / 2
    p.drawImage(QRectF(x, 41, 30, 30), logo)
    p.setPen(tone(WHITE, .95))
    p.drawText(QRectF(x + 40, 36, width + 4, 40), Qt.AlignVCenter | Qt.AlignLeft, "Snaplens")

    arrow = QPainterPath(QPointF(APP + 78, ROW))  # from the app's icon edge to Applications'
    arrow.lineTo(APPS - 78, ROW)
    arrow.moveTo(APPS - 92, ROW - 13)
    arrow.lineTo(APPS - 78, ROW)
    arrow.lineTo(APPS - 92, ROW + 13)
    p.setPen(QPen(tone(WHITE, .85), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(arrow)

    hint = QFont([".AppleSystemUIFont", "Thonburi"])
    hint.setPixelSize(13)
    p.setFont(hint)
    p.setPen(tone(WHITE, .85))
    p.drawText(QRectF(0, 340, W, 24), Qt.AlignCenter, "ลาก Snaplens ไปไว้ที่ Applications เพื่อติดตั้ง")


def render(scale, path):
    im = QImage(W * scale, H * scale, QImage.Format_ARGB32_Premultiplied)
    im.setDotsPerMeterX(round(72 * scale / .0254))  # 72 / 144 dpi: tiffutil pairs them as one HiDPI background
    im.setDotsPerMeterY(round(72 * scale / .0254))
    p = QPainter(im)
    p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
    p.scale(scale, scale)
    draw(p)
    p.end()
    im.convertToFormat(QImage.Format_RGB32).save(path)


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    render(1, os.path.join(HERE, "background.png"))
    render(2, os.path.join(HERE, "background@2x.png"))
