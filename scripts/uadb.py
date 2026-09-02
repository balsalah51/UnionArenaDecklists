#!/usr/bin/env python3
"""Shared helpers for Union Arena Deck Base, GitHub Pages static site."""

from __future__ import annotations

import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://unionarenadecklists.com"
UA = "UnionArenaDecklists/1.0 (+https://unionarenadecklists.com; public UA list scrape)"
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
DISCORD = "https://discord.gg/aY9RfB662"
BRAND = "Union Arena Decklists"
SUBTITLE = "50-card lists for Standard"
CSS_VER = "ua23"
JS_VER = "ua8"
TCGPLAYER_CATEGORY_ID = 81
TCGPLAYER_PRICES_FILE = "data/tcgplayer-prices.json"
HERO_IMAGE = f"{SITE}/img/uadb-hero.png"
HERO_WIDTH = 1200
HERO_HEIGHT = 630
OG_IMAGE = f"{SITE}/img/og-logo.png"
OG_WIDTH = 1200
OG_HEIGHT = 630
ICON_48 = f"{SITE}/img/icon-48.png"
ICON_192 = f"{SITE}/img/icon-192.png"
ICON_512 = f"{SITE}/img/icon-512.png"
SEARCH_PATH = "/characters.html"
DEFAULT_ROBOTS = "index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1"
SITE_DESCRIPTION = "50-card Union Arena TCG decklists for Standard, grouped by anime and manga title."
ADSENSE_CLIENT = "ca-pub-1074015774205047"
FONT_LINKS = f"""  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link rel="preconnect" href="https://www.unionarena-tcg.com" crossorigin />
  <link rel="dns-prefetch" href="https://www.unionarena-tcg.com" />
  <link href="https://fonts.googleapis.com/css2?family=Bungee&family=Nunito:wght@400;600;700;800&display=swap" rel="stylesheet" />
  <link rel="icon" href="/img/icon-48.png" type="image/png" sizes="48x48" />
  <link rel="icon" href="/img/icon-192.png" type="image/png" sizes="192x192" />
  <link rel="icon" href="/favicon.ico" sizes="48x48" />
  <link rel="icon" href="/favicon.svg" type="image/svg+xml" sizes="any" />
  <link rel="apple-touch-icon" href="/img/apple-touch-icon.png" sizes="180x180" />
  <link rel="manifest" href="/site.webmanifest" />
  <meta name="theme-color" content="#7a2e2e" />
  <link rel="alternate" type="application/rss+xml" title="{BRAND}" href="/feed.xml" />
  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={ADSENSE_CLIENT}" crossorigin="anonymous"></script>
"""
MIN_CARDS = 40
TARGET = 50
RESTRICTED_CARDS = (
    "UE15BT/EVA-1-051",  # Asuka Shikinami Langley
    "UE15BT/EVA-1-063",  # Spear of Gaius
)
RESTRICTED_ONE = set(RESTRICTED_CARDS)
# Shadow Soldiers (Solo Leveling) may exceed the usual 4-copy cap.
HIGH_COPY_NUMBERS = {
    "SLG-1-030": 12,
}
STAMP_RE = re.compile(
    r"\s*\((?:"
    r"winner|box topper foil|ur\*|sr\*|r\*|ur|sr|r|c\*|alt\s*\d+"
    r"|release event(?: participation| participant| winner)?"
    r"|super pre-release event participation"
    r"|regionals[^)]*"
    r")\)\s*",
    re.I,
)
LINE_RE = re.compile(
    r"(?i)(\d+)\s*[x×*]\s*((?:UE|UA|ST|PR|UEX)[A-Z0-9]{0,8}[/_\-]+[A-Z]{2,4}\d?-\d-\d{3})"
)
CID_TOKEN_RE = re.compile(
    r"(?i)\b((?:UE|UA|ST|PR|UEX)[A-Z0-9]{2,8})[/_\-]+([A-Z]{2,4}\d?-\d-\d{3})(?:-ALT\d+)?"
)
ANIME_PRETTY = {
    "csm": "Chainsaw Man",
    "chainsaw man": "Chainsaw Man",
    "iys": "Inuyasha",
    "inuyasha": "Inuyasha",
    "opm": "One Punch Man",
    "one punch man": "One Punch Man",
    "fma": "Fullmetal Alchemist",
    "fullmetal alchemist": "Fullmetal Alchemist",
    "aot": "Attack On Titan",
    "attack on titan": "Attack On Titan",
    "yyh": "Yu Yu Hakusho",
    "yu yu hakusho": "Yu Yu Hakusho",
    "bcv": "Black Clover",
    "black clover": "Black Clover",
    "htr": "Hunter x Hunter",
    "hunter x hunter": "Hunter x Hunter",
    "kmy": "Demon Slayer",
    "demon slayer": "Demon Slayer",
    "mha": "My Hero Academia",
    "my hero academia": "My Hero Academia",
    "rez": "Re:Zero",
    "re zero": "Re:Zero",
    "nik": "Nikke",
    "nikke": "Nikke",
    "slime": "That Time I Got Reincarnated As A Slime",
    "kj8": "Kaiju No. 8",
    "kaiju no 8": "Kaiju No. 8",
    "kaiju no. 8": "Kaiju No. 8",
}
QTY_BEFORE_RE = re.compile(
    r"(?i)(\d{1,2})\s*[x×*]\s*((?:UE|UA|ST|PR|UEX)[A-Z0-9]{2,8}[/_\-]+[A-Z]{2,4}\d?-\d-\d{3})"
)
QTY_AFTER_RE = re.compile(
    r"(?i)((?:UE|UA|ST|PR|UEX)[A-Z0-9]{2,8}[/_\-]+[A-Z]{2,4}\d?-\d-\d{3})\s*[x×*]\s*(\d{1,2})"
)
POPUP_JS = r"""
    (function(){
      var lines = document.querySelectorAll('.text-line');
      if (!lines.length) return;
      function resetPop(pop){
        pop.style.position = '';
        pop.style.left = '';
        pop.style.top = '';
        pop.style.right = '';
        pop.style.bottom = '';
        pop.classList.remove('flip-left', 'flip-down');
      }
      function place(line){
        var pop = line.querySelector('.card-pop');
        var title = line.querySelector('.card-title');
        if (!pop || !title) return;
        resetPop(pop);
        var tr = title.getBoundingClientRect();
        var width = pop.offsetWidth || 340;
        var height = pop.offsetHeight || 475;
        var left = tr.left;
        var top = tr.top - height - 10;
        if (left + width > window.innerWidth - 12) left = window.innerWidth - width - 12;
        if (left < 12) left = 12;
        if (top < 12) top = tr.bottom + 10;
        if (top + height > window.innerHeight - 12) top = Math.max(12, window.innerHeight - height - 12);
        pop.style.position = 'fixed';
        pop.style.left = left + 'px';
        pop.style.top = top + 'px';
        pop.style.bottom = 'auto';
        pop.style.right = 'auto';
      }
      lines.forEach(function(line){
        line.addEventListener('mouseenter', function(){ place(line); });
        line.addEventListener('focus', function(){ place(line); });
        line.addEventListener('click', function(e){
          if (e.target.closest('a')) return;
          if (window.matchMedia('(hover: hover)').matches) return;
          e.stopPropagation();
          lines.forEach(function(other){ if (other !== line) other.classList.remove('is-open'); });
          line.classList.toggle('is-open');
          place(line);
        });
      });
      document.addEventListener('click', function(e){
        if (!e.target.closest('.text-line')) {
          lines.forEach(function(line){ line.classList.remove('is-open'); });
        }
      });
    })();
"""

TITLE_PREFIX = {
    "solo leveling": "SOLO LEVELING",
    "sakamoto days": "SAKAMOTO DAYS",
    "evangelion": "EVANGELION",
    "csm": "CHAINSAW MAN",
    "chainsaw man": "CHAINSAW MAN",
    "jujutsu kaisen": "JUJUTSU KAISEN",
    "rurouni kenshin": "RUROUNI KENSHIN",
    "kagurabachi": "KAGURABACHI",
    "sword art online": "SWORD ART ONLINE",
    "that time i got reincarnated as a slime": "SLIME",
    "tokyo ghoul": "TOKYO GHOUL",
    "bleach": "BLEACH",
    "code geass": "CODE GEASS",
    "one punch man": "ONE PUNCH MAN",
    "the 100 girlfriends": "100 GIRLFRIENDS",
}

COLOR_CLASS = {
    "red": "color-red",
    "green": "color-green",
    "blue": "color-blue",
    "purple": "color-purple",
    "yellow": "color-yellow",
    "black": "color-black",
}


def log(*args) -> None:
    print(*args, flush=True)


def fetch(
    url: str,
    timeout: int = 20,
    data: bytes | None = None,
    content_type: str | None = None,
    browser: bool = False,
    extra_headers: dict | None = None,
) -> tuple[int, str]:
    headers = {
        "User-Agent": BROWSER_UA if browser else UA,
        "Accept": "text/html,application/json,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method="POST" if data is not None else "GET",
    )
    if data is not None:
        req.add_header("Content-Type", content_type or "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace") if exc.fp else ""
        return exc.code, body
    except Exception as exc:  # noqa: BLE001
        return 0, f"{type(exc).__name__}: {exc}"


def http_json(url: str, retries: int = 5, data: bytes | None = None, content_type: str | None = None):
    last = None
    for attempt in range(retries):
        try:
            headers = {"User-Agent": UA, "Accept": "application/json"}
            if content_type:
                headers["Content-Type"] = content_type
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read())
        except Exception as exc:  # noqa: BLE001
            last = exc
            wait = 0.6 * (attempt + 1)
            if "429" in str(exc):
                wait = 6 * (attempt + 1)
            time.sleep(wait)
    raise last


def slugify(text: str) -> str:
    s = (text or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:80] or "list"


def load_json(rel: str, default):
    path = ROOT / rel
    if not path.exists():
        return default
    return json.loads(path.read_text())


def save_json(rel: str, data) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def official_image(cid: str) -> str:
    slug = (cid or "").replace("/", "_")
    return f"https://www.unionarena-tcg.com/na/images/cardlist/card/{slug}.png"


def card_image_url(cid: str, cache: dict | None = None) -> str:
    if cid and "/" in cid and "UNRESOLVED" not in cid:
        return official_image(cid)
    meta = (cache or {}).get(cid) or {}
    if meta.get("image"):
        img = meta["image"]
        if img.startswith("/"):
            return "https://tcgcontender.com" + img
        return img
    return official_image(cid)


def color_class(color: str | None) -> str:
    raw = (color or "").split(";")[0].split("/")[0].strip().lower()
    return COLOR_CLASS.get(raw, "color-red")


def display_name(name: str) -> str:
    return " ".join(no_em(name or "").split())


def ordinal(n) -> str | None:
    if n is None:
        return None
    try:
        n = int(n)
    except (TypeError, ValueError):
        return None
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def nav_html(current: str = "") -> str:
    def item(href: str, label: str, key: str) -> str:
        cur = ' aria-current="page"' if current == key else ""
        extra = ' target="_blank" rel="noopener"' if href.startswith("http") else ""
        return f'        <a href="{html.escape(href)}"{cur}{extra}>{html.escape(label)}</a>'

    return "\n".join(
        [
            '      <nav aria-label="Primary">',
            item("/#recent", "Recent lists", "recent"),
            item("/characters.html", "Characters", "characters"),
            item("/format.html", "Format", "format"),
            item("/shop.html", "Shop", "shop"),
            item("/discord/welcome.html", "Discord", "discord"),
            "      </nav>",
        ]
    )


def brand_heading() -> str:
    return (
        '<p class="brand-lockup">'
        '<span class="brand-kicker">Union Arena</span>'
        '<span class="brand-name">Decklists</span>'
        "</p>"
    )


def logo_html() -> str:
    return (
        f'<img class="logo" src="/img/logo.svg" width="56" height="56" '
        f'alt="{html.escape(BRAND)}" />'
    )


def absolute_url(path: str) -> str:
    raw = (path or "").strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    if not raw or raw == "/":
        return f"{SITE}/"
    return f"{SITE}/{raw.lstrip('/')}"


def clip_meta(text: str, limit: int = 160) -> str:
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if len(clean) <= limit:
        return clean
    cut = clean[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,.;:|-")
    return (cut or clean[: limit - 1]) + "…"


def page_title(primary: str, brand: str | None = None) -> str:
    brand = brand or BRAND
    primary = re.sub(r"\s+", " ", (primary or "").strip())
    if not primary:
        return f"{brand} | Standard TCG 50-card lists"
    if primary.lower() == brand.lower():
        return f"{brand} | Standard TCG 50-card lists"
    if brand.lower() in primary.lower():
        return primary[:70]
    titled = f"{primary} | {brand}"
    if len(titled) <= 70:
        return titled
    for use_brand in (brand, "UA Decklists"):
        titled = f"{primary} | {use_brand}"
        if len(titled) <= 70:
            return titled
    use_brand = "UA Decklists"
    budget = max(24, 70 - len(use_brand) - 3)
    if len(primary) <= budget:
        return f"{primary} | {use_brand}"
    head_budget = max(12, budget // 2)
    tail_budget = max(10, budget - head_budget - 1)
    head = primary[:head_budget].rsplit(" ", 1)[0].rstrip(" ·|-")
    tail = primary[-tail_budget:].split(" ", 1)[-1].strip(" ·|-")
    if head and tail and head != tail:
        short = f"{head}…{tail}"
        if len(short) <= budget:
            return f"{short} | {use_brand}"
    short = primary[:budget].rsplit(" ", 1)[0].rstrip(" ·|-") or primary[:budget]
    return f"{short} | {use_brand}"


def crumb_html(parts: list[tuple[str | None, str]]) -> str:
    bits = []
    for href, label in parts:
        if href:
            bits.append(f'<a href="{html.escape(href)}">{html.escape(label)}</a>')
        else:
            bits.append(html.escape(label))
    return f'<nav class="crumb" aria-label="Breadcrumb">{" / ".join(bits)}</nav>'


def breadcrumb_ld(parts: list[tuple[str, str]]) -> dict:
    items = []
    for i, (href, label) in enumerate(parts, start=1):
        entry: dict = {"@type": "ListItem", "position": i, "name": label}
        if href:
            entry["item"] = absolute_url(href)
        items.append(entry)
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items}


def organization_ld() -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "@id": f"{SITE}/#organization",
        "name": BRAND,
        "alternateName": ["UAD", "UA Decklists"],
        "url": f"{SITE}/",
        "logo": {
            "@type": "ImageObject",
            "url": ICON_512,
            "contentUrl": ICON_512,
            "width": 512,
            "height": 512,
        },
        "image": ICON_512,
        "sameAs": [DISCORD],
        "description": SITE_DESCRIPTION,
    }


def website_ld() -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "@id": f"{SITE}/#website",
        "name": BRAND,
        "alternateName": ["UAD", "UA Decklists"],
        "url": f"{SITE}/",
        "inLanguage": "en-US",
        "description": SITE_DESCRIPTION,
        "publisher": {"@id": f"{SITE}/#organization"},
        "potentialAction": {
            "@type": "SearchAction",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": f"{SITE}{SEARCH_PATH}?q={{search_term_string}}",
            },
            "query-input": "required name=search_term_string",
        },
    }


def item_list_ld(name: str, rows: list[tuple[str, str]], *, url: str = "") -> dict:
    block: dict = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": name,
        "numberOfItems": len(rows),
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i,
                "url": absolute_url(href),
                "name": label,
            }
            for i, (href, label) in enumerate(rows, start=1)
        ],
    }
    if url:
        block["url"] = absolute_url(url)
    return block


def faq_ld(pairs: list[tuple[str, str]]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": question,
                "acceptedAnswer": {"@type": "Answer", "text": answer},
            }
            for question, answer in pairs
        ],
    }


def webpage_ld(
    path: str,
    title: str,
    description: str,
    *,
    page_type: str = "WebPage",
    date_modified: str = "",
    date_published: str = "",
    image: str = "",
) -> dict:
    block: dict = {
        "@context": "https://schema.org",
        "@type": page_type,
        "name": title,
        "url": absolute_url(path),
        "description": clip_meta(description),
        "inLanguage": "en-US",
        "isPartOf": {"@id": f"{SITE}/#website"},
        "publisher": {"@id": f"{SITE}/#organization"},
    }
    if date_published:
        block["datePublished"] = date_published
    if date_modified or date_published:
        block["dateModified"] = date_modified or date_published
    if image:
        block["image"] = absolute_url(image) if image.startswith("/") else image
    return block


def decklist_ld(
    path: str,
    title: str,
    description: str,
    *,
    date: str = "",
    image: str = "",
    series: str = "",
    character: str = "",
) -> dict:
    about = [{"@type": "Thing", "name": "Union Arena"}]
    if series:
        about.append({"@type": "Thing", "name": series})
    if character and character != series:
        about.append({"@type": "Thing", "name": character})
    block = webpage_ld(
        path,
        title,
        description,
        page_type="CreativeWork",
        date_published=date,
        date_modified=date,
        image=image,
    )
    block["genre"] = "Trading Card Game decklist"
    block["about"] = about
    return block


def json_ld_script(blocks: list[dict] | None) -> str:
    if not blocks:
        return ""
    chunks = []
    for block in blocks:
        payload = json.dumps(block, ensure_ascii=False, separators=(",", ":"))
        payload = payload.replace("<", "\\u003c")
        chunks.append(f'  <script type="application/ld+json">{payload}</script>')
    return "\n".join(chunks) + "\n"


def site_graph(blocks: list[dict] | None) -> list[dict]:
    out = list(blocks or [])
    if not any(block.get("@type") == "Organization" for block in out):
        out.insert(0, organization_ld())
    if not any(block.get("@type") == "WebSite" for block in out):
        idx = 1 if out and out[0].get("@type") == "Organization" else 0
        out.insert(idx, website_ld())
    return out


def seo_head(
    title: str,
    description: str,
    path: str,
    *,
    image: str = "",
    image_alt: str = "",
    page_type: str = "website",
    json_ld: list[dict] | None = None,
    extra: str = "",
    robots: str = "",
    published: str = "",
    modified: str = "",
) -> str:
    desc = clip_meta(description)
    url = absolute_url(path)
    img = image or OG_IMAGE
    if img.startswith("/"):
        img = absolute_url(img)
    alt = image_alt or title
    robots_val = robots or DEFAULT_ROBOTS
    robots_tag = f'  <meta name="robots" content="{html.escape(robots_val)}" />\n'
    dates = ""
    if published:
        dates += f'  <meta property="article:published_time" content="{html.escape(published)}" />\n'
    if modified or published:
        dates += f'  <meta property="article:modified_time" content="{html.escape(modified or published)}" />\n'
    og_size = ""
    if (
        img.rstrip("/") == OG_IMAGE.rstrip("/")
        or img.endswith("/img/og-logo.png")
        or img.rstrip("/") == HERO_IMAGE.rstrip("/")
        or img.endswith("/img/uadb-hero.png")
    ):
        og_size = (
            f'  <meta property="og:image:width" content="{OG_WIDTH}" />\n'
            f'  <meta property="og:image:height" content="{OG_HEIGHT}" />\n'
            f'  <meta property="og:image:type" content="image/png" />\n'
        )
    extra_html = extra if extra.endswith("\n") or not extra else extra + "\n"
    return (
        f"  <title>{html.escape(title)}</title>\n"
        f'  <meta name="description" content="{html.escape(desc)}" />\n'
        f"{robots_tag}"
        f'  <link rel="canonical" href="{html.escape(url)}" />\n'
        f'  <meta property="og:site_name" content="{html.escape(BRAND)}" />\n'
        f'  <meta property="og:title" content="{html.escape(title)}" />\n'
        f'  <meta property="og:description" content="{html.escape(desc)}" />\n'
        f'  <meta property="og:url" content="{html.escape(url)}" />\n'
        f'  <meta property="og:type" content="{html.escape(page_type)}" />\n'
        f'  <meta property="og:image" content="{html.escape(img)}" />\n'
        f"{og_size}"
        f'  <meta property="og:image:alt" content="{html.escape(alt)}" />\n'
        f'  <meta property="og:locale" content="en_US" />\n'
        f'  <meta name="twitter:card" content="summary_large_image" />\n'
        f'  <meta name="twitter:title" content="{html.escape(title)}" />\n'
        f'  <meta name="twitter:description" content="{html.escape(desc)}" />\n'
        f'  <meta name="twitter:image" content="{html.escape(img)}" />\n'
        f'  <meta name="twitter:image:alt" content="{html.escape(alt)}" />\n'
        f"{dates}"
        f"{json_ld_script(site_graph(json_ld))}"
        f"{extra_html}"
    )


def skip_link() -> str:
    return '<a class="skip-link" href="#main">Skip to content</a>'


def footer_links() -> str:
    return (
        f'      © <span id="year"></span> {html.escape(BRAND)}. Fan site, not affiliated with Bandai.\n'
        '      <a href="/characters.html">Characters</a> · '
        '<a href="/series.html">Titles</a> · '
        '<a href="/#recent">Recent lists</a> · '
        '<a href="/format.html">Format</a> · '
        '<a href="/shop.html">Shop</a> · '
        '<a href="/discord/welcome.html">Discord</a> · '
        '<a href="/feed.xml">RSS</a> · '
        '<a href="/privacy.html">Privacy</a>\n'
        '      <span class="footer-amazon">As an Amazon Associate I earn from qualifying purchases.</span>'
    )


def page_chrome(
    title: str,
    description: str,
    color: str,
    body: str,
    current: str = "",
    *,
    path: str = "",
    image: str = "",
    image_alt: str = "",
    json_ld: list[dict] | None = None,
    robots: str = "",
    published: str = "",
    modified: str = "",
) -> str:
    return no_em(f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
{seo_head(title, description, path, image=image, image_alt=image_alt, json_ld=json_ld, robots=robots, published=published, modified=modified)}{FONT_LINKS}  <link rel="stylesheet" href="/css/site.css?v={CSS_VER}" />
</head>
<body class="{html.escape(color)}">
  {skip_link()}
  <div class="wrap">
    <header>
      <a class="brand" href="/">
        {logo_html()}
        <div class="brand-copy">
          {brand_heading()}
          <div class="subtitle">{html.escape(SUBTITLE)}</div>
        </div>
      </a>
{nav_html(current)}
    </header>

    <main class="single" id="main">
      <div class="card hero">
{body}
      </div>
    </main>
    <footer>
{footer_links()}
    </footer>
  </div>
  <script>
    document.getElementById('year').textContent = new Date().getFullYear();
{POPUP_JS}
  </script>
  <script src="/js/affiliate.js?v={JS_VER}"></script>
  <script src="/js/site.js?v={JS_VER}"></script>
</body>
</html>
""")


def home_chrome(
    body: str,
    *,
    title: str | None = None,
    description: str | None = None,
    image: str = "",
    image_alt: str = "",
    json_ld: list[dict] | None = None,
) -> str:
    page_t = title or page_title(BRAND)
    page_d = description or (
        "Union Arena TCG decklists for Standard: 50-card lists, character hubs, and consensus cores by anime and manga title."
    )
    ld = json_ld or [organization_ld(), website_ld()]
    brand_image = image or OG_IMAGE
    brand_alt = image_alt or BRAND
    return no_em(f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
{seo_head(page_t, page_d, "/", image=brand_image, image_alt=brand_alt, json_ld=ld)}{FONT_LINKS}  <link rel="stylesheet" href="/css/site.css?v={CSS_VER}" />
</head>
<body>
  {skip_link()}
  <div class="wrap">
    <header>
      <a class="brand" href="/">
        {logo_html()}
        <div class="brand-copy">
          {brand_heading()}
          <div class="subtitle">{html.escape(SUBTITLE)}</div>
        </div>
      </a>
{nav_html()}
    </header>

    <main class="single home" id="main" role="main">
{body}
    </main>
    <footer>
{footer_links()}
    </footer>
  </div>
  <script>
    document.getElementById('year').textContent = new Date().getFullYear();
  </script>
  <script src="/js/affiliate.js?v={JS_VER}"></script>
  <script src="/js/site.js?v={JS_VER}"></script>
</body>
</html>
""")


def copy_button(sim_text: str) -> str:
    compact = " ".join((sim_text or "").split())
    if not compact:
        return ""
    return (
        f'<button type="button" class="copy-sim" data-copy-sim data-sim="{html.escape(compact, quote=True)}">'
        "Copy list</button>"
    )


def _tcgplayer_card_label(cid: str, name: str) -> tuple[str, str, str]:
    cid = (cid or "").strip()
    set_code = cid.split("/", 1)[0] if "/" in cid else ""
    number = legal_number(cid) if cid else ""
    label, _printed = parse_named_card(name)
    label = display_name(label)
    if not label or label.upper() == cid.upper() or "/" in label:
        label = ""
    return label, set_code, number


def tcgplayer_card_search_url(cid: str, name: str = "") -> str:
    cid = (cid or "").strip()
    if not cid or "UNRESOLVED" in cid:
        return ""
    label, set_code, number = _tcgplayer_card_label(cid, name)
    q = " ".join(part for part in (label, set_code, number) if part)
    if not q:
        return ""
    query = urllib.parse.urlencode(
        {"productLineName": "union-arena", "q": q, "view": "grid"}
    )
    return f"https://www.tcgplayer.com/search/union-arena/product?{query}"


def tcgplayer_mass_entry_url(items: list | None, cache: dict | None = None) -> str:
    cache = cache or {}
    parts: list[str] = []
    for it in items or []:
        if (it.get("group") or "") == "AP cards":
            continue
        cid = (it.get("id") or "").strip()
        if not cid or "UNRESOLVED" in cid:
            continue
        try:
            qty = int(it.get("count") or 0)
        except (TypeError, ValueError):
            continue
        if qty < 1:
            continue
        meta = cache.get(cid) or {}
        label, set_code, number = _tcgplayer_card_label(
            cid, meta.get("name") or it.get("name") or ""
        )
        if not label:
            label = number or cid
        line = " ".join(part for part in (str(qty), label, set_code, number) if part)
        parts.append(line)
    if not parts:
        return ""
    query = urllib.parse.urlencode({"productline": "Union Arena", "c": "||".join(parts)})
    return f"https://www.tcgplayer.com/massentry?{query}"


TCGPLAYER_PARTNER = "https://partner.tcgplayer.com/c/7670706/1780961/21018"


def tcgplayer_affiliate_url(url: str) -> str:
    dest = (url or "").strip()
    if not dest:
        return ""
    if "partner.tcgplayer.com" in dest:
        return dest
    if "tcgplayer.com" not in dest.lower():
        return dest
    return f"{TCGPLAYER_PARTNER}?u={urllib.parse.quote(dest, safe='')}"


def _tcgplayer_row_median(row: dict) -> float:
    """Listed median (midPrice) on TCGplayer, then market price."""
    for key in ("midPrice", "marketPrice"):
        raw = row.get(key)
        if raw is None or raw == "":
            continue
        try:
            val = float(raw)
        except (TypeError, ValueError):
            continue
        if val > 0:
            return val
    return 0.0


def _product_number(product: dict) -> str:
    for field in product.get("extendedData") or []:
        if (field.get("name") or "").lower() == "number":
            return (field.get("value") or "").strip()
    return ""


def fetch_tcgplayer_medians() -> dict[str, float]:
    """Map Union Arena card IDs to TCGplayer listed-median prices via tcgcsv.com."""
    groups_url = f"https://tcgcsv.com/tcgplayer/{TCGPLAYER_CATEGORY_ID}/groups"
    payload = http_json(groups_url, retries=3)
    groups = payload.get("results") or []
    by_cid: dict[str, float] = {}
    for group in groups:
        abbr = (group.get("abbreviation") or "").upper()
        if "_RE" in abbr or "_PRE" in abbr:
            continue
        gid = group.get("groupId")
        if not gid:
            continue
        try:
            products = http_json(
                f"https://tcgcsv.com/tcgplayer/{TCGPLAYER_CATEGORY_ID}/{gid}/products",
                retries=3,
            ).get("results") or []
            prices = http_json(
                f"https://tcgcsv.com/tcgplayer/{TCGPLAYER_CATEGORY_ID}/{gid}/prices",
                retries=3,
            ).get("results") or []
        except Exception as exc:  # noqa: BLE001
            log("tcgplayer prices skip group", abbr or gid, exc)
            continue
        by_pid: dict[int, list[dict]] = defaultdict(list)
        for row in prices:
            pid = row.get("productId")
            if pid is None:
                continue
            by_pid[int(pid)].append(row)
        for product in products:
            cid = _product_number(product)
            if not cid or "/" not in cid:
                continue
            pid = product.get("productId")
            median = 0.0
            if pid is not None:
                median = max((_tcgplayer_row_median(row) for row in by_pid.get(int(pid), [])), default=0.0)
            if median <= 0:
                continue
            prev = by_cid.get(cid, 0.0)
            if median > prev:
                by_cid[cid] = round(median, 2)
    return by_cid


def load_tcgplayer_prices(refresh: bool = False) -> dict[str, float]:
    cached = load_json(TCGPLAYER_PRICES_FILE, {})
    by_cid = cached.get("by_cid") if isinstance(cached, dict) else {}
    if not refresh and isinstance(by_cid, dict) and by_cid:
        return {str(k): float(v) for k, v in by_cid.items() if v is not None}
    try:
        by_cid = fetch_tcgplayer_medians()
    except Exception as exc:  # noqa: BLE001
        log("tcgplayer prices fetch failed", exc)
        if isinstance(cached, dict) and cached.get("by_cid"):
            return {str(k): float(v) for k, v in cached["by_cid"].items() if v is not None}
        return {}
    if by_cid:
        save_json(
            TCGPLAYER_PRICES_FILE,
            {
                "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source": "https://tcgcsv.com/tcgplayer/81",
                "by_cid": by_cid,
            },
        )
        log("tcgplayer prices", len(by_cid))
    return by_cid


def tcgplayer_median_price(cid: str, prices: dict | None = None) -> float:
    prices = prices or {}
    cid = (cid or "").strip().replace("_", "/")
    if not cid:
        return 0.0
    raw = prices.get(cid)
    if raw is None:
        return 0.0
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return 0.0
    return val if val > 0 else 0.0


def buy_deck_button(url: str, label: str = "Buy on TCGplayer") -> str:
    if not url:
        return ""
    dest = tcgplayer_affiliate_url(url)
    return (
        f'<a class="buy-tcg buy-deck buy-pill" href="{html.escape(dest, quote=True)}" '
        f'target="_blank" rel="noopener sponsored">{html.escape(label)}</a>'
    )


def buy_card_link(url: str, label: str = "TCGplayer") -> str:
    if not url:
        return ""
    dest = tcgplayer_affiliate_url(url)
    return (
        f'<a class="buy-tcg buy-card" href="{html.escape(dest, quote=True)}" '
        f'target="_blank" rel="noopener sponsored">{html.escape(label)}</a>'
    )


def list_actions(*bits: str) -> str:
    packed = "".join(bit for bit in bits if bit)
    if not packed:
        return ""
    return f'<div class="list-actions">{packed}</div>'


def group_for(card_type: str) -> str:
    t = (card_type or "character").lower()
    if t.startswith("event"):
        return "Events"
    if t.startswith("site") or t.startswith("field") or t.startswith("stage"):
        return "Sites"
    if "action" in t or t == "ap":
        return "AP cards"
    return "Characters"


def legal_number(cid: str) -> str:
    raw = re.sub(r"(?i)-ALT\d+$", "", (cid or "").strip())
    if "/" in raw:
        raw = raw.split("/", 1)[1]
    return raw.upper()


def is_restricted(cid: str) -> bool:
    if not cid or "UNRESOLVED" in cid:
        return False
    if cid in RESTRICTED_ONE:
        return True
    num = legal_number(cid)
    return any(legal_number(r) == num for r in RESTRICTED_CARDS)


def max_copies(cid: str, cap_restricted: bool = True) -> int:
    if cap_restricted and is_restricted(cid):
        return 1
    num = legal_number(cid)
    if num in HIGH_COPY_NUMBERS:
        return HIGH_COPY_NUMBERS[num]
    return 4


def parse_named_card(label: str) -> tuple[str, str | None]:
    raw = (label or "").strip()
    number = None
    m = re.search(r"\((\d{2,3})\)", raw)
    if m:
        number = m.group(1).zfill(3)
    cleaned = STAMP_RE.sub(" ", raw)
    cleaned = re.sub(r"\s*\(\d{2,3}\)\s*", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")
    return cleaned or raw, number


def pretty_anime(name: str) -> str:
    raw = (name or "").strip()
    key = re.sub(r"[^a-z0-9]+", " ", raw.lower()).strip()
    if key in ANIME_PRETTY:
        return ANIME_PRETTY[key]
    return raw


def normalize_cid(raw: str) -> str | None:
    cleaned = re.sub(r"(?i)-ALT\d+$", "", (raw or "").strip())
    m = CID_TOKEN_RE.search(cleaned)
    if not m:
        return None
    set_code = m.group(1).upper()
    number = m.group(2).upper()
    if "-AP" in number:
        return None
    return f"{set_code}/{number}"


def parse_counts(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    blob = text or ""
    seen_spans: list[tuple[int, int]] = []
    for m in QTY_BEFORE_RE.finditer(blob):
        cid = normalize_cid(m.group(2))
        if not cid:
            continue
        counts[cid] = counts.get(cid, 0) + int(m.group(1))
        seen_spans.append(m.span())
    for m in QTY_AFTER_RE.finditer(blob):
        if any(m.start() >= a and m.end() <= b for a, b in seen_spans):
            continue
        cid = normalize_cid(m.group(1))
        if not cid:
            continue
        counts[cid] = counts.get(cid, 0) + int(m.group(2))
    out = {}
    for cid, n in counts.items():
        cap = max_copies(cid, cap_restricted=False)
        if 1 <= n <= cap:
            out[cid] = n
    return out


def list_is_complete(counts: dict[str, int]) -> bool:
    total = sum(counts.values())
    return MIN_CARDS <= total <= 60


def no_em(s: str) -> str:
    text = s or ""
    text = re.sub(r"\s*\u2014\s*", " - ", text)
    return text.replace("\u2013", "-").replace("\u2015", "-")
