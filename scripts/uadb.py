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
LOGO = "UA"
CSS_VER = "ua8"
JS_VER = "ua2"
FONT_LINKS = """  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Bungee&family=Nunito:wght@400;600;700;800&display=swap" rel="stylesheet" />
"""
MIN_CARDS = 40
TARGET = 50
RESTRICTED_CARDS = (
    "UE15BT/EVA-1-051",  # Asuka Shikinami Langley
    "UE15BT/EVA-1-063",  # Spear of Gaius
)
RESTRICTED_ONE = set(RESTRICTED_CARDS)
STAMP_RE = re.compile(
    r"\s*\((?:"
    r"winner|box topper foil|ur|sr|r|c\*|alt\s*\d+"
    r"|release event(?: participation| participant| winner)?"
    r"|super pre-release event participation"
    r"|regionals[^)]*"
    r")\)\s*",
    re.I,
)
LINE_RE = re.compile(
    r"(?i)(\d+)\s*[x×*]\s*((?:UE|UA|ST|PR|UEX)[A-Z0-9]{0,8}[/_\-]+[A-Z]{2,4}-\d-\d{3})"
)
CID_TOKEN_RE = re.compile(
    r"(?i)\b((?:UE|UA|ST|PR|UEX)[A-Z0-9]{2,8})[/_\-]+([A-Z]{2,4}-\d-\d{3})(?:-ALT\d+)?"
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
}
QTY_BEFORE_RE = re.compile(
    r"(?i)(\d{1,2})\s*[x×*]\s*((?:UE|UA|ST|PR|UEX)[A-Z0-9]{2,8}[/_\-]+[A-Z]{2,4}-\d-\d{3})"
)
QTY_AFTER_RE = re.compile(
    r"(?i)((?:UE|UA|ST|PR|UEX)[A-Z0-9]{2,8}[/_\-]+[A-Z]{2,4}-\d-\d{3})\s*[x×*]\s*(\d{1,2})"
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
        var width = pop.offsetWidth || 110;
        var height = pop.offsetHeight || 154;
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
    return " ".join((name or "").split())


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
            item("/#characters", "Characters", "characters"),
            item("/format.html", "Format", "format"),
            item(DISCORD, "Discord", "discord"),
            "      </nav>",
        ]
    )


def brand_heading() -> str:
    return (
        "<h1>"
        '<span class="brand-kicker">Union Arena</span>'
        '<span class="brand-name">Decklists</span>'
        "</h1>"
    )


def page_chrome(title: str, description: str, color: str, body: str, current: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(description)}" />
{FONT_LINKS}  <link rel="stylesheet" href="/css/site.css?v={CSS_VER}" />
</head>
<body class="{html.escape(color)}">
  <div class="wrap">
    <header>
      <a class="brand" href="/">
        <div class="logo">{LOGO}</div>
        <div class="brand-copy">
          {brand_heading()}
          <div class="subtitle">{html.escape(SUBTITLE)}</div>
        </div>
      </a>
{nav_html(current)}
    </header>

    <main class="single">
      <div class="card hero">
{body}
      </div>
    </main>
    <footer>
      © <span id="year"></span> {html.escape(BRAND)}. Fan site, not affiliated with Bandai.
      <a href="/characters.html">Characters</a> · <a href="/#recent">Recent lists</a> · <a href="/format.html">Format</a> · <a href="/privacy.html">Privacy</a>
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
"""


def home_chrome(body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{html.escape(BRAND)}</title>
  <meta name="description" content="Union Arena TCG decklists. Character pictures and recent 50-card lists for Standard." />
{FONT_LINKS}  <link rel="stylesheet" href="/css/site.css?v={CSS_VER}" />
</head>
<body>
  <div class="wrap">
    <header>
      <a class="brand" href="/">
        <div class="logo">{LOGO}</div>
        <div class="brand-copy">
          {brand_heading()}
          <div class="subtitle">{html.escape(SUBTITLE)}</div>
        </div>
      </a>
{nav_html()}
    </header>

    <main class="single home" role="main">
{body}
    </main>
    <footer>
      © <span id="year"></span> {html.escape(BRAND)}. Fan site, not affiliated with Bandai.
      <a href="/characters.html">Characters</a> · <a href="/#recent">Recent lists</a> · <a href="/format.html">Format</a> · <a href="/privacy.html">Privacy</a>
    </footer>
  </div>
  <script>
    document.getElementById('year').textContent = new Date().getFullYear();
  </script>
  <script src="/js/affiliate.js?v={JS_VER}"></script>
  <script src="/js/site.js?v={JS_VER}"></script>
</body>
</html>
"""


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


def buy_deck_button(url: str, label: str = "Buy on TCGplayer") -> str:
    if not url:
        return ""
    return (
        f'<a class="buy-tcg buy-deck" href="{html.escape(url, quote=True)}" '
        f'target="_blank" rel="noopener">{html.escape(label)}</a>'
    )


def buy_card_link(url: str, label: str = "Buy") -> str:
    if not url:
        return ""
    return (
        f'<a class="buy-tcg buy-card" href="{html.escape(url, quote=True)}" '
        f'target="_blank" rel="noopener">{html.escape(label)}</a>'
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
    return {cid: n for cid, n in counts.items() if 1 <= n <= 4}


def list_is_complete(counts: dict[str, int]) -> bool:
    total = sum(counts.values())
    return MIN_CARDS <= total <= 60


def no_em(s: str) -> str:
    return (s or "").replace("\u2014", " - ").replace("\u2013", "-").replace("\u2015", "-")
