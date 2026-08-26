#!/usr/bin/env python3
"""Homepage: 20 raid leaders, shop pill, character search."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_site  # noqa: E402
from generate_site import (  # noqa: E402
    build_character_search,
    combo_has_raid_face,
    is_raid_meta,
    pick_home_raid_leaders,
    write_home,
)


def raid_card(name: str, cost: str = "4") -> dict:
    return {
        "name": name,
        "cost": cost,
        "category": "Character",
        "color": "Purple",
        "trigger": "[Raid] Add this card to your hand.",
    }


class RaidTests(unittest.TestCase):
    def test_raid_detect(self):
        self.assertTrue(is_raid_meta({"trigger": "[Raid] 1"}))
        self.assertTrue(is_raid_meta({"effect": "When this [Raid]s"}))
        self.assertFalse(is_raid_meta({"trigger": "[Impact]"}))

    def test_combo_has_raid_face(self):
        cache = {"a-04": raid_card("A")}
        feats = {"a": {"meta": raid_card("A")}}
        arch = {"key": "a", "name": "A", "cons_items": [{"id": "a-04", "group": "Characters", "name": "A"}]}
        self.assertTrue(combo_has_raid_face(arch, cache, feats))
        feats2 = {"a": {"meta": {"trigger": "", "cost": "4", "category": "Character"}}}
        cache2 = {"a-04": {"name": "A", "cost": "4", "category": "Character", "trigger": ""}}
        self.assertFalse(combo_has_raid_face(arch, cache2, feats2))

    def test_pick_caps_at_twenty(self):
        cache = {}
        feats = {}
        combo = []
        meta = {}
        for i in range(30):
            cid = f"r-{i:02d}"
            name = f"Raid {i:02d}"
            cache[cid] = raid_card(name)
            key = f"raid-{i:02d}"
            feats[key] = {"meta": raid_card(name)}
            meta[f"raid {i:02d}"] = 0.02 - i * 0.0001
            combo.append(
                {
                    "key": key,
                    "name": name,
                    "title": f"IP {i // 3}",
                    "page": f"decklists/{key}.html",
                    "cons_items": [{"id": cid, "group": "Characters", "name": name}],
                    "lists": [{"date": "2026-08-20", "href": f"/{key}"}],
                    "meta_share": 0,
                }
            )
        picked = pick_home_raid_leaders(combo, cache, feats, meta_priority=meta)
        self.assertEqual(len(picked), 20)
        self.assertLessEqual(max(sum(1 for a in picked if a["title"] == t) for t in {a["title"] for a in picked}), 3)

    def test_pick_skips_unnamed_support(self):
        raid_meta = raid_card("Sung Jinwoo")
        combo = [
            {
                "key": "sung-jinwoo",
                "name": "Sung Jinwoo",
                "title": "Solo Leveling",
                "cons_items": [{"id": "sl-04", "group": "Characters", "name": "Sung Jinwoo"}],
                "lists": [{"date": "2026-08-20"}],
                "meta_share": 0.08,
            },
            {
                "key": "igris",
                "name": "Igris",
                "title": "Solo Leveling",
                "cons_items": [{"id": "sl-01", "group": "Characters", "name": "Igris"}],
                "lists": [{"date": "2026-08-20"}] * 40,
                "meta_share": 0,
            },
        ]
        cache = {
            "sl-04": raid_meta,
            "sl-01": {"name": "Igris", "cost": "4", "category": "Character", "trigger": "[Get]"},
        }
        feats = {
            "sung-jinwoo": {"meta": raid_meta},
            "igris": {"meta": cache["sl-01"]},
        }
        picked = pick_home_raid_leaders(combo, cache, feats, meta_priority={"sung jinwoo": 0.08})
        self.assertEqual([a["key"] for a in picked], ["sung-jinwoo"])

    def test_pick_uses_current_meta_share(self):
        def hub(key: str, name: str) -> dict:
            return {
                "key": key,
                "name": name,
                "cons_items": [{"id": key, "group": "Characters", "name": name}],
                "lists": [{"date": "2026-08-01"}],
            }

        combo = [hub("a", "Also Ran"), hub("b", "Sung Jinwoo")]
        cache = {"a": raid_card("Also Ran"), "b": raid_card("Sung Jinwoo")}
        feats = {"a": {"meta": cache["a"]}, "b": {"meta": cache["b"]}}
        picked = pick_home_raid_leaders(
            combo, cache, feats, meta_priority={"sung jinwoo": 0.09, "also ran": 0.001}
        )
        self.assertEqual(picked[0]["name"], "Sung Jinwoo")

    def test_character_search_index(self):
        cache = {
            "a-01": {"name": "Sung Jinwoo", "cost": "1", "category": "Character", "color": "Purple"},
            "a-04": {"name": "Igris", "cost": "4", "category": "Character", "color": "Purple"},
        }
        combo = [
            {
                "key": "sl-igris",
                "name": "Igris",
                "page": "decklists/sl-igris.html",
                "full": "Solo Leveling - Igris",
                "color": "Purple",
                "lists": [{}],
            }
        ]
        published = [
            {
                "href": "/decklists/sl-igris/x.html",
                "title": "Igris 50",
                "subtitle": "Locals",
                "date": "2026-08-01",
                "items": [
                    {"id": "a-01", "qty": 4, "group": "Characters", "name": "Sung Jinwoo"},
                    {"id": "a-04", "qty": 4, "group": "Characters", "name": "Igris"},
                ],
            }
        ]
        idx = build_character_search(published, combo, cache, {})
        names = {e["name"] for e in idx}
        self.assertIn("Sung Jinwoo", names)
        self.assertIn("Igris", names)
        jin = next(e for e in idx if e["name"] == "Sung Jinwoo")
        self.assertEqual(jin["lists"][0]["href"], "/decklists/sl-igris/x.html")
        igris = next(e for e in idx if e["name"] == "Igris")
        self.assertTrue(any(h["href"] == "/decklists/sl-igris.html" for h in igris["hubs"]))

    def test_home_markup(self):
        combo = [
            {
                "key": "opm-saitama",
                "name": "Saitama",
                "full": "One Punch Man - Saitama",
                "title": "One Punch Man",
                "page": "decklists/opm-saitama.html",
                "color": "Yellow",
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(generate_site.uadb, "ROOT", root):
                write_home(combo, [], {}, {})
            html = (root / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="/shop.html"', html)
        self.assertIn("home-big-shop", html)
        self.assertNotIn("home-shop-grid", html)
        self.assertNotIn('id="shop"', html)
        self.assertIn("char-search", html)
        self.assertIn("data-char-search", html)
        self.assertIn("Raid leaders", html)
        self.assertIn("/decklists/opm-saitama.html", html)
        self.assertIn("Saitama", html)


if __name__ == "__main__":
    unittest.main()
