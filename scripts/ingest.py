#!/usr/bin/env python3
"""Build Union Arena Deck Base from public sources.

Order: TCG Contender decks + cards, official Bandai cardlist, optional community
YouTube/web scrape, then HTML. Does not touch any OPTCG simulator.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.chdir(ROOT)


def main() -> None:
    import scrape_contender
    import scrape_official_cards
    import generate_site

    print("=== TCG Contender ===")
    scrape_contender.main()

    print("=== official Bandai cardlist ===")
    scrape_official_cards.main()
    scrape_contender.merge_card_caches()

    if "--community" in sys.argv:
        print("=== YouTube / public pages ===")
        import scrape_community

        scrape_community.main()

    print("=== HTML ===")
    generate_site.main()
    print("ingest done")


if __name__ == "__main__":
    main()
