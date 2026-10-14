"""The image's side of a slip vs the bank's: names, accounts, refs, dates, times."""
import difflib
import re

from smartshot.config import THAI
from smartshot.qr.promptpay import TH_MONTHS


# --- reading the image's side of a slip, for compare()
TITLES = ("นางสาว", "นาง", "นาย", "นส", "ดช", "ดญ", "MISS", "MRS", "MR", "MS")  # longest first; dots are gone by then
MASKS = str.maketrans("*•×", "XXX")
ACCOUNT = re.compile(r"[0-9xX*•×][0-9xX*•×\s\-–—一]{6,}[0-9xX*•×]")  # 一: the Chinese model reads a dash so
TIME = re.compile(r"(\d{1,2}):(\d\d)(?::\d\d)?\s*([AP]M)?", re.I)  # no (?<!\d): a garbled "256901:25" still has 01:25
DATE = re.compile(r"(?<!\d)(\d{1,2})\s*(?:(เ?[ก-ฮ][ิี]?\.?\s?[ก-ฮ]\.?|[A-Za-z]{3})[A-Za-z]*\.?|[/.-]\s*(\d{1,2})\s*[/.-])"
                  r"\s*(\d{4}|\d\d)(?!\d)")  # 7 ต.ค. 69, 07 ต.ค. 2569, 7 Oct 2026, 07/10/2569
MONTHS = {m: i for i, m in enumerate([m.replace(".", "") for m in TH_MONTHS], 1)} | \
    {m: i for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), 1)}
PAIR = {"ผู้โอน": "ผู้รับ", "ผู้รับ": "ผู้โอน", "บัญชีผู้โอน": "บัญชีผู้รับ", "บัญชีผู้รับ": "บัญชีผู้โอน"}


def _name(s):  # -> (letters only, upper case, title off; had a title)
    s = "".join(re.findall(r"[A-Za-zก-๎]", s)).upper()
    t = next((t for t in TITLES if s.startswith(t)), "")
    return s[len(t):], bool(t)


def _like(a, b):  # how much of the shorter name is in the other, in runs of 2+ letters: OCR drops and swaps some
    n = min(len(a), len(b))
    return sum(m.size for m in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks()
               if m.size > 1) / n if n >= 4 else 0


def _acc(s):  # the account number a line shows, as [0-9X] (masked digits: X), or ""
    runs = [re.sub(r"[^0-9X]", "", m.upper().translate(MASKS)) for m in ACCOUNT.findall(s)]
    return max((r for r in runs if sum(c.isdigit() for c in r) >= 3), key=len, default="")


def _acc_is(b, a):  # the bank's account b vs the image's a (both [0-9X]) -> True / False / None: can't tell
    if len(a) == len(b):  # the same mask: digit by digit where both show one
        both = [(x, y) for x, y in zip(a, b) if x != "X" and y != "X"]
        return all(x == y for x, y in both) if len(both) >= 3 else None
    groups = re.findall(r"\d{3,}", b)  # masked otherwise (an e-wallet id, a phone): the bank's digits are in it
    return True if groups and "X" in a and all(g in a for g in groups) else None


def _ref(s):
    return re.sub(r"[^0-9A-Z]", "", s.upper()).translate(str.maketrans("OIL", "011"))  # what OCR mixes up


def _day_is(m, d):  # a DATE match is d's day; the year in BE or CE, 4 or 2 digits
    month = int(m[3]) if m[3] else MONTHS.get(re.sub(r"[.\s]", "", m[2]).upper())
    return int(m[1]) == d.day and month == d.month and m[4] in {
        str(d.year), str(d.year + 543), f"{d.year % 100:02d}", f"{(d.year + 543) % 100:02d}"}


def _time_is(m, d):  # a TIME match is d's, give or take 2 minutes (slips cut the seconds)
    h = int(m[1]) % 12 + 12 * (m[3].upper() == "PM") if m[3] else int(m[1])
    diff = abs(h * 60 + int(m[2]) - d.hour * 60 - d.minute)
    return min(diff, 1440 - diff) <= 2


def compare(fields, lines, nums, few, alone):
    """slip_fields() against the OCR'd lines by that slip's code -> [(label, seen in the image, the bank's, under it,
    mark)]. ✓ the image shows it; ✗ the image plainly shows something else; ? OCR can't tell (or the slip doesn't
    print it), which never counts against it. nums: amounts read by the code; few: the bank's amount is printed
    fewer times here than codes here pay it; alone: the only code here, so the lines are all its slip's."""
    out, hit = [], {}
    names = [(i, *_name(t)) for i, t in enumerate(lines)]
    accs = [(i, _acc(t)) for i, t in enumerate(lines)]
    for label, how, v, shown, under in fields:
        seen, mark = "", "?"
        if how == "amount" and isinstance(v, (int, float)):
            a = round(v, 2)
            if a in nums:
                seen, mark = f"{a:,.2f}", "✓"
            elif few:  # read amounts here, none of them the bank's: an edited image (or a misread)
                seen, mark = ", ".join(f"{x:,.2f}" for x in sorted(nums)), "✗"
        elif how == "name":  # "นาย สมชาย ใ" is in "นาย สมชาย ใจดี"
            score, i = max(((max(_like(_name(n)[0], nm) for n in v), i) for i, nm, _ in names), default=(0, 0))
            if score >= 0.8:
                seen, mark, hit[label] = lines[i], "✓", i
        elif how == "acc" and v:
            i = next((i for i, a in accs if a and _acc_is(_acc(v) or v.upper(), a)), None)
            if i is not None:
                seen, mark, hit[label] = lines[i], "✓", i
        elif how == "date" and v:
            got = [(t, any(_day_is(m, v) for m in DATE.finditer(t)), any(_time_is(m, v) for m in TIME.finditer(t)),
                    bool(DATE.search(t)) and bool(TIME.search(t))) for t in lines]
            day = next((t for t, d, _, _ in got if d), "")
            at = next((t for t, d, ti, _ in got if ti and d), "") or next((t for t, _, ti, _ in got if ti), "")
            if at and (day or not any(DATE.search(t) for t in lines)):  # BAY's date is unreadable: its time
                seen, mark = at if at == day or not day else f"{day} {at}", "✓"
            elif alone and (full := [t for t, _, _, both in got if both]):  # the slip's date and time, not the bank's
                seen, mark = full[0], "✗"
        elif how == "ref" and v:  # some slips print only its start (BAY), TrueMoney another number: never ✗
            r = _ref(v)
            seen = next((t for t in lines if len(x := _ref(t)) >= 10 and (x in r or r in x)
                         or difflib.SequenceMatcher(None, r, x).ratio() >= 0.85), "")
            mark = "✓" if seen else "?"
        out.append([label, seen, shown, under, mark, how, v])
    if alone:  # the 2 lines that look like a name / an account: one is the other party's; this one says otherwise?
        for row in out:
            label, how, v = row[0], row[5], row[6]
            if row[4] != "?" or how not in ("name", "acc") or hit.get(PAIR.get(label)) is None:
                continue
            if how == "name":
                cand = [i for i, nm, titled in names if titled and len(nm) >= 4]
            else:
                cand = [i for i, a in accs if a and ("X" in a or len(a) == len(_acc(v)))]
            rest = [i for i in cand if i != hit[PAIR[label]]]
            if len(rest) != 1:  # the other party found (BAY prints its name untitled), one left: this party's
                continue
            j = rest[0]
            if how == "name":  # Thunder may give the name in English only: never ✗ across scripts
                nm, th = names[j][1], bool(THAI.search(names[j][1]))
                mine = [_name(n)[0] for n in v if bool(THAI.search(n)) == th]
                differs = bool(mine) and all(_like(n, nm) < 0.5 for n in mine)
            else:
                differs = _acc_is(_acc(v), accs[j][1]) is False
            if differs:
                row[1], row[4] = lines[j], "✗"
    return [tuple(r[:5]) for r in out]
