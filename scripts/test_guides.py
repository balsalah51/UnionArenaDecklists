#!/usr/bin/env python3
"""Tier list ranking and strategy guide pages."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_site  # noqa: E402
import uadb  # noqa: E402
import write_guides  # noqa: E402
from generate_site import write_hub  # noqa: E402


def _arch(name: str, title: str, **extra) -> dict:
    key = extra.pop("key", None) or uadb.slugify(name)
    row = {
        "key": key,
        "name": name,
        "full": f"{title} - {name}",
        "title": title,
        "page": f"decklists/{key}.html",
        "dir": f"decklists/{key}",
        "from_combo": True,
        "color": extra.pop("color", "Purple"),
        "tier": extra.pop("tier", ""),
        "style": extra.pop("style", "Midrange"),
        "meta_share": extra.pop("meta_share", 0.0),
        "strengths": extra.pop("strengths", ["Public Standard list."]),
        "weaknesses": extra.pop("weaknesses", []),
        "updated": "2026-09-01",
    }
    row.update(extra)
    return row


def _list(slug: str, when: str, kind: str = "event", **extra) -> dict:
    row = {
        "slug": slug,
        "kind": kind,
        "title": extra.pop("title", slug),
        "subtitle": extra.pop("subtitle", ""),
        "player": extra.pop("player", ""),
        "date": when,
        "href": extra.pop("href", f"/decklists/x/{slug}.html"),
    }
    row.update(extra)
    return row


def _job(arch, lists, items, feature=None):
    return (arch, lists, items, feature or {}, False)


class PlacementTests(unittest.TestCase):
    def test_reads_ordinals_from_slug_and_player(self):
        self.assertEqual(write_guides.placement_of({"slug": "event-1st-solo-leveling-sung-jinwoo"}), 1)
        self.assertEqual(write_guides.placement_of({"player": "3rd Place"}), 3)
        self.assertEqual(write_guides.placement_of({"subtitle": "Top 8"}), 8)
        self.assertEqual(write_guides.placement_of({"title": "locals dump"}), None)

    def test_result_kinds_count_without_place(self):
        self.assertTrue(write_guides.is_result_list({"kind": "official"}))
        self.assertTrue(write_guides.is_result_list({"kind": "event", "title": "locals dump"}))
        self.assertFalse(write_guides.is_result_list({"kind": "youtube", "title": "profile"}))
        self.assertFalse(
            write_guides.is_result_list(
                {
                    "kind": "web",
                    "title": "3rd Wheel Subaru (Crusch x Ferris)",
                    "slug": "exburst-3rd-wheel-subaru-crusch-x-ferris-re-zero-126972",
                }
            )
        )

    def test_shared_fifty_does_not_name_every_character(self):
        entry = {
            "slug": "event-1st-solo-leveling-sung-jinwoo",
            "title": "Solo Leveling - Sung Jinwoo",
            "kind": "event",
        }
        self.assertTrue(write_guides.list_names_character(entry, "Sung Jinwoo"))
        self.assertFalse(write_guides.list_names_character(entry, "Cha Hae-In"))


class TierAssignTests(unittest.TestCase):
    def test_contender_one_with_recent_results_is_s(self):
        rows = [
            {
                "name": "Sung Jinwoo",
                "contender_tier": "1",
                "meta_share": 0.08,
                "recent_top8": 2,
                "recent_wins": 1,
                "recent_results": 3,
                "recent_lists": 4,
                "list_count": 12,
            },
            {
                "name": "Quiet Tier One",
                "contender_tier": "1",
                "meta_share": 0.02,
                "recent_top8": 0,
                "recent_wins": 0,
                "recent_results": 0,
                "recent_lists": 1,
                "list_count": 3,
            },
            {
                "name": "Mid",
                "contender_tier": "2",
                "meta_share": 0.02,
                "recent_top8": 0,
                "recent_wins": 0,
                "recent_results": 1,
                "recent_lists": 2,
                "list_count": 5,
            },
            {
                "name": "Low",
                "contender_tier": "3",
                "meta_share": 0.01,
                "recent_top8": 0,
                "recent_wins": 0,
                "recent_results": 0,
                "recent_lists": 1,
                "list_count": 2,
            },
            {
                "name": "Fringe",
                "contender_tier": "",
                "meta_share": 0.0,
                "recent_top8": 0,
                "recent_wins": 0,
                "recent_results": 0,
                "recent_lists": 1,
                "list_count": 1,
            },
        ]
        write_guides.assign_letters(rows)
        by_name = {r["name"]: r["tier"] for r in rows}
        self.assertEqual(by_name["Sung Jinwoo"], "S")
        self.assertEqual(by_name["Quiet Tier One"], "A")
        self.assertEqual(by_name["Mid"], "B")
        self.assertEqual(by_name["Low"], "C")
        self.assertEqual(by_name["Fringe"], "D")

    def test_hosted_volume_letters_when_contender_has_no_number(self):
        rows = [
            {
                "name": "Rem",
                "contender_tier": "",
                "meta_share": 0.0,
                "recent_top8": 0,
                "recent_wins": 0,
                "recent_results": 0,
                "recent_lists": 40,
                "list_count": 62,
            },
            {
                "name": "Ram",
                "contender_tier": "",
                "meta_share": 0.0,
                "recent_top8": 0,
                "recent_wins": 0,
                "recent_results": 0,
                "recent_lists": 3,
                "list_count": 3,
            },
        ]
        write_guides.assign_letters(rows)
        by_name = {r["name"]: r["tier"] for r in rows}
        self.assertEqual(by_name["Rem"], "C")
        self.assertEqual(by_name["Ram"], "D")
        self.assertTrue(all(letter in "SABCD" for letter in by_name.values()))

    def test_field_with_many_locals_is_a_bell_curve(self):
        rows = []
        for i in range(12):
            rows.append(
                {
                    "name": f"Regular {i:02d}",
                    "contender_tier": "2",
                    "meta_share": 0.02 - i * 0.001,
                    "recent_top8": 12 - i,
                    "recent_top4": max(0, 6 - i),
                    "recent_wins": 1 if i < 2 else 0,
                    "recent_results": 14 - i,
                    "recent_lists": 16 - i,
                    "list_count": 20,
                }
            )
        rows.append(
            {
                "name": "Sung Jinwoo",
                "contender_tier": "1",
                "meta_share": 0.08,
                "recent_top8": 20,
                "recent_top4": 12,
                "recent_wins": 8,
                "recent_results": 24,
                "recent_lists": 30,
                "list_count": 40,
            }
        )
        write_guides.assign_letters(rows)
        letters = [row["tier"] for row in rows]
        counts = {letter: letters.count(letter) for letter in "SABCD"}
        self.assertEqual(max(rows, key=lambda r: r["score"])["tier"], "S")
        self.assertGreaterEqual(counts["B"], counts["A"])
        self.assertGreaterEqual(counts["B"], 3)
        self.assertLess(counts["A"], 6)
        self.assertTrue(counts["S"] >= 1)
        self.assertLess(counts["S"], counts["B"])
        self.assertEqual(write_guides.curve_letters(5), ["S", "A", "B", "C", "D"])
        curve = write_guides.curve_letters(22)
        self.assertGreater(curve.count("B"), curve.count("A"))
        self.assertGreater(curve.count("B"), curve.count("S"))


class PlanAndPagesTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 9, 7)
        self.cache = {
            "UE17BT/SLG-1-022": {
                "name": "Sung Jinwoo",
                "category": "Character",
                "color": "Purple",
                "cost": "12",
                "bp": "5000",
                "trigger": "[Raid] Add this card to your hand, or if you have the required energy, perform Raid with it.",
            },
            "UE17BT/SLG-1-018": {
                "name": "Sung Jinwoo",
                "category": "Character",
                "color": "Purple",
                "cost": "4",
                "bp": "3000",
                "trigger": "[Raid] Add this card to your hand.",
            },
            "UE17BT/SLG-1-030": {
                "name": "Shadow Soldiers",
                "category": "Character",
                "color": "Purple",
                "cost": "1",
                "trigger": "",
            },
            "UE15BT/EVA-1-005": {
                "name": "Rei Ayanami",
                "category": "Character",
                "color": "Blue",
                "cost": "5",
                "trigger": "[Raid] Add this card to your hand.",
            },
        }
        sung_items = [
            {"id": "UE17BT/SLG-1-022", "name": "Sung Jinwoo", "count": 4, "group": "Characters"},
            {"id": "UE17BT/SLG-1-018", "name": "Sung Jinwoo", "count": 4, "group": "Characters"},
            {"id": "UE17BT/SLG-1-030", "name": "Shadow Soldiers", "count": 12, "group": "Characters"},
        ]
        rei_items = [
            {"id": "UE15BT/EVA-1-005", "name": "Rei Ayanami", "count": 4, "group": "Characters"},
        ]
        self.jobs = [
            _job(
                _arch("Sung Jinwoo", "Solo Leveling", key="sung-jinwoo", tier="1", meta_share=0.08),
                [
                    _list("event-1st-solo-leveling-sung-jinwoo", "2026-08-21", player="1st Place"),
                    _list("event-2nd-solo-leveling-sung-jinwoo", "2026-08-28", player="2nd Place"),
                    _list("event-top8-solo-leveling-sung-jinwoo", "2026-09-01", subtitle="Top 8"),
                    _list("web-lab", "2026-08-10", kind="web"),
                ],
                sung_items,
                {"id": "UE17BT/SLG-1-022", "meta": self.cache["UE17BT/SLG-1-022"]},
            ),
            _job(
                _arch("Rei Ayanami", "Evangelion", key="rei-ayanami", tier="1", meta_share=0.03, color="Blue"),
                [
                    _list("official-3rd-place-evangelion-rei", "2026-08-21", kind="official", player="3rd Place"),
                    _list("event-rei-2", "2026-08-30"),
                    _list("event-rei-3", "2026-09-02"),
                ],
                rei_items,
                {"id": "UE15BT/EVA-1-005", "meta": self.cache["UE15BT/EVA-1-005"]},
            ),
        ]

    def test_plan_builds_s_tier_and_guides(self):
        plan = write_guides.build_plan(self.jobs, self.cache, today=self.today)
        board = {r["name"]: r for r in plan["board"]}
        self.assertEqual(board["Sung Jinwoo"]["tier"], "S")
        self.assertGreaterEqual(board["Sung Jinwoo"]["recent_top8"], 2)
        hrefs = [g["href"] for g in plan["character_guides"]]
        self.assertIn("/guides/sung-jinwoo-strategy.html", hrefs)
        self.assertTrue(any(g["slug"] == "how-to-read-a-50" for g in plan["topic_guides"]))
        self.assertEqual(write_guides.guide_for_arch(plan, self.jobs[0][0])["href"], "/guides/sung-jinwoo-strategy.html")

    def test_named_community_faces_get_letters_and_board_slots(self):
        rem_lists = [
            _list(
                f"exburst-rem-deck-{i}",
                "2026-08-20",
                kind="web",
                title="Rem Deck",
                key="re-zero",
            )
            for i in range(8)
        ]
        ram_lists = [
            _list(
                f"exburst-ram-deck-{i}",
                "2026-08-21",
                kind="web",
                title="Ram Deck",
                key="re-zero",
            )
            for i in range(3)
        ]
        jobs = self.jobs + [
            _job(
                _arch("re-zero", "Re:Zero", key="re-zero", tier=""),
                rem_lists + ram_lists,
                [],
            )
        ]
        plan = write_guides.build_plan(jobs, self.cache, today=self.today)
        rows = {r["name"]: r for r in plan["rows"]}
        self.assertIn("Rem", rows)
        self.assertIn("Ram", rows)
        self.assertIn(rows["Rem"]["tier"], "SABCD")
        self.assertIn(rows["Ram"]["tier"], "SABCD")
        self.assertTrue(rows["Rem"]["tier"])
        board = {r["name"] for r in plan["board"]}
        self.assertIn("Rem", board)
        self.assertIn("Ram", board)
        self.assertNotIn("re-zero", {r["name"].lower() for r in plan["board"]})

    def test_pages_render_board_and_writeup(self):
        plan = write_guides.build_plan(self.jobs, self.cache, today=self.today)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(write_guides.uadb, "ROOT", root), patch.object(uadb, "ROOT", root):
                paths = write_guides.write_pages(plan, self.cache)
            tier = (root / "tier-list.html").read_text(encoding="utf-8")
            guide = (root / "guides/sung-jinwoo-strategy.html").read_text(encoding="utf-8")
            index = (root / "guides/index.html").read_text(encoding="utf-8")
        self.assertIn("tier-list.html", paths)
        self.assertIn("tier-board", tier)
        self.assertIn("tier-s", tier)
        self.assertIn("Sung Jinwoo", tier)
        self.assertIn("TCG Contender", tier)
        self.assertIn("hosted", tier.lower())
        self.assertIn("Sung Jinwoo strategy", guide)
        self.assertIn("Shadow Soldiers", guide)
        self.assertIn("[Raid]", guide)
        self.assertIn("How the raid face works", guide)
        self.assertIn("The current 50-card core", guide)
        self.assertNotIn("52.1%", guide)
        self.assertIn("Sung Jinwoo strategy", index)
        self.assertIn("How to read a Union Arena 50", index)
        self.assertIn('href="/tier-list.html"', index)

    def test_nav_and_hub_link_guides(self):
        nav = uadb.nav_html("guides")
        self.assertIn("/tier-list.html", nav)
        self.assertIn("Tier List", nav)
        self.assertIn("/guides/", nav)
        self.assertIn("Guides", nav)
        self.assertIn('aria-current="page"', nav)
        foot = uadb.footer_links()
        self.assertIn("/tier-list.html", foot)
        self.assertIn("/guides/", foot)
        plan = write_guides.build_plan(self.jobs, self.cache, today=self.today)
        arch = self.jobs[0][0]
        lists = self.jobs[0][1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "decklists").mkdir(parents=True)
            with patch.object(generate_site.uadb, "ROOT", root), patch.object(uadb, "ROOT", root):
                write_hub(
                    arch,
                    lists,
                    self.jobs[0][2],
                    self.cache,
                    self.jobs[0][3],
                    guide=write_guides.guide_for_arch(plan, arch),
                )
            hub = (root / "decklists/sung-jinwoo.html").read_text(encoding="utf-8")
        self.assertIn("/guides/sung-jinwoo-strategy.html", hub)
        self.assertIn("leader-strategy", hub)
        self.assertIn("How it plays", hub)


if __name__ == "__main__":
    unittest.main()
