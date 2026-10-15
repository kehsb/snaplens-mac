"""The capture: select, OCR, translate, mark up; a card saying what its QR codes say. The canvas is Qt-painted; its
chrome (toolbar, hints, toast, menus, ink popover: chrome.py; the QR card: qrcard.py) is native AppKit inside its NSView."""
import os

from AppKit import NSWorkspace
from Foundation import NSURL
from PySide6.QtCore import QLineF, QPoint, QPointF, QRect, QRectF, QSizeF, QStandardPaths, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QCursor, QFont, QFontMetrics, QGuiApplication, QImage, QKeySequence,
                           QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QRegion, QTransform)
from PySide6.QtWidgets import QFileDialog, QLineEdit, QWidget

from smartshot.config import CTRL, LANGS
from smartshot.ocr.engine import ocr
from smartshot.ocr.translate import translate
from smartshot.qr.scan import panels, scan_qr
from smartshot.system import mac
from smartshot.task import Task
from smartshot.ui.assets import font, glyph_svg, ui_font
from smartshot.ui.chrome import Chrome
from smartshot.ui.glass import DIM, clear, frame_shadow, frost, ink, paint_glass, qimage, rgba, rim, shadow
from smartshot.ui.native import host
from smartshot.ui.qrcard import QRCard, model


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
        self.qrs = []  # [(QPolygonF, payload)] found in the crop

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
            for n, (poly, _) in enumerate(self.qrs, 1):  # boxed and badged as on the QR card: its head disc's blue
                u, c = self.unit, QColor(76, 194, 255)
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
                p.setPen(QPen(rgba(170, 228, 255, .7), u))
                p.setBrush(c)
                p.drawEllipse(b)
                rim(p, b.adjusted(u, u, -u, -u), 12 * u, rgba(255, 255, 255, .5))
                if len(self.qrs) > 1:  # several: numbered, as on the card
                    p.setPen(QColor(Qt.white))
                    p.setFont(ui_font(round(13 * u), QFont.Bold))
                    p.drawText(b, Qt.AlignCenter, str(n))
                else:
                    g = QRectF(0, 0, 15 * u, 15 * u)
                    g.moveCenter(b.center())
                    glyph_svg("qr", "#ffffffff", 2).render(p, g)
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
    """One per screen, ShareX/Snipaste style. Drag out a region, or click the panel the pointer previews (the wheel
    steps out to the panel around it and back), then work on it in place: OCR starts at once in the background, lines
    can be selected lens-style, drawn on, and translated over the image; drag the border to resize (Shift keeps its
    shape), right-click for a menu (a drawing tool's size while drawing). QR codes in it are explained on a card
    beside it. No second window."""
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
    folder = ""  # where the last image went: the next one is offered there

    def __init__(self, shot_bgr, geometry, mode):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        h, w, _ = shot_bgr.shape
        self.shot, self.mode = shot_bgr, mode
        self.img = qimage(shot_bgr).convertToFormat(QImage.Format_RGB32)
        self.pix = QPixmap.fromImage(self.img)
        self.setGeometry(geometry)
        self.setFixedSize(geometry.size())  # not a window macOS lets an edge drag resize: a drag to the screen's corner selects
        self.k = w / geometry.width()  # screenshot px per widget px (the screen's DPI scale)
        # what the canvas's own glass (the size tag, the magnifier's label) shows through it: the capture frosted;
        # none when Reduce transparency is on
        self.clear = clear()
        self.frost = frost(shot_bgr, geometry.size(), 22)
        # a/b: selection corners. Compare with None: QPoint(0, 0) is falsy
        self.a = self.b = self.layer = self.edit = self.queued = self.band = self.grip = None
        self.drag = None  # "region" | "resize" | "band" | "shape" while the left button is down
        # what a click can pick (widget px, smallest first); the one previewed, the cursor's own (the wheel moves off
        # it), the one a press was on
        self.picks, self.hover, self.base_pick, self.pick = [], None, None, None
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
        self.setFocusPolicy(Qt.ClickFocus)  # a click on the image takes keys (⌘C) back from the QR card's text
        # native, in this window's own view (its winId(), made now, before it's shown): the toolbar, the hint bar
        # (shown while nothing is selected), the toast, the menus; over them the card
        self.view = host(self)
        self.chrome = Chrome(self)
        self.card = QRCard(self.view, self.chrome_pressed, self.copy_card, self.open_link)
        # show_qrs put off while a press on the card is held: a rebuild then would take the button, and its click, away
        self.again = QTimer(self, singleShot=True, interval=50, timeout=self.show_qrs)

    def chrome_pressed(self):
        """A press on native chrome (before its control acts), as one on Qt's did: a text-tool edit is put on the
        image, and the keys come back to the image unless the press is on a card label being selected."""
        self.end_edit()
        if not self.card.keeps_keys() and self.view.window() is not None:
            self.view.window().makeFirstResponder_(self.view)

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

    def backdrop(self, p, r):  # behind the canvas's glass at r: the capture frosted, dimmed like the screen around it
        q = self.frost.width() / self.width()
        p.drawPixmap(QRectF(r), self.frost, QRectF(r.x() * q, r.y() * q, r.width() * q, r.height() * q))
        lit = self.sel_rect() if self.a is not None else self.hover
        p.save()
        if lit is not None:
            p.setClipRegion(QRegion(r).subtracted(QRegion(lit)), Qt.IntersectClip)
        p.fillRect(r, DIM)
        p.restore()

    def reset(self):  # drop the selection and everything done on it
        self.end_edit(False)
        self.gen += 1  # OCR/translation still running for it is ignored when it lands
        self.a = self.b = self.layer = self.queued = self.band = self.drag = self.grip = None
        self.status, self.asked = "", set()
        self.chrome.show_bar(False)
        self.chrome.hints(True)
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

    def place_bar(self):  # the toolbar under the selection (chrome.place: place_bar's rule), then the card
        self.chrome.place()
        self.place_card()

    def place_card(self):  # beside the selection, off the toolbar (QRCard.place); not while the border is dragged:
        if self.drag == "resize" or self.a is None:  # codes read then wait for the release
            return
        bar = self.chrome.bar_frame()
        self.card.place(self.sel_rect().getRect(), bar.getRect() if bar is not None else None)

    def set_picks(self, found):  # panels() is back: boxes in widget px; the cursor may already be on one
        self.picks = [QRect(*(round(v / self.k) for v in b)) for b in found]
        self.hover = self.base_pick = self.pick_at(self.cur) if self.cur is not None and self.a is None else None
        self.update()

    def pick_at(self, pt):  # the smallest panel under the cursor
        return next((r for r in self.picks if r.contains(pt)), None)

    def open_layer(self):  # selection made: tools appear and text is read right away, in the background
        self.hover = self.base_pick = None
        self.layer = Layer(self.img, self._src(self.sel_rect()), self.k)
        self.chrome.set_translate_title(f"แปล · {LANGS[self.lang][0]}")  # may have been changed on another screen
        self.chrome.set_original(False, False)
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
        """The QR card beside the selection: what each code in it says (qrcard.model)."""
        L = self.layer
        if not L or not L.qrs:
            return self.card.show(None)
        if self.card.busy():  # a card button held down (codes read again mid-click): rebuilt once it's let go
            return self.again.start()
        self.card.show(model([p for _, p in L.qrs]))
        self.place_card()

    def on_ocr(self, items, c):
        self.layer.set_items([(r.translated(c.topLeft()), t) for r, t in items])
        self.ready = True
        self.set_status(f"อ่านแล้ว {len(items)} บรรทัด · คลิกบรรทัดเพื่อเลือก" if items else "อ่านข้อความไม่ได้ · ลองขยายพื้นที่")
        fn, self.queued = self.queued, None
        if fn:
            fn()

    def after_ocr(self, fn):  # an action pressed while OCR is still running waits for it
        if self.ready:
            fn()
        else:
            self.queued = fn

    def translate_lines(self, auto=False):
        """Selected lines, or all. auto: lines were just picked; translate those, unless the original is shown."""
        L = self.layer
        if auto and (not L.sel or self.chrome.original()):
            return
        if not auto:
            self.chrome.set_original(False)
        rows = [L.items[i] for i in sorted(L.sel)] or L.items
        if not self.send([t for _, t in rows]) and not auto and not self.asked:
            self.set_status(f"แปลเป็น{LANGS[self.lang][0]}แล้ว") if rows else self.chrome.say("ไม่พบข้อความ", "bad")

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
        self.chrome.set_original(enabled=True)
        self.set_status(f"แปลเป็น{LANGS[lang][0]}แล้ว {len(lines)} บรรทัด")

    def set_ink(self, c):  # the toolbar's dot and the popover show it (chrome)
        self.color = c

    def set_lang(self, code):  # what was translated is redone in the new language; nothing yet: translate now
        if code == self.lang:
            return self.after_ocr(self.translate_lines)
        Overlay.lang = code
        self.chrome.set_translate_title(f"แปล · {LANGS[code][0]}")
        self.place_bar()  # the button's width changed
        L = self.layer
        redo = [t for _, t in L.items if t in L.tr or t in self.asked]
        L.tr, self.asked = {}, set()
        L.layout()
        self.chrome.set_original(False)
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
            return self.chrome.say("ไม่พบข้อความ", "bad")
        QGuiApplication.clipboard().setText("\n".join(lines))
        self.chrome.say(f"คัดลอกข้อความแล้ว {len(lines)} บรรทัด")

    def copy_card(self, text):  # the card's คัดลอก: what its codes say
        QGuiApplication.clipboard().setText(text)
        self.chrome.say("คัดลอกแล้ว")

    def open_link(self, url):  # the card's เปิดลิงก์: the capture ends first (the browser would open under it), as Esc
        u = NSURL.URLWithString_(url)
        if u is None or (u.scheme() or "").lower() not in ("http", "https"):
            return self.chrome.say("เปิดลิงก์ไม่ได้", "bad")
        self.closed.emit()
        NSWorkspace.sharedWorkspace().openURL_(u)

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
                self.chrome.say("บันทึกรูปไม่สำเร็จ", "bad")

    def ask_path(self, title, path, types):  # where to save: the dialog over this (above the menu bar)
        self.chrome.escape()  # the ink popover shut first: its monitor would eat the dialog's first click
        with mac.under_dialogs(self):
            return QFileDialog.getSaveFileName(self, title, os.path.normpath(path), types)[0]

    def undo(self):
        if self.layer and self.layer.shapes:
            self.layer.shapes.pop()
            self.update()

    def set_tool(self, name):
        self.end_edit()
        self.tool = name
        self.chrome.set_tool(name)
        self.update()

    def context_menu(self, pos):  # right-click on a selection (or the toolbar): what can be done with it, at the mouse
        L = self.layer
        if self.tool != "select":  # drawing: the ink's colour and how big this tool draws
            return self.chrome.inks(pos)
        i = L.hit(self.to_layer(pos).toPoint())
        if i is not None and i not in L.sel:  # right-click on a line selects it, like text anywhere else
            L.sel = {i}
            self.translate_lines(auto=True)
            self.update()
        self.chrome.context_menu(pos)  # แปล, คัดลอกข้อความ, คัดลอกรูปแล้วปิด, บันทึกรูป | เลือกพื้นที่ใหม่, ปิด

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
            self._tag(p, f, f"{s.width()} × {s.height()}", "คลิกเพื่อเลือก")
        if self.band:
            p.setPen(QPen(QColor("#4285f4"), 1, Qt.DashLine))
            p.drawRect(QRect(*self.band).normalized())
        if self.cur and (not self.layer or self.drag == "resize"):
            self._magnifier(p)

    def under(self):  # paint_glass's backdrop for glass painted on the overlay itself; None: opaque
        return (lambda p, r: self.backdrop(p, r.toRect())) if self.clear else None

    def state(self):
        """The tag's words after the size, and its dot's colour (G7): with codes in it, how many (the card's blue), else
        the status: blue while working, red if it failed."""
        s, L = self.status, self.layer
        if L and L.qrs and s.startswith(("กำลังอ่าน", "อ่านแล้ว", "อ่านข้อความไม่ได้")):
            return f"พบ QR {len(L.qrs)} รายการ", QColor("#4CC2FF")
        if not s:
            return "", None
        return s, QColor("#4CC2FF") if s.startswith("กำลัง") else \
            QColor("#FF4646") if s.startswith("ผิดพลาด") or "ไม่" in s else QColor("#34C778")

    def _tag(self, p, f, size, text="", dot=None):
        """G1/G3's glass label on a frame f (its outside): the size, then what's going on after a dot of its colour.
        12 above f, else inside its top; never under the hint bar or the toolbar (native: they'd show over it)."""
        sw, tw = QFontMetrics(ui_font(13, mono=True)).horizontalAdvance(size), QFontMetrics(ui_font(13)).horizontalAdvance(text)
        w = 28 + sw + (21 + (13 if dot else 0) + tw if text else 0)  # CSS: padding 0 14, gap 10, a 1px rule; dot 7 + 6
        x, over = max(0, min(f.left(), self.width() - w)), \
            [QRectF(b) for b in (self.chrome.hints_frame(), self.chrome.bar_frame()) if b is not None]
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
        if (w := self.view.window()) is not None:  # any button, as Qt's ClickFocus: the keys come back from the card
            w.makeFirstResponder_(self.view)  # (AppKit moves them on a left press only)
        if e.button() == Qt.RightButton:
            if not self.layer:  # like ShareX: drop a half-made selection, or exit
                return self.reset() if self.a is not None else self.closed.emit()
            if self.drag:
                return None
            return self.context_menu(pos)
        if e.button() != Qt.LeftButton:
            return
        L, grip = self.layer, self.grip_at(pt)
        if grip:  # drag the border to resize: a is the corner that stays, b the one that moves
            r, (gx, gy) = self.sel_rect(), grip
            self.a = QPoint(r.right() if gx < 0 else r.left(), r.bottom() if gy < 0 else r.top())
            self.b = QPoint(r.left() if gx < 0 else r.right(), r.top() if gy < 0 else r.bottom())
            self.drag, self.grip = "resize", (gx, gy, L.crop, self.b)
            self.chrome.show_bar(False)
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
        self.chrome.hints(False)
        self.started.emit()
        self.a = self.b = self.cur = pt
        self.drag, self.pick = "region", pick

    def mouseMoveEvent(self, e):
        pos, pt = e.position(), e.position().toPoint()
        if not self.drag and self.chrome.covers(pt):  # on the toolbar or the card (their moves reach Qt too): an
            return self.setCursor(Qt.ArrowCursor)  # arrow, and nothing under them lit or magnified, as on Qt's chrome
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
            elif r.width() <= 8 or r.height() <= 8:  # a click on nothing, or a twitch of the hand: keep picking
                return self.reset()
            self.open_layer()
        self.update()

    def escape(self):  # Esc: drops a text-tool edit, else the capture
        return self.end_edit(False) if self.edit else self.closed.emit()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            return self.escape()
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
        self.again.stop()
        self.chrome.close()  # nothing native left on the view, nothing left to call back
        self.card.close()
        super().closeEvent(e)
