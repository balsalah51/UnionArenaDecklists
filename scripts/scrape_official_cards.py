#!/usr/bin/env python3
"""Scrape the official Bandai Union Arena NA cardlist into data/card-cache.json."""

from __future__ import annotations

import html as htmlmod
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

import uadb

TITLES = [
    "BLEACH: Thousand-Year Blood War",
    "HUNTER X HUNTER",
    "JUJUTSU KAISEN",
    "CODE GEASS Lelouch of the Rebellion",
    "Demon Slayer: Kimetsu no Yaiba",
    "ONE PUNCH MAN",
    "Sword Art Online",
    "Black Clover",
    "FULLMETAL ALCHEMIST",
    "Attack on Titan",
    "Rurouni Kenshin",
    "Kaiju No. 8",
    "Yu Yu Hakusho: Ghost Files",
    "GODDESS OF VICTORY: NIKKE",
    "Evangelion: New Theatrical Edition",
    "SOLO LEVELING",
    "KAGURABACHI",
    "Tokyo Ghoul",
    "SAKAMOTO DAYS",
    "That Time I Got Reincarnated as a Slime",
    "The 100 Girlfriends Who Really, Really, Really, Really, REALLY Love You",
    "CHAINSAW MAN",
    "INUYASHA",
    "Re:ZERO -Starting Life in Another World-",
]

IMG_RE = re.compile(
    r'data-src="(/na/images/cardlist/card/([^"]+))"\s+alt="([^"]+)"',
    re.I,
)
ID_RE = re.compile(r"((?:UE|UA|ST|PR|UEX)[A-Z0-9]{0,8}/[A-Z]{2,4}-\d-\d{3}(?:_p\d+)?)")


def parse_list(body: str, title: str) -> dict[str, dict]:
    out = {}
    for path, file_stem, alt in IMG_RE.findall(body or ""):
        alt = htmlmod.unescape(alt)
        m = ID_RE.search(alt) or ID_RE.search(file_stem.replace("_", "/", 1))
        if not m:
            cid = file_stem.replace(".png", "").replace("_p", "/").replace("_", "/", 1)
            cid = cid.split("?")[0]
        else:
            cid = m.group(1)
        name = alt
        name = re.sub(re.escape(cid), "", name).strip(" -")
        if cid.endswith(("_p1", "_p2")):
            continue
        out[cid] = {
            "id": cid,
            "name": name or cid,
            "title": title,
            "image": "https://www.unionarena-tcg.com" + path.split("?")[0],
            "source": f"https://www.unionarena-tcg.com/na/cardlist/detail.php?card_no={cid}",
        }
    return out


def fetch_title(title: str) -> dict[str, dict]:
    data = urllib.parse.urlencode(
        {
            "freewords": "",
            "cardnameFlag": "",
            "selectTitle": title,
            "needEnergy_min": "",
            "needEnergy_max": "",
            "bp_min": "",
            "bp_max": "",
            "keyeffect": "",
            "attribute": "",
        }
    ).encode()
    status, body = uadb.fetch(
        "https://www.unionarena-tcg.com/na/cardlist/index.php?search=true",
        timeout=40,
        data=data,
    )
    cards = parse_list(body, title)
    uadb.log("official", title, status, "cards", len(cards))
    return cards


DETAIL_RE = {
    "name": re.compile(r'class="cardNameCol">\s*([^<]+)', re.S),
    "id": re.compile(r'class="cardNumData">([^<]+)', re.S),
    "rarity": re.compile(r'class="rareData">([^<]+)', re.S),
    # Bandai puts the type in class="cardDataCol categoryData", not class="categoryData".
    "type": re.compile(
        r'class="[^"]*categoryData"[^>]*>.*?class="cardDataContents">\s*([^<]+)',
        re.S,
    ),
    "bp": re.compile(
        r'class="[^"]*\bbpData\b".*?class="cardDataContents">\s*([^<]+)',
        re.S,
    ),
    "ap": re.compile(
        r'class="[^"]*\bapData\b".*?class="cardDataContents">\s*([^<]+)',
        re.S,
    ),
}
TITLE_RE = re.compile(
    r'class="cardDataTitleCol[^"]*"[^>]*>\s*<img[^>]*alt="([^"]+)"',
    re.S,
)


def _detail_text(blob: str) -> str:
    text = re.sub(r'<img[^>]*alt="([^"]*)"[^>]*>', r" [\1] ", blob or "", flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(htmlmod.unescape(text).split())


def enrich_one(cid: str) -> dict:
    url = f"https://www.unionarena-tcg.com/na/cardlist/detail_iframe.php?card_no={urllib.parse.quote(cid)}"
    status, body = uadb.fetch(url, timeout=20)
    if status != 200:
        return {}
    extra = {}
    for key, rx in DETAIL_RE.items():
        m = rx.search(body)
        if m:
            extra[key] = htmlmod.unescape(m.group(1)).strip()
    em = re.search(r'class="[^"]*effectData".*?class="cardDataContents">(.*?)</dd>', body, re.S)
    if em:
        extra["effect"] = _detail_text(em.group(1))
    tm = re.search(r'class="[^"]*triggerData".*?class="cardDataContents">(.*?)</dd>', body, re.S)
    if tm:
        extra["trigger"] = _detail_text(tm.group(1))
    title = TITLE_RE.search(body)
    if title:
        extra["title"] = htmlmod.unescape(title.group(1)).strip()
    cm = re.search(r'ico_character_energy_([a-z]+)(\d+)', body, re.I)
    if cm:
        extra["color"] = cm.group(1).title()
        extra["cost"] = cm.group(2)
    gm = re.search(r'ico_resource_energy_([a-z]+)', body, re.I)
    if gm:
        extra["generated"] = gm.group(1).title()
    if extra.get("type"):
        extra["category"] = extra["type"]
    return extra


def enrich(cache: dict, ids: set[str]) -> dict:
    missing = [cid for cid in sorted(ids) if cid in cache and not cache[cid].get("category")]
    uadb.log("enrich details", len(missing))
    if not missing:
        return cache
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(enrich_one, cid): cid for cid in missing}
        done = 0
        for fut in as_completed(futs):
            cid = futs[fut]
            extra = fut.result() or {}
            cache.setdefault(cid, {})
            cache[cid].update({k: v for k, v in extra.items() if v})
            done += 1
            if done % 40 == 0:
                uadb.log("  details", done, "/", len(missing))
    return cache


def needs_official_fetch(cid: str, meta: dict | None) -> bool:
    meta = meta or {}
    if not cid or "UNRESOLVED" in cid or "/" not in cid:
        return False
    if cid.endswith(("_p1", "_p2")) or "-AP" in cid.upper():
        return False
    name = str(meta.get("name") or "").strip()
    category = str(meta.get("category") or meta.get("type") or "").strip()
    if not name or name.upper() == cid.upper() or "/" in name:
        return True
    return not category


def fetch_missing(cache: dict, ids: list[str]) -> list[str]:
    """Fetch Bandai detail pages for list cards the cache cannot name or type.

    Returns card ids that are still unresolved after the fetch.
    """
    wanted = []
    seen: set[str] = set()
    for cid in ids:
        if cid in seen:
            continue
        seen.add(cid)
        if needs_official_fetch(cid, cache.get(cid)):
            wanted.append(cid)
    uadb.log("bandai detail fetch", len(wanted))
    if not wanted:
        return []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(enrich_one, cid): cid for cid in wanted}
        done = 0
        for fut in as_completed(futs):
            cid = futs[fut]
            try:
                extra = fut.result() or {}
            except Exception as exc:  # noqa: BLE001
                uadb.log("bandai detail error", cid, exc)
                extra = {}
            if extra.get("name"):
                row = cache.setdefault(cid, {"id": cid})
                row.update({k: v for k, v in extra.items() if v})
                row.setdefault("source", f"https://www.unionarena-tcg.com/na/cardlist/detail.php?card_no={cid}")
                if not row.get("image"):
                    row["image"] = uadb.official_image(cid)
                if row.get("type") and not row.get("category"):
                    row["category"] = row["type"]
            done += 1
            if done % 25 == 0 or done == len(wanted):
                uadb.log("  bandai details", done, "/", len(wanted))
    uadb.inherit_printings(cache)
    unresolved = [cid for cid in wanted if needs_official_fetch(cid, cache.get(cid))]
    for cid in unresolved:
        uadb.log("UNRESOLVED CARD", cid)
    return unresolved


def main(only_used: set[str] | None = None) -> dict:
    cache = uadb.load_json("data/card-cache.json", {})
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = [pool.submit(fetch_title, t) for t in TITLES]
        for fut in as_completed(futs):
            batch = fut.result()
            for cid, card in batch.items():
                cache.setdefault(cid, {}).update(card)
            time.sleep(0.05)
    uadb.log("official cache", len(cache))
    if only_used:
        cache = enrich(cache, only_used)
    uadb.save_json("data/card-cache.json", cache)
    return cache


if __name__ == "__main__":
    main()
