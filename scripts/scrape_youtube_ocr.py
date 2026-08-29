#!/usr/bin/env python3
"""Read Union Arena 50-card lists from YouTube thumbnails and early video frames."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

import uadb

VIDEO_CAP = 55
CLIP_SECONDS = 70
FPS = "1/6"
MAX_FRAMES = 10
MIN_UNIQUE = 12
NODE = "/exec-daemon/node"
YTDLP = [os.environ.get("PYTHON", "python3"), "-m", "yt_dlp"]
if Path(NODE).is_file():
    YTDLP += ["--js-runtimes", f"node:{NODE}"]
STILLS = ("maxresdefault", "hq720", "sddefault", "hqdefault", "0", "1", "2", "3")
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
TESSERACT = shutil.which("tesseract") or "tesseract"

LOOSE_ID = re.compile(
    r"((?:UEX|UE)\s*\d{2}\s*(?:BT|ST|PR))\W{0,8}([A-Z]{2,6}\d?)\W{0,6}(\d)\W{0,6}(\d{3})",
    re.I,
)
SHORT_ID = re.compile(r"\b([A-Z]{2,4}\d?-\d-\d{3})\b", re.I)
QTY_NEAR = re.compile(r"(\d{1,2})\s*[xX×*]?\s*$")
OCR_FIXES = (
    (re.compile(r"(?i)\bUE[Il](\d{2}BT)"), r"UE\1"),
    (re.compile(r"(?i)\b(UE\d{2}BT)\s+([A-Z]{2,4}\d?-\d-)"), r"\1/\2"),
    (re.compile(r"(?i)\b(UE\d{2}BT)[_|\\]+"), r"\1/"),
)
PUB = re.compile(r'"publishDate"\s*:\s*"(\d{4}-\d{2}-\d{2})"')
UPLOAD = re.compile(r'"uploadDate"\s*:\s*"(\d{4}-\d{2}-\d{2})"')
TITLE_META = re.compile(r'<meta name="title" content="([^"]+)"')
DECK_WORDS = (
    "deck",
    "list",
    "profile",
    "top 8",
    "top 16",
    "top 32",
    "1st",
    "2nd",
    "3rd",
    "winner",
    "regionals",
)


def ocr_available() -> bool:
    return bool(shutil.which("tesseract"))


def ffmpeg_available() -> bool:
    return bool(shutil.which("ffmpeg"))


def watch_date(html: str) -> str:
    m = PUB.search(html or "") or UPLOAD.search(html or "")
    return m.group(1) if m else ""


def watch_title(html: str) -> str:
    m = TITLE_META.search(html or "")
    if m:
        return re.sub(r"\s+", " ", m.group(1)).replace(" - YouTube", "").strip()
    return ""


def compact_index(cache: dict) -> dict[str, str]:
    idx: dict[str, str] = {}
    for cid in cache:
        if cid.endswith(("_p1", "_p2")):
            continue
        key = re.sub(r"[^A-Z0-9]", "", cid.upper())
        idx[key] = cid
    return idx


def qty_before(text: str, start: int) -> int:
    window = text[max(0, start - 18) : start]
    m = QTY_NEAR.search(window.replace("\n", " "))
    if m and 1 <= int(m.group(1)) <= 12:
        return int(m.group(1))
    return 0


def add_count(counts: dict[str, int], cid: str, n: int, cache: dict) -> None:
    if cid not in cache:
        return
    cap = uadb.max_copies(cid, cap_restricted=False)
    if n < 1:
        return
    if n > cap:
        n = cap
    counts[cid] = max(counts.get(cid, 0), n)


def clean_ocr_text(text: str) -> str:
    blob = text or ""
    for pat, repl in OCR_FIXES:
        blob = pat.sub(repl, blob)
    return blob


def resolve_short(number: str, cache: dict, prefixes: list[str]) -> str | None:
    number = (number or "").upper()
    for pref in prefixes:
        cid = f"{pref}/{number}"
        if cid in cache:
            return cid
    hits = [cid for cid in cache if cid.endswith("/" + number) and not cid.endswith(("_p1", "_p2"))]
    return hits[0] if len(hits) == 1 else None


def counts_from_ocr(text: str, cache: dict, idx: dict[str, str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    blob = clean_ocr_text(text or "")
    for m in uadb.QTY_BEFORE_RE.finditer(blob):
        cid = uadb.normalize_cid(m.group(2))
        if cid:
            add_count(counts, cid, int(m.group(1)), cache)
    for m in uadb.QTY_AFTER_RE.finditer(blob):
        cid = uadb.normalize_cid(m.group(1))
        if cid:
            add_count(counts, cid, int(m.group(2)), cache)
    for m in LOOSE_ID.finditer(blob):
        setn = re.sub(r"\s+", "", m.group(1).upper())
        cid = f"{setn}/{m.group(2).upper()}-{m.group(3)}-{m.group(4)}"
        add_count(counts, cid, qty_before(blob, m.start()) or 4, cache)
        compact = re.sub(r"[^A-Z0-9]", "", cid)
        if compact in idx:
            add_count(counts, idx[compact], qty_before(blob, m.start()) or 4, cache)
    prefixes = []
    for cid in counts:
        pref = cid.split("/", 1)[0]
        if pref not in prefixes:
            prefixes.append(pref)
    if not prefixes:
        prefixes = ["UE23BT", "UE22BT", "UE21BT", "UE19BT", "UE17BT", "UE15BT", "UE13BT", "UE11BT", "UE09BT"]
    for m in SHORT_ID.finditer(blob):
        cid = resolve_short(m.group(1), cache, prefixes)
        if not cid:
            continue
        n = qty_before(blob, m.start())
        if n:
            add_count(counts, cid, n, cache)
        elif cid not in counts:
            add_count(counts, cid, 4, cache)
    if len(counts) >= 6:
        alnum = re.sub(r"[^A-Z0-9]", "", blob.upper())
        for compact, cid in idx.items():
            if 12 <= len(compact) <= 22 and compact in alnum:
                add_count(counts, cid, 4, cache)
    return counts


def preprocess(path: Path, invert: bool = False) -> Path | None:
    try:
        from PIL import Image, ImageEnhance, ImageOps
    except ImportError:
        return None
    try:
        im = Image.open(path).convert("L")
        im = im.resize((im.width * 2, im.height * 2), Image.Resampling.LANCZOS)
        im = ImageOps.autocontrast(im)
        im = ImageEnhance.Contrast(im).enhance(1.7)
        if invert:
            im = ImageOps.invert(im)
        suffix = "_inv.png" if invert else "_prep.png"
        out = path.with_name(path.stem + suffix)
        im.save(out)
        return out
    except OSError:
        return None


def tesseract(path: Path, psm: int = 6, whitelist: bool = False) -> str:
    cmd = [TESSERACT, str(path), "stdout", "-l", "eng", "--psm", str(psm)]
    if whitelist:
        cmd += ["-c", "tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZxX/- "]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=25, check=False)
        return (r.stdout or b"").decode("utf-8", "replace")
    except (OSError, subprocess.TimeoutExpired):
        return ""


def merge_counts(dst: dict[str, int], src: dict[str, int]) -> None:
    for cid, n in src.items():
        dst[cid] = max(dst.get(cid, 0), n)


def ocr_image(path: Path, cache: dict, idx: dict[str, str], quick: bool = False) -> dict[str, int]:
    merged: dict[str, int] = {}
    merge_counts(merged, counts_from_ocr(tesseract(path, psm=6), cache, idx))
    if len(merged) >= 10 and sum(merged.values()) >= uadb.MIN_CARDS:
        return merged
    merge_counts(merged, counts_from_ocr(tesseract(path, psm=6, whitelist=True), cache, idx))
    if quick or (len(merged) >= 10 and sum(merged.values()) >= uadb.MIN_CARDS):
        return merged
    variants = [preprocess(path), preprocess(path, invert=True)]
    for prep in variants:
        if not prep:
            continue
        for psm in (6, 4, 11):
            merge_counts(merged, counts_from_ocr(tesseract(prep, psm=psm), cache, idx))
            merge_counts(merged, counts_from_ocr(tesseract(prep, psm=psm, whitelist=True), cache, idx))
            if len(merged) >= 12 and sum(merged.values()) >= uadb.MIN_CARDS:
                return merged
    return merged


def frames_from_video(video: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    pat = str(out_dir / "f_%03d.png")
    subprocess.run(
        [FFMPEG, "-y", "-i", str(video), "-vf", f"fps={FPS}", "-frames:v", str(MAX_FRAMES), pat],
        capture_output=True,
        timeout=120,
        check=False,
    )
    return sorted(out_dir.glob("f_*.png"))


def download_clip(vid: str, dest: Path) -> bool:
    url = f"https://www.youtube.com/watch?v={vid}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    attempts = [
        ["-f", "18/best[height<=480]/worst", "--download-sections", f"*0-{CLIP_SECONDS}", "--force-keyframes-at-cuts"],
        ["-f", "worst", "--download-sections", f"*0-{CLIP_SECONDS}"],
        ["-f", "18/worst", "--external-downloader", "ffmpeg", "--external-downloader-args", f"ffmpeg_i:-ss 0 -t {CLIP_SECONDS}"],
    ]
    for extra in attempts:
        cmd = YTDLP + extra + ["--no-playlist", "--no-warnings", "-o", str(dest), url]
        try:
            subprocess.run(cmd, capture_output=True, timeout=200, check=False)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if dest.exists() and dest.stat().st_size > 12000:
            return True
        try:
            dest.unlink()
        except OSError:
            pass
    return False


def fetch_jpeg(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": uadb.BROWSER_UA, "Accept": "image/jpeg,image/webp,*/*", "Referer": "https://www.youtube.com/"},
        )
        with urllib.request.urlopen(req, timeout=14) as resp:
            raw = resp.read()
    except Exception:
        return None
    if raw.startswith(b"\xff\xd8") and len(raw) > 2500:
        return raw
    return None


def crops(path: Path, tmp: Path, tag: str) -> list[Path]:
    try:
        from PIL import Image
    except ImportError:
        return []
    try:
        im = Image.open(path)
    except OSError:
        return []
    w, h = im.size
    if w < 400 or h < 300:
        return []
    boxes = {
        "bottom": (0, h // 2, w, h),
        "right": (w // 2, 0, w, h),
        "left": (0, 0, w // 2, h),
    }
    out = []
    for name, box in boxes.items():
        dest = tmp / f"{tag}_{name}.png"
        im.crop(box).save(dest)
        out.append(dest)
    return out


def stills(vid: str, tmp: Path) -> list[Path]:
    paths: list[Path] = []
    for q in STILLS:
        raw = fetch_jpeg(f"https://i.ytimg.com/vi/{vid}/{q}.jpg")
        if not raw:
            continue
        dest = tmp / f"{vid}_{q}.jpg"
        dest.write_bytes(raw)
        paths.append(dest)
        if q == "maxresdefault" and len(raw) > 50000:
            paths.extend(crops(dest, tmp, f"{vid}_{q}"))
    return paths


def looks_like_deck(title: str) -> bool:
    low = (title or "").lower()
    return any(w in low for w in DECK_WORDS)


def complete_enough(counts: dict[str, int]) -> bool:
    return len(counts) >= MIN_UNIQUE and uadb.list_is_complete(counts)


def scrape_ocr(found: list[dict], seen: set[str], cache: dict, arches: list[dict], video_ids: list[str]) -> None:
    from scrape_community import guess_key, item_from_counts, record

    if not ocr_available():
        uadb.log("youtube ocr skipped: tesseract missing")
        return
    idx = compact_index(cache)
    picks: list[tuple[str, str]] = []
    used = set()
    for vid, title in video_ids:
        if vid in used or not looks_like_deck(title):
            continue
        used.add(vid)
        picks.append((vid, title))
        if len(picks) >= VIDEO_CAP:
            break
    if len(picks) < VIDEO_CAP:
        for vid, title in video_ids:
            if vid in used:
                continue
            used.add(vid)
            picks.append((vid, title or ""))
            if len(picks) >= VIDEO_CAP:
                break
    uadb.log("youtube ocr videos", len(picks))
    downloads = 0
    with tempfile.TemporaryDirectory(prefix="uadb-ocr-") as td:
        tmp = Path(td)
        for i, (vid, title) in enumerate(picks, 1):
            uadb.log("ocr", i, "/", len(picks), vid, (title or "")[:48])
            status, html = uadb.fetch(f"https://www.youtube.com/watch?v={vid}", timeout=22, browser=True)
            page = html if status == 200 else ""
            date = watch_date(page)
            title = title or watch_title(page)
            merged: dict[str, int] = {}
            for image in stills(vid, tmp):
                for cid, n in ocr_image(image, cache, idx, quick=True).items():
                    merged[cid] = max(merged.get(cid, 0), n)
            if not complete_enough(merged) and downloads < 18 and ffmpeg_available():
                clip = tmp / f"{vid}.mp4"
                if download_clip(vid, clip):
                    downloads += 1
                    for frame in frames_from_video(clip, tmp / f"{vid}_frames"):
                        for cid, n in ocr_image(frame, cache, idx, quick=True).items():
                            merged[cid] = max(merged.get(cid, 0), n)
                    try:
                        clip.unlink()
                    except OSError:
                        pass
            if not complete_enough(merged):
                uadb.log("ocr miss", vid, "unique", len(merged), "cards", sum(merged.values()) if merged else 0)
                continue
            uadb.log("ocr hit", vid, "unique", len(merged), "cards", sum(merged.values()))
            blob = f"{title} {page[:4000]}"
            key = guess_key(blob, merged, cache, arches)
            if not key:
                uadb.log("ocr no-key", vid, "cards", sum(merged.values()))
                continue
            player = re.sub(r"\s*[-|].*", "", title or "").strip()[:40] or "YouTube"
            record(
                found,
                item_from_counts(
                    merged,
                    key=key,
                    kind="youtube",
                    player=player,
                    title=(title or f"{key} YouTube list")[:90],
                    subtitle="YouTube on-screen list (from the video or thumbnail)",
                    source_url=f"https://www.youtube.com/watch?v={vid}",
                    slug=uadb.slugify(f"yt-ocr-{player}-{key}-{vid}"),
                    date=date,
                ),
                seen,
            )


def main() -> int:
    import scrape_community

    cache = uadb.load_json("data/card-cache.json", {})
    extra = uadb.load_json("data/contender-cards.json", {})
    for cid, card in extra.items():
        cache.setdefault(cid, {}).update({k: v for k, v in card.items() if v})
    arches = scrape_community.archetypes()
    ids: list[tuple[str, str]] = []
    seen: set[str] = set()
    for query in scrape_community.youtube_queries(arches)[:24]:
        for vid in scrape_community.youtube_search(query):
            if vid not in seen:
                seen.add(vid)
                ids.append((vid, ""))
        if len(ids) >= 80:
            break
    found: list[dict] = []
    scrape_ocr(found, set(), cache, arches, ids)
    existing = uadb.load_json("data/community-decks.json", [])
    seen_raw = {row.get("raw") for row in existing}
    added = 0
    for item in found:
        if item.get("raw") in seen_raw:
            continue
        existing.append(item)
        seen_raw.add(item.get("raw"))
        added += 1
    uadb.save_json("data/youtube-ocr-decks.json", found)
    uadb.save_json("data/community-decks.json", existing)
    print("youtube ocr lists", len(found), "added", added)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
