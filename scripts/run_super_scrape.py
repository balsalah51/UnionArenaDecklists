#!/usr/bin/env python3
"""Wide refresh of public English 50s since the last hosted scrape."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
os.chdir(ROOT)

import scrape_community
import scrape_contender
import scrape_events
import scrape_exburst
import scrape_exburst_events
import uadb

# Last hosted fill closed 2026-09-19. Re-read that day for same-day leftovers.
SINCE = "2026-09-19"
TARGET_NEW = 2000
SKIP_SLUGS = {
    "reddit-pic-does-anyone-know-the-most-optimal-purple-sao-song-deck-1qls",
}


def persist(found: list[dict]) -> list[dict]:
    stored = scrape_community.collapse_by_slug(found)
    stored = [row for row in stored if (row.get("slug") or "") not in SKIP_SLUGS]
    for item in stored:
        item["counts"] = item.get("counts") or {}
    uadb.save_json("data/community-decks.json", stored)
    uadb.log("saved community lists", len(stored))
    return stored


def cache_and_arches() -> tuple[dict, list[dict]]:
    cache = uadb.load_json("data/card-cache.json", {})
    extra = uadb.load_json("data/contender-cards.json", {})
    for cid, card in extra.items():
        cache.setdefault(cid, {}).update({k: v for k, v in card.items() if v})
    return cache, scrape_community.archetypes()


def widen_events() -> None:
    scrape_events.MIN_PLAYERS = 1
    scrape_events.RECENT_DAYS = 45
    scrape_events.MAX_PAGES = 60
    scrape_events.MAX_TOURNAMENTS = 800
    scrape_events.MAX_LISTS = TARGET_NEW
    scrape_events.DATE_FROM = SINCE
    scrape_exburst_events.MIN_PLAYERS = 1
    scrape_exburst_events.RECENT_DAYS = 45
    scrape_exburst_events.MAX_TOURNAMENTS = 400
    scrape_exburst_events.MAX_LISTS = TARGET_NEW
    scrape_exburst_events.DATE_FROM = SINCE
    scrape_exburst.MAX_LISTS = TARGET_NEW
    scrape_exburst.MAX_PAGES = 220
    scrape_exburst.DATE_FROM = SINCE


def main() -> None:
    print("=== TCG Contender meta ===")
    scrape_contender.fetch_overview()
    scrape_contender.fetch_format_decks()
    scrape_contender.merge_card_caches()

    cache, arches = cache_and_arches()
    found: list[dict] = []
    seen: set[str] = set()
    scrape_community.seed_existing(found, seen)
    start_slugs = {row.get("slug") for row in found if row.get("slug")}
    start_n = len(found)
    uadb.log("start lists", start_n)

    print("=== official, blogs, reddit ===")
    scrape_community.scrape_official(found, seen, cache, arches)
    more = scrape_community.discover_blog_pages()
    for url in more:
        if url not in scrape_community.WEB_PAGES:
            scrape_community.WEB_PAGES.append(url)
    scrape_community.scrape_web_pages(found, seen, cache, arches)
    scrape_community.scrape_reddit(found, seen, cache, arches)
    persist(found)

    print("=== Contender events ===")
    widen_events()
    scrape_events.scrape_events(found, seen, cache, arches)
    persist(found)

    print("=== ExBurst tournaments ===")
    scrape_exburst_events.scrape_exburst_events(found, seen, cache, arches, limit=TARGET_NEW)
    persist(found)

    new_now = len({row.get("slug") for row in found if row.get("slug")} - start_slugs)
    remain = max(0, TARGET_NEW - new_now)
    uadb.log("new after events", new_now, "catalog remain", remain)
    print("=== ExBurst catalog ===")
    if remain:
        scrape_exburst.scrape_exburst(found, seen, cache, arches, limit=remain)
        persist(found)

    if "--skip-youtube" not in sys.argv:
        print("=== YouTube text lists ===")
        scrape_community.scrape_youtube(found, seen, cache, arches)
        persist(found)

    stored = persist(found)
    new_slugs = {row.get("slug") for row in stored if row.get("slug")} - start_slugs
    uadb.log("done total", len(stored), "new", len(new_slugs))
    print(f"START={start_n} TOTAL={len(stored)} NEW={len(new_slugs)}")


if __name__ == "__main__":
    main()
