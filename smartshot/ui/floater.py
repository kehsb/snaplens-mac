"""A capture kept on the desktop, its menu, and the notice after an update."""
import numpy as np
from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, QSize, QTimer, Qt
from PySide6.QtGui import QAccessible, QAccessibleEvent, QFont, QFontMetrics, QGuiApplication, QImage, QPainter
from PySide6.QtWidgets import QWidget

from smartshot.ui.assets import app_svg, ui_font
from smartshot.ui.glass import clear, frost, ink, write
from smartshot.ui.overlay import Overlay
from smartshot.ui.widgets import GlassMenu, GlassPanel


class Floater(QWidget):
    """A glass panel out on the desktop (the tray's menu, a notice) in a clear window of its own, with room round the
    panel for its shadow. Its glass frosts the screen as it was when it opened (ponytail: a still, not live; it's up
    for seconds). It goes when the panel hides (a pick, Esc, a click on it) and, a popup, on a click elsewhere."""
    M = 70  # room for the shadow: its blur and drop
    up = set()  # the open ones: nothing else holds them

    def __init__(self, popup):
        super().__init__(None, (Qt.Popup if popup else Qt.Tool | Qt.WindowStaysOnTopHint) | Qt.FramelessWindowHint
                         | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating, not popup)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)  # else hidden while another app is in front
        self.popup, self.clear = popup, clear()
        Floater.up.add(self)

    def open(self, panel, at):  # panel (a child) with its top-left at screen point at, kept in the work area
        scr = QGuiApplication.screenAt(at + QPoint(0, panel.height())) or QGuiApplication.primaryScreen()  # a menu's anchor
        self.work = work = scr.availableGeometry()
        s = scr.geometry()
        at = QPoint(min(max(at.x(), work.left()), work.right() + 1 - panel.width()),
                    min(max(at.y(), work.top()), work.bottom() + 1 - panel.height()))
        if self.clear:  # what's under the panel, before it's there
            img = scr.grabWindow(0, at.x() - s.x(), at.y() - s.y(), panel.width(), panel.height()).toImage()
            img = img.convertToFormat(QImage.Format_BGR888)
            px = np.frombuffer(img.constBits(), np.uint8).reshape(img.height(), img.bytesPerLine())
            self.frost = frost(px[:, :img.width() * 3].reshape(img.height(), img.width(), 3), panel.size(), 30)
        self.setGeometry(QRect(at - QPoint(self.M, self.M), panel.size() + QSize(2 * self.M, 2 * self.M)))
        panel.move(self.M, self.M)
        panel.installEventFilter(self)
        self.show()
        if self.popup:
            self.activateWindow()

    def backdrop(self, p, r, panel=None):  # under the panel's glass at r (this window's px): the screen, frosted
        q = self.frost.width() / (self.width() - 2 * self.M)
        p.drawPixmap(QRectF(r), self.frost, QRectF((r.x() - self.M) * q, (r.y() - self.M) * q, r.width() * q, r.height() * q))

    shadows = Overlay.shadows

    def paintEvent(self, _):  # none over the taskbar or the next screen: clear (alpha 0) lets their clicks through
        p = QPainter(self)
        p.setClipRect(self.work.translated(-self.pos()))
        self.shadows(p)
        p.end()

    def eventFilter(self, _, e):
        if e.type() == QEvent.Hide:
            self.close()
        return False

    def hideEvent(self, e):  # let go once this event is through: Python deletes it then
        QTimer.singleShot(0, lambda: Floater.up.discard(self))


def float_menu(rows, at, head=""):  # a GlassMenu on the desktop (the tray's), its bottom-left at screen point at
    f = Floater(True)
    m = GlassMenu(f, rows, 280, head)
    f.open(m, QPoint(at.x(), at.y() - m.height()))
    m.popup(QPoint(f.M, f.M))
    return m


class Notice(GlassPanel):
    """G4's notice at the top right, under the menu bar, where the system's own notices are (the app is out of sight
    there): its icon and name, a title and a line or two. Goes after 5 s or on a click."""

    def __init__(self, title, text):
        super().__init__(Floater(False), "menu", 24)
        self.title, self.text = title, text
        self.setAccessibleName(f"{title}. {text}")
        self.lines = QFontMetrics(ui_font(14)).boundingRect(QRect(0, 0, 256, 1000), Qt.TextWordWrap, text).height()
        self.resize(340, 62 + self.lines + 16)  # CSS: padding 16 18; the icon 36, 12 before the words
        QTimer(self, singleShot=True, interval=5000, timeout=self.hide).start()
        work = QGuiApplication.primaryScreen().availableGeometry()
        self.window().open(self, QPoint(work.right() - 14 - self.width(), work.top() + 14))  # 15 clear
        QAccessible.updateAccessibility(QAccessibleEvent(self, QAccessible.Alert))

    def mousePressEvent(self, e):
        self.hide()

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        app_svg().render(p, QRectF(18, 16, 36, 36))
        w = self.width() - 84
        write(p, QRectF(66, 16, w, 18), "Snaplens", 12, .6)
        write(p, QRectF(66, 16, w, 18), "ตอนนี้", 12, .6, align=Qt.AlignRight)
        write(p, QRectF(66, 37, w, 22), self.title, 15, weight=QFont.DemiBold)
        p.setPen(ink(.8))
        p.setFont(ui_font(14))
        p.drawText(QRectF(66, 62, w, self.lines), Qt.TextWordWrap, self.text)
        p.end()
