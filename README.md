# Snaplens for macOS

แอปแถบเมนูสำหรับแคปหน้าจอแล้ว **อ่านข้อความ (OCR) จีน อังกฤษ ไทย และแปลทับลงบนภาพ** ตรงตำแหน่งเดิม
อ่าน QR code ในภาพได้ (PromptPay และอื่นๆ) และตรวจสลิปโอนเงินกับธนาคารผ่าน [Thunder API](https://document.thunder.in.th/th/v2/)

- กด **⌃⌥S** (Control+Option+S) หรือคลิกไอคอนที่แถบเมนู เพื่อแคป
- ลากเลือกพื้นที่ หรือคลิกเลือกกรอบที่ไฮไลต์ แล้ว OCR จะเริ่มอ่านทันที
- เลือกบรรทัดแล้วแปล, วาด, เบลอ, คัดลอกรูป (⌘C) หรือบันทึก (⌘S)
- คลิกขวาที่ไอคอนเพื่อเปิดเมนู: เลือกภาษาที่อ่าน และเปิดหน้าตั้งค่า

OCR ทำงานในเครื่องด้วย [RapidOCR](https://github.com/RapidAI/RapidOCR) (PP-OCR บน onnxruntime) ส่วนการแปลส่งข้อความที่เลือกไปยังบริการแปลออนไลน์

## ความต้องการ

- macOS 12 ขึ้นไป (ทดสอบบน macOS 26, Apple Silicon)
- Python 3.13 (เช่น `brew install python@3.13`) สำหรับรันจากซอร์สหรือ build

## รันจากซอร์ส

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

ครั้งแรกจะดาวน์โหลดโมเดล OCR (หลายสิบ MB) `./dev.sh` รันแบบรีสตาร์ตเองเมื่อแก้ไฟล์

## Build เป็นแอป

```bash
./build.sh
```

ได้ `dist/Snaplens.app` และ `installer/Snaplens-<version>.dmg`

แอปเซ็นด้วย certificate ที่ `build.sh` สร้างไว้ใน login keychain ของเครื่องนั้นเอง (ชื่อ "Snaplens Local Signing") จึงให้สิทธิ์บันทึกหน้าจอครั้งเดียวแล้วใช้ได้ทุก build
ไม่ได้เซ็นด้วย Apple Developer ID: เครื่องอื่นต้องคลิกขวา > Open ตอนเปิดครั้งแรก

## สิทธิ์ที่ต้องให้

- **การบันทึกหน้าจอ** (การตั้งค่าระบบ > ความเป็นส่วนตัวและความปลอดภัย > การบันทึกหน้าจอ): ครั้งแรกที่แคประบบจะถาม ให้อนุญาตแล้ว**เปิดแอปใหม่**
- คีย์ลัดใช้ระบบคีย์ลัดของ macOS ไม่ต้องให้สิทธิ์ Accessibility หรือ Input Monitoring

ถ้าสิทธิ์ค้างหรือใช้ไม่ได้ ล้างแล้วให้ใหม่:

```bash
tccutil reset ScreenCapture io.github.kehsb.snaplens
```

## ตรวจสลิป

ใส่ Thunder API key ที่ ตั้งค่า > Thunder API key (เก็บที่ `~/Library/Application Support/smartshot/thunder.key`)
ตอนรันจากซอร์สจะอ่านจาก `thunder.key` ในโฟลเดอร์โปรเจกต์ หรือตัวแปร `THUNDER_API_KEY`

## โครงสร้าง

| โฟลเดอร์ | หน้าที่ |
|---|---|
| `app.py` | จุดเริ่ม: แอปเดียว ไม่มี Dock icon |
| `smartshot/ui/` | `main.py` แอปและเมนู, `settings.py` หน้าตั้งค่า (AppKit), `overlay.py` หน้าแคป |
| `smartshot/system/` | `mac.py` (AppKit, Quartz, Carbon): จับภาพ, คีย์ลัด, หน้าต่างเหนือแถบเมนู; `autostart.py` |
| `smartshot/ocr/`, `qr/`, `slip/` | OCR และแปล, อ่าน QR, ตรวจสลิป |

## License

[MIT](LICENSE) · ฟอนต์ Anuphan และ Geist Mono ใช้ [SIL Open Font License](assets/fonts/)
