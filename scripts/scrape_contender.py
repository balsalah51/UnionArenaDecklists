#!/usr/bin/env python3
"""Pull Union Arena meta decks from TCG Contender (not Limitless / not OPTCG)."""

from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import uadb

GAME = "unionarena"
FORMAT = "standard"


def fetch_format_decks() -> dict:
    url = f"https://tcgcontender.com/api/v2/format-deck-data/{GAME}/{FORMAT}"
    obj = uadb.http_json(url)
    data = obj.get("data") or obj
    uadb.save_json("data/contender-format.json", data)
    details = data.get("deckDetails") or {}
    uadb.log("contender archetypes", len(details))
    return data


def fetch_overview() -> dict:
    url = f"https://tcgcontender.com/api/v2/game-initial/{GAME}"
    obj = uadb.http_json(url)
    data = obj.get("data") or obj
    uadb.save_json("data/contender-overview.json", data)
    ov = data.get("defaultOverview") or {}
    uadb.log("contender overview decks", len(ov.get("decks") or []))
    return data


def fetch_card_page(page: int) -> list[dict]:
    url = f"https://tcgcontender.com/api/cards/{GAME}/browse?page={page}"
    obj = uadb.http_json(url)
    data = obj.get("data") or {}
    return data.get("cards") or [], (data.get("pagination") or {})


def fetch_card_catalog(max_pages: int = 140) -> dict:
    cache = uadb.load_json("data/contender-cards.json", {})
    first_cards, pag = fetch_card_page(1)
    total_pages = min(int(pag.get("totalPages") or 1), max_pages)
    pages = {1: first_cards}

    def one(p: int):
        cards, _ = fetch_card_page(p)
        return p, cards

    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = [pool.submit(one, p) for p in range(2, total_pages + 1)]
        done = 1
        for fut in as_completed(futs):
            p, cards = fut.result()
            pages[p] = cards
            done += 1
            if done % 20 == 0:
                uadb.log("contender cards page", done, "/", total_pages)
            time.sleep(0.02)
    for p in sorted(pages):
        for card in pages[p]:
            cid = card.get("cardId") or ""
            if not cid:
                continue
            attrs = card.get("attributes") or {}
            cache[cid] = {
                "id": cid,
                "name": card.get("name") or cid,
                "category": card.get("cardType") or "Character",
                "color": attrs.get("color") or "",
                "cost": str(attrs.get("requiredEnergy")) if attrs.get("requiredEnergy") is not None else None,
                "ap": str(attrs.get("ap")) if attrs.get("ap") is not None else None,
                "bp": str(attrs.get("bp")) if attrs.get("bp") is not None else None,
                "trigger": attrs.get("trigger") or "",
                "types": attrs.get("affinity") or "",
                "title": attrs.get("sourceTitle") or "",
                "image": (
                    "https://tcgcontender.com" + card["imageUrl"]
                    if (card.get("imageUrl") or "").startswith("/")
                    else card.get("imageUrl") or uadb.official_image(cid)
                ),
                "source": f"https://tcgcontender.com/{GAME}/cards/{uadb.slugify(card.get('name') or cid)}",
            }
    uadb.log("contender card catalog", len(cache))
    uadb.save_json("data/contender-cards.json", cache)
    return cache


def merge_card_caches() -> dict:
    official = uadb.load_json("data/card-cache.json", {})
    contender = uadb.load_json("data/contender-cards.json", {})
    merged = dict(official)
    for cid, card in contender.items():
        if cid not in merged:
            merged[cid] = card
            continue
        for key, val in card.items():
            if val and not merged[cid].get(key):
                merged[cid][key] = val
        if not merged[cid].get("image"):
            merged[cid]["image"] = card.get("image")
    uadb.save_json("data/card-cache.json", merged)
    return merged


def main() -> None:
    fetch_overview()
    fetch_format_decks()
    fetch_card_catalog()
    merge_card_caches()


if __name__ == "__main__":
    main()
