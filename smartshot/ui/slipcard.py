"""The QR card beside a capture's selection, native AppKit on Liquid Glass inside the overlay's own view: what each
code in it says; a slip's verdict from its bank (Thunder), compared field by field with what the image shows; the key
box when Thunder has no key; and the receipt it saves as.

model() reads the overlay's state into plain data (no Qt, no AppKit); SlipCard shows it, rebuilt in place on every
change (the key field, what's typed in it and its focus survive), and hands what the user does back through callbacks.

The overlay (Overlay.show_qrs) passes the codes' and OCR lines' centres in screenshot px, asks the slips in m.ask,
takes m.marks for the codes' badges on the image (tone_rgb), places the card beside the selection (place(), not
while the border is dragged), hides it on a grip press, closes it with itself, and composes save_receipt() from
receipt_png() in the appearance of its own canvas (chrome()'s ground). Its chrome_pressed leaves the keys where they
are when keeps_keys() (a click in the key box, or on the label being selected)."""
import math
import re
from datetime import datetime
from functools import partial
from types import SimpleNamespace

import AppKit
import objc
from Foundation import NSMakeRange, NSMakeRect, NSObject
from PySide6.QtCore import QTimer

from smartshot.config import THAI
from smartshot.qr.promptpay import TH_MONTHS, qr_info
from smartshot.slip.compare import compare
from smartshot.slip.thunder import NO_KEY, THUNDER_ERRORS, slip_fields
from smartshot.ui.native import GLASS, Surface, box, dynamic, fixed, glass, pin, srgb, stack, symbol, target

# verdict -> the head disc: fill, line (design: these colours are for verdicts, nowhere else); dark, light
TONES = {"ok": ((52, 199, 120, .55), (140, 240, 180, .5)), "warn": ((255, 170, 40, .55), (255, 214, 140, .5)),
         "bad": ((255, 70, 70, .55), (255, 160, 160, .5)), "info": ((76, 194, 255, .5), (170, 228, 255, .5)),
         "none": ((255, 255, 255, .16), (255, 255, 255, .25))}
TONES_LIGHT = {"ok": ((31, 162, 94), (31, 162, 94)), "warn": ((224, 138, 0), (224, 138, 0)),  # G8's (light glass)
               "bad": ((229, 72, 77), (229, 72, 77)), "info": ((47, 155, 224), (47, 155, 224)),
               "none": ((122, 130, 148), (122, 130, 148))}
MARKS = {"✓": ("check", (52, 199, 120, .7)), "✗": ("x", (255, 70, 70, .75)), "?": ("question", (255, 255, 255, .16))}
MARKS_LIGHT = {"✓": ("check", (31, 162, 94)), "✗": ("x", (229, 72, 77)), "?": ("question", (122, 130, 148, .6))}
KEYLESS = (NO_KEY, THUNDER_ERRORS["INVALID_API_KEY"])  # answers the card asks for a key on
MONEY = re.compile(r"(?<![\d.,])\d{1,3}(?:,?\d{3})*\.\d\d(?!\d)")  # 123.45, 1,234.56; not part of a longer number
# the verdicts' glyphs (model(), the image's badges) as SF Symbols: on the head's 44 disc, on a table row's 22
HEAD = {"check": "checkmark.seal.fill", "x": "xmark.octagon.fill", "question": "questionmark",
        "history": "clock.arrow.circlepath", "search": "magnifyingglass", "key": "key.fill", "qr": "qrcode"}
MARK = {"check": "checkmark", "x": "xmark", "question": "questionmark"}
SAYS = {"✓": "ตรง", "✗": "ไม่ตรง", "?": "เทียบไม่ได้"}  # a mark, to VoiceOver


def tone_rgb(tone):  # a verdict's colour, solid: its code's box and badge on the image ("none": grey, seen on white too)
    return (138, 138, 138) if tone == "none" else TONES[tone][0][:3]


def verdict(payload, res, table=(), seen=None):
    """A slip's state, compare()'s rows -> tone, glyph (None: still asking), head, sub. seen: Overlay.seen."""
    if res is None:
        return "info", None, "กำลังตรวจกับธนาคาร…", ""
    if res[1]:  # messages read "what: what to do"; red only for a slip the bank doesn't have, not "couldn't check"
        bad, (head, _, sub) = res[1] == THUNDER_ERRORS["SLIP_NOT_FOUND"], res[1].partition(": ")
        return "bad" if bad else "none", "x" if bad else "question", head, sub
    if res[0].get("isDuplicate"):  # amber either way: a slip shown again may be a payment claimed twice
        if first := (seen or {}).get(payload):  # the app lives in the menu bar for days: the day too, unless today
            day = "" if first.date() == datetime.now().date() else f"{first.day} {TH_MONTHS[first.month - 1]} "
            return "warn", "history", f"ตรวจสลิปนี้ไปแล้วเมื่อ {day}{first:%H:%M} น.", "ธนาคารยืนยันรายการ ถ้ารับเงินไปแล้ว อย่ารับซ้ำ"
        return "warn", "history", "สลิปนี้เคยถูกตรวจแล้ว", "ถ้าไม่ได้ตรวจเอง อาจเป็นสลิปที่ใช้ซ้ำ"
    if bad := [r[0] for r in table if r[4] == "✗"]:  # an edited image (or a misread): the table shows both sides
        return "warn", "search", "ข้อมูลในภาพไม่ตรงกับธนาคาร", f"ไม่ตรง: {', '.join(bad)}"
    n, unsure = sum(r[4] == "✓" for r in table), sum(r[4] == "?" for r in table)
    return "ok", "check", "ธนาคารยืนยันรายการ", \
        f"ตรง {n} · เทียบไม่ได้ {unsure}" if unsure else "ข้อมูลในภาพตรงกับธนาคาร" if table else "เทียบข้อมูลกับสลิป"


def model(codes, lines, slips, ready, seen):
    """The card for the codes in a selection, read like a bank receipt: verdict, amount, who, when.
    codes: [(payload, centre)] in scan order (top to bottom, then left); lines: OCR's [(text, centre)]; centres (x, y)
    in one unit (a line goes with the code nearest it); slips: payload -> Thunder's (data, error, when), None while
    asking; ready: OCR is done for this crop; seen: Overlay.seen. -> a namespace:
      entries: one per code: n (its number when there are several, else 0), tone, glyph (None: a spinner), head, sub,
        sub_sel (sub selectable: an error), time (when the bank answered, or None), warn, amount (as shown, or None),
        table [(label, in the image, the bank's, under it, mark)], rows [(label, value)] (the code's own), key (the
        key box goes under it: the first entry waiting on a key)
      ask: [(kind, payload)] slips not in slips yet, to check now (shown as asking)
      marks: payload -> (tone, glyph), for the codes' boxes and badges on the image
      retry: the payloads ตรวจใหม่ asks again ([]: no button); copy: what คัดลอก copies (None: no button);
      receipt: บันทึกใบตรวจ shown; wide: a table in it (the card's 540, else 420); dense: several codes, tighter"""
    ask = list(dict.fromkeys((k, p) for p, _ in codes if (k := qr_info(p)[0]) in ("slip", "truemoney") and p not in slips))
    slips = {**slips, **{p: None for _, p in ask}}  # new slips are asked first: a verdict waits for every answer
    # to tell an edited slip: every amount OCR read here (0.00: fee lines), and what the bank says each code paid
    found = [(c, v) for t, c in lines for m in MONEY.findall(t) if (v := round(float(m.replace(",", "")), 2))]
    fields = {p: slip_fields(qr_info(p)[0], s[0]) for p, _ in codes if (s := slips.get(p)) and s[0]}
    paid = [round(f[2], 2) for p, _ in codes for f in fields.get(p, ()) if f[1] == "amount" and isinstance(f[2], (int, float))]
    # ponytail: a line belongs to the code nearest it; the slip's outline (which isn't known) would be exact
    near = lambda c: min(range(len(codes)), key=lambda i: abs(codes[i][1][0] - c[0]) + abs(codes[i][1][1] - c[1]))
    dense = len(codes) > 1  # ponytail: no scrolling; tighter, 2 checked slips fit 1080p, 3 don't
    entries, texts, retry, marks, key = [], [], [], {}, False
    for i, (payload, _) in enumerate(codes):
        kind, title, rows, warn = qr_info(payload)
        slip, res, amount, table = kind in ("slip", "truemoney"), None, None, []
        if slip and (res := slips[payload]) and res[0]:
            f, rows = fields[payload], []
            amount = next((x[2] for x in f if x[1] == "amount"), None)
            a = round(amount, 2) if isinstance(amount, (int, float)) else None
            # edited: printed fewer times than the codes here pay it, and not beside this one (stacked slips put
            # one's amount nearer the next one's code, so "not beside it" alone can't say)
            few = bool(found) and a is not None and [v for _, v in found].count(a) < paid.count(a)
            # OCR's lines are of the crop as it was: a resized one is compared once it's read again
            table = compare(f, [t for t, c in lines if near(c) == i], {v for c, v in found if near(c) == i},
                            few, len(codes) == 1) if ready else [(x[0], "…", x[3], x[4], "") for x in f]
        tone, glyph, head, sub = verdict(payload, res, table, seen) if slip else \
            ("info", "qr", title, "QR นี้ใช้จ่ายเงิน ไม่ใช่สลิป" if kind in ("promptpay", "emv", "bill") else "")
        if tone == "ok" and [p for p, _ in codes].count(payload) > 1:  # one transfer shown twice: claimed twice?
            tone, glyph, head, sub = "warn", "history", "สลิปเดียวกันซ้ำในภาพนี้", "ธนาคารยืนยันแค่รายการเดียว อย่ารับเงินซ้ำ"
        elif tone == "ok" and (not ready or None in [slips.get(p, 0) for p, _ in codes]):
            # no green before the image could be compared: OCR's, and the other codes' answers (one may pay the same)
            tone, glyph, head, sub = "info", None, "กำลังเทียบข้อมูลในภาพ…", "ธนาคารยืนยันรายการแล้ว"
        if slip and res is None:
            sub = "อ่าน QR สลิปแล้ว · รอคำตอบจาก Thunder"
        keyless = bool(res) and res[1] in KEYLESS
        if keyless:  # the card takes the key itself: no file to edit, no "ตรวจใหม่" to press
            glyph, sub = "key", "ใส่คีย์ครั้งเดียว แล้วตรวจสลิปกับธนาคารได้ทันที" if res[1] == NO_KEY else \
                "วางคีย์ที่ถูกต้องด้านล่าง แล้วตรวจได้ทันที"
        retry += [payload] * bool(res and res[1] and not keyless)
        marks[payload] = tone, glyph
        num = f"{amount:,.2f}" if isinstance(amount, (int, float)) else str(amount)
        entries.append(SimpleNamespace(
            n=(i + 1) * dense, tone=tone, glyph=glyph, head=head, sub=sub, sub_sel=bool(res and res[1]),
            time=res[2] if res and not keyless else None, warn=warn.lstrip("⚠ "), table=table,
            amount=num if amount is not None else None, key=keyless and not key,
            rows=rows if not table and not keyless and (res or not slip) else []))  # a slip's: once the bank answered
        key = key or keyless
        texts.append("\n".join([head] + [sub] * bool(sub) + [f"จำนวนเงิน: {num} บาท"] * (amount is not None)
                               + [f"{k}: {shown}" + (f" ({u})" if u else "") + (f" | ในภาพ: {s or '–'} {mark}" if mark else "")
                                  for k, s, shown, u, mark in table]
                               + [(f"{k}: " if k else "") + v for k, v in rows]
                               + [warn] * bool(warn) + [f"QR: {payload}"] * (kind not in ("url", "text"))))
    checked = [s for p, _ in codes if (s := slips.get(p)) and (s[0] or s[1] == THUNDER_ERRORS["SLIP_NOT_FOUND"])]
    return SimpleNamespace(
        entries=entries, ask=ask, marks=marks, retry=retry, dense=dense, wide=any(e.table for e in entries),
        copy="\n\n".join(texts) if not key or len(codes) > 1 else None,  # a lone no-key slip has nothing to copy
        receipt=bool(ready and checked and None not in [slips.get(p, 0) for p, _ in codes]))  # every answer in


# --- the view
def rgba(c):  # the tables' (r, g, b[, a]), 0-255 and an alpha, as native.dynamic's
    return (c[0] / 255, c[1] / 255, c[2] / 255, c[3] if len(c) > 3 else 1.0)


# the tables' colours, following the appearance
FILL, LINE = ({k: dynamic(rgba(TONES[k][i]), rgba(TONES_LIGHT[k][i])) for k in TONES} for i in (0, 1))
MARK_FILL = {k: dynamic(rgba(MARKS[k][1]), rgba(MARKS_LIGHT[k][1])) for k in MARKS}
LIT = AppKit.NSColor.colorWithWhite_alpha_(1, .4)
BOX = dynamic((1, 1, 1, .07), (1, 1, 1, .7)), dynamic((1, 1, 1, .08), (1, 1, 1, .9))  # a box in the card: fill, line
FIELD = dynamic((0, 0, 0, .3), (1, 1, 1, .8)), dynamic((1, 1, 1, .14), (28 / 255, 31 / 255, 38 / 255, .14))
BAND = srgb(255, 70, 70, .18)  # a table row the image differs on
# the receipt's card, opaque (glass.chrome() under the card's glass fill): ground, fill, lit top edge, edge
FLAT = (dynamic(rgba((28, 31, 38)), rgba((244, 245, 248))), dynamic((28 / 255, 30 / 255, 36 / 255, .42), (1, 1, 1, .55)),
        dynamic((1, 1, 1, .34), (1, 1, 1, 1)), dynamic(rgba((51, 56, 68)), rgba((213, 216, 222))))
SECONDARY, FAINT = AppKit.NSColor.secondaryLabelColor(), AppKit.NSColor.tertiaryLabelColor()
RED = AppKit.NSColor.systemRedColor()
SEMIBOLD, REGULAR = AppKit.NSFontWeightSemibold, AppKit.NSFontWeightRegular
# the buttons: glass capsules on macOS 26, else rounded ones (PyObjC has 26's constants on any macOS: ask the class)
BEZEL, SIZE = (AppKit.NSBezelStyleGlass, AppKit.NSControlSizeExtraLarge) if GLASS is not None else \
    (AppKit.NSBezelStyleRounded, AppKit.NSControlSizeLarge)


def text(s, size=14, weight=REGULAR, color=None, mono=False, sel=False, width=None, digits=False):
    """A label of untrusted text (QR payloads, Thunder's answers): plain, never a link, at most 400 characters;
    wrapped at width (points; None: one line). sel: selectable, as the values a user may want to copy."""
    s = s if len(s) <= 400 else s[:400] + "…"
    f = AppKit.NSTextField.wrappingLabelWithString_(s) if width else AppKit.NSTextField.labelWithString_(s)
    f.setFont_(AppKit.NSFont.monospacedSystemFontOfSize_weight_(size, weight) if mono else
               AppKit.NSFont.monospacedDigitSystemFontOfSize_weight_(size, weight) if digits else
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
    """A verdict's round badge: its tone's fill; the head's (line set) has a 1px edge, a lit top and its number in
    its corner when there are several codes, as their badges on the image. The glyph or spinner is a subview."""
    fill = line = None
    n, badge = 0, None

    def isFlipped(self):
        return True

    def drawRect_(self, _):
        b = self.bounds()
        oval = AppKit.NSBezierPath.bezierPathWithOvalInRect_(AppKit.NSInsetRect(b, .5, .5))
        self.fill.setFill()
        oval.fill()
        if self.line:
            self.line.setStroke()
            oval.setLineWidth_(1)
            oval.stroke()
            r = AppKit.NSInsetRect(b, 1, 1)
            lit_top(r, r.size.width / 2, LIT)
        if self.n:
            self.badge.setFill()
            AppKit.NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(0, 0, 16, 16)).fill()
            s = AppKit.NSAttributedString.alloc().initWithString_attributes_(str(self.n), {
                AppKit.NSFontAttributeName: AppKit.NSFont.systemFontOfSize_weight_(11, AppKit.NSFontWeightBold),
                AppKit.NSForegroundColorAttributeName: AppKit.NSColor.whiteColor()})
            z = s.size()
            s.drawAtPoint_(((16 - z.width) / 2, (16 - z.height) / 2))


def disc(d, fill, line, glyph, live, n=0, badge=None, says=""):
    v = fixed(Disc.alloc().initWithFrame_(NSMakeRect(0, 0, d, d)), d, d)
    v.fill, v.line, v.n, v.badge = fill, line, n, badge
    if glyph is None:  # still asking: a white spinner
        icon = AppKit.NSProgressIndicator.alloc().initWithFrame_(NSMakeRect(0, 0, 16, 16))
        icon.setStyle_(AppKit.NSProgressIndicatorStyleSpinning)
        icon.setControlSize_(AppKit.NSControlSizeSmall)
        icon.setAppearance_(AppKit.NSAppearance.appearanceNamed_(AppKit.NSAppearanceNameDarkAqua))
        fixed(icon, 16, 16)
        if live:
            icon.startAnimation_(None)
    else:
        icon = AppKit.NSImageView.imageViewWithImage_(symbol(glyph, 20 if line else 10, AppKit.NSFontWeightSemibold if line
                                                             else AppKit.NSFontWeightBold))
        icon.setContentTintColor_(AppKit.NSColor.whiteColor())
        icon.setTranslatesAutoresizingMaskIntoConstraints_(False)
    v.addSubview_(icon)
    icon.centerXAnchor().constraintEqualToAnchor_(v.centerXAnchor()).setActive_(True)
    icon.centerYAnchor().constraintEqualToAnchor_(v.centerYAnchor()).setActive_(True)
    v.setAccessibilityElement_(True)
    v.setAccessibilityRole_(AppKit.NSAccessibilityImageRole)
    v.setAccessibilityLabel_(says)
    return v


class Band(AppKit.NSView):
    """A table's box inside: the rows the image differs on (bad, grid rows) tinted red behind the grid."""
    grid, bad = None, ()

    def isFlipped(self):
        return True

    def drawRect_(self, _):
        g = self.grid
        BAND.setFill()
        for i in self.bad:  # CSS: the row's padding 9, radius 16, across the box inside its padding 6
            cells = [self.convertRect_fromView_(v.bounds(), v) for c in range(g.numberOfColumns())
                     if (v := g.cellAtColumnIndex_rowIndex_(c, i).contentView()) is not None]
            top, bottom = min(r.origin.y for r in cells), max(r.origin.y + r.size.height for r in cells)
            AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                NSMakeRect(6, top - 9, self.bounds().size.width - 12, bottom - top + 18), 16, 16).fill()


class Flat(AppKit.NSView):
    """The receipt's card: opaque, as its glass would look over nothing (FLAT), corners of 30."""

    def isFlipped(self):
        return True

    def drawRect_(self, _):
        b = self.bounds()
        shape = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(b, 30, 30)
        for c in FLAT[:2]:
            c.setFill()
            shape.fill()
        lit_top(AppKit.NSInsetRect(b, 1, 1), 29, FLAT[2])
        FLAT[3].setStroke()
        edge = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(AppKit.NSInsetRect(b, .5, .5), 29.5, 29.5)
        edge.setLineWidth_(1)
        edge.stroke()


class _Keys(NSObject):
    """The key field's delegate: Return saves the key; Esc does what it does on the overlay (closes the capture),
    as the Qt field let it through to it."""

    def initWithCard_(self, card):
        self = objc.super(_Keys, self).init()
        self.card = card
        return self

    def control_textView_doCommandBySelector_(self, control, view, sel):
        if sel == "cancelOperation:":
            self.card.later(self.card.escape)
            return True
        if sel == "insertNewline:":
            self.card.later(partial(self.card.key, control.stringValue()))
            return True
        return False


class KeyCapsule(AppKit.NSBox):
    """The key field's capsule, all of it the field's, as the Qt field's padding was: a press on its edge goes to the
    field (to its editor while typing), the caret to the nearest place."""
    field = None

    def hitTest_(self, pt):
        hit = objc.super(KeyCapsule, self).hitTest_(pt)
        if hit is None or hit.isDescendantOf_(self.field):
            return hit
        return self.field.currentEditor() or self.field


class SlipCard:
    """The card, one per overlay: made once (hidden), rebuilt in place by show(), put beside the selection by
    place(). host: the overlay's NSView (native.host), flipped, in the overlay's points; pressed: its Surface's
    (Overlay.chrome_pressed). What the user does goes back through callbacks, each called after the event that asked
    (later; none once the card is closed): retry(payloads) (ตรวจใหม่: drop their answers, show again), copy(text) (คัดลอก:
    Overlay.copy_card puts what the codes say on the clipboard), receipt() (บันทึกใบตรวจ: Overlay.save_receipt), key(text)
    (the key box's Return or button: Overlay.use_key), escape() (Esc in the key field: what Esc does on the overlay)."""

    def __init__(self, host, pressed, retry, copy, receipt, key, escape):
        self.host, self.retry, self.copy, self.receipt, self.key, self.escape = host, retry, copy, receipt, key, escape
        self.keep, self.spinners, self.m, self.content, self.w, self.h = [], [], None, None, 420, 0
        self.root = Surface.alloc().initWithPressed_(pressed)
        self.root.setHidden_(True)
        self.root.setAccessibilityElement_(True)
        self.root.setAccessibilityRole_(AppKit.NSAccessibilityGroupRole)
        self.body = AppKit.NSView.alloc().init()
        pin(glass(self.body, 30), self.root)
        host.addSubview_(self.root)
        self.keys = _Keys.alloc().initWithCard_(self)
        self.field = AppKit.NSSecureTextField.alloc().init()  # one for the card's life: what's typed stays
        self.field.setPlaceholderString_("วางคีย์ที่นี่")
        self.field.setDelegate_(self.keys)
        self.capsule = self.key_field(self.field)

    # --- what the overlay calls
    def show(self, m):
        """Rebuild from model() (None or no entries: gone). Placed (and shown) by place()."""
        had = self.focus()
        ed = self.field.currentEditor()
        caret = ed.selectedRange() if ed is not None else None
        self.m = m if m and m.entries else None
        for s in self.spinners:
            s.stopAnimation_(None)
        if self.content is not None:
            self.content.removeFromSuperview()
        self.keep, self.spinners, self.content = [], [], None
        if not any(e.key for e in (self.m.entries if self.m else ())):
            self.field.setStringValue_("")  # its box gone: what was typed with it (the Qt card's went too)
        if not self.m:
            return self.hide(had)
        foot = self.footer(self.m)
        self.w = self.width(self.m, foot)
        self.content = self.build(self.m, self.w, foot, True)
        pin(self.content, self.body)
        self.h = math.ceil(self.content.fittingSize().height)
        f = self.root.frame()
        self.move(f.origin.x, f.origin.y)
        self.root.setAccessibilityLabel_(self.m.entries[0].head if len(self.m.entries) == 1 else f"QR {len(self.m.entries)} รายการ")
        self.root.layoutSubtreeIfNeeded()
        win = self.host.window()
        if had == "key" and self.field.window() is not None and not self.root.isHidden():
            win.makeFirstResponder_(self.field)  # typing on
            if caret is not None and self.field.currentEditor() is not None:
                self.field.currentEditor().setSelectedRange_(caret)
        elif had and win is not None:  # the field or label with the keys went: back to the overlay, as Qt's focus
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
        for s in self.spinners:
            s.stopAnimation_(None)
        self.root.removeFromSuperview()
        self.keep, self.spinners, self.m = [], [], None
        self.root.pressed = self.keys.card = None  # no cycle through AppKit objects: the overlay can go (Chrome.close)

    def busy(self):  # a press on the card is held (a button tracking it): rebuilt now, the button and its click would go
        e, win = AppKit.NSApp.currentEvent(), self.root.window()
        return e is not None and win is not None and e.window() == win and not self.root.isHidden() \
            and e.type() in (AppKit.NSEventTypeLeftMouseDown, AppKit.NSEventTypeLeftMouseDragged) \
            and AppKit.NSPointInRect(self.root.convertPoint_fromView_(e.locationInWindow(), None), self.root.bounds())

    def focus(self):  # what of the card has the keys: "key" (its key field), "label" (a selected label), or None
        win = self.root.window()
        fr = win.firstResponder() if win is not None else None
        owner = fr.delegate() if isinstance(fr, AppKit.NSText) else fr
        if owner is self.field:
            return "key"
        return "label" if isinstance(owner, AppKit.NSView) and owner.isDescendantOf_(self.root) else None

    def keeps_keys(self):
        """The press being handled is on the key box's capsule, or on the label being selected (a second click, a
        drag, its right-click Copy): they have the keys, or take them. Taken away, the label's editor (the very view
        the press goes to) would leave the window."""
        e, win = AppKit.NSApp.currentEvent(), self.root.window()
        if e is None or win is None:
            return False
        fr = win.firstResponder()
        owner = fr.delegate() if isinstance(fr, AppKit.NSText) else None
        views = [self.capsule] + [owner] * (isinstance(owner, AppKit.NSView) and owner.isDescendantOf_(self.root))
        return any(v.window() is not None and not v.isHiddenOrHasHiddenAncestor() and
                   AppKit.NSPointInRect(v.convertPoint_fromView_(e.locationInWindow(), None), v.bounds()) for v in views)

    def later(self, fn):  # after the event that asked (an action may rebuild the card, the control that sent it with
        # it), on Qt's queue as chrome's menus: an exception there is printed, not the app's end, and the receipt's
        # dialog runs its loop as from a click. Nothing once the card is closed.
        QTimer.singleShot(0, lambda: self.root.superview() is not None and fn())

    def receipt_png(self, scale, appearance=None):
        """The card as the receipt shows it -> PNG bytes: opaque (FLAT), no buttons (cut straight under the last row,
        8 below it, as the Qt card was grabbed above its footer), in scale px per point (the overlay's k: the
        screenshot's). appearance: an NSAppearance name (match the receipt's ground), None: the card's own."""
        content = self.build(self.m, self.w, None, False)
        root = Flat.alloc().initWithFrame_(NSMakeRect(0, 0, self.w, 1))
        root.setAppearance_(AppKit.NSAppearance.appearanceNamed_(appearance) if appearance else self.root.effectiveAppearance())
        content.setTranslatesAutoresizingMaskIntoConstraints_(False)
        root.addSubview_(content)
        content.topAnchor().constraintEqualToAnchor_(root.topAnchor()).setActive_(True)
        content.leadingAnchor().constraintEqualToAnchor_(root.leadingAnchor()).setActive_(True)
        h = math.ceil(content.fittingSize().height)
        root.setFrame_(NSMakeRect(0, 0, self.w, h + 40))  # its bottom corners below the cut
        root.layoutSubtreeIfNeeded()
        rep = AppKit.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
            None, round(self.w * scale), round(h * scale), 8, 4, True, False, AppKit.NSCalibratedRGBColorSpace, 0, 32)
        rep = rep.bitmapImageRepByRetaggingWithColorSpace_(AppKit.NSColorSpace.sRGBColorSpace())
        rep.setSize_((self.w, h))  # points: drawn at scale
        root.cacheDisplayInRect_toBitmapImageRep_(NSMakeRect(0, 0, self.w, h), rep)
        return bytes(rep.representationUsingType_properties_(AppKit.NSBitmapImageFileTypePNG, {}))

    # --- building it
    def width(self, m, foot):  # 540 with a table (a ref that won't wrap), else 420; what won't wrap; the screen less 20
        need = [foot.fittingSize().width] if foot else []
        need += [self.hero(e, m.dense).fittingSize().width for e in m.entries if e.amount is not None]
        need += [self.key_row(None).fittingSize().width + 100 + 28 for e in m.entries if e.key]  # the field: 100
        return min(max(540 if m.wide else 420, math.ceil(max(need, default=0)) + 16), int(self.host.bounds().size.width) - 20)

    def build(self, m, w, foot, live):  # the card's column, w wide, foot (its buttons) under; live: on screen, else the receipt's
        inner, views = w - 16, []
        for e in m.entries:
            if e.n > 1:  # a hairline between codes
                line = AppKit.NSBox.alloc().init()
                line.setBoxType_(AppKit.NSBoxSeparator)
                views.append(line)
            views += self.entry(e, inner, m.dense, live)
        if foot:
            views.append(foot)
        col = stack(views, vertical=True, spacing=8, insets=(8, 8, 8, 8))
        fixed(col, w)
        for v in views:  # each the card's width inside its margins
            v.setTranslatesAutoresizingMaskIntoConstraints_(False)
            v.widthAnchor().constraintEqualToConstant_(inner).setActive_(True)
        # laid out once: a box measures 3 short before its first layout, so the card (h) and the receipt's cut would
        # be; from then on fittingSize is the height it lays out at
        col.setFrame_(NSMakeRect(0, 0, w, math.ceil(col.fittingSize().height)))
        col.layoutSubtreeIfNeeded()
        return col

    def entry(self, e, inner, dense, live):  # a code's views: head, warn, hero amount, table or rows, key box
        badge = srgb(*tone_rgb(e.tone))
        d = disc(44, FILL[e.tone], LINE[e.tone], HEAD.get(e.glyph) if e.glyph else None, live, e.n, badge,
                 e.head + (f" · QR ที่ {e.n}" if e.n else ""))
        if e.glyph is None:
            self.spinners += [v for v in d.subviews() if isinstance(v, AppKit.NSProgressIndicator)] * live
        at = text(f"{e.time:%H:%M}", 12, color=FAINT, digits=True) if e.time else None
        room = inner - 28 - 44 - 14 - (math.ceil(at.fittingSize().width) + 14 if at else 0)
        words = stack([text(e.head, 17, SEMIBOLD, width=room)] +
                      [text(e.sub, 14, color=SECONDARY, sel=e.sub_sel, width=room)] * bool(e.sub), vertical=True, spacing=2)
        words.setContentHuggingPriority_forOrientation_(1, AppKit.NSLayoutConstraintOrientationHorizontal)
        row = stack([d, words] + [at] * bool(at), spacing=14, insets=(0, 14, 0, 14))
        row.setDistribution_(AppKit.NSStackViewDistributionFill)
        views = [margins(row, 6 if dense else 14, 4 if dense else 10)]
        if e.warn:
            views.append(inset(text(e.warn, 13, color=RED, width=inner - 28), left=14, right=14))
        if e.amount is not None:  # the hero, as big as on the slip
            views.append(self.hero(e, dense))
        if e.table:  # the image beside the bank, field by field; a row the image differs on, tinted red
            views.append(self.table(e.table, inner, dense))
        elif e.rows:  # what the code says
            views.append(self.code_rows(e.rows, inner))
        if e.key:  # one box for every slip waiting on it: saved as on the settings page, then asked again
            views.append(self.key_box(inner, live))
        return views

    def hero(self, e, dense):
        big = text(e.amount, 32 if dense else 44, SEMIBOLD, sel=True, digits=True)
        return margins(stack([big, text("บาท", 17, color=SECONDARY)], spacing=8, insets=(0, 14, 0, 14),
                             align=AppKit.NSLayoutAttributeFirstBaseline), 0, 6)

    def table(self, table, inner, dense):
        c0 = max([88] + [math.ceil(text(k, 13).fittingSize().width) for k, *_ in table])
        c1 = (inner - 36 - c0 - 22 - 36) / 2  # the image's and the bank's columns share what's left
        rows = [[AppKit.NSGridCell.emptyContentView(), text("ในภาพสลิป", 12, color=FAINT),
                 text("ธนาคารยืนยัน", 12, color=FAINT), AppKit.NSGridCell.emptyContentView()]]
        for k, seen, shown, under, mark in table:
            mono = k.startswith("บัญชี") or k == "เลขอ้างอิง"  # numbers, as the slip prints them (SF Mono: a size less)
            cell = stack([text(shown, 13 if mono else 14, SEMIBOLD if k in ("ยอดเงิน", "ผู้โอน", "ผู้รับ") else REGULAR, mono=mono, sel=True,
                               width=c1)] + [text(under, 12, color=FAINT, sel=True, width=c1)] * bool(under),
                         vertical=True, spacing=1)
            rows.append([text(k, 13, color=FAINT, width=c0),
                         text(seen or "–", 13 if mono else 14, color=RED if mark == "✗" else SECONDARY, mono=mono, sel=bool(seen), width=c1),
                         cell, disc(22, MARK_FILL[mark], None, MARK[MARKS[mark][0]], False, says=SAYS[mark])
                         if mark else AppKit.NSGridCell.emptyContentView()])
        g = AppKit.NSGridView.gridViewWithViews_(rows)
        g.setColumnSpacing_(12)
        g.setRowSpacing_(8 if dense else 18)
        g.setYPlacement_(AppKit.NSGridCellPlacementTop)
        g.setXPlacement_(AppKit.NSGridCellPlacementLeading)
        for i, cw in enumerate((c0, c1, c1, 22)):
            g.columnAtIndex_(i).setWidth_(cw)
        band = Band.alloc().init()
        band.grid, band.bad = g, [i for i, r in enumerate(table, 1) if r[4] == "✗"]
        pin(g, band, (14, 18, 15, 18))
        return self.box(band)

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

    def key_field(self, field):  # a capsule like the button beside it, the field across it
        field.setBezeled_(False)
        field.setBordered_(False)
        field.setDrawsBackground_(False)
        field.setFocusRingType_(AppKit.NSFocusRingTypeNone)
        field.setFont_(AppKit.NSFont.monospacedSystemFontOfSize_weight_(13, REGULAR))
        field.setTranslatesAutoresizingMaskIntoConstraints_(False)
        cap = KeyCapsule.alloc().init()
        cap.field = field
        cap.setBoxType_(AppKit.NSBoxCustom)
        cap.setTitlePosition_(AppKit.NSNoTitle)
        cap.setCornerRadius_(18)
        cap.setFillColor_(FIELD[0])
        cap.setBorderColor_(FIELD[1])
        cap.setBorderWidth_(1)
        cap.setContentViewMargins_((0, 0))
        fixed(cap, None, 36)
        cap.contentView().addSubview_(field)
        field.leadingAnchor().constraintEqualToAnchor_constant_(cap.contentView().leadingAnchor(), 15).setActive_(True)
        field.trailingAnchor().constraintEqualToAnchor_constant_(cap.contentView().trailingAnchor(), -15).setActive_(True)
        field.centerYAnchor().constraintEqualToAnchor_(cap.contentView().centerYAnchor()).setActive_(True)
        cap.setContentHuggingPriority_forOrientation_(1, AppKit.NSLayoutConstraintOrientationHorizontal)
        return cap

    def key_row(self, cap):  # the field's capsule (None: just the button, to measure) and its button
        if cap is None or cap is self.capsule:
            go = self.button("บันทึกและตรวจ", None, 2, lambda: self.key(self.field.stringValue()))
        else:  # the receipt's: no glass to draw, a capsule of the accent colour
            go = fixed(box(inset(text("บันทึกและตรวจ", 13, AppKit.NSFontWeightMedium, AppKit.NSColor.whiteColor()),
                                 0, 16, 0, 16), 18, AppKit.NSColor.controlAccentColor()), None, 36)
        row = stack([cap] * bool(cap) + [go], spacing=8)
        row.setDistribution_(AppKit.NSStackViewDistributionFill)
        return row

    def key_box(self, inner, live):
        if live:
            self.capsule.removeFromSuperview()
            cap = self.capsule
        else:  # the receipt's: dots for what's typed, as the Qt grab had them
            f = AppKit.NSSecureTextField.alloc().init()
            f.setStringValue_(self.field.stringValue())
            f.setPlaceholderString_("วางคีย์ที่นี่")
            cap = self.key_field(f)
        row = self.key_row(cap)
        row.setTranslatesAutoresizingMaskIntoConstraints_(False)
        row.widthAnchor().constraintEqualToConstant_(inner - 28).setActive_(True)
        v = stack([inset(text("Thunder API key", 12, color=FAINT), left=4), row,
                   inset(text("เก็บไว้ในเครื่องนี้เท่านั้น · แก้ได้ที่หน้าตั้งค่า", 12, color=FAINT, width=inner - 32), left=4)],
                  vertical=True, spacing=10, insets=(14, 14, 14, 14))
        return self.box(v)

    def box(self, view):  # a box in the card: radius 22, a faint wash and line
        b = box(view, 22, BOX[0], border=True)
        b.setBorderColor_(BOX[1])
        b.setBorderWidth_(1)
        return b

    def button(self, title, glyph, prominence, fn):  # a glass capsule; no focus: the keys stay the overlay's
        t = target(lambda _: self.later(fn), self.keep)
        b = AppKit.NSButton.buttonWithTitle_image_target_action_(title, symbol(glyph), t, "fire:") if glyph else \
            AppKit.NSButton.buttonWithTitle_target_action_(title, t, "fire:")
        b.setBezelStyle_(BEZEL)
        b.setControlSize_(SIZE)
        if b.respondsToSelector_("setTintProminence:"):
            b.setTintProminence_(prominence)  # NSTintProminence: 1 none, 2 primary, 3 secondary
        b.setImagePosition_(AppKit.NSImageLeading)
        b.setRefusesFirstResponder_(True)
        return b

    def footer(self, m):  # ตรวจใหม่, คัดลอก, บันทึกใบตรวจ at the card's trailing end; None: no buttons
        buttons = []
        if m.retry:
            buttons.append(self.button("ตรวจใหม่", "arrow.clockwise", 3, lambda p=list(m.retry): self.retry(p)))
        if m.copy is not None:
            buttons.append(self.button("คัดลอก", "doc.on.doc", 1, lambda t=m.copy: self.copy(t)))
        if m.receipt:
            buttons.append(self.button("บันทึกใบตรวจ", "square.and.arrow.down", 2, self.receipt))
        if not buttons:
            return None
        foot = stack([], spacing=8, insets=(4, 6, 6, 6))
        for b in buttons:
            foot.addView_inGravity_(b, AppKit.NSStackViewGravityTrailing)
        return foot
