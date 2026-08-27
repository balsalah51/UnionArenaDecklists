#!/usr/bin/env python3
"""SEO chrome, unique titles, and series internal links."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_site  # noqa: E402
import uadb  # noqa: E402
from generate_site import (  # noqa: E402
    build_title_catalog,
    list_doc_title,
    related_character_hubs,
    series_href,
    write_hub,
    write_list_page,
    write_sitemap,
)


class SeoChromeTests(unittest.TestCase):
    def test_page_title_is_unique_and_branded(self):
        self.assertNotEqual(uadb.page_title("Home"), "Home")
        self.assertNotEqual(uadb.page_title(""), "Untitled")
        home = uadb.page_title(uadb.BRAND)
        self.assertIn("Union Arena", home)
        self.assertIn("Standard", home)
        self.assertIn("|", uadb.page_title("Solo Leveling - Sung Jinwoo decklist"))
        self.assertLessEqual(len(uadb.page_title("Solo Leveling - Sung Jinwoo decklist")), 70)

    def test_seo_head_has_description_canonical_and_og(self):
        head = uadb.seo_head(
            "Sung Jinwoo decklist | Union Arena Decklists",
            "Sung Jinwoo Union Arena 50-card lists.",
            "decklists/solo-leveling-sung-jinwoo.html",
            image="/img/uadb-hero.png",
        )
        self.assertIn("<title>Sung Jinwoo decklist | Union Arena Decklists</title>", head)
        self.assertIn('name="description"', head)
        self.assertIn("Sung Jinwoo Union Arena 50-card lists.", head)
        self.assertIn('rel="canonical"', head)
        self.assertIn("https://unionarenadecklists.com/decklists/solo-leveling-sung-jinwoo.html", head)
        self.assertIn('property="og:title"', head)
        self.assertIn('name="twitter:card"', head)

    def test_page_chrome_never_uses_home_or_untitled(self):
        html = uadb.page_chrome(
            uadb.page_title("Yu Yu Hakusho - Youko Kurama event list · 2026-08-16"),
            "Youko Kurama event list.",
            "color-red",
            "<h1>Youko Kurama</h1>",
            path="decklists/yyh/x.html",
        )
        self.assertNotIn("<title>Home</title>", html)
        self.assertNotIn("<title>Untitled</title>", html)
        self.assertIn('name="description"', html)
        self.assertIn("<h1>Youko Kurama</h1>", html)
        self.assertIn('alt=', uadb.page_chrome("A", "B", "color-red", '<img src="/x.png" alt="Youko Kurama card" />', path="x.html"))


class SeriesLinkTests(unittest.TestCase):
    def test_series_href_and_related_hubs(self):
        self.assertEqual(series_href("Solo Leveling"), "/series/solo-leveling.html")
        self.assertEqual(series_href("YYH"), "/series/yu-yu-hakusho.html")
        hubs = [
            {
                "key": "yyh-kurama",
                "name": "Youko Kurama",
                "full": "Yu Yu Hakusho - Youko Kurama",
                "title": "Yu Yu Hakusho",
                "page": "decklists/yyh-kurama.html",
                "lists": [{"slug": "a"}],
                "from_color": False,
            },
            {
                "key": "yyh-toguro",
                "name": "Younger Toguro",
                "full": "Yu Yu Hakusho - Younger Toguro",
                "title": "Yu Yu Hakusho",
                "page": "decklists/yyh-toguro.html",
                "lists": [{"slug": "b"}, {"slug": "c"}],
                "from_color": False,
            },
            {
                "key": "yyh-purple",
                "name": "Purple",
                "full": "Yu Yu Hakusho - Purple",
                "title": "Yu Yu Hakusho",
                "page": "decklists/yyh-purple.html",
                "lists": [],
                "from_color": True,
            },
        ]
        catalog = build_title_catalog(hubs)
        self.assertEqual(len(catalog), 1)
        self.assertEqual(catalog[0]["slug"], "yu-yu-hakusho")
        related = related_character_hubs(hubs[0], catalog)
        names = {h["name"] for h in related}
        self.assertIn("Younger Toguro", names)
        self.assertNotIn("Youko Kurama", names)
        self.assertNotIn("Purple", names)

    def test_list_titles_include_kind_and_date(self):
        arch = {"name": "Sung Jinwoo", "full": "Solo Leveling - Sung Jinwoo"}
        title = list_doc_title(
            arch,
            {"title": "Solo Leveling - Sung Jinwoo", "kind": "event", "date": "2026-08-16"},
        )
        self.assertIn("event list", title)
        self.assertIn("2026-08-16", title)
        other = list_doc_title(
            arch,
            {"title": "Solo Leveling - Sung Jinwoo", "kind": "contender", "date": "2026-08-23"},
        )
        self.assertNotEqual(title, other)
        placed = list_doc_title(
            arch,
            {
                "title": "Solo Leveling - Sung Jinwoo",
                "kind": "event",
                "date": "2026-08-16",
                "slug": "event-1st-solo-leveling-sung-jinwoo-1471350",
            },
        )
        self.assertIn("1st", placed)

    def test_hub_and_list_markup_link_series(self):
        arch = {
            "key": "yyh-kurama",
            "name": "Youko Kurama",
            "full": "Yu Yu Hakusho - Youko Kurama",
            "title": "Yu Yu Hakusho",
            "page": "decklists/yyh-kurama.html",
            "dir": "decklists/yyh-kurama",
            "lists": [],
        }
        sibling = {
            "key": "yyh-toguro",
            "name": "Younger Toguro",
            "full": "Yu Yu Hakusho - Younger Toguro",
            "title": "Yu Yu Hakusho",
            "page": "decklists/yyh-toguro.html",
            "dir": "decklists/yyh-toguro",
            "lists": [{"slug": "x"}],
        }
        catalog = build_title_catalog([arch, sibling])
        lists = [
            {
                "slug": "event-1",
                "kind": "event",
                "title": "Yu Yu Hakusho - Youko Kurama",
                "subtitle": "1st",
                "date": "2026-08-16",
                "href": "/decklists/yyh-kurama/event-1.html",
                "sim_text": "4xUE08BT/YYH-1-001",
            },
            {
                "slug": "event-2",
                "kind": "event",
                "title": "Yu Yu Hakusho - Youko Kurama",
                "subtitle": "Top 4",
                "date": "2026-08-10",
                "href": "/decklists/yyh-kurama/event-2.html",
                "sim_text": "",
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "decklists" / "yyh-kurama").mkdir(parents=True)
            with patch.object(generate_site.uadb, "ROOT", root), patch.object(uadb, "ROOT", root):
                write_hub(arch, lists, [], {}, {"id": "", "meta": {"color": "red"}}, catalog=catalog)
                write_list_page(arch, lists[0], [], {}, {"id": "", "meta": {"color": "red"}}, siblings=lists, catalog=catalog)
            hub = (root / "decklists/yyh-kurama.html").read_text(encoding="utf-8")
            page = (root / "decklists/yyh-kurama/event-1.html").read_text(encoding="utf-8")
        self.assertIn("/series/yu-yu-hakusho.html", hub)
        self.assertIn("Younger Toguro", hub)
        self.assertIn("<h1>Yu Yu Hakusho - Youko Kurama</h1>", hub)
        self.assertIn('rel="canonical"', hub)
        self.assertIn('name="description"', hub)
        self.assertIn("/series/yu-yu-hakusho.html", page)
        self.assertIn("event-2.html", page)
        self.assertIn("<title>", page)
        self.assertNotIn("<title>Home</title>", page)
        self.assertIn('name="description"', page)

    def test_sitemap_skips_json_and_thread_redirects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(generate_site.uadb, "ROOT", root):
                write_sitemap(
                    [
                        "",
                        "series.html",
                        "discord/welcome.html",
                        "discord/board.json",
                        "discord/threads/foo.html",
                        "discord/",
                    ],
                    lastmod="2026-08-27",
                )
            xml = (root / "sitemap.xml").read_text(encoding="utf-8")
        self.assertIn("https://unionarenadecklists.com/</loc>", xml)
        self.assertIn("series.html", xml)
        self.assertIn("<lastmod>2026-08-27</lastmod>", xml)
        self.assertNotIn("board.json", xml)
        self.assertNotIn("/threads/", xml)


if __name__ == "__main__":
    unittest.main()
