#!/usr/bin/env python3
"""Pull the official English card list for BLEACH Vol. 3 into data/spoilers-uex08bt.json.

The NA product page numbers this set UEX08BT/BLC-4. The public English card
database still files the same collector numbers under the Japanese set code
EX15BT. Pictures and rules text come from that official list. Alt-art files
(_p1, _p2) stay attached to the base number.
"""

from __future__ import annotations

import html as htmlmod
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

import uadb

SERIES_URL = "https://www.unionarena-tcg.com/en/cardlist/?search=true&series=589215"
DETAIL_URL = "https://www.unionarena-tcg.com/en/cardlist/detail_iframe.php?card_no={cid}"
OUT = "data/spoilers-uex08bt.json"
EN_CODE = "UEX08BT"
JP_CODE = "EX15BT"
IMG_RE = re.compile(
    r'data-src="(/en/images/cardlist/card/([^"?]+))(?:\?[^"]*)?"\s+alt="([^"]+)"',
    re.I,
)
ALT_RE = re.compile(r"^(EX15BT/(BLC-4-[A-Z0-9-]+))(?:_p\d+)?\s+(.+)$", re.I)
DETAIL_RE = {
    "rarity": re.compile(r'class="rareData">([^<]+)', re.S),
    "category": re.compile(r'categoryData".*?class="cardDataContents">\s*([^<]+)', re.S),
    "bp": re.compile(r'bpData".*?class="cardDataContents">\s*([^<]+)', re.S),
    "ap": re.compile(r'apData".*?class="cardDataContents">\s*([^<]+)', re.S),
}


def english_id(jp_id: str) -> str:
    return jp_id.replace(JP_CODE + "/", EN_CODE + "/", 1)


def image_url(path: str) -> str:
    return "https://www.unionarena-tcg.com" + path.split("?")[0]


def parse_gallery(body: str) -> dict[str, dict]:
    cards: dict[str, dict] = {}
    for path, _file, alt in IMG_RE.findall(body or ""):
        alt = htmlmod.unescape(alt).strip()
        m = ALT_RE.match(alt)
        if not m:
            continue
        jp_id, _num, name = m.group(1), m.group(2), m.group(3).strip()
        base = jp_id.split("_p")[0]
        row = cards.setdefault(
            base,
            {
                "id": english_id(base),
                "jp_id": base,
                "name": name,
                "image": "",
                "alts": [],
            },
        )
        url = image_url(path)
        if "_p" in path:
            if url not in row["alts"]:
                row["alts"].append(url)
        else:
            row["image"] = url
            row["name"] = name or row["name"]
    for row in cards.values():
        if not row["image"] and row["alts"]:
            row["image"] = row["alts"].pop(0)
    return cards


def plain(fragment: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", fragment, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(htmlmod.unescape(text).split())


def fetch_detail(jp_id: str) -> dict:
    url = DETAIL_URL.format(cid=urllib.parse.quote(jp_id))
    status, body = uadb.fetch(url, timeout=25)
    if status != 200 or "cardNumData" not in body:
        return {}
    extra: dict[str, str] = {}
    for key, rx in DETAIL_RE.items():
        m = rx.search(body)
        if m:
            extra[key] = htmlmod.unescape(m.group(1)).strip()
    em = re.search(r'effectData".*?class="cardDataContents">(.*?)</dd>', body, re.S)
    if em:
        extra["effect"] = plain(em.group(1))
    tm = re.search(r'triggerData".*?class="cardDataContents">(.*?)</dd>', body, re.S)
    if tm:
        extra["trigger"] = plain(tm.group(1))
    cm = re.search(r"ico_character_energy_([a-z]+)(\d+)", body, re.I)
    if cm:
        extra["color"] = cm.group(1).title()
        extra["cost"] = cm.group(2)
    elif re.search(r"ico_event_energy_([a-z]+)", body, re.I):
        extra["color"] = re.search(r"ico_event_energy_([a-z]+)", body, re.I).group(1).title()
    gm = re.search(r"ico_resource_energy_([a-z]+)", body, re.I)
    if gm and not extra.get("color"):
        extra["color"] = gm.group(1).title()
    return extra


def main() -> dict:
    status, body = uadb.fetch(SERIES_URL, timeout=40)
    if status != 200:
        raise SystemExit(f"spoiler list {status}")
    cards = parse_gallery(body)
    uadb.log("spoiler gallery", len(cards))
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(fetch_detail, jp): jp for jp in cards}
        done = 0
        for fut in as_completed(futs):
            jp = futs[fut]
            cards[jp].update({k: v for k, v in (fut.result() or {}).items() if v})
            if not cards[jp].get("category") and "-AP" in jp:
                cards[jp]["category"] = "AP"
            done += 1
            if done % 20 == 0:
                uadb.log("spoiler details", done, "/", len(cards))
    ordered = sorted(cards.values(), key=lambda row: row["id"])
    payload = {
        "code": EN_CODE,
        "jp_code": JP_CODE,
        "name": "BLEACH: Thousand-Year Blood War Vol. 3",
        "short": "BLEACH Vol. 3",
        "title": "BLEACH",
        "series_href": "/series/bleach.html",
        "page": "spoilers/bleach-vol-3.html",
        "release": "2026-11-13",
        "prerelease": "2026-11-06",
        "source": SERIES_URL,
        "product": "https://www.unionarena-tcg.com/na/products/boosters/ex_blc-3.php",
        "cards": ordered,
    }
    uadb.save_json(OUT, payload)
    uadb.log("wrote", OUT, "cards", len(ordered))
    return payload


if __name__ == "__main__":
    main()
