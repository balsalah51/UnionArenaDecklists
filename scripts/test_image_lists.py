#!/usr/bin/env python3
"""Photo-to-list conversion for public Union Arena deck screenshots."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import match_deck_photo  # noqa: E402
import scrape_image_lists  # noqa: E402
import scrape_youtube_ocr as ocr  # noqa: E402
import uadb  # noqa: E402


class ImageListTests(unittest.TestCase):
    def test_counts_from_messy_screenshot_text(self):
        cache = {
            "UE19BT/SMD-1-016": {"name": "Taro Sakamoto"},
            "UE19BT/SMD-1-022": {"name": "Shin Asakura"},
            "UE17BT/SLG-1-022": {"name": "Sung Jinwoo"},
            "UE17BT/SLG-1-030": {"name": "Shadow Soldiers"},
        }
        idx = ocr.compact_index(cache)
        text = """
        4x UE19BT/SMD-1-016 Taro
        3xUE19BT SMD-1-022 Shin
        4x SLG-1-022
        12x SLG-1-030 Shadow
        """
        counts = ocr.counts_from_ocr(text, cache, idx)
        self.assertEqual(counts.get("UE19BT/SMD-1-016"), 4)
        self.assertEqual(counts.get("UE19BT/SMD-1-022"), 3)
        self.assertEqual(counts.get("UE17BT/SLG-1-022"), 4)
        self.assertEqual(counts.get("UE17BT/SLG-1-030"), 12)

    def test_reddit_gallery_urls(self):
        post = {
            "url": "https://www.reddit.com/gallery/abc",
            "preview": {"images": [{"source": {"url": "https://preview.redd.it/one.jpg?width=1080&amp;s=abc"}}]},
            "media_metadata": {
                "x": {"s": {"u": "https://preview.redd.it/two.png?width=2000"}},
            },
            "url_overridden_by_dest": "https://i.redd.it/three.jpg",
        }
        urls = scrape_image_lists.reddit_image_urls(post)
        self.assertTrue(any("three.jpg" in u for u in urls))
        self.assertTrue(any("one.jpg" in u or "two.png" in u for u in urls))

    def test_nitter_media_rewrites_to_twimg(self):
        url = scrape_image_lists.clean_img_url("https://nitter.net/pic/orig/media%2FABC123.jpg")
        self.assertEqual(url, "https://pbs.twimg.com/media/ABC123.jpg")

    def test_reddit_atom_extracts_i_reddit_images(self):
        xml = """<feed><entry><title>My list for Esper sisters</title>
        <link href="https://www.reddit.com/r/Union_Arena_TCG/comments/abc/my_list/"/>
        <name>/u/Tester</name><updated>2026-08-20T00:00:00+00:00</updated>
        <content>https://i.redd.it/ew6beax21nlh1.png</content></entry></feed>"""
        jobs = scrape_image_lists.atom_jobs(xml)
        self.assertEqual(len(jobs), 1)
        self.assertIn("ew6beax21nlh1.png", jobs[0]["images"][0])
        self.assertEqual(jobs[0]["kind"], "reddit")

    def test_title_tokens_keep_character_words(self):
        tokens = match_deck_photo.title_tokens("My list for Esper sisters. This deck so fun")
        self.assertIn("esper", tokens)
        self.assertIn("sisters", tokens)
        self.assertNotIn("deck", tokens)
        self.assertNotIn("list", tokens)

    def test_card_num_and_set_code(self):
        self.assertEqual(match_deck_photo.card_num("UE06BT/OPM-1-027"), 27)
        self.assertEqual(match_deck_photo.set_code("UE06BT/OPM-1-027"), "OPM")
        self.assertFalse(match_deck_photo.playable("UE06BT/OPM-1-AP01"))

    def test_expand_window_keeps_nearby_events(self):
        cache = {
            "UE06BT/OPM-1-011": {"name": "Terrible Tornado"},
            "UE06BT/OPM-1-027": {"name": "Esper Sisters"},
            "UE06BT/OPM-1-031": {"name": "Psychic Power"},
            "UE06BT/OPM-1-062": {"name": "Saitama"},
            "UE17BT/SLG-1-022": {"name": "Sung Jinwoo"},
        }
        index = {cid: b"x" * 1024 for cid in cache}
        out = match_deck_photo.expand_from_hits(
            index, cache, ["UE06BT/OPM-1-011", "UE06BT/OPM-1-027"], "Esper sisters"
        )
        self.assertIn("UE06BT/OPM-1-031", out)
        self.assertIn("UE06BT/OPM-1-027", out)
        self.assertNotIn("UE17BT/SLG-1-022", out)
        self.assertNotIn("UE06BT/OPM-1-062", out)

    def test_fit_fifty_drops_low_score_copies(self):
        counts = {f"UE06BT/OPM-1-{i:03d}": 4 for i in range(1, 15)}
        scores = {cid: 0.6 for cid in counts}
        scores["UE06BT/OPM-1-014"] = 0.12
        scores["UE06BT/OPM-1-013"] = 0.15
        scores["UE06BT/OPM-1-012"] = 0.18
        fitted = match_deck_photo.fit_fifty(counts, scores)
        self.assertEqual(sum(fitted.values()), 50)

    def test_sale_titles_are_skipped(self):
        self.assertTrue(scrape_image_lists.SALE_HINT.search("WTB: 3 STARS AND SERIALS"))
        self.assertTrue(scrape_image_lists.SALE_HINT.search("HUGE Union Arena Selling"))
        self.assertFalse(scrape_image_lists.SALE_HINT.search("My list for Esper sisters"))

    def test_same_set_share(self):
        good = {"UE06BT/OPM-1-011": 4, "UE06BT/OPM-1-027": 4, "UE06ST/OPM-1-104": 4}
        mixed = {"UE06BT/OPM-1-011": 4, "UE19BT/SMD-1-016": 4, "UE17BT/SLG-1-022": 4}
        self.assertGreaterEqual(scrape_image_lists.set_share(good), 0.99)
        self.assertLess(scrape_image_lists.set_share(mixed), 0.5)

    def test_complete_list_window(self):
        counts = {f"UE19BT/SMD-1-{i:03d}": 4 for i in range(1, 11)}
        counts["UE19BT/SMD-1-011"] = 4
        counts["UE19BT/SMD-1-012"] = 2
        self.assertEqual(sum(counts.values()), 46)
        self.assertTrue(uadb.list_is_complete({**counts, "UE19BT/SMD-1-013": 4}))


if __name__ == "__main__":
    unittest.main()
