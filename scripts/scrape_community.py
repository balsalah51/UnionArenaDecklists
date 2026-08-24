#!/usr/bin/env python3
"""Pull public Union Arena 50-card lists from YouTube and official pages.

Uses complete NxSET/CODE (or _/-) text lists, official Bandai recipes, and
on-screen lists read from YouTube thumbnails and early video frames.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import uadb

YT_ID_RE = re.compile(r"(?:watch\?v=|/shorts/|youtu\.be/)([A-Za-z0-9_-]{11})")
YT_JSON_ID_RE = re.compile(r'"videoId":"([A-Za-z0-9_-]{11})"')
RECIPE_RE = re.compile(r"bandai-tcg-plus\.com/deck_code_recipe/([A-Za-z0-9]+)", re.I)
HTTP_RE = re.compile(r"https?://[^\s\"'<>]+")
YT_CLIENT = {
    "clientName": "WEB",
    "clientVersion": "2.20240815.00.00",
    "hl": "en",
    "gl": "US",
}
SET_PREFIX = {
    "SLG": "solo-leveling",
    "SMD": "sakamoto-days",
    "EVA": "evangelion",
    "CSM": "csm",
    "JJK": "jujutsu-kaisen",
    "RNK": "rurouni-kenshin",
    "KGR": "kagurabachi",
    "SAO": "sword-art-online",
    "TSK": "that-time-i-got-reincarnated-as-a-slime",
    "TKG": "tokyo-ghoul",
    "BLC": "bleach",
    "CGH": "code-geass",
    "OPM": "one-punch-man",
    "RLY": "the-100-girlfriends",
}
WEB_PAGES = [
    "https://www.josephwriteranderson.com/blog/6-top-union-arena-decks-from-the-virginia-regionals-analyzed-by-deck-sensei",
    "https://www.unionarena-tcg.com/na/decks/top-placing/",
]


def innertube(path: str, payload: dict) -> dict:
    url = f"https://www.youtube.com/youtubei/v1/{path}?prettyPrint=false"
    raw = json.dumps({"context": {"client": YT_CLIENT}, **payload}).encode()
    status, body = uadb.fetch(url, timeout=28, data=raw, content_type="application/json", browser=True)
    if status != 200 or not body.startswith("{"):
        uadb.log("innertube", path, status, len(body))
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {}


def video_ids_from(blob: str) -> list[str]:
    ids = YT_JSON_ID_RE.findall(blob or "") + YT_ID_RE.findall(blob or "")
    return list(dict.fromkeys(ids))


def walk_strings(obj, found: list[str], budget: int = 40) -> None:
    if len(found) >= budget:
        return
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key in {"content", "simpleText", "text", "title"} and isinstance(val, str) and len(val) > 40:
                found.append(val)
            else:
                walk_strings(val, found, budget)
    elif isinstance(obj, list):
        for item in obj[:120]:
            walk_strings(item, found, budget)


def youtube_publish_date(vid: str) -> str:
    status, html = uadb.fetch(f"https://www.youtube.com/watch?v={vid}", timeout=20, browser=True)
    if status != 200:
        return ""
    m = re.search(r'"publishDate"\s*:\s*"(\d{4}-\d{2}-\d{2})"', html)
    if not m:
        m = re.search(r'"uploadDate"\s*:\s*"(\d{4}-\d{2}-\d{2})"', html)
    return m.group(1) if m else ""


def youtube_search(query: str) -> list[str]:
    data = innertube("search", {"query": query})
    ids = video_ids_from(json.dumps(data))
    if ids:
        return ids
    q = urllib.parse.quote_plus(query)
    status, html = uadb.fetch(f"https://www.youtube.com/results?search_query={q}", timeout=25, browser=True)
    uadb.log("yt search html", status, query[:60], "ids", len(video_ids_from(html)))
    return video_ids_from(html)


def youtube_video(vid: str) -> dict:
    data = innertube("next", {"videoId": vid})
    title = ""
    desc = ""
    strings: list[str] = []
    walk_strings(data, strings, 80)
    for s in strings:
        low = s.lower()
        if not title and 12 <= len(s) <= 140 and "http" not in low:
            if "union arena" in low or " - " in s:
                title = s
        if len(s) > len(desc) and ("http" in low or "4x" in low or "UE" in s or "deck" in low):
            desc = s
    if not title:
        for s in strings:
            if 16 <= len(s) <= 140:
                title = s
                break
    return {"id": vid, "title": title.strip(), "desc": desc, "blob": "\n".join(strings)}


def archetypes() -> list[dict]:
    fmt = uadb.load_json("data/contender-format.json", {})
    rows = []
    for name in (fmt.get("deckDetails") or {}):
        title, char = name.split(" - ", 1) if " - " in name else (name, name)
        rows.append({"key": uadb.slugify(name), "full": name, "title": title, "name": char})
    return rows


COLOR_ONLY = {"purple", "red", "yellow", "green", "blue", "black"}


def guess_key(text: str, counts: dict[str, int], cache: dict, arches: list[dict], set_hint: str = "") -> str | None:
    blob = f"{text}".lower()
    needles = []
    for arch in arches:
        if arch["name"].lower() in COLOR_ONLY:
            continue
        needles.append((arch["full"].lower(), arch["key"]))
        needles.append((arch["name"].lower(), arch["key"]))
    needles.sort(key=lambda row: -len(row[0]))
    named_hit = None
    for needle, key in needles:
        if len(needle) >= 5 and needle in blob:
            named_hit = key
            break
    prefixes: dict[str, int] = {}
    if set_hint:
        prefixes[set_hint.upper()] = 99
    for cid, n in counts.items():
        m = re.search(r"/([A-Z]{2,4})-\d-", cid)
        if m:
            prefixes[m.group(1)] = prefixes.get(m.group(1), 0) + n
    title_slug = SET_PREFIX.get(max(prefixes, key=prefixes.get), "") if prefixes else ""
    cands = [a for a in arches if title_slug and a["key"].startswith(title_slug + "-")]
    if named_hit and (not cands or named_hit in {a["key"] for a in cands}):
        return named_hit
    best, best_n = None, -1
    for arch in cands or arches:
        score = 0
        char_n = re.sub(r"[^a-z0-9]+", " ", arch["name"].lower())
        if char_n in COLOR_ONLY:
            score -= 5
        for cid, n in counts.items():
            name = (cache.get(cid) or {}).get("name") or cid
            if char_n and char_n not in COLOR_ONLY and char_n in name.lower():
                score += n + 2
        color_m = re.search(r"【(purple|red|yellow|green|blue|black)】", blob)
        if color_m and arch["name"].lower() == color_m.group(1):
            score += 8
        if score > best_n:
            best, best_n = arch["key"], score
    if best_n > 0:
        return best
    if cands:
        color_m = re.search(r"【(purple|red|yellow|green|blue|black)】", blob)
        if color_m:
            for arch in cands:
                if arch["name"].lower() == color_m.group(1):
                    return arch["key"]
        return cands[0]["key"]
    return named_hit


def record(found: list[dict], item: dict, seen: set[str]) -> None:
    raw = item.get("raw") or ""
    if not raw or raw in seen:
        return
    seen.add(raw)
    found.append(item)
    uadb.log("found", item.get("kind"), item.get("key"), item.get("slug"), "cards", item.get("cards"))


def item_from_counts(
    counts: dict[str, int],
    *,
    key: str,
    kind: str,
    player: str,
    title: str,
    subtitle: str,
    source_url: str,
    slug: str,
    date: str = "",
) -> dict:
    raw = " ".join(f"{n}x{cid}" for cid, n in sorted(counts.items()))
    return {
        "key": key,
        "kind": kind,
        "slug": slug[:70],
        "player": player,
        "title": title[:110],
        "subtitle": subtitle,
        "source_url": source_url,
        "date": date,
        "raw": raw,
        "counts": counts,
        "cards": sum(counts.values()),
    }


def cid_from_bandai(card: dict) -> str | None:
    number = (card.get("card_number") or "").upper()
    img = card.get("image_url") or ""
    m = re.search(r"(?:batch_)(?:dummy_)?((?:UEX|UE|UA|ST)[A-Z0-9]+)_", img, re.I)
    if m and number and "-AP" not in number:
        return f"{m.group(1).upper()}/{number}"
    m2 = re.search(r"((?:UEX|UE|ST)[A-Z0-9]+)[_-]([A-Z]{2,4}-\d-\d{3})", img, re.I)
    if m2 and "-AP" not in m2.group(2).upper():
        return f"{m2.group(1).upper()}/{m2.group(2).upper()}"
    return uadb.normalize_cid(number)


def bandai_recipe(code: str) -> tuple[dict[str, int], dict]:
    headers = {
        "Origin": "https://www.bandai-tcg-plus.com",
        "Referer": "https://www.bandai-tcg-plus.com/",
    }
    meta: dict = {}
    for attempt in range(4):
        status, body = uadb.fetch(
            f"https://api.bandai-tcg-plus.com/api/user/deck/url_code?deck_code={urllib.parse.quote(code)}",
            timeout=22,
            browser=True,
            extra_headers=headers,
        )
        if status != 200 or not body.startswith("{"):
            time.sleep(0.4 * (attempt + 1))
            continue
        meta = json.loads(body).get("success") or {}
        url_code = meta.get("url_code") or ""
        gid = meta.get("game_title_id")
        if not url_code or gid is None:
            time.sleep(0.3)
            continue
        q = urllib.parse.urlencode({"url_code": url_code, "game_title_id": gid})
        st2, body2 = uadb.fetch(
            f"https://api.bandai-tcg-plus.com/api/user/deck/recipe?{q}",
            timeout=22,
            browser=True,
            extra_headers=headers,
        )
        if st2 != 200 or not body2.startswith("{"):
            time.sleep(0.4 * (attempt + 1))
            continue
        cards = ((json.loads(body2).get("success") or {}).get("main_deck")) or []
        counts: dict[str, int] = {}
        for card in cards:
            cid = cid_from_bandai(card)
            n = int(card.get("card_count") or 0)
            if cid and n:
                counts[cid] = max(counts.get(cid, 0), n)
        if sum(counts.values()) >= uadb.MIN_CARDS:
            return counts, meta
        time.sleep(0.35 * (attempt + 1))
    return {}, meta


def scrape_official(found: list[dict], seen: set[str], cache: dict, arches: list[dict]) -> None:
    status, html = uadb.fetch("https://www.unionarena-tcg.com/na/decks/top-placing/", timeout=30, browser=True)
    uadb.log("official top-placing", status, "len", len(html))
    blocks = re.findall(r'<li class="decksDetail.*?</li>', html, re.S)
    uadb.log("official tiles", len(blocks))

    def one(block: str) -> dict | None:
        m = RECIPE_RE.search(block)
        if not m:
            return None
        code = m.group(1)
        tit = re.search(r'js_decksTit">(.*?)</span>', block, re.S)
        label = re.sub(r"<br\s*/?>", " · ", tit.group(1) if tit else "")
        label = re.sub(r"<[^>]+>", "", label)
        label = re.sub(r"\s+", " ", label).strip()
        event = re.search(r"decksCategory.*?>([^<]+)</a>", block, re.S)
        event_name = re.sub(r"\s+", " ", event.group(1)).strip() if event else "Official event"
        date_m = re.search(r"Reveal Date</span><br>([^<]+)", block)
        date = ""
        if date_m:
            try:
                date = str(datetime.strptime(date_m.group(1).strip(), "%B %d, %Y").date())
            except Exception:
                date = date_m.group(1).strip()
        tags = re.search(r'data-tags="([^"]+)"', block)
        set_hint = ""
        if tags:
            parts = [p.strip() for p in tags.group(1).split(",") if re.fullmatch(r"[A-Z]{2,4}", p.strip())]
            set_hint = parts[-1] if parts else ""
        counts, _meta = bandai_recipe(code)
        if not uadb.list_is_complete(counts):
            uadb.log("official skip", code, "cards", sum(counts.values()), label[:40])
            return None
        key = guess_key(label + " " + event_name, counts, cache, arches, set_hint=set_hint)
        if not key:
            uadb.log("official no-key", code, label[:50])
            return None
        place = label.split("·")[0].strip() if "·" in label else "Official"
        slug = uadb.slugify(f"official-{place}-{key}-{code[-6:]}")
        return item_from_counts(
            counts,
            key=key,
            kind="official",
            player=place or "Official",
            title=f"{label} - {event_name}"[:110],
            subtitle=f"Official Bandai top-placing list · {event_name}",
            source_url=f"https://www.bandai-tcg-plus.com/deck_code_recipe/{code}",
            slug=slug,
            date=date,
        )

    with ThreadPoolExecutor(max_workers=3) as pool:
        futs = [pool.submit(one, b) for b in blocks]
        for fut in as_completed(futs):
            item = fut.result()
            if item:
                record(found, item, seen)
            time.sleep(0.02)


def scrape_web_pages(found: list[dict], seen: set[str], cache: dict, arches: list[dict]) -> None:
    for url in WEB_PAGES:
        status, body = uadb.fetch(url, timeout=28, browser=True)
        uadb.log("web", status, url[:80], "ids", len(uadb.CID_TOKEN_RE.findall(body)))
        # Split on 50-card markers so multiple lists on one page stay separate.
        chunks = re.split(r"(?i)total:\s*50\s*cards", body)
        if len(chunks) == 1:
            chunks = [body]
        for i, chunk in enumerate(chunks):
            window = chunk if i == 0 else chunks[i - 1][-2500:] + chunk[:800]
            counts = uadb.parse_counts(window)
            if not uadb.list_is_complete(counts):
                continue
            key = guess_key(window[:1500] + " " + url, counts, cache, arches)
            if not key:
                continue
            slug = uadb.slugify(f"web-{key}-{i}-{url.split('/')[-1]}")[:70]
            record(
                found,
                item_from_counts(
                    counts,
                    key=key,
                    kind="web",
                    player="Community",
                    title="Community list",
                    subtitle="Public deck page",
                    source_url=url,
                    slug=slug,
                ),
                seen,
            )


def youtube_queries(arches: list[dict]) -> list[str]:
    queries = [
        "Union Arena deck profile",
        "Union Arena decklist 50 cards",
        "Union Arena DamosTCG deck profile",
        "DamosTCG Union Arena decklist",
        "SpencerUA Union Arena deck",
        "Union Arena regionals decklist",
        "Union Arena Sung Jinwoo decklist",
        "Union Arena Hajime Saito deck profile",
        "Union Arena Shin Asakura deck profile",
        "Union Arena Rei Ayanami decklist",
        "Union Arena Taro Sakamoto deck profile",
        "Union Arena Denji Chainsaw Man decklist",
        "Union Arena Power CSM deck profile",
        "Union Arena Rimuru decklist",
        "Union Arena Yuna SAO deck profile",
        "Union Arena Hakuri Kagurabachi decklist",
        "Union Arena Cha Hae-In deck profile",
        "Union Arena 4xUE17BT",
        "Union Arena 4xUE19BT",
        "Union Arena 4xUE15BT",
        "Union Arena 4xUE22BT",
        "Union Arena 4xUE11BT Saito",
        "EVERY TOP 16 DECK LIST Union Arena",
        "EVERY TOP 32 DECK LIST Union Arena",
    ]
    # A few more character names from the current meta snapshot
    for arch in arches[:18]:
        queries.append(f"Union Arena {arch['name']} deck profile")
        queries.append(f"Union Arena {arch['name']} decklist")
    return list(dict.fromkeys(queries))


def follow_links(text: str, cache: dict, arches: list[dict]) -> list[dict]:
    out = []
    for href in HTTP_RE.findall(text or ""):
        href = href.rstrip(").,]")
        m = RECIPE_RE.search(href)
        if m:
            counts, _ = bandai_recipe(m.group(1))
            if uadb.list_is_complete(counts):
                key = guess_key(text, counts, cache, arches)
                if key:
                    out.append(
                        item_from_counts(
                            counts,
                            key=key,
                            kind="official",
                            player="YouTube",
                            title="Bandai recipe linked from YouTube",
                            subtitle="Official recipe linked in a YouTube description",
                            source_url=f"https://www.bandai-tcg-plus.com/deck_code_recipe/{m.group(1)}",
                            slug=uadb.slugify(f"yt-recipe-{key}-{m.group(1)[-6:]}"),
                        )
                    )
            continue
        if any(host in href for host in ("josephwriteranderson.com", "unionarena-tcg.com")):
            status, body = uadb.fetch(href, timeout=20, browser=True)
            counts = uadb.parse_counts(body)
            if uadb.list_is_complete(counts):
                key = guess_key(body[:2000] + " " + text, counts, cache, arches)
                if key:
                    out.append(
                        item_from_counts(
                            counts,
                            key=key,
                            kind="web",
                            player="Community",
                            title="Linked deck page",
                            subtitle="Public page linked from a YouTube description",
                            source_url=href,
                            slug=uadb.slugify(f"yt-web-{key}-{href.split('/')[-1]}"),
                        )
                    )
    return out


def scrape_youtube(found: list[dict], seen: set[str], cache: dict, arches: list[dict]) -> list[tuple[str, str]]:
    ids: list[str] = []
    titles: dict[str, str] = {}
    for query in youtube_queries(arches):
        for vid in youtube_search(query):
            if vid not in ids:
                ids.append(vid)
        time.sleep(0.12)
    uadb.log("youtube unique videos", len(ids))
    tagged: list[tuple[str, str]] = []
    for vid in ids[:160]:
        info = youtube_video(vid)
        title = info.get("title") or ""
        titles[vid] = title
        tagged.append((vid, title))
        blob = " ".join([title, info.get("desc") or "", info.get("blob") or ""])
        url = f"https://www.youtube.com/watch?v={vid}"
        counts = uadb.parse_counts(blob)
        title_l = title.lower()
        if not any(w in title_l for w in ("deck", "list", "profile", "top 8", "top 16", "top 32", "1st", "2nd", "3rd")):
            continue
        if uadb.list_is_complete(counts):
            key = guess_key(blob, counts, cache, arches)
            if key:
                player = re.sub(r"\s*[-|].*", "", title)[:40] or "YouTube"
                record(
                    found,
                    item_from_counts(
                        counts,
                        key=key,
                        kind="youtube",
                        player=player,
                        title=title[:90] or f"{key} YouTube list",
                        subtitle="YouTube deck profile from a public description",
                        source_url=url,
                        slug=uadb.slugify(f"yt-{player}-{key}-{vid}"),
                        date=youtube_publish_date(vid),
                    ),
                    seen,
                )
        for extra in follow_links(blob, cache, arches):
            extra["subtitle"] = extra.get("subtitle") or "Linked from YouTube"
            record(found, extra, seen)
        time.sleep(0.08)
    return tagged


def main() -> None:
    cache = uadb.load_json("data/card-cache.json", {})
    extra = uadb.load_json("data/contender-cards.json", {})
    for cid, card in extra.items():
        cache.setdefault(cid, {}).update({k: v for k, v in card.items() if v})
    arches = archetypes()
    found: list[dict] = []
    seen: set[str] = set()
    scrape_official(found, seen, cache, arches)
    scrape_web_pages(found, seen, cache, arches)
    video_ids: list[tuple[str, str]] = []
    if "--skip-youtube" not in sys.argv:
        video_ids = scrape_youtube(found, seen, cache, arches)
        if "--skip-ocr" not in sys.argv:
            import scrape_youtube_ocr

            scrape_youtube_ocr.scrape_ocr(found, seen, cache, arches, video_ids)
    stored = []
    for item in found:
        row = dict(item)
        row["counts"] = item.get("counts") or {}
        stored.append(row)
    uadb.save_json("data/community-decks.json", stored)
    uadb.log("community lists", len(stored))


if __name__ == "__main__":
    main()
