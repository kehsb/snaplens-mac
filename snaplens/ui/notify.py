"""Notices while no window of ours is up (ready, still in the menu bar, Screen Recording needed). From the built app
they're Notification Center's. Run from source they'd be Python's, asked for as Python, so the app shows its own
instead: a small Liquid Glass one at the top right, under the menu bar. It does the same where notices are turned off."""
import os
import traceback

import AppKit
import objc
import UserNotifications as UN
from Foundation import NSBundle, NSMakeRect, NSObject, NSOperationQueue, NSRunLoop, NSRunLoopCommonModes, NSTimer

from snaplens.config import ASSETS, BUNDLE, FROZEN
from snaplens.ui.native import fixed, glass, label, pin, stack

NOTICE = "snaplens.notice"  # every notice's id: a new one replaces the last
WIDTH, WORDS, INSET = 340, 256, 14  # the HUD: its width, its text's (after the icon), its gap to the screen's corner
_center = _delegate = _hud = None


def notify(title, text):  # title, and a line or two under it; one at a time
    global _center, _delegate
    if not (FROZEN and NSBundle.mainBundle().bundleIdentifier() == BUNDLE):  # Notification Center's: the bundle's icon
        return hud(title, text)
    if _center is None:
        _center, _delegate = UN.UNUserNotificationCenter.currentNotificationCenter(), _NoticeDelegate.alloc().init()
        _center.setDelegate_(_delegate)

    def post(allowed):  # turned off: ours instead, as one saying Screen Recording is needed must be seen
        if not allowed:
            return hud(title, text)
        content = UN.UNMutableNotificationContent.alloc().init()
        content.setTitle_(title)
        content.setBody_(text)
        _center.removeDeliveredNotificationsWithIdentifiers_([NOTICE])
        _center.addNotificationRequest_withCompletionHandler_(
            UN.UNNotificationRequest.requestWithIdentifier_content_trigger_(NOTICE, content, None), posted)

    def posted(error):
        if error is not None:
            on_main(lambda: hud(title, text))

    def asked(granted, error):
        on_main(lambda: post(granted))

    def settled(settings):  # permission is asked the first time a notice goes out, not at launch
        status = settings.authorizationStatus()
        if status == UN.UNAuthorizationStatusNotDetermined:
            _center.requestAuthorizationWithOptions_completionHandler_(UN.UNAuthorizationOptionAlert, asked)
        else:
            on_main(lambda: post(status != UN.UNAuthorizationStatusDenied))
    _center.getNotificationSettingsWithCompletionHandler_(settled)


def on_main(fn):  # a completion handler's work, on the main thread: the handlers run on a queue of their own
    def run():  # a void block: nothing out of it, no value (that raises) and no exception (GCD ends the app on one)
        try:
            fn()
        except Exception:
            traceback.print_exc()
    NSOperationQueue.mainQueue().addOperationWithBlock_(run)


class _NoticeDelegate(NSObject, protocols=[objc.protocolNamed("UNUserNotificationCenterDelegate")]):
    def userNotificationCenter_willPresentNotification_withCompletionHandler_(self, center, note, done):
        done(UN.UNNotificationPresentationOptionBanner | UN.UNNotificationPresentationOptionList)  # the settings in front too

    def userNotificationCenter_didReceiveNotificationResponse_withCompletionHandler_(self, center, answer, done):
        done()  # a click only dismisses it


def hud(title, text):  # ours, shown now; the one before goes
    global _hud
    if _hud:
        _hud.hide()
    _hud = Hud(title, text)
    _hud.show()


class _HudView(AppKit.NSView):  # the HUD's own view: a click anywhere on it, with any button, hides it
    def initWithFn_(self, fn):
        self = objc.super(_HudView, self).init()
        self.fn = fn
        return self

    def hitTest_(self, pt):  # the click is on the notice, not on its words
        return self if objc.super(_HudView, self).hitTest_(pt) is not None else None

    def acceptsFirstMouse_(self, e):
        return True

    def mouseDown_(self, e):
        self.fn()

    def rightMouseDown_(self, e):
        self.fn()

    def otherMouseDown_(self, e):
        self.fn()


def words(text, size, weight=AppKit.NSFontWeightRegular):  # wrapped at the HUD's text width
    f = AppKit.NSTextField.wrappingLabelWithString_(text)
    f.setFont_(AppKit.NSFont.systemFontOfSize_weight_(size, weight))
    f.setTextColor_(AppKit.NSColor.labelColor())
    f.setPreferredMaxLayoutWidth_(WORDS)
    return fixed(f, WORDS)


class Hud:
    """The notice of the app's own, where the system's are: the top right of the screen in use, under the menu bar,
    over other apps' windows without taking their keys. The app's icon, "Snaplens" and "ตอนนี้", the title and the
    text. It goes after 5 s, or on a click."""

    def __init__(self, title, text):
        self.text = f"{title}. {text}"
        icon = AppKit.NSImage.alloc().initWithContentsOfFile_(os.path.join(ASSETS, "icons", "app-256.png"))
        head = fixed(stack([label("Snaplens", 12, color=AppKit.NSColor.secondaryLabelColor()),
                            label("ตอนนี้", 12, color=AppKit.NSColor.secondaryLabelColor())]), WORDS)
        head.setDistribution_(AppKit.NSStackViewDistributionEqualSpacing)  # the name at the start, the time at the end
        column = stack([head, words(title, 15, AppKit.NSFontWeightSemibold), words(text, 14)], vertical=True, spacing=4)
        row = stack([fixed(AppKit.NSImageView.imageViewWithImage_(icon), 36, 36), column], spacing=12,
                    align=AppKit.NSLayoutAttributeTop)
        # a top-aligned row holds no bottom inset, and glass squeezes a stack's side insets: a column, its width fixed
        body = fixed(stack([row], vertical=True, insets=(16, 18, 16, 18)), WIDTH)
        self.root = _HudView.alloc().initWithFn_(self.hide)
        pin(glass(body, 24), self.root)
        self.root.setAccessibilityElement_(True)
        self.root.setAccessibilityRole_(AppKit.NSAccessibilityGroupRole)
        self.root.setAccessibilityLabel_(self.text)
        w, h = self.root.fittingSize()
        area = AppKit.NSScreen.mainScreen().visibleFrame()  # under the menu bar of the screen in use
        self.panel = p = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(area.origin.x + area.size.width - INSET - w, area.origin.y + area.size.height - INSET - h, w, h),
            AppKit.NSWindowStyleMaskBorderless | AppKit.NSWindowStyleMaskNonactivatingPanel, AppKit.NSBackingStoreBuffered, True)
        p.setContentView_(self.root)
        p.setLevel_(AppKit.NSStatusWindowLevel)
        p.setCollectionBehavior_(AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces | AppKit.NSWindowCollectionBehaviorStationary
                                 | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
                                 | AppKit.NSWindowCollectionBehaviorIgnoresCycle)
        p.setOpaque_(False)
        p.setBackgroundColor_(AppKit.NSColor.clearColor())
        p.setHasShadow_(True)
        p.setHidesOnDeactivate_(False)  # an accessory app is seldom the active one
        p.setReleasedWhenClosed_(False)

    def show(self):
        self.panel.orderFrontRegardless()  # the app isn't in front: over the others all the same
        self.timer = NSTimer.timerWithTimeInterval_repeats_block_(5, False, lambda t: self.hide())
        NSRunLoop.mainRunLoop().addTimer_forMode_(self.timer, NSRunLoopCommonModes)  # in a menu's or a dialog's loop too
        AppKit.NSAccessibilityPostNotificationWithUserInfo(  # VoiceOver reads it out, as it did the glass one
            AppKit.NSApp, AppKit.NSAccessibilityAnnouncementRequestedNotification,
            {AppKit.NSAccessibilityAnnouncementKey: self.text,
             AppKit.NSAccessibilityPriorityKey: AppKit.NSAccessibilityPriorityHigh})

    def hide(self):  # again too: hud() hides the last one, which may have gone by itself
        if self.timer is not None:
            self.timer.invalidate()
        self.panel.orderOut_(None)
        self.timer = self.root.fn = None  # the cycles through AppKit (its timer's block, its view) Python can't collect
