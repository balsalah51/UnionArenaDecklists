#!/usr/bin/env python3
"""Turn public Union Arena deck photos into 50-card text lists."""

from __future__ import annotations

import json
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import scrape_youtube_ocr as ocr
import match_deck_photo
import uadb
from scrape_community import archetypes, guess_key, item_from_counts, key_from_counts, record, seed_existing

CACHE_FILE = "data/ocr-image-cache.json"
MAX_IMAGES = 160
MAX_WORKERS = 4
MIN_BYTES = 8000
DECK_HINT = re.compile(
    r"deck|list|50.?card|4x\s*ue|ue\d{2}bt|top\s*\d|regional|profile|my\s+50|constructed|exburst|4-0|screenshot",
    re.I,
)
SALE_HINT = re.compile(
    r"\b(?:wtb|wts|buying|selling|sale|bulk|serials?|3\s*stars?|champ cards|pulls?|pulled|for sale)\b",
    re.I,
)
IMG_EXT = re.compile(r"\.(?:png|jpe?g|webp|gif)(?:\?|$)", re.I)
HOST_OK = (
    "i.redd.it",
    "preview.redd.it",
    "i.imgur.com",
    "imgur.com",
    "pbs.twimg.com",
    "media.discordapp.net",
    "cdn.discordapp.com",
    "unionarena-tcg.com",
    "josephwriteranderson.com",
    "shonentcg.com",
    "preview.redd",
)
REDDIT_FEEDS = [
    "https://old.reddit.com/r/Union_Arena_TCG/new.json?limit=100&raw_json=1",
    "https://old.reddit.com/r/Union_Arena_TCG/hot.json?limit=100&raw_json=1",
    "https://old.reddit.com/r/Union_Arena_TCG/top.json?t=month&limit=100&raw_json=1",
    "https://old.reddit.com/r/Union_Arena_TCG/top.json?t=year&limit=100&raw_json=1",
    "https://old.reddit.com/r/UnionArena/new.json?limit=100&raw_json=1",
    "https://old.reddit.com/r/UnionArena/top.json?t=year&limit=100&raw_json=1",
    "https://old.reddit.com/search.json?q=union+arena+decklist&sort=new&t=year&limit=100&raw_json=1",
    "https://old.reddit.com/search.json?q=union+arena+deck+photo&sort=new&t=year&limit=100&raw_json=1",
    "https://old.reddit.com/search.json?q=%22union+arena%22+4xUE&sort=new&t=year&limit=100&raw_json=1",
    "https://old.reddit.com/search.json?q=subreddit%3AUnion_Arena_TCG+self%3Ano&sort=new&t=year&limit=100&raw_json=1",
    "https://www.reddit.com/r/Union_Arena_TCG/new.json?limit=100&raw_json=1",
]
PULLPUSH = [
    "https://api.pullpush.io/reddit/search/submission/?subreddit=Union_Arena_TCG&sort=desc&size=100",
    "https://api.pullpush.io/reddit/search/submission/?subreddit=UnionArena&sort=desc&size=100",
    "https://api.pullpush.io/reddit/search/submission/?q=union%20arena%20decklist&sort=desc&size=100",
    "https://api.pullpush.io/reddit/search/submission/?q=union%20arena%204xUE&sort=desc&size=100",
]
X_QUERIES = [
    "union arena decklist",
    "union arena 4xUE deck",
    "union arena UE23BT decklist",
    "union arena UE22BT decklist",
    "union arena UE19BT decklist",
    "union arena inuyasha decklist",
    "union arena sung jinwoo decklist",
    "union arena sakamoto decklist",
    "\"union arena\" deck photo",
    "site:x.com union arena decklist",
    "exburst.dev union arena deck",
    "\"Decklist Created Using ExBurst\"",
    "union arena deckbuilder screenshot",
]
NITTER = [
    "https://nitter.poast.org/search?f=images&q=",
    "https://nitter.privacyredirect.com/search?f=images&q=",
    "https://nitter.net/search?f=images&q=",
]
BLOG_PAGES = [
    "https://www.josephwriteranderson.com/blog/6-top-union-arena-decks-from-the-virginia-regionals-analyzed-by-deck-sensei",
    "https://www.josephwriteranderson.com/blog/the-best-union-arena-tcg-decks-right-now",
    "https://www.josephwriteranderson.com/blog/union-arena-purple-yuna-deck-list-and-guide",
    "https://www.shonentcg.com/blog/union-arena-current-meta-tier-list",
    "https://www.shonentcg.com/blog/ua-en-meta-tier-list-2026",
    "https://www.unionarena-tcg.com/na/decks/top-placing/",
]


def reddit_headers() -> dict[str, str]:
    return {"User-Agent": uadb.BROWSER_UA, "Accept": "application/json,text/html,*/*"}


def fetch_bytes(url: str, timeout: int = 20) -> bytes:
    url = (url or "").replace("&amp;", "&").strip()
    if not url.startswith("http"):
        return b""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": uadb.BROWSER_UA,
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except Exception:
        raw = b""
    if len(raw) < MIN_BYTES and "preview.redd.it" in url:
        name = Path(urllib.parse.urlparse(url).path).name
        if name:
            return fetch_bytes(f"https://i.redd.it/{name}", timeout=timeout)
    return raw


def looks_like_image(url: str) -> bool:
    low = (url or "").lower()
    if any(host in low for host in HOST_OK):
        return True
    return bool(IMG_EXT.search(low))


def clean_img_url(url: str) -> str:
    url = (url or "").replace("&amp;", "&").strip()
    if url.startswith("//"):
        url = "https:" + url
    if "imgur.com/" in url and not IMG_EXT.search(url) and "/a/" not in url:
        url = url.rstrip("/") + ".jpg"
    if "nitter." in url and "/pic/" in url:
        m = re.search(r"/pic/(?:orig/)?media%2F([^/?]+)", url)
        if m:
            name = urllib.parse.unquote(m.group(1))
            return f"https://pbs.twimg.com/media/{name}"
    if "preview.redd.it" in url:
        url = url.split("?")[0] + "?" + "&".join(
            p for p in urllib.parse.urlparse(url).query.split("&") if p.startswith(("width=", "auto=", "s="))
        )
    return url


def reddit_image_urls(post: dict) -> list[str]:
    urls: list[str] = []
    for key in ("url_overridden_by_dest", "url"):
        raw = post.get(key) or ""
        if looks_like_image(raw):
            urls.append(raw)
    preview = ((post.get("preview") or {}).get("images")) or []
    for img in preview:
        src = ((img.get("source") or {}).get("url")) or ""
        if src:
            urls.append(src)
    meta = post.get("media_metadata") or {}
    for row in meta.values():
        if not isinstance(row, dict):
            continue
        src = ((row.get("s") or {}).get("u")) or ((row.get("s") or {}).get("gif")) or ""
        if src:
            urls.append(src)
    out = []
    seen = set()
    for raw in urls:
        url = clean_img_url(raw)
        if url and url not in seen and looks_like_image(url):
            seen.add(url)
            out.append(url)
    return out


def reddit_date(post: dict) -> str:
    created = post.get("created_utc")
    if not created:
        return ""
    try:
        return datetime.fromtimestamp(float(created), tz=timezone.utc).date().isoformat()
    except Exception:
        return ""


def walk_json_posts(obj, out: list[dict]) -> None:
    if isinstance(obj, dict):
        kind = obj.get("kind")
        data = obj.get("data")
        if kind == "t3" and isinstance(data, dict):
            out.append(data)
            return
        if "title" in obj and ("url" in obj or "permalink" in obj) and "subreddit" in obj:
            out.append(obj)
            return
        for val in obj.values():
            walk_json_posts(val, out)
    elif isinstance(obj, list):
        for item in obj:
            walk_json_posts(item, out)


def load_json_url(url: str) -> object | None:
    status, body = uadb.fetch(url, timeout=22, browser=True, extra_headers=reddit_headers())
    uadb.log("image-json", status, url.split(".com")[-1][:70], "len", len(body))
    if status != 200 or not body.lstrip().startswith(("{", "[")):
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


REDDIT_RSS = [
    "https://www.reddit.com/r/Union_Arena_TCG/.rss?limit=100",
    "https://www.reddit.com/r/Union_Arena_TCG/new/.rss?limit=100",
    "https://old.reddit.com/r/Union_Arena_TCG/top/.rss?t=month&limit=100",
    "https://old.reddit.com/r/Union_Arena_TCG/top/.rss?t=year&limit=100",
    "https://www.reddit.com/r/Union_Arena_TCG/search.rss?q=decklist&restrict_sr=1&sort=new&t=year",
    "https://www.reddit.com/r/Union_Arena_TCG/search.rss?q=exburst&restrict_sr=1&sort=new&t=year",
    "https://www.reddit.com/r/Union_Arena_TCG/search.rss?q=deckbuilder+OR+4xUE+OR+%2250%22&restrict_sr=1&sort=new&t=year",
    "https://www.reddit.com/r/Union_Arena_TCG/search.rss?q=my+list+OR+my+deck&restrict_sr=1&sort=new&t=year",
    "https://www.reddit.com/r/Union_Arena_TCG/search.rss?q=screenshot+OR+%22deck+photo%22&restrict_sr=1&sort=new&t=year",
    "https://www.reddit.com/r/Union_Arena_TCG/search.rss?q=4-0+OR+top+8+OR+regionals&restrict_sr=1&sort=new&t=year",
    "https://www.reddit.com/search.rss?q=union+arena+decklist&sort=new&t=year",
    "https://www.reddit.com/search.rss?q=%22union+arena%22+exburst+deck&sort=new&t=year",
]


def atom_jobs(xml: str) -> list[dict]:
    jobs = []
    blob = (xml or "").replace("&amp;", "&")
    blob = re.sub(r"&quot;", '"', blob)
    for ent in re.findall(r"<entry>(.*?)</entry>", blob, re.S):
        title = re.search(r"<title>([^<]+)</title>", ent)
        link = re.search(r"<link[^>]+href=\"([^\"]+)\"", ent) or re.search(r"<link>([^<]+)</link>", ent)
        author = re.search(r"<name>([^<]+)</name>", ent)
        updated = re.search(r"<updated>([^<]+)</updated>", ent) or re.search(r"<published>([^<]+)</published>", ent)
        title_t = re.sub(r"\s+", " ", (title.group(1) if title else "Reddit list")).strip()
        if not DECK_HINT.search(title_t) and "exburst" not in title_t.lower() and "list" not in title_t.lower():
            # still keep UA subreddit images; filter later only if no images
            pass
        images = []
        for raw in re.findall(r"https://(?:i|preview)\.redd\.it/[A-Za-z0-9]+\.(?:png|jpe?g|webp)", ent, re.I):
            images.append(clean_img_url(raw.split("?")[0].replace("preview.redd.it", "i.redd.it")))
        for raw in re.findall(r"https://i\.imgur\.com/[A-Za-z0-9]+\.(?:png|jpe?g|webp)", ent, re.I):
            images.append(clean_img_url(raw))
        images = list(dict.fromkeys(images))
        text_blob = re.sub(r"<[^>]+>", " ", ent)
        text_counts = uadb.parse_counts(text_blob)
        if not images and not uadb.list_is_complete(text_counts):
            continue
        source = link.group(1) if link else (images[0] if images else "")
        date = ""
        if updated:
            date = updated.group(1)[:10]
        pid = re.search(r"/comments/([a-z0-9]+)/", source or "")
        jobs.append(
            {
                "kind": "reddit",
                "player": (author.group(1) if author else "Reddit").replace("/u/", ""),
                "title": title_t,
                "subtitle": "Deck photo converted to a 50-card list",
                "source_url": source,
                "date": date,
                "slug": f"reddit-pic-{title_t}-{pid.group(1) if pid else (images[0][-12:] if images else 'text')}",
                "images": images[:8],
                "hint": title_t,
                "counts": text_counts if uadb.list_is_complete(text_counts) else {},
            }
        )
    return jobs


def collect_reddit_jobs() -> list[dict]:
    jobs: list[dict] = []
    seen = set()
    for url in REDDIT_RSS:
        status, body = uadb.fetch(url, timeout=22, browser=True)
        uadb.log("reddit rss", status, url.split(".com")[-1][:70], "entry", body.count("<entry"))
        for job in atom_jobs(body):
            key = job.get("source_url") or job.get("slug")
            if not key or key in seen:
                continue
            seen.add(key)
            jobs.append(job)
        time.sleep(3.2)
    uadb.log("reddit image jobs", len(jobs))
    return jobs


def html_image_urls(html: str) -> list[str]:
    urls = []
    for raw in re.findall(r'(?:src|data-src|href|murl|imgurl)=["\']([^"\']+)', html or "", re.I):
        url = clean_img_url(urllib.parse.unquote(raw))
        if looks_like_image(url):
            urls.append(url)
    for raw in re.findall(r"https?://[^\s\"'<>]+", html or ""):
        url = clean_img_url(raw.rstrip(").,;"))
        if looks_like_image(url) and any(h in url for h in HOST_OK):
            urls.append(url)
    return list(dict.fromkeys(urls))


def collect_x_jobs() -> list[dict]:
    jobs: list[dict] = []
    seen = set()
    ddg = "https://html.duckduckgo.com/html/?q="
    bing = "https://www.bing.com/images/search?q="
    for q in X_QUERIES:
        encoded = urllib.parse.quote_plus(q)
        pages = [ddg + encoded, bing + encoded + "&qft=+filterui:imagesize-large"]
        pages.extend(host + encoded for host in NITTER)
        for url in pages:
            status, body = uadb.fetch(url, timeout=20, browser=True)
            uadb.log("x image search", status, q[:42], "imgs", len(html_image_urls(body)))
            if status != 200 or len(body) < 200:
                continue
            for i, image in enumerate(html_image_urls(body)):
                if image in seen:
                    continue
                if any(bad in image for bad in ("duckduckgo.com/assets", "anomaly/images", "Flag_Feedback", "bing.com/sa/")):
                    continue
                if not any(h in image for h in ("pbs.twimg.com", "twimg", "imgur", "redd.it", "discord", "exburst", "unionarena", "media")):
                    if "x.com" not in image and "twitter" not in image:
                        continue
                seen.add(image)
                jobs.append(
                    {
                        "kind": "twitter",
                        "player": "X",
                        "title": f"X deck photo · {q}",
                        "subtitle": "Deck photo converted to a 50-card list",
                        "source_url": image if "pbs.twimg.com" in image else url.split("?")[0],
                        "date": "",
                        "slug": f"x-pic-{q}-{i}",
                        "images": [image],
                        "hint": q,
                    }
                )
            time.sleep(0.12)
    uadb.log("x image jobs", len(jobs))
    return jobs


def collect_other_jobs() -> list[dict]:
    jobs: list[dict] = []
    seen = set()
    for page in BLOG_PAGES:
        status, body = uadb.fetch(page, timeout=22, browser=True)
        uadb.log("other images", status, page[-48:], "imgs", len(html_image_urls(body)))
        if status != 200:
            continue
        for i, image in enumerate(html_image_urls(body)):
            if image in seen or image.endswith(".svg"):
                continue
            if not any(h in image for h in ("josephwriter", "shonentcg", "unionarena-tcg", "imgur", "redd.it")):
                continue
            seen.add(image)
            jobs.append(
                {
                    "kind": "web",
                    "player": "Community",
                    "title": "Community deck photo",
                    "subtitle": "Deck photo converted to a 50-card list",
                    "source_url": page,
                    "date": "",
                    "slug": f"web-pic-{Path(urllib.parse.urlparse(page).path).name}-{i}",
                    "images": [image],
                    "hint": page,
                }
            )
        time.sleep(0.1)
    uadb.log("other image jobs", len(jobs))
    return jobs


def ocr_urls(urls: list[str], cache: dict, idx: dict[str, str], ocr_cache: dict, art_index: dict | None = None, hint: str = "") -> dict[str, int]:
    merged: dict[str, int] = {}
    with tempfile.TemporaryDirectory(prefix="uadb-pic-") as td:
        tmp = Path(td)
        for i, url in enumerate(urls):
            cached = ocr_cache.get(url)
            if isinstance(cached, dict) and uadb.list_is_complete({k: int(v) for k, v in cached.items()}):
                ocr.merge_counts(merged, {k: int(v) for k, v in cached.items()})
                continue
            raw = fetch_bytes(url)
            if len(raw) < MIN_BYTES:
                ocr_cache[url] = {}
                continue
            ext = ".png" if raw[:8] == b"\x89PNG\r\n\x1a\n" else ".jpg"
            dest = tmp / f"img-{i}{ext}"
            dest.write_bytes(raw)
            counts: dict[str, int] = {}
            if art_index:
                ocr.merge_counts(counts, match_deck_photo.counts_from_photo(dest, cache, art_index, hint=hint))
            if not uadb.list_is_complete(counts):
                ocr.merge_counts(counts, ocr.ocr_image(dest, cache, idx, quick=True))
            ocr_cache[url] = counts
            ocr.merge_counts(merged, counts)
            if len(ocr_cache) % 8 == 0:
                uadb.save_json(CACHE_FILE, ocr_cache)
            if len(merged) >= 12 and sum(merged.values()) >= uadb.MIN_CARDS:
                break
    return merged


def set_share(counts: dict[str, int]) -> float:
    bags: dict[str, int] = {}
    for cid, n in counts.items():
        code = match_deck_photo.set_code(cid) or (cid.split("/")[0] if "/" in cid else cid[:5])
        bags[code] = bags.get(code, 0) + int(n)
    total = sum(counts.values())
    if not bags or total < 1:
        return 0.0
    return max(bags.values()) / total


def ingest_job(job: dict, cache: dict, idx: dict[str, str], arches: list[dict], ocr_cache: dict, art_index: dict | None = None) -> dict | None:
    title = job.get("title") or job.get("hint") or ""
    if SALE_HINT.search(title):
        uadb.log("pic skip sale", title[:48])
        return None
    counts = {k: int(v) for k, v in (job.get("counts") or {}).items() if int(v) > 0}
    if not uadb.list_is_complete(counts):
        counts = ocr_urls(job.get("images") or [], cache, idx, ocr_cache, art_index=art_index, hint=job.get("hint") or title)
    photo_ok = len(counts) >= 8 and 40 <= sum(counts.values()) <= 60 and set_share(counts) >= 0.72
    if not ((uadb.list_is_complete(counts) and set_share(counts) >= 0.72) or photo_ok):
        uadb.log("pic miss", job.get("kind"), title[:48], "unique", len(counts), "cards", sum(counts.values()), "set", f"{set_share(counts):.2f}")
        return None
    hint = job.get("hint") or job.get("title") or ""
    key = guess_key(hint, counts, cache, arches) or key_from_counts(counts, cache)
    named = {
        cid: n
        for cid, n in counts.items()
        if any(
            tok in ((cache.get(cid) or {}).get("name") or "").lower()
            for tok in match_deck_photo.title_tokens(hint)
        )
    }
    titled = key_from_counts(named, cache) if named else None
    if titled:
        key = titled
    if not key:
        uadb.log("pic no-key", job.get("kind"), sum(counts.values()))
        return None
    uadb.log("pic hit", job.get("kind"), key, "cards", sum(counts.values()), (job.get("title") or "")[:40])
    return item_from_counts(
        counts,
        key=key,
        kind=job.get("kind") or "image",
        player=job.get("player") or "Community",
        title=(job.get("title") or key)[:90],
        subtitle=job.get("subtitle") or "Deck photo converted to a 50-card list",
        source_url=job.get("source_url") or "",
        slug=uadb.slugify(job.get("slug") or f"pic-{key}")[:70],
        date=job.get("date") or "",
    )


def scrape_images(
    found: list[dict],
    seen: set[str],
    cache: dict,
    arches: list[dict],
    *,
    include_other: bool = True,
    include_x: bool = True,
) -> int:
    if not ocr.ocr_available():
        uadb.log("image ocr skipped: tesseract missing")
        return 0
    idx = ocr.compact_index(cache)
    ocr_cache = uadb.load_json(CACHE_FILE, {})
    art_index = match_deck_photo.load_index()
    if len(art_index) < 400:
        art_index = match_deck_photo.ensure_index(cache)
    uadb.log("card art index loaded", len(art_index))
    jobs = collect_reddit_jobs()
    if include_x:
        jobs.extend(collect_x_jobs())
    if include_other:
        jobs.extend(collect_other_jobs())
    jobs.sort(
        key=lambda j: (
            0 if DECK_HINT.search(j.get("title") or j.get("hint") or "") else 1,
            0 if j.get("counts") else 1,
        )
    )
    picked = []
    seen_img = set()
    for job in jobs:
        title = job.get("title") or job.get("hint") or ""
        if SALE_HINT.search(title):
            continue
        if not DECK_HINT.search(title) and not job.get("counts"):
            continue
        images = [u for u in (job.get("images") or []) if u not in seen_img]
        if job.get("kind") == "twitter" and not any(
            any(h in u for h in ("pbs.twimg.com", "i.redd.it", "i.imgur.com", "exburst")) for u in images
        ):
            continue
        if not images and not job.get("counts"):
            continue
        for u in images:
            seen_img.add(u)
        job = dict(job)
        job["images"] = images
        picked.append(job)
        if len(picked) >= MAX_IMAGES:
            break
    uadb.log("image jobs to ocr", len(picked))
    added = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = [pool.submit(ingest_job, job, cache, idx, arches, ocr_cache, art_index) for job in picked]
        for fut in as_completed(futs):
            try:
                item = fut.result()
            except Exception as exc:  # noqa: BLE001
                uadb.log("pic error", type(exc).__name__, exc)
                continue
            if item and record(found, item, seen):
                added += 1
    uadb.save_json(CACHE_FILE, ocr_cache)
    uadb.log("image lists added", added)
    return added


def main() -> int:
    import sys

    cache = uadb.load_json("data/card-cache.json", {})
    extra = uadb.load_json("data/contender-cards.json", {})
    for cid, card in extra.items():
        cache.setdefault(cid, {}).update({k: v for k, v in card.items() if v})
    arches = archetypes()
    found: list[dict] = []
    seen: set[str] = set()
    seed_existing(found, seen)
    before = len(found)
    scrape_images(
        found,
        seen,
        cache,
        arches,
        include_other="--skip-other" not in sys.argv,
        include_x="--skip-x" not in sys.argv,
    )
    from scrape_community import collapse_by_slug

    stored = collapse_by_slug(found)
    uadb.save_json("data/community-decks.json", stored)
    uadb.log("community lists", len(stored), "new from photos", len(stored) - before)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
