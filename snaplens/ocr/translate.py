"""Translate OCR lines (Google, else MyMemory)."""
import sys
from concurrent.futures import ThreadPoolExecutor

from deep_translator import GoogleTranslator, MyMemoryTranslator

from snaplens.config import CJK, LANGS, PINYIN, THAI


def translate(lines, target="th"):
    """One request for all lines (gentler on Google's free endpoint); per-line fallback if it fails/misaligns."""
    gt = GoogleTranslator(source="auto", target=target)
    # skip: Thai going to Thai, pinyin (romanization), and fragments with <2 letters (list numbers like "1)")
    todo = [i for i, t in enumerate(lines) if sum(c.isalpha() for c in t) >= 2
            and not (target == "th" and THAI.search(t)) and not PINYIN.search(t)]
    out = list(lines)
    if not todo:
        return out
    flat = [lines[i].replace("\n", " ") for i in todo]
    google_ok = True
    try:
        res = gt.translate("\n".join(flat)).split("\n")
        if len(res) == len(todo):
            for i, r in zip(todo, res):
                out[i] = r
            return out
    except Exception:  # rate limited: don't retry Google line by line, it fails the same way
        google_ok = False

    def one(t):
        if google_ok:
            try:
                return gt.translate(t) or t
            except Exception:
                pass
        try:  # MyMemory: free, ~5k chars/day, needs explicit source
            src, dst = "zh-CN" if CJK.search(t) else "th-TH" if THAI.search(t) else "en-US", LANGS[target][1]
            if src[:2] == dst[:2]:  # already in that language; MyMemory rejects same-language pairs
                return t
            return MyMemoryTranslator(source=src, target=dst).translate(t[:490]) or t
        except Exception as e:
            print("translate failed:", repr(e)[:100], file=sys.stderr)
            return t  # keep original line

    with ThreadPoolExecutor(4) as ex:
        for i, r in zip(todo, ex.map(one, flat)):
            out[i] = r
    return out
