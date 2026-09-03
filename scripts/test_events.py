#!/usr/bin/env python3
"""Tournament event scrape: page caps, filters, and known-id skip."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import scrape_events  # noqa: E402


class EventScrapeTests(unittest.TestCase):
    def test_limits_cover_the_full_contender_catalog(self):
        self.assertGreaterEqual(scrape_events.MAX_PAGES, 20)
        self.assertGreaterEqual(scrape_events.MAX_TOURNAMENTS, 360)
        self.assertGreaterEqual(scrape_events.MAX_LISTS, 2000)

    def test_pick_keeps_regionals_and_multi_list_locals(self):
        rows = [
            {"id": 1, "eventType": "local", "playerCount": 4, "decklistCount": 1},
            {"id": 2, "eventType": "regional", "playerCount": 4, "decklistCount": 2},
            {"id": 3, "eventType": "local", "playerCount": 8, "decklistCount": 3},
            {"id": 4, "eventType": "online", "playerCount": 4, "decklistCount": 5},
            {"id": 5, "eventType": "local", "playerCount": 16, "decklistCount": 0},
        ]
        picked = scrape_events.pick_tournaments(rows)
        self.assertEqual([r["id"] for r in picked], [2, 3, 4])
        recent = scrape_events.pick_tournaments(
            [
                {
                    "id": 9,
                    "eventType": "local",
                    "playerCount": 3,
                    "decklistCount": 1,
                    "date": "2026-08-29",
                }
            ]
        )
        self.assertEqual([r["id"] for r in recent], [9])

    def test_known_event_ids_from_slugs(self):
        found = [
            {"kind": "event", "slug": "event-1st-solo-leveling-sung-jinwoo-1471380", "cards": 44},
            {"kind": "event", "slug": "event-2nd-sakamoto-days-taro-sakamoto-1471411", "cards": 50},
            {"kind": "official", "slug": "official-1st-foo-abc123"},
            {"kind": "event", "slug": "event-3rd-missing-id"},
        ]
        self.assertEqual(scrape_events.known_event_ids(found), {1471380, 1471411})
        stored = scrape_events.known_event_lists(found)
        self.assertEqual(stored[1471380]["cards"], 44)
        self.assertTrue(scrape_events.should_refresh(stored[1471380], 50))
        self.assertFalse(scrape_events.should_refresh(stored[1471411], 50))
        self.assertTrue(scrape_events.should_refresh(None, 50))

    def test_counts_from_cards_ignore_non_main_zones(self):
        cards = [
            {"cardName": "UE17BT/SLG-1-022", "quantity": 4, "zone": "main"},
            {"cardName": "UE17BT/SLG-1-030", "quantity": 12, "zone": "deck"},
            {"cardName": "UE17BT/SLG-1-001", "quantity": 1, "zone": "ap"},
            {"cardName": "UE20BT/TSK-P-003", "quantity": 4, "zone": "main"},
        ]
        counts = scrape_events.counts_from_cards(cards)
        self.assertEqual(counts["UE17BT/SLG-1-022"], 4)
        self.assertEqual(counts["UE17BT/SLG-1-030"], 12)
        self.assertEqual(counts["UE20BT/TSK-P-003"], 4)
        self.assertNotIn("UE17BT/SLG-1-001", counts)


if __name__ == "__main__":
    unittest.main()
