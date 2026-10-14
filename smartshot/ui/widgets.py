"""Glass widgets shared by the capture and the windows: panels, buttons, tips, toasts, menus."""
import time

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractButton, QApplication, QGraphicsDropShadowEffect, QWidget
from qfluentwidgets import isDarkTheme

from smartshot.ui.assets import glyph_svg, ui_font
from smartshot.ui.glass import focus_ring, glass, ink, ink_dot, paint_glass, rgba, rim, themed, wash


class GlassPanel(QWidget):
    """A glass surface (paint_glass) over its window's backdrop() if it has one (the capture overlay) and Reduce
    transparency is off (its clear), else opaque.
    radius None: a capsule. Its shadow falls outside it, so the window paints that (Overlay.shadows)."""
    flat = False  # opaque for now: a receipt shows nothing of the screen behind the card

    def __init__(self, parent=None, kind="bar", radius=None):
        super().__init__(parent)
        self.kind, self.radius = kind, radius

    def corner(self):
        return self.height() / 2 if self.radius is None else self.radius

    def mousePressEvent(self, e):  # a click on glass isn't one on the screen behind; a right-click still opens the menu
        e.setAccepted(e.button() == Qt.LeftButton)

    def paintEvent(self, _):
        o, at = self.window(), self.mapTo(self.window(), QPoint())
        under = None if self.flat or not getattr(o, "clear", 0) else \
            lambda p, r: (p.translate(-at), o.backdrop(p, r.translated(QPointF(at)).toRect(), self))
        p = QPainter(self)
        paint_glass(p, QRectF(self.rect()), self.kind, self.corner(), under)
        p.end()

    def moveEvent(self, _):  # its shadow moves with it: the window repaints it
        self.window().update()

    resizeEvent = hideEvent = showEvent = moveEvent


class GlassButton(QAbstractButton):
    """A 40px round button on glass: a line icon (glyph), a colour dot (swatch) or an icon and text; a white wash when
    hovered, pressed or checked. tip, keys: its glass tooltip (Overlay.tipbox). Takes no focus: keys stay the overlay's.
    look: the card's capsules: "soft" (white .14), "plain" (none), "solid" (white, dark text), "tint" (blue, 44 high);
    "dim" (white .08): the settings window's own. There they take Tab focus and show Qt's tooltip (setToolTip)."""

    dim = .08, .8  # look "dim": its fill, its ink (G4's)

    def __init__(self, glyph=None, text="", tip="", keys="", look=None):
        super().__init__()
        self.glyph, self.swatch, self.tip, self.keys, self.look = glyph, None, tip, keys, look
        self.icon_px = 18 if text else 20
        self.setText(text)
        self.setFont(ui_font(14, QFont.Medium if look in ("soft", "plain") else QFont.DemiBold))
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_Hover)
        if look == "solid":  # CSS box-shadow: 0 4px 14px rgba(0,0,0,.25)
            self.setGraphicsEffect(QGraphicsDropShadowEffect(blurRadius=14, offset=QPointF(0, 4), color=rgba(0, 0, 0, .25)))

    def sizeHint(self):
        tw = self.fontMetrics().horizontalAdvance(self.text())
        if self.look:  # CSS padding 0 16 (no icon: 0 18), gap 8
            return QSize(32 + (self.icon_px + 8 if self.glyph else 4) + tw, 44 if self.look == "tint" else 40)
        return QSize(28 + self.icon_px + tw if self.text() else 40, 40)  # CSS padding 0 8 0 12, gap 8

    def event(self, e):
        box = getattr(self.window(), "tipbox", None)  # the overlay's
        if box and e.type() == QEvent.ToolTip:
            if self.tip:
                box.show_for(self)
            return True
        if box and e.type() in (QEvent.Leave, QEvent.MouseButtonPress):
            box.hide()
        return super().event(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        if not self.isEnabled():
            p.setOpacity(.4)
        r, s, look = QRectF(self.rect()), self.icon_px, self.look
        tint = look == "tint" or isinstance(self.parent(), GlassPanel) and self.parent().kind == "tint"
        c = QColor(Qt.white) if tint else ink()  # (on the tint glass: white, G8's)
        if look:  # a capsule of its own; a wash over it when hovered or pressed (solid: whiter)
            body, rad = QPainterPath(), r.height() / 2
            body.addRoundedRect(r.adjusted(.5, .5, -.5, -.5), rad - .5, rad - .5)
            if look == "solid":
                p.fillPath(body, themed((255, 255, 255, 1 if self.underMouse() else .9), (28, 31, 38, .85 if self.underMouse() else 1)))
                c = themed((11, 13, 18), (255, 255, 255))
            elif look == "plain":
                c = ink(.8)
            elif look == "dim":
                p.fillPath(body, ink(self.dim[0]))
                p.strokePath(body, QPen(ink(.14), 1))
                c = ink(self.dim[1])
            elif look == "tint":
                p.fillPath(body, themed((76, 194, 255, .55), (47, 155, 224, .85)))
                p.strokePath(body, QPen(themed((170, 228, 255, .5), (255, 255, 255, .6)), 1))
                rim(p, r.adjusted(1, 1, -1, -1), rad - 1, themed((255, 255, 255, .5), (255, 255, 255, .6)))
                c = QColor(Qt.white)
            elif isDarkTheme():
                p.fillPath(body, ink(.14))
                p.strokePath(body, QPen(ink(.16), 1))
                rim(p, r.adjusted(1, 1, -1, -1), rad - 1, ink(.3))
            else:
                p.fillPath(body, ink(.07))
            if look != "solid" and (self.isDown() or self.underMouse()):
                wash(p, r, rad, .16 if self.isDown() else .08, tint=tint)
            ic = QRectF(16 if self.text() else (r.width() - s) / 2, (r.height() - s) / 2, s, s)
        else:
            if self.isDown() or self.isChecked() or self.underMouse():
                wash(p, r, 20, .22, .45, tint)
            ic = QRectF(12 if self.text() else (r.width() - s) / 2, (r.height() - s) / 2, s, s)
        if self.swatch:
            ink_dot(p, ic.center(), 20, self.swatch, True)
        elif self.glyph:
            glyph_svg(self.glyph, c.name(QColor.HexArgb), 2 if s <= 16 else 1.75).render(p, ic)
        if self.text():
            p.setPen(c)
            if self.glyph:
                p.drawText(r.adjusted(ic.right() + 8, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, self.text())
            else:
                p.drawText(r, Qt.AlignCenter, self.text())
        focus_ring(p, self, r, r.height() / 2 if look else 20)
        p.end()


class Disc(QWidget):
    """A round badge d px: a white glyph (None: a spinner, still asking) on fill; line: a 1px edge and a lit top, as the
    card's head has; badge: (text, colour) in its corner, numbered like its code on the image."""

    def __init__(self, d, fill, line=None, glyph=None, badge=None):
        super().__init__()
        self.setFixedSize(d, d)
        self.fill, self.line, self.glyph, self.badge, self.turn = rgba(*fill), line and rgba(*line), glyph, badge, 90
        if glyph is None:
            QTimer(self, interval=30, timeout=self.spin).start()

    def spin(self):
        self.turn -= 12  # clockwise, a turn a second
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        r, d = QRectF(self.rect()), self.width()
        p.setPen(QPen(self.line, 1) if self.line else Qt.NoPen)
        p.setBrush(self.fill)
        p.drawEllipse(r.adjusted(.5, .5, -.5, -.5))
        if self.line:
            rim(p, r.adjusted(1, 1, -1, -1), d / 2 - 1, rgba(255, 255, 255, .4))
        s = d / 2 if self.line else 13  # CSS: 22 in the head's 44, 13 in a row's 22
        g = QRectF(0, 0, s, s)
        g.moveCenter(r.center())
        if self.glyph:
            glyph_svg(self.glyph, "#ffffffff", 2 if s <= 16 else 1.75).render(p, g)
        else:  # CSS: a ring r 9 of 2.5 on the 24 grid at .3, a quarter of it white
            ring, w = g.adjusted(s / 8, s / 8, -s / 8, -s / 8), 2.5 * s / 24
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(rgba(255, 255, 255, .3), w))
            p.drawEllipse(ring)
            p.setPen(QPen(QColor(Qt.white), w, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(ring, self.turn * 16, -90 * 16)
        if self.badge:
            p.setPen(Qt.NoPen)
            p.setBrush(self.badge[1])
            p.drawEllipse(QRectF(0, 0, 16, 16))
            p.setPen(QColor(Qt.white))
            p.setFont(ui_font(11, QFont.Bold))
            p.drawText(QRectF(0, 0, 16, 16), Qt.AlignCenter, self.badge[0])
        p.end()


class Box(QWidget):
    """A box in the card: radius 22, a faint wash and line. bad: rows of its grid tinted red (the image differs)."""

    def __init__(self):
        super().__init__()
        self.bad = []

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(themed((255, 255, 255, .08), (255, 255, 255, .9)), 1))
        p.setBrush(themed((255, 255, 255, .07), (255, 255, 255, .7)))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 21.5, 21.5)
        p.setPen(Qt.NoPen)
        p.setBrush(rgba(255, 70, 70, .18))
        g = self.layout()
        for i in self.bad:  # CSS: the row's padding 9, radius 16, across the box inside its padding 6
            cells = [it.geometry() for c in range(g.columnCount()) if (it := g.itemAtPosition(i, c))]
            top, bottom = min(r.top() for r in cells), max(r.bottom() for r in cells)
            p.drawRoundedRect(QRectF(6, top - 9, self.width() - 12, bottom - top + 19), 16, 16)
        p.end()


class GlassTip(GlassPanel):
    """The glass tooltip, over the toolbar: what a button does, its keys as keycaps."""

    def __init__(self, parent):
        super().__init__(parent, "tip")
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.text, self.caps = "", []
        self.hide()

    def show_for(self, b):
        x, km, self.text, self.caps = 14 + QFontMetrics(ui_font(14)).horizontalAdvance(b.tip), \
            QFontMetrics(ui_font(12, mono=True)), b.tip, []
        for k in b.keys.split("+") if b.keys else ():  # CSS padding 2 7, 3 apart, 10 after the text
            x += 3 if self.caps else 10
            self.caps.append((QRectF(x, 8, km.horizontalAdvance(k) + 14, 20), k))
            x += self.caps[-1][0].width()
        self.resize(round(x) + (8 if self.caps else 14), 36)
        o, g = self.parentWidget(), b.parentWidget()  # g: the button's capsule
        top = g.mapTo(o, QPoint()).y()
        y = top - 10 - self.height() if top >= 10 + self.height() else top + g.height() + 10
        c = b.mapTo(o, QPoint(b.width() // 2, 0)).x()
        self.move(min(max(c - self.width() // 2, 0), o.width() - self.width()), y)
        self.show()
        self.raise_()

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(ink())
        p.setFont(ui_font(14))
        p.drawText(QRectF(14, 0, self.width(), self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.text)
        p.setFont(ui_font(12, mono=True))
        for r, k in self.caps:
            path = QPainterPath()
            path.addRoundedRect(r, 8, 8)
            p.fillPath(path, ink(.16))
            p.drawText(r, Qt.AlignCenter, k)
        p.end()


class HintBar(GlassPanel):
    """G1, at the top of the screen while nothing is selected: what the mouse does, and the OCR mode that will read
    it. Clicks go through it: a selection can start under it."""
    KEYS = (("ลาก", "เลือกพื้นที่"), ("คลิก", "เลือกช่องที่ไฮไลต์"), ("ล้อเมาส์", "ขยาย/ย่อ"), ("Esc", "ปิด"))

    def __init__(self, parent, mode):
        super().__init__(parent, "bar")
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.chip, km, fm = f"อ่าน: {mode}", QFontMetrics(ui_font(12, mono=True)), QFontMetrics(ui_font(14))
        x, self.keys = 18.0, []
        for k, t in self.KEYS:  # CSS: keycaps padding 3 9, 7 before their words, 18 apart
            self.keys.append((QRectF(x, 15, km.horizontalAdvance(k) + 18, 22), k, t))
            x += self.keys[-1][0].width() + 7 + fm.horizontalAdvance(t) + 18
        self.box = QRectF(x, 8, 36 + fm.horizontalAdvance(self.chip) + 14, 36)  # the mode: tinted, padding 0 14, icon 16 + 6
        self.resize(round(self.box.right()) + 8, 52)

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        for r, k, t in self.keys:
            wash(p, r, 9, .16, .3)
            p.setPen(ink())
            p.setFont(ui_font(12, mono=True))
            p.drawText(r, Qt.AlignCenter, k)
            p.setFont(ui_font(14))
            p.drawText(QRectF(r.right() + 7, 0, self.width(), self.height()), Qt.AlignVCenter | Qt.AlignLeft, t)
        fill, edge, lit, _ = glass("tint")
        chip = QPainterPath()
        chip.addRoundedRect(self.box, 18, 18)
        p.fillPath(chip, fill)
        rim(p, self.box.adjusted(1, 1, -1, -1), 17, lit)
        p.setPen(QPen(edge, 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(self.box.adjusted(.5, .5, -.5, -.5), 17.5, 17.5)
        glyph_svg("lang", "#ffffffff", 2).render(p, QRectF(self.box.left() + 14, 18, 16, 16))  # (tint glass: white)
        p.setPen(QColor(Qt.white))
        p.drawText(self.box.adjusted(36, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, self.chip)
        p.end()


class Toast(GlassPanel):
    """G7: what an action did, in a capsule under the toolbar for a moment. tone: "ok" (a check), "save", or "bad"
    (red glass, an x)."""
    LOOK = {"ok": ("check", (52, 199, 120, .85)), "save": ("save", (76, 194, 255, .85)), "bad": ("x", (255, 70, 70, .85))}

    def __init__(self, parent):
        super().__init__(parent, "toast")
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.text, self.tone = "", "ok"
        self.timer = QTimer(self, singleShot=True, interval=2500, timeout=self.hide)
        self.hide()

    def say(self, text, tone="ok"):
        self.kind, self.text, self.tone = "alarm" if tone == "bad" else "toast", text, tone
        self.resize(48 + QFontMetrics(ui_font(14, QFont.Medium)).horizontalAdvance(text) + 18, 44)  # CSS: padding 0 18 0 8, a 30 disc, gap 10
        o, bar = self.parentWidget(), self.parentWidget().bar
        r = bar.geometry() if bar.isVisible() else QRect(o.width() // 2, o.height() // 2, 0, 0)
        y = r.bottom() + 11 if r.bottom() + 11 + self.height() <= o.height() else r.top() - 10 - self.height()
        self.move(min(max(r.center().x() - self.width() // 2, 0), o.width() - self.width()), y)
        self.show()
        self.raise_()
        self.update()
        self.timer.start()

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        glyph, fill = self.LOOK[self.tone]
        p.setPen(Qt.NoPen)
        p.setBrush(rgba(*fill))
        p.drawEllipse(QRectF(8, 7, 30, 30))
        glyph_svg(glyph, "#ffffffff", 2).render(p, QRectF(15.5, 14.5, 15, 15))
        p.setPen(ink())
        p.setFont(ui_font(14, QFont.Medium))
        p.drawText(QRectF(48, 0, self.width() - 48, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.text)
        p.end()


class GlassPopup(GlassPanel):
    """A glass menu or popover inside the overlay (so the glass shows the capture under it): opened by popup(), shut by
    Esc or a click anywhere else, which does nothing more, as with any menu."""

    def __init__(self, parent, radius):
        super().__init__(parent, "menu", radius)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.ArrowCursor)
        self.hide()

    def popup(self, at):  # top-left at this point of the overlay, kept on it
        o = self.parentWidget()
        self.move(min(max(at.x(), 0), o.width() - self.width()), min(max(at.y(), 0), o.height() - self.height()))
        self.show()
        self.raise_()
        self.setFocus()
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, _, e):
        if e.type() in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick) and \
                not self.rect().contains(self.mapFromGlobal(e.globalPosition().toPoint())):
            self.hide()
            return True
        return False

    def hideEvent(self, e):
        QApplication.instance().removeEventFilter(self)
        self.parentWidget().setFocus()
        super().hideEvent(e)

    def mousePressEvent(self, e):  # all of it: nothing falls through to the screen behind
        pass

    def mouseMoveEvent(self, e):
        pass

    def mouseReleaseEvent(self, e):
        pass

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            return self.hide()
        e.ignore()  # Ctrl+C and co.: the overlay's


class GlassMenu(GlassPopup):
    """A glass menu of rows (glyph, text, keys, checked, fn), None: a separator; head: a title over them. checked: True
    (a check), or a glyph's name at the row's end (a submenu's chevron; keys then its choice). The row under the mouse
    or picked with the arrow keys is lit; a click, Enter or Space runs it. One use."""

    def __init__(self, parent, rows, width, head=""):
        super().__init__(parent, 24)
        self.rows, self.head, self.boxes = rows, head, []
        self.setMouseTracking(True)
        fm, km = QFontMetrics(ui_font(14)), QFontMetrics(ui_font(12, mono=True))
        width = max([width] + [64 + (28 if r[0] else 0) + fm.horizontalAdvance(r[1]) + km.horizontalAdvance(r[2])
                               for r in rows if r])
        y, h = (38 if head else 8), (38 if head else 40)
        for r in rows:  # CSS: rows 2 apart, a separator 1px with margin 4 10
            self.boxes.append(QRectF(18, y + 4, width - 36, 1) if r is None else QRectF(8, y, width - 16, h))
            y += 11 if r is None else h + 2
        self.resize(width, y + 6)
        self.light(next((i for i, r in enumerate(rows) if r and r[3] is True), 0))

    def light(self, i):  # the row lit, its name a screen reader's
        self.at = i
        self.setAccessibleName(self.rows[i][1])
        self.update()

    def row_at(self, pt):
        return next((i for i, (r, b) in enumerate(zip(self.rows, self.boxes)) if r and b.contains(pt)), None)

    def pick(self, i):
        self.hide()
        self.rows[i][4]()

    def hideEvent(self, e):  # one use; but a new one is hidden, and told so, before a window of its own (Floater) shows
        super().hideEvent(e)
        if self.parentWidget().isVisible():  # (that window, gone, takes it along)
            self.deleteLater()

    def mouseMoveEvent(self, e):
        i = self.row_at(e.position())
        if i is not None and i != self.at:
            self.light(i)

    born = 0.0  # when, if it opened over the row clicked to open it (the tray's language menu)

    def mouseReleaseEvent(self, e):  # (not the rest of that click's double click)
        i = self.row_at(e.position())
        if i is not None and e.button() == Qt.LeftButton and time.monotonic() - self.born > QApplication.doubleClickInterval() / 1000:
            self.pick(i)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Up, Qt.Key_Down):
            n, step = len(self.rows), -1 if e.key() == Qt.Key_Up else 1
            return self.light(next(j for j in ((self.at + step * k) % n for k in range(1, n + 1)) if self.rows[j]))
        if e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            return self.pick(self.at)
        super().keyPressEvent(e)

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        if self.head:
            p.setPen(ink(.55))
            p.setFont(ui_font(12))
            p.drawText(QRectF(20, 8, self.width() - 40, 30), Qt.AlignVCenter | Qt.AlignLeft, self.head)
        for i, (r, b) in enumerate(zip(self.rows, self.boxes)):
            if r is None:
                p.fillRect(b, ink(.12))
                continue
            glyph, text, keys, checked, _ = r
            if i == self.at:
                wash(p, b, 16, .18, .35)
            x, c = b.left() + 12, ink().name(QColor.HexArgb)
            if glyph:
                glyph_svg(glyph, c, 1.75).render(p, QRectF(x, b.center().y() - 9, 18, 18))
                x += 28
            p.setPen(ink())
            p.setFont(ui_font(14))
            p.drawText(QRectF(x, b.top(), b.right() - x, b.height()), Qt.AlignVCenter | Qt.AlignLeft, text)
            if keys:
                p.setPen(ink(.55))
                p.setFont(ui_font(12, mono=keys.isascii()))
                p.drawText(b.adjusted(0, 0, -38 if checked else -12, 0), Qt.AlignVCenter | Qt.AlignRight, keys)
            if checked:
                glyph_svg("check" if checked is True else checked, c, 2).render(p, QRectF(b.right() - 28, b.center().y() - 8, 16, 16))
        p.end()


class InkPopover(GlassPopup):
    """The ink's colour and size, from the toolbar's dot or a right-click while drawing. Sizes are each drawing tool's
    own: shown for the current one, dimmed under select. Stays open for another pick until a click elsewhere."""

    def __init__(self, o):
        super().__init__(o, 28)
        self.resize(300, 216)  # CSS padding 16, gap 16: label, 5 dots, label, the sizes' grid

    def setVisible(self, on):  # the toolbar's dot lit while it's open, however it was opened (G7)
        super().setVisible(on)
        self.parentWidget().ink_btn.setChecked(on)

    @staticmethod
    def dot(i):
        return QRectF(16 + i * 57, 50, 40, 40)

    @staticmethod
    def cell(j):
        return QRectF(20 + j * 66, 144, 62, 52)

    def mousePressEvent(self, e):
        o, pt = self.parentWidget(), e.position()
        if e.button() != Qt.LeftButton:
            return
        for i, c in enumerate(o.COLORS):
            if self.dot(i).contains(pt):
                o.set_ink(c)
        for j, (s, *_) in enumerate(o.SIZES):
            if self.cell(j).contains(pt) and o.tool != "select":
                o.sizes[o.tool] = s
        self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        o, p = self.parentWidget(), QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        p.setFont(ui_font(12))
        p.setPen(ink(.6))
        p.drawText(QRectF(16, 16, 268, 18), Qt.AlignVCenter | Qt.AlignLeft, "สี")
        p.drawText(QRectF(16, 106, 268, 18), Qt.AlignVCenter | Qt.AlignLeft, "ขนาด")
        for i, c in enumerate(o.COLORS):
            b = self.dot(i)
            if c == o.color:  # CSS: inset 0 0 0 2px rgba(255,255,255,.9)
                p.setPen(QPen(themed((255, 255, 255, .9), (28, 31, 38, .85)), 2))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(b.adjusted(1, 1, -1, -1))
            ink_dot(p, b.center(), 28, c, False)
        grid = QPainterPath()
        grid.addRoundedRect(QRectF(16, 140, 268, 60), 20, 20)
        p.fillPath(grid, themed((0, 0, 0, .25), (28, 31, 38, .07)))  # (G8's segmented track)
        if o.tool == "select":
            p.setOpacity(.4)
        size = o.sizes.get(o.tool, 1)
        p.setFont(ui_font(12))
        for j, (s, name, d) in enumerate(o.SIZES):
            b = self.cell(j)
            if s == size and o.tool != "select":
                wash(p, b, 16, .2, .4)
            top = b.top() + (b.height() - d - 20) / 2  # the dot, 4 apart, a 16px line of text
            p.setPen(Qt.NoPen)
            p.setBrush(ink())
            p.drawEllipse(QRectF(b.center().x() - d / 2, top, d, d))
            p.setPen(ink())
            p.drawText(QRectF(b.left(), top + d + 4, b.width(), 16), Qt.AlignCenter, name)
        p.end()
