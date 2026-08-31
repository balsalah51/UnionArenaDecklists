#!/usr/bin/env python3
"""UA Arena Discord board: welcome, announcements, and per-title deck threads."""

from __future__ import annotations

import html
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import uadb  # noqa: E402

BOARD_PATH = "discord/board.json"
MARKER_PREFIX = "ua-deck:"
EMBED_DESC = 4096
FIELD_VALUE = 1024
MESSAGE_LIMIT = 2000

THEME_ALIASES = {
    "yyh": "yu-yu-hakusho",
    "yuyu": "yu-yu-hakusho",
    "yuyuhakusho": "yu-yu-hakusho",
    "yu yu hakusho": "yu-yu-hakusho",
    "solo": "solo-leveling",
    "sl": "solo-leveling",
    "slg": "solo-leveling",
    "sololeveling": "solo-leveling",
    "csm": "chainsaw-man",
    "chainsaw": "chainsaw-man",
    "hxh": "hunter-x-hunter",
    "htr": "hunter-x-hunter",
    "hunter": "hunter-x-hunter",
    "eva": "evangelion",
    "nge": "evangelion",
    "jjk": "jujutsu-kaisen",
    "jujutsu": "jujutsu-kaisen",
    "smd": "sakamoto-days",
    "sakamoto": "sakamoto-days",
    "slime": "that-time-i-got-reincarnated-as-a-slime",
    "tsk": "that-time-i-got-reincarnated-as-a-slime",
    "tensura": "that-time-i-got-reincarnated-as-a-slime",
    "iys": "inuyasha",
    "inuyasha": "inuyasha",
    "aot": "attack-on-titan",
    "snk": "attack-on-titan",
    "fma": "fullmetal-alchemist",
    "fullmetal": "fullmetal-alchemist",
    "bc": "black-clover",
    "bcv": "black-clover",
    "opm": "one-punch-man",
    "tg": "tokyo-ghoul",
    "sao": "sword-art-online",
    "rnk": "rurouni-kenshin",
    "kenshin": "rurouni-kenshin",
    "rk": "rurouni-kenshin",
    "geass": "code-geass",
    "ds": "demon-slayer",
    "kmy": "demon-slayer",
    "kagura": "kagurabachi",
    "100gf": "the-100-girlfriends",
    "100girlfriends": "the-100-girlfriends",
    "kj8": "kaiju-no-8",
    "kaiju": "kaiju-no-8",
}

COLOR_ONLY = {"purple", "red", "yellow", "green", "blue", "black"}
COLOR_INT = {
    "red": 0xD32F2F,
    "green": 0x2E7D32,
    "blue": 0x1565C0,
    "purple": 0x6A1B9A,
    "yellow": 0xF9A825,
    "black": 0x212121,
}

MASH_TITLE = re.compile(
    r"(?i)\b(opm|bcv|kj8|htr|csm|slg|yyh|iys)\b.+\b(opm|bcv|kj8|htr|csm|slg|yyh|iys)\b"
)


def norm_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def is_real_theme(title: str, slug: str = "") -> bool:
    if not (title or "").strip():
        return False
    blob = f"{title or ''} {slug or ''}".replace(",", " ").replace("-", " ")
    if MASH_TITLE.search(blob):
        return False
    if blob.count(",") >= 2 and len(blob) < 48:
        return False
    return True


def theme_slug(title: str) -> str:
    pretty = uadb.pretty_anime(title or "") or (title or "")
    slug = uadb.slugify(pretty)
    mapped = THEME_ALIASES.get(pretty.lower().strip()) or THEME_ALIASES.get(slug)
    return mapped or slug or "title"


def aliases_for(slug: str, name: str = "") -> list[str]:
    extras = [alias for alias, target in THEME_ALIASES.items() if target == slug]
    extras.extend([slug, uadb.slugify(name), name.lower().strip()])
    out = []
    seen = set()
    for item in extras:
        item = (item or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def resolve_theme(query: str, themes: list[dict]) -> dict | None:
    raw = (query or "").strip()
    if not raw:
        return None
    slug = THEME_ALIASES.get(raw.lower()) or THEME_ALIASES.get(uadb.slugify(raw)) or uadb.slugify(raw)
    compact = norm_key(raw)
    for theme in themes:
        hay = {theme.get("slug") or "", uadb.slugify(theme.get("name") or "")}
        hay.update(theme.get("aliases") or [])
        if raw.lower() in {h.lower() for h in hay if h}:
            return theme
        if slug and slug == theme.get("slug"):
            return theme
        if compact and compact == norm_key(theme.get("name") or ""):
            return theme
        if compact and compact in norm_key(theme.get("name") or ""):
            return theme
    return None


def deck_record(arch: dict, items: list[dict], cache: dict, feature: dict, lists: list[dict]) -> dict:
    cons = next((row for row in lists if row.get("kind") == "contender"), None)
    if not cons and lists:
        cons = lists[0]
    lines = []
    for item in items:
        if item.get("group") == "AP cards":
            continue
        cid = item.get("id") or ""
        meta = cache.get(cid) or {}
        lines.append(
            {
                "count": int(item.get("count") or 0),
                "id": cid,
                "name": uadb.display_name(meta.get("name") or item.get("name") or cid),
                "group": item.get("group") or "Characters",
            }
        )
    slug = (cons or {}).get("slug") or ""
    cards = sum(row["count"] for row in lines)
    recent = []
    for row in lists[:8]:
        recent.append(
            {
                "slug": row.get("slug") or "",
                "kind": row.get("kind") or "",
                "title": row.get("title") or arch.get("full") or "",
                "date": row.get("date") or "",
                "href": f"{arch['dir']}/{row['slug']}.html" if row.get("slug") else arch.get("page") or "",
            }
        )
    return {
        "key": arch.get("key") or "",
        "name": arch.get("name") or "",
        "full": arch.get("full") or arch.get("name") or "",
        "title": uadb.pretty_anime(arch.get("title") or "") or arch.get("title") or "",
        "page": arch.get("page") or "",
        "dir": arch.get("dir") or "",
        "tier": str(arch.get("tier") or ""),
        "style": arch.get("style") or "",
        "meta_share": float(arch.get("meta_share") or 0),
        "color": (arch.get("color") or (feature.get("meta") or {}).get("color") or ""),
        "img": uadb.card_image_url(feature.get("id") or "", cache) if feature.get("id") else "",
        "updated": arch.get("updated") or "",
        "consensus_slug": slug,
        "consensus_kind": (cons or {}).get("kind") or "",
        "consensus_date": (cons or {}).get("date") or arch.get("updated") or "",
        "consensus_url": f"{arch['dir']}/{slug}.html" if slug else (arch.get("page") or ""),
        "lines": lines,
        "sim_text": "\n".join(f"{row['count']}x{row['id']}" for row in lines if row.get("id")),
        "cards": cards,
        "list_count": len(lists),
        "recent_lists": recent,
    }


def build_announcements(decks: list[dict], updated: str = "") -> list[dict]:
    stamp = updated or date.today().isoformat()
    ranked = [row for row in decks if row.get("meta_share")]
    ranked.sort(key=lambda row: (-float(row.get("meta_share") or 0), row.get("full") or ""))
    leaders = ", ".join(row["full"] for row in ranked[:4]) or "the public Standard snapshot"
    restricted = ", ".join(uadb.RESTRICTED_CARDS)
    return [
        {
            "id": "format-pulse",
            "title": "Format pulse",
            "date": stamp,
            "body": (
                f"English events are single-title Standard: 50 cards, usually one IP. "
                f"Names showing up most on public lists right now: {leaders}."
            ),
        },
        {
            "id": "restricted",
            "title": "Restricted in constructed",
            "date": "2026-04-17",
            "body": (
                f"Bandai limited {restricted} to one copy each. "
                "This site flags lists that still play more than one."
            ),
        },
        {
            "id": "how-lists-land",
            "title": "How lists land here",
            "date": stamp,
            "body": (
                "Consensus 50s come from TCG Contender Standard snapshots. "
                "Official top-placing recipes and public YouTube lists sit next to them. "
                "The board refreshes with the weekly site ingest."
            ),
        },
        {
            "id": "share-a-50",
            "title": "Share a 50",
            "date": stamp,
            "body": (
                "Paste `NxSET/CODE` lines in the matching anime or manga thread. "
                "Copy on any list page dumps that format. "
                "One thread per title: Solo Leveling, Yu Yu Hakusho, Evangelion, and the rest."
            ),
        },
    ]


def build_board(decks: list[dict], updated: str = "") -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for deck in decks:
        if not deck.get("key"):
            continue
        if (deck.get("name") or "").strip().lower() in COLOR_ONLY:
            continue
        title = (deck.get("title") or "").strip()
        if not title:
            continue
        slug = theme_slug(title)
        if not is_real_theme(title, slug):
            continue
        grouped[slug].append(deck)
    themes = []
    for slug, rows in grouped.items():
        rows = sorted(rows, key=lambda row: (-float(row.get("meta_share") or 0), row.get("name") or ""))
        name = uadb.pretty_anime(rows[0].get("title") or "") or rows[0].get("title") or slug
        themes.append(
            {
                "slug": slug,
                "name": name,
                "aliases": aliases_for(slug, name),
                "deck_count": len(rows),
                "meta_share": sum(float(row.get("meta_share") or 0) for row in rows),
                "color": next((row.get("color") for row in rows if row.get("color")), ""),
                "img": next((row.get("img") for row in rows if row.get("img")), ""),
                "decks": rows,
            }
        )
    themes.sort(key=lambda row: (-float(row.get("meta_share") or 0), row.get("name") or ""))
    stamp = updated or date.today().isoformat()
    return {
        "updated": stamp,
        "site": uadb.SITE,
        "discord_invite": uadb.DISCORD,
        "welcome": {
            "title": "Welcome to UA Arena",
            "kicker": "Union Arena lists, titles, and table talk",
        },
        "announcements": build_announcements(decks, stamp),
        "themes": themes,
        "deck_count": sum(len(row.get("decks") or []) for row in themes),
        "theme_count": len(themes),
        "roles": title_roles_from(themes),
    }


def list_count_label(n) -> str:
    n = int(n or 0)
    return "1 list" if n == 1 else f"{n} lists"


def title_roles_from(themes: list[dict]) -> list[dict]:
    roles = []
    for theme in themes:
        roles.append(
            {
                "name": theme.get("name") or theme.get("slug") or "Title",
                "slug": theme.get("slug") or "",
                "color": theme.get("color") or "",
                "color_class": uadb.color_class(theme.get("color") or ""),
                "deck_count": int(theme.get("deck_count") or 0),
                "href": f"/discord/{theme.get('slug') or 'title'}.html",
            }
        )
    return roles


def title_roles(board: dict) -> list[dict]:
    return list(board.get("roles") or title_roles_from(board.get("themes") or []))


def list_kind_label(kind: str) -> str:
    if kind == "contender":
        return "Consensus 50"
    if kind == "official":
        return "Official top placing"
    if kind == "event":
        return "Event list"
    if kind:
        return kind.replace("-", " ").title()
    return "Public 50"


def consensus_header(deck: dict) -> str:
    bits = [deck.get("full") or deck.get("name") or "Deck"]
    bits.append(list_kind_label(deck.get("consensus_kind") or ""))
    if deck.get("consensus_date"):
        bits.append(deck["consensus_date"])
    if deck.get("tier"):
        bits.append(f"Tier {deck['tier']}")
    if deck.get("style"):
        bits.append(deck["style"])
    cards = int(deck.get("cards") or 0)
    if cards:
        bits.append(f"{cards}/50")
    return " · ".join(bits)


def grouped_card_lines(deck: dict) -> list[tuple[str, list[str]]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    order = ["Characters", "Events", "Sites"]
    for card in deck.get("lines") or []:
        group = card.get("group") or "Characters"
        grouped[group].append(f"{card.get('count') or 0}x `{card.get('id') or ''}` {card.get('name') or ''}".strip())
        if group not in order:
            order.append(group)
    return [(group, grouped[group]) for group in order if grouped.get(group)]


def absolute_url(path: str, site: str | None = None) -> str:
    base = (site or uadb.SITE).rstrip("/")
    rel = (path or "").lstrip("/")
    return f"{base}/{rel}" if rel else base


def format_consensus_text(deck: dict, site: str | None = None) -> str:
    url = absolute_url(deck.get("consensus_url") or deck.get("page") or "", site)
    chunks = [f"**{consensus_header(deck)}**", url, ""]
    for group, lines in grouped_card_lines(deck):
        chunks.append(f"**{group}**")
        chunks.extend(lines)
        chunks.append("")
    chunks.append(f"`{MARKER_PREFIX}{deck.get('key') or ''}`")
    return "\n".join(chunks).strip()


def _split_values(lines: list[str], limit: int) -> list[str]:
    out: list[str] = []
    buf: list[str] = []
    size = 0
    for line in lines:
        extra = len(line) + (1 if buf else 0)
        if buf and size + extra > limit:
            out.append("\n".join(buf))
            buf = [line]
            size = len(line)
        else:
            buf.append(line)
            size += extra
    if buf:
        out.append("\n".join(buf))
    return out


def format_consensus_embed(deck: dict, site: str | None = None) -> dict:
    url = absolute_url(deck.get("consensus_url") or deck.get("page") or "", site)
    color_name = (deck.get("color") or "").split(";")[0].split("/")[0].strip().lower()
    fields = []
    description_parts = []
    for group, lines in grouped_card_lines(deck):
        chunks = _split_values(lines, FIELD_VALUE)
        if len(chunks) == 1 and len(chunks[0]) <= FIELD_VALUE:
            fields.append({"name": group, "value": chunks[0], "inline": False})
        else:
            for i, chunk in enumerate(chunks, start=1):
                label = group if i == 1 else f"{group} ({i})"
                fields.append({"name": label, "value": chunk, "inline": False})
    desc = f"{list_kind_label(deck.get('consensus_kind') or '')} from unionarenadecklists.com"
    if deck.get("consensus_date"):
        desc += f" · {deck['consensus_date']}"
    if deck.get("style") or deck.get("tier"):
        extra = " · ".join(bit for bit in (deck.get("style"), f"Tier {deck['tier']}" if deck.get("tier") else "") if bit)
        if extra:
            desc += f"\n{extra}"
    description_parts.append(desc)
    description = "\n".join(description_parts)[:EMBED_DESC]
    return {
        "title": deck.get("full") or deck.get("name") or "Deck",
        "url": url,
        "description": description,
        "color": COLOR_INT.get(color_name, 0x5865F2),
        "thumbnail": {"url": deck["img"]} if deck.get("img") else None,
        "fields": fields[:25],
        "footer": {"text": f"{MARKER_PREFIX}{deck.get('key') or ''}"},
    }


def format_welcome_text(board: dict) -> str:
    themes = ", ".join((t.get("name") or t.get("slug") or "") for t in board.get("themes") or [])
    return (
        f"**Welcome to UA Arena**\n"
        f"Union Arena Standard lists, title talk, and 50-card cores.\n\n"
        f"**Start here**\n"
        f"• Read #announcements for format notes and restricted cards\n"
        f"• Grab a title role in #roles (Solo Leveling, Yu Yu Hakusho, …)\n"
        f"• Open that title’s thread and talk the 50\n"
        f"• Consensus lists are pulled from {uadb.SITE}\n\n"
        f"**Title threads**\n{themes}\n\n"
        f"Be decent. No spoiler dumps without tags. Keep lists in `NxSET/CODE`.\n"
        f"Invite: {board.get('discord_invite') or uadb.DISCORD}"
    )


def format_announcements_text(board: dict) -> str:
    lines = ["**UA Arena announcements**", ""]
    for note in board.get("announcements") or []:
        when = note.get("date") or ""
        title = note.get("title") or "Update"
        lines.append(f"**{title}**" + (f" · {when}" if when else ""))
        lines.append(note.get("body") or "")
        lines.append("")
    return "\n".join(lines).strip()


def format_roles_text(board: dict) -> str:
    lines = [
        "**Title roles**",
        "Pick the anime or manga you sleeve. One role per IP, same names as the title threads.",
        "",
    ]
    for role in title_roles(board):
        lines.append(f"• **{role['name']}** — {list_count_label(role['deck_count'])} · #{role['slug']}")
    return "\n".join(lines).strip()


def format_theme_intro(theme: dict, board: dict | None = None) -> str:
    site = (board or {}).get("site") or uadb.SITE
    names = ", ".join(d.get("name") or d.get("key") or "" for d in (theme.get("decks") or []))
    return (
        f"**{theme.get('name') or theme.get('slug')}** title thread\n"
        f"{int(theme.get('deck_count') or 0)} public 50s in this IP. "
        f"Role: {theme.get('name')}. Lists from {site}.\n"
        f"{names}\n"
        f"`ua-theme:{theme.get('slug') or ''}`"
    )


def dump_theme(board: dict, query: str | None = None) -> str:
    themes = board.get("themes") or []
    if query:
        theme = resolve_theme(query, themes)
        if not theme:
            return f"No theme matched {query!r}."
        themes = [theme]
    blocks = []
    for theme in themes:
        blocks.append(f"# {theme['name']}  ({theme['slug']})")
        for deck in theme.get("decks") or []:
            blocks.append(format_consensus_text(deck, board.get("site")))
            blocks.append("")
    return "\n".join(blocks).strip()


def fetch_board(source: str | None = None, prefer: str = "local") -> dict:
    local = uadb.ROOT / BOARD_PATH

    def from_url(url: str) -> dict:
        status, body = uadb.fetch(url)
        if status != 200:
            raise RuntimeError(f"board fetch failed ({status}) {url}")
        return json.loads(body)

    if source:
        if source.startswith("http://") or source.startswith("https://"):
            return from_url(source)
        path = Path(source)
        if not path.is_absolute():
            path = uadb.ROOT / path
        return json.loads(path.read_text())
    live_url = f"{uadb.SITE}/discord/board.json"
    if prefer == "live":
        try:
            return from_url(live_url)
        except Exception:
            if local.exists():
                return json.loads(local.read_text())
            raise
    if local.exists():
        return json.loads(local.read_text())
    return from_url(live_url)


def _channel_link(href: str, label: str, kind: str, current: str, extra: str = "", filterable: bool = False) -> str:
    active = " is-active" if current == kind else ""
    filt = " data-filterable" if filterable else ""
    return (
        f'<a class="discord-channel{active}" href="{html.escape(href)}" data-channel="{html.escape(extra or label)}"{filt}>'
        f'<span class="discord-hash">#</span>{html.escape(label)}</a>'
    )


def render_sidebar(board: dict, current: str) -> str:
    theme_links = []
    for theme in board.get("themes") or []:
        extra = " ".join(
            [theme.get("slug") or "", theme.get("name") or "", *(theme.get("aliases") or [])]
        )
        active = " is-active" if current == f"theme:{theme['slug']}" else ""
        theme_links.append(
            f'<a class="discord-channel discord-thread-link{active}" href="/discord/{html.escape(theme["slug"])}.html" '
            f'data-channel="{html.escape(extra)}" data-filterable>'
            f'<span class="discord-thread-icon" aria-hidden="true">#</span>'
            f'{html.escape(theme.get("name") or theme["slug"])}</a>'
        )
    return f"""        <aside class="discord-sidebar" aria-label="Server channels">
          <div class="discord-server">
            <div class="discord-server-mark">UA</div>
            <div>
              <div class="discord-server-name">UA Arena</div>
              <div class="discord-server-note">Union Arena Standard</div>
            </div>
          </div>
          <label class="discord-search">
            <span class="visually-hidden">Filter channels</span>
            <input type="search" data-discord-filter placeholder="Find a title" />
          </label>
          <div class="discord-cat">Information</div>
          {_channel_link("/discord/welcome.html", "welcome", "welcome", current, "welcome start here")}
          {_channel_link("/discord/announcements.html", "announcements", "announcements", current, "announcements format restricted")}
          {_channel_link("/discord/roles.html", "roles", "roles", current, "roles titles anime manga")}
          <div class="discord-cat">Title threads</div>
          {chr(10).join(theme_links)}
        </aside>"""


def discord_chrome(title: str, description: str, board: dict, current: str, body: str, path: str = "") -> str:
    rel = path or "discord/welcome.html"
    crumbs = [("/", "Home"), ("/discord/welcome.html", "Discord")]
    if rel.rstrip("/") not in {"discord", "discord/welcome.html"}:
        crumbs.append((f"/{rel.lstrip('/')}", title.split("|")[0].strip()))
    ld = [uadb.website_ld(), uadb.breadcrumb_ld(crumbs)]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
{uadb.seo_head(title, description, rel, json_ld=ld)}{uadb.FONT_LINKS}  <link rel="stylesheet" href="/css/site.css?v={uadb.CSS_VER}" />
</head>
<body class="discord-app">
  {uadb.skip_link()}
  <div class="wrap discord-wrap">
{uadb.events_bar_html()}
    <header>
      <a class="brand" href="/">
        {uadb.logo_html()}
        <div class="brand-copy">
          {uadb.brand_heading()}
          <div class="subtitle">{html.escape(uadb.SUBTITLE)}</div>
        </div>
      </a>
{uadb.nav_html("discord")}
    </header>
    <div class="discord-shell">
{render_sidebar(board, current)}
      <div class="discord-main" id="main">
{body}
      </div>
    </div>
    <footer>
{uadb.footer_links()}
    </footer>
  </div>
  <script>
    document.getElementById('year').textContent = new Date().getFullYear();
  </script>
  <script src="/js/site.js?v={uadb.JS_VER}"></script>
  <script src="/js/discord.js?v={uadb.JS_VER}"></script>
</body>
</html>
"""


def _bot_chip() -> str:
    return '<span class="discord-bot-tag">BOT</span>'


def _message(author: str, when: str, body: str, extra_class: str = "", msg_id: str = "") -> str:
    id_attr = f' id="{html.escape(msg_id)}"' if msg_id else ""
    return f"""          <article class="discord-msg {html.escape(extra_class)}"{id_attr}>
            <div class="discord-avatar" aria-hidden="true">UA</div>
            <div class="discord-msg-body">
              <div class="discord-msg-head">
                <span class="discord-author">{html.escape(author)}</span>
                {_bot_chip()}
                <time>{html.escape(when)}</time>
              </div>
              <div class="discord-msg-text">{body}</div>
            </div>
          </article>"""


def write_welcome(board: dict, dest: Path) -> None:
    updated = html.escape(board.get("updated") or "")
    invite = html.escape(board.get("discord_invite") or uadb.DISCORD)
    theme_pills = []
    for theme in board.get("themes") or []:
        theme_pills.append(
            f'<a class="discord-pill" href="/discord/{html.escape(theme["slug"])}.html">'
            f'{html.escape(theme.get("name") or theme["slug"])} <span>{theme["deck_count"]}</span></a>'
        )
    roles = "".join(
        f'<li><a class="discord-role {html.escape(role["color_class"])}" href="{html.escape(role["href"])}">'
        f'{html.escape(role["name"])}</a></li>'
        for role in title_roles(board)
    )
    body = f"""        <div class="discord-head">
          <div class="discord-head-hash">#</div>
          <div>
            <h2>welcome</h2>
            <p>Start here. Grab a title role, then hop that anime or manga thread.</p>
          </div>
          <a class="discord-join" href="{invite}" target="_blank" rel="noopener">Join Discord</a>
        </div>
        <div class="discord-banner">
          <div class="discord-banner-kicker">UA Arena</div>
          <h3>Welcome to the list hall</h3>
          <p>Same 50-card cores as the website, split into Discord-style rooms: welcome, announcements, roles, then one discussion thread per anime or manga title.</p>
        </div>
        <div class="discord-feed">
{_message("UA Arena Bot", updated, f"""              <p><strong>Welcome to UA Arena.</strong> This board mirrors the live Discord rooms and the consensus 50s on <a href="{html.escape(uadb.SITE)}">{html.escape(uadb.SITE.replace("https://", ""))}</a>.</p>
              <ol class="discord-rules">
                <li>Be decent. Argue the list, not the person.</li>
                <li>English events are single-title Standard. Say the IP if you mix for casual.</li>
                <li>Paste lists as <code>NxSET/CODE</code>. Copy on any deck page dumps that format.</li>
                <li>Spoilers get a tag. Tournament tells wait until the round is over.</li>
                <li>Keep each 50 in its title thread so the next player can find it.</li>
              </ol>""", "is-pin")}
{_message("UA Arena Bot", updated, f"""              <p><strong>Channel map</strong></p>
              <ul class="discord-map">
                <li><a href="/discord/welcome.html">#welcome</a> — you are here</li>
                <li><a href="/discord/announcements.html">#announcements</a> — format, restricted cards, refresh notes</li>
                <li><a href="/discord/roles.html">#roles</a> — one role per anime or manga title</li>
                <li>Title threads such as <a href="/discord/solo-leveling.html">Solo Leveling</a> and <a href="/discord/yu-yu-hakusho.html">Yu Yu Hakusho</a></li>
              </ul>
              <div class="discord-pills">{"".join(theme_pills)}</div>""")}
{_message("UA Arena Bot", updated, f"""              <p><strong>Title roles</strong> match the threads. Grab the IP you sleeve.</p>
              <ul class="discord-roles">{roles}</ul>
              <p class="discord-muted">{board.get("theme_count") or 0} titles · {board.get("deck_count") or 0} lists · updated {updated}</p>
              <p><a class="discord-join discord-join-inline" href="{invite}" target="_blank" rel="noopener">Open the live server</a></p>""")}
        </div>"""
    page = discord_chrome(
        "Welcome | UA Arena Discord",
        "Welcome to UA Arena. Rules, title roles, and one Union Arena thread per anime or manga.",
        board,
        "welcome",
        body,
        path="discord/welcome.html",
    )
    (dest / "welcome.html").write_text(page)
    index = discord_chrome(
        "UA Arena Discord",
        "UA Arena Discord: rules, title roles, and one Union Arena thread per anime or manga.",
        board,
        "welcome",
        body,
        path="discord/index.html",
    )
    (dest / "index.html").write_text(index)


def write_announcements(board: dict, dest: Path) -> None:
    updated = html.escape(board.get("updated") or "")
    messages = []
    for note in board.get("announcements") or []:
        messages.append(
            _message(
                "UA Arena Bot",
                html.escape(note.get("date") or updated),
                f"<p><strong>{html.escape(note.get('title') or 'Update')}</strong></p><p>{html.escape(note.get('body') or '')}</p>",
                "is-pin" if note.get("id") == "format-pulse" else "",
            )
        )
    body = f"""        <div class="discord-head">
          <div class="discord-head-hash">#</div>
          <div>
            <h2>announcements</h2>
            <p>Format notes, restricted cards, and how the consensus 50s land.</p>
          </div>
        </div>
        <div class="discord-feed">
{chr(10).join(messages)}
        </div>"""
    page = discord_chrome(
        "Announcements | UA Arena Discord",
        "UA Arena Discord announcements: Standard format, restricted cards, and consensus list updates.",
        board,
        "announcements",
        body,
        path="discord/announcements.html",
    )
    (dest / "announcements.html").write_text(page)


def write_roles(board: dict, dest: Path) -> None:
    updated = html.escape(board.get("updated") or "")
    items = []
    for role in title_roles(board):
        items.append(
            f'<li><a class="discord-role-row" href="{html.escape(role["href"])}">'
            f'<span class="discord-role {html.escape(role["color_class"])}">{html.escape(role["name"])}</span>'
            f'<span class="discord-role-note">{html.escape(list_count_label(role["deck_count"]))} · thread</span></a></li>'
        )
    body = f"""        <div class="discord-head">
          <div class="discord-head-hash">#</div>
          <div>
            <h2>roles</h2>
            <p>One role per anime or manga title. Same names as the threads.</p>
          </div>
        </div>
        <div class="discord-feed">
{_message("UA Arena Bot", updated, f"""              <p><strong>Title roles</strong></p>
              <p>Grab the IP you sleeve. The live server uses these same names so people can ping Solo Leveling, Yu Yu Hakusho, Evangelion, and the rest.</p>
              <ul class="discord-role-list">{"".join(items)}</ul>""", "is-pin")}
        </div>"""
    page = discord_chrome(
        "Title roles | UA Arena Discord",
        "UA Arena Discord roles: one role per anime or manga title, matching the title threads.",
        board,
        "roles",
        body,
        path="discord/roles.html",
    )
    (dest / "roles.html").write_text(page)


def _deck_message(board: dict, deck: dict) -> str:
    updated = html.escape(deck.get("consensus_date") or board.get("updated") or "")
    list_url = absolute_url(deck.get("consensus_url") or deck.get("page") or "")
    hub_url = "/" + (deck.get("page") or "").lstrip("/")
    copy = uadb.copy_button(deck.get("sim_text") or "")
    others = []
    for row in deck.get("recent_lists") or []:
        others.append(
            f'<li><a href="/{html.escape(row["href"])}">{html.escape(row.get("title") or row["slug"])}</a> '
            f'<span class="muted">{html.escape(row.get("date") or row.get("kind") or "")}</span></li>'
        )
    other_html = (
        f"<p><strong>Other public lists</strong></p><ul class=\"discord-more\">{''.join(others)}</ul>"
        if others
        else ""
    )
    return _message(
        "UA Arena Bot",
        updated,
        f"""              <p><strong>{html.escape(consensus_header(deck))}</strong></p>
              <p>Pulled from the website. <a href="{html.escape(list_url)}">Open the full list</a> · <a href="{html.escape(hub_url)}">Character page</a></p>
              {copy}
              <div class="discord-deck">{_card_rows(deck)}</div>
              {other_html}""",
        msg_id=deck.get("key") or "",
    )


def write_theme(board: dict, theme: dict, dest: Path) -> None:
    aliases = ", ".join(html.escape(a) for a in (theme.get("aliases") or [])[:6] if a != theme.get("slug"))
    jumps = []
    for deck in theme.get("decks") or []:
        jumps.append(
            f'<a href="#{html.escape(deck["key"])}">{html.escape(deck.get("name") or deck["key"])}</a>'
        )
    messages = [
        _message(
            "UA Arena Bot",
            html.escape(board.get("updated") or ""),
            f"""              <p><strong>{html.escape(theme.get("name") or theme.get("slug") or "Title")} thread</strong></p>
              <p>One thread for this anime or manga. Role: <span class="discord-role {html.escape(uadb.color_class(theme.get("color") or ""))}">{html.escape(theme.get("name") or "")}</span>. Consensus 50s pulled from the website.</p>
              <p><a href="/series/{html.escape(theme.get("slug") or "")}.html">All {html.escape(theme.get("name") or "title")} decks on the site</a> · <a href="/characters.html">Characters</a> · <a href="/format.html">Format</a></p>
              <p class="discord-jump">{' · '.join(jumps)}</p>""",
            "is-pin",
        )
    ]
    for deck in theme.get("decks") or []:
        messages.append(_deck_message(board, deck))
    body = f"""        <div class="discord-head">
          <div class="discord-head-hash">#</div>
          <div>
            <h2>{html.escape(theme.get("name") or theme.get("slug") or "")}</h2>
            <p>{html.escape(list_count_label(theme.get("deck_count")))} in this title{f" · aliases {aliases}" if aliases else ""}</p>
          </div>
        </div>
        <div class="discord-feed">
{chr(10).join(messages)}
        </div>"""
    page = discord_chrome(
        uadb.page_title(f"{theme.get('name') or theme.get('slug')} Discord"),
        f"{theme.get('name')} Union Arena title thread with consensus 50-card lists for this anime or manga.",
        board,
        f"theme:{theme.get('slug')}",
        body,
        path=f"discord/{theme.get('slug') or 'title'}.html",
    )
    (dest / f"{theme['slug']}.html").write_text(page)


def _card_rows(deck: dict) -> str:
    groups: dict[str, list[dict]] = defaultdict(list)
    for card in deck.get("lines") or []:
        groups[card.get("group") or "Characters"].append(card)
    order = ["Characters", "Events", "Sites"]
    blocks = []
    for group in order:
        rows = groups.get(group) or []
        if not rows:
            continue
        items = []
        for card in rows:
            items.append(
                f"<li><span class=\"qty\">{html.escape(str(card.get('count') or 0))}x</span> "
                f"<span class=\"card-title\">{html.escape(card.get('name') or '')}</span> "
                f"<span class=\"muted card-id\">{html.escape(card.get('id') or '')}</span></li>"
            )
        blocks.append(f"<h4>{html.escape(group)}</h4><ul class=\"discord-list\">{''.join(items)}</ul>")
    return "".join(blocks)


def write_thread_redirect(theme: dict, deck: dict, dest: Path) -> None:
    target = f"/discord/{theme.get('slug') or 'welcome'}.html#{deck.get('key') or ''}"
    name = html.escape(theme.get("name") or theme.get("slug") or "title")
    deck_name = html.escape(deck.get("full") or deck.get("name") or "Deck")
    desc = uadb.clip_meta(
        f"{deck.get('full') or deck.get('name') or 'Deck'} consensus list in the {theme.get('name') or 'title'} UA Arena Discord thread."
    )
    canonical = f"discord/{theme.get('slug') or 'welcome'}.html"
    key = deck.get("key") or ""
    name = deck.get("name") or "Deck"
    tail = key.rsplit("-", 1)[-1].lower()
    if tail in {"purple", "red", "yellow", "green", "blue", "black"} and tail not in name.lower():
        name = f"{name} {tail}"
    elif key and uadb.slugify(name) not in key:
        rest = key
        theme_slug = theme.get("slug") or ""
        if theme_slug and rest.startswith(f"{theme_slug}-"):
            rest = rest[len(theme_slug) + 1 :]
        if rest:
            name = rest.replace("-", " ")
    title = uadb.page_title(f"{name} · {theme.get('name') or 'title'} Discord")
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <meta http-equiv="refresh" content="0;url={html.escape(target)}" />
{uadb.seo_head(title, desc, canonical, robots="noindex, follow")}
</head>
<body>
  <p>{deck_name} lives in the <a href="{html.escape(target)}">{name} thread</a>.</p>
</body>
</html>
"""
    thread_dir = dest / "threads"
    thread_dir.mkdir(parents=True, exist_ok=True)
    (thread_dir / f"{deck['key']}.html").write_text(page)


def write_pages(board: dict, dest: Path | None = None) -> list[str]:
    dest = dest or (uadb.ROOT / "discord")
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "threads").mkdir(parents=True, exist_ok=True)
    (dest / "board.json").write_text(json.dumps(board, indent=2, ensure_ascii=False) + "\n")
    write_welcome(board, dest)
    write_announcements(board, dest)
    write_roles(board, dest)
    paths = [
        "discord/",
        "discord/welcome.html",
        "discord/announcements.html",
        "discord/roles.html",
        "discord/board.json",
    ]
    keep_files = {"board.json", "welcome.html", "announcements.html", "index.html", "roles.html"}
    keep_threads: set[str] = set()
    for theme in board.get("themes") or []:
        write_theme(board, theme, dest)
        keep_files.add(f"{theme['slug']}.html")
        paths.append(f"discord/{theme['slug']}.html")
        for deck in theme.get("decks") or []:
            write_thread_redirect(theme, deck, dest)
            keep_threads.add(f"{deck['key']}.html")
            paths.append(f"discord/threads/{deck['key']}.html")
    for path in dest.iterdir():
        if path.is_file() and path.name not in keep_files:
            path.unlink()
    thread_dir = dest / "threads"
    if thread_dir.exists():
        for path in thread_dir.iterdir():
            if path.is_file() and path.name not in keep_threads:
                path.unlink()
    return paths


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    prefer = "live" if "--live" in args else "local"
    theme = ""
    if "--theme" in args:
        idx = args.index("--theme")
        theme = args[idx + 1] if idx + 1 < len(args) else ""
    source = ""
    if "--source" in args:
        idx = args.index("--source")
        source = args[idx + 1] if idx + 1 < len(args) else ""
    board = fetch_board(source or None, prefer=prefer)
    if "--dump" in args or theme:
        print(dump_theme(board, theme or None))
        return
    paths = write_pages(board)
    print("wrote", len(paths), "discord pages")


if __name__ == "__main__":
    main()
