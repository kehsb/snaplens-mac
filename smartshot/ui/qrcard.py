"""The QR card beside a capture's selection, native AppKit on Liquid Glass inside the overlay's own view: what each
code in it says, to copy, and a link's เปิดลิงก์.

model() reads the codes into plain data (no Qt, no AppKit); QRCard shows it, rebuilt in place on every change, and
hands what the user does back through callbacks.

The overlay (Overlay.show_qrs) passes the codes' payloads in scan order (its badges on the image are numbered the
same), places the card beside the selection (place(), not while the border is dragged), hides it on a grip press and
closes it with itself. Its chrome_pressed leaves the keys where they are when keeps_keys() (a click on the label
being selected)."""
import math
import re
from types import SimpleNamespace

import AppKit
from Foundation import NSMakeRange, NSMakeRect
from PySide6.QtCore import QTimer

from smartshot.config import THAI
from smartshot.qr.promptpay import qr_info
from smartshot.ui.native import GLASS, Surface, box, dynamic, fixed, glass, pin, srgb, stack, symbol, target

LINK = re.compile(r"https?://\S+", re.I)  # what เปิดลิงก์ opens: a web link, nothing else (no file:, no app schemes)
PAY = ("promptpay", "emv", "bill")  # qr_info's kinds that ask for money


def model(codes):
    """The card for the codes in a selection: what each says. codes: their payloads in scan order (top to bottom,
    then left). -> a namespace:
      entries: one per code: n (its number when there are several, else 0), head, sub, rows [(label, value)]
        (qr_info's), warn (the CRC's), url (the payload when it's a web link, else None)
      copy: what คัดลอก copies; dense: several codes, tighter"""
    dense, entries, texts = len(codes) > 1, [], []
    for i, payload in enumerate(codes):
        kind, title, rows, warn = qr_info(payload)
        sub = "QR นี้ใช้จ่ายเงิน" if kind in PAY else ""
        url = payload.strip() if kind == "url" and LINK.fullmatch(payload.strip()) else None
        entries.append(SimpleNamespace(n=(i + 1) * dense, head=title, sub=sub, rows=rows, warn=warn.lstrip("⚠ "),
                                       url=url))
        texts.append("\n".join([title] + [sub] * bool(sub) + [(f"{k}: " if k else "") + v for k, v in rows]
                               + [warn] * bool(warn) + [f"QR: {payload}"] * (kind not in ("url", "text"))))
    return SimpleNamespace(entries=entries, copy="\n\n".join(texts), dense=dense)


# --- the view
def rgba(c):  # (r, g, b[, a]), 0-255 and an alpha, as native.dynamic's
    return (c[0] / 255, c[1] / 255, c[2] / 255, c[3] if len(c) > 3 else 1.0)


# the head disc: fill, line (the info tone: the codes' boxes and badges on the image are its too), following the
# appearance; its number's badge
FILL = dynamic(rgba((76, 194, 255, .5)), rgba((47, 155, 224)))
LINE = dynamic(rgba((170, 228, 255, .5)), rgba((47, 155, 224)))
BADGE = srgb(76, 194, 255)
LIT = AppKit.NSColor.colorWithWhite_alpha_(1, .4)
BOX = dynamic((1, 1, 1, .07), (1, 1, 1, .7)), dynamic((1, 1, 1, .08), (1, 1, 1, .9))  # a box in the card: fill, line
SECONDARY, FAINT = AppKit.NSColor.secondaryLabelColor(), AppKit.NSColor.tertiaryLabelColor()
RED = AppKit.NSColor.systemRedColor()
SEMIBOLD, REGULAR = AppKit.NSFontWeightSemibold, AppKit.NSFontWeightRegular
WIDTH = 420  # the card's, or the screen less 20
# the buttons: glass capsules on macOS 26, else rounded ones (PyObjC has 26's constants on any macOS: ask the class)
BEZEL, SIZE = (AppKit.NSBezelStyleGlass, AppKit.NSControlSizeExtraLarge) if GLASS is not None else \
    (AppKit.NSBezelStyleRounded, AppKit.NSControlSizeLarge)


def text(s, size=14, weight=REGULAR, color=None, mono=False, sel=False, width=None):
    """A label of untrusted text (QR payloads): plain, never a link, at most 400 characters; wrapped at width
    (points; None: one line). sel: selectable, as the values a user may want to copy."""
    s = s if len(s) <= 400 else s[:400] + "…"
    f = AppKit.NSTextField.wrappingLabelWithString_(s) if width else AppKit.NSTextField.labelWithString_(s)
    f.setFont_(AppKit.NSFont.monospacedSystemFontOfSize_weight_(size, weight) if mono else
               AppKit.NSFont.systemFontOfSize_weight_(size, weight))
    f.setTextColor_(color or AppKit.NSColor.labelColor())
    f.setSelectable_(sel)
    if width:
        f.setPreferredMaxLayoutWidth_(width)
    return f


def inset(view, top=0, left=0, bottom=0, right=0):
    return stack([view], insets=(top, left, bottom, right))


def margins(row, top, bottom):
    """A row of views of different heights, top and bottom above and below the tallest. A row's own insets across it
    hold for a lone view only: each view is held to them, weakly, so they give way (insets 14 and 10, a 44 disc beside
    30 of words: the disc got 7 and 7)."""
    v = AppKit.NSView.alloc().init()
    pin(row, v, (top, 0, bottom, 0))
    return v


def lit_top(rect, radius, color):  # CSS inset 0 1px 0: the top edge of a rounded rect lit (flipped views)
    AppKit.NSGraphicsContext.saveGraphicsState()
    AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, radius, radius).addClip()
    rim = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, radius, radius)
    rim.appendBezierPath_(AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        AppKit.NSOffsetRect(rect, 0, 1), radius, radius))
    rim.setWindingRule_(AppKit.NSWindingRuleEvenOdd)
    color.setFill()
    rim.fill()
    AppKit.NSGraphicsContext.restoreGraphicsState()


class Disc(AppKit.NSView):
    """The head's round badge: the info tone's fill, a 1px edge, a lit top, and its number in its corner when there
    are several codes, as their badges on the image. The glyph is a subview."""
    n = 0

    def isFlipped(self):
        return True

    def drawRect_(self, _):
        b = self.bounds()
        oval = AppKit.NSBezierPath.bezierPathWithOvalInRect_(AppKit.NSInsetRect(b, .5, .5))
        FILL.setFill()
        oval.fill()
        LINE.setStroke()
        oval.setLineWidth_(1)
        oval.stroke()
        r = AppKit.NSInsetRect(b, 1, 1)
        lit_top(r, r.size.width / 2, LIT)
        if self.n:
            BADGE.setFill()
            AppKit.NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(0, 0, 16, 16)).fill()
            s = AppKit.NSAttributedString.alloc().initWithString_attributes_(str(self.n), {
                AppKit.NSFontAttributeName: AppKit.NSFont.systemFontOfSize_weight_(11, AppKit.NSFontWeightBold),
                AppKit.NSForegroundColorAttributeName: AppKit.NSColor.whiteColor()})
            z = s.size()
            s.drawAtPoint_(((16 - z.width) / 2, (16 - z.height) / 2))


def disc(n=0, says=""):
    v = fixed(Disc.alloc().initWithFrame_(NSMakeRect(0, 0, 44, 44)), 44, 44)
    v.n = n
    icon = AppKit.NSImageView.imageViewWithImage_(symbol("qrcode", 20, AppKit.NSFontWeightSemibold))
    icon.setContentTintColor_(AppKit.NSColor.whiteColor())
    icon.setTranslatesAutoresizingMaskIntoConstraints_(False)
    v.addSubview_(icon)
    icon.centerXAnchor().constraintEqualToAnchor_(v.centerXAnchor()).setActive_(True)
    icon.centerYAnchor().constraintEqualToAnchor_(v.centerYAnchor()).setActive_(True)
    v.setAccessibilityElement_(True)
    v.setAccessibilityRole_(AppKit.NSAccessibilityImageRole)
    v.setAccessibilityLabel_(says)
    return v


class QRCard:
    """The card, one per overlay: made once (hidden), rebuilt in place by show(), put beside the selection by
    place(). host: the overlay's NSView (native.host), flipped, in the overlay's points; pressed: its Surface's
    (Overlay.chrome_pressed). What the user does goes back through callbacks, each called after the event that asked
    (later; none once the card is closed): copy(text) (คัดลอก: Overlay.copy_card puts what the codes say on the
    clipboard), open_link(url) (เปิดลิงก์, a lone web link's: Overlay.open_link ends the capture, then opens it)."""

    def __init__(self, host, pressed, copy, open_link):
        self.host, self.copy, self.open_link = host, copy, open_link
        self.keep, self.m, self.content, self.w, self.h = [], None, None, WIDTH, 0
        self.root = Surface.alloc().initWithPressed_(pressed)
        self.root.setHidden_(True)
        self.root.setAccessibilityElement_(True)
        self.root.setAccessibilityRole_(AppKit.NSAccessibilityGroupRole)
        self.body = AppKit.NSView.alloc().init()
        pin(glass(self.body, 30), self.root)
        host.addSubview_(self.root)

    # --- what the overlay calls
    def show(self, m):
        """Rebuild from model() (None or no entries: gone). Placed (and shown) by place()."""
        had = self.focus()
        self.m = m if m and m.entries else None
        if self.content is not None:
            self.content.removeFromSuperview()
        self.keep, self.content = [], None
        if not self.m:
            return self.hide(had)
        self.w = min(WIDTH, int(self.host.bounds().size.width) - 20)
        self.content = self.build(self.m, self.w, self.footer(self.m))
        pin(self.content, self.body)
        self.h = math.ceil(self.content.fittingSize().height)
        f = self.root.frame()
        self.move(f.origin.x, f.origin.y)
        self.root.setAccessibilityLabel_(self.m.entries[0].head if len(self.m.entries) == 1 else f"QR {len(self.m.entries)} รายการ")
        self.root.layoutSubtreeIfNeeded()
        win = self.host.window()
        if had and win is not None:  # the label with the keys went: back to the overlay, as Qt's focus
            win.makeFirstResponder_(self.host)

    def place(self, sel, bar=None):
        """Beside the selection sel (x, y, w, h in the overlay's points): right, else left, else inside its top-right
        corner; off the toolbar's frame bar (or None); kept on the screen (a card taller than it: at the top)."""
        if not self.m:
            return
        size = self.host.bounds().size
        (x, y, sw, _), w, h = sel, self.w, self.h
        right = x + sw - 1  # Qt's QRect.right()
        cx = right + 10 if right + 10 + w <= size.width else x - 10 - w
        if cx < 0:
            cx = right - w - 10
        cx, cy = max(cx, 0), max(y, 0)
        if bar and cx < bar[0] + bar[2] and bar[0] < cx + w and cy < bar[1] + bar[3] and bar[1] < cy + h:
            cy = bar[1] - 8 - h if bar[1] - 8 - h >= 0 else bar[1] + bar[3] + 7  # Qt's bottom() + 8
        self.move(cx, min(cy, max(size.height - h, 0)))
        self.root.setHidden_(False)

    def move(self, x, y):  # no implicit animation
        AppKit.CATransaction.begin()
        AppKit.CATransaction.setDisableActions_(True)
        self.root.setFrame_(NSMakeRect(x, y, self.w, self.h))
        AppKit.CATransaction.commit()

    def hide(self, had=None):  # e.g. while the selection's border is dragged; place() shows it again
        had = had if had is not None else self.focus()
        self.root.setHidden_(True)
        if had and self.host.window() is not None:
            self.host.window().makeFirstResponder_(self.host)

    def close(self):
        self.root.removeFromSuperview()
        self.keep, self.m = [], None
        self.root.pressed = None  # no cycle through AppKit objects: the overlay can go (Chrome.close)

    def busy(self):  # a press on the card is held (a button tracking it): rebuilt now, the button and its click would go
        e, win = AppKit.NSApp.currentEvent(), self.root.window()
        return e is not None and win is not None and e.window() == win and not self.root.isHidden() \
            and e.type() in (AppKit.NSEventTypeLeftMouseDown, AppKit.NSEventTypeLeftMouseDragged) \
            and AppKit.NSPointInRect(self.root.convertPoint_fromView_(e.locationInWindow(), None), self.root.bounds())

    def focus(self):  # a selected label of the card has the keys
        win = self.root.window()
        fr = win.firstResponder() if win is not None else None
        owner = fr.delegate() if isinstance(fr, AppKit.NSText) else fr
        return isinstance(owner, AppKit.NSView) and owner.isDescendantOf_(self.root)

    def keeps_keys(self):
        """The press being handled is on the label being selected (a second click, a drag, its right-click Copy): it
        has the keys. Taken away, the label's editor (the very view the press goes to) would leave the window."""
        e, win = AppKit.NSApp.currentEvent(), self.root.window()
        if e is None or win is None:
            return False
        fr = win.firstResponder()
        owner = fr.delegate() if isinstance(fr, AppKit.NSText) else None
        return isinstance(owner, AppKit.NSView) and owner.isDescendantOf_(self.root) and owner.window() is not None \
            and not owner.isHiddenOrHasHiddenAncestor() \
            and AppKit.NSPointInRect(owner.convertPoint_fromView_(e.locationInWindow(), None), owner.bounds())

    def later(self, fn):  # after the event that asked (an action may rebuild the card, the control that sent it with
        # it), on Qt's queue as chrome's menus: an exception there is printed, not the app's end. Nothing once the
        # card is closed.
        QTimer.singleShot(0, lambda: self.root.superview() is not None and fn())

    # --- building it
    def build(self, m, w, foot):  # the card's column, w wide, foot (its buttons) under
        inner, views = w - 16, []
        for e in m.entries:
            if e.n > 1:  # a hairline between codes
                line = AppKit.NSBox.alloc().init()
                line.setBoxType_(AppKit.NSBoxSeparator)
                views.append(line)
            views += self.entry(e, inner, m.dense)
        views.append(foot)
        col = stack(views, vertical=True, spacing=8, insets=(8, 8, 8, 8))
        fixed(col, w)
        for v in views:  # each the card's width inside its margins
            v.setTranslatesAutoresizingMaskIntoConstraints_(False)
            v.widthAnchor().constraintEqualToConstant_(inner).setActive_(True)
        # laid out once: a box measures 3 short before its first layout, so the card (h) would; from then on
        # fittingSize is the height it lays out at
        col.setFrame_(NSMakeRect(0, 0, w, math.ceil(col.fittingSize().height)))
        col.layoutSubtreeIfNeeded()
        return col

    def entry(self, e, inner, dense):  # a code's views: head, warn, rows
        d = disc(e.n, e.head + (f" · QR ที่ {e.n}" if e.n else ""))
        room = inner - 28 - 44 - 14
        words = stack([text(e.head, 17, SEMIBOLD, width=room)] +
                      [text(e.sub, 14, color=SECONDARY, width=room)] * bool(e.sub), vertical=True, spacing=2)
        words.setContentHuggingPriority_forOrientation_(1, AppKit.NSLayoutConstraintOrientationHorizontal)
        row = stack([d, words], spacing=14, insets=(0, 14, 0, 14))
        row.setDistribution_(AppKit.NSStackViewDistributionFill)
        views = [margins(row, 6 if dense else 14, 4 if dense else 10)]
        if e.warn:
            views.append(inset(text(e.warn, 13, color=RED, width=inner - 28), left=14, right=14))
        if e.rows:  # what the code says
            views.append(self.code_rows(e.rows, inner))
        return views

    def code_rows(self, rows, inner):
        room = inner - 36
        c0 = max([96] + [min(math.ceil(text(k, 13).fittingSize().width), (room - 12) // 2) for k, _ in rows if k])
        cells = []
        for k, v in rows:
            mono = not THAI.search(v) and sum(c.isdigit() for c in v) >= 4  # ids, phones, refs
            if k:
                cells.append([text(k, 13, color=FAINT, width=c0), text(v, 13 if mono else 14, mono=mono, sel=True, width=room - c0 - 12)])
            else:  # a link or text: the box's width, not selectable (as the Qt card)
                cells.append([text(v, 13 if mono else 14, mono=mono, width=room), AppKit.NSGridCell.emptyContentView()])
        g = AppKit.NSGridView.gridViewWithViews_(cells)
        g.setColumnSpacing_(12)
        g.setRowSpacing_(20)
        g.setYPlacement_(AppKit.NSGridCellPlacementTop)
        g.setXPlacement_(AppKit.NSGridCellPlacementLeading)
        g.columnAtIndex_(0).setWidth_(c0)
        g.columnAtIndex_(1).setWidth_(room - c0 - 12)
        for i, (k, _) in enumerate(rows):
            if not k:
                g.mergeCellsInHorizontalRange_verticalRange_(NSMakeRange(0, 2), NSMakeRange(i, 1))
        return self.box(inset(g, 16, 18, 16, 18))

    def box(self, view):  # a box in the card: radius 22, a faint wash and line
        b = box(view, 22, BOX[0], border=True)
        b.setBorderColor_(BOX[1])
        b.setBorderWidth_(1)
        return b

    def button(self, title, glyph, prominence, fn):  # a glass capsule; no focus: the keys stay the overlay's
        t = target(lambda _: self.later(fn), self.keep)
        b = AppKit.NSButton.buttonWithTitle_image_target_action_(title, symbol(glyph), t, "fire:")
        b.setBezelStyle_(BEZEL)
        b.setControlSize_(SIZE)
        if b.respondsToSelector_("setTintProminence:"):
            b.setTintProminence_(prominence)  # NSTintProminence: 1 none, 2 primary, 3 secondary
        b.setImagePosition_(AppKit.NSImageLeading)
        b.setRefusesFirstResponder_(True)
        return b

    def footer(self, m):  # คัดลอก, and a lone web link's เปิดลิงก์, at the card's trailing end
        buttons = [self.button("คัดลอก", "doc.on.doc", 1, lambda t=m.copy: self.copy(t))]
        if len(m.entries) == 1 and m.entries[0].url:
            buttons.append(self.button("เปิดลิงก์", "safari", 2, lambda u=m.entries[0].url: self.open_link(u)))
        foot = stack([], spacing=8, insets=(4, 6, 6, 6))
        for b in buttons:
            foot.addView_inGravity_(b, AppKit.NSStackViewGravityTrailing)
        return foot
