"""The settings: a native AppKit window laid out as System Settings (a sidebar with the app, its capture keys and
how things stand; the settings in grouped rows). Main keeps the state and the logic; this shows it and hands it
what's changed. The capture keys are recorded in their row, as a Mac's Keyboard Shortcuts are."""
import os

import AppKit
import objc
from Foundation import NSMakeRect, NSMakeSize, NSObject

from snaplens.config import ASSETS, TRAY, VERSION
from snaplens.system import mac
from snaplens.system.autostart import USABLE, autostart, login_items, waiting
from snaplens.system.hotkey import MODS, chord, key_rule, keyname
from snaplens.ui.native import box, dynamic, fixed, label, stack, target, tile

FLAGS = {"cmd": 1 << 20, "shift": 1 << 17, "alt": 1 << 19, "ctrl": 1 << 18}  # NSEventModifierFlag*, by MODS' names
SIDEBAR, CONTENT, HEIGHT = 230, 500, 420


class _Delegate(NSObject):  # the window's: its close button hides it (and Main says once where the app went)
    def initWithFn_(self, fn):
        self = objc.super(_Delegate, self).init()
        self.fn = fn
        return self

    def windowShouldClose_(self, window):
        self.fn()
        return False

    def windowDidResignKey_(self, note):
        self.fn(resign=True)

    def toolbarDefaultItemIdentifiers_(self, toolbar):  # the title over the settings, not over the sidebar
        return [AppKit.NSToolbarSidebarTrackingSeparatorItemIdentifier]

    def toolbarAllowedItemIdentifiers_(self, toolbar):
        return self.toolbarDefaultItemIdentifiers_(toolbar)

    def toolbar_itemForItemIdentifier_willBeInsertedIntoToolbar_(self, toolbar, ident, insert):
        return None


GROUP = dynamic((1, 1, 1, .05), (1, 1, 1, .9))  # System Settings' grouped rows
CAP = dynamic((1, 1, 1, .1), (1, 1, 1, 1))  # a keycap


class Row:  # a grouped row: its tile, a title and a line under it (hidden when empty), its controls at the end
    def __init__(self, symbol, rgb, title, *controls):
        self.title, self.sub = label(title), label("", 11, color=AppKit.NSColor.secondaryLabelColor())
        words = stack([self.title, self.sub], vertical=True, spacing=1)
        words.setContentHuggingPriority_forOrientation_(1, AppKit.NSLayoutConstraintOrientationHorizontal)
        words.setContentCompressionResistancePriority_forOrientation_(250, AppKit.NSLayoutConstraintOrientationHorizontal)
        for c in controls:  # the words take the room between: the controls at the row's end
            c.setContentHuggingPriority_forOrientation_(750, AppKit.NSLayoutConstraintOrientationHorizontal)
        self.view = stack([tile(symbol, rgb), words, *controls], spacing=10, insets=(9, 10, 9, 10))
        self.view.setDistribution_(AppKit.NSStackViewDistributionFill)
        self.view.heightAnchor().constraintGreaterThanOrEqualToConstant_(46).setActive_(True)

    def say(self, text, bad=False):
        self.sub.setStringValue_(text)
        self.sub.setTextColor_(AppKit.NSColor.systemRedColor() if bad else AppKit.NSColor.secondaryLabelColor())
        self.sub.setHidden_(not text)


def group(rows):  # rows in one rounded box, hairlines between them (from the words, as System Settings')
    views = []
    for i, r in enumerate(rows):
        if i:
            line = AppKit.NSBox.alloc().init()
            line.setBoxType_(AppKit.NSBoxSeparator)
            views.append(stack([line], insets=(0, 44, 0, 0), align=AppKit.NSLayoutAttributeHeight))
        views.append(r.view)
    s = stack(views, vertical=True, spacing=0)
    for v in views:  # each row the group's width
        v.setTranslatesAutoresizingMaskIntoConstraints_(False)
        v.widthAnchor().constraintEqualToAnchor_(s.widthAnchor()).setActive_(True)
    return box(s, 10, GROUP, border=True)


def button(title, fn, keep):
    b = AppKit.NSButton.buttonWithTitle_target_action_(title, target(fn, keep), "fire:")
    b.setBezelStyle_(AppKit.NSBezelStyleRounded)
    return b


class SettingsWindow:
    """The window. main: Main (its key, mode, states() and the methods that change them)."""

    def __init__(self, main):
        self.main, self.keep, self.recording, self.monitor = main, [], False, None
        self.down, self.chord = {}, ""
        w = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, SIDEBAR + CONTENT, HEIGHT),
            AppKit.NSWindowStyleMaskTitled | AppKit.NSWindowStyleMaskClosable | AppKit.NSWindowStyleMaskMiniaturizable
            | AppKit.NSWindowStyleMaskFullSizeContentView, AppKit.NSBackingStoreBuffered, False)
        w.setReleasedWhenClosed_(False)
        w.setTitle_("ตั้งค่า")
        w.setTitlebarAppearsTransparent_(True)
        self.delegate = _Delegate.alloc().initWithFn_(self.closing)
        w.setDelegate_(self.delegate)
        bar = AppKit.NSToolbar.alloc().initWithIdentifier_("snaplens.settings")
        bar.setDelegate_(self.delegate)
        bar.setDisplayMode_(AppKit.NSToolbarDisplayModeIconOnly)
        w.setToolbar_(bar)
        w.setToolbarStyle_(AppKit.NSWindowToolbarStyleUnified)
        split = AppKit.NSSplitViewController.alloc().init()
        for vc, item in ((self.sidebar(), AppKit.NSSplitViewItem.sidebarWithViewController_),
                         (self.content(), AppKit.NSSplitViewItem.splitViewItemWithViewController_)):
            it = item(vc)
            it.setCanCollapse_(False)
            split.addSplitViewItem_(it)
        split.splitViewItems()[0].setMinimumThickness_(SIDEBAR)
        split.splitViewItems()[0].setMaximumThickness_(SIDEBAR)
        w.setContentViewController_(split)
        w.setContentSize_(NSMakeSize(SIDEBAR + CONTENT, HEIGHT))
        w.setContentMinSize_(NSMakeSize(SIDEBAR + CONTENT, HEIGHT))
        w.setContentMaxSize_(NSMakeSize(SIDEBAR + CONTENT, HEIGHT))
        self.window = w

    # --- the two panes
    def sidebar(self):
        icon = AppKit.NSImageView.imageViewWithImage_(AppKit.NSImage.alloc().initWithContentsOfFile_(
            os.path.join(ASSETS, "icons", "app-256.png")))
        fixed(icon, 64, 64)
        self.caps = stack([], spacing=6)
        self.caption = label("", 11, color=AppKit.NSColor.secondaryLabelColor())
        self.states = stack([], vertical=True, spacing=10)
        top = stack([icon, label("Snaplens", 17, AppKit.NSFontWeightBold),
                     label(f"เวอร์ชัน {VERSION}", 11, color=AppKit.NSColor.secondaryLabelColor()),
                     stack([], insets=(4, 0, 0, 0)),
                     label("คีย์ลัดแคปหน้าจอ", 11, AppKit.NSFontWeightSemibold, AppKit.NSColor.secondaryLabelColor()),
                     self.caps, self.caption], vertical=True, spacing=6, align=AppKit.NSLayoutAttributeCenterX)
        root = AppKit.NSView.alloc().init()
        for v in (top, self.states):
            v.setTranslatesAutoresizingMaskIntoConstraints_(False)
            root.addSubview_(v)
        top.topAnchor().constraintEqualToAnchor_constant_(root.safeAreaLayoutGuide().topAnchor(), 16).setActive_(True)
        top.centerXAnchor().constraintEqualToAnchor_(root.centerXAnchor()).setActive_(True)
        self.states.leadingAnchor().constraintEqualToAnchor_constant_(root.leadingAnchor(), 20).setActive_(True)
        self.states.trailingAnchor().constraintLessThanOrEqualToAnchor_constant_(root.trailingAnchor(), -12).setActive_(True)
        self.states.bottomAnchor().constraintEqualToAnchor_constant_(root.bottomAnchor(), -20).setActive_(True)
        vc = AppKit.NSViewController.alloc().init()
        vc.setView_(root)
        return vc

    def content(self):
        self.key_label = label("", 13, color=AppKit.NSColor.secondaryLabelColor())
        self.key_btn = button("เปลี่ยน…", lambda _: self.cancel_record() if self.recording else self.record(), self.keep)
        self.key_row = Row("keyboard", (47, 155, 224), "คีย์ลัดแคปหน้าจอ", self.key_label, self.key_btn)
        self.mode = AppKit.NSPopUpButton.alloc().initWithFrame_pullsDown_(NSMakeRect(0, 0, 140, 24), False)
        self.mode.addItemsWithTitles_(self.main.MODE_NAMES)
        self.mode.setTarget_(target(lambda b: self.main.pick_mode(b.indexOfSelectedItem()), self.keep))
        self.mode.setAction_("fire:")
        lang = Row("globe", (18, 169, 138), "ภาษาที่อ่าน", self.mode)
        lang.say("ภาษาของข้อความที่จะให้อ่านตอนแคป")
        self.boot = AppKit.NSSwitch.alloc().init()
        self.boot.setTarget_(target(self.toggle_boot, self.keep))
        self.boot.setAction_("fire:")
        self.boot.setEnabled_(USABLE)
        self.boot_row = Row("power", (122, 130, 148), "เปิดเมื่อเข้าสู่ระบบ", self.boot)
        views = []
        for title, rows in (("การแคป", (self.key_row, lang)), ("ทั่วไป", (self.boot_row,))):
            head = label(title, 13, AppKit.NSFontWeightBold)
            views += [stack([head], insets=(0, 4, 0, 0)), group(rows)]
        body = stack(views, vertical=True, spacing=10, align=AppKit.NSLayoutAttributeWidth)
        for i in range(1, len(views) - 1, 2):  # more room above a section's title than under it
            body.setCustomSpacing_afterView_(22, views[i])
        root = AppKit.NSView.alloc().init()
        body.setTranslatesAutoresizingMaskIntoConstraints_(False)
        root.addSubview_(body)
        body.topAnchor().constraintEqualToAnchor_constant_(root.safeAreaLayoutGuide().topAnchor(), 14).setActive_(True)
        body.leadingAnchor().constraintEqualToAnchor_constant_(root.leadingAnchor(), 24).setActive_(True)
        body.trailingAnchor().constraintEqualToAnchor_constant_(root.trailingAnchor(), -24).setActive_(True)
        for v in views:  # every group and title the pane's width
            v.setTranslatesAutoresizingMaskIntoConstraints_(False)
            v.widthAnchor().constraintEqualToAnchor_(body.widthAnchor()).setActive_(True)
        vc = AppKit.NSViewController.alloc().init()
        vc.setView_(root)
        return vc

    # --- what it shows
    def refresh(self):  # from Main's state: the keys, the mode, the switch, how things stand
        m = self.main
        if not self.recording:
            self.show_keys(m.key)
            self.key_row.say("")
        self.mode.selectItemAtIndex_(m.mode)
        self.boot.setState_(AppKit.NSControlStateValueOn if autostart() else AppKit.NSControlStateValueOff)
        if not USABLE:  # run from source: no app to start
            self.boot_row.say("ใช้ได้เมื่อเปิดจากแอปที่ติดตั้ง")
        elif waiting():  # on, but Login Items has it switched off
            self.boot_row.say("อนุญาต Snaplens ใน การตั้งค่าระบบ > ทั่วไป > รายการเข้าสู่ระบบ", bad=True)
        else:
            self.boot_row.say(f"เริ่มเองแล้วรออยู่ที่{TRAY}")
        self.caption.setStringValue_(f"หรือเลือก แคปหน้าจอ จากไอคอนที่{TRAY}")
        for v in list(self.states.arrangedSubviews()):
            self.states.removeView_(v)
        for title, line, ok in m.states():
            dot = fixed(AppKit.NSView.alloc().init(), 8, 8)
            dot.setWantsLayer_(True)
            dot.layer().setCornerRadius_(4)
            dot.layer().setBackgroundColor_((AppKit.NSColor.systemGreenColor() if ok else AppKit.NSColor.tertiaryLabelColor()).CGColor())
            words = stack([label(title, 12, AppKit.NSFontWeightMedium), label(line, 11, color=AppKit.NSColor.secondaryLabelColor())],
                          vertical=True, spacing=1)
            self.states.addArrangedSubview_(stack([dot, words], spacing=8, align=AppKit.NSLayoutAttributeFirstBaseline))

    def toggle_boot(self, s):  # the user's own flip: the only place Login Items is opened, if macOS waits on it there
        autostart(bool(s.state()))
        if s.state() and waiting():
            login_items()
        self.refresh()

    def show_keys(self, k):  # the sidebar's keycaps and the row's ⌃⌥S
        names = keyname(k).split("+") if k else []
        self.key_label.setStringValue_("".join(names) if k else "กดคีย์ที่ต้องการ…")
        for v in list(self.caps.arrangedSubviews()):
            self.caps.removeView_(v)
        for n in names or ["…"]:
            cap = label(n, 15, AppKit.NSFontWeightMedium)
            cap.setAlignment_(AppKit.NSTextAlignmentCenter)
            b = box(stack([cap], insets=(4, 9, 4, 9), align=AppKit.NSLayoutAttributeCenterY), 7, CAP, border=True)
            b.widthAnchor().constraintGreaterThanOrEqualToConstant_(32).setActive_(True)
            self.caps.addArrangedSubview_(b)

    def show(self):
        if not self.window.isVisible():
            self.window.center()
        self.main.refresh()
        mac.activate()
        self.window.makeKeyAndOrderFront_(None)
        self.window.makeFirstResponder_(None)  # no focus ring on a button till Tab

    def hide(self):
        self.cancel_record()
        self.window.orderOut_(None)

    def visible(self):
        return bool(self.window.isVisible())

    def closing(self, resign=False):  # the close button: hidden, Main says once where it went; a resign ends a recording
        self.cancel_record()
        if not resign:
            self.window.orderOut_(None)
            self.main.hint_tray()

    # --- the capture keys, recorded in their row: held keys show as they go down; once all are up the chord is
    # checked (key_rule) and saved, or why not is said and it records again. Esc cancels. The old keys are unbound
    # meanwhile, and nothing pressed reaches the app (⌘Q, ⌘W) while it records.
    def record(self):
        self.main.carbon.unbind()
        self.recording, self.down, self.chord = True, {}, ""
        self.key_btn.setTitle_("ยกเลิก")
        self.show_keys("")
        self.key_row.say("ต้องมี ⌃ หรือ ⌘ คู่กับปุ่มอื่น หรือปุ่ม F ปุ่มเดียว · Esc ยกเลิก")
        mask = AppKit.NSEventMaskKeyDown | AppKit.NSEventMaskKeyUp | AppKit.NSEventMaskFlagsChanged
        self.monitor = AppKit.NSEvent.addLocalMonitorForEventsMatchingMask_handler_(mask, self.on_event)

    def cancel_record(self, saved=False):
        if not self.recording:
            return
        AppKit.NSEvent.removeMonitor_(self.monitor)
        self.recording, self.monitor = False, None
        self.key_btn.setTitle_("เปลี่ยน…")
        if not saved:
            self.main.bind_keys()  # the old keys back
        self.main.refresh()

    def on_event(self, e):
        code, kind = e.keyCode(), e.type()
        name = mac.KEYS.get(code, "")
        if kind == AppKit.NSEventTypeFlagsChanged:
            if name not in FLAGS:
                return None
            kind = AppKit.NSEventTypeKeyDown if e.modifierFlags() & FLAGS[name] else AppKit.NSEventTypeKeyUp
        elif e.isARepeat():
            return None
        if kind == AppKit.NSEventTypeKeyDown:
            if name == "esc":
                self.cancel_record()
            elif name and code not in self.down:
                self.down[code] = name
                self.chord = chord(self.down.values())
                self.show_keys(self.chord)
                self.key_row.say("ปล่อยทุกปุ่มเพื่อบันทึก")
            return None
        if name in MODS:  # a Mac sends no key up for a key let go while ⌘ is held: those go up with it
            for c in [c for c, n in self.down.items() if n not in MODS]:
                self.down.pop(c)
        if self.down.pop(code, None) is None or self.down:
            return None
        why = key_rule(self.chord)
        if why:  # said, and it records again
            self.show_keys("")
            self.key_row.say(why, bad=True)
            return None
        self.main.set_key(self.chord)
        self.cancel_record(saved=True)
        self.key_row.say(f"{''.join(keyname(self.chord).split('+'))} บันทึกแล้ว")
        return None
