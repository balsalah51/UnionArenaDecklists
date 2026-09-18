#!/usr/bin/env python3
"""Pull finished English Union Arena tournament 50s from ExBurst.

Reads published Finished uaen events and the registration deckLinks those
events already attached. Catalog web lists stay kind=web. Does not invent
results and does not read Asia gameid=ua cups.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

import scrape_exburst
import uadb

GAME_ID = "uaen"
TOURNAMENT_TABLE = "tournaments"
REGISTRATION_TABLE = "tournament_registrations"
DECK_TABLE = scrape_exburst.GAME_TABLE
PAGE_SIZE = 100
MAX_TOURNAMENTS = 250
MAX_LISTS = 600
MIN_PLAYERS = 4
RECENT_DAYS = 21
DATE_FROM = ""
DATE_TO = ""
SKIP_SLUGS = {
    "reddit-pic-does-anyone-know-the-most-optimal-purple-sao-song-deck-1qls",
}
SKIP_NAME_RE = re.compile(r"(live test cup|playwright)|^(test|testing)$", re.I)
DECK_URL_RE = re.compile(r"exburst\.dev/ua/en/decklists/(\d+)")
SLUG_ID_RE = re.compile(r"(?:^|-)(?:exburst|tournament)(?:-.+)?-(\d{4,})$")
TOUR_SELECT = "id,name,startDate,maxPlayers,location,organizer,gameFormat,status,hasBeenPublished,gameid"
REG_SELECT = (
    "id,tournamentId,deckLink,placement,deckName,deckSeries,deckArchetypes,"
    "name,realPlayerName,status,gameId"
)
DECK_SELECT = "id,decklist_name,modified_date,archetype,decklist_content"


def skip_test_event(row: dict) -> bool:
    name = (row.get("name") or "").strip()
    return bool(SKIP_NAME_RE.search(name))


def keep_tournament(row: dict, regs: list[dict] | None = None, today: date | None = None) -> bool:
    if skip_test_event(row):
        return False
    if (row.get("gameid") or "") != GAME_ID:
        return False
    if not row.get("hasBeenPublished"):
        return False
    if (row.get("status") or "") != "Finished":
        return False
    players = max(int(row.get("maxPlayers") or 0), len(regs or []))
    when = (row.get("startDate") or "")[:10]
    if DATE_FROM or DATE_TO:
        if DATE_FROM and (not when or when < DATE_FROM):
            return False
        if DATE_TO and (not when or when >= DATE_TO):
            return False
        return True
    recent_cut = ((today or date.today()) - timedelta(days=RECENT_DAYS)).isoformat()
    return players >= MIN_PLAYERS or (bool(when) and when >= recent_cut)


def place_label(n) -> str:
    ordinal = uadb.ordinal(n)
    return f"{ordinal} Place" if ordinal else ""


def tournament_slug(place: str, arch_key: str, did: int) -> str:
    ordinal = (place or "event").replace(" Place", "").strip() or "event"
    suffix = f"-{did}"
    base = uadb.slugify(f"tournament-{ordinal}-{arch_key}")[: 70 - len(suffix)]
    return f"{base}{suffix}"


def slug_has_deck_id(slug: str, did: int = 0) -> bool:
    if did:
        return (slug or "").endswith(f"-{did}")
    return bool(re.search(r"-\d{6,}$", slug or ""))


def deck_id_of(link) -> int:
    raw = str(link or "").strip()
    if raw.isdigit():
        return int(raw)
    m = DECK_URL_RE.search(raw)
    return int(m.group(1)) if m else 0


def exburst_deck_id(row: dict) -> int:
    src = row.get("source_url") or ""
    m = DECK_URL_RE.search(src)
    if m:
        return int(m.group(1))
    slug = row.get("slug") or ""
    m = SLUG_ID_RE.search(slug)
    if m:
        return int(m.group(1))
    return 0


def known_exburst_decks(found: list[dict]) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for row in found:
        did = exburst_deck_id(row)
        if did:
            out[did] = row
    return out


def stored_card_count(row: dict | None) -> int:
    if not row:
        return 0
    return int(row.get("cards") or sum((row.get("counts") or {}).values()) or 0)


def should_refresh(stored: dict | None, live_cards: int = 0) -> bool:
    have = stored_card_count(stored)
    if stored is None:
        return True
    if (stored.get("kind") or "") != "tournament":
        return True
    if not slug_has_deck_id(stored.get("slug") or "", exburst_deck_id(stored)):
        return True
    if have < uadb.MIN_CARDS:
        return True
    return bool(live_cards) and have < live_cards


def chunked(values: list, size: int) -> list[list]:
    return [values[i : i + size] for i in range(0, len(values), size)]


def fetch_finished_tournaments(key: str, cap: int = MAX_TOURNAMENTS) -> list[dict]:
    query = (
        f"gameid=eq.{GAME_ID}&hasBeenPublished=eq.true&status=eq.Finished"
        f"&select={TOUR_SELECT}&order=startDate.desc"
    )
    out: list[dict] = []
    offset = 0
    while len(out) < cap:
        rows = scrape_exburst.rest_range(key, TOURNAMENT_TABLE, query, offset, PAGE_SIZE)
        if not rows:
            break
        for row in rows:
            if keep_tournament(row):
                out.append(row)
            if len(out) >= cap:
                break
        uadb.log("exburst events page", offset // PAGE_SIZE + 1, "rows", len(rows), "kept", len(out))
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return out


def fetch_registrations(key: str, tournament_ids: list[int]) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {tid: [] for tid in tournament_ids}
    if not tournament_ids:
        return out
    for group in chunked(tournament_ids, 40):
        ids = ",".join(str(tid) for tid in group)
        query = (
            f"gameId=eq.{GAME_ID}&tournamentId=in.({ids})&deckLink=neq."
            f"&placement=not.is.null&select={REG_SELECT}&order=placement.asc"
        )
        offset = 0
        while True:
            rows = scrape_exburst.rest_range(key, REGISTRATION_TABLE, query, offset, PAGE_SIZE)
            for row in rows:
                if (row.get("gameId") or "") != GAME_ID:
                    continue
                tid = int(row.get("tournamentId") or 0)
                if tid in out:
                    out[tid].append(row)
            if len(rows) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
    return out


def fetch_decks(key: str, deck_ids: list[int]) -> dict[int, dict]:
    out: dict[int, dict] = {}
    if not deck_ids:
        return out
    for group in chunked(deck_ids, 40):
        ids = ",".join(str(did) for did in group)
        query = f"id=in.({ids})&select={DECK_SELECT}"
        rows = scrape_exburst.rest_range(key, DECK_TABLE, query, 0, max(len(group), 1))
        for row in rows:
            did = int(row.get("id") or 0)
            if did:
                out[did] = row
    return out


def item_title(row: dict, place: str) -> str:
    name = (row.get("deckName") or "").strip()
    return name[:90] if name else place or "Tournament list"


def item_player(row: dict, place: str) -> str:
    name = (row.get("realPlayerName") or row.get("name") or "").strip()
    return (name or place or "ExBurst")[:40]


def series_blob(row: dict, event: str) -> str:
    from scrape_community import SET_PREFIX

    series = (row.get("deckSeries") or "").upper()
    title = SET_PREFIX.get(series, series.lower())
    return " ".join(
        bit
        for bit in (
            row.get("deckName") or "",
            row.get("deckArchetypes") or "",
            title,
            event,
        )
        if bit
    )


def upsert_tournament(found: list[dict], seen: set[str], have: dict[int, dict], item: dict, deck_id: int) -> bool:
    from scrape_community import record

    old = have.get(deck_id)
    if old:
        item["slug"] = (old.get("slug") or item.get("slug") or "")[:70]
        ident = item.get("slug") or item.get("raw") or ""
        for i, row in enumerate(found):
            if row is old or (row.get("slug") and row.get("slug") == old.get("slug")):
                found[i] = item
                if ident:
                    seen.add(ident)
                have[deck_id] = item
                uadb.log("upgraded", "tournament", item.get("key"), ident, "cards", item.get("cards"))
                return True
    if record(found, item, seen):
        have[deck_id] = item
        return True
    return False


def scrape_exburst_events(
    found: list[dict],
    seen: set[str],
    cache: dict,
    arches: list[dict],
    limit: int | None = None,
) -> int:
    from scrape_community import guess_key, item_from_counts, key_from_counts

    cap = MAX_LISTS if limit is None else limit
    if cap < 1:
        return 0
    key = scrape_exburst.discover_anon_key()
    # Keep stored tournament rows even when the slug ends short of six
    # digits. Dropping those here deleted hosted 50s on the next scrape.
    tours = fetch_finished_tournaments(key)
    regs_by_tour = fetch_registrations(key, [int(t.get("id") or 0) for t in tours if t.get("id")])
    have = known_exburst_decks(found)
    wanted: list[tuple[dict, dict, int]] = []
    for tour in tours:
        tid = int(tour.get("id") or 0)
        regs = [row for row in regs_by_tour.get(tid, []) if deck_id_of(row.get("deckLink"))]
        if not keep_tournament(tour, regs):
            continue
        for row in regs:
            did = deck_id_of(row.get("deckLink"))
            stored = have.get(did)
            if not should_refresh(stored):
                continue
            wanted.append((tour, row, did))
            if len(wanted) >= cap * 2:
                break
        if len(wanted) >= cap * 2:
            break
    decks = fetch_decks(key, list(dict.fromkeys(did for _t, _r, did in wanted)))
    added = 0
    skipped = 0
    refreshed = 0
    for tour, row, did in wanted:
        if added >= cap:
            break
        payload = decks.get(did) or {}
        text = payload.get("decklist_content") or ""
        counts = uadb.parse_counts(text)
        if not uadb.list_is_complete(counts) or not scrape_exburst.english_enough(counts):
            skipped += 1
            continue
        stored = have.get(did)
        if stored and (stored.get("kind") or "") == "tournament" and sum(counts.values()) <= stored_card_count(stored):
            skipped += 1
            continue
        event = (tour.get("name") or "").strip() or "Tournament"
        place = place_label(row.get("placement"))
        blob = series_blob(row, event)
        series = (row.get("deckSeries") or "").upper()
        arch_key = guess_key(blob, counts, cache, arches, set_hint=series)
        if not arch_key:
            arch_key = key_from_counts(counts, cache, set_hint=series)
        if not arch_key:
            skipped += 1
            continue
        slug = tournament_slug(place, arch_key, did)
        if slug in SKIP_SLUGS or (stored or {}).get("slug") in SKIP_SLUGS:
            continue
        when = (tour.get("startDate") or payload.get("modified_date") or "")[:10]
        item = item_from_counts(
            counts,
            key=arch_key,
            kind="tournament",
            player=item_player(row, place),
            title=item_title(row, place),
            subtitle=f"{place} · {event}" if place else event,
            source_url=f"https://exburst.dev/ua/en/tournaments/{tour.get('id')}",
            slug=(stored or {}).get("slug") or slug,
            date=when,
        )
        if upsert_tournament(found, seen, have, item, did):
            if stored and (stored.get("kind") or "") == "tournament":
                refreshed += 1
            else:
                added += 1
        else:
            skipped += 1
    uadb.log("exburst events lists added", added, "refreshed", refreshed, "skipped", skipped)
    return added


def main() -> None:
    from scrape_community import archetypes, collapse_by_slug, seed_existing

    cache = uadb.load_json("data/card-cache.json", {})
    extra = uadb.load_json("data/contender-cards.json", {})
    for cid, card in extra.items():
        cache.setdefault(cid, {}).update({k: v for k, v in card.items() if v})
    found: list[dict] = []
    seen: set[str] = set()
    seed_existing(found, seen)
    scrape_exburst_events(found, seen, cache, archetypes())
    stored = collapse_by_slug(found)
    for item in stored:
        item["counts"] = item.get("counts") or {}
    uadb.save_json("data/community-decks.json", stored)
    uadb.log("community lists", len(stored))


if __name__ == "__main__":
    main()
