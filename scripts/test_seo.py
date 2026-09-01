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
    hub_doc_title,
    list_doc_title,
    related_character_hubs,
    series_href,
    write_feed,
    write_format,
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
        long_list = uadb.page_title(
            "Evangelion Test Type-01 Pseudo DMS Phase event list 5th (2026-08-16) 1471425"
        )
        self.assertLessEqual(len(long_list), 70)
        self.assertIn("1471425", long_list)

    def test_hub_titles_disambiguate_color_and_short_slugs(self):
        series_hub = hub_doc_title(
            {
                "name": "Taro Sakamoto",
                "title": "Sakamoto Days",
                "key": "sakamoto-days-taro-sakamoto",
            }
        )
        short_hub = hub_doc_title(
            {
                "name": "Taro Sakamoto",
                "title": "Sakamoto Days",
                "key": "taro-sakamoto",
            }
        )
        color_hub = hub_doc_title(
            {
                "name": "Taro Sakamoto",
                "title": "Sakamoto Days",
                "key": "sakamoto-days-yellow",
                "from_color": True,
            }
        )
        mismatched = hub_doc_title(
            {
                "name": "Roy Mustang",
                "title": "Fullmetal Alchemist",
                "key": "fullmetal-alchemist-olivier-mira-armstrong",
            }
        )
        self.assertNotEqual(series_hub, short_hub)
        self.assertNotEqual(series_hub, color_hub)
        self.assertIn("Yellow", color_hub)
        self.assertIn("Olivier", mismatched)
        self.assertNotIn("Roy", mismatched)
        asuka_purple = hub_doc_title(
            {
                "name": "Asuka Shikinami Langley",
                "title": "Evangelion",
                "key": "asuka-shikinami-langley-purple",
            }
        )
        eva_purple = hub_doc_title(
            {
                "name": "Rei Ayanami",
                "title": "Evangelion",
                "key": "evangelion-red",
                "from_color": True,
            }
        )
        self.assertIn("Asuka", asuka_purple)
        self.assertIn("purple", asuka_purple.lower())
        self.assertNotEqual(asuka_purple, eva_purple)
        unit_a = list_doc_title(
            {
                "name": "Evangelion Production Model-02",
                "title": "Evangelion",
                "key": "evangelion-evangelion-production-model-02",
            },
            {"kind": "contender", "date": "2026-08-23", "slug": "contender-consensus"},
        )
        unit_b = list_doc_title(
            {
                "name": "Evangelion Production Model-08",
                "title": "Evangelion",
                "key": "evangelion-evangelion-production-model-08",
            },
            {"kind": "contender", "date": "2026-08-23", "slug": "contender-consensus"},
        )
        self.assertNotEqual(unit_a, unit_b)
        self.assertIn("02", unit_a)
        self.assertIn("08", unit_b)

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
        self.assertIn("max-image-preview:large", head)
        self.assertIn('property="og:image:alt"', head)
        self.assertIn('rel="icon"', uadb.FONT_LINKS)
        self.assertIn("/img/icon-48.png", uadb.FONT_LINKS)
        self.assertLess(uadb.FONT_LINKS.find("/img/icon-48.png"), uadb.FONT_LINKS.find("/favicon.svg"))
        self.assertIn("/favicon.svg", uadb.FONT_LINKS)
        self.assertIn("/feed.xml", uadb.FONT_LINKS)
        self.assertIn("adsbygoogle.js", uadb.FONT_LINKS)
        self.assertIn(uadb.ADSENSE_CLIENT, uadb.FONT_LINKS)
        chrome = uadb.page_chrome("Title", "Desc", "red", "body")
        self.assertIn("ca-pub-1074015774205047", chrome)
        ads_txt = (ROOT / "ads.txt").read_text()
        self.assertIn("google.com, pub-1074015774205047, DIRECT", ads_txt)
        self.assertIn('src="/img/logo.svg"', uadb.logo_html())
        favicon = (ROOT / "favicon.svg").read_text(encoding="utf-8")
        self.assertNotIn(">UA</text>", favicon)
        self.assertNotIn(">UA<", favicon)
        self.assertIn("<polygon", favicon)
        self.assertTrue((ROOT / "img" / "logo.svg").is_file())

    def test_pages_have_no_em_dashes(self):
        self.assertEqual(uadb.no_em("A — B"), "A - B")
        self.assertEqual(uadb.display_name("Pi... 3.141592—"), "Pi... 3.141592 -")
        html = uadb.page_chrome("Title — Meta", "Desc — more", "red", "Hello — world")
        self.assertNotIn("\u2014", html)
        self.assertNotIn("&mdash;", html)
        self.assertIn("Hello - world", html)
        self.assertIn("Title - Meta", html)

    def test_website_search_action_and_organization(self):
        site = uadb.website_ld()
        org = uadb.organization_ld()
        action = site["potentialAction"]
        self.assertEqual(action["@type"], "SearchAction")
        self.assertIn("{search_term_string}", action["target"]["urlTemplate"])
        self.assertIn("/characters.html?q=", action["target"]["urlTemplate"])
        self.assertEqual(org["logo"]["url"], "https://unionarenadecklists.com/img/icon-512.png")
        self.assertEqual(org["logo"]["width"], 512)
        self.assertEqual(org["image"], "https://unionarenadecklists.com/img/icon-512.png")
        self.assertIn(uadb.DISCORD, org["sameAs"])
        graph = uadb.site_graph([site])
        types = [block["@type"] for block in graph]
        self.assertIn("Organization", types)
        self.assertIn("WebSite", types)
        faq = uadb.faq_ld([("How many cards are in a Union Arena deck?", "Exactly 50 cards.")])
        self.assertEqual(faq["@type"], "FAQPage")
        self.assertEqual(faq["mainEntity"][0]["name"], "How many cards are in a Union Arena deck?")

    def test_google_favicon_files_exist(self):
        root = Path(__file__).resolve().parents[1]
        for rel in (
            "favicon.ico",
            "favicon.svg",
            "site.webmanifest",
            "img/icon-48.png",
            "img/icon-96.png",
            "img/icon-192.png",
            "img/icon-512.png",
            "img/apple-touch-icon.png",
            "img/logo.svg",
        ):
            self.assertTrue((root / rel).is_file(), rel)
        robots = (root / "robots.txt").read_text(encoding="utf-8")
        self.assertIn("Allow: /favicon.ico", robots)
        self.assertIn("Allow: /img/", robots)

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
        self.assertEqual(series_href("100 Girlfriends"), "/series/the-100-girlfriends.html")
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

    def test_catalog_collapses_100_girlfriends_aliases(self):
        hubs = [
            {
                "key": "nano-eiai",
                "name": "Nano Eiai",
                "title": "100 Girlfriends",
                "page": "decklists/nano-eiai.html",
                "lists": [{"slug": "a"}, {"slug": "b"}],
                "from_color": False,
            },
            {
                "key": "shizuka",
                "name": "Shizuka Yoshimoto",
                "title": "The 100 Girlfriends",
                "page": "decklists/the-100-girlfriends-shizuka-yoshimoto.html",
                "lists": [{"slug": "c"}],
                "from_color": False,
            },
        ]
        catalog = build_title_catalog(hubs)
        self.assertEqual(len(catalog), 1)
        self.assertEqual(catalog[0]["slug"], "the-100-girlfriends")
        self.assertEqual(catalog[0]["name"], "100 Girlfriends")
        self.assertEqual(catalog[0]["hub_count"], 2)

    def test_catalog_keeps_the_hub_with_lists(self):
        thin = {
            "key": "solo-leveling-sung-jinwoo",
            "name": "Sung Jinwoo",
            "title": "Solo Leveling",
            "page": "decklists/solo-leveling-sung-jinwoo.html",
            "lists": [{"slug": "a"}],
            "from_color": False,
            "from_combo": False,
        }
        rich = {
            "key": "sung-jinwoo",
            "name": "Sung Jinwoo",
            "title": "Solo Leveling",
            "page": "decklists/sung-jinwoo.html",
            "lists": [{"slug": "b"}, {"slug": "c"}, {"slug": "d"}],
            "from_color": False,
            "from_combo": True,
        }
        catalog = build_title_catalog([thin, rich])
        chars = catalog[0]["characters"]
        sung = [h for h in chars if h["name"] == "Sung Jinwoo"]
        self.assertEqual(len(sung), 1)
        self.assertEqual(sung[0]["key"], "sung-jinwoo")
        self.assertEqual(len(sung[0]["lists"]), 3)

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
        self.assertIn("1471350", placed)
        a = list_doc_title(
            arch,
            {
                "title": "Rurouni Kenshin - Kenshin Himura",
                "kind": "official",
                "date": "2025-12-25",
                "slug": "official-1st-place-rurouni-kenshin-kenshin-himura-6ukbcj",
                "subtitle": "1st Place",
            },
        )
        b = list_doc_title(
            arch,
            {
                "title": "Rurouni Kenshin - Kenshin Himura",
                "kind": "official",
                "date": "2025-12-25",
                "slug": "official-1st-place-rurouni-kenshin-kenshin-himura-5pwvqn",
                "subtitle": "1st Place",
            },
        )
        self.assertNotEqual(a, b)

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
        self.assertIn("max-image-preview:large", hub)
        self.assertIn("SearchAction", hub)
        self.assertIn("CollectionPage", hub)
        self.assertIn("CreativeWork", page)
        self.assertIn("article:published_time", page)

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
        self.assertIn("xmlns:image", xml)
        self.assertNotIn("board.json", xml)
        self.assertNotIn("/threads/", xml)

    def test_sitemap_embeds_card_images_and_feed_lists_recent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(generate_site.uadb, "ROOT", root):
                write_sitemap(
                    ["", "decklists/sung-jinwoo.html"],
                    lastmod="2026-08-28",
                    images={
                        "": [
                            ("/img/uadb-hero.png", "Union Arena Decklists"),
                            ("/img/icon-512.png", "Union Arena Decklists logo"),
                        ],
                        "decklists/sung-jinwoo.html": (
                            "https://www.unionarena-tcg.com/na/images/cardlist/card/UE17BT_SLG-1-022.png",
                            "Sung Jinwoo",
                        ),
                    },
                )
                write_feed(
                    [
                        {
                            "href": "/decklists/sung-jinwoo/event-1.html",
                            "who": "Solo Leveling - Sung Jinwoo",
                            "meta": "1st",
                            "when": "2026-08-16",
                        }
                    ],
                    lastmod="2026-08-28",
                )
            xml = (root / "sitemap.xml").read_text(encoding="utf-8")
            feed = (root / "feed.xml").read_text(encoding="utf-8")
        self.assertIn("image:loc", xml)
        self.assertIn("uadb-hero.png", xml)
        self.assertIn("icon-512.png", xml)
        self.assertIn("UE17BT_SLG-1-022.png", xml)
        self.assertIn("<rss", feed)
        self.assertIn("Sung Jinwoo", feed)
        self.assertIn("/decklists/sung-jinwoo/event-1.html", feed)

    def test_format_page_has_visible_faq(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(generate_site.uadb, "ROOT", root), patch.object(uadb, "ROOT", root):
                write_format(
                    [
                        {
                            "page": "decklists/sung-jinwoo.html",
                            "full": "Solo Leveling - Sung Jinwoo",
                            "style": "Aggro",
                            "tier": "1",
                            "strengths": ["Public Standard list."],
                        }
                    ]
                )
            html = (root / "format.html").read_text(encoding="utf-8")
        self.assertIn("FAQPage", html)
        self.assertIn("How many cards are in a Union Arena deck?", html)
        self.assertIn("Exactly 50 cards", html)
        self.assertIn('id="faq"', html)


if __name__ == "__main__":
    unittest.main()
