#!/usr/bin/env python3
"""Pull individual Union Arena tournament 50s from TCG Contender / ExBurst."""

from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

import uadb

GAME = "unionarena"
PAGE_SIZE = 20
MAX_PAGES = 40
MAX_TOURNAMENTS = 500
MAX_LISTS = 3000
MIN_PLAYERS = 6
RECENT_DAYS = 14
EVENT_ID_RE = re.compile(r"-(\d{6,})$")


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
    recent_cut = (date.today() - timedelta(days=RECENT_DAYS)).isoformat()
    picked = []
    for row in rows:
        if int(row.get("decklistCount") or 0) < 1:
            continue
        event = (row.get("eventType") or "").lower()
        players = int(row.get("playerCount") or 0)
        when = (row.get("date") or "")[:10]
        if (
            event == "regional"
            or players >= MIN_PLAYERS
            or int(row.get("decklistCount") or 0) >= 4
            or when >= recent_cut
        ):
            picked.append(row)
        if len(picked) >= MAX_TOURNAMENTS:
            break
    return picked


def fetch_json(url: str, attempts: int = 4) -> dict:
    for attempt in range(attempts):
        status, body = uadb.fetch(url, timeout=22, browser=True)
        if status == 200 and body.startswith("{"):
            try:
                return json.loads(body).get("data") or {}
            except json.JSONDecodeError:
                pass
        time.sleep(0.45 * (attempt + 1))
    return {}


def tournament_detail(tid: int) -> dict:
    return fetch_json(f"https://tcgcontender.com/api/tournaments/{GAME}/{tid}")


def fetch_decklist(tid: int, did: int) -> dict:
    return fetch_json(f"https://tcgcontender.com/api/tournaments/{GAME}/{tid}/decklists/{did}")


def known_event_ids(found: list[dict]) -> set[int]:
    return set(known_event_lists(found))


def known_event_lists(found: list[dict]) -> dict[int, dict]:
    """Map Contender decklist id to the stored community row."""
    out: dict[int, dict] = {}
    for row in found:
        if row.get("kind") != "event":
            continue
        m = EVENT_ID_RE.search(row.get("slug") or "")
        if m:
            out[int(m.group(1))] = row
    return out


def stored_card_count(row: dict | None) -> int:
    if not row:
        return 0
    return int(row.get("cards") or sum((row.get("counts") or {}).values()) or 0)


def should_refresh(stored: dict | None, live_cards: int) -> bool:
    have = stored_card_count(stored)
    if stored is None:
        return True
    if have < 50:
        return True
    return bool(live_cards) and have < live_cards


def player_from_name(deck_name: str) -> str:
    m = re.search(r"\(([^@)]+?)\s*@", deck_name or "")
    if m:
        return m.group(1).strip()
    return ""


def scrape_events(found: list[dict], seen: set[str], cache: dict, arches: list[dict]) -> None:
    from scrape_community import guess_key, item_from_counts, key_from_counts, record

    tours = pick_tournaments(tournament_pages())
    have = known_event_lists(found)
    uadb.log("events picked", len(tours), "already stored", len(have))
    added = 0
    skipped = 0
    refreshed = 0
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
            did = int(did)
            stored = have.get(did)
            if not should_refresh(stored, cards):
                skipped += 1
                continue
            jobs.append((did, row, stored))
        if not jobs:
            continue

        def one(job):
            did, row, stored = job
            time.sleep(0.04)
            payload = fetch_decklist(tid, did)
            return did, row, stored, payload

        with ThreadPoolExecutor(max_workers=4) as pool:
            futs = [pool.submit(one, job) for job in jobs]
            for fut in as_completed(futs):
                if added >= MAX_LISTS:
                    break
                did, row, stored, payload = fut.result()
                cards = (payload.get("cards") or []) if payload else []
                counts = counts_from_cards(cards)
                if not uadb.list_is_complete(counts):
                    continue
                if stored and sum(counts.values()) <= stored_card_count(stored):
                    skipped += 1
                    continue
                archetype = row.get("archetype") or (payload.get("decklist") or {}).get("archetype") or ""
                key = (stored or {}).get("key") or ""
                if not key and archetype.count(" - ") == 1 and len(archetype) <= 72:
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
                player = player_from_name(row.get("deckName") or "") or (stored or {}).get("player") or place
                slug = (stored or {}).get("slug") or uadb.slugify(f"event-{place}-{key}-{did}")
                item = item_from_counts(
                    counts,
                    key=key,
                    kind="event",
                    player=player,
                    title=archetype or (stored or {}).get("title") or place,
                    subtitle=f"{place} · {event}",
                    source_url=source,
                    slug=slug,
                    date=date or (stored or {}).get("date") or "",
                )
                item["archetype"] = archetype or (stored or {}).get("archetype") or item.get("archetype")
                if record(found, item, seen):
                    have[did] = item
                    if stored:
                        refreshed += 1
                    else:
                        added += 1
        time.sleep(0.06)
    uadb.log("events lists added", added, "refreshed", refreshed, "already stored skipped", skipped)
