"""RapidOCR: one recognizer per language, a shared detector, and ocr() over a capture."""
import threading

import cv2
import numpy as np
from PySide6.QtCore import QRect
from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR

from snaplens.config import MIN_SCORE, PAD, SMALL, UPSCALE


_engines = {}
_lock = threading.Lock()  # ponytail: one OCR at a time; fine for a single-user tool
_det = None


def engine(lang):  # recognizer per language; lazy: first use downloads the model
    if lang not in _engines:
        _engines[lang] = RapidOCR(params={
            "Rec.lang_type": LangRec(lang), "Rec.ocr_version": OCRVersion.PPOCRV5, "Rec.model_type": ModelType.MOBILE,
        })
    return _engines[lang]


def detector():  # PP-OCRv6 det finds Thai/CJK/Latin lines alike; v5 det misses Thai rows
    global _det
    if _det is None:
        v6, small = OCRVersion.PPOCRV6, ModelType.SMALL
        _det = RapidOCR(params={"Det.ocr_version": v6, "Det.model_type": small,
                                "Rec.ocr_version": v6, "Rec.model_type": small})
    return _det


def warmup():  # load + run every model once at startup so the first capture is fast
    with _lock:
        blank = np.full((48, 160, 3), 255, np.uint8)
        detector()(blank, use_rec=False, use_cls=False)
        for lang in ("ch", "th"):
            engine(lang)(blank, use_det=False, use_cls=False)


def ocr(img, mode):
    with _lock:
        return _ocr(img, mode)


def _ocr(img, mode):
    """img: BGR ndarray. mode: 'auto' | 'ch' (zh+en) | 'th'. Returns [(QRect, text)].
    Detect lines once, then every language reads every line; the wrong language scores low, so best wins."""
    langs = ["ch", "th"] if mode == "auto" else [mode]
    k = UPSCALE if min(img.shape[:2]) < SMALL else 1  # small captures lose Thai tone marks
    if k > 1:
        img = cv2.resize(img, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)
    img = cv2.copyMakeBorder(img, PAD, PAD, PAD, PAD, cv2.BORDER_REPLICATE)  # detector misses text in thin crops
    boxes = detector()(img, use_rec=False, use_cls=False).boxes
    out = []
    for box in [] if boxes is None else boxes:
        x0, y0 = np.maximum(box.min(axis=0).astype(int) - 4, 0)
        x1, y1 = box.max(axis=0).astype(int) + 4
        crop = img[y0:y1, x0:x1]
        best = (0.0, "")
        for lang in langs:
            r = engine(lang)(crop, use_det=False, use_cls=False)
            if r.txts and float(r.scores[0]) > best[0]:
                best = (float(r.scores[0]), r.txts[0])
        if best[0] >= MIN_SCORE:
            out.append((QRect(*((int(v) // k) for v in (x0 + 4 - PAD, y0 + 4 - PAD, x1 - x0 - 8, y1 - y0 - 8))), best[1]))
    return sorted(out, key=lambda o: (o[0].y(), o[0].x()))
