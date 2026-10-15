**English** | [ภาษาไทย](README.th.md)

<p align="center">
  <img src="assets/icons/app-256.png" width="128" height="128" alt="Snaplens app icon">
</p>

<h1 align="center">Snaplens</h1>

<p align="center">
  <b>Capture part of your screen, read it, and see the translation where the text was.</b>
  <br>
  A macOS menu bar app for screen captures: it reads Chinese, English and Thai on your Mac, translates in place,
  lets you mark up the capture and explains the QR codes in it.
</p>

<p align="center">
  <a href="https://github.com/kehsb/snaplens-mac/releases/latest"><img src="https://img.shields.io/github/v/release/kehsb/snaplens-mac?label=release" alt="Latest release"></a>
  <img src="https://img.shields.io/badge/macOS-26%20Tahoe-000000?logo=apple&logoColor=white" alt="macOS 26 Tahoe">
  <img src="https://img.shields.io/badge/Apple%20Silicon-arm64-000000" alt="Apple Silicon (arm64) only">
  <img src="https://img.shields.io/badge/UI-Thai-0A84FF" alt="Interface language: Thai">
  <a href="LICENSE"><img src="https://img.shields.io/github/license/kehsb/snaplens-mac" alt="Source code license: MIT"></a>
</p>

<p align="center">
  <a href="https://github.com/kehsb/snaplens-mac/releases/download/v0.17.1/Snaplens-0.17.1.dmg"><img src="https://img.shields.io/badge/Download%20for%20Mac-Snaplens%200.17.1-0A84FF?style=for-the-badge&logo=apple&logoColor=white" alt="Download Snaplens 0.17.1 for Mac"></a>
  <br>
  <sub>Snaplens-0.17.1.dmg · about 170 MB · macOS 26 Tahoe · Apple Silicon ·
  <a href="https://github.com/kehsb/snaplens-mac/releases/latest">Latest release</a> ·
  <a href="#install">Install guide</a></sub>
</p>

<p align="center">
  <a href="#features">Features</a> ·
  <a href="#install">Install</a> ·
  <a href="#usage">Usage</a> ·
  <a href="#keyboard-and-mouse">Shortcuts</a> ·
  <a href="#privacy-and-permissions">Privacy</a> ·
  <a href="#faq-and-troubleshooting">FAQ</a> ·
  <a href="#build-from-source">Build from source</a>
</p>

> [!NOTE]
> **The Snaplens interface is in Thai.** This README is in English; there is also a [Thai version](README.th.md).
> Wherever it names an on-screen label, it gives the Thai text and its English meaning, so you can find each control.

<p align="center">
  <img src="docs/images/capture.png" width="820" alt="Snaplens on a macOS desktop. A Chinese product page in a window is selected under the Liquid Glass capture toolbar, and every line in the selection is painted over with its Thai translation in place.">
  <br>
  <sub>A Chinese shop page, translated into Thai where the text was. Demo pages and data throughout.</sub>
</p>

## Features

- **Translation in place.** Each translated line is painted over the original, on a box filled to match its
  background, so the layout stays intact. Translate into Thai (the default), English, Simplified Chinese,
  Traditional Chinese, Japanese, Korean or Vietnamese.
- **OCR on your Mac.** Chinese, English and Thai are read locally by [RapidOCR](https://github.com/RapidAI/RapidOCR),
  which runs PaddleOCR (PP-OCR) models on ONNX Runtime. Screenshots are never uploaded.
- **Every display, one shortcut.** **⌃⌥S** freezes each display at full Retina resolution, above the menu bar and
  Dock, on any Space and over full-screen apps.
- **Snipaste-style panel picking.** Snaplens finds boxes in the pixels. Hover and click to select one, scroll to step
  out to a larger panel, or drag your own region. An 8× magnifier shows pixel coordinates and colour.
- **Markup.** Pen, highlighter, rectangle, arrow, text and mosaic, in five colours and four sizes, with undo. Copy the
  result (**⌘C**) or save it as PNG or JPEG (**⌘S**).
- **QR codes.** Every QR code in the selection is decoded and boxed, and a card beside the selection says what each
  one holds: links, text, PromptPay, Thai QR bill payments, EMVCo merchant codes and the mini-QRs on bank and
  TrueMoney slips. Copy what the card says, or open a web link in your browser. Payment and slip codes that fail their
  CRC check get a warning.
- **Native macOS UI.** A Liquid Glass capture toolbar, a Settings window styled like System Settings, Notification
  Center notices and no Dock icon. The global shortcut uses Carbon, so no Accessibility or Input Monitoring
  permission is needed.
- **No telemetry.** No analytics, no crash reporting and no update checks.

Looking for slip verification? Checking Thai bank slips with the Thunder API is no longer part of Snaplens. It lives on
the [`ThunderAPI`](https://github.com/kehsb/snaplens-mac/tree/ThunderAPI) branch, and its last build is
[Snaplens 0.16.0](https://github.com/kehsb/snaplens-mac/releases/tag/v0.16.0).

## Install

### Requirements

| | Prebuilt app (DMG) | From source |
|---|---|---|
| **Mac** | Apple Silicon (arm64) only | Apple Silicon (the pinned wheels are arm64) |
| **macOS** | **macOS 26 Tahoe** (tested on 26.7.1) | 14 or later per the wheel tags (PySide6's Qt bindings target 15). Only 26 has been tested. |
| **Python** | Bundled | 3.13 (`brew install python@3.13`) |
| **Disk** | About 170 MB download, about 365 MB installed | |
| **Internet** | For translation | The same, plus a one-time OCR model download (about 56 MB) |

> [!NOTE]
> The app's `Info.plist` declares macOS 12, but the bundled Python and its libraries are built for macOS 26.
> **The DMG does not run on macOS versions before 26.**

### Download

| | |
|---|---|
| **Latest release** | <https://github.com/kehsb/snaplens-mac/releases/latest> |
| **Snaplens 0.17.1** | [Snaplens-0.17.1.dmg](https://github.com/kehsb/snaplens-mac/releases/download/v0.17.1/Snaplens-0.17.1.dmg) (about 170 MB, Apple Silicon) |
| **SHA-256** | `c0d2e9cdef86a3e1c7036f9f6862b8bdcfe6862483163fbea1321b968aa86138` |

To verify the download:

```bash
shasum -a 256 ~/Downloads/Snaplens-0.17.1.dmg
# c0d2e9cdef86a3e1c7036f9f6862b8bdcfe6862483163fbea1321b968aa86138
```

### First launch

1. Open the DMG and drag **Snaplens** onto **Applications**.
2. Open Snaplens. macOS blocks the first launch because the app is not notarized. Open
   **System Settings > Privacy & Security**, scroll down, click **Open Anyway** next to the Snaplens message, then
   authenticate and confirm **Open**.
3. Press **⌃⌥S** and allow **Screen Recording** when macOS asks
   (**System Settings > Privacy & Security > Screen & System Audio Recording**). Then quit Snaplens from its menu bar
   icon (**ออกจาก Snaplens**, Quit) and **open it again**.

Snaplens lives in the menu bar. It posts a **พร้อมแล้ว** (Ready) notification once the OCR models have loaded; macOS
asks whether Snaplens may send notifications the first time it posts one.

> [!IMPORTANT]
> **Why macOS warns you.** Releases are signed with a self-signed certificate ("Snaplens Local Signing"), not an
> Apple Developer ID. They are not notarized and do not use the hardened runtime, so Gatekeeper blocks them until you
> click **Open Anyway**. Advanced users can clear the quarantine flag instead:
> `xattr -dr com.apple.quarantine /Applications/Snaplens.app`

### Updating

Snaplens does not update itself or check for updates. To hear about new versions, watch this repository
(**Watch > Custom > Releases**). To update, quit Snaplens, download the new DMG and replace the app in Applications.

The Screen Recording permission is tied to the app's signing identity, so it carries over only if the new release is
signed with the same certificate. If capture stops working after an update, reset the permission as described in the
[FAQ](#faq-and-troubleshooting).

## Usage

### Quick start

1. Press **⌃⌥S**, or choose **แคปหน้าจอ** (Capture screen) from the menu bar icon. Every display freezes.
2. Drag a region, or hover over a highlighted panel and click it.
3. OCR starts straight away and outlines each line it finds. QR codes are read at the same time and explained on a
   card beside the selection.
4. Click lines (or press **⌘A**) to translate them, or press the blue **แปล** (Translate) button for every line.
   **▾** picks the target language.
5. Mark it up if you like, then press **⌘C** to copy the image and close, **⌘S** to save it, or **Esc** to close.

### Selecting an area

The hint bar at the top reads *ลาก เลือกพื้นที่ · คลิก เลือกช่องที่ไฮไลต์ · ล้อเมาส์ ขยาย/ย่อ · Esc ปิด*: drag to
select an area · click a highlighted box · mouse wheel to grow or shrink · Esc to close.

- **Panels.** Hovering previews the panel under the cursor in a dashed frame labelled *คลิกเพื่อเลือก* (click to
  select). Click to select it. Scroll up to step out to the enclosing panel, and down to step back in. Detection is a
  heuristic, so drag by hand if it misses.
- **Free selection.** Drag any region. A tag shows its size in screenshot pixels and the current status. The
  magnifier shows the pixel coordinates and `#RRGGBB` colour under the cursor.
- **Resizing.** Drag an edge or a corner; hold **⇧ Shift** to keep the aspect ratio. Snaplens reads the new area again
  and keeps the translations it already has.
- **Cancelling.** Before a selection is made, right-click drops a half-drawn selection or closes the capture.

### Translating

<p align="center">
  <img src="docs/images/translate.png" width="640" alt="Close-up of a selection on a Chinese product page: the title, the warranty line and four feature lines are each replaced in place by their Thai translations, on boxes that match the page background. The prices are left as they are.">
  <br>
  <sub>Each line keeps its place and size; numbers and prices stay as they are.</sub>
</p>

- **Selecting lines translates them.** Click a line to select it, **⌘-click** to add or remove one, **⌘-drag** or a drag
  band to add several, and **⌘A** for all of them. Right-clicking an unselected line selects and translates it too.
- **The แปล (Translate) button** translates the selected lines, or every line if none is selected. **▾** opens the
  target-language menu (*แปลเป็น*). Picking a language translates straight away: a new language redoes the lines
  already translated, and if there are none, or you pick the current language again, it translates the selected lines
  (or all lines) like แปล. The target applies to every screen and resets to Thai at the next launch.
- **How translations look.** Each line gets an opaque box filled with the average colour of its corners, with dark or
  light text. The font first shrinks to as little as 65% of the line height to stay on one line. If the text still
  does not fit, it wraps downward into the space above the next line, and shrinks further only if that space runs out
  (down to 7 px, where a very long translation can still overlap the next line).
- **Lines that are skipped:** fragments with fewer than two letters, Thai lines when the target is Thai, and pinyin:
  any line containing a vowel with a pinyin tone mark, such as á, è or ǚ, so a word like *café* also skips its line.
- **The eye button** switches between the original and the translation once a translation has arrived. While it shows
  the original, selecting lines does not translate them.
- **Copy text** copies the selected lines (or all) as they are shown: translations if visible, otherwise the
  originals. It has no keyboard shortcut; use the toolbar button or the context menu.

### Reading modes

| Mode (Thai label) | What it does |
|---|---|
| Auto (อัตโนมัติ) | Runs the Chinese and Thai recognizers on every line and keeps the higher-scoring result |
| Chinese + English (จีน+อังกฤษ) | Chinese and English recognizer only |
| Thai (ไทย) | Thai recognizer only |

Change the mode from **ภาษาที่อ่าน** (Reading language) in the menu bar menu, or in Settings. It resets to Auto at
every launch. OCR is built and tested for **Chinese, English and Thai**. The Chinese model also reads some Japanese
(its character set includes kana), but Korean and Vietnamese are translation targets only.

### Toolbar and markup

| Group | Buttons |
|---|---|
| **Tools** | Select text (เลือกข้อความ) · Pen (ปากกา) · Highlighter (ปากกาเน้นข้อความ) · Rectangle (สี่เหลี่ยม) · Arrow (ลูกศร) · Text (พิมพ์ข้อความ) · Mosaic (เบลอ (โมเสก)) |
| **Ink** | Colour dot: colour and size · Undo (⌘Z) |
| **Translate** | **แปล · *language*** translates the selected lines, or all lines · **▾** picks the target language |
| **View** | Eye: original / translation · Copy text · Copy image and close (⌘C) · Save image (⌘S) |
| **Close** | ปิด (Esc) |

- **Colours and sizes.** Five colours (red by default, yellow, green, blue, white) and four sizes (0.6×, 1×, 1.6× and
  2.5× of each tool's base size). Right-click or ⌃-click a tool, or click the colour dot, to change them. The ink
  colour is shared by all tools and starts as red in every new capture. Each tool keeps its own size until you quit.
- **Text tool.** Type where you clicked. **Enter**, or a click elsewhere, places the text; **Esc** discards it.
- **Undo.** **⌘Z** undoes the last drawing. There is no redo.
- **Your drawings are protected.** Once you have drawn something, a stray click outside the selection does nothing.
- **Context menu.** With the Select tool, right-click the selection to translate, copy text, copy the image and close,
  save the image, start a new selection (*เลือกพื้นที่ใหม่*) or close. With a drawing tool, right-click opens the
  colour and size popover instead.
- **Copying and saving.** **⌘C** copies the crop with its translations and drawings, without selection marks, and
  closes the capture. **⌘S** saves it as PNG or JPEG (default `snaplens.png` in Pictures) and closes the capture once
  saved. Until you quit, the last folder you saved an image to is offered next.

### QR codes

<p align="center">
  <img src="docs/images/qr.png" width="820" alt="A café page selected in the capture overlay. Its QR code is boxed in blue with a QR badge, and a Liquid Glass card beside the selection says it is a link to https://example.com/menu, with Copy and Open link buttons.">
</p>

Snaplens decodes every QR code in the selection, retrying small or blurred ones. Each code is boxed in blue on the
image: a lone code gets a QR badge, and several are numbered top to bottom, as on the card. When it finds codes, the
size tag says *พบ QR N รายการ* (N QR codes found). The boxes are on-screen guides, shown while the Select tool is on:
copying or saving the image leaves them out.

A card beside the selection says what each code holds:

| QR type | Card title | What you see |
|---|---|---|
| Link | ลิงก์ | The link as text. A web link also gets an **เปิดลิงก์** (Open link) button |
| Anything else | ข้อความ | The text |
| PromptPay | พร้อมเพย์ (รับเงิน) | Recipient (phone, national ID or tax ID, e-wallet, or bank account), amount and name |
| Thai QR bill payment / bill barcode | Thai QR จ่ายบิล / บาร์โค้ดจ่ายบิล | Biller ID, Ref 1, Ref 2 and amount |
| Other EMVCo merchant QR | QR รับชำระเงิน (EMVCo) | Amount, merchant name and city, when the code has them |
| Bank-transfer slip (mini-QR) | สลิปโอนเงิน | Sending bank and reference, which is all the code holds |
| TrueMoney Wallet slip | สลิป TrueMoney Wallet | Transaction, number and date; the format is inferred from real slips, as there is no official spec |

- **Payment QRs** (PromptPay, bill payment and EMVCo) are labelled *QR นี้ใช้จ่ายเงิน* ("this QR is for paying").
- **CRC check.** If a payment or slip code fails its CRC-16/CCITT check, the card warns in red that the data may have
  been altered.
- **Bank names** are shown for 18 Thai bank codes.
- **Slip codes are read, not verified.** The card shows what the code says; it cannot tell whether the transfer
  happened.

Using the card:

- **คัดลอก** (Copy) copies what the card says as text: each code's title, fields and warning, plus the raw payload
  (`QR: …`) for payment and slip codes. The capture stays open.
- **เปิดลิงก์** (Open link) appears when the selection holds a single code that is a web link (`http://` or
  `https://`). It closes the capture, as Esc does, and opens the link in your default browser. Other schemes, such as
  `javascript:`, `file:` or app links, never get the button.
- **Field values** such as phone numbers, references and amounts can be selected; **⌘C** then copies the selected
  text. A click on the image gives the keys back to the capture.
- **Several codes** are listed in one card, numbered like their badges and separated by a line.

## Keyboard and mouse

⌘ Command · ⌃ Control · ⌥ Option · ⇧ Shift

| Input | Action |
|---|---|
| **⌃⌥S** | Start a capture from any app (changeable in Settings) |
| **Esc** | Discard text being typed, else close the colour popover, else close the capture |
| **⌘A** | Select every line, switch to the Select tool and translate |
| **⌘C** | Copy the image (with translations and drawings) and close. With text selected on the QR card, copy that text |
| **⌘S** | Save the image as PNG or JPEG |
| **⌘Z** | Undo the last drawing |
| **⌘-click** / **⌘-drag** | Add or remove a line / add lines to the selection |
| **⇧ Shift** + drag an edge or corner | Resize, keeping the aspect ratio |
| **Scroll wheel** (before selecting) | Step out to the enclosing panel, or back in |
| **Enter** | Place text (Text tool) |
| **Right-click** | Select tool: context menu. Drawing tool: colour and size. Before a selection: cancel it, or close |
| **⌃-click** on the toolbar | Same as right-click |
| **⌘,** / **⌘Q** | Settings / Quit, from the menu bar menu. During a capture ⌘, and ⌘H do nothing; ⌘Q still quits |

The shortcut is bound to physical key positions, so **⌃⌥S** works while the Thai keyboard layout is active.

## Settings

<p align="center">
  <img src="docs/images/settings.png" width="600" alt="The Snaplens settings window in dark mode on the macOS Sonoma wallpaper, styled like System Settings. It shows the Control-Option-S shortcut, reading mode set to Auto, and the Open at login switch.">
</p>

The menu bar menu has **แคปหน้าจอ** (Capture screen), **ภาษาที่อ่าน** (Reading language), **ตั้งค่า…** (Settings, ⌘,)
and **ออกจาก Snaplens** (Quit, ⌘Q). Opening Snaplens again while it runs also brings up Settings. The sidebar shows
the version, the current shortcut, and whether the OCR models are ready.

| Section | Setting |
|---|---|
| **การแคป** (Capture) | **คีย์ลัดแคปหน้าจอ** (capture shortcut) · **ภาษาที่อ่าน** (reading mode) |
| **ทั่วไป** (General) | **เปิดเมื่อเข้าสู่ระบบ** (Open at login) |

- **Changing the shortcut.** Click **เปลี่ยน…** (Change), press the new combination, then release all keys to save it;
  Esc cancels. It must use ⌃ or ⌘ with another key, or be an F-key, alone or with other modifiers. ⌘ cannot be the
  only modifier, because it clashes with app menus, and Tab and ⌘/⌃-Space are not allowed. If the system or another app already uses the
  combination, Snaplens silently falls back to ⌃⌥S.
- **Open at login** registers the login item built into the app with macOS, so it is listed as **Snaplens** in
  **System Settings > General > Login Items & Extensions**, where it can also be switched off. At login it starts the
  app with `--startup` (the Ready notification is then skipped). If macOS refuses that item, Snaplens falls back to a
  plain Open at Login entry, which starts it as if opened by hand, Ready notification included.
- **When macOS needs your approval**, or Snaplens is switched off in System Settings, the switch stays on and the line
  under it turns red: *อนุญาต Snaplens ใน การตั้งค่าระบบ > ทั่วไป > รายการเข้าสู่ระบบ* (allow Snaplens in System
  Settings > General > Login Items). If approval is still needed when you turn the switch on, Snaplens opens that page.
- **From source**, the switch is greyed out and reads *ใช้ได้เมื่อเปิดจากแอปที่ติดตั้ง* (works when opened from the
  installed app).
- **Only the shortcut is remembered** between launches. The reading mode resets to Auto, the target language to Thai,
  and tool sizes to their defaults (the ink colour already resets with every capture).
- **Closing Settings** only hides the window. The first time you close it after each launch, Snaplens posts a notice
  that it is still in the menu bar.

## Privacy and permissions

### Permissions

| Permission | Needed? | Notes |
|---|---|---|
| **Screen Recording** | Required | macOS asks on the first capture. After allowing it, reopen Snaplens. |
| **Notifications** | Optional, built app only | Asked the first time a notice is sent. If denied, or when running from source, notices appear as an in-app panel at the top right that closes after 5 seconds or on a click. |
| Accessibility / Input Monitoring | **Not needed** | The shortcut uses Carbon `RegisterEventHotKey`. |

### What leaves your Mac

**Local only:** screen capture, OCR, QR decoding and panel detection. Screenshots are never uploaded. The complete
list of network requests:

| What | When | Sent to | What is sent |
|---|---|---|---|
| Translation | When you press แปล, **pick a language from ▾, or select lines**, including ⌘A and right-clicking a line (selecting does not translate while the eye shows originals) | Google Translate's unofficial web endpoint (`https://translate.google.com/m`) | The text of the lines that need translating, in the URL query string, and the target language. Normally one request for all lines; if Google's reply has a different number of lines, each line is sent to Google again on its own |
| Translation fallback | If the Google request fails, including when the text is 5,000 characters or more, or a per-line Google retry fails | MyMemory (`http://api.mymemory.translated.net/get`, redirected to HTTPS) | Each line (cut to 490 characters, four at a time) and a guessed source language. **The first request goes over plain HTTP** |
| OCR models | First launch from source, and `build.sh` | ModelScope | Nothing of yours: it downloads about 56 MB of model files. The DMG already includes them |

**เปิดลิงก์** (Open link) on the QR card hands a web link to your default browser, which loads it; Snaplens itself
sends nothing. There is no telemetry, analytics, crash reporting or update check. Translation errors are printed to
stderr only.

### What is stored

| Data | Location |
|---|---|
| Preferences (the shortcut, and which build registered the login item) | `~/Library/Preferences/io.github.kehsb.snaplens.plist` |
| Login item (when enabled) | Registered with macOS and listed as Snaplens in **System Settings > General > Login Items & Extensions**. Its launchd agent stays inside the app: `Snaplens.app/Contents/Library/LaunchAgents/io.github.kehsb.snaplens.plist` |
| Images | Only where you save them |

**Upgrading from a version that used the internal name `smartshot`** (releases up to and including the published
0.17.0). The first time the new version starts, it copies your shortcut out of
`~/Library/Preferences/com.smartshot.smartshot.plist`. Once the old app is no longer installed in `/Applications` or
`~/Applications`, it also deletes that file. Once it has replaced the old app in the same place (for example
`/Applications`), it also replaces the old login item, `~/Library/LaunchAgents/smartshot.plist`, with the new one.
`~/Library/Application Support/smartshot`, left by 0.16.0 and earlier, has to be deleted by hand (see
[Uninstall](#uninstall)).

## FAQ and troubleshooting

**macOS says Snaplens can't be opened.**
It is not notarized. Go to **System Settings > Privacy & Security** and click **Open Anyway** (see
[First launch](#first-launch)).

**⌃⌥S shows *ต้องอนุญาตให้บันทึกหน้าจอก่อน* (Screen Recording permission needed), or capture stopped working after an update.**
Enable Snaplens under **System Settings > Privacy & Security > Screen & System Audio Recording**, then quit and reopen
it. If that does not help, reset the permission, reopen Snaplens and allow it again:

```bash
tccutil reset ScreenCapture io.github.kehsb.snaplens
```

**My custom shortcut does nothing, or it is back to ⌃⌥S.**
The combination is probably taken by the system or another app, so Snaplens fell back to ⌃⌥S. The menu bar icon's
tooltip and the Settings sidebar show the shortcut in use. Pick a different combination.

**Some text isn't recognized.**
OCR is built for Chinese, English and Thai. If you see *อ่านข้อความไม่ได้ · ลองขยายพื้นที่* (couldn't read any text,
try a larger area), enlarge the selection or switch the reading mode.

**Translation failed or stopped working.**
Translation uses Google Translate's unofficial web endpoint, with the MyMemory free tier (about 5,000 characters a
day) as a fallback. Either can be rate-limited or change without notice. Try again later, or translate fewer lines at
a time.

**A QR code is not found.**
Make sure the whole code is inside the selection. Very small or heavily blurred codes can be missed: zoom in on the
page and capture again.

**The เปิดลิงก์ (Open link) button is missing.**
It appears only when the selection holds a single QR code and that code is a web link starting with `http://` or
`https://`. With several codes, select just the one you want, or use **คัดลอก** (Copy).

**Open at login stopped working.**
Look at the line under **เปิดเมื่อเข้าสู่ระบบ** in Settings. If it is red, Snaplens is switched off or not yet
allowed in **System Settings > General > Login Items & Extensions**: switch it on there. If you moved the app, turn
**เปิดเมื่อเข้าสู่ระบบ** off and on again.

**Does it run on Intel Macs or macOS 15?**
No. The release supports Apple Silicon and macOS 26 only.

**Is there an English interface?**
No. The interface is in Thai only.

**Why is the download so large?**
The app bundles its own Python runtime, Qt, OpenCV, ONNX Runtime and the OCR models, so it needs no further downloads.

## Known limitations

- **Platform.** Apple Silicon only, macOS 26 only for the release build, Thai interface only.
- **Distribution.** Not notarized, so every install goes through **Open Anyway**. No automatic updates. Granting
  Screen Recording requires a relaunch.
- **Translation** relies on an unofficial Google endpoint and the MyMemory free tier, so it can be rate-limited or
  break. The fallback guesses the source language as Chinese, Thai or English only.
- **OCR** is built for Chinese, English and Thai only, works on the still image taken when you press the shortcut, and runs
  one recognition at a time.
- **QR codes.** TrueMoney slip codes are parsed from observed slips, not a published spec. Slip codes are only read,
  never verified.
- **The QR card does not scroll.** About five payment codes fit on a 1080p screen; more run past the bottom.
- **Panel detection** is a heuristic. If it misses, use the scroll wheel or drag by hand.
- **Not built (yet):** redo, scrolling or window capture, capture history.
- **No automated tests or CI.**

## Uninstall

1. Turn off **เปิดเมื่อเข้าสู่ระบบ** (Open at login) in Settings before you delete the app (if the app is already
   gone, switch Snaplens off in **System Settings > General > Login Items & Extensions** instead), then quit Snaplens
   (**ออกจาก Snaplens**, ⌘Q).
2. Delete the app and its settings, and reset the Screen Recording permission:

```bash
rm -rf /Applications/Snaplens.app
rm -f ~/Library/Preferences/io.github.kehsb.snaplens.plist
tccutil reset ScreenCapture io.github.kehsb.snaplens
```

Older versions may have left files of their own. If `~/Library/Preferences/com.smartshot.smartshot.plist` or
`~/Library/LaunchAgents/smartshot.plist` is still there (left by the versions that used the internal name `smartshot`),
delete it too.
If you used 0.16.0 or earlier, also delete `~/Library/Application Support/smartshot` if it is there: those versions
kept their slip-check key in it.

## Build from source

You need an Apple Silicon Mac and Python 3.13 (`brew install python@3.13`). The pinned packages need macOS 14 or later
and PySide6's binaries target macOS 15; only macOS 26 has been tested.

```bash
git clone https://github.com/kehsb/snaplens-mac.git
cd snaplens-mac
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

- The first launch downloads the OCR models (about 56 MB) from ModelScope into the virtual environment.
- From source, the **Screen Recording permission goes to the terminal or IDE** that runs Python, not to Snaplens.
- Notices appear as the in-app panel instead of Notification Center.
- `./dev.sh` restarts the app whenever `app.py` or anything in `snaplens/` changes.
- **Open at login** works only in the built app; from source its switch is greyed out. If you turned it on while
  running a version that used the internal name `smartshot` (up to 0.17.0) from source, delete
  `~/Library/LaunchAgents/smartshot.plist`: nothing removes it for you, and it keeps starting `app.py` at login.
- While an old `smartshot` copy is running, `python app.py` hands over to it instead of starting a second one.

### Build the app and DMG

```bash
./build.sh
```

> [!WARNING]
> `build.sh` changes your system. On its first run it **adds a self-signed code-signing certificate** ("Snaplens Local
> Signing") to your login keychain and lets `codesign` use it. Every run **replaces `/Applications/Snaplens.app`**;
> a copy running from there is quit first and the new build reopened.

In order, the script:

1. Reads `VERSION` from `snaplens/config.py`.
2. Creates the signing certificate if it is missing (openssl, RSA-2048, valid for 3650 days). A stable identity keeps
   the Screen Recording permission across rebuilds.
3. Downloads the OCR models so they are bundled.
4. Builds `dist/Snaplens.app` with PyInstaller from `snaplens.spec`: a one-folder app (a one-file app would unpack
   the whole bundle, about 365 MB with the models, to a temporary folder on every start), without unused models, other
   inference engines, QML, PDF, WebEngine or Qt translations. It also copies the login item's launchd agent,
   `assets/launchd/io.github.kehsb.snaplens.plist`, into `Contents/Library/LaunchAgents`.
5. Signs it with `codesign --force --deep`.
6. Creates `installer/Snaplens-<version>.dmg` with dmgbuild, using the settings in `dmg.py`: UDZO, the app icon as the
   volume icon, and a Finder window that shows the app, an arrow and an `Applications` link on the background picture
   in `assets/dmg/`.
7. Installs the app to `/Applications/Snaplens.app` with `ditto`.

The bundle id is `io.github.kehsb.snaplens`, the executable is `Snaplens.app/Contents/MacOS/Snaplens`, and
`LSUIElement` keeps it out of the Dock. PyInstaller and dmgbuild are pinned in `requirements.txt`, so the setup above
already installed them. The DMG background is drawn by `assets/dmg/background.py`: after changing it, run
`.venv/bin/python assets/dmg/background.py` to redraw `background.png` and `background@2x.png`.

### Project structure

```text
snaplens-mac/
├── app.py                  # Entry point: single instance, no Dock icon, Edit menu, starts the app
├── snaplens/               # The app package
│   ├── config.py           # Version, bundle id, default shortcut, languages, fonts, OCR thresholds
│   ├── task.py             # Task: runs a function off the UI thread (QThread)
│   ├── ocr/
│   │   ├── engine.py       # RapidOCR: shared PP-OCRv6 detector, PP-OCRv5 Chinese/Thai recognizers
│   │   └── translate.py    # Google batch translation, then per-line MyMemory fallback
│   ├── qr/
│   │   ├── scan.py         # Finds and decodes QR codes; detects panels in a capture
│   │   └── promptpay.py    # What a QR says: EMVCo, PromptPay, bill and slip QR parsing; CRC; banks, money
│   ├── system/
│   │   ├── mac.py          # AppKit/Quartz/Carbon: display capture, overlay level, permission, shortcut
│   │   ├── hotkey.py       # Shortcut names and symbols, and which combinations are allowed
│   │   ├── autostart.py    # Login item: the app's launchd agent, registered with SMAppService
│   │   └── prefs.py        # Settings store (QSettings), and moving settings over from older versions
│   └── ui/
│       ├── main.py         # App controller: menu bar, shortcut, settings state, capture lifecycle
│       ├── menubar.py      # Status item and its native menu
│       ├── settings.py     # Native Settings window and shortcut recorder
│       ├── overlay.py      # Capture canvas: selection, OCR/translate, drawing, copy/save, QR boxes
│       ├── chrome.py       # Native overlay chrome: toolbar, hint bar, toast, popover, menus, keys
│       ├── qrcard.py       # Native QR card: what each code says, Copy and Open link
│       ├── native.py       # Shared AppKit building blocks: Liquid Glass with fallback, stacks, menus
│       ├── glass.py        # Qt-painted glass for the canvas (size tag, magnifier label)
│       ├── notify.py       # Notification Center notices, or the in-app panel
│       └── assets.py       # Fonts, the QR badge's glyph, app icon
├── assets/icons/           # App and menu bar icons
├── assets/dmg/             # DMG window background, and background.py, which draws it
├── assets/launchd/         # The login item's launchd agent, copied into the app
├── docs/images/            # README screenshots
├── testset/                # Sample image
├── snaplens.spec           # PyInstaller recipe and bundle metadata
├── dmg.py                  # dmgbuild settings: DMG window, icon positions, background
├── build.sh                # Build, sign, DMG, install
├── dev.sh                  # Auto-restart dev runner
└── requirements.txt        # Pinned dependencies
```

### How it fits together

- **Qt (PySide6)** paints the capture canvas (the frozen screenshot, selection, translations and drawings) and
  provides worker threads, the settings store and the single-instance socket.
- **AppKit through PyObjC** draws everything around it: the menu bar menu, the overlay toolbar, hint bar, popovers and
  menus, the QR card, the Settings window and Notification Center notices. Liquid Glass (`NSGlassEffectView`)
  needs macOS 26; the `NSVisualEffectView` fallback for older systems is untested.
- **Quartz** captures each display at full resolution, **Carbon** provides the global shortcut, and
  **ServiceManagement** (`SMAppService`) registers the login item.
- **OCR:** the PP-OCRv6 small detector finds lines once, and each line is recognized with the PP-OCRv5 mobile Chinese
  and/or Thai model. Captures under 400 px on a side are upscaled 2×, and readings scoring below 0.5 are dropped.

## Contributing

Issues and pull requests are welcome.

- **Bug reports:** include your macOS version and Mac model, whether you use the DMG or run from source, and the steps
  to reproduce. Remove personal data from screenshots first, such as names, account numbers and payment QR codes.
- **Pull requests:** keep each to one topic. There is no test suite or CI yet, so describe how you tested by hand,
  including the macOS version. For larger changes, such as localization or a new capture mode, open an issue first.
- **Code:** put code in the domain packages under `snaplens/` (`ocr`, `qr`, `system`, `ui`). Build native UI
  with AppKit through PyObjC, reusing `snaplens/ui/native.py`; Qt paints the capture canvas. Keep slow work off the
  UI thread with `snaplens.task.Task`. User-facing strings are Thai, so match the existing wording. `pyflakes` is in
  `requirements.txt`: run `.venv/bin/pyflakes app.py snaplens` before pushing.
- **Never commit** an API key or real slip images. `thunder.key` and `testset/slips/`, the `ThunderAPI` branch's key
  file and slip images, stay git-ignored on main too, so they are not committed after you switch branches.

## Acknowledgements

Snaplens is built on these open-source projects:

| Project | Licence | Used for |
|---|---|---|
| [RapidOCR](https://github.com/RapidAI/RapidOCR) | Apache-2.0 | OCR pipeline and the ONNX conversions of the PP-OCR models |
| [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) PP-OCR models | Apache-2.0 | PP-OCRv6 detection, PP-OCRv5 Chinese and Thai recognition |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) | MIT | On-device inference |
| [OpenCV](https://github.com/opencv/opencv-python) (opencv-python) | Apache-2.0; the wheel bundles a GPL-3.0-or-later build of FFmpeg | Image processing, panel detection, QR detection and decoding |
| [Qt for Python](https://doc.qt.io/qtforpython-6/) (PySide6, shiboken6) | LGPL-3.0 / GPL-2.0 / GPL-3.0 | Capture canvas, threads, settings, single-instance socket |
| [PyObjC](https://github.com/ronaldoussoren/pyobjc) | MIT | AppKit, Quartz and Notification Center from Python |
| [deep-translator](https://github.com/nidhaloff/deep-translator) | MIT | Google Translate and MyMemory clients |
| [NumPy](https://numpy.org) | BSD-3-Clause and others | Arrays |
| [PyInstaller](https://pyinstaller.org) | GPL-2.0-or-later with the bootloader exception | Building the app bundle |
| [dmgbuild](https://github.com/dmgbuild/dmgbuild) (with ds_store and mac_alias) | MIT | Building the DMG |
| [Python](https://www.python.org) | PSF License | Runtime, bundled in the app |

Also bundled through dependencies, each under its own licence: shapely (BSD-3-Clause) with GEOS (LGPL-2.1),
pyclipper, omegaconf, antlr4-python3-runtime, PyYAML, Pillow, requests, urllib3, idna, charset-normalizer,
certifi (MPL-2.0), beautifulsoup4, soupsieve, tqdm (MPL-2.0 and MIT), colorlog, colorama, packaging,
typing_extensions and setuptools.

External services: Google Translate (unofficial web endpoint) and [MyMemory](https://mymemory.translated.net) by
Translated.

## License

The Snaplens **source code** is released under the [MIT License](LICENSE). Copyright (c) 2026 kehsb.

The **prebuilt app (DMG)** also contains third-party components under their own licences, which the MIT License does
not cover, including:

- **LGPL-3.0:** PySide6 / Qt
- **LGPL-2.1:** GEOS, shipped with shapely
- **GPL-3.0-or-later:** FFmpeg as shipped inside the opencv-python wheel (`libavcodec`, `libavformat`, `libavutil`,
  `libswscale` and the other FFmpeg libraries, built with `--enable-gpl --enable-version3`), together with the GPL
  libraries it links: `libx264`, `libx265`, `libpostproc`, `librubberband` and `libvidstab`

See [Acknowledgements](#acknowledgements) for the full list.

---

<sub>Snaplens is an independent project. It is not affiliated with Google or MyMemory (Translated).</sub>
