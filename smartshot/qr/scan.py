"""QR codes: find and decode them in a capture, and cut a capture into panels."""
import threading

import cv2
import numpy as np


# --- QR codes: find and decode them (promptpay.qr_info says what they are)
_QR = cv2.QRCodeDetectorAruco()  # finds small on-screen codes the classic detector misses
_qp = _QR.getArucoParameters()
_qp.minMarkerPerimeterRate = 0.01  # the default 0.02 drops finder patterns under ~1.4 px per module
_QR.setArucoParameters(_qp)
_QR2 = cv2.QRCodeDetector()  # a second decoder: each reads some codes the other can't
_qr_lock = threading.Lock()  # the detectors aren't thread-safe; a scan takes < 0.3 s


def _qr_find(img):  # candidate codes: [4x2 corners]
    try:
        ok, pts = _QR.detectMulti(img)
    except cv2.error:
        return []
    return list(pts) if ok else []


def _qr_read(img, q):
    """Decode one candidate -> (text, corners). Screenshots have no perspective, so the corner without a finder
    pattern (index 2) is rebuilt as a parallelogram: OpenCV's guess is often a few px off and the decode fails.
    Decodes a crop around it: on a whole big frame each call costs ~100 ms."""
    m = 8 + int(np.ptp(q[:, 0])) // 6
    x0, y0 = np.maximum(np.floor(q.min(0)).astype(int) - m, 0)
    crop = img[y0:int(q[:, 1].max()) + m, x0:int(q[:, 0].max()) + m]
    q = q - (x0, y0)
    fixed = q.copy()
    fixed[2] = q[1] + q[3] - q[0]
    for quad in (fixed, q):
        for det in (_QR, _QR2):
            try:
                text = det.decode(crop, quad.reshape(1, 4, 2).astype(np.float32))[0]
            except cv2.error:  # asserts on garbage candidates
                continue
            if text:
                return text, quad + (x0, y0)
    return "", q + (x0, y0)


def _qr_retry(g, q):  # a candidate that didn't decode (small, blurred): crop it, x4, sharpen, find + decode again
    x0, y0 = np.floor(q.min(0)).astype(int)
    x1, y1 = np.ceil(q.max(0)).astype(int)
    m = max(4, (x1 - x0) // 6)
    X0, Y0 = max(0, x0 - m), max(0, y0 - m)
    crop = cv2.resize(g[Y0:y1 + m, X0:x1 + m], None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    crop = cv2.addWeighted(crop, 2, cv2.GaussianBlur(crop, (0, 0), 2), -1, 0)  # unsharp mask
    crop = cv2.copyMakeBorder(crop, 16, 16, 16, 16, cv2.BORDER_CONSTANT, value=255)
    for cq in _qr_find(crop):
        text, cq = _qr_read(crop, cq)
        if text:
            return text, (cq - 16) / 4 + (X0, Y0)
    return "", q


def _near(q, quads):  # the same code found twice
    return any(np.linalg.norm(q.mean(0) - f.mean(0)) < 0.25 * np.ptp(f[:, 0]) for f in quads)


def scan_qr(img):
    """BGR image -> [(text, 4x2 corners in img px)], top to bottom. Benchmarked on screenshots: 99.8% of codes at
    >= 2 px per module (blurred chat-app images included), ~70 ms on a full HD frame."""
    B = 32  # white quiet zone: codes touching the crop's edge are still found
    g = cv2.copyMakeBorder(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), B, B, B, B, cv2.BORDER_CONSTANT, value=255)
    found = []
    with _qr_lock:
        for s, interp in ((2, cv2.INTER_CUBIC), (3, cv2.INTER_NEAREST)):  # x3 nearest rescues tiny crisp codes
            big = cv2.resize(g, None, fx=s, fy=s, interpolation=interp)
            pending = []
            for q in _qr_find(big):
                if _near(q / s, [f for _, f in found] + pending):
                    continue
                text, q = _qr_read(big, q)
                (found.append((text, q / s)) if text else pending.append(q / s))
            for q in pending[:8]:  # ponytail: bounds the worst case on busy frames; raise if codes get missed
                if not _near(q, [f for _, f in found]):
                    text, q = _qr_retry(g, q)
                    if text:
                        found.append((text, q))
            if found:
                break
    found = [(t, (q - B).astype(np.float32)) for t, q in found]
    return sorted(found, key=lambda f: (f[1][:, 1].min(), f[1][:, 0].min()))


def panels(img, k):
    """Screenshot -> what pointing and clicking can select, Snipaste style, found in its pixels (the overlay covers
    every window: there is no UI tree to ask) -> [x, y, w, h] smallest first, in img px. A box is an edge outline
    with 3 of its 4 sides drawn: a white card on a white page has no bottom edge. The wheel and a drag cover the
    rest."""
    H, W = img.shape[:2]
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(g, 20, 40)  # low: a screenshot has no noise, and a light grey card on white must show
    e = cv2.dilate(edges, np.ones((3, 3), np.uint8))
    st, lo = cv2.connectedComponentsWithStats(e)[2][1:, :4], 48 * k
    st = st[(st[:, 2] >= lo) & (st[:, 3] >= lo) & (st[:, 2] * st[:, 3] <= W * H // 2)]
    same = lambda a, b: all(abs(u - v) <= 4 * k for u, v in zip((*a[:2], a[0] + a[2], a[1] + a[3]),
                                                                 (*b[:2], b[0] + b[2], b[1] + b[3])))
    boxes = []
    for x, y, w, h in sorted(st.tolist(), key=lambda b: b[2] * b[3]):
        sides = (e[y:y + 3, x:x + w].any(0), e[y + h - 3:y + h, x:x + w].any(0),
                 e[y:y + h, x:x + 3].any(1), e[y:y + h, x + w - 3:x + w].any(1))
        if sum(s.mean() >= 0.75 for s in sides) >= 3 and not any(same(b, (x, y, w, h)) for b in boxes):
            boxes.append((x, y, w, h))
    for x, y, w, h in list(boxes):  # an outline broken where a card's colour meets the page's (a coloured header):
        m = w // 10                 # its own top or bottom line, past a gap its sides still reach over, closes it
        for up in (True, False):
            a, b = (max(y - h // 2, 0), max(y - 3, 0)) if up else (y + h + 3, min(y + h + h // 2, H))
            rows = np.flatnonzero((e[a:b, x + m:x + w - m] > 0).mean(1) >= 0.9) + a
            if not len(rows):
                continue
            t0, t1 = (int(rows[-1]), y) if up else (y + h, int(rows[0]) + 1)
            if e[t0:t1, x:x + 3].any(1).mean() + e[t0:t1, x + w - 3:x + w].any(1).mean() >= 1.2:
                c = (x, t0, w, y + h - t0) if up else (x, y, w, t1 - y)
                if not any(same(c, d) for d in boxes):
                    boxes.append(c)
    return sorted(boxes, key=lambda b: b[2] * b[3])
