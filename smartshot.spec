# PyInstaller recipe, run by build.sh -> dist/Snaplens.app
# A folder, not one file: a one-file app unpacks ~60 MB of models to a temp folder on every start.
import re

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

UNUSED = ("ch_PP-OCRv5_det_mobile.onnx", "ch_PP-OCRv5_det_server.onnx")  # rapidocr ships them; the app never loads them
OTHER_ENGINES = (".openvino", ".paddle", ".pytorch", ".mnn", ".tensorrt")  # only onnxruntime is installed
VERSION = re.search(r'^VERSION = "([\d.]+)"', open("smartshot/config.py", encoding="utf-8").read(), re.M)[1]

datas = [(src, dst) for src, dst in collect_data_files("rapidocr") if not src.endswith(UNUSED)]
datas += [("assets/icons/app-256.png", "assets/icons"), ("assets/icons/tray-light-32.png", "assets/icons")]
hidden = collect_submodules("rapidocr", filter=lambda name: not any(e in name for e in OTHER_ENGINES))  # lazy imports

DROP = ("qtquick", "qtqml", "qtpdf", "qtvirtualkeyboard", "qtwebengine", "pyside6/translations/")  # QML, PDF: unused
keep = lambda entry: not any(d in entry[0].lower() for d in DROP)

a = Analysis(["app.py"], datas=datas, hiddenimports=hidden, excludes=["tkinter"])
a.binaries, a.datas = list(filter(keep, a.binaries)), list(filter(keep, a.datas))
exe = EXE(PYZ(a.pure), a.scripts, exclude_binaries=True, name="smartshot", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="smartshot")
# no Dock icon (it lives in the menu bar); its bundle id and signature are what Screen Recording is granted to
app = BUNDLE(coll, name="Snaplens.app", icon="assets/icons/app.icns", bundle_identifier="io.github.kehsb.snaplens",
             version=VERSION, info_plist={
                 "CFBundleDisplayName": "Snaplens", "CFBundleShortVersionString": VERSION, "LSUIElement": True,
                 "LSMinimumSystemVersion": "12.0", "NSHighResolutionCapable": True,
                 "NSScreenCaptureUsageDescription": "Snaplens จับภาพหน้าจอเพื่ออ่านและแปลข้อความ"})
