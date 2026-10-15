# dmgbuild settings, run by build.sh (from here: paths are the repo's) -> installer/Snaplens-<version>.dmg
# The volume with the app's icon; its window: the app on the left, Applications on the right, an arrow between them
# on assets/dmg/background.png (and @2x, made by background.py there). -D app=... the Snaplens.app to put in.
import os

app = globals()["defines"].get("app", "dist/Snaplens.app")  # dmgbuild -D app=...
format = "UDZO"  # zlib, as hdiutil's was
files = [app]
symlinks = {"Applications": "/Applications"}  # drag it there
icon = "assets/icons/app.icns"  # the volume's, on the desktop and in Finder's sidebar
background = "assets/dmg/background.png"
window_rect = ((200, 140), (600, 440))  # the picture is 600 x 420: the title bar takes some of the 440
icon_size = 128
text_size = 13
icon_locations = {os.path.basename(app): (160, 200), "Applications": (440, 200)}  # background.py's APP, APPS, ROW
default_view = "icon-view"
show_icon_preview = False
include_icon_view_settings = True
include_list_view_settings = False
