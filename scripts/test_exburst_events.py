#!/usr/bin/env python3
"""ExBurst tournament puller: English finished events only, real placements."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import scrape_community  # noqa: E402
import scrape_exburst  # noqa: E402
import scrape_exburst_events  # noqa: E402
import write_guides  # noqa: E402


class ExburstEventScrapeTests(unittest.TestCase):
    def test_reads_english_finished_events_only(self):
        self.assertEqual(scrape_exburst_events.GAME_ID, "uaen")
        self.assertEqual(scrape_exburst_events.TOURNAMENT_TABLE, "tournaments")
        self.assertEqual(scrape_exburst_events.REGISTRATION_TABLE, "tournament_registrations")
        self.assertEqual(scrape_exburst_events.DECK_TABLE, "uaen_decklists")
        self.assertEqual(scrape_exburst_events.DECK_TABLE, scrape_exburst.GAME_TABLE)
        self.assertGreaterEqual(scrape_exburst_events.MAX_TOURNAMENTS, 200)
        self.assertGreaterEqual(scrape_exburst_events.MAX_LISTS, 300)
        self.assertGreaterEqual(scrape_exburst_events.MIN_PLAYERS, 4)

    def test_skips_drafts_test_cups_and_asia(self):
        self.assertTrue(scrape_exburst_events.skip_test_event({"name": "Playwright Live test cup"}))
        self.assertTrue(scrape_exburst_events.skip_test_event({"name": "test"}))
        self.assertFalse(scrape_exburst_events.skip_test_event({"name": 'UA Weekly "Locals" 28'}))
        draft = {
            "gameid": "uaen",
            "hasBeenPublished": False,
            "status": "Result-Draft",
            "name": "Carta Magica Montreal",
            "maxPlayers": 16,
        }
        self.assertFalse(scrape_exburst_events.keep_tournament(draft))
        asia = {
            "gameid": "ua",
            "hasBeenPublished": True,
            "status": "Finished",
            "name": "Asia cup",
            "maxPlayers": 16,
        }
        self.assertFalse(scrape_exburst_events.keep_tournament(asia))
        live = {
            "gameid": "uaen",
            "hasBeenPublished": True,
            "status": "Finished",
            "name": 'UA Weekly "Locals" 28',
            "maxPlayers": 12,
            "startDate": "2026-09-10T20:30:00+00:00",
        }
        self.assertTrue(scrape_exburst_events.keep_tournament(live))

    def test_keeps_recent_small_locals(self):
        from datetime import date

        small = {
            "gameid": "uaen",
            "hasBeenPublished": True,
            "status": "Finished",
            "name": "Re:Zero launch locals",
            "maxPlayers": 2,
            "startDate": "2026-09-10T20:30:00+00:00",
        }
        self.assertTrue(scrape_exburst_events.keep_tournament(small, today=date(2026, 9, 11)))
        old = dict(small, startDate="2026-01-01T00:00:00+00:00")
        self.assertFalse(scrape_exburst_events.keep_tournament(old, today=date(2026, 9, 11)))

    def test_place_label_feeds_result_ranking(self):
        self.assertEqual(scrape_exburst_events.place_label(1), "1st Place")
        self.assertEqual(scrape_exburst_events.place_label(2), "2nd Place")
        self.assertEqual(scrape_exburst_events.place_label(3), "3rd Place")
        self.assertEqual(scrape_exburst_events.place_label(8), "8th Place")
        self.assertEqual(scrape_exburst_events.place_label(None), "")
        item = scrape_community.item_from_counts(
            {"UE22BT/CSM-1-008": 4, "UE22BT/CSM-1-017": 46},
            key="csm-denji",
            kind="tournament",
            player="danwall100",
            title="Denji",
            subtitle="1st Place · UA Weekly Locals 28",
            source_url="https://exburst.dev/ua/en/tournaments/10295",
            slug="tournament-1st-place-csm-denji-125494",
            date="2026-09-10",
        )
        self.assertEqual(item["kind"], "tournament")
        self.assertIn(item["kind"], write_guides.RESULT_KINDS)
        self.assertTrue(write_guides.is_result_list(item))
        self.assertEqual(write_guides.placement_of(item), 1)

    def test_slug_keeps_full_deck_id(self):
        long_key = "that-time-i-got-reincarnated-as-a-slime-diablo"
        slug = scrape_exburst_events.tournament_slug("3rd Place", long_key, 125498)
        self.assertTrue(slug.endswith("-125498"))
        self.assertLessEqual(len(slug), 70)
        self.assertTrue(scrape_exburst_events.slug_has_deck_id(slug, 125498))
        self.assertFalse(
            scrape_exburst_events.slug_has_deck_id(
                "tournament-3rd-place-that-time-i-got-reincarnated-as-a-slime-diablo-12"
            )
        )
        self.assertFalse(
            scrape_exburst_events.slug_has_deck_id(
                "tournament-4th-place-that-time-i-got-reincarnated-as-a-slime-soei-1198"
            )
        )

    def test_event_scrape_does_not_drop_short_existing_slugs(self):
        src = Path(scrape_exburst_events.__file__).read_text(encoding="utf-8")
        self.assertNotIn("dropped truncated slugs", src)
        self.assertNotIn("found[:] = kept", src)

    def test_known_ids_from_deck_url_and_slug(self):
        have = scrape_exburst_events.known_exburst_decks(
            [
                {"source_url": "https://exburst.dev/ua/en/decklists/125053", "slug": "exburst-foo"},
                {
                    "kind": "tournament",
                    "slug": "tournament-1st-place-csm-denji-125494",
                    "source_url": "https://exburst.dev/ua/en/tournaments/10295",
                },
                {"kind": "web", "slug": "blog-list"},
            ]
        )
        self.assertEqual(set(have), {125053, 125494})
        self.assertEqual(scrape_exburst_events.deck_id_of("125513"), 125513)
        self.assertEqual(scrape_exburst_events.deck_id_of(""), 0)

    def test_refreshes_catalog_web_row_but_skips_complete_tournament(self):
        web = {"kind": "web", "slug": "exburst-denji-125494", "cards": 50}
        done = {"kind": "tournament", "slug": "tournament-1st-csm-denji-125494", "cards": 50}
        self.assertTrue(scrape_exburst_events.should_refresh(web))
        self.assertFalse(scrape_exburst_events.should_refresh(done))
        self.assertTrue(scrape_exburst_events.should_refresh(None))

    def test_collapse_keeps_one_tournament_id(self):
        rows = [
            {"kind": "tournament", "slug": "tournament-1st-csm-denji-125494", "cards": 44, "key": "csm-denji"},
            {"kind": "tournament", "slug": "tournament-2nd-csm-denji-125494", "cards": 50, "key": "csm-denji"},
            {"kind": "event", "slug": "event-1st-solo-leveling-sung-jinwoo-1471380", "cards": 50, "key": "x"},
        ]
        out = scrape_community.collapse_by_slug(rows)
        slugs = [row["slug"] for row in out]
        self.assertEqual(slugs.count("tournament-2nd-csm-denji-125494"), 1)
        self.assertNotIn("tournament-1st-csm-denji-125494", slugs)
        self.assertIn("event-1st-solo-leveling-sung-jinwoo-1471380", slugs)


if __name__ == "__main__":
    unittest.main()
