# Union Arena Decklists

Static GitHub Pages site for **Union Arena** TCG 50-card lists.

Live domain: [unionarenadecklists.com](https://unionarenadecklists.com)

GitHub Pages must serve this branch (or merge to `main`). The old `Index.html` stub on `main` 404s because Linux Pages only picks up lowercase `index.html`.

## What it is

- Home splash, character grid, and recent lists (newest published first)
- One page per current-format character / title
- Consensus 50-card lists plus official top-placing lists and public YouTube lists
- Copy button pastes `NxSET/CODE` lines

## Data sources

- [TCG Contender Union Arena](https://tcgcontender.com/unionarena/meta): Standard archetypes and 50-card cores
- [Official Bandai cardlist](https://www.unionarena-tcg.com/na/cardlist/): names and pictures
- [Official top-placing decks](https://www.unionarena-tcg.com/na/decks/top-placing/): Bandai TCG Plus recipes
- YouTube: search, public video descriptions, and on-screen lists read from thumbnails and early video frames

## Rebuild

Python 3.12. YouTube screenshot lists also need `tesseract-ocr`, `ffmpeg`, `yt-dlp`, and `pillow`. Video-frame OCR uses the public thumbnail/still images always; early-video clips are used when YouTube allows the download (the weekly GitHub Action).

```bash
python3 scripts/ingest.py
```

Skip the YouTube / official-list pass:

```bash
python3 scripts/ingest.py --skip-community
```

Skip screenshot OCR only:

```bash
python3 scripts/ingest.py --skip-ocr
```

Or run the pieces:

```bash
python3 scripts/scrape_contender.py
python3 scripts/scrape_official_cards.py
python3 scripts/scrape_community.py
python3 scripts/generate_site.py
```

## Discord

The site ships Discord-style rooms plus a bot that mirrors them on the live server.

- Welcome, announcements, and title roles: [unionarenadecklists.com/discord/welcome.html](https://unionarenadecklists.com/discord/welcome.html)
- One discussion thread per anime or manga title (Yu Yu Hakusho, Solo Leveling, Evangelion, …)
- Roles use those same title names
- Each title thread posts the current consensus 50s from this site (`/discord/board.json`)

Invite: [discord.gg/aY9RfB662](https://discord.gg/aY9RfB662)

Run the bot after a site build (or against the live board):

```bash
pip install -r requirements-bot.txt
export DISCORD_TOKEN=...
python3 scripts/discord_bot.py --live
```

Slash commands: `/setup`, `/refresh`, `/consensus yyh`, `/themes`, `/roles`.

Dry-run a title without Discord:

```bash
python3 scripts/discord_bot.py --dump --theme yyh
python3 scripts/discord_bot.py --dump --theme "solo leveling"
```

`/setup` creates `#welcome`, `#announcements`, `#roles`, title roles, and one `#title-threads` thread per anime or manga. Each thread gets that title’s consensus 50s.

## Notes

Fan site, not affiliated with Bandai Namco.
