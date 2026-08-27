#!/usr/bin/env python3
"""Tests for UA Arena Discord board grouping, aliases, and pages."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import discord_board  # noqa: E402
import discord_bot  # noqa: E402
import uadb  # noqa: E402


def sample_decks() -> list[dict]:
    return [
        {
            "key": "solo-leveling-sung-jinwoo",
            "name": "Sung Jinwoo",
            "full": "Solo Leveling - Sung Jinwoo",
            "title": "Solo Leveling",
            "page": "decklists/solo-leveling-sung-jinwoo.html",
            "dir": "decklists/solo-leveling-sung-jinwoo",
            "tier": "1",
            "style": "Midrange",
            "meta_share": 0.22,
            "color": "green",
            "img": "https://example.test/sjw.png",
            "consensus_slug": "contender-consensus",
            "consensus_kind": "contender",
            "consensus_date": "2026-08-23",
            "consensus_url": "decklists/solo-leveling-sung-jinwoo/contender-consensus.html",
            "cards": 50,
            "sim_text": "4xUE17BT/SLG-1-022\n4xUE17BT/SLG-1-030",
            "list_count": 2,
            "recent_lists": [
                {
                    "slug": "contender-consensus",
                    "kind": "contender",
                    "title": "Solo Leveling - Sung Jinwoo",
                    "date": "2026-08-23",
                    "href": "decklists/solo-leveling-sung-jinwoo/contender-consensus.html",
                }
            ],
            "lines": [
                {"count": 4, "id": "UE17BT/SLG-1-022", "name": "Sung Jinwoo (022)", "group": "Characters"},
                {"count": 4, "id": "UE17BT/SLG-1-030", "name": "Shadow Soldiers", "group": "Characters"},
            ],
        },
        {
            "key": "yu-yu-hakusho-youko-kurama",
            "name": "Youko Kurama",
            "full": "Yu Yu Hakusho - Youko Kurama",
            "title": "Yu Yu Hakusho",
            "page": "decklists/yu-yu-hakusho-youko-kurama.html",
            "dir": "decklists/yu-yu-hakusho-youko-kurama",
            "tier": "",
            "style": "",
            "meta_share": 0.0,
            "color": "red",
            "img": "",
            "consensus_slug": "event-1st-yu-yu-hakusho-youko-kurama-1471428",
            "consensus_kind": "event",
            "consensus_date": "2026-08-16",
            "consensus_url": "decklists/yu-yu-hakusho-youko-kurama/event-1st-yu-yu-hakusho-youko-kurama-1471428.html",
            "cards": 50,
            "sim_text": "4xUE08BT/YYH-1-001",
            "list_count": 1,
            "recent_lists": [],
            "lines": [
                {"count": 4, "id": "UE08BT/YYH-1-001", "name": "Youko Kurama", "group": "Characters"},
            ],
        },
        {
            "key": "csm-denji",
            "name": "Denji",
            "full": "Chainsaw Man - Denji",
            "title": "CSM",
            "page": "decklists/csm-denji.html",
            "dir": "decklists/csm-denji",
            "tier": "2",
            "style": "Aggro",
            "meta_share": 0.08,
            "color": "red",
            "img": "",
            "consensus_slug": "contender-consensus",
            "consensus_kind": "contender",
            "consensus_date": "2026-08-23",
            "consensus_url": "decklists/csm-denji/contender-consensus.html",
            "cards": 50,
            "sim_text": "4xUE22BT/CSM-1-051",
            "list_count": 1,
            "recent_lists": [],
            "lines": [
                {"count": 4, "id": "UE22BT/CSM-1-051", "name": "Denji", "group": "Characters"},
            ],
        },
    ]


def test_aliases_and_grouping() -> None:
    board = discord_board.build_board(sample_decks(), updated="2026-08-25")
    slugs = {t["slug"]: t for t in board["themes"]}
    assert "solo-leveling" in slugs
    assert "yu-yu-hakusho" in slugs
    assert slugs["chainsaw-man"]["name"] == "Chainsaw Man"
    assert discord_board.resolve_theme("yyh", board["themes"])["slug"] == "yu-yu-hakusho"
    assert discord_board.resolve_theme("solo leveling", board["themes"])["slug"] == "solo-leveling"
    assert discord_board.resolve_theme("SLG", board["themes"])["slug"] == "solo-leveling"
    assert discord_board.resolve_theme("csm", board["themes"])["slug"] == "chainsaw-man"
    assert discord_board.theme_slug("IYS") == "inuyasha"
    assert discord_board.is_real_theme("OPM,BCV,KJ8,HTR", "opm-bcv-kj8-htr") is False
    assert board["theme_count"] == 3
    assert board["deck_count"] == 3
    junk = sample_decks() + [
        {
            "key": "riza-hawkeye",
            "name": "Riza Hawkeye",
            "title": "",
            "full": "Riza Hawkeye",
            "meta_share": 0,
        },
        {
            "key": "csm-purple",
            "name": "Purple",
            "title": "Chainsaw Man",
            "full": "Chainsaw Man - Purple",
            "meta_share": 0,
        },
    ]
    cleaned = discord_board.build_board(junk, updated="2026-08-25")
    assert "riza-hawkeye" not in {t["slug"] for t in cleaned["themes"]}
    csm = next(t for t in cleaned["themes"] if t["slug"] == "chainsaw-man")
    assert all(d["key"] != "csm-purple" for d in csm["decks"])


def test_consensus_messages() -> None:
    board = discord_board.build_board(sample_decks(), updated="2026-08-25")
    yyh = discord_board.resolve_theme("yyh", board["themes"])
    deck = yyh["decks"][0]
    text = discord_board.format_consensus_text(deck)
    assert "Youko Kurama" in text
    assert "4x `UE08BT/YYH-1-001`" in text
    assert "ua-deck:yu-yu-hakusho-youko-kurama" in text
    assert "unionarenadecklists.com/decklists/yu-yu-hakusho-youko-kurama/" in text
    embed = discord_board.format_consensus_embed(deck)
    assert embed["footer"]["text"] == "ua-deck:yu-yu-hakusho-youko-kurama"
    assert embed["fields"]
    welcome = discord_board.format_welcome_text(board)
    assert "#announcements" in welcome
    assert "Yu Yu Hakusho" in welcome
    assert "#roles" in welcome
    roles_text = discord_board.format_roles_text(board)
    assert "flair" in roles_text.lower()
    assert "menu" in roles_text.lower()
    dump = discord_board.dump_theme(board, "yyh")
    assert "Yu Yu Hakusho" in dump
    assert "Sung Jinwoo" not in dump
    roles = {r["name"] for r in discord_board.title_roles(board)}
    assert roles == {"Solo Leveling", "Yu Yu Hakusho", "Chainsaw Man"}


def test_pages_and_fetch(tmp_path: Path | None = None) -> None:
    board = discord_board.build_board(sample_decks(), updated="2026-08-25")
    dest = Path(tmp_path) if tmp_path else Path(tempfile.mkdtemp())
    paths = discord_board.write_pages(board, dest)
    welcome = (dest / "welcome.html").read_text()
    assert "Welcome to UA Arena" in welcome or "Welcome to the list hall" in welcome
    assert "announcements" in welcome
    assert "Solo Leveling" in welcome
    assert "Title roles" in welcome
    assert "Color flair" not in welcome
    assert "Join Discord" in welcome
    announce = (dest / "announcements.html").read_text()
    assert "Restricted in constructed" in announce
    assert "UE15BT/EVA-1-051" in announce
    theme = (dest / "yu-yu-hakusho.html").read_text()
    assert "Youko Kurama" in theme
    assert "UE08BT/YYH-1-001" in theme
    assert "Yu Yu Hakusho thread" in theme
    assert "aliases" in theme and "yyh" in theme
    roles_page = (dest / "roles.html").read_text()
    assert "Solo Leveling" in roles_page
    assert "Yu Yu Hakusho" in roles_page
    assert "one role per anime" in roles_page.lower() or "One role per anime" in roles_page
    thread = (dest / "threads" / "yu-yu-hakusho-youko-kurama.html").read_text()
    assert "yu-yu-hakusho.html#yu-yu-hakusho-youko-kurama" in thread
    data = json.loads((dest / "board.json").read_text())
    assert data["themes"]
    assert {r["name"] for r in data["roles"]} == {"Solo Leveling", "Yu Yu Hakusho", "Chainsaw Man"}
    loaded = discord_board.fetch_board(str(dest / "board.json"))
    assert loaded["deck_count"] == 3
    assert "discord/welcome.html" in paths
    assert 'data-filterable' in (dest / "welcome.html").read_text()
    assert "yyh" in (dest / "welcome.html").read_text()
    assert discord_bot.channel_name("Solo Leveling") == "solo-leveling"
    assert discord_bot._markers_in_text("hello `ua-welcome`") == ["ua-welcome"]
    assert discord_bot._markers_in_text("ua-deck:yu-yu-hakusho-youko-kurama") == [
        "ua-deck:yu-yu-hakusho-youko-kurama"
    ]


def test_deck_record() -> None:
    arch = {
        "key": "solo-leveling-sung-jinwoo",
        "name": "Sung Jinwoo",
        "full": "Solo Leveling - Sung Jinwoo",
        "title": "Solo Leveling",
        "page": "decklists/solo-leveling-sung-jinwoo.html",
        "dir": "decklists/solo-leveling-sung-jinwoo",
        "tier": "1",
        "style": "Midrange",
        "meta_share": 0.2,
        "color": "green",
        "updated": "2026-08-23",
    }
    items = [
        {"count": 4, "id": "UE17BT/SLG-1-022", "name": "Sung Jinwoo (022)", "group": "Characters"},
        {"count": 1, "id": "UE17BT/SLG-1-001-AP", "name": "AP", "group": "AP cards"},
    ]
    cache = {"UE17BT/SLG-1-022": {"name": "Sung Jinwoo (022)"}}
    lists = [{"slug": "contender-consensus", "kind": "contender", "title": arch["full"], "date": "2026-08-23"}]
    row = discord_board.deck_record(arch, items, cache, {"id": "UE17BT/SLG-1-022", "meta": {"color": "green"}}, lists)
    assert row["cards"] == 4
    assert row["consensus_url"].endswith("contender-consensus.html")
    assert len(row["lines"]) == 1


if __name__ == "__main__":
    test_aliases_and_grouping()
    test_consensus_messages()
    test_pages_and_fetch()
    test_deck_record()
    print("ok")
