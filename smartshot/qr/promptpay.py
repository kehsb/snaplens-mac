"""What a QR says: EMVCo TLV, PromptPay, banks, money and Thai times as slips print them."""
import binascii
import re
from datetime import datetime, timedelta, timezone


AID_PROMPTPAY = ("A000000677010111", "A000000677010114")  # PromptPay transfer: merchant / customer presented
AID_BILL = ("A000000677010112", "A000000677012006")  # PromptPay bill payment: domestic / cross-border
BANKS = {"002": "กรุงเทพ", "004": "กสิกรไทย", "006": "กรุงไทย", "011": "ทีทีบี", "014": "ไทยพาณิชย์", "022": "ซีไอเอ็มบี",
         "024": "ยูโอบี", "025": "กรุงศรี", "030": "ออมสิน", "033": "ธอส.", "034": "ธ.ก.ส.", "066": "อิสลาม", "067": "ทิสโก้",
         "069": "เกียรตินาคินภัทร", "070": "ไอซีบีซี", "071": "ไทยเครดิต", "073": "แลนด์ แอนด์ เฮ้าส์", "098": "SME D"}
BAD_CRC = "⚠ CRC ไม่ตรง: ข้อมูลใน QR อาจถูกแก้ไข"
TH_MONTHS = "ม.ค. ก.พ. มี.ค. เม.ย. พ.ค. มิ.ย. ก.ค. ส.ค. ก.ย. ต.ค. พ.ย. ธ.ค.".split()


def tlv(s):
    """EMVCo data objects: id (2 digits) length (2 digits) value, repeated -> {id: value}; None unless all of s
    parses that way."""
    out, i = {}, 0
    while i < len(s):
        head = s[i:i + 4]
        if len(head) < 4 or not (head.isascii() and head.isdigit()) or i + 4 + int(head[2:]) > len(s):
            return None
        out[head[:2]] = s[i + 4:i + 4 + int(head[2:])]
        i += 4 + int(head[2:])
    return out


def crc_ok(s, tag, v):
    """v: the CRC object's value, which must end s. CRC-16/CCITT-FALSE over everything before it, its own
    'id + 04' included. Some slips drop the CRC's leading zeros ('9103' + '77E'); it was still summed as '04'."""
    return (s.endswith(f"{tag}{len(v):02d}{v}") and re.fullmatch(r"[0-9A-Fa-f]{1,4}", v) is not None
            and int(v, 16) == binascii.crc_hqx((s[:-len(v) - 4] + tag + "04").encode(), 0xFFFF))


def bank(code):
    return BANKS.get(code, code)


def phone(p):
    return f"{p[:3]}-{p[3:6]}-{p[6:]}" if len(p) == 10 and p.isdigit() else p


def money(v, currency="764"):
    try:
        amount = f"{float(v):,.2f}"
    except (TypeError, ValueError):
        return str(v or "")
    return f"{amount} บาท" if currency in ("764", "THB") else f"{amount} ({currency})"


def bank_time(iso):  # Thunder's ISO time -> datetime in Thai time, as on the slip, whatever this PC's zone; or None
    try:
        d = datetime.fromisoformat(str(iso))
    except ValueError:
        return None
    return d.astimezone(timezone(timedelta(hours=7))) if d.tzinfo else d


def thai_time(iso):  # -> ("1 ม.ค. 2569 · 09:00 น.", "45 นาทีก่อน"): as slips print it, and how old it is
    if (d := bank_time(iso)) is None:
        return str(iso or ""), ""
    m = int((datetime.now(d.tzinfo) - d).total_seconds() // 60)
    ago = "" if m < 0 else "เมื่อสักครู่" if m < 1 else f"{m} นาทีก่อน" if m < 60 else \
        f"{m // 60} ชั่วโมงก่อน" if m < 1440 else f"{m // 1440} วันก่อน"
    return f"{d.day} {TH_MONTHS[d.month - 1]} {d.year + 543} · {d:%H:%M} น.", ago


def proxy(k, v):  # who a PromptPay QR pays: 01 mobile (0066...), 02 national / tax ID, 03 e-wallet, 04 bank account
    if k == "01":
        return "เบอร์โทร", phone("0" + v[4:] if v.startswith("0066") else v)
    if k == "02":
        return "เลขบัตรประชาชน / ผู้เสียภาษี", f"{v[0]}-{v[1:5]}-{v[5:10]}-{v[10:12]}-{v[12]}" if len(v) == 13 else v
    if k == "03":
        return ("TrueMoney Wallet", phone(v[5:])) if v.startswith("14000") else ("e-Wallet ID", v)
    return ("บัญชีธนาคาร", f"{bank(v[:3])} {v[3:]}") if k == "04" else ("ผู้รับ", "-")


def qr_info(s):
    """What a QR payload is, for people -> (kind, title, [(label, value)], warning or ""). Thai QR Payment
    (BOT, EMVCo), the slip "mini QR", TrueMoney slips, bill barcodes, links, text. Only kind "slip" (bank
    transfer) and "truemoney" can be checked with Thunder: every other kind carries all it has in the code."""
    s = s.strip()
    t = tlv(s) or {}
    if "91" in t and set(t) <= {"00", "51", "91"} and t.get("51", "TH") == "TH":  # a slip's QR
        sub, warn = tlv(t.get("00", "")) or {}, "" if crc_ok(s, "91", t["91"]) else BAD_CRC
        if sub.get("00", "000001") == "000001" and sub.get("02"):  # BOT slip verification (old SCB ones: no 00/01)
            rows = [("จาก", bank(sub["01"]))] if "01" in sub else []
            return "slip", "สลิปโอนเงิน", rows + [("เลขอ้างอิง", sub["02"])], warn
        if sub.get("00") == "01" and sub.get("01") == "01":  # TrueMoney Wallet (no official spec: as seen)
            d = sub.get("04", "")
            return "truemoney", "สลิป TrueMoney Wallet", [("รายการ", sub.get("02", "")), ("เลขที่", sub.get("03", "")),
                                                          ("วันที่", f"{d[:2]}/{d[2:4]}/{d[4:]}")], warn
    if t.get("00") == "01" and "63" in t:  # EMVCo merchant-presented: Thai QR Payment / PromptPay
        warn = "" if crc_ok(s, "63", t["63"]) else BAD_CRC
        pp, bill = tlv(t.get("29", "")) or {}, tlv(t.get("30", "")) or {}
        tail = [("จำนวนเงิน", money(t["54"], t.get("53", "764")))] if "54" in t else []
        tail += [("ชื่อ", t["59"])] if "59" in t else []
        if pp.get("00") in AID_PROMPTPAY:
            k = next((k for k in ("01", "02", "03", "04") if k in pp), "")
            return "promptpay", "พร้อมเพย์ (รับเงิน)", [proxy(k, pp.get(k, ""))] + tail, warn
        if bill.get("00") in AID_BILL:
            refs = [("Biller ID", bill.get("01", "")), ("Ref 1", bill.get("02", "")), ("Ref 2", bill.get("03", ""))]
            return "bill", "Thai QR จ่ายบิล", [r for r in refs if r[1]] + tail, warn
        return "emv", "QR รับชำระเงิน (EMVCo)", tail + ([("เมือง", t["60"])] if "60" in t else []), warn
    if s.startswith("|"):  # BOT bill-payment barcode as a QR: |biller CR ref1 CR ref2 CR amount in satang
        f = (re.split(r"\r\n?|\n", s[1:]) + [""] * 4)[:4]
        rows = [r for r in (("Biller ID", f[0]), ("Ref 1", f[1]), ("Ref 2", f[2])) if r[1]]
        amount = re.fullmatch(r"[0-9]{1,15}", f[3]) and int(f[3])  # not isdigit(): '²' and 400 digits pass it, int() / 100 raises
        return "bill", "บาร์โค้ดจ่ายบิล", rows + ([("จำนวนเงิน", money(amount / 100))] if amount else []), ""
    if re.match(r"[a-z][a-z0-9+.-]*:\S", s, re.I):
        return "url", "ลิงก์", [("", s)], ""
    return "text", "ข้อความ", [("", s)], ""
