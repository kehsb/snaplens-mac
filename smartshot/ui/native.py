"""AppKit building blocks shared by the native UI (the settings, the menu bar menu, the capture's chrome, the card):
targets for Python callbacks, labels, stacks, SF Symbols, Liquid Glass, menus, and the root view a capture's native
surface hangs from inside the overlay's own NSView."""
import ctypes

import AppKit
import objc
from Foundation import NSMakeSize, NSObject

try:
    GLASS = objc.lookUpClass("NSGlassEffectView")  # macOS 26: Liquid Glass; else a vibrant blur stands in
except objc.nosuchclass_error:
    GLASS = None


class Target(NSObject):  # a control's or menu item's target: AppKit holds it weakly, its owner keeps it (keep)
    def initWithFn_(self, fn):
        self = objc.super(Target, self).init()
        self.fn = fn
        return self

    def fire_(self, sender):
        self.fn(sender)


def target(fn, keep):  # -> a Target calling fn(sender), kept alive in the list keep
    t = Target.alloc().initWithFn_(fn)
    keep.append(t)
    return t


def dynamic(dark, light):  # a colour that follows the appearance: (r, g, b, a) 0-1 each
    rgba = lambda c: AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(*c)

    def pick(appearance):
        names = [AppKit.NSAppearanceNameAqua, AppKit.NSAppearanceNameDarkAqua]
        return rgba(dark if appearance.bestMatchFromAppearancesWithNames_(names) == names[1] else light)
    return AppKit.NSColor.colorWithName_dynamicProvider_(None, pick)


def srgb(r, g, b, a=1.0):  # 0-255 channels, as the app's colour tables are
    return AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(r / 255, g / 255, b / 255, a)


def label(text, size=13, weight=AppKit.NSFontWeightRegular, color=None, mono=False):
    f = AppKit.NSTextField.labelWithString_(text)
    f.setFont_(AppKit.NSFont.monospacedSystemFontOfSize_weight_(size, weight) if mono else
               AppKit.NSFont.systemFontOfSize_weight_(size, weight))
    f.setTextColor_(color or AppKit.NSColor.labelColor())
    f.setLineBreakMode_(AppKit.NSLineBreakByTruncatingTail)
    return f


def fixed(view, w=None, h=None):
    view.setTranslatesAutoresizingMaskIntoConstraints_(False)
    if w is not None:
        view.widthAnchor().constraintEqualToConstant_(w).setActive_(True)
    if h is not None:
        view.heightAnchor().constraintEqualToConstant_(h).setActive_(True)
    return view


def stack(views, vertical=False, spacing=8, insets=None, align=None):
    s = AppKit.NSStackView.stackViewWithViews_(views)
    s.setOrientation_(AppKit.NSUserInterfaceLayoutOrientationVertical if vertical else
                      AppKit.NSUserInterfaceLayoutOrientationHorizontal)
    s.setSpacing_(spacing)
    s.setAlignment_(align if align is not None else
                    AppKit.NSLayoutAttributeLeading if vertical else AppKit.NSLayoutAttributeCenterY)
    if insets:
        s.setEdgeInsets_(AppKit.NSEdgeInsets(*insets))
    return s


def pin(view, into, insets=(0, 0, 0, 0)):  # view fills into, inset (top, left, bottom, right)
    view.setTranslatesAutoresizingMaskIntoConstraints_(False)
    into.addSubview_(view)
    t, l, b, r = insets
    view.topAnchor().constraintEqualToAnchor_constant_(into.topAnchor(), t).setActive_(True)
    view.leadingAnchor().constraintEqualToAnchor_constant_(into.leadingAnchor(), l).setActive_(True)
    view.bottomAnchor().constraintEqualToAnchor_constant_(into.bottomAnchor(), -b).setActive_(True)
    view.trailingAnchor().constraintEqualToAnchor_constant_(into.trailingAnchor(), -r).setActive_(True)
    return view


def symbol(name, size=None, weight=AppKit.NSFontWeightRegular):  # an SF Symbol, a template image
    img = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, None)
    if img is not None and size:
        img = img.imageWithSymbolConfiguration_(AppKit.NSImageSymbolConfiguration.configurationWithPointSize_weight_(size, weight))
    return img


def tile(name, rgb):  # System Settings' icon: a white SF Symbol on a coloured rounded square
    v = fixed(AppKit.NSView.alloc().init(), 24, 24)
    v.setWantsLayer_(True)
    v.layer().setCornerRadius_(6)
    v.layer().setBackgroundColor_(srgb(*rgb).CGColor())
    img = AppKit.NSImageView.imageViewWithImage_(symbol(name, 13, AppKit.NSFontWeightSemibold))
    img.setContentTintColor_(AppKit.NSColor.whiteColor())
    img.setTranslatesAutoresizingMaskIntoConstraints_(False)
    v.addSubview_(img)
    img.centerXAnchor().constraintEqualToAnchor_(v.centerXAnchor()).setActive_(True)
    img.centerYAnchor().constraintEqualToAnchor_(v.centerYAnchor()).setActive_(True)
    return v


def box(view, radius, fill, border=False):  # view on a rounded, filled box (opaque: what glass can't be, a receipt)
    b = AppKit.NSBox.alloc().init()
    b.setBoxType_(AppKit.NSBoxCustom)
    b.setTitlePosition_(AppKit.NSNoTitle)
    b.setCornerRadius_(radius)
    b.setFillColor_(fill)
    b.setBorderWidth_(.5 if border else 0)
    b.setBorderColor_(AppKit.NSColor.separatorColor())
    b.setContentViewMargins_(NSMakeSize(0, 0))
    b.setTranslatesAutoresizingMaskIntoConstraints_(False)
    pin(view, b.contentView())
    return b


def glass(view, radius, tint=None, clear=False):
    """view on Liquid Glass (NSGlassEffectView), cornered radius (a capsule: half its height); tint: an NSColor
    washing the glass (the translate capsule's blue). Before macOS 26, a HUD blur with the same corners."""
    if GLASS is not None:
        g = GLASS.alloc().init()
        g.setCornerRadius_(radius)
        g.setStyle_(1 if clear else 0)  # NSGlassEffectViewStyleClear, Regular
        if tint is not None:
            g.setTintColor_(tint)
        view.setTranslatesAutoresizingMaskIntoConstraints_(False)
        g.setContentView_(view)
    else:
        g = AppKit.NSVisualEffectView.alloc().init()
        g.setMaterial_(AppKit.NSVisualEffectMaterialHUDWindow)
        g.setBlendingMode_(AppKit.NSVisualEffectBlendingModeWithinWindow)
        g.setState_(AppKit.NSVisualEffectStateActive)
        g.setWantsLayer_(True)
        g.layer().setCornerRadius_(radius)
        g.layer().setMasksToBounds_(True)
        pin(view, g)
    g.setTranslatesAutoresizingMaskIntoConstraints_(False)
    return g


def host(widget):  # a Qt top-level's own NSView (QNSView): its window's content view, flipped, in Qt's points
    return objc.objc_object(c_void_p=ctypes.c_void_p(int(widget.winId())))


class Surface(AppKit.NSView):
    """The root of a native surface inside the capture overlay's QNSView, laid out in Qt's coordinates. What its
    controls don't take stays here: a click between buttons mustn't climb to Qt as a click on the image. pressed:
    called on any press inside (before a control acts), for what a click on chrome does to the overlay's focus."""

    def initWithPressed_(self, pressed):
        self = objc.super(Surface, self).init()
        self.pressed = pressed
        return self

    def isFlipped(self):
        return True

    def acceptsFirstMouse_(self, e):
        return True

    def hitTest_(self, pt):  # a press anywhere inside: the overlay first (pressed), then whatever is hit
        hit = objc.super(Surface, self).hitTest_(pt)
        if hit is not None and self.pressed and AppKit.NSApp.currentEvent() is not None and \
                AppKit.NSApp.currentEvent().type() in (AppKit.NSEventTypeLeftMouseDown, AppKit.NSEventTypeRightMouseDown):
            self.pressed()
        return hit

    def mouseDown_(self, e):
        pass

    def rightMouseDown_(self, e):
        pass

    def otherMouseDown_(self, e):
        pass

    def scrollWheel_(self, e):
        pass

    def cursorUpdate_(self, e):
        AppKit.NSCursor.arrowCursor().set()


def menu(rows, keep, title=""):
    """An NSMenu from rows: (symbol or None, title, (key, mask) or None, checked, fn or submenu rows), None for a
    separator, ("head", title) for a section header. fn gets no arguments."""
    m = AppKit.NSMenu.alloc().initWithTitle_(title)
    m.setAutoenablesItems_(False)
    for row in rows:
        if row is None:
            m.addItem_(AppKit.NSMenuItem.separatorItem())
            continue
        if row[0] == "head":
            m.addItem_(AppKit.NSMenuItem.sectionHeaderWithTitle_(row[1]))
            continue
        glyph, text, keys, checked, fn = row
        it = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(text, None, keys[0] if keys else "")
        if keys:
            it.setKeyEquivalentModifierMask_(keys[1])
        if glyph:
            it.setImage_(symbol(glyph))
        if checked:
            it.setState_(AppKit.NSControlStateValueOn)
        if isinstance(fn, (list, tuple)):
            it.setSubmenu_(menu(fn, keep, text))
        elif fn is not None:
            it.setTarget_(target(lambda _, fn=fn: fn(), keep))
            it.setAction_("fire:")
        m.addItem_(it)
    return m


def install_edit_menu():  # once: ⌘X ⌘C ⌘V ⌘A in native text fields (the settings' key sheet, the card's key box)
    main = AppKit.NSApp.mainMenu()
    if main is None or main.itemWithTitle_("Edit") is not None:
        return
    edit = AppKit.NSMenu.alloc().initWithTitle_("Edit")
    for title, action, key in (("Cut", "cut:", "x"), ("Copy", "copy:", "c"), ("Paste", "paste:", "v"),
                               ("Select All", "selectAll:", "a")):  # no Undo: NSWindow answers undo:, Qt's ⌘Z wouldn't
        edit.addItemWithTitle_action_keyEquivalent_(title, action, key)  # target nil: the first responder
    item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Edit", None, "")
    item.setSubmenu_(edit)
    main.insertItem_atIndex_(item, min(1, main.numberOfItems()))
