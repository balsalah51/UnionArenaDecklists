# Union Arena Deck Base

Static GitHub Pages site for **Union Arena** TCG 50-card lists. Same layout and averaging style as [One Piece Deck Base](https://onepiecedeckbase.com/) — no OPTCG simulator.

Live domain: [unionarenadecklists.com](https://unionarenadecklists.com)

## What it is

- Home splash, character grid, and recent lists
- One page per current-format character / title
- Consensus 50-card lists plus any public YouTube or web lists the scrape can parse
- Copy button pastes `NxSET/CODE` lines (not OP TCG SIM)

## Data sources

Different sites than the One Piece version:

- [TCG Contender Union Arena](https://tcgcontender.com/unionarena/meta) — Standard archetypes and 50-card cores
- [Official Bandai cardlist](https://www.unionarena-tcg.com/na/cardlist/) — names and pictures
- Public YouTube / web pages — only complete `NxUE##BT/...` text lists (optional)

## Rebuild

Python 3.12, stdlib only.

```bash
python3 scripts/ingest.py
```

Add community YouTube / public-page lists:

```bash
python3 scripts/ingest.py --community
```

Or run the pieces:

```bash
python3 scripts/scrape_contender.py
python3 scripts/scrape_official_cards.py
python3 scripts/generate_site.py
```

## Notes

Fan site, not affiliated with Bandai Namco.
