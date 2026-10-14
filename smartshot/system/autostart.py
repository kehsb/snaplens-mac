"""Start at login: a LaunchAgent."""
import os
import plistlib
import sys

from smartshot.config import FROZEN, HERE

AGENT = os.path.expanduser("~/Library/LaunchAgents/smartshot.plist")


def autostart(on=None):  # on: add or remove the agent (launchd starts it quietly into the menu bar) -> is it there
    if on:  # the app's own path: a moved Snaplens.app needs the switch again
        args = [sys.executable] if FROZEN else [sys.executable, os.path.join(HERE, "app.py")]
        os.makedirs(os.path.dirname(AGENT), exist_ok=True)
        with open(AGENT, "wb") as f:
            plistlib.dump({"Label": "smartshot", "ProgramArguments": args + ["--startup"], "RunAtLoad": True,
                           "ProcessType": "Interactive"}, f)
    elif on is not None and os.path.exists(AGENT):
        os.remove(AGENT)
    return os.path.exists(AGENT)
