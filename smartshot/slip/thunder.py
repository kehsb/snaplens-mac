"""Bank slips checked with Thunder: the API key, the call, and the fields of its answer."""
import base64
import json
import os
import re
import urllib.error
import urllib.request

import cv2

from smartshot.config import DATA, FROZEN, HERE, TRAY, VERSION
from smartshot.qr.promptpay import BANKS, bank_time, money, phone, thai_time


THUNDER = "https://api.thunder.in.th/v2"  # slip verification, https://document.thunder.in.th/th/v2/
KEY_FILE = (os.path.join(DATA, "thunder.key") if FROZEN  # kept through reinstalls
            else os.path.join(HERE, "thunder.key"))  # git-ignored
NO_KEY = f"ยังไม่มี API key ของ Thunder: ใส่คีย์ที่ ตั้งค่า (เปิดจากไอคอนที่{TRAY}) หรือในไฟล์นี้ แล้วกด ตรวจใหม่"  # + KEY_FILE
THUNDER_ERRORS = {  # error.code -> "what: what to do" for the card (branch on the code: Thunder's messages change)
    "MISSING_API_KEY": NO_KEY,
    "INVALID_API_KEY": f"API key ของ Thunder ไม่ถูกต้อง: แก้ที่ ตั้งค่า (เปิดจากไอคอนที่{TRAY}) หรือในไฟล์นี้ แล้วกด ตรวจใหม่",
    "SLIP_NOT_FOUND": "ไม่พบรายการนี้ในระบบธนาคาร: อาจเป็นสลิปปลอม หรือเก่าเกินกว่าจะตรวจได้ (7-30 วัน)",
    "SLIP_PENDING": "สลิปธนาคารกรุงเทพยังไม่เข้าระบบ (ช่วง 5 นาทีแรก): รอสักครู่แล้วกด ตรวจใหม่",
    "QUOTA_EXCEEDED": "โควต้า Thunder หมดแล้ว", "SERVICE_EXPIRED": "แพ็กเกจ Thunder หมดอายุ",
    "IP_NOT_ALLOWED": "IP เครื่องนี้ไม่อยู่ใน whitelist ของ Thunder", "BRANCH_INACTIVE": "สาขานี้ของ Thunder ถูกปิดใช้งาน",
    "INVALID_IMAGE": "Thunder อ่าน QR สลิป TrueMoney นี้ไม่ได้: ตรวจยอดในแอป TrueMoney Wallet แทน",
    "API_SERVER_ERROR": "ระบบธนาคารหรือ Thunder ขัดข้อง: ลองกด ตรวจใหม่", "INTERNAL_SERVER_ERROR": "Thunder ขัดข้อง: ลองกด ตรวจใหม่",
}


def thunder_key():  # thunder.key (KEY_FILE), else the THUNDER_API_KEY env var; read on every use, no restart
    try:
        with open(KEY_FILE, "rb") as f:
            raw = f.read()
    except OSError:
        return os.environ.get("THUNDER_API_KEY", "").strip()
    # a key file some editors save as UTF-16
    return raw.decode("utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig", "replace").strip()


def store_key(k):  # into thunder.key, which every check reads -> False: not a key (Thunder's are printable ASCII)
    if not (k.isascii() and k.isprintable()):
        return False
    os.makedirs(os.path.dirname(KEY_FILE), exist_ok=True)
    with open(KEY_FILE, "w", encoding="ascii") as f:
        f.write(k)
    return True


def verify_slip(kind, payload):
    """Ask Thunder about a slip -> (data, "") or (None, why not, in Thai). Never raises. Bank slips go by their QR
    payload. TrueMoney takes images only: the code is drawn afresh from its payload and sent alone, so the answer is
    about this code and nothing else on screen is uploaded. checkDuplicate: a slip this key checked before comes
    back flagged, and costs no quota."""
    key = thunder_key()
    if not key:
        return None, NO_KEY
    if not (key.isascii() and key.isprintable()):  # a stray newline would put the key into the error shown
        return None, THUNDER_ERRORS["INVALID_API_KEY"]
    try:
        if kind == "slip":
            url, body = f"{THUNDER}/verify/bank", {"payload": payload}
        else:
            q = cv2.resize(cv2.QRCodeEncoder.create().encode(payload), None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST)
            url, body = f"{THUNDER}/verify/truewallet", {"base64": base64.b64encode(cv2.imencode(".png", q)[1]).decode()}
        req = urllib.request.Request(url, json.dumps({**body, "checkDuplicate": True}).encode(), {
            "Content-Type": "application/json",
            "User-Agent": f"smartshot/{VERSION}"})  # Cloudflare there rejects urllib's default agent (error 1010)
        req.add_unredirected_header("Authorization", f"Bearer {key}")  # urllib re-sends other headers on a redirect
        with urllib.request.urlopen(req, timeout=20) as r:
            res = json.load(r)
    except urllib.error.HTTPError as e:  # API errors are JSON too
        try:
            res = json.load(e)
        except Exception:  # Cloudflare's own pages aren't JSON; the body can also time out
            res = {"error": {"code": f"HTTP {e.code}", "message": str(e.reason)}}
    except Exception:  # offline, timeout, cut-off reply (http.client's errors aren't OSError), not JSON
        return None, "ติดต่อ Thunder ไม่ได้: เช็กอินเทอร์เน็ต แล้วกด ตรวจใหม่"
    res = res if isinstance(res, dict) else {}
    if res.get("success") and isinstance(res.get("data"), dict):
        return res["data"], ""
    err = res.get("error") if isinstance(res.get("error"), dict) else {}
    code = str(err.get("code", ""))
    return None, THUNDER_ERRORS.get(code) or f"Thunder: {code} {err.get('message', '')}".strip()


def dig(o, *keys):  # o[k1][k2]..., or "" where anything is missing: Thunder leaves fields out
    for k in keys:
        o = o.get(k) if isinstance(o, dict) else None
    return "" if o is None else o


def slip_fields(kind, d):
    """Thunder's verified slip -> [(label, kind of field, its value to compare, as shown, under it)], in the slip's order;
    what Thunder left out is dropped. Names come as "title first initial" ("นาย สมชาย ใ"), in Thai and English."""
    def party(p, who):
        a = dig(p, "account")
        names = list(dict.fromkeys(str(n) for n in (dig(a, "name", "th"), dig(a, "name", "en")) if n))
        acc, where = dig(a, "bank", "account"), BANKS.get(dig(p, "bank", "id")) or dig(p, "bank", "short")
        if not acc and dig(a, "proxy", "account"):  # PromptPay (a top-up: an e-wallet id)
            acc, where = dig(a, "proxy", "account"), "e-Wallet" if dig(a, "proxy", "type") == "EWALLETID" else "พร้อมเพย์"
        acc = str(acc)
        return [(who, "name", names, names[0] if names else "", " · ".join(names[1:])),  # a 10-char id is a phone: 3-3-4
                (f"บัญชี{who}", "acc", acc, re.sub(r"^(\w{3})(\w{3})(\w{4})$", r"\1-\2-\3", acc), str(where or ""))]
    s = d.get("rawSlip") or {}
    if kind == "slip":
        amount, ref = dig(s, "amount", "amount"), dig(s, "transRef")
        who = party(dig(s, "sender"), "ผู้โอน") + party(dig(s, "receiver"), "ผู้รับ")
    else:
        amount, ref, r = dig(s, "amount"), dig(s, "transactionId"), dig(s, "receiver")
        sender, receiver, tel = str(dig(s, "sender", "name")), str(dig(r, "name")), str(dig(r, "phone"))
        who = [("ผู้โอน", "name", [sender], sender, ""), ("ผู้รับ", "name", [receiver], receiver, ""),
               ("บัญชีผู้รับ", "acc", tel, phone(tel), "TrueMoney Wallet")]
    amount = amount or d.get("amountInSlip")
    rows = [("ยอดเงิน", "amount", amount, money(amount), "")] + who + [
        ("วันเวลา", "date", bank_time(dig(s, "date")), *thai_time(dig(s, "date"))), ("เลขอ้างอิง", "ref", str(ref), str(ref), "")]
    return [r for r in rows if r[3]]
