#!/usr/bin/env python3
"""Pull individual Union Arena tournament 50s from TCG Contender / ExBurst."""

from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import uadb

GAME = "unionarena"
PAGE_SIZE = 20
MAX_PAGES = 12
MAX_TOURNAMENTS = 120
MAX_LISTS = 800
MIN_PLAYERS = 6


def counts_from_cards(cards: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for card in cards or []:
        if (card.get("zone") or "main").lower() not in {"main", "deck", ""}:
            continue
        cid = uadb.normalize_cid(card.get("cardName") or card.get("cardId") or "")
        n = int(card.get("quantity") or 0)
        if not cid or n < 1:
            continue
        counts[cid] = min(uadb.max_copies(cid, cap_restricted=False), counts.get(cid, 0) + n)
    return counts


def tournament_pages() -> list[dict]:
    out = []
    for page in range(1, MAX_PAGES + 1):
        url = f"https://tcgcontender.com/api/tournaments/{GAME}?page={page}"
        status, body = uadb.fetch(url, timeout=22, browser=True)
        if status != 200 or not body.startswith("{"):
            uadb.log("events page fail", page, status)
            break
        data = json.loads(body).get("data") or {}
        rows = data.get("tournaments") or []
        out.extend(rows)
        pag = data.get("pagination") or {}
        uadb.log("events page", page, "rows", len(rows), "total", pag.get("totalCount"))
        if page >= int(pag.get("totalPages") or page) or len(rows) < PAGE_SIZE:
            break
        time.sleep(0.08)
    return out


def pick_tournaments(rows: list[dict]) -> list[dict]:
    picked = []
    for row in rows:
        if int(row.get("decklistCount") or 0) < 1:
            continue
        event = (row.get("eventType") or "").lower()
        players = int(row.get("playerCount") or 0)
        if event == "regional" or players >= MIN_PLAYERS or int(row.get("decklistCount") or 0) >= 4:
            picked.append(row)
        if len(picked) >= MAX_TOURNAMENTS:
            break
    return picked


def tournament_detail(tid: int) -> dict:
    status, body = uadb.fetch(f"https://tcgcontender.com/api/tournaments/{GAME}/{tid}", timeout=22, browser=True)
    if status != 200 or not body.startswith("{"):
        return {}
    return json.loads(body).get("data") or {}


def fetch_decklist(tid: int, did: int) -> dict:
    status, body = uadb.fetch(
        f"https://tcgcontender.com/api/tournaments/{GAME}/{tid}/decklists/{did}",
        timeout=20,
        browser=True,
    )
    if status != 200 or not body.startswith("{"):
        return {}
    return json.loads(body).get("data") or {}


def player_from_name(deck_name: str) -> str:
    m = re.search(r"\(([^@)]+?)\s*@", deck_name or "")
    if m:
        return m.group(1).strip()
    return ""


def scrape_events(found: list[dict], seen: set[str], cache: dict, arches: list[dict]) -> None:
    from scrape_community import guess_key, item_from_counts, key_from_counts, record

    tours = pick_tournaments(tournament_pages())
    uadb.log("events picked", len(tours))
    added = 0
    for tour in tours:
        if added >= MAX_LISTS:
            break
        tid = int(tour.get("id") or 0)
        if not tid:
            continue
        detail = tournament_detail(tid)
        event = (detail.get("tournament") or tour).get("name") or "Tournament"
        date = ((detail.get("tournament") or tour).get("date") or "")[:10]
        source = (detail.get("tournament") or tour).get("sourceUrl") or (
            f"https://tcgcontender.com/unionarena/tournaments/{tour.get('slug')}/decks"
        )
        standings = detail.get("standings") or []
        jobs = []
        for row in standings:
            did = row.get("decklistId")
            cards = int(row.get("totalCards") or 0)
            if not did or cards and cards < uadb.MIN_CARDS:
                continue
            jobs.append((int(did), row))
        if not jobs:
            continue

        def one(pair):
            did, row = pair
            time.sleep(0.04)
            payload = fetch_decklist(tid, did)
            return did, row, payload

        with ThreadPoolExecutor(max_workers=4) as pool:
            futs = [pool.submit(one, job) for job in jobs]
            for fut in as_completed(futs):
                if added >= MAX_LISTS:
                    break
                did, row, payload = fut.result()
                cards = (payload.get("cards") or []) if payload else []
                counts = counts_from_cards(cards)
                if not uadb.list_is_complete(counts):
                    continue
                archetype = row.get("archetype") or (payload.get("decklist") or {}).get("archetype") or ""
                key = ""
                if archetype.count(" - ") == 1 and len(archetype) <= 72:
                    title, name = [part.strip() for part in archetype.split(" - ", 1)]
                    if title and name and name.lower() not in {"purple", "red", "yellow", "green", "blue", "black"}:
                        key = uadb.slugify(archetype)
                if not key:
                    key = guess_key(archetype + " " + event, counts, cache, arches)
                if not key:
                    key = key_from_counts(counts, cache)
                if not key:
                    continue
                place = uadb.ordinal(row.get("placement")) or "Event"
                player = player_from_name(row.get("deckName") or "")
                slug = uadb.slugify(f"event-{place}-{key}-{did}")
                item = item_from_counts(
                    counts,
                    key=key,
                    kind="event",
                    player=player or place,
                    title=archetype or place,
                    subtitle=f"{place} · {event}",
                    source_url=source,
                    slug=slug,
                    date=date,
                )
                item["archetype"] = archetype
                if record(found, item, seen):
                    added += 1
        time.sleep(0.06)
    uadb.log("events lists added", added)
