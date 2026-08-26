#!/usr/bin/env python3
"""URL builders for TCGplayer buy links."""

from __future__ import annotations

import uadb


def test_card_search() -> None:
    url = uadb.tcgplayer_card_search_url("UE17BT/SLG-1-022", "Sung Jinwoo")
    assert url.startswith("https://www.tcgplayer.com/search/union-arena/product?")
    assert "productLineName=union-arena" in url
    assert "Sung+Jinwoo" in url or "Sung%20Jinwoo" in url
    assert "UE17BT" in url
    assert "SLG-1-022" in url
    assert uadb.tcgplayer_card_search_url("UNRESOLVED") == ""
    numbered = uadb.tcgplayer_card_search_url("UE17BT/SLG-1-022", "Sung Jinwoo (022)")
    assert "Sung+Jinwoo" in numbered or "Sung%20Jinwoo" in numbered
    assert "022%29" not in numbered and "(022)" not in numbered
    cid_only = uadb.tcgplayer_card_search_url("UE17BT/SLG-1-022", "UE17BT/SLG-1-022")
    assert "UE17BT" in cid_only and "SLG-1-022" in cid_only


def test_mass_entry() -> None:
    items = [
        {"id": "UE17BT/SLG-1-022", "name": "Sung Jinwoo", "count": 4, "group": "Characters"},
        {"id": "UE17BT/SLG-1-038", "name": "Igris", "count": 4, "group": "Characters"},
        {"id": "UE17BT/SLG-1-001-AP", "name": "AP", "count": 1, "group": "AP cards"},
        {"id": "UNRESOLVED", "name": "x", "count": 2, "group": "Events"},
    ]
    cache = {
        "UE17BT/SLG-1-022": {"name": "Sung Jinwoo"},
        "UE17BT/SLG-1-038": {"name": "Igris"},
    }
    url = uadb.tcgplayer_mass_entry_url(items, cache)
    assert url.startswith("https://www.tcgplayer.com/massentry?")
    assert "productline=Union+Arena" in url or "productline=Union%20Arena" in url
    assert "4+Sung+Jinwoo+UE17BT+SLG-1-022" in url or "4%20Sung%20Jinwoo%20UE17BT%20SLG-1-022" in url
    assert "Igris" in url
    assert "AP" not in url
    assert "UNRESOLVED" not in url
    assert uadb.tcgplayer_mass_entry_url([], {}) == ""


def test_buttons() -> None:
    url = "https://www.tcgplayer.com/massentry?productline=Union+Arena&c=4+x"
    wrapped = uadb.tcgplayer_affiliate_url(url)
    assert wrapped.startswith("https://partner.tcgplayer.com/c/7670706/1780961/21018?")
    assert "u=" in wrapped
    assert "massentry" in wrapped
    assert uadb.tcgplayer_affiliate_url("") == ""
    assert uadb.tcgplayer_affiliate_url(wrapped) == wrapped
    html = uadb.buy_deck_button(url)
    assert 'class="buy-tcg buy-deck"' in html
    assert "partner.tcgplayer.com" in html
    assert 'rel="noopener sponsored"' in html
    assert 'target="_blank"' in html
    assert uadb.buy_deck_button("") == ""
    card = uadb.buy_card_link("https://www.tcgplayer.com/search/union-arena/product?q=x")
    assert 'class="buy-tcg buy-card"' in card
    assert "partner.tcgplayer.com" in card
    assert uadb.list_actions("", "") == ""
    assert "list-actions" in uadb.list_actions("a", "b")


if __name__ == "__main__":
    test_card_search()
    test_mass_entry()
    test_buttons()
    print("ok")
