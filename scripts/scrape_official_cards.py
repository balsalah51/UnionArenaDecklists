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
    "type": re.compile(r'class="categoryData".*?class="cardDataContents">([^<]+)', re.S),
    "bp": re.compile(r'class="bpData".*?class="cardDataContents">([^<]+)', re.S),
    "ap": re.compile(r'class="apData".*?class="cardDataContents">([^<]+)', re.S),
}


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
    em = re.search(r'class="effectData".*?class="cardDataContents">(.*?)</dd>', body, re.S)
    if em:
        text = re.sub(r"<[^>]+>", " ", em.group(1))
        extra["effect"] = " ".join(htmlmod.unescape(text).split())
    tm = re.search(r'class="triggerData".*?class="cardDataContents">(.*?)</dd>', body, re.S)
    if tm:
        text = re.sub(r"<[^>]+>", " ", tm.group(1))
        extra["trigger"] = " ".join(htmlmod.unescape(text).split())
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
