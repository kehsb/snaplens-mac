"""The capture overlay's chrome, native (all of it but the QR card): the toolbar of Liquid Glass capsules, the hint bar,
the toast, the ink popover, the right-click and translate-language menus, and the keys a native view hands back to
the overlay. It lives in the overlay's own NSView (native.host), laid out in Qt's widget points. The Overlay keeps the
state and does the work; this shows it and calls the Overlay's methods.

The overlay tells it: place() (the selection changed: the toolbar under it, shown), show_bar(visible), hints(visible),
set_tool(name), set_translate_title(text), set_original(checked, enabled), say(text, tone), inks(at=None),
context_menu(pos), close(). It answers the canvas and the card: bar_frame(), capsule_frame(name), hints_frame() (QRect,
None while hidden), covers(pt) and original() (the eye's state). The size tag stays painted by the overlay: it avoids
hints_frame() and bar_frame() as it avoided those widgets.

What it calls on the Overlay: its tools, colours, sizes, lang and layer; set_tool, set_ink (the colour only: the dot
reads it), undo, after_ocr with translate_lines and copy_text, copy_image, save, show_original, set_lang, closed,
chrome_pressed (any press on the toolbar), reset (the menu's เลือกพื้นที่ใหม่), drag (no right-click menu mid-drag),
mode and MODES (the hint bar's reading mode), chrome (KeyMonitor), and context_menu(pos): a drawing tool → inks(pos);
select → the line under pos picked and translated, then this context_menu(pos)."""
import math
from functools import partial

import AppKit
import objc
import Quartz
from Foundation import NSMakeRect, NSObject
from PySide6.QtCore import QPointF, QRect, QTimer

from snaplens.config import CTRL, LANGS
from snaplens.system import mac
from snaplens.ui.native import (GLASS, Surface, box, dynamic, fixed, glass, host, label, menu, pin, reported, srgb, stack,
                                 symbol, target)

try:
    GROUP = objc.lookUpClass("NSGlassEffectContainerView")  # capsules side by side, their glass sampled together
except objc.nosuchclass_error:
    GROUP = None

CMD, CTRL_KEY = AppKit.NSEventModifierFlagCommand, AppKit.NSEventModifierFlagControl
SYMBOLS = {"select": "text.viewfinder", "pen": "pencil.tip", "marker": "highlighter", "rect": "rectangle",
           "arrow": "arrow.up.right", "text": "textformat", "mosaic": "checkerboard.rectangle"}
HINTS = (("ลาก", "เลือกพื้นที่"), ("คลิก", "เลือกช่องที่ไฮไลต์"), ("ล้อเมาส์", "ขยาย/ย่อ"), ("Esc", "ปิด"))
NAMES = ("แดง", "เหลือง", "เขียว", "ฟ้า", "ขาว")  # Overlay.COLORS, for VoiceOver
INK = 28 / 255, 31 / 255, 38 / 255  # the light glass's ink, #1C1F26
WASH = dynamic((1, 1, 1, .22), (1, 1, 1, 1))  # a button hovered, pressed or on; light glass: white, edged
EDGE = dynamic((1, 1, 1, 0), (*INK, .12))
LIT = srgb(255, 255, 255, .22)  # on the blue glass, either way
CAP = dynamic((1, 1, 1, .16), (1, 1, 1, 1))  # a keycap
CHIP = dynamic((76 / 255, 194 / 255, 1, .42), (47 / 255, 155 / 255, 224 / 255, .85))  # the hint bar's mode: the tint glass's
RING = dynamic((1, 1, 1, .9), (*INK, .85))  # the popover's colour picked
TRACK = dynamic((0, 0, 0, .25), (*INK, .07))  # under its sizes
TOASTS = {"ok": ("checkmark", AppKit.NSColor.systemGreenColor()), "save": ("square.and.arrow.down", AppKit.NSColor.systemBlueColor()),
          "bad": ("xmark", AppKit.NSColor.systemRedColor())}


def fit(view):  # what its constraints make it, once laid out somewhere roomy (a bordered box's edge counts only then)
    if not view.frame().size.width:
        view.setFrameSize_((4000, 400))
    view.layoutSubtreeIfNeeded()
    s = view.fittingSize()
    return math.ceil(s.width), math.ceil(s.height)


def move(view, x, y, w, h):  # Qt's coordinates as they are; no implicit animation
    Quartz.CATransaction.begin()
    Quartz.CATransaction.setDisableActions_(True)
    view.setFrame_(NSMakeRect(x, y, w, h))
    view.layoutSubtreeIfNeeded()
    Quartz.CATransaction.commit()


def later(fn):  # a menu's pick runs once the menu is gone and the press that opened it has returned (GlassMenu.pick)
    return lambda: QTimer.singleShot(0, fn)


def hexcolor(c):
    return srgb(int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))


def oval(r):
    return AppKit.NSBezierPath.bezierPathWithOvalInRect_(r)


def centred(b, d):
    return NSMakeRect(b.origin.x + (b.size.width - d) / 2, b.origin.y + (b.size.height - d) / 2, d, d)


def shade(a):  # what's filled next casts a soft shadow (inside saveGraphicsState)
    s = AppKit.NSShadow.alloc().init()
    s.setShadowBlurRadius_(6)
    s.setShadowOffset_((0, -2))
    s.setShadowColor_(AppKit.NSColor.colorWithWhite_alpha_(0, a))
    s.set()


class ChromeKey(AppKit.NSButton):
    """A button on the chrome's glass: an SF Symbol (and a title); a wash behind it when hovered, pressed or on. Takes no
    focus (the keys stay the overlay's), works on a first click (another screen's overlay). right: what a right-click
    on it does (every toolbar button has one: the bar's, a tool's own); without one (the popover's), nothing. ⌃-click
    is a right-click, as Qt has it."""
    hover, area, right, radius, tinted = False, None, None, 20, False

    def acceptsFirstMouse_(self, e):
        return True

    def alignmentRectInsets(self):  # its frame is the 40 laid out (a symbol's own insets would grow it)
        return AppKit.NSEdgeInsets(0, 0, 0, 0)

    def updateTrackingAreas(self):
        objc.super(ChromeKey, self).updateTrackingAreas()
        if self.area is not None:
            self.removeTrackingArea_(self.area)
        self.area = AppKit.NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
            AppKit.NSZeroRect, AppKit.NSTrackingMouseEnteredAndExited | AppKit.NSTrackingActiveAlways
            | AppKit.NSTrackingInVisibleRect, self, None)
        self.addTrackingArea_(self.area)

    def mouseEntered_(self, e):
        self.hover = True
        self.setNeedsDisplay_(True)

    def mouseExited_(self, e):
        self.hover = False
        self.setNeedsDisplay_(True)

    def mouseDown_(self, e):
        if e.modifierFlags() & CTRL_KEY:
            return self.rightMouseDown_(e)
        objc.super(ChromeKey, self).mouseDown_(e)

    def rightMouseDown_(self, e):
        if self.right:
            return self.right(e)
        objc.super(ChromeKey, self).rightMouseDown_(e)

    def drawRect_(self, r):
        if self.isEnabled() and (self.state() or self.isHighlighted() or self.hover):
            path = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(self.bounds(), self.radius, self.radius)
            (LIT if self.tinted else WASH).setFill()
            path.fill()
            if not self.tinted:
                edge = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                    AppKit.NSInsetRect(self.bounds(), .5, .5), self.radius - .5, self.radius - .5)
                EDGE.setStroke()
                edge.stroke()
        objc.super(ChromeKey, self).drawRect_(r)


class ChromeSwatch(ChromeKey):  # the toolbar's ink: the colour in a white ring, shadowed
    color = None

    def drawRect_(self, r):
        objc.super(ChromeSwatch, self).drawRect_(r)
        b = self.bounds()
        AppKit.NSGraphicsContext.saveGraphicsState()
        shade(.35)
        srgb(255, 255, 255, .85).setFill()
        oval(centred(b, 24)).fill()
        AppKit.NSGraphicsContext.restoreGraphicsState()
        self.color.setFill()
        oval(centred(b, 20)).fill()


class ChromeDot(ChromeKey):  # one of the popover's colours: a 28 disc, ringed when it's the ink's
    def drawRect_(self, r):
        b = self.bounds()
        if self.state():
            ring = oval(AppKit.NSInsetRect(b, 1, 1))
            ring.setLineWidth_(2)
            RING.setStroke()
            ring.stroke()
        AppKit.NSGraphicsContext.saveGraphicsState()
        shade(.3)
        self.color.setFill()
        oval(centred(b, 28)).fill()
        AppKit.NSGraphicsContext.restoreGraphicsState()


class ChromeCell(ChromeKey):  # one of the popover's sizes: its dot over its name, centred
    dot, name, radius = 7, "", 16

    def isFlipped(self):
        return True

    def drawRect_(self, r):
        objc.super(ChromeCell, self).drawRect_(r)
        b, ink = self.bounds(), AppKit.NSColor.labelColor()
        top = (b.size.height - self.dot - 20) / 2  # the dot, 4, a 16 line
        ink.setFill()
        oval(NSMakeRect((b.size.width - self.dot) / 2, top, self.dot, self.dot)).fill()
        mid = AppKit.NSMutableParagraphStyle.alloc().init()
        mid.setAlignment_(AppKit.NSTextAlignmentCenter)
        AppKit.NSString.stringWithString_(self.name).drawInRect_withAttributes_(
            NSMakeRect(0, top + self.dot + 4, b.size.width, 16),
            {AppKit.NSFontAttributeName: AppKit.NSFont.systemFontOfSize_(12), AppKit.NSForegroundColorAttributeName: ink,
             AppKit.NSParagraphStyleAttributeName: mid})


class ChromeBar(Surface):  # the toolbar's root: a right-click (or ⌃-click) anywhere on it is the overlay's
    right = None

    def rightMouseDown_(self, e):
        self.right(e)

    def mouseDown_(self, e):
        if e.modifierFlags() & CTRL_KEY:
            self.right(e)


class ChromeGhost(Surface):  # the hint bar's and the toast's: clicks, wheel and moves go through to the image
    def hitTest_(self, pt):
        return None


class ChromePopoverDelegate(NSObject):
    def initWithFn_(self, fn):
        self = objc.super(ChromePopoverDelegate, self).init()
        self.fn = fn
        return self

    def popoverDidClose_(self, note):
        reported(self.fn)


def key(glyph, tip, fn, keep, keys="", size=17, toggle=False, width=40, height=40):
    """A toolbar button: tip (and keys, "⌘+Z") its tooltip, the tip's head its name for VoiceOver; fn(button)."""
    b = ChromeKey.buttonWithImage_target_action_(symbol(glyph, size, AppKit.NSFontWeightMedium), target(fn, keep), "fire:")
    b.setBordered_(False)
    if toggle:
        b.setButtonType_(AppKit.NSButtonTypePushOnPushOff)
    b.setImagePosition_(AppKit.NSImageOnly)
    b.setContentTintColor_(AppKit.NSColor.labelColor())
    b.setRefusesFirstResponder_(True)
    b.setToolTip_(f"{tip}  {keys.replace('+', '')}" if keys else tip)
    b.setAccessibilityLabel_(tip.split(" · ")[0].split(": ")[0])
    return fixed(b, width, height)


def drawn(cls, w, h, tip, fn, keep):  # a toggle drawn by itself (cls): the ink, a colour, a size
    b = fixed(cls.alloc().init(), w, h)
    b.setBordered_(False)
    b.setTitle_("")
    b.setButtonType_(AppKit.NSButtonTypePushOnPushOff)
    b.setTarget_(target(fn, keep))
    b.setAction_("fire:")
    b.setRefusesFirstResponder_(True)
    b.setAccessibilityLabel_(tip)
    return b


def capsule(views, tint=None):  # glass round 40 buttons: 52 high, 6 around them, 2 between (0 on the tinted one)
    return fixed(glass(stack(views, spacing=0 if tint else 2, insets=(6, 6, 6, 6)), 26, tint), h=52)


class Chrome:
    """One per overlay (o): built hidden but for the hint bar, in o's own NSView."""

    def __init__(self, o):
        self.o, self.keep, self.picks, self.view = o, [], [], host(o)  # picks: the open menu's targets
        self.pop = self.clicks = None
        self.bar, self.hint, self.toast = self.toolbar(), self.hint_bar(), self.toaster()
        # the toast's own: a slot holding this would keep it (and the overlay) alive through Qt's connection
        self.timer = QTimer(singleShot=True, interval=2500, timeout=partial(self.toast.setHidden_, True))
        self.set_tool(o.tool)
        for v in (self.bar, self.hint, self.toast):
            self.view.addSubview_(v)
        w, h = fit(self.hint)
        move(self.hint, (o.width() - w) // 2, 20, w, h)

    # --- the toolbar: capsules 8 apart: tools | ink, undo | translate (blue) | view, copy, image, save | close
    def toolbar(self):
        o, keep = self.o, self.keep
        self.tools = {}
        for name, tip in o.TOOLS:
            b = self.tools[name] = key(SYMBOLS[name], tip if name == "select" else f"{tip} · คลิกขวา: สีและขนาด",
                                       lambda _, n=name: self.pick_tool(n), keep, toggle=True)
            b.right = lambda e, n=name: self.right(e, n)  # that tool, then its ink (or the menu, under select)
        sep = fixed(AppKit.NSBox.alloc().init(), 1, 22)
        sep.setBoxType_(AppKit.NSBoxSeparator)
        first = self.tools[o.TOOLS[0][0]]
        tools = capsule([first, sep, *list(self.tools.values())[1:]])
        for v in (first, sep):  # 4 more either side of the line
            first.superview().setCustomSpacing_afterView_(6, v)
        self.ink = drawn(ChromeSwatch, 40, 40, "สีและขนาดเส้น", lambda _: self.inks(), keep)  # on while its popover's open
        self.ink.setToolTip_("สีและขนาดเส้น")
        self.ink.color = hexcolor(o.color)
        undo = key("arrow.uturn.backward", "เลิกทำ", lambda _: o.undo(), keep, f"{CTRL}+Z")
        self.tr = key("translate", "แปลบรรทัดที่เลือก หรือทั้งหมด แล้ววางทับในภาพ",
                      lambda _: o.after_ocr(o.translate_lines), keep, size=15, width=None)
        self.tr.setImagePosition_(AppKit.NSImageLeading)
        self.tr.setImageHugsTitle_(True)
        self.tr_width = self.tr.widthAnchor().constraintEqualToConstant_(40)
        self.tr_width.setActive_(True)
        self.set_translate_title(f"แปล · {LANGS[o.lang][0]}")
        langs = key("chevron.down", "เลือกภาษา", lambda _: self.lang_menu(), keep, size=12, width=32)
        for b in (self.tr, langs):  # on the blue glass: white, as today's
            b.tinted = True
            b.setContentTintColor_(AppKit.NSColor.whiteColor())
        self.orig = key("eye", "สลับดูต้นฉบับ / คำแปล", lambda b: o.show_original(bool(b.state())), keep, toggle=True)
        view = [self.orig, key("doc.on.doc", "คัดลอกข้อความ: ที่เลือก หรือทั้งหมด", lambda _: o.after_ocr(o.copy_text), keep),
                key("photo.on.rectangle", "คัดลอกรูปแล้วปิด", lambda _: o.copy_image(), keep, f"{CTRL}+C"),
                key("square.and.arrow.down", "บันทึกรูป", lambda _: o.save(), keep, f"{CTRL}+S")]
        close = key("xmark", "ปิด", lambda _: o.closed.emit(), keep, "Esc")
        self.keys = [*self.tools.values(), self.ink, undo, self.tr, langs, *view, close]
        for b in self.keys[len(self.tools):]:  # a right-click or ⌃-click on the others is the bar's (a ⌃-click on a
            b.right = self.right               # button doesn't climb to it)
        self.capsules = {"tools": tools, "ink": capsule([self.ink, undo]),
                         "translate": capsule([self.tr, langs], AppKit.NSColor.systemBlueColor()),
                         "view": capsule(view), "close": capsule([close])}  # close: a circle of its own
        row = stack(list(self.capsules.values()), spacing=8)
        bar = ChromeBar.alloc().initWithPressed_(o.chrome_pressed)
        bar.right = self.right
        if GROUP is not None:
            group = GROUP.alloc().init()
            row.setTranslatesAutoresizingMaskIntoConstraints_(False)
            group.setContentView_(row)
            pin(group, bar)
        else:
            pin(row, bar)
        bar.setHidden_(True)
        return bar

    def place(self):  # under the selection from its left, else above it, else inside its bottom edge (place_bar's)
        o, r = self.o, self.o.sel_rect()
        self.swatch()
        w, h = fit(self.bar)
        y = r.bottom() + 21  # 18 under the selection's frame, which is 2 outside it
        if y + h > o.height():
            y = r.top() - h - 20
        if y < 0:
            y = r.bottom() - h - 8
        move(self.bar, min(max(r.left() - 2, 0), o.width() - w), y, w, h)
        self.bar.setHidden_(False)

    def show_bar(self, visible):
        if not visible:
            self.escape()
            for b in self.keys:  # no exit comes for the button the pointer was on
                b.hover = False
        self.bar.setHidden_(not visible)

    def pick_tool(self, name):
        self.o.set_tool(name)
        self.set_tool(self.o.tool)  # a click on the tool that's on doesn't turn it off

    def set_tool(self, name):
        for n, b in self.tools.items():
            b.setState_(int(n == name))
        self.inks_now()

    def set_translate_title(self, text):  # its width with it: then place() again
        font = AppKit.NSFont.systemFontOfSize_weight_(14, AppKit.NSFontWeightSemibold)
        t = AppKit.NSAttributedString.alloc().initWithString_attributes_(
            text, {AppKit.NSFontAttributeName: font, AppKit.NSForegroundColorAttributeName: AppKit.NSColor.whiteColor()})
        self.tr.setAttributedTitle_(t)
        self.tr_width.setConstant_(math.ceil(28 + self.tr.image().size().width + t.size().width))  # 12 icon 8 text 8

    def set_original(self, checked=None, enabled=None):  # the eye (None: as it is); as Qt's toggled did, a change of
        if enabled is not None:                             # checked shows the original or not
            self.orig.setEnabled_(enabled)
        if checked is not None and checked != self.original():
            self.orig.setState_(int(checked))
            self.o.show_original(checked)

    def original(self):  # the eye on: the original shown, not the translations
        return bool(self.orig.state())

    def swatch(self):
        self.ink.color = hexcolor(self.o.color)
        self.ink.setNeedsDisplay_(True)

    def right(self, e, name=None):  # a right-click on the bar is the overlay's, as it went through Qt's glass
        o = self.o
        if o.drag:
            return
        if name:
            self.pick_tool(name)
        p = self.view.convertPoint_fromView_(e.locationInWindow(), None)
        o.context_menu(QPointF(p.x, p.y))

    # --- where things are, in the overlay's points (QRect: bottom() is y + h - 1, as Qt's own widgets were)
    def frame(self, v):
        f = v.convertRect_toView_(v.bounds(), self.view)
        return QRect(round(f.origin.x), round(f.origin.y), round(f.size.width), round(f.size.height))

    def bar_frame(self):
        return None if self.bar.isHidden() else self.frame(self.bar)

    def capsule_frame(self, name):  # "tools", "ink", "translate", "view", "close"
        return None if self.bar.isHidden() else self.frame(self.capsules[name])

    def hints_frame(self):
        return None if self.hint.isHidden() else self.frame(self.hint)

    def covers(self, pt):  # over native chrome that takes the mouse (the bar, the card): not the image's move
        return any(isinstance(v, Surface) and not isinstance(v, ChromeGhost) and not v.isHidden()
                   and AppKit.NSPointInRect((pt.x(), pt.y()), v.frame()) for v in self.view.subviews())

    # --- the hint bar: while nothing is selected, what the mouse does and the reading mode; clicks go through
    def hint_bar(self):
        pairs = []
        for k, t in HINTS:
            cap = box(stack([label(k, 12, mono=k.isascii())], insets=(3, 9, 3, 9)), 9, CAP, border=True)
            pairs.append(stack([fixed(cap, h=22), label(t, 14)], spacing=7))
        globe = AppKit.NSImageView.imageViewWithImage_(symbol("globe", 13, AppKit.NSFontWeightMedium))
        globe.setContentTintColor_(AppKit.NSColor.whiteColor())
        chip = box(stack([globe, label(f"อ่าน: {self.o.MODES.get(self.o.mode, self.o.mode)}", 14, color=AppKit.NSColor.whiteColor())],
                         spacing=6, insets=(0, 14, 0, 14)), 18, CHIP)
        v = ChromeGhost.alloc().initWithPressed_(None)
        pin(fixed(glass(stack([*pairs, fixed(chip, h=36)], spacing=18, insets=(8, 18, 8, 8)), 26), h=52), v)
        return v

    def hints(self, visible):
        self.hint.setHidden_(not visible)

    # --- the toast: what an action did, under the toolbar for 2.5 s; clicks go through
    def toaster(self):
        self.toast_icon = fixed(AppKit.NSImageView.alloc().init(), 30, 30)
        self.toast_icon.setContentTintColor_(AppKit.NSColor.whiteColor())
        self.toast_disc = box(self.toast_icon, 15, TOASTS["ok"][1])
        self.toast_text = label("", 14, AppKit.NSFontWeightMedium)
        self.toast_glass = fixed(glass(stack([self.toast_disc, self.toast_text], spacing=10, insets=(7, 8, 7, 18)), 22), h=44)
        v = ChromeGhost.alloc().initWithPressed_(None)
        pin(self.toast_glass, v)
        v.setHidden_(True)
        return v

    def say(self, text, tone="ok"):  # tone: "ok" (a check), "save", "bad" (red glass, an x)
        o, (glyph, color) = self.o, TOASTS[tone]
        self.toast_icon.setImage_(symbol(glyph, 15, AppKit.NSFontWeightSemibold))
        self.toast_disc.setFillColor_(color)
        self.toast_text.setStringValue_(text)
        if GLASS is not None:
            self.toast_glass.setTintColor_(AppKit.NSColor.systemRedColor().colorWithAlphaComponent_(.5) if tone == "bad" else None)
        w, h = fit(self.toast)
        r = self.bar_frame() or QRect(o.width() // 2, o.height() // 2, 0, 0)  # 10 under the bar, else above; else mid-screen
        y = r.bottom() + 11 if r.bottom() + 11 + h <= o.height() else r.top() - 10 - h
        move(self.toast, min(max(r.center().x() - w // 2, 0), o.width() - w), y, w, h)
        self.view.addSubview_positioned_relativeTo_(self.toast, AppKit.NSWindowAbove, None)  # over everything
        self.toast.setHidden_(False)
        self.timer.start()
        AppKit.NSAccessibilityPostNotificationWithUserInfo(
            AppKit.NSApp, AppKit.NSAccessibilityAnnouncementRequestedNotification,
            {AppKit.NSAccessibilityAnnouncementKey: text, AppKit.NSAccessibilityPriorityKey: AppKit.NSAccessibilityPriorityHigh})

    # --- the ink popover: colour and size, from the toolbar's dot or a right-click while drawing. Stays open for another
    # pick; a press anywhere else shuts it and does nothing more, and so does Esc (KeyMonitor)
    def ink_popover(self):
        o, keep = self.o, self.keep
        self.dots = []
        for c, name in zip(o.COLORS, NAMES):
            d = drawn(ChromeDot, 40, 40, name, lambda _, c=c: self.pick_color(c), keep)
            d.color = hexcolor(c)
            self.dots.append(d)
        self.cells = []
        for s, name, px in o.SIZES:
            b = drawn(ChromeCell, 62, 52, name, lambda _, s=s: self.pick_size(s), keep)
            b.dot, b.name = px, name
            self.cells.append(b)
        self.sizes = stack(self.cells, spacing=4, insets=(4, 4, 4, 4))
        grey = AppKit.NSColor.secondaryLabelColor()
        content = stack([label("สี", 12, color=grey), stack(self.dots, spacing=17), label("ขนาด", 12, color=grey),
                         box(self.sizes, 20, TRACK)], vertical=True, spacing=16, insets=(16, 16, 16, 16))
        content.setHuggingPriority_forOrientation_(999, AppKit.NSLayoutConstraintOrientationHorizontal)  # 16 on the right too
        vc = AppKit.NSViewController.alloc().init()
        vc.setView_(content)
        self.pop = AppKit.NSPopover.alloc().init()
        self.pop.setBehavior_(AppKit.NSPopoverBehaviorApplicationDefined)  # shut by outside() and Esc, not by AppKit
        self.pop.setContentViewController_(vc)
        self.pop.setContentSize_(fit(content))
        self.pop_delegate = ChromePopoverDelegate.alloc().initWithFn_(self.inks_closed)
        self.pop.setDelegate_(self.pop_delegate)

    def inks(self, at=None):  # under the toolbar's dot, or at at (an overlay point: a right-click while drawing)
        if self.pop is None:
            self.ink_popover()
        self.escape()
        self.inks_now()
        if at is None:
            self.show_popover(self.ink.bounds(), self.ink)
        else:
            self.show_popover(NSMakeRect(at.x(), at.y(), 1, 1), self.view)
        self.ink.setState_(AppKit.NSControlStateValueOn)
        self.clicks = AppKit.NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            AppKit.NSEventMaskLeftMouseDown | AppKit.NSEventMaskRightMouseDown | AppKit.NSEventMaskOtherMouseDown,
            lambda e: reported(self.outside, e, fallback=e))

    def show_popover(self, rect, view):  # under rect (MaxY: the bottom in a flipped view), else where AppKit finds room
        self.pop.showRelativeToRect_ofView_preferredEdge_(rect, view, AppKit.NSRectEdgeMaxY)
        self.pop.contentViewController().view().window().setBecomesKeyOnlyIfNeeded_(True)  # the overlay keeps the keys

    def outside(self, e):  # a press on anything but the popover (the dot too: a second click shuts it) is eaten
        if e.window() is not None and e.window() == self.pop.contentViewController().view().window():
            return e
        self.escape()
        return None

    def escape(self):  # -> True if the popover was open: Esc shuts only that
        if self.pop is None or not self.pop.isShown():
            return False
        self.inks_closed()
        self.pop.close()
        return True

    def inks_closed(self):  # however it closed
        if self.clicks is not None:
            AppKit.NSEvent.removeMonitor_(self.clicks)
            self.clicks = None
        self.ink.setState_(AppKit.NSControlStateValueOff)

    def inks_now(self):  # the dot's colour; the popover's ring and size, the tool's own (none under select)
        o = self.o
        self.swatch()
        if self.pop is None:
            return
        for d, c in zip(self.dots, o.COLORS):
            d.setState_(int(c == o.color))
        size, sized = o.sizes.get(o.tool, 1), o.tool != "select"
        for b, (s, *_) in zip(self.cells, o.SIZES):
            b.setState_(int(sized and s == size))
            b.setEnabled_(sized)
        self.sizes.setAlphaValue_(1 if sized else .4)

    def pick_color(self, c):
        self.o.set_ink(c)
        self.inks_now()

    def pick_size(self, s):
        if self.o.tool != "select":
            self.o.sizes[self.o.tool] = s
        self.inks_now()

    # --- menus: built on every open from the overlay's state; a pick runs once the menu is gone
    def context_menu(self, pos):  # the right-click's, under select: what can be done with the selection, at the mouse
        o, keep = self.o, self.picks
        keep.clear()
        what, lang = "ที่เลือก" if o.layer.sel else "ทั้งหมด", LANGS[o.lang][0]
        self.pop_menu(menu([("translate", f"แปล{what}เป็น{lang}", None, False, later(lambda: o.after_ocr(o.translate_lines))),
                            ("doc.on.doc", f"คัดลอกข้อความ{what}", None, False, later(lambda: o.after_ocr(o.copy_text))),
                            ("photo.on.rectangle", "คัดลอกรูปแล้วปิด", ("c", CMD), False, later(o.copy_image)),
                            ("square.and.arrow.down", "บันทึกรูป", ("s", CMD), False, later(o.save)), None,
                            ("viewfinder", "เลือกพื้นที่ใหม่", None, False, later(o.reset)),
                            # no Esc on ปิด: the open menu's own Esc only shuts the menu
                            ("xmark", "ปิด", None, False, later(o.closed.emit))], keep), pos, context=True)

    def lang_menu(self):  # the translate capsule's arrow: under the capsule from its left, else above it (drop's)
        o, keep = self.o, self.picks
        keep.clear()
        m = menu([("head", "แปลเป็น")] + [(None, n, None, c == o.lang, later(lambda c=c: o.set_lang(c)))
                                          for c, (n, _) in LANGS.items()], keep)
        g, h = self.capsule_frame("translate"), m.size().height
        self.pop_menu(m, QPointF(g.left(), g.bottom() + 11 if g.bottom() + 11 + h <= o.height() else g.top() - 10 - h))

    def pop_menu(self, m, at, context=False):  # blocks while it's open
        m.setAllowsContextMenuPlugIns_(False)
        e = AppKit.NSApp.currentEvent()
        if context and e is not None and e.type() in (AppKit.NSEventTypeLeftMouseDown, AppKit.NSEventTypeRightMouseDown):
            AppKit.NSMenu.popUpContextMenu_withEvent_forView_(m, e, self.view)
        else:
            m.popUpMenuPositioningItem_atLocation_inView_(None, (at.x(), at.y()), self.view)
        self.view.resetMouseButtons()  # the menu took the release: Qt would think the button still down

    def close(self):  # the overlay is closing: nothing of it left on its view, nothing left to call it
        self.timer.stop()
        self.escape()
        for v in (self.bar, self.hint, self.toast):
            v.removeFromSuperview()
        # what AppKit objects hold of Python goes: Python can't collect a cycle through them, and the overlay (its
        # screenshot, ~70 MB a Retina screen) would stay for the app's life
        self.keep.clear()
        self.picks.clear()
        self.bar.pressed = self.bar.right = None
        for b in self.keys:
            b.right = None
        if self.pop is not None:
            self.pop.setDelegate_(None)  # no call after this (its close may come once the animation's done)
            self.pop_delegate.fn = None


def letter(e):  # Esc, else the key a ⌘-shortcut means: its letter, or its place on the keyboard under a Thai layout
    if e.keyCode() == 53:
        return "esc"
    c = (e.charactersIgnoringModifiers() or "").lower()
    return c if c.isascii() else mac.KEYS.get(e.keyCode(), "")


class KeyMonitor:
    """A capture's keys while a native view has them: one per capture (Main: from the overlays opening to end_capture),
    for every overlay. With an overlay's own view first responder, Qt has them as ever. In the card's key box only
    Esc and ⌘S are the overlay's (Return is the box's: use_key); in a card label ⌘C and ⌘A copy and select its text;
    from anything else native, Esc ⌘C ⌘A ⌘Z ⌘S go back to the overlay's view, which takes the keys from then on.
    ⌘C ⌘A ⌘X ⌘V on their way to the overlay's view are handed to it here: the Edit menu (install_edit_menu) would take
    them first, a disabled item too (the image's ⌘C and ⌘A, the text tool's field). Esc shuts an open ink popover
    first, and only that. ⌘H and ⌘, (the app menu's Hide and Settings…) do nothing during a capture; ⌘Q still quits."""

    def __init__(self, overlays):
        self.overlays = overlays
        self.monitor = AppKit.NSEvent.addLocalMonitorForEventsMatchingMask_handler_(AppKit.NSEventMaskKeyDown, self.on_key)

    def remove(self):
        if self.monitor is not None:
            AppKit.NSEvent.removeMonitor_(self.monitor)
            self.monitor = None

    def on_key(self, e):  # AppKit's: a bug in route() is printed and the key goes on (it mustn't eat Esc)
        return reported(self.route, e, fallback=e)

    def route(self, e):
        k, cmd, w = letter(e), bool(e.modifierFlags() & CMD), e.window()
        if cmd and k in ("h", ","):
            return None
        found = next(((v, o) for o in self.overlays if w is not None and (v := host(o)).window() in (w, w.parentWindow())), None)
        if found is None:
            return e
        view, o = found
        if k == "esc" and o.chrome.escape():
            return None
        fr = w.firstResponder()
        if fr != view:
            if not (k == "esc" or cmd and k in ("c", "a", "z", "s")):
                return e
            field = fr.delegate() if isinstance(fr, AppKit.NSTextView) and fr.isFieldEditor() else None
            if field is not None and (k not in ("esc", "s") if field.isEditable() else k in ("c", "a")):
                return e  # the key box's, a label's
            view.window().makeFirstResponder_(view)
        if cmd and k in ("c", "a", "x", "v"):  # Qt's, not the Edit menu's
            view.keyDown_(e)
            return None
        return e
