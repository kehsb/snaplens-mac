"""Build facts, paths and the app's fixed choices: languages, fonts, OCR thresholds, script ranges."""
import glob
import os
import re
import sys
import time


VERSION = "0.16.1"  # bump on feature changes
BUNDLE = "io.github.kehsb.snaplens"  # the built app's bundle id (snaplens.spec): its prefs, login item and notices
FROZEN = getattr(sys, "frozen", False)  # Snaplens.app built by PyInstaller (build.sh), not python app.py
QUIET = bool({"--startup", "--login"} & set(sys.argv))  # at login: launchd's --startup, or the copy it hands on to (app.py)
HERE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # app.py, assets/; the app's too
SOURCES = glob.glob(os.path.join(HERE, "snaplens", "**", "*.py"), recursive=True) + [os.path.join(HERE, "app.py")]
BUILD = time.strftime("%H:%M:%S", time.localtime(os.path.getmtime(sys.executable) if FROZEN else  # auto: when saved/built
                                                 max(map(os.path.getmtime, SOURCES))))
TITLE = f"Snaplens v{VERSION} (build {BUILD})"
HOTKEY = "ctrl+alt+s"  # Control+Option+S, until the user records their own (kept in QSettings)
DATA = os.path.expanduser("~/Library/Application Support/Snaplens")  # the app's files, kept through reinstalls
OLD_DATA = os.path.expanduser("~/Library/Application Support/smartshot")  # 0.16.0's: slip/thunder.py moves its key over
CTRL = "⌘"  # the shortcuts' modifier, as their keycaps say it: ⌘+C
TRAY = "แถบเมนู"  # where the app's icon lives
# translation targets: Google code -> (name, MyMemory code)
LANGS = {"th": ("ไทย", "th-TH"), "en": ("อังกฤษ", "en-GB"), "zh-CN": ("จีนตัวย่อ", "zh-CN"), "zh-TW": ("จีนตัวเต็ม", "zh-TW"),
         "ja": ("ญี่ปุ่น", "ja-JP"), "ko": ("เกาหลี", "ko-KR"), "vi": ("เวียดนาม", "vi-VN")}
PAD = 100
UPSCALE, SMALL = 2, 400  # captures under SMALL px on a side are enlarged before OCR
# text drawn on the image (translations, the text tool); the app's own text is the system's (SF, Menlo)
FONTS = ["Thonburi", "Helvetica Neue", "PingFang SC"]
ASSETS = os.path.join(HERE, "assets")
MIN_SCORE = 0.5  # below this the reading is usually hallucinated
THAI = re.compile(r"[฀-๿]")
PINYIN = re.compile(r"[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]")
CJK = re.compile(r"[一-鿿]")
