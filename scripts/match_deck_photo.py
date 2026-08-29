#!/usr/bin/env python3
"""Turn a Union Arena deck screenshot into card counts via official art."""

from __future__ import annotations

import base64
import io
import math
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image
import numpy as np

import scrape_youtube_ocr as ocr
import uadb

INDEX_FILE = "data/card-art-index.json"
SIZE = 32
MIN_SCORE = 0.58
ART_CROP = 0.88
QTY_RE = re.compile(r"(?i)(?:^|[^0-9])x\s*([1-4])\b")
STOP = {
    "list",
    "deck",
    "this",
    "that",
    "with",
    "from",
    "your",
    "just",
    "have",
    "like",
    "photo",
    "pics",
    "what",
    "does",
    "really",
    "about",
    "been",
    "they",
    "them",
    "fun",
    "love",
    "help",
    "need",
    "want",
    "anyone",
    "think",
    "would",
    "could",
    "made",
    "make",
    "using",
    "built",
    "build",
    "here",
    "some",
    "more",
    "than",
    "only",
    "also",
    "very",
    "much",
    "good",
    "best",
    "top",
    "first",
    "time",
    "union",
    "arena",
    "card",
    "cards",
    "tcg",
    "please",
    "thanks",
    "thank",
    "place",
    "after",
    "before",
}
_MATRIX = None
_MATRIX_IDS: list[str] = []


def title_tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", (text or "").lower()) if w not in STOP}


def set_code(cid: str) -> str:
    m = re.search(r"/([A-Z]{2,4})\d?-", cid or "")
    return m.group(1) if m else ""


def card_num(cid: str) -> int:
    m = re.search(r"-(\d+)$", (cid or "").split("/")[-1])
    return int(m.group(1)) if m else 0


def playable(cid: str) -> bool:
    tail = (cid or "").split("/")[-1]
    if not cid or cid.endswith(("_p1", "_p2")) or "/AP" in cid or "-AP" in tail:
        return False
    return True


def card_name(cid: str, cache: dict) -> str:
    return ((cache.get(cid) or {}).get("name") or "").strip()


def _vec(im: Image.Image, size: int = SIZE) -> bytes:
    gray = im.convert("L").resize((size, size), Image.Resampling.BILINEAR)
    data = gray.get_flattened_data() if hasattr(gray, "get_flattened_data") else gray.getdata()
    return bytes(data)


def _cos(a: bytes, b: bytes) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    ma = sum(a) / len(a)
    mb = sum(b) / len(b)
    dot = sa = sb = 0.0
    for x, y in zip(a, b):
        dx, dy = x - ma, y - mb
        dot += dx * dy
        sa += dx * dx
        sb += dy * dy
    if sa <= 1 or sb <= 1:
        return 0.0
    return dot / math.sqrt(sa * sb)


def load_index() -> dict[str, bytes]:
    raw = uadb.load_json(INDEX_FILE, {})
    cards = raw.get("cards") if isinstance(raw, dict) else {}
    out = {}
    for cid, blob in (cards or {}).items():
        try:
            out[cid] = base64.b64decode(blob)
        except Exception:
            continue
    return out


def save_index(index: dict[str, bytes]) -> None:
    payload = {
        "size": SIZE,
        "cards": {cid: base64.b64encode(vec).decode("ascii") for cid, vec in sorted(index.items())},
    }
    uadb.save_json(INDEX_FILE, payload)


def _download_vec(cid: str, url: str) -> tuple[str, bytes | None]:
    req = urllib.request.Request(url, headers={"User-Agent": uadb.BROWSER_UA, "Accept": "image/*"})
    try:
        with urllib.request.urlopen(req, timeout=14) as resp:
            im = Image.open(io.BytesIO(resp.read())).convert("RGB")
        return cid, _vec(im)
    except Exception:
        return cid, None


def ensure_index(cache: dict, limit: int = 0) -> dict[str, bytes]:
    index = load_index()
    missing = []
    recent = ("UE23", "UE22", "UE21", "UE19", "UE17", "UE16", "UE15", "UE14", "UE13", "UE12", "UE11", "UE10", "UE09", "UE08", "UE07", "UE06")
    for cid, meta in cache.items():
        if cid.endswith(("_p1", "_p2")) or "/AP" in cid or cid.endswith("-AP"):
            continue
        if cid in index:
            continue
        url = uadb.card_image_url(cid, cache)
        if url:
            missing.append((cid, url))
        if limit and len(index) + len(missing) >= limit:
            break
    missing.sort(key=lambda row: next((i for i, p in enumerate(recent) if row[0].startswith(p)), 99))
    if not missing:
        uadb.log("card art index ready", len(index))
        return index
    uadb.log("card art index download", len(missing), "have", len(index))
    with ThreadPoolExecutor(max_workers=10) as pool:
        futs = [pool.submit(_download_vec, cid, url) for cid, url in missing]
        for i, fut in enumerate(as_completed(futs), 1):
            cid, vec = fut.result()
            if vec:
                index[cid] = vec
            if i % 200 == 0:
                uadb.log("card art hashed", i, "/", len(missing), "total", len(index))
                save_index(index)
    save_index(index)
    uadb.log("card art index", len(index))
    return index


def _sat_rows(im: Image.Image) -> list[float]:
    pix = im.convert("RGB")
    w, h = pix.size
    src = pix.load()
    out = []
    for y in range(h):
        n = 0
        for x in range(0, w, 2):
            r, g, b = src[x, y][:3]
            if max(r, g, b) - min(r, g, b) > 48:
                n += 1
        out.append(n / max(1, w / 2))
    return out


def detect_rows(im: Image.Image) -> list[tuple[int, int]]:
    energy = _sat_rows(im)
    h = len(energy)
    bands = []
    y = 0
    while y < h:
        if energy[y] >= 0.22:
            a = y
            while y < h and energy[y] >= 0.16:
                y += 1
            if 4 <= (y - a) <= 28:
                bands.append((a, y))
        else:
            y += 1
    rows = []
    i = 0
    while i < len(bands) - 1:
        top = bands[i][0]
        for j in range(i + 1, len(bands)):
            bot = bands[j][1]
            height = bot - top
            if 0.18 * h <= height <= 0.42 * h:
                rows.append((top, bot))
                i = j
                break
        i += 1
    if len(rows) >= 2:
        return rows
    # fallback: skip header/footer and assume 3 rows
    top, bot = int(h * 0.18), int(h * 0.92)
    step = (bot - top) // 3
    return [(top + r * step, top + (r + 1) * step) for r in range(3)]


def qty_from_tile(tile: Image.Image) -> int:
    strip = tile.crop((0, int(tile.height * 0.72), tile.width, tile.height))
    if strip.width < 20:
        return 4
    big = strip.resize((strip.width * 3, strip.height * 3), Image.Resampling.LANCZOS)
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
        tmp = Path(fh.name)
        big.save(tmp)
    try:
        text = ocr.tesseract(tmp, psm=7) + " " + ocr.tesseract(tmp, psm=11)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    m = QTY_RE.search(text.replace("X", "x"))
    return int(m.group(1)) if m else 4


def prefer_cid(cid: str) -> int:
    if re.match(r"UE\d{2}BT/", cid):
        return 2
    if cid.startswith("UEPR/") or "ST/" in cid:
        return 0
    return 1


def _matrix(index: dict[str, bytes]):
    global _MATRIX, _MATRIX_IDS
    ids = list(index)
    if _MATRIX is not None and _MATRIX_IDS == ids:
        return _MATRIX, _MATRIX_IDS
    arr = np.zeros((len(ids), SIZE * SIZE), dtype=np.float32)
    for i, cid in enumerate(ids):
        raw = np.frombuffer(index[cid], dtype=np.uint8).astype(np.float32)
        raw -= raw.mean()
        n = np.linalg.norm(raw)
        if n > 1:
            raw /= n
        arr[i] = raw
    _MATRIX, _MATRIX_IDS = arr, ids
    return arr, ids


def best_card(vec: bytes, index: dict[str, bytes]) -> tuple[str, float]:
    if not vec or not index:
        return "", 0.0
    arr, ids = _matrix(index)
    q = np.frombuffer(vec, dtype=np.uint8).astype(np.float32)
    q -= q.mean()
    n = np.linalg.norm(q)
    if n <= 1:
        return "", 0.0
    q /= n
    scores = arr @ q
    order = np.argpartition(scores, -3)[-3:]
    order = order[np.argsort(scores[order])[::-1]]
    best = ids[int(order[0])]
    score = float(scores[order[0]])
    for i in order[1:]:
        cid = ids[int(i)]
        s = float(scores[i])
        if score - s < 0.015 and prefer_cid(cid) > prefer_cid(best):
            best, score = cid, s
    return best, score


def _hint_index(index: dict[str, bytes], cache: dict, hint: str) -> dict[str, bytes]:
    blob = re.sub(r"[^a-z0-9]+", " ", (hint or "").lower())
    if len(blob) < 4:
        return {cid: vec for cid, vec in index.items() if playable(cid)} or index
    codes = set()
    from scrape_community import SET_PREFIX

    for code, anime in SET_PREFIX.items():
        if anime.replace("-", " ") in blob or code.lower() in blob.split():
            codes.add(code)
    tokens = title_tokens(hint)
    for cid, meta in cache.items():
        name = re.sub(r"[^a-z0-9]+", " ", ((meta.get("name") or "")).lower()).strip()
        title = re.sub(r"[^a-z0-9]+", " ", ((meta.get("title") or "")).lower()).strip()
        hit = (name and len(name) >= 5 and name in blob) or (title and len(title) >= 8 and title in blob)
        if not hit and name and tokens:
            parts = set(name.split())
            hit = any(t in parts or (len(t) >= 5 and t in name) for t in tokens)
        if hit:
            code = set_code(cid)
            if code:
                codes.add(code)
    playable_idx = {cid: vec for cid, vec in index.items() if playable(cid)}
    if not codes:
        return playable_idx or index
    narrowed = {cid: vec for cid, vec in playable_idx.items() if set_code(cid) in codes}
    return narrowed if len(narrowed) >= 12 else playable_idx or index


def expand_from_hits(index: dict[str, bytes], cache: dict, seed_cids: list[str], hint: str = "") -> dict[str, bytes]:
    names: set[str] = set()
    nums: list[int] = []
    codes: set[str] = set()
    for cid in seed_cids:
        name = card_name(cid, cache)
        if name:
            names.add(name.lower())
        num = card_num(cid)
        if 1 <= num < 100:
            nums.append(num)
        code = set_code(cid)
        if code:
            codes.add(code)
    tokens = title_tokens(hint)
    if tokens:
        for cid, meta in cache.items():
            name = (meta.get("name") or "").lower()
            if not name:
                continue
            parts = set(re.findall(r"[a-z0-9]+", name))
            if any(t in parts or (len(t) >= 5 and t in name) for t in tokens):
                if (meta.get("name") or "").strip():
                    names.add((meta.get("name") or "").strip().lower())
                code = set_code(cid)
                if code:
                    codes.add(code)
    lo, hi = 1, 99
    if nums:
        lo, hi = max(1, min(nums) - 4), min(99, max(nums) + 8)
    out: dict[str, bytes] = {}
    for cid, vec in index.items():
        if not playable(cid):
            continue
        if codes and set_code(cid) not in codes:
            continue
        name = card_name(cid, cache).lower()
        num = card_num(cid)
        name_hit = bool(name and name in names)
        window = lo <= num <= hi and num < 100 and "PR/" not in cid
        if "ST/" in cid and not name_hit:
            continue
        if name_hit or window:
            out[cid] = vec
    return out if len(out) >= 3 else index


def fit_fifty(counts: dict[str, int], scores: dict[str, float]) -> dict[str, int]:
    counts = dict(counts)
    order = sorted(counts, key=lambda cid: scores.get(cid, 0.0))
    for cid in order:
        if sum(counts.values()) <= 50:
            break
        if counts.get(cid, 0) >= 4:
            counts[cid] = 2
    while sum(counts.values()) > 50 and counts:
        cid = min(counts, key=lambda c: scores.get(c, 0.0))
        if counts[cid] > 1:
            counts[cid] -= 1
        else:
            counts.pop(cid)
    return counts


def _tiles(im: Image.Image, rows: list[tuple[int, int]], cols: int) -> list[Image.Image]:
    w, _h = im.size
    cw = w / cols
    tiles: list[Image.Image] = []
    for y0, y1 in rows:
        for c in range(cols):
            x0, x1 = int(c * cw) + 8, int((c + 1) * cw) - 8
            if x1 - x0 < 40 or y1 - y0 < 60:
                continue
            tile = im.crop((x0, y0 + 6, x1, y1 - 8))
            gray = tile.convert("L")
            extrema = gray.getextrema()
            if extrema and extrema[1] - extrema[0] < 18:
                continue
            tiles.append(tile.crop((6, 10, tile.width - 6, max(20, int(tile.height * ART_CROP)))))
    return tiles


def _match_tiles(
    tiles: list[Image.Image], index: dict[str, bytes], cache: dict, need: float
) -> tuple[list[tuple[str, float]], list[Image.Image]]:
    out: list[tuple[str, float]] = []
    leftover: list[Image.Image] = []
    used: set[str] = set()
    for art in tiles:
        cid, score = best_card(_vec(art), index)
        if score >= need and cid in cache and cid not in used:
            used.add(cid)
            out.append((cid, score))
        else:
            leftover.append(art)
    return out, leftover


def _color_name(rgb: tuple[int, int, int]) -> str:
    r, g, b = rgb
    if r > 170 and g > 150 and b < 130:
        return "Yellow"
    if r > 160 and g < 90 and b < 90:
        return "Red"
    if r > 120 and b > 130 and g < 110:
        return "Purple"
    if g > 130 and r < 110 and b < 120:
        return "Green"
    if b > 140 and r < 110:
        return "Blue"
    return ""


def filter_by_color(index: dict[str, bytes], cache: dict, color: str) -> dict[str, bytes]:
    if not color:
        return index
    out = {
        cid: vec
        for cid, vec in index.items()
        if not (cache.get(cid) or {}).get("color")
        or ((cache.get(cid) or {}).get("color") or "").lower() == color.lower()
    }
    return out if len(out) >= 8 else index


def counts_from_photo(path: Path, cache: dict, index: dict[str, bytes] | None = None, hint: str = "") -> dict[str, int]:
    index = index or load_index()
    index = _hint_index(index, cache, hint)
    if len(index) < 12:
        return {}
    try:
        im = Image.open(path).convert("RGB")
    except OSError:
        return {}
    if im.width < 400 or im.height < 400:
        return {}
    rows = detect_rows(im)
    if rows:
        votes = []
        y0, y1 = rows[0]
        cw = im.size[0] / 5
        px = im.load()
        for c in range(5):
            x = int(c * cw + cw * 0.08)
            y = int(y0 + (y1 - y0) * 0.12)
            try:
                votes.append(_color_name(px[x, y][:3]))
            except Exception:
                pass
        color = max((v for v in votes if v), key=votes.count, default="")
        if color:
            index = filter_by_color(index, cache, color)
    best_counts: dict[str, int] = {}
    best_hits = 0
    for cols in (5, 4):
        tiles = _tiles(im, rows, cols)
        if len(tiles) < 6:
            continue
        need = 0.42 if len(index) <= 220 else MIN_SCORE
        first, _miss = _match_tiles(tiles, index, cache, need)
        if len(first) < 4:
            first, _miss = _match_tiles(tiles, index, cache, 0.36)
        seed = [cid for cid, _score in first]
        expanded = expand_from_hits(index, cache, seed, hint)
        need2 = 0.28 if len(expanded) <= 45 else 0.32
        second, leftover_tiles = _match_tiles(tiles, expanded, cache, need2)
        used_names = {card_name(cid, cache) for cid, _s in second if card_name(cid, cache)}
        leftover_idx = {
            cid: vec
            for cid, vec in expanded.items()
            if card_name(cid, cache) not in used_names and "ST/" not in cid and "PR/" not in cid
        }
        if leftover_idx and leftover_tiles:
            extra_need = 0.12 if len(leftover_idx) <= 24 else 0.18
            extra, _ = _match_tiles(leftover_tiles, leftover_idx, cache, extra_need)
            second.extend(extra)
        scores = {cid: score for cid, score in second}
        counts = {
            cid: min(uadb.max_copies(cid, cap_restricted=False), 4)
            for cid in scores
            if cid in cache
        }
        counts = fit_fifty(counts, scores)
        hits = len(counts)
        if hits > best_hits:
            best_hits = hits
            best_counts = counts
        if hits >= 10:
            break
    return best_counts


def main() -> int:
    cache = uadb.load_json("data/card-cache.json", {})
    extra = uadb.load_json("data/contender-cards.json", {})
    for cid, card in extra.items():
        cache.setdefault(cid, {}).update({k: v for k, v in card.items() if v})
    ensure_index(cache)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
