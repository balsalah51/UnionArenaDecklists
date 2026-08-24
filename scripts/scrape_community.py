#!/usr/bin/env python3
"""Scrape public YouTube / web pages for complete NxSET-NNN Union Arena lists.

Same style as One Piece Deck Base community scrape, different sites and ID regex.
Does not invent cards from screenshots.
"""

from __future__ import annotations

import json
import re
import urllib.parse

import uadb

TARGET_KEYS = {
    "sung jinwoo": "solo-leveling-sung-jinwoo",
    "hajime saito": "rurouni-kenshin-hajime-saito",
    "shin asakura": "sakamoto-days-shin-asakura",
    "rei ayanami": "evangelion-rei-ayanami",
    "taro sakamoto": "sakamoto-days-taro-sakamoto",
    "aoi todo": "jujutsu-kaisen-aoi-todo",
    "kenshin himura": "rurouni-kenshin-kenshin-himura",
    "heisuke mashimo": "sakamoto-days-heisuke-mashimo",
    "denji": "csm-denji",
    "power": "csm-power",
    "yuna": "sword-art-online-yuna",
    "hakuri": "kagurabachi-hakuri-sazanami",
    "rimuru": "that-time-i-got-reincarnated-as-a-slime-rimuru",
    "cha hae": "solo-leveling-cha-hae-in",
}

QUERIES = [
    "Union Arena Sung Jinwoo decklist youtube",
    "Union Arena Hajime Saito decklist youtube",
    "Union Arena Shin Asakura decklist youtube",
    "Union Arena Rei Ayanami decklist youtube",
    "Union Arena Taro Sakamoto decklist youtube",
    "Union Arena Aoi Todo decklist youtube",
    "Union Arena Kenshin Himura decklist 50 cards",
    "Union Arena Heisuke Mashimo decklist youtube",
    "Union Arena Denji decklist youtube",
    "Union Arena Yuna SAO decklist youtube",
    "Union Arena Hakuri Sazanami decklist",
    "Union Arena Rimuru decklist youtube",
    "exburst.dev ua en decklist",
    "egmanevents unionarena decklist",
]


def parse_counts(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for n, cid in uadb.LINE_RE.findall(text or ""):
        cid = cid.upper()
        counts[cid] = counts.get(cid, 0) + int(n)
    return counts


def complete(counts: dict[str, int]) -> bool:
    total = sum(counts.values())
    if any(cid in uadb.RESTRICTED_ONE and counts[cid] > 1 for cid in counts):
        return False
    return 46 <= total <= 54


def ddg(query: str) -> str:
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    status, body = uadb.fetch(url, timeout=14)
    uadb.log("ddg", status, query[:70])
    return body


def youtube_ids(html: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{8,})", html)))


def guess_key(text: str) -> str | None:
    low = (text or "").lower()
    for needle, key in TARGET_KEYS.items():
        if needle in low:
            return key
    return None


def record(found: list[dict], item: dict, seen: set[str]) -> None:
    key = item["raw"]
    if key in seen:
        return
    seen.add(key)
    found.append(item)
    uadb.log("found", item.get("key"), item.get("kind"), item.get("slug"), "cards", item.get("cards"))


def scrape_youtube(found: list[dict], seen: set[str]) -> None:
    for query in QUERIES:
        body = ddg(query)
        hrefs = re.findall(r'href="(https?://[^"]+)"', body)
        for href in hrefs[:8]:
            if "youtube.com" not in href and "youtu.be" not in href:
                continue
            status, page = uadb.fetch(href, timeout=16)
            uadb.log("yt", status, href[:80])
            counts = parse_counts(page)
            if not complete(counts):
                # Try the description-only watch page query param
                continue
            key = guess_key(page + " " + query)
            if not key:
                continue
            title_m = re.search(r"<title>([^<]+)</title>", page, re.I)
            title = re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else "YouTube list"
            player = re.sub(r"\s*[-|].*", "", title)[:40] or "YouTube"
            slug = uadb.slugify(f"yt-{player}-{key}")[:70]
            raw = " ".join(f"{n}x{cid}" for cid, n in sorted(counts.items()))
            record(
                found,
                {
                    "key": key,
                    "kind": "youtube",
                    "slug": slug,
                    "player": player,
                    "title": title[:90],
                    "subtitle": "YouTube deck profile from a public description",
                    "source_url": href,
                    "date": "",
                    "raw": raw,
                    "counts": counts,
                    "cards": sum(counts.values()),
                },
                seen,
            )


def scrape_web(found: list[dict], seen: set[str]) -> None:
    queries = [
        "site:exburst.dev union arena decklist UE17BT",
        "site:deckbuilder.egmanevents.com unionarena 4xUE",
        "Union Arena 4xUE17BT/SLG decklist",
        "Union Arena 4xUE19BT/SMD decklist",
        "Union Arena 4xUE15BT/EVA decklist",
        "Union Arena 4xUE22BT/CSM decklist",
    ]
    for query in queries:
        body = ddg(query)
        hrefs = re.findall(r'uddg=([^&"]+)', body) + re.findall(r'href="(https?://[^"]+)"', body)
        urls = []
        for h in hrefs:
            try:
                urls.append(urllib.parse.unquote(h))
            except Exception:
                urls.append(h)
        for href in urls[:6]:
            if not href.startswith("http"):
                continue
            if any(bad in href for bad in ("duckduckgo.com", "youtube.com", "facebook.com")):
                continue
            status, page = uadb.fetch(href, timeout=16)
            uadb.log("web", status, href[:90])
            counts = parse_counts(page)
            if not complete(counts):
                continue
            key = guess_key(page + " " + query) or guess_key(href)
            if not key:
                continue
            slug = uadb.slugify(f"web-{key}-{href.split('/')[-1]}")[:70]
            raw = " ".join(f"{n}x{cid}" for cid, n in sorted(counts.items()))
            record(
                found,
                {
                    "key": key,
                    "kind": "web",
                    "slug": slug,
                    "player": "Community",
                    "title": "Community list",
                    "subtitle": "Public deck page",
                    "source_url": href,
                    "date": "",
                    "raw": raw,
                    "counts": counts,
                    "cards": sum(counts.values()),
                },
                seen,
            )


def main() -> None:
    found: list[dict] = []
    seen: set[str] = set()
    extra = uadb.load_json("data/community-decks.json", [])
    for item in extra:
        if item.get("raw"):
            seen.add(item["raw"])
            found.append(item)
    scrape_youtube(found, seen)
    scrape_web(found, seen)
    # drop huge nested counts duplication for storage
    stored = []
    for item in found:
        row = dict(item)
        row["counts"] = item.get("counts") or {}
        stored.append(row)
    uadb.save_json("data/community-decks.json", stored)
    uadb.log("community lists", len(stored))


if __name__ == "__main__":
    main()
