# Union Arena Deck Base

Static GitHub Pages site for **Union Arena** TCG 50-card lists. Same layout and averaging style as [One Piece Deck Base](https://onepiecedeckbase.com/) — no OPTCG simulator.

Live domain: [unionarenadecklists.com](https://unionarenadecklists.com)

GitHub Pages must serve this branch (or merge to `main`). The old `Index.html` stub on `main` 404s because Linux Pages only picks up lowercase `index.html`.

## What it is

- Home splash, character grid, and recent lists
- One page per current-format character / title
- Consensus 50-card lists plus official top-placing lists and public YouTube descriptions
- Copy button pastes `NxSET/CODE` lines (not OP TCG SIM)

## Data sources

Different sites than the One Piece version:

- [TCG Contender Union Arena](https://tcgcontender.com/unionarena/meta) — Standard archetypes and 50-card cores
- [Official Bandai cardlist](https://www.unionarena-tcg.com/na/cardlist/) — names and pictures
- [Official top-placing decks](https://www.unionarena-tcg.com/na/decks/top-placing/) — Bandai TCG Plus recipes
- YouTube — search + public video descriptions (only complete text lists)

## Rebuild

Python 3.12, stdlib only.

```bash
python3 scripts/ingest.py
```

Skip the YouTube / official-list pass:

```bash
python3 scripts/ingest.py --skip-community
```

Or run the pieces:

```bash
python3 scripts/scrape_contender.py
python3 scripts/scrape_official_cards.py
python3 scripts/scrape_community.py
python3 scripts/generate_site.py
```

## Notes

Fan site, not affiliated with Bandai Namco.
