#!/usr/bin/env python3
"""Public ExBurst catalog scrape: English 50s only, capped new lists."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import scrape_exburst  # noqa: E402
import uadb  # noqa: E402


class ExburstScrapeTests(unittest.TestCase):
    def test_caps_cover_a_300_list_run(self):
        self.assertGreaterEqual(scrape_exburst.MAX_LISTS, 300)
        self.assertGreaterEqual(scrape_exburst.MAX_PAGES, 80)
        self.assertEqual(scrape_exburst.GAME_TABLE, "uaen_decklists")

    def test_parses_exburst_qty_lines(self):
        text = "4 x UE17BT/SLG-1-022\n4 x UE17BT/SLG-1-030\n2 x UEX06BT/SAO-2-031\n"
        counts = uadb.parse_counts(text)
        self.assertEqual(counts.get("UE17BT/SLG-1-022"), 4)
        self.assertEqual(counts.get("UE17BT/SLG-1-030"), 4)
        self.assertEqual(counts.get("UEX06BT/SAO-2-031"), 2)

    def test_english_enough_rejects_asia_ua_lists(self):
        en = {"UE17BT/SLG-1-022": 4, "UE17BT/SLG-1-030": 12, "UE17BT/SLG-1-001": 34}
        ja = {"UA48BT/KGD-1-002": 4, "UA48BT/KGD-1-003": 46}
        self.assertTrue(scrape_exburst.english_enough(en))
        self.assertFalse(scrape_exburst.english_enough(ja))

    def test_date_window_keeps_last_week(self):
        old_from, old_to = scrape_exburst.DATE_FROM, scrape_exburst.DATE_TO
        scrape_exburst.DATE_FROM = "2026-09-10"
        scrape_exburst.DATE_TO = "2026-09-17"
        try:
            self.assertTrue(scrape_exburst.in_date_window("2026-09-10"))
            self.assertTrue(scrape_exburst.in_date_window("2026-09-16T18:00:00"))
            self.assertFalse(scrape_exburst.in_date_window("2026-09-09"))
            self.assertFalse(scrape_exburst.in_date_window("2026-09-17"))
        finally:
            scrape_exburst.DATE_FROM, scrape_exburst.DATE_TO = old_from, old_to

    def test_catalog_slug_keeps_full_deck_id(self):
        slug = scrape_exburst.catalog_slug(
            "Yellow Rimiru Diablo",
            "that-time-i-got-reincarnated-as-a-slime-diablo",
            125918,
        )
        self.assertTrue(slug.endswith("-125918"))
        self.assertLessEqual(len(slug), 70)
        self.assertTrue(slug.startswith("exburst-"))

    def test_known_ids_from_source_url(self):
        have = scrape_exburst.known_exburst_ids(
            [{"source_url": "https://exburst.dev/ua/en/decklists/125053", "slug": "exburst-foo"}]
        )
        self.assertEqual(have, {125053})


if __name__ == "__main__":
    unittest.main()
