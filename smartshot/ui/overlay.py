"""The capture: select, OCR, translate, mark up; QR cards and slip verdicts."""
import os
from datetime import datetime

from PySide6.QtCore import QEvent, QLineF, QPoint, QPointF, QRect, QRectF, QSizeF, QStandardPaths, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QCursor, QFont, QFontMetrics, QGuiApplication, QImage, QKeySequence,
                           QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QRegion, QTransform)
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFileDialog, QGridLayout, QHBoxLayout, QLineEdit,
                               QVBoxLayout, QWidget)
from qfluentwidgets import isDarkTheme

from smartshot.config import CTRL, LANGS, THAI, VERSION
from smartshot.ocr.engine import ocr
from smartshot.ocr.translate import translate
from smartshot.qr.promptpay import TH_MONTHS, qr_info
from smartshot.qr.scan import panels, scan_qr
from smartshot.slip.compare import compare
from smartshot.slip.thunder import NO_KEY, THUNDER_ERRORS, slip_fields, store_key, verify_slip
from smartshot.system import mac
from smartshot.task import Task
from smartshot.ui.assets import font, glyph_svg, ui_font
from smartshot.ui.card import KEYLESS, MARKS, MARKS_LIGHT, MONEY, TONES, TONES_LIGHT, lab, tone_ink
from smartshot.ui.glass import (DIM, chrome, clear, field_qss, frame_shadow, frost, glass, ink, paint_glass,
                                qimage, rgba, rim, shadow, themed)
from smartshot.ui.widgets import (Box, Disc, GlassButton, GlassMenu, GlassPanel, GlassPopup, GlassTip, HintBar,
                                  InkPopover, Toast)



def verdict(payload, res, table=()):  # a slip's state, compare()'s rows -> tone, glyph (None: still asking), head, sub
    if res is None:
        return "info", None, "กำลังตรวจกับธนาคาร…", ""
    if res[1]:  # messages read "what: what to do"; red only for a slip the bank doesn't have, not "couldn't check"
        bad, (head, _, sub) = res[1] == THUNDER_ERRORS["SLIP_NOT_FOUND"], res[1].partition(": ")
        return "bad" if bad else "none", "x" if bad else "question", head, sub
    if res[0].get("isDuplicate"):  # amber either way: a slip shown again may be a payment claimed twice
        if first := Overlay.seen.get(payload):  # the app lives in the tray for days: the day too, unless it's today
            day = "" if first.date() == datetime.now().date() else f"{first.day} {TH_MONTHS[first.month - 1]} "
            return "warn", "history", f"ตรวจสลิปนี้ไปแล้วเมื่อ {day}{first:%H:%M} น.", "ธนาคารยืนยันรายการ ถ้ารับเงินไปแล้ว อย่ารับซ้ำ"
        return "warn", "history", "สลิปนี้เคยถูกตรวจแล้ว", "ถ้าไม่ได้ตรวจเอง อาจเป็นสลิปที่ใช้ซ้ำ"
    if bad := [r[0] for r in table if r[4] == "✗"]:  # an edited image (or a misread): the table shows both sides
        return "warn", "search", "ข้อมูลในภาพไม่ตรงกับธนาคาร", f"ไม่ตรง: {', '.join(bad)}"
    n, unsure = sum(r[4] == "✓" for r in table), sum(r[4] == "?" for r in table)
    return "ok", "check", "ธนาคารยืนยันรายการ", \
        f"ตรง {n} · เทียบไม่ได้ {unsure}" if unsure else "ข้อมูลในภาพตรงกับธนาคาร" if table else "เทียบข้อมูลกับสลิป"


class Layer:
    """What is being worked on, all in screenshot px: the screenshot, the selected crop of it, OCR lines
    (translations painted over them) and drawings. Changing the crop (resize) moves nothing else.
    The overlay paints it in place on screen; render() flattens the crop for copy/save."""

    def __init__(self, img, crop=None, unit=1.0):
        self.img = img.convertToFormat(QImage.Format_RGB32)  # native format: no conversion on every repaint
        self.crop = crop if crop is not None else self.img.rect()  # replaced, never mutated in place
        self.unit = unit  # image px per screen px, so strokes look the same at any DPI
        self.items, self.boxes, self.tr = [], [], {}  # items: [(rect, text)]; tr: text -> translation
        self.shapes, self.sel, self.show_tr = [], set(), True  # shapes: [kind, color, points, text, size]
        self.qrs, self.marks = [], {}  # qrs: [(QPolygonF, payload)] found in the crop; marks: payload -> verdict, glyph

    def set_items(self, items):  # a new OCR result: translations already known come back by text
        self.items, self.sel = items, set()
        self.layout()

    def add_tr(self, lines, trs):
        self.tr.update(zip(lines, trs))
        self.layout()

    def layout(self):  # translation boxes, laid out once here instead of on every repaint
        # lines left as they are (Thai, pinyin) keep their original pixels
        self.boxes = [self._box(r, self.tr[t]) if self.tr.get(t, t) != t else None for r, t in self.items]

    def rects(self):  # hit areas: the drawn (possibly grown) translation boxes, else the original lines
        return [b[0] if self.show_tr and b else r for (r, _), b in zip(self.items, self.boxes)]

    def hit(self, pt):
        return next((i for i, r in enumerate(self.rects()) if r.contains(pt)), None)

    def texts(self):  # what the user sees: translation or original; selected lines, or all if none
        rows = [self.items[i] for i in sorted(self.sel)] or self.items
        return [self.tr.get(t, t) if self.show_tr else t for _, t in rows]

    def paint(self, p, live=False):
        p.setClipRect(self.crop)
        p.drawImage(self.crop.topLeft(), self.img, self.crop)
        if self.show_tr:
            for (r, size, bg), (_, t) in [(b, it) for b, it in zip(self.boxes, self.items) if b]:
                p.fillRect(r, bg)  # opaque: translucent fill lets the original text show through
                p.setFont(font(size))
                p.setPen(QColor("#111") if bg.lightness() > 128 else QColor("#fff"))
                p.drawText(r, Qt.AlignTop | Qt.TextWrapAnywhere, self.tr[t])
        if live:  # lens-style: outline every line found, highlight the selected ones
            p.setPen(QPen(QColor(76, 194, 255, 160), self.unit))
            for i, r in enumerate(self.rects()):
                if i in self.sel:
                    p.fillRect(r, QColor(66, 133, 244, 90))
                else:
                    p.drawRect(r)
            for n, (poly, text) in enumerate(self.qrs, 1):  # boxed and badged like their verdicts on the QR card
                tone, glyph = self.marks.get(text, ("info", None))
                u, c = self.unit, tone_ink(tone)
                box = poly.boundingRect().adjusted(-6 * u, -6 * u, 6 * u, 6 * u)
                b = QRectF(box.x() - 12 * u, box.y() - 12 * u, 26 * u, 26 * u)  # G3: 26px, 12 out from its corner
                p.save()
                p.setClipping(False)  # a code at the crop's edge: its box and badge stick out of it
                p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
                p.setPen(QPen(c, 2.5 * u))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(box, 14 * u, 14 * u)
                p.drawImage(QRectF(b.x() - 10 * u, b.y() - 6 * u, 46 * u, 46 * u), shadow(26, 26, 13, 10, (0, 0, 0, .3)))
                c.setAlphaF(.85)
                p.setPen(QPen(rgba(*TONES[tone][1][:3], .7), u))
                p.setBrush(c)
                p.drawEllipse(b)
                rim(p, b.adjusted(u, u, -u, -u), 12 * u, rgba(255, 255, 255, .5))
                if len(self.qrs) > 1:  # several: numbered, as on the card
                    p.setPen(QColor(Qt.white))
                    p.setFont(ui_font(round(13 * u), QFont.Bold))
                    p.drawText(b, Qt.AlignCenter, str(n))
                elif glyph:
                    g = QRectF(0, 0, 15 * u, 15 * u)
                    g.moveCenter(b.center())
                    glyph_svg(glyph, "#ffffffff", 2).render(p, g)
                p.restore()
        p.setRenderHint(QPainter.Antialiasing)
        for s in self.shapes:
            self._shape(p, *s)

    def render(self):  # the crop flattened for copy/save: no selection marks
        out = QImage(self.crop.size(), QImage.Format_RGB32)
        p = QPainter(out)
        p.translate(-self.crop.x(), -self.crop.y())
        self.paint(p)
        p.end()
        return out

    def _shape(self, p, kind, color, pts, text, size):  # size: x the tool's usual width/font/blocks
        u, c = self.unit * size, QColor(color)
        if kind == "mosaic":
            r = QRectF(pts[0], pts[-1]).normalized().toRect().intersected(self.img.rect())
            if not r.isEmpty():
                b = max(int(10 * u), 4)  # block size
                small = self.img.copy(r).scaled(max(r.width() // b, 1), max(r.height() // b, 1),
                                                Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                p.drawImage(r, small.scaled(r.size()))  # fast (nearest) upscale = blocks
            return
        if kind == "marker":
            c.setAlpha(110)
        p.setPen(QPen(c, (18 if kind == "marker" else 3) * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        if kind in ("pen", "marker"):
            p.drawPolyline(QPolygonF(pts))
        elif kind == "rect":
            p.drawRect(QRectF(pts[0], pts[-1]).normalized())
        elif kind == "arrow":
            tip, head = pts[-1], 22 * u
            shaft = QLineF(pts[0], tip)
            shaft.setLength(max(shaft.length() - head * 0.7, 0))  # stop inside the head: no round cap poking out
            p.drawLine(shaft)
            back = QLineF(tip, pts[0]).angle()
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawPolygon(QPolygonF([tip] + [tip + QLineF.fromPolar(head, back + a).p2() for a in (25, -25)]))
        elif kind == "text":
            p.setFont(font(int(20 * u), True))
            p.drawText(QRectF(pts[0], QSizeF(1e5, 1e5)), Qt.AlignLeft | Qt.AlignTop, text)

    def _box(self, r, tr):  # where and at what size a translation is drawn over its line
        r = r.adjusted(-2, -1, 2, 1)  # cover antialiased edges of the original glyphs
        size, h = self._fit(r, tr)
        r.setHeight(max(r.height(), h))  # too long for one line: grow downward
        return r, size, self._bg(r)

    def _fit(self, r, tr):
        """(font px, text height). Prefer one line at >=65% of the original height; else wrap and grow down
        (never past the next line below, or it would hide it); shrink further only if that room runs out."""
        below = [o.top() for o, _ in self.items if o.top() > r.bottom() - 2 and o.left() < r.right() and o.right() > r.left()]
        room = min(below + [self.crop.bottom() + 1]) - r.top() - 2
        hmeasure = lambda sz: QFontMetrics(font(sz)).boundingRect(0, 0, r.width(), 10**5, Qt.TextWrapAnywhere, tr).height()
        top, floor = max(r.height(), 8), max(int(r.height() * 0.65), 10)
        for sz in range(top, floor - 1, -1):
            if hmeasure(sz) <= r.height():
                return sz, hmeasure(sz)
        for sz in range(floor, 6, -1):
            if hmeasure(sz) <= max(room, r.height()):
                return sz, hmeasure(sz)
        return 7, hmeasure(7)

    def _bg(self, r):  # box background = average of the 4 corner pixels of the original
        img, w, h = self.img, self.img.width() - 1, self.img.height() - 1
        cs = [img.pixelColor(min(max(x, 0), w), min(max(y, 0), h)) for x in (r.left(), r.right()) for y in (r.top(), r.bottom())]
        return QColor(*(sum(getattr(c, k)() for c in cs) // 4 for k in ("red", "green", "blue")))


class Overlay(QWidget):
    """One per screen, ShareX/Snipaste style. Drag out a region, or click the panel the pointer previews (a slip
    around its QR code; the wheel steps out to the panel around it and back), then work on it in place: OCR starts
    at once in the background, lines can be selected lens-style, drawn on, and translated over the image; drag the
    border to resize (Shift keeps its shape), right-click for a menu (a drawing tool's size while drawing). QR codes
    in it are explained on a card beside it, slips checked with Thunder and compared with what the image says; the
    card saves as a receipt. No second window."""
    started = Signal()  # a selection began on this screen: the others drop theirs
    closed = Signal()
    ZOOM, SPAN = 8, 17  # magnifier shows SPAN x SPAN screenshot pixels, each ZOOM x ZOOM: a 136 circle
    MODES = {"auto": "อัตโนมัติ", "ch": "จีน + อังกฤษ", "th": "ไทย"}  # the hint bar's names for the OCR modes
    GRIP = 6  # px either side of the selection border that grab it for resizing
    TOOLS = [("select", f"เลือกข้อความ: ลากคลุมหรือคลิกบรรทัด · {CTRL}+คลิก เพิ่ม · {CTRL}+A ทั้งหมด"), ("pen", "ปากกา"),
             ("marker", "ปากกาเน้นข้อความ"), ("rect", "สี่เหลี่ยม"), ("arrow", "ลูกศร"),
             ("text", "พิมพ์ข้อความ (Enter เพื่อวาง)"), ("mosaic", "เบลอ (โมเสก)")]  # name: its glyph too
    COLORS = ["#FF4D4F", "#FFB547", "#3DD68C", "#4CC2FF", "#FFFFFF"]  # red, yellow, green, blue, white
    lang = "th"  # translation target: shared by every screen and kept for the next capture (Thai on restart)
    SIZES = [(0.6, "เล็ก", 4), (1, "กลาง", 7), (1.6, "ใหญ่", 11), (2.5, "ใหญ่มาก", 16)]  # x each tool's usual size; its dot
    sizes = {}  # tool -> size; shared and kept like lang (mutated, never reassigned)
    seen = {}  # slip payload -> when this run first checked it (Thunder says "duplicate" after that)
    folder = ""  # where the last image or receipt went: the next one is offered there

    def __init__(self, shot_bgr, geometry, mode):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        h, w, _ = shot_bgr.shape
        self.shot, self.mode = shot_bgr, mode
        self.img = qimage(shot_bgr).convertToFormat(QImage.Format_RGB32)
        self.pix = QPixmap.fromImage(self.img)
        self.setGeometry(geometry)
        self.k = w / geometry.width()  # screenshot px per widget px (the screen's DPI scale)
        # what glass shows through it: the capture frosted; none when Reduce transparency is on
        self.clear = clear()
        self.frost = frost(shot_bgr, geometry.size(), 22)
        # a/b: selection corners. Compare with None: QPoint(0, 0) is falsy
        self.a = self.b = self.layer = self.edit = self.queued = self.band = self.grip = self.card = None
        self.drag = None  # "region" | "resize" | "band" | "shape" while the left button is down
        self.slips = {}  # QR payload -> Thunder's (data, error, when); None while asking. Per selection
        # what a click can pick (widget px, smallest first), slips around their codes; the one previewed, the
        # cursor's own (the wheel moves off it), the one a press was on
        self.picks, self.qr_picks, self.hover, self.base_pick, self.pick = [], [], None, None, None
        k = self.k
        finder = Task(lambda: panels(shot_bgr, k))  # no self in it: the overlay may be gone when it's done
        finder.done.connect(self.set_picks)  # a method: disconnected if the overlay goes first
        finder.start()
        self.gen, self.ready, self.base, self.asked = 0, False, set(), set()  # asked: texts out for translation
        self.tool, self.color, self.status = "select", self.COLORS[0], ""
        cur = self.mapFromGlobal(QCursor.pos())
        self.cur = cur if self.rect().contains(cur) else None
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.ClickFocus)  # a click on the image takes keys (Ctrl+C) back from the QR card's text
        self.bar = self._toolbar()
        self.inks, self.tipbox = InkPopover(self), GlassTip(self)
        self.hints = HintBar(self, self.MODES.get(mode, mode))  # shown while nothing is selected
        self.toast = Toast(self)
        self.hints.move((self.width() - self.hints.width()) // 2, 20)

    def _toolbar(self):  # glass capsules 8 apart: tools | ink, undo | translate (tinted) | view, copy, save | close
        bar = QWidget(self)
        bar.setCursor(Qt.ArrowCursor)
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        def group(kind, *buttons):
            g = GlassPanel(bar, kind)
            lay = QHBoxLayout(g)
            lay.setContentsMargins(6, 6, 6, 6)
            lay.setSpacing(2 if kind == "bar" else 0)
            for b in buttons:
                lay.addWidget(b) if isinstance(b, QWidget) else lay.addSpacing(b)
            row.addWidget(g)

        self.tools = QButtonGroup(bar)  # exclusive: one tool
        for i, (name, tip) in enumerate(self.TOOLS):
            b = GlassButton(name, tip=tip if name == "select" else f"{tip} · คลิกขวา: สีและขนาด")
            b.setCheckable(True)
            self.tools.addButton(b, i)
        self.tools.button(0).setChecked(True)
        self.tools.idClicked.connect(lambda i: self.set_tool(self.TOOLS[i][0]))
        sep = QWidget()  # CSS: 1 x 22, margin 0 4
        sep.setFixedSize(1, 22)
        sep.setAttribute(Qt.WA_StyledBackground)
        sep.setStyleSheet(f"background:{ink(.16).name(QColor.HexArgb)}")
        group("bar", self.tools.button(0), 4, sep, 4, *self.tools.buttons()[1:])
        self.ink_btn = GlassButton(tip="สีและขนาดเส้น")
        self.ink_btn.swatch = self.color
        self.ink_btn.setCheckable(True)  # lit while its popover is open (InkPopover)
        self.ink_btn.clicked.connect(self.ink_menu)
        undo = GlassButton("undo", tip="เลิกทำ", keys=f"{CTRL}+Z")
        undo.clicked.connect(self.undo)
        group("bar", self.ink_btn, undo)
        self.tr_btn = GlassButton("translate", f"แปล · {LANGS[self.lang][0]}", tip="แปลบรรทัดที่เลือก หรือทั้งหมด แล้ววางทับในภาพ")
        self.tr_btn.clicked.connect(lambda: self.after_ocr(self.translate_lines))
        langs = GlassButton("chevron", tip="เลือกภาษา")
        langs.icon_px = 16
        langs.setFixedWidth(32)
        langs.clicked.connect(self.lang_menu)
        group("tint", self.tr_btn, langs)
        self.orig_btn = GlassButton("eye", tip="สลับดูต้นฉบับ / คำแปล")
        self.orig_btn.setCheckable(True)
        self.orig_btn.toggled.connect(self.show_original)
        buttons = [self.orig_btn]
        for glyph, tip, keys, slot in (("copy", "คัดลอกข้อความ: ที่เลือก หรือทั้งหมด", "", lambda: self.after_ocr(self.copy_text)),
                                       ("image", "คัดลอกรูปแล้วปิด", f"{CTRL}+C", self.copy_image),
                                       ("save", "บันทึกรูป", f"{CTRL}+S", self.save),
                                       ("close", "ปิด", "Esc", lambda: self.closed.emit())):
            b = GlassButton(glyph, tip=tip, keys=keys)
            b.clicked.connect(slot)
            buttons.append(b)
        group("bar", *buttons[:-1])
        group("bar", buttons[-1])  # a circle of its own
        bar.hide()
        return bar

    def drop(self, g, w):  # where w opens under the toolbar capsule g: 10 below, else 10 above it
        r = QRect(g.mapTo(self, QPoint()), g.size())
        return QPoint(r.left(), r.bottom() + 11 if r.bottom() + 11 + w.height() <= self.height() else r.top() - 10 - w.height())

    def sel_rect(self):  # clamped: a drag can run past the screen edge
        # span, not normalized(): that drops a px per flipped axis, so grabbing a top/left grip would shrink it
        return QRect.span(self.a, self.b).intersected(self.rect())

    def _src(self, r):  # widget rect -> screenshot pixel rect
        k = self.k
        return QRect(int(r.x() * k), int(r.y() * k), int(r.width() * k), int(r.height() * k))

    def to_layer(self, pos):  # widget point -> screenshot px, the layer's coordinates
        return QPointF(pos) * self.k

    def grip_at(self, pt):  # which edges a press here would drag: (gx, gy) in -1/0/1, or None
        if not self.layer:
            return None
        r, m = self.sel_rect(), self.GRIP
        if not r.adjusted(-m, -m, m, m).contains(pt):
            return None
        gx = -1 if abs(pt.x() - r.left()) <= m else 1 if abs(pt.x() - r.right()) <= m else 0
        gy = -1 if abs(pt.y() - r.top()) <= m else 1 if abs(pt.y() - r.bottom()) <= m else 0
        return (gx, gy) if gx or gy else None

    @staticmethod
    def grip_cursor(gx, gy):
        if not gx:
            return Qt.SizeVerCursor
        if not gy:
            return Qt.SizeHorCursor
        return Qt.SizeFDiagCursor if gx == gy else Qt.SizeBDiagCursor

    def set_status(self, text):
        self.status = text
        self.update()

    def backdrop(self, p, r, panel=None):
        """Behind panel's glass at r: the capture frosted, dimmed like the screen around it; under a menu or tooltip
        also the glass it opens over (its fill, unblurred: the frost is of the capture only)."""
        q = self.frost.width() / self.width()
        p.drawPixmap(QRectF(r), self.frost, QRectF(r.x() * q, r.y() * q, r.width() * q, r.height() * q))
        lit = self.sel_rect() if self.a is not None else self.hover
        p.save()
        if lit is not None:
            p.setClipRegion(QRegion(r).subtracted(QRegion(lit)), Qt.IntersectClip)
        p.fillRect(r, DIM)
        p.restore()
        if isinstance(panel, (GlassPopup, GlassTip)):
            for w in self.findChildren(GlassPanel):
                if w.isVisible() and not isinstance(w, (GlassPopup, GlassTip)):
                    shape = QPainterPath()
                    shape.addRoundedRect(QRectF(QRect(w.mapTo(self, QPoint()), w.size())), w.corner(), w.corner())
                    p.fillPath(shape, glass(w.kind)[0])

    def shadows(self, p):  # under the glass on this screen: a panel can't paint outside itself
        for w in self.findChildren(GlassPanel):
            if w.isVisible():
                dy, blur, color = glass(w.kind)[3]
                g = QRect(w.mapTo(self, QPoint()), w.size())
                p.drawImage(g.topLeft() + QPoint(-blur, dy - blur), shadow(g.width(), g.height(), round(w.corner()), blur, color))

    def reset(self):  # drop the selection and everything done on it
        self.end_edit(False)
        self.gen += 1  # OCR/translation still running for it is ignored when it lands
        self.a = self.b = self.layer = self.queued = self.band = self.drag = self.grip = None
        self.status, self.asked, self.slips = "", set(), {}
        self.bar.hide()
        self.hints.show()
        self.show_qrs()  # no layer: removes the card
        self.setCursor(Qt.CrossCursor)
        self.update()

    def run(self, fn, on_done):
        g = self.gen
        t = Task(fn)
        t.done.connect(lambda res: g == self.gen and on_done(res))
        t.failed.connect(lambda m: g == self.gen and self.fail(m))
        t.start()

    def fail(self, msg):
        self.ready, self.asked = True, set()
        self.set_status(f"ผิดพลาด: {msg[:80]}")
        if self.card:  # a slip held back for the amount check gets its verdict
            self.show_qrs()

    def place_bar(self):  # under the selection from its left, else above it, else inside its bottom edge
        r, bar = self.sel_rect(), self.bar
        QApplication.sendPostedEvents(None, QEvent.LayoutRequest)  # a label just changed: its capsule's new width
        bar.adjustSize()
        y = r.bottom() + 21  # 18 under the selection's frame, which is 2 outside it
        if y + bar.height() > self.height():
            y = r.top() - bar.height() - 20
        if y < 0:
            y = r.bottom() - bar.height() - 8
        bar.move(min(max(r.left() - 2, 0), self.width() - bar.width()), y)
        bar.show()
        if self.card:
            self.place_card()

    def place_card(self):  # beside the selection: right, else left, else inside its top-right corner; off the toolbar
        r, c, bar = self.sel_rect(), self.card, self.bar.geometry()
        c.show()  # first: the labels' styled fonts set their wrapped height
        h = c.heightForWidth(c.width())  # not adjustSize(), which wraps labels at a guessed width
        c.resize(c.width(), h if h > 0 else c.sizeHint().height())
        x = r.right() + 10 if r.right() + 10 + c.width() <= self.width() else r.left() - 10 - c.width()
        if x < 0:
            x = r.right() - c.width() - 10
        x, y = max(x, 0), max(r.top(), 0)
        if QRect(x, y, c.width(), c.height()).intersects(bar):  # taller than the selection: up off the toolbar
            y = bar.top() - 8 - c.height() if bar.top() - 8 - c.height() >= 0 else bar.bottom() + 8
        c.move(x, min(y, max(self.height() - c.height(), 0)))
        c.raise_()
        for w in self.findChildren(GlassPopup):  # a menu open when the card was rebuilt stays over it
            if w.isVisible():
                w.raise_()

    def set_picks(self, found):  # panels() is back: boxes in widget px; the cursor may already be on a slip
        self.picks, self.qr_picks = ([QRect(*(round(v / self.k) for v in b)) for b in boxes] for boxes in found)
        self.hover = self.base_pick = self.pick_at(self.cur) if self.cur is not None and self.a is None else None
        self.update()

    def pick_at(self, pt):  # a slip around its code under the cursor, else the smallest panel there
        r = next((r for r in self.qr_picks if r.contains(pt)), None)
        return r if r is not None else next((r for r in self.picks if r.contains(pt)), None)

    def open_layer(self):  # selection made: tools appear and text is read right away, in the background
        self.hover = self.base_pick = None
        self.layer = Layer(self.img, self._src(self.sel_rect()), self.k)
        self.tr_btn.setText(f"แปล · {LANGS[self.lang][0]}")  # may have been changed on another screen
        self.orig_btn.setChecked(False)
        self.orig_btn.setEnabled(False)
        self.place_bar()
        self.read()

    def read(self):  # OCR the crop; a result for a crop that was resized meanwhile is dropped
        L, c = self.layer, self.layer.crop
        bgr = self.shot[c.y():c.y() + c.height(), c.x():c.x() + c.width()].copy()
        self.ready = False
        self.set_status("กำลังอ่านข้อความ…")
        self.run(lambda: ocr(bgr, self.mode), lambda items: c == L.crop and self.on_ocr(items, c))
        self.run(lambda: scan_qr(bgr), lambda qrs: c == L.crop and self.on_qr(qrs, c))

    def on_qr(self, qrs, c):
        self.layer.qrs = [(QPolygonF([QPointF(float(x) + c.x(), float(y) + c.y()) for x, y in q]), text)
                          for text, q in qrs]
        self.show_qrs()
        self.update()

    def show_qrs(self):
        """The QR card beside the selection, read like a bank receipt: verdict, amount, who, when. Slips are checked with
        Thunder once per selection: the answer is kept, so resizing doesn't ask (or spend quota) again."""
        typed, had = "", False
        if self.card:
            if old := self.card.findChild(QLineEdit):  # the key box: what's typed stays across a rebuild
                typed, had = old.text(), old.hasFocus()
            self.card.hide()
            self.card.deleteLater()
        self.card, L = None, self.layer
        if not L or not L.qrs:
            return
        card = self.card = GlassPanel(self, "card", 30)
        card.setAttribute(Qt.WA_NoMousePropagation)  # a click on it mustn't reach the overlay (new selection)
        card.setCursor(Qt.ArrowCursor)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)
        texts, retry, key, L.marks, wide = [], [], False, {}, False
        for _, p in L.qrs:  # new slips are asked first: a verdict waits for every answer (one may pay the same)
            if (k := qr_info(p)[0]) in ("slip", "truemoney") and p not in self.slips:
                self.check_slip(k, p)
        # to tell an edited slip: every amount OCR read here (0.00: fee lines), and what the bank says each code paid
        found = [(r, v) for r, t in L.items for m in MONEY.findall(t) if (v := round(float(m.replace(",", "")), 2))]
        fields = {p: slip_fields(qr_info(p)[0], s[0]) for _, p in L.qrs if (s := self.slips.get(p)) and s[0]}
        paid = [round(f[2], 2) for _, p in L.qrs for f in fields.get(p, ()) if f[1] == "amount" and isinstance(f[2], (int, float))]
        # ponytail: a line belongs to the code nearest it; the slip's outline (which isn't known) would be exact
        near = lambda r: min(L.qrs, key=lambda q: (q[0].boundingRect().center() - QRectF(r).center()).manhattanLength())[0]
        dense = len(L.qrs) > 1  # ponytail: no scrolling; tighter, 2 checked slips fit 1080p, 3 don't
        for n, (poly, payload) in enumerate(L.qrs, 1):
            if n > 1:  # a hairline between codes
                lay.addWidget(rule := QWidget())
                rule.setFixedHeight(1)
                rule.setStyleSheet(f"background:{ink(.12).name(QColor.HexArgb)}")
            kind, title, rows, warn = qr_info(payload)
            slip, res, amount, table = kind in ("slip", "truemoney"), None, None, []
            if slip and (res := self.slips[payload]) and res[0]:
                f, rows = fields[payload], []
                amount = next((x[2] for x in f if x[1] == "amount"), None)
                a = round(amount, 2) if isinstance(amount, (int, float)) else None
                # edited: printed fewer times than the codes here pay it, and not beside this one (stacked slips put
                # one's amount nearer the next one's code, so "not beside it" alone can't say)
                few = bool(found) and a is not None and [v for _, v in found].count(a) < paid.count(a)
                # OCR's lines are of the crop as it was: a resized one is compared once it's read again
                table = compare(f, [t for r, t in L.items if near(r) is poly], {v for r, v in found if near(r) is poly},
                                few, len(L.qrs) == 1) if self.ready else [(x[0], "…", x[3], x[4], "") for x in f]
            tone, glyph, head, sub = verdict(payload, res, table) if slip else \
                ("info", "qr", title, "QR นี้ใช้จ่ายเงิน ไม่ใช่สลิป" if kind in ("promptpay", "emv", "bill") else "")
            if tone == "ok" and [p for _, p in L.qrs].count(payload) > 1:  # one transfer shown twice: claimed twice?
                tone, glyph, head, sub = "warn", "history", "สลิปเดียวกันซ้ำในภาพนี้", "ธนาคารยืนยันแค่รายการเดียว อย่ารับเงินซ้ำ"
            elif tone == "ok" and (not self.ready or None in [self.slips.get(p, 0) for _, p in L.qrs]):
                # no green before the image could be compared: OCR's, and the other codes' answers (one may pay the same)
                tone, glyph, head, sub = "info", None, "กำลังเทียบข้อมูลในภาพ…", "ธนาคารยืนยันรายการแล้ว"
            if slip and res is None:
                sub = "อ่าน QR สลิปแล้ว · รอคำตอบจาก Thunder"
            keyless = bool(res) and res[1] in KEYLESS
            if keyless:  # the card takes the key itself: no file to edit, no "ตรวจใหม่" to press
                glyph, sub = "key", "ใส่คีย์ครั้งเดียว แล้วตรวจสลิปกับธนาคารได้ทันที" if res[1] == NO_KEY else \
                    "วางคีย์ที่ถูกต้องด้านล่าง แล้วตรวจได้ทันที"
            retry += [payload] * bool(res and res[1] and not keyless)
            L.marks[payload] = tone, glyph
            lay.addLayout(top := QHBoxLayout())
            top.setContentsMargins(14, 6 if dense else 14, 14, 4 if dense else 10)
            top.setSpacing(14)
            # several codes: numbered like their badges on the image, in the same colour
            top.addWidget(Disc(44, *(TONES if isDarkTheme() else TONES_LIGHT)[tone], glyph, (str(n), tone_ink(tone)) if len(L.qrs) > 1 else None))
            top.addLayout(text := QVBoxLayout(), 1)
            text.setSpacing(2)
            text.addWidget(lab(head, 17, weight=QFont.DemiBold))
            if sub:
                text.addWidget(lab(sub, 14, .68, sel=bool(res and res[1])))
            if res and not keyless:  # when the bank answered
                top.addWidget(at := lab(f"{res[2]:%H:%M}", 12, .5, mono=True))
                at.setWordWrap(False)
            if warn:
                lay.addWidget(w := lab(warn.lstrip("⚠ "), 13, color=themed((255, 176, 176), (198, 40, 40))))
                w.setContentsMargins(14, 0, 14, 0)
            num = f"{amount:,.2f}" if isinstance(amount, (int, float)) else str(amount)
            if amount is not None:  # the hero, as big as on the slip
                lay.addLayout(line := QHBoxLayout())
                line.setContentsMargins(14, 0, 14, 6)
                line.setSpacing(8)
                line.addWidget(big := lab(num, 32 if dense else 44, weight=QFont.DemiBold, sel=True), 0, Qt.AlignBottom)
                big.setWordWrap(False)
                line.addWidget(baht := lab("บาท", 17, .68), 0, Qt.AlignBottom)
                baht.setContentsMargins(0, 0, 0, QFontMetrics(big.font()).descent() - QFontMetrics(baht.font()).descent())
                line.addStretch()
            if table:  # the image beside the bank, field by field; a row the image differs on, tinted red
                wide = True
                lay.addWidget(box := Box())
                g = QGridLayout(box)
                g.setContentsMargins(18, 14, 18, 15)  # CSS: the box's padding 6, its rows' 9 12, its head's 8 12 6
                g.setHorizontalSpacing(12)
                g.setVerticalSpacing(8 if dense else 18)
                g.setColumnMinimumWidth(0, 88)
                g.setColumnMinimumWidth(3, 22)
                g.setColumnStretch(1, 1)
                g.setColumnStretch(2, 1)
                g.addWidget(lab("ในภาพสลิป", 12, .5), 0, 1)
                g.addWidget(lab("ธนาคารยืนยัน", 12, .5), 0, 2)
                for i, (k, seen, shown, under, mark) in enumerate(table, 1):
                    mono = k.startswith("บัญชี") or k == "เลขอ้างอิง"  # numbers, as the slip prints them
                    g.addWidget(lab(k, 13, .55), i, 0, Qt.AlignTop)
                    g.addWidget(lab(seen or "–", 14, .78, mono=mono, sel=bool(seen), color=themed((255, 176, 176), (198, 40, 40)) if mark == "✗" else None),
                                i, 1, Qt.AlignTop)
                    g.addLayout(cell := QVBoxLayout(), i, 2, Qt.AlignTop)
                    cell.setSpacing(1)
                    cell.addWidget(lab(shown, 14, weight=QFont.DemiBold if k in ("ยอดเงิน", "ผู้โอน", "ผู้รับ") else QFont.Normal,
                                       mono=mono, sel=True))
                    if under:
                        cell.addWidget(lab(under, 12, .5, sel=True))
                    if mark:
                        g.addWidget(Disc(22, (MARKS if isDarkTheme() else MARKS_LIGHT)[mark][1], None, MARKS[mark][0]),
                                    i, 3, Qt.AlignTop)
                    box.bad += [i] * (mark == "✗")
            elif rows and not keyless and (res or not slip):  # what the code says (a slip's: once the bank answered)
                lay.addWidget(box := Box())
                g = QGridLayout(box)
                g.setContentsMargins(18, 16, 18, 16)  # CSS: the box's padding 6 18, its rows' 10 0
                g.setHorizontalSpacing(12)
                g.setVerticalSpacing(20)
                g.setColumnMinimumWidth(0, 96)
                g.setColumnStretch(1, 1)
                for i, (k, v) in enumerate(rows):
                    if k:
                        g.addWidget(lab(k, 13, .55), i, 0, Qt.AlignTop)
                    mono = not THAI.search(v) and sum(c.isdigit() for c in v) >= 4  # ids, phones, refs
                    g.addWidget(lab(v, 14, mono=mono, sel=bool(k)), i, 1 if k else 0, 1, 1 if k else 2)
            if keyless and not key:  # one box for every slip waiting on it: saved as on the settings page, then asked again
                lay.addWidget(box := Box())
                v = QVBoxLayout(box)
                v.setContentsMargins(14, 14, 14, 14)
                v.setSpacing(10)
                v.addWidget(t := lab("Thunder API key", 12, .6))
                v.addLayout(h := QHBoxLayout())
                v.addWidget(note := lab("เก็บไว้ในเครื่องนี้เท่านั้น · แก้ได้ที่หน้าตั้งค่า", 12, .5))
                for w in (t, note):
                    w.setContentsMargins(4, 0, 0, 0)
                h.setSpacing(8)
                h.addWidget(edit := QLineEdit(), 1)
                h.addWidget(go := GlassButton(text="บันทึกและตรวจ", look="tint"))
                edit.setEchoMode(QLineEdit.Password)
                edit.setPlaceholderText("วางคีย์ที่นี่")
                edit.setFixedHeight(44)
                edit.setFont(ui_font(13, mono=True))
                edit.setStyleSheet(field_qss(22, 15))
                edit.setText(typed)
                if had:
                    edit.setFocus()
                edit.returnPressed.connect(lambda: self.use_key(edit.text()))
                go.clicked.connect(lambda: self.use_key(edit.text()))
            key = key or keyless
            texts.append("\n".join([head] + [sub] * bool(sub) + [f"จำนวนเงิน: {num} บาท"] * (amount is not None)
                                   + [f"{k}: {shown}" + (f" ({u})" if u else "") + (f" | ในภาพ: {seen or '–'} {mark}" if mark else "")
                                      for k, seen, shown, u, mark in table]
                                   + [(f"{k}: " if k else "") + v for k, v in rows]
                                   + [warn] * bool(warn) + [f"QR: {payload}"] * (kind not in ("url", "text"))))
        buttons = []
        if retry:
            buttons.append(again := GlassButton("refresh", "ตรวจใหม่", look="soft"))
            again.clicked.connect(lambda: ([self.slips.pop(p, None) for p in retry], self.show_qrs()))
        if not key or len(L.qrs) > 1:  # a lone no-key slip has nothing to copy
            buttons.append(copy := GlassButton("copy", "คัดลอก", look="plain"))
            info = "\n\n".join(texts).replace("\u200b", "")
            copy.clicked.connect(lambda: (QGuiApplication.clipboard().setText(info), self.toast.say("คัดลอกแล้ว")))
        checked = [s for _, p in L.qrs if (s := self.slips.get(p)) and (s[0] or s[1] == THUNDER_ERRORS["SLIP_NOT_FOUND"])]
        if self.ready and checked and None not in [self.slips.get(p, 0) for _, p in L.qrs]:  # every answer in
            buttons.append(receipt := GlassButton("save", "บันทึกใบตรวจ", look="solid"))
            receipt.clicked.connect(lambda: self.save_receipt(foot))
        if buttons:
            lay.addLayout(foot := QHBoxLayout())
            foot.setContentsMargins(6, 4, 6, 6)
            foot.setSpacing(8)
            foot.addStretch()
            for b in buttons:
                foot.addWidget(b)
        card.setFixedWidth(min(max(540 if wide else 420, card.minimumSizeHint().width()), self.width() - 20))  # wider for a ref that won't wrap
        self.place_card()
        self.update()  # the codes on the image take the verdicts' colours

    def use_key(self, k):  # the no-key card's box: thunder.key, then the slips that waited for it are asked again
        if not (k := k.strip()):
            return
        if not store_key(k):
            return self.toast.say("คีย์ไม่ถูกต้อง: มีได้แค่ตัวอักษรภาษาอังกฤษ ตัวเลข และเครื่องหมาย", "bad")
        for p in [p for p, s in self.slips.items() if s and s[1] in KEYLESS]:
            del self.slips[p]
        self.show_qrs()

    def check_slip(self, kind, payload):  # the answer lands in self.slips and redraws the card
        def ask():  # in the worker: Thunder keeps a check even when reset/close drops its answer here
            res = verify_slip(kind, payload)
            if res[0] and not res[0].get("isDuplicate"):  # our own first check: a "duplicate" later in this run is ours
                Overlay.seen.setdefault(payload, datetime.now())
            return res

        def done(res):
            self.slips[payload] = (*res, datetime.now())  # when: printed on the receipt
            self.show_qrs()
        self.slips[payload] = None
        self.run(ask, done)

    def on_ocr(self, items, c):
        self.layer.set_items([(r.translated(c.topLeft()), t) for r, t in items])
        self.ready = True
        self.set_status(f"อ่านแล้ว {len(items)} บรรทัด · คลิกบรรทัดเพื่อเลือก" if items else "อ่านข้อความไม่ได้ · ลองขยายพื้นที่")
        fn, self.queued = self.queued, None
        if fn:
            fn()
        if self.card:  # the amount check needs the text: redraw once it's read
            self.show_qrs()

    def after_ocr(self, fn):  # an action pressed while OCR is still running waits for it
        if self.ready:
            fn()
        else:
            self.queued = fn

    def translate_lines(self, auto=False):
        """Selected lines, or all. auto: lines were just picked; translate those, unless the original is shown."""
        L = self.layer
        if auto and (not L.sel or self.orig_btn.isChecked()):
            return
        if not auto:
            self.orig_btn.setChecked(False)
        rows = [L.items[i] for i in sorted(L.sel)] or L.items
        if not self.send([t for _, t in rows]) and not auto and not self.asked:
            self.set_status(f"แปลเป็น{LANGS[self.lang][0]}แล้ว") if rows else self.toast.say("ไม่พบข้อความ", "bad")

    def send(self, texts):  # translate these, except what's done or on its way; True if any went
        L, lang = self.layer, self.lang
        todo = list(dict.fromkeys(t for t in texts if t not in L.tr and t not in self.asked))
        if todo:
            self.asked |= set(todo)
            self.set_status("กำลังแปล…")
            self.run(lambda: translate(todo, lang), lambda tr: self.on_translated(todo, tr, lang))
        return bool(todo)

    def on_translated(self, lines, tr, lang):
        if lang != self.lang:  # language changed while this was out: set_lang asked again
            return
        self.asked -= set(lines)
        self.layer.add_tr(lines, tr)
        self.orig_btn.setEnabled(True)
        self.set_status(f"แปลเป็น{LANGS[lang][0]}แล้ว {len(lines)} บรรทัด")

    def lang_menu(self):  # the translate capsule's arrow
        m = GlassMenu(self, [(None, n, "", c == self.lang, lambda c=c: self.set_lang(c)) for c, (n, _) in LANGS.items()],
                      232, "แปลเป็น")
        m.popup(self.drop(self.tr_btn.parentWidget(), m))

    def ink_menu(self):  # the toolbar's dot
        self.inks.popup(self.drop(self.ink_btn.parentWidget(), self.inks))

    def set_ink(self, c):
        self.color = self.ink_btn.swatch = c
        self.ink_btn.update()

    def set_lang(self, code):  # what was translated is redone in the new language; nothing yet: translate now
        if code == self.lang:
            return self.after_ocr(self.translate_lines)
        Overlay.lang = code
        self.tr_btn.setText(f"แปล · {LANGS[code][0]}")
        self.place_bar()  # the button's width changed
        L = self.layer
        redo = [t for _, t in L.items if t in L.tr or t in self.asked]
        L.tr, self.asked = {}, set()
        L.layout()
        self.orig_btn.setChecked(False)
        self.update()
        if not self.send(redo):
            self.after_ocr(self.translate_lines)

    def show_original(self, on):
        if self.layer:
            self.layer.show_tr = not on
            self.update()

    def copy_text(self):
        lines = self.layer.texts()
        if not lines:
            return self.toast.say("ไม่พบข้อความ", "bad")
        QGuiApplication.clipboard().setText("\n".join(lines))
        self.toast.say(f"คัดลอกข้อความแล้ว {len(lines)} บรรทัด")

    def copy_image(self):
        self.end_edit()
        QGuiApplication.clipboard().setImage(self.layer.render())
        self.closed.emit()

    def save(self):
        self.end_edit()
        folder = self.folder or QStandardPaths.writableLocation(QStandardPaths.PicturesLocation)  # not the cwd (System32 at login)
        path = self.ask_path("บันทึกรูป", os.path.join(folder, "snaplens.png"), "PNG (*.png);;JPEG (*.jpg)")
        if path:
            if self.layer.render().save(path):
                Overlay.folder = os.path.dirname(path)
                self.closed.emit()
            else:  # the capture stays: save it elsewhere
                self.toast.say("บันทึกรูปไม่สำเร็จ", "bad")

    def ask_path(self, title, path, types):  # where to save: the dialog over this (above the menu bar)
        with mac.under_dialogs(self):
            return QFileDialog.getSaveFileName(self, title, os.path.normpath(path), types)[0]

    def save_receipt(self, foot):
        """The card (its buttons cut off) beside the slip's own pixels, in screen px, and when it was checked; made
        before the file dialog, whose event loop may rebuild the card when an answer lands."""
        card, L, k = self.card, self.layer, self.k
        card.flat = True  # nothing of the screen behind it goes in the file
        pm = card.grab(QRect(0, 0, card.width(), foot.geometry().top()))
        card.flat = False
        pm.setDevicePixelRatio(1)  # the grab is in device px, as the screenshot is
        slip, (bg, edge) = L.img.copy(L.crop), chrome()
        when = max(s[2] for s in self.slips.values() if s)
        note = f"ตรวจเมื่อ {when.day} {TH_MONTHS[when.month - 1]} {when.year + 543} {when:%H:%M:%S} น. · Thunder API · Snaplens v{VERSION}"
        f, pad = font(round(12 * k)), round(16 * k)
        fh = QFontMetrics(f).height()
        out = QImage(3 * pad + slip.width() + pm.width(), 3 * pad + max(slip.height(), pm.height()) + fh, QImage.Format_RGB32)
        out.fill(QColor(bg))
        p = QPainter(out)
        p.drawImage(pad, pad, slip)
        x = 2 * pad + slip.width()
        p.drawPixmap(x, pad, pm)
        p.setPen(QColor(edge))  # close the card where its buttons were cut off
        p.drawLine(x, pad + pm.height() - 1, x + pm.width() - 1, pad + pm.height() - 1)
        p.setFont(f)
        p.setPen(ink(.7))
        p.drawText(QRect(pad, out.height() - pad - fh, out.width() - 2 * pad, fh), Qt.AlignLeft | Qt.AlignVCenter, note)
        p.end()
        amount = next((f"_{x[2]:.2f}" for _, q in L.qrs if (s := self.slips.get(q)) and s[0]
                       for x in slip_fields(qr_info(q)[0], s[0]) if x[1] == "amount" and isinstance(x[2], (int, float))), "")
        folder = self.folder or QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        path = self.ask_path("บันทึกใบตรวจ", os.path.join(folder, f"slip_{when:%Y%m%d-%H%M%S}{amount}.png"), "PNG (*.png)")
        if path:  # names and accounts in it: only where the user puts it
            Overlay.folder = os.path.dirname(path)
            self.toast.say(*(("บันทึกใบตรวจแล้ว", "save") if out.save(path, "PNG") else ("บันทึกใบตรวจไม่สำเร็จ", "bad")))

    def undo(self):
        if self.layer and self.layer.shapes:
            self.layer.shapes.pop()
            self.update()

    def set_tool(self, name):
        self.end_edit()
        self.tool = name
        self.tools.button([t[0] for t in self.TOOLS].index(name)).setChecked(True)
        self.update()

    def context_menu(self, pos):  # right-click on a selection: what can be done with it, at the mouse
        L = self.layer
        if self.tool != "select":  # drawing: the ink's colour and how big this tool draws
            return self.inks.popup(pos.toPoint())
        i = L.hit(self.to_layer(pos).toPoint())
        if i is not None and i not in L.sel:  # right-click on a line selects it, like text anywhere else
            L.sel = {i}
            self.translate_lines(auto=True)
            self.update()
        what = "ที่เลือก" if L.sel else "ทั้งหมด"
        GlassMenu(self, [("translate", f"แปล{what}เป็น{LANGS[self.lang][0]}", "", False, lambda: self.after_ocr(self.translate_lines)),
                         ("copy", f"คัดลอกข้อความ{what}", "", False, lambda: self.after_ocr(self.copy_text)),
                         ("image", "คัดลอกรูปแล้วปิด", f"{CTRL}+C", False, self.copy_image),
                         ("save", "บันทึกรูป", f"{CTRL}+S", False, self.save), None,
                         ("capture", "เลือกพื้นที่ใหม่", "", False, self.reset),
                         ("close", "ปิด", "Esc", False, lambda: self.closed.emit())], 290).popup(pos.toPoint())

    def start_edit(self, pos):  # text tool: type in place, Enter (or clicking elsewhere) puts it on the image
        e = self.edit = QLineEdit(self)
        e.ink, e.text_size = self.color, self.sizes.get("text", 1)
        e.setFont(font(round(20 * e.text_size), True))
        e.setStyleSheet(f"background:transparent;color:{self.color};border:1px dashed {self.color};padding:0")
        e.resize(round(280 * e.text_size), QFontMetrics(e.font()).height() + 4)
        e.move(pos.toPoint() - QPoint(3, e.height() // 2))
        e.editingFinished.connect(self.end_edit)
        e.show()
        e.setFocus()

    def end_edit(self, keep=True):
        e, self.edit = self.edit, None
        if not e:
            return
        if keep and e.text().strip() and self.layer:
            self.layer.shapes.append(["text", e.ink, [self.to_layer(e.pos() + QPoint(3, 2))], e.text(), e.text_size])
        e.hide()
        e.deleteLater()
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.drawPixmap(self.rect(), self.pix)
        p.fillRect(self.rect(), DIM)
        r = self.sel_rect() if self.a is not None else None
        if r:
            f = QRectF(r).adjusted(-2, -2, 2, 2)  # the frame's outside
            if self.drag not in ("region", "resize"):  # its shadow: not while the size changes (a new blur each frame)
                p.drawImage(f.topLeft() + QPointF(-30, -20), frame_shadow(round(f.width()), round(f.height()), 8, 30, (0, 0, 0, .3)))
            if self.layer:
                p.save()
                p.scale(1 / self.k, 1 / self.k)
                self.layer.paint(p, self.tool == "select" and self.drag != "resize")
                p.restore()
            else:
                p.drawPixmap(r, self.pix, self._src(r))
            p.save()
            p.setRenderHint(QPainter.Antialiasing)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(rgba(0, 0, 0, .25), 1))  # CSS: border 2px white, radius 8; box-shadow 0 0 0 1px
            p.drawRoundedRect(f.adjusted(-.5, -.5, .5, .5), 8.5, 8.5)
            p.setPen(QPen(Qt.white, 2))
            p.drawRoundedRect(f.adjusted(1, 1, -1, -1), 7, 7)
            if self.layer:  # resize handles on the corners (the whole border can be dragged)
                p.setPen(Qt.NoPen)
                p.setBrush(Qt.white)
                for c in (f.topLeft(), f.topRight(), f.bottomLeft(), f.bottomRight()):
                    p.drawImage(c - QPointF(10, 9), shadow(12, 12, 6, 4, (0, 0, 0, .4)))
                    p.drawEllipse(c, 6, 6)
            p.restore()
            s = self._src(r)
            self._tag(p, f, f"{s.width()} × {s.height()}", *self.state())
        elif self.hover is not None:  # what a click here would pick: lit, in a dashed frame 6 outside it
            h, s = self.hover, self._src(self.hover)
            p.drawPixmap(h, self.pix, s)
            f = QRectF(h).adjusted(-6, -6, 6, 6)
            p.save()
            p.setRenderHint(QPainter.Antialiasing)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(rgba(0, 0, 0, .25), 1))  # CSS: border 2px dashed white .9, radius 18; box-shadow 0 0 0 1px
            p.drawRoundedRect(f.adjusted(-.5, -.5, .5, .5), 18.5, 18.5)
            dash = QPen(rgba(255, 255, 255, .9), 2)
            dash.setCapStyle(Qt.FlatCap)  # the default square caps lengthen each dash by the pen's width
            dash.setDashPattern([3, 2])  # in pen widths: 6 on, 4 off, as the board
            p.setPen(dash)
            p.drawRoundedRect(f.adjusted(1, 1, -1, -1), 17, 17)
            p.restore()
            self._tag(p, f, f"{s.width()} × {s.height()}", "สลิป · คลิกเพื่อเลือก" if h in self.qr_picks else "คลิกเพื่อเลือก")
        self.shadows(p)
        if self.band:
            p.setPen(QPen(QColor("#4285f4"), 1, Qt.DashLine))
            p.drawRect(QRect(*self.band).normalized())
        if self.cur and (not self.layer or self.drag == "resize"):
            self._magnifier(p)

    def under(self):  # paint_glass's backdrop for glass painted on the overlay itself; None: opaque
        return (lambda p, r: self.backdrop(p, r.toRect())) if self.clear else None

    def state(self):
        """The tag's words after the size, and its dot's colour (G7): with codes in it, how their checks stand (amber
        while asking, then the worst verdict's colour), else the status: blue while working, red if it failed."""
        s, L = self.status, self.layer
        if L and L.qrs and L.marks and s.startswith(("กำลังอ่าน", "อ่านแล้ว", "อ่านข้อความไม่ได้")):
            slips = [p for _, p in L.qrs if qr_info(p)[0] in ("slip", "truemoney")]
            asking = len({p for p in slips if self.slips.get(p) is None})
            done = any((a := self.slips.get(p)) and a[0] for p in slips)
            head = f"สลิป {len(slips)} ใบ" if len(slips) == len(L.qrs) else f"พบ QR {len(L.qrs)} รายการ"
            worst = min((t for t, _ in L.marks.values()), key=["bad", "warn", "none", "info", "ok"].index)
            return (head + (f" · กำลังตรวจ {asking}" if asking else " · ตรวจแล้ว" if done else ""),
                    tone_ink("warn" if asking else worst))
        if not s:
            return "", None
        return s, QColor("#4CC2FF") if s.startswith("กำลัง") else \
            QColor("#FF4646") if s.startswith("ผิดพลาด") or "ไม่" in s else QColor("#34C778")

    def _tag(self, p, f, size, text="", dot=None):
        """G1/G3's glass label on a frame f (its outside): the size, then what's going on after a dot of its colour.
        12 above f, else inside its top; never under the hint bar or the toolbar (children: they'd paint over it)."""
        sw, tw = QFontMetrics(ui_font(13, mono=True)).horizontalAdvance(size), QFontMetrics(ui_font(13)).horizontalAdvance(text)
        w = 28 + sw + (21 + (13 if dot else 0) + tw if text else 0)  # CSS: padding 0 14, gap 10, a 1px rule; dot 7 + 6
        x, over = max(0, min(f.left(), self.width() - w)), [QRectF(b.geometry()) for b in (self.hints, self.bar) if b.isVisible()]
        ys = ([f.top() - 48] if f.top() >= 48 else []) + [f.top() + 8] + [b.bottom() + 9 for b in over]
        box = next((b for b in (QRectF(x, y, w, 36) for y in ys) if not any(b.intersects(o) for o in over)), QRectF(x, ys[0], w, 36))
        p.drawImage(box.topLeft() + QPointF(-28, 10 - 28), shadow(round(w), 36, 18, 28, (0, 0, 0, .3)))
        paint_glass(p, box, "bar", 18, self.under())
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(ink())
        p.setFont(ui_font(13, mono=True))
        x = box.left() + 14
        p.drawText(QRectF(x, box.top(), sw + 2, 36), Qt.AlignVCenter | Qt.AlignLeft, size)
        if text:
            x += sw + 10
            p.fillRect(QRectF(x, box.center().y() - 7, 1, 14), ink(.25))
            x += 11
            if dot:
                p.setPen(Qt.NoPen)
                p.setBrush(dot)
                p.drawEllipse(QRectF(x, box.center().y() - 3.5, 7, 7))
                x += 13
            p.setPen(ink())
            p.setFont(ui_font(13))
            p.drawText(QRectF(x, box.top(), box.right() - x, 36), Qt.AlignVCenter | Qt.AlignLeft, text)
        p.restore()

    def spot(self, c):  # the screenshot pixel under widget point c: "x, y · #RRGGBB"
        x, y = min(max(int(c.x() * self.k), 0), self.img.width() - 1), min(max(int(c.y() * self.k), 0), self.img.height() - 1)  # a drag goes on past the screen's edge
        return f"{x}, {y} · {self.img.pixelColor(x, y).name().upper()}"

    def _magnifier(self, p):  # G1: a 136 lens 24 off the cursor (flipped near the edges), its pixel's place and colour
        c, d, z, half = self.cur, self.SPAN * self.ZOOM, self.ZOOM, self.SPAN // 2
        label = self.spot(c)
        lw = QFontMetrics(ui_font(12, mono=True)).horizontalAdvance(label) + 24
        x = c.x() + 24 if c.x() + 24 + d < self.width() else c.x() - 24 - d
        y = c.y() + 24 if c.y() + 24 + d + 36 < self.height() else c.y() - 24 - d - 36  # 36: the label under it
        box = QRectF(x, y, d, d)
        zoom = QPixmap(d, d)  # the pixels, gridded, filled into the circle below (a clip path's edge is jagged)
        zoom.fill(Qt.black)  # shows where the source runs off the screenshot
        q = QPainter(zoom)
        q.drawPixmap(QRect(0, 0, d, d), self.pix, QRect(int(c.x() * self.k) - half, int(c.y() * self.k) - half, self.SPAN, self.SPAN))
        q.setPen(rgba(0, 0, 0, .08))  # the pixel grid
        for i in range(1, self.SPAN):
            q.drawLine(i * z, 0, i * z, d)
            q.drawLine(0, i * z, d, i * z)
        q.setPen(QPen(QColor("#0A84FF"), 2))  # the pixel under the cursor
        q.drawRect(QRectF(half * z, half * z, z, z))
        q.end()
        p.drawImage(box.topLeft() + QPointF(-40, 18 - 40), shadow(d, d, d // 2, 40, (0, 0, 0, .4)))
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        lens = QPainterPath()
        lens.addEllipse(box)
        brush = QBrush(zoom)
        brush.setTransform(QTransform.fromTranslate(x, y))
        p.fillPath(lens, brush)
        p.setPen(QPen(rgba(255, 255, 255, .18), 6))  # CSS: inset 0 0 0 6px white .18, inset 0 2px 0 white .6
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(box.adjusted(3, 3, -3, -3))
        p.fillPath(lens - lens.translated(0, 2), rgba(255, 255, 255, .6))
        p.setPen(QPen(rgba(255, 255, 255, .5), 1))
        p.drawEllipse(box.adjusted(.5, .5, -.5, -.5))
        p.restore()
        tag = QRectF(box.center().x() - lw / 2, box.bottom() + 8, lw, 28)
        paint_glass(p, tag, "bar", 14, self.under())
        p.setPen(ink())
        p.setFont(ui_font(12, mono=True))
        p.drawText(tag, Qt.AlignCenter, label)

    def mousePressEvent(self, e):
        pos, pt = e.position(), e.position().toPoint()
        self.end_edit()
        if e.button() == Qt.RightButton:
            if not self.layer:  # like ShareX: drop a half-made selection, or exit
                return self.reset() if self.a is not None else self.closed.emit()
            if self.drag:
                return None
            b = self.childAt(pt)  # a tool's button: that tool, then its size
            if b in self.tools.buttons():
                b.click()
            return self.context_menu(pos)
        if e.button() != Qt.LeftButton:
            return
        L, grip = self.layer, self.grip_at(pt)
        if grip:  # drag the border to resize: a is the corner that stays, b the one that moves
            r, (gx, gy) = self.sel_rect(), grip
            self.a = QPoint(r.right() if gx < 0 else r.left(), r.bottom() if gy < 0 else r.top())
            self.b = QPoint(r.left() if gx < 0 else r.right(), r.top() if gy < 0 else r.bottom())
            self.drag, self.grip = "resize", (gx, gy, L.crop, self.b)
            self.bar.hide()
            if self.card:
                self.card.hide()
            return self.update()
        if L and self.sel_rect().contains(pt):  # work on the selection with the current tool
            if self.tool == "select":
                self.drag, self.band = "band", (pt, pt)
                self.base = set(L.sel) if e.modifiers() & Qt.ControlModifier else set()
            elif self.tool == "text":
                self.start_edit(pos)
            else:
                q = self.to_layer(pos)
                L.shapes.append([self.tool, self.color, [q, q], "", self.sizes.get(self.tool, 1)])
                self.drag = "shape"
            return self.update()
        if L and L.shapes:  # a stray click outside must not throw the drawings away
            return
        pick = self.hover if self.hover is not None else self.pick_at(pt)  # a click (not a drag) takes it
        self.reset()
        self.hints.hide()
        self.started.emit()
        self.a = self.b = self.cur = pt
        self.drag, self.pick = "region", pick

    def mouseMoveEvent(self, e):
        pos, pt = e.position(), e.position().toPoint()
        self.cur, L = pt, self.layer
        if self.drag == "region":
            self.b = pt
        elif self.drag == "resize":
            (gx, gy, _, b0), a = self.grip, self.a
            b = QPoint(pt.x() if gx else b0.x(), pt.y() if gy else b0.y())
            w, h = abs(b0.x() - a.x()), abs(b0.y() - a.y())
            if e.modifiers() & Qt.ShiftModifier and w and h:  # Shift: keep the shape it had when the drag began
                d = b - a
                sx, sy = (1 if d.x() >= 0 else -1), (1 if d.y() >= 0 else -1)
                s = max(abs(d.x()) / w if gx else 0, abs(d.y()) / h if gy else 0)
                s = min(s, (self.width() - 1 - a.x() if sx > 0 else a.x()) / w,  # stop at the screen edge, not skew
                        (self.height() - 1 - a.y() if sy > 0 else a.y()) / h)
                b = a + QPoint(sx * round(s * w), sy * round(s * h))
            self.b = b
            L.crop = self._src(self.sel_rect())
        elif self.drag == "band":
            self.band = (self.band[0], pt)
            band = QRect(self.to_layer(self.band[0]).toPoint(), self.to_layer(pos).toPoint()).normalized()
            L.sel = self.base | {i for i, r in enumerate(L.rects()) if r.intersects(band)}
        elif self.drag == "shape":
            kind, _, pts = L.shapes[-1][:3]
            if kind in ("pen", "marker"):
                pts.append(self.to_layer(pos))
            else:
                pts[-1] = self.to_layer(pos)
        elif L:  # just hovering over a selection: show what a press would do, nothing to repaint
            grip = self.grip_at(pt)
            if grip:
                return self.setCursor(self.grip_cursor(*grip))
            inside = self.sel_rect().contains(pt)
            if inside and self.tool == "select":
                over_text = L.hit(self.to_layer(pos).toPoint()) is not None
                return self.setCursor(Qt.IBeamCursor if over_text else Qt.ArrowCursor)
            return self.setCursor(Qt.CrossCursor if inside or not L.shapes else Qt.ArrowCursor)
        elif self.a is None and (r := self.pick_at(pt)) is not self.base_pick:  # onto another panel: the wheel's
            self.hover = self.base_pick = r                                       # choice gives way to the new one
        self.update()

    def wheelEvent(self, e):  # previewing: up steps out to the panel around this one, down back in
        if self.a is not None or self.hover is None:
            return
        here = [r for r in self.picks if r.contains(e.position().toPoint())]  # smallest first
        i = next((i for i, r in enumerate(here) if r == self.hover), None)
        if i is not None:
            self.hover = here[min(max(i + (1 if e.angleDelta().y() > 0 else -1), 0), len(here) - 1)]
            self.update()

    def leaveEvent(self, _):  # cursor went to another screen: no magnifier, no preview here
        self.cur = self.hover = self.base_pick = None
        self.update()

    def mouseReleaseEvent(self, e):
        drag, self.drag = self.drag, None
        L = self.layer
        if drag == "resize":
            before, self.grip = self.grip[2], None
            self.place_bar()
            # new area: read it again (known translations come back by text); also if a read for an area passed
            # through mid-drag was dropped
            if L.crop != before or not self.ready:
                self.read()
        elif drag == "band":
            a, b = self.band
            self.band = None
            if (b - a).manhattanLength() < 4:  # a click: toggle the line under it
                i = L.hit(self.to_layer(a).toPoint())
                L.sel = self.base ^ {i} if i is not None else self.base
            self.translate_lines(auto=True)
        elif drag == "shape":
            kind, _, pts = L.shapes[-1][:3]
            if kind not in ("pen", "marker") and QLineF(pts[0], pts[-1]).length() < 4 * self.k:
                L.shapes.pop()  # a click, not a drag
        elif drag == "region":
            r, pick, self.pick = self.sel_rect(), self.pick, None
            if (self.b - self.a).manhattanLength() <= 8 and pick is not None:  # a click on a panel: that panel
                self.a, self.b = pick.topLeft(), pick.bottomRight()  # sel_rect spans both corners
            elif r.width() <= 8 or r.height() <= 8:  # a click on nothing, or a slip of the hand: keep picking
                return self.reset()
            self.open_layer()
        self.update()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            return self.end_edit(False) if self.edit else self.closed.emit()
        if not self.layer:
            return
        if e.matches(QKeySequence.Copy):  # the result as shown (translations, drawings), like ShareX/Snipaste
            self.copy_image()
        elif e.matches(QKeySequence.SelectAll):
            self.layer.sel = set(range(len(self.layer.items)))
            self.set_tool("select")
            self.translate_lines(auto=True)
        elif e.matches(QKeySequence.Undo):
            self.undo()
        elif e.matches(QKeySequence.Save):
            self.save()

    def closeEvent(self, e):
        self.gen += 1  # OCR/translation still running would report to a closed window: drop it
        super().closeEvent(e)
