"""Start at login: the launchd agent inside Snaplens.app (Contents/Library/LaunchAgents, put there by snaplens.spec
from assets/), registered with SMAppService, so Login Items shows it as Snaplens with the app's icon. Run from source
there's no bundle to register: the switch is greyed (settings.py). macOS 12 has no SMAppService: a LaunchAgent of
our own there, as 0.16.0's was."""
import os
import plistlib
import sys

from PySide6.QtCore import QSettings

from snaplens.config import BUNDLE, FROZEN
from snaplens.system.prefs import NEW, alone

try:  # macOS 13
    from ServiceManagement import SMAppService, SMAppServiceStatusEnabled as ENABLED, \
        SMAppServiceStatusRequiresApproval as WAITING
    ON = (ENABLED, WAITING)  # registered; waiting: Login Items has it switched off
except ImportError:
    SMAppService = None

AGENT = f"{BUNDLE}.plist"  # its name in the bundle: Label, BundleProgram Contents/MacOS/Snaplens, --startup, RunAtLoad
LEGACY = os.path.expanduser(f"~/Library/LaunchAgents/{AGENT}")  # macOS 12's
OLD = os.path.expanduser("~/Library/LaunchAgents/smartshot.plist")  # 0.16.0 and before: label smartshot, MacOS/smartshot
USABLE = FROZEN  # from source there's no app to start at login


def services():  # the agent, then Open at Login: its stand-in, when the agent can't be registered
    return SMAppService.agentServiceWithPlistName_(AGENT), SMAppService.mainAppService()


def autostart(on=None):  # on: register or unregister (launchd starts it quietly into the menu bar) -> is it on
    if not USABLE:
        return False
    if SMAppService is None:
        return legacy(on)
    agent, app = services()
    if on and agent.status() not in ON:
        if call(agent.registerAndReturnError_):
            mark()
        if agent.status() not in ON:  # refused outright: Open at Login instead. That starts the app without
            call(app.registerAndReturnError_)  # --startup, so at login it says it's ready as one started by hand does
    elif on is False:  # the agent's process is killed with it: app.py hands the app on, so that's not this one
        for s in (agent, app):
            if s.status() in ON:
                call(s.unregisterAndReturnError_)
    return any(s.status() in ON for s in (agent, app))  # waiting counts as on: the user asked, Login Items decides


def waiting():  # registered, but switched off in Login Items: the user allows it there
    return USABLE and SMAppService is not None and any(s.status() == WAITING for s in services())


def login_items():  # System Settings > General > Login Items: only on the user's own toggle
    SMAppService.openSystemSettingsLoginItems()


def call(fn):  # an SMAppService (un)register -> done; its NSError printed, not raised
    ok, err = fn(None)
    if not ok:
        print("login item:", err, file=sys.stderr)
    return ok


def legacy(on):  # macOS 12: a LaunchAgent file of ours, the app's own path (a moved Snaplens.app needs the switch again)
    if on:
        os.makedirs(os.path.dirname(LEGACY), exist_ok=True)
        with open(LEGACY, "wb") as f:
            plistlib.dump({"Label": BUNDLE, "ProgramArguments": [sys.executable, "--startup"], "RunAtLoad": True,
                           "ProcessType": "Interactive"}, f)
    elif on is not None and os.path.exists(LEGACY):
        os.remove(LEGACY)
    return os.path.exists(LEGACY)


def carry():  # once, in the built app that replaced 0.16.0 in place: its agent gone, ours registered in its place
    if not USABLE or not os.path.exists(OLD):
        return
    try:
        with open(OLD, "rb") as f:
            exe = plistlib.load(f)["ProgramArguments"][0]
    except (OSError, plistlib.InvalidFileException, KeyError, IndexError, TypeError):
        return
    if os.path.dirname(exe) != os.path.dirname(sys.executable) or os.path.exists(exe):
        return  # 0.16.0 still there (this copy runs from the DMG, dist/...): its login item stays as it is
    if autostart(True):  # RunAtLoad: a second copy starts with --startup and leaves (app.py), the server up already
        os.remove(OLD)  # still loaded in launchd till logout: harmless, it doesn't run again. Refused: tried next start


def stamp():  # this build's executable: a new one (an update) is registered again
    return str(os.stat(sys.executable).st_mtime_ns)


def mark():  # the agent registered for this build
    alone(QSettings(*NEW)).setValue("agent", stamp())


def renew():  # at start: Apple's agent, its executable updated, "must be re-registered or it may not launch"
    if not USABLE or SMAppService is None:  # not unregistered first: that would kill a copy launchd started
        return
    agent = services()[0]
    if agent.status() == ENABLED and alone(QSettings(*NEW)).value("agent") != stamp():
        call(agent.registerAndReturnError_)
        mark()  # once a build, refused or not: not tried at every start
