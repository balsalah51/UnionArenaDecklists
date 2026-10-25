#!/usr/bin/env python3
"""Character assignment, card groups, and the Reddit payload that aborted refresh."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_site  # noqa: E402
import primary_hubs  # noqa: E402
import scrape_community  # noqa: E402
import uadb  # noqa: E402
import write_guides  # noqa: E402


class TaxonomyTests(unittest.TestCase):
    def test_group_for_does_not_invent_a_character(self):
        self.assertEqual(uadb.group_for(""), "Other")
        self.assertEqual(uadb.group_for("Event"), "Events")
        self.assertEqual(uadb.group_for("Character"), "Characters")
        self.assertEqual(uadb.group_for("Site"), "Sites")

    def test_identity_ignores_event_cards(self):
        cache = {
            "UE10BT/AOT-1-066": {
                "name": "I'm Going For a Perfect Game.",
                "category": "Event",
                "cost": "1",
                "color": "Green",
                "title": "Attack on Titan",
            },
            "UEX07BT/AOT-2-052": {
                "name": "Zeke Jaeger",
                "category": "Character",
                "cost": "3",
                "color": "Green",
                "title": "Attack on Titan",
            },
        }
        items = [
            {"id": "UE10BT/AOT-1-066", "count": 4, "name": "I'm Going For a Perfect Game.", "group": "Events"},
            {"id": "UEX07BT/AOT-2-052", "count": 4, "name": "Zeke Jaeger", "group": "Characters"},
        ]
        ident = generate_site.assign_list_identity(items, cache, prefer_name="Eren Jaeger")
        self.assertEqual(ident["character"], "Zeke Jaeger")
        self.assertEqual(ident["color"], "green")
        self.assertNotIn("Perfect Game", ident["character"])

    def test_reddit_list_payload_does_not_crash(self):
        posts = scrape_community.reddit_posts({"data": [{"title": "Zeke 50", "selftext": "4xUE10BT/AOT-1-001"}]})
        self.assertEqual(posts[0]["title"], "Zeke 50")
        wrapped = scrape_community.reddit_posts(
            {"data": {"children": [{"data": {"title": "Rem 50", "selftext": ""}}]}}
        )
        self.assertEqual(wrapped[0]["title"], "Rem 50")

    def test_deck_title_drops_a_long_numeric_id(self):
        title = generate_site.deck_page_title(
            {"name": "Zeke Jaeger"},
            {
                "deck_name": "Attack On Titan 1471425",
                "deck_color": "Green",
                "date": "2026-10-16",
            },
        )
        self.assertIn("Zeke Jaeger", title)
        self.assertIn("Green", title)
        self.assertIn("2026-10-16", title)
        self.assertNotIn("1471425", title)

    def test_redirect_stub_is_noindex(self):
        page = uadb.html_redirect("/decklists/zeke-jaeger.html", "Moved")
        self.assertIn('content="noindex, follow"', page)
        self.assertIn('http-equiv="refresh"', page)
        self.assertIn("/decklists/zeke-jaeger.html", page)

    def test_fallback_redirect_peels_color_and_does_not_guess_a_shorter_name(self):
        written = {
            "decklists/aoi-todo.html",
            "decklists/emilia.html",
            "decklists/ichigo-kurosaki.html",
            "decklists/silva.html",
        }
        self.assertEqual(
            primary_hubs.fallback_redirect_target("decklists/aoi-todo-blue.html", written),
            "/decklists/aoi-todo.html",
        )
        self.assertEqual(
            primary_hubs.fallback_redirect_target("decklists/emilia-box-topper-gold-foil.html", written),
            "/decklists/emilia.html",
        )
        self.assertEqual(
            primary_hubs.fallback_redirect_target("decklists/nozel-silva.html", written),
            "/characters.html",
        )
        self.assertEqual(
            primary_hubs.fallback_redirect_target("decklists/bleach-ichigo-kurosaki/event-2nd.html", written),
            "/decklists/ichigo-kurosaki.html",
        )

    def test_retired_guide_keeps_a_url(self):
        hubs = {
            "decklists/aki-hayakawa.html",
            "decklists/crusch-karsten.html",
            "decklists/crusch-karsten-blue.html",
            "decklists/evangelion-test-type-01.html",
        }
        guides = {"guides/index.html"}
        self.assertEqual(
            write_guides.retired_guide_target("aki-hayakawa-strategy.html", hubs, guides),
            "/decklists/aki-hayakawa.html",
        )
        self.assertEqual(
            write_guides.retired_guide_target("crusch-strategy.html", hubs, guides),
            "/decklists/crusch-karsten.html",
        )
        self.assertEqual(
            write_guides.retired_guide_target(
                "evangelion-test-type-01-pseudo-dms-phase-strategy.html", hubs, guides
            ),
            "/decklists/evangelion-test-type-01.html",
        )
        self.assertEqual(
            write_guides.retired_guide_target("erwin-smith-strategy.html", hubs, guides),
            "/guides/",
        )

    def test_href_for_name_skips_a_missing_hub(self):
        self.assertEqual(generate_site._href_for_name("Crusch Karsten", []), "")
        href = generate_site._href_for_name(
            "Crusch",
            [{"name": "Crusch Karsten", "page": "decklists/crusch-karsten.html", "key": "crusch-karsten"}],
        )
        self.assertEqual(href, "/decklists/crusch-karsten.html")


if __name__ == "__main__":
    unittest.main()
