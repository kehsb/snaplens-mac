"""QR codes: find and decode them in a capture, and cut a capture into panels."""
import threading

import cv2
import numpy as np


# --- QR codes: find and decode them, say what they are, check bank slips with Thunder
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
    >= 2 px per module (blurred chat-app slips included), ~70 ms on a full HD frame."""
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
    every window: there is no UI tree to ask) -> ([x, y, w, h] smallest first, [those around a QR code]), in img px.
    A box is an edge outline with 3 of its 4 sides drawn: a white slip on a white page has no bottom edge. Around a
    QR code: the smallest box 4-150x its area (real slips: 16-75x; bigger is the chat, smaller the code itself),
    grown to the boxes around it while each is under 2.5x (a slip's inner card or top part -> the slip -> its
    bubble, not the chat), but a box of strong lines around it wins (a slip in an image viewer, the page dimmed);
    else the blob of the code and the text by it, for a slip with no edge at all.
    ponytail: tuned on 7 real slips in made-up chat screens (40 of 42 whole) and 2 real image viewer screenshots
    (both whole); the wheel and a drag cover the rest."""
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
    for x, y, w, h in list(boxes):  # an outline broken where the slip's colour meets the page's (Krungthai's header):
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
    boxes.sort(key=lambda b: b[2] * b[3])
    qd = cv2.QRCodeDetectorAruco()  # its own, finding only: the shared ones read the selection's codes meanwhile
    qd.setArucoParameters(_qp)
    z = max(2 / k, 1)  # ~2 px per screen px finds chat-sized codes (all 7 real slips at 320 px wide), ~60 ms
    try:
        ok, pts = qd.detectMulti(cv2.resize(g, None, fx=z, fy=z, interpolation=cv2.INTER_CUBIC) if z > 1 else g)
    except cv2.error:
        ok = False
    inside = lambda a, b: b[0] <= a[0] and b[1] <= a[1] and a[0] + a[2] <= b[0] + b[2] and a[1] + a[3] <= b[1] + b[3]
    hi = cv2.dilate(cv2.Canny(g, 150, 300), np.ones((3, 3), np.uint8)) > 0  # strong lines only
    one = lambda a: (a[np.diff(a, prepend=-2) > 1] + 1).tolist()  # a line, 3+ px thick when dilated -> its middle
    around = []
    for q in pts / z if ok else []:
        (x0, y0), (x1, y1) = q.min(0), q.max(0)
        qa = max((x1 - x0) * (y1 - y0), 1.0)
        fit = [b for b in boxes if inside((x0, y0, x1 - x0, y1 - y0), b) and 4 <= b[2] * b[3] / qa <= 150]
        b = fit[0] if fit else None
        while b and (up := next((u for u in fit if u != b and inside(b, u) and u[2] * u[3] <= 2.5 * b[2] * b[3]), None)):
            b = up
        # an image viewer dims the page behind the slip, and the page's faint lines join the slip's outline to the
        # column border its side lies on: strong lines right across the code, on all four sides, are the slip's own
        hr, vc = np.flatnonzero(hi[:, int(x0):int(x1) + 1].all(1)), np.flatnonzero(hi[int(y0):int(y1) + 1].all(0))
        T, D, L, R = one(hr[hr < y0])[-6:], one(hr[hr > y1])[:6], one(vc[vc < x0])[-6:], one(vc[vc > x1])[:6]
        drawn = [(l, t, r - l, d - t) for t in T for d in D for l in L for r in R if (r - l) * (d - t) <= 150 * qa
                 and min(hi[t, l:r].mean(), hi[d, l:r].mean(), hi[t:d, l].mean(), hi[t:d, r].mean()) >= 0.9]
        if drawn:
            b = max(drawn, key=lambda c: c[2] * c[3])
        if b is None:  # no outline: grow the code into the text around it, as far as real slips reach from theirs
            s = int(max(x1 - x0, y1 - y0))
            X0, Y0 = max(int(x0) - 6 * s, 0), max(int(y0) - 9 * s, 0)
            X1, Y1 = min(int(x1) + 6 * s, W), min(int(y1) + 8 * s, H)
            blob = edges[Y0:Y1, X0:X1].copy()
            for x, y, w, h in boxes:  # the chat bubbles by it are panels of their own: the blob must not run into them
                if not inside((x0, y0, x1 - x0, y1 - y0), (x, y, w, h)):
                    blob[max(y - Y0 - 3, 0):max(y + h - Y0 + 3, 0), max(x - X0 - 3, 0):max(x + w - X0 + 3, 0)] = 0
            blob = cv2.dilate(blob, np.ones((s // 5 | 1,) * 2, np.uint8))  # bridges a slip's line gaps
            labels, st2 = cv2.connectedComponentsWithStats(blob)[1:3]
            i = labels[int(y0 + y1) // 2 - Y0, int(x0 + x1) // 2 - X0]
            bx, by, bw, bh = st2[i, :4].tolist()
            kept = i and (bx or not X0) and (by or not Y0) and (bx + bw < X1 - X0 or X1 == W) and (by + bh < Y1 - Y0 or Y1 == H)
            b = (X0 + bx, Y0 + by, bw, bh) if kept and 4 <= bw * bh / qa <= 150 else None
        if b and b not in around:
            around.append(b)
    boxes += [b for b in around if b not in boxes]
    area = lambda b: b[2] * b[3]
    return sorted(boxes, key=area), sorted(around, key=area)
