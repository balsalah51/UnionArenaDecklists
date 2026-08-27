#!/usr/bin/env python3
"""Render Union Arena Deck Base HTML from scraped TCG Contender + official cards."""

from __future__ import annotations

import html
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import discord_board
import uadb

COLOR_ONLY = {"purple", "red", "yellow", "green", "blue", "black"}
COLOR_MARK = re.compile(r"【\s*(?:PURPLE|RED|YELLOW|GREEN|BLUE|BLACK)\s*】", re.I)
MIN_FACE_COST = 4
HOME_RAID_LEADERS = 20
MAX_HOME_PER_TITLE = 3
RAID_RE = re.compile(r"\[raid\]", re.I)
RAID_COPLAY_FRACTION = 0.5
SEARCH_RECENT_DAYS = 21
SERIES_ALIASES = {
    "100 girlfriends": "100 Girlfriends",
    "attack on titan": "Attack On Titan",
    "black clover": "Black Clover",
    "bleach": "Bleach",
    "bleach thousand year blood war": "Bleach",
    "chainsaw man": "Chainsaw Man",
    "code geass": "Code Geass",
    "code geass lelouch of the rebellion": "Code Geass",
    "demon slayer": "Demon Slayer",
    "demon slayer kimetsu no yaiba": "Demon Slayer",
    "evangelion": "Evangelion",
    "evangelion new theatrical edition": "Evangelion",
    "fullmetal alchemist": "Fullmetal Alchemist",
    "goddess of victory nikke": "Nikke",
    "hunter x hunter": "Hunter x Hunter",
    "inuyasha": "Inuyasha",
    "jujutsu kaisen": "Jujutsu Kaisen",
    "kagurabachi": "Kagurabachi",
    "kaiju no 8": "Kaiju No. 8",
    "my hero academia": "My Hero Academia",
    "my hero acadamia": "My Hero Academia",
    "nikke": "Nikke",
    "one punch man": "One Punch Man",
    "re zero": "Re:Zero",
    "re zero starting life in another world": "Re:Zero",
    "rurouni kenshin": "Rurouni Kenshin",
    "sakamoto days": "Sakamoto Days",
    "solo leveling": "Solo Leveling",
    "sword art online": "Sword Art Online",
    "that time i got reincarnated as a slime": "That Time I Got Reincarnated As A Slime",
    "the 100 girlfriends who really really really really really love you": "100 Girlfriends",
    "tokyo ghoul": "Tokyo Ghoul",
    "yu yu hakusho": "Yu Yu Hakusho",
    "yu yu hakusho ghost files": "Yu Yu Hakusho",
    "jjk": "Jujutsu Kaisen",
    "sl": "Solo Leveling",
    "slg": "Solo Leveling",
    "csm": "Chainsaw Man",
    "eva": "Evangelion",
    "smd": "Sakamoto Days",
    "rnk": "Rurouni Kenshin",
    "kgr": "Kagurabachi",
    "sao": "Sword Art Online",
    "tsk": "That Time I Got Reincarnated As A Slime",
    "tensura": "That Time I Got Reincarnated As A Slime",
    "tkg": "Tokyo Ghoul",
    "blc": "Bleach",
    "opm": "One Punch Man",
    "cgh": "Code Geass",
    "aot": "Attack On Titan",
    "fma": "Fullmetal Alchemist",
    "htr": "Hunter x Hunter",
    "hxh": "Hunter x Hunter",
    "kmy": "Demon Slayer",
    "iys": "Inuyasha",
    "rly": "100 Girlfriends",
    "yyh": "Yu Yu Hakusho",
    "bcv": "Black Clover",
    "mha": "My Hero Academia",
    "nik": "Nikke",
    "rez": "Re:Zero",
}

AMAZON_SHORT = "As an Amazon Associate I earn from qualifying purchases."
SHOP_GROUP_META = [
    ("Sleeves", "packs", "Card sleeves on Amazon"),
    ("Dice", "sets", "Dice on Amazon"),
    ("Playmats", "mats", "Playmats on Amazon"),
    ("Deck boxes", "boxes", "Deck boxes on Amazon"),
    ("Desk", "items", "Desk extras on Amazon"),
]
SHOP_ITEMS = [
    {
        "group": "Sleeves",
        "name": "Dragon Shield Matte Jet",
        "note": "100 standard-size sleeves",
        "href": "https://amzn.to/4qFzNrw",
        "asin": "B073G88D1M",
        "kind": "sleeves",
    },
    {
        "group": "Sleeves",
        "name": "Dragon Shield Matte Dual Red/Gold",
        "note": "100 standard-size sleeves",
        "href": "https://amzn.to/46s2YVu",
        "asin": "B0DJQRPPLV",
        "kind": "sleeves",
    },
    {
        "group": "Sleeves",
        "name": "Dragon Shield Matte Dual Soul",
        "note": "100 standard-size sleeves",
        "href": "https://amzn.to/4wMuTKw",
        "asin": "B0CRRPCT5P",
        "kind": "sleeves",
    },
    {
        "group": "Sleeves",
        "name": "Dragon Shield Matte Midnight Blue",
        "note": "100 standard-size sleeves",
        "href": "https://amzn.to/4hSoJoD",
        "asin": "B0BX21VDRV",
        "kind": "sleeves",
    },
    {
        "group": "Sleeves",
        "name": "Dragon Shield Matte Dual Cobalt/Silver",
        "note": "100 standard-size sleeves",
        "href": "https://amzn.to/4wNVOFR",
        "asin": "B0D7QRNNZZ",
        "kind": "sleeves",
    },
    {
        "group": "Sleeves",
        "name": "Hard plastic toploaders, 200 ct",
        "note": "3x4 card protectors",
        "href": "https://amzn.to/4ixZmZn",
        "asin": "B0DRZNHLSB",
        "kind": "sleeves",
    },
    {
        "group": "Sleeves",
        "name": "Dragon Shield Matte Amethyst",
        "note": "100 standard-size sleeves",
        "href": "https://amzn.to/3SSyuZM",
        "asin": "B0F1FWPV6B",
        "kind": "sleeves",
    },
    {
        "group": "Dice",
        "name": "Power counter dice, 32 pcs",
        "note": "Plus and minus counters for life and damage",
        "href": "https://amzn.to/46pbKUi",
        "asin": "B0GZKFDSQF",
        "kind": "dice",
    },
    {
        "group": "Dice",
        "name": "Premium dice set with tin case",
        "note": "Collectible dice in a tin",
        "href": "https://amzn.to/4xEOaiF",
        "asin": "B0D9KW7ZC1",
        "kind": "dice",
    },
    {
        "group": "Dice",
        "name": "16mm D6 dice, blue/black",
        "note": "10 acrylic six-siders",
        "href": "https://amzn.to/4gQtpdA",
        "asin": "B09NPQL2LT",
        "kind": "dice",
    },
    {
        "group": "Playmats",
        "name": "Custom TCG playmat",
        "note": "Personalized zones, non-slip, with bag",
        "href": "https://amzn.to/4hWBnD9",
        "asin": "B0CX94HCFR",
        "kind": "playmat",
    },
    {
        "group": "Playmats",
        "name": "One Piece TCG playmat (Skeleton)",
        "note": "14x24 in with dice and bag",
        "href": "https://amzn.to/4ypjUbx",
        "asin": "B0FH1ZM5MX",
        "kind": "playmat",
    },
    {
        "group": "Deck boxes",
        "name": "Wanted poster commander box",
        "note": "100 double-sleeved, commander window",
        "href": "https://amzn.to/4xuKTlW",
        "asin": "B0G41JDRM7",
        "kind": "box",
    },
    {
        "group": "Deck boxes",
        "name": "4-pack magnetic deck boxes",
        "note": "100+ double-sleeved with dividers",
        "href": "https://amzn.to/3SSyyJ0",
        "asin": "B0G4976LFL",
        "kind": "box",
    },
    {
        "group": "Deck boxes",
        "name": "Commander box with dice tray",
        "note": "Magnetic case, 100+ double-sleeved",
        "href": "https://amzn.to/4gVNBuw",
        "asin": "B0G493DTD1",
        "kind": "box",
    },
    {
        "group": "Deck boxes",
        "name": "UAONO commander deck box",
        "note": "Commander display, 100 double-sleeved",
        "href": "https://amzn.to/4zVuIzE",
        "asin": "B0CSYX7PPK",
        "kind": "box",
    },
    {
        "group": "Desk",
        "name": "Koonie USB desk fan",
        "note": "Quiet 3-speed, USB-C, folding",
        "href": "https://amzn.to/4cc2lD5",
        "asin": "B0C27NGKCV",
        "kind": "desk",
    },
]


def load_cache() -> dict:
    cache = uadb.load_json("data/card-cache.json", {})
    extra = uadb.load_json("data/contender-cards.json", {})
    for cid, card in extra.items():
        cache.setdefault(cid, {}).update({k: v for k, v in card.items() if v})
    return cache


def archetypes_from_contender() -> list[dict]:
    fmt = uadb.load_json("data/contender-format.json", {})
    ov = uadb.load_json("data/contender-overview.json", {})
    details = fmt.get("deckDetails") or {}
    overview_decks = (ov.get("defaultOverview") or {}).get("decks") or []
    meta = {d.get("name"): d for d in overview_decks}
    updated = ((ov.get("defaultOverview") or {}).get("lastUpdated") or "")[:10]
    out = []
    for name, detail in details.items():
        key = uadb.slugify(name)
        meta_row = meta.get(name) or {}
        title_name, char_name = split_arch(name)
        out.append(
            {
                "id": key,
                "key": key,
                "name": char_name,
                "full": name,
                "from_color": char_name.lower() in COLOR_ONLY,
                "title": title_name,
                "page": f"decklists/{key}.html",
                "dir": f"decklists/{key}",
                "tier": str(meta_row.get("tier") or ""),
                "style": meta_row.get("style") or "",
                "meta_share": float(meta_row.get("metaShare") or 0),
                "updated": updated,
                "strengths": detail.get("strengths") or [],
                "weaknesses": detail.get("weaknesses") or [],
                "decklist": detail.get("decklist") or {},
            }
        )
    out.sort(key=lambda a: (-a["meta_share"], a["full"]))
    return out


def split_arch(name: str) -> tuple[str, str]:
    if " - " in name:
        left, right = name.split(" - ", 1)
        return left.strip(), right.strip()
    return name, name


def norm_name(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def resolve_card(
    label: str,
    title_hint: str,
    cache: dict,
    used_numbers: set[str] | None = None,
) -> str | None:
    used_numbers = used_numbers or set()
    label = (label or "").strip()
    if not label:
        return None

    def pick(cids: list[str]) -> str | None:
        if not cids:
            return None
        titled = [
            cid
            for cid in cids
            if title_matches(title_hint, cid, (cache.get(cid) or {}).get("title") or "")
        ]
        pool = titled or list(cids)
        unused = [cid for cid in pool if uadb.legal_number(cid) not in used_numbers]
        pool = unused or pool
        pool.sort(key=lambda cid: _feature_score(cid, cache.get(cid) or {}), reverse=True)
        return pool[0]

    exact = []
    want_exact = norm_name(label)
    for cid, meta in cache.items():
        if cid.endswith(("_p1", "_p2")) or "/" not in cid:
            continue
        if norm_name(meta.get("name") or "") == want_exact:
            exact.append(cid)
    if exact:
        return pick(exact)

    name, number = uadb.parse_named_card(label)
    want = norm_name(name)
    scored = []
    for cid, meta in cache.items():
        if cid.endswith(("_p1", "_p2")):
            continue
        mname = norm_name(meta.get("name") or "")
        mname_base, mnum = uadb.parse_named_card(meta.get("name") or "")
        base = norm_name(mname_base)
        if want not in (mname, base) and base not in want and want not in base:
            continue
        if number:
            num = uadb.legal_number(cid)
            if not (num.endswith("-" + number) or cid.endswith("-" + number) or (mnum and mnum == number)):
                continue
        score = 0
        if want and want == base:
            score += 40
        elif want and want == mname:
            score += 30
        if number:
            score += 50
        mt = norm_name(meta.get("title") or "")
        title_n = norm_name(title_hint)
        if title_n and title_n[:8] and title_n[:8] in mt:
            score += 10
        if "BT/" in cid:
            score += 25
        if cid.startswith("UEPR"):
            score -= 20
        if "/" not in cid:
            score -= 40
        if meta.get("category", "").lower().startswith("character"):
            score += 1
        scored.append((score, cid))
    if not scored:
        return None
    scored.sort(key=lambda row: (row[0], "BT/" in row[1], row[1]), reverse=True)
    ranked = [cid for _score, cid in scored]
    return pick(ranked)


def legalize_items(items: list[dict], cache: dict, cap_restricted: bool = False) -> list[dict]:
    grouped: dict[tuple[str, str], dict] = {}
    order: list[tuple[str, str]] = []
    for it in items:
        cid = it.get("id") or ""
        if it.get("group") == "AP cards" or "UNRESOLVED" in cid:
            key = ("unique", cid or it.get("name") or "")
        else:
            key = ("card", uadb.legal_number(cid) or cid)
        if key not in grouped:
            grouped[key] = {
                "count": int(it.get("count") or 0),
                "id": cid,
                "name": it.get("name") or cid,
                "group": it.get("group") or "Characters",
            }
            order.append(key)
            continue
        row = grouped[key]
        row["count"] += int(it.get("count") or 0)
        other = cid
        cur = row["id"]
        if _feature_score(other, cache.get(other) or {}) > _feature_score(cur, cache.get(cur) or {}):
            row["id"] = other
            if cache.get(other, {}).get("name"):
                row["name"] = it.get("name") or row["name"]
    out = []
    for key in order:
        row = grouped[key]
        cap = uadb.max_copies(row["id"], cap_restricted=cap_restricted)
        row["count"] = min(int(row["count"]), cap)
        if row["count"] > 0:
            out.append(row)
    return out


def flatten_contender(arch: dict, cache: dict) -> list[dict]:
    dl = arch.get("decklist") or {}
    numbered = []
    pending = []
    for card in dl.get("main") or []:
        _name, number = uadb.parse_named_card(card.get("name") or "")
        (numbered if number else pending).append(card)
    items = []
    used: set[str] = set()

    def add_main(card: dict) -> None:
        label = card.get("name") or ""
        cid = resolve_card(label, arch.get("title") or "", cache, used)
        if not cid:
            cid = f"UNRESOLVED/{uadb.slugify(label)}"
        items.append(
            {
                "count": int(card.get("copies") or 0),
                "id": cid,
                "name": label,
                "group": uadb.group_for(card.get("cardType") or cache.get(cid, {}).get("category") or ""),
            }
        )
        if "UNRESOLVED" not in cid:
            used.add(uadb.legal_number(cid))

    for card in numbered:
        add_main(card)
    for card in pending:
        add_main(card)
    for card in dl.get("ap") or []:
        label = card.get("name") or "Action Point"
        cid = resolve_card(label, arch.get("title") or "", cache) or f"AP/{uadb.slugify(label)}"
        items.append(
            {
                "count": int(card.get("copies") or 0),
                "id": cid,
                "name": label,
                "group": "AP cards",
            }
        )
    return legalize_items([it for it in items if it["count"] > 0], cache, cap_restricted=True)


def flatten_counts(counts: dict[str, int], cache: dict) -> list[dict]:
    items = []
    for cid, n in counts.items():
        meta = cache.get(cid) or {}
        items.append(
            {
                "count": int(n),
                "id": cid,
                "name": meta.get("name") or cid,
                "group": uadb.group_for(meta.get("category") or "Character"),
            }
        )
    return legalize_items(items, cache, cap_restricted=False)


def _feature_score(cid: str, meta: dict) -> tuple:
    num = 0
    m = re.search(r"-(\d{3})$", cid)
    if m:
        num = int(m.group(1))
    bt = 1 if "BT/" in cid else 0
    promo = 0 if cid.startswith("UEPR") else 1
    return (promo, bt, num, cid)


def title_matches(title: str, cid: str, card_title: str) -> bool:
    t = norm_name(title)
    ct = norm_name(card_title)
    if not t:
        return True
    if t in ct or ct in t:
        return True
    code = re.sub(r"[^a-z0-9]", "", t)
    if 2 <= len(code) <= 4:
        needle = f"/{code.upper()}-"
        if needle in cid.upper():
            return True
    return False


def card_character(name: str) -> str:
    base, _num = uadb.parse_named_card(name or "")
    return uadb.display_name(base)


def strip_color_marks(s: str) -> str:
    s = COLOR_MARK.sub("", s or "")
    s = uadb.no_em(s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s*·\s*", " · ", s)
    return s.strip(" ·-")


def card_cost(meta: dict) -> int | None:
    raw = meta.get("cost")
    if raw is None or raw == "":
        return None
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def card_color(meta: dict) -> str:
    return (meta.get("color") or "").split(";")[0].split("/")[0].strip().lower()


def is_character_card(meta: dict, item: dict | None = None) -> bool:
    cat = (meta.get("category") or (item or {}).get("group") or "").lower()
    return "character" in cat


def is_raid_meta(meta: dict) -> bool:
    blob = f"{meta.get('effect') or ''} {meta.get('trigger') or ''}"
    return bool(RAID_RE.search(blob))


def combo_has_raid_face(arch: dict, cache: dict, features: dict) -> bool:
    feat = features.get(arch.get("key") or "") or {}
    meta = feat.get("meta") or {}
    if is_raid_meta(meta) and (card_cost(meta) or 0) >= MIN_FACE_COST:
        return True
    want = norm_name(arch.get("name") or "")
    color = card_color(meta) or card_color({"color": arch.get("color") or ""})
    for it in arch.get("cons_items") or []:
        cid = it.get("id") or ""
        card = cache.get(cid) or {}
        if not is_character_card(card, it):
            continue
        cost = card_cost(card)
        if cost is None or cost < MIN_FACE_COST or not is_raid_meta(card):
            continue
        name = card_character(card.get("name") or it.get("name") or "")
        if norm_name(name) != want:
            continue
        if color and card_color(card) != color:
            continue
        return True
    return False


def raid_names_in_items(items: list[dict] | None, cache: dict) -> set[str]:
    names: set[str] = set()
    for it in items or []:
        if it.get("group") == "AP cards":
            continue
        meta = cache.get(it.get("id") or "") or {}
        if not is_character_card(meta, it):
            continue
        if (card_cost(meta) or 0) < MIN_FACE_COST or not is_raid_meta(meta):
            continue
        nkey = norm_name(card_character(meta.get("name") or it.get("name") or ""))
        if nkey and nkey not in COLOR_ONLY:
            names.add(nkey)
    return names


def arch_raid_names(arch: dict, cache: dict) -> set[str]:
    """Raid namesakes that show up in most of this archetype's 50s."""
    want = norm_name(arch.get("name") or "")
    counts: Counter[str] = Counter()
    n = 0
    for entry in arch.get("lists") or []:
        names = raid_names_in_items(entry.get("items") or [], cache)
        if not names:
            continue
        n += 1
        counts.update(names)
    if n == 0:
        names = raid_names_in_items(arch.get("cons_items") or [], cache)
        if want and want not in COLOR_ONLY:
            names.add(want)
        return names
    frequent = {name for name, c in counts.items() if c / n >= RAID_COPLAY_FRACTION}
    if want and want not in COLOR_ONLY:
        frequent.add(want)
    return frequent


def arch_face_price(arch: dict, features: dict, prices: dict | None) -> float:
    feat = features.get(arch.get("key") or "") or {}
    return uadb.tcgplayer_median_price(feat.get("id") or "", prices or {})


def current_raid_priority() -> dict[str, float]:
    """Character-name → current Standard share from TCG Contender."""
    ov = uadb.load_json("data/contender-overview.json", {})
    decks = (ov.get("defaultOverview") or {}).get("decks") or []
    out: dict[str, float] = {}
    for deck in decks:
        _, char = split_arch(deck.get("name") or "")
        nkey = norm_name(char)
        if not nkey or nkey in COLOR_ONLY:
            continue
        recent = float((deck.get("metaShares") or {}).get("recent30d") or 0)
        share = float(deck.get("metaShare") or 0)
        out[nkey] = max(out.get(nkey, 0.0), recent, share)
    return out


def pick_home_raid_leaders(
    combo_arches: list[dict],
    cache: dict,
    features: dict,
    meta_priority: dict[str, float] | None = None,
    prices: dict | None = None,
) -> list[dict]:
    """Top 20 namesake raid faces, one raider per archetype.

    If a 50 plays several raiders, keep the one with the highest TCGplayer
    listed-median price as the face of that cluster.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=SEARCH_RECENT_DAYS)).date().isoformat()
    priority = current_raid_priority() if meta_priority is None else meta_priority
    prices = prices or {}
    best_by_name: dict[str, dict] = {}
    for arch in combo_arches:
        nkey = norm_name(arch.get("name") or "")
        if not nkey or nkey in COLOR_ONLY:
            continue
        prev = best_by_name.get(nkey)
        if prev is None or len(arch.get("lists") or []) > len(prev.get("lists") or []):
            best_by_name[nkey] = arch

    scored = []
    score_by_key: dict[str, float] = {}
    for nkey, arch in best_by_name.items():
        lists = arch.get("lists") or []
        n = len(lists)
        if n < 1:
            continue
        recent_n = sum(1 for e in lists if (e.get("date") or "") >= cutoff)
        meta_share = max(float(arch.get("meta_share") or 0), float(priority.get(nkey) or 0))
        named_deck = nkey in priority or float(arch.get("meta_share") or 0) > 0
        if not named_deck:
            continue
        raid_bonus = 80 if combo_has_raid_face(arch, cache, features) else 0
        score = meta_share * 10000 + recent_n * 25 + n * 0.5 + raid_bonus
        if named_deck:
            score += 200
        score_by_key[arch.get("key") or nkey] = score
        scored.append((score, meta_share, recent_n, n, arch.get("name") or "", arch))
    scored.sort(key=lambda row: (row[0], row[1], row[2], row[3], row[4]), reverse=True)

    def pick_cluster_face(arch: dict) -> dict:
        raid_ns = arch_raid_names(arch, cache)
        cands = [best_by_name[n] for n in raid_ns if n in best_by_name]
        if not cands:
            cands = [arch]
        return max(
            cands,
            key=lambda a: (
                arch_face_price(a, features, prices),
                score_by_key.get(a.get("key") or "", 0.0),
                len(a.get("lists") or []),
                a.get("name") or "",
            ),
        )

    cluster_score: dict[str, float] = defaultdict(float)
    faces: dict[str, dict] = {}
    for row in scored:
        arch = row[5]
        face = pick_cluster_face(arch)
        key = face.get("key") or ""
        if not key:
            continue
        cluster_score[key] = max(cluster_score[key], row[0])
        faces.setdefault(key, face)

    ranked = sorted(
        faces.values(),
        key=lambda a: (
            cluster_score.get(a.get("key") or "", 0.0),
            arch_face_price(a, features, prices),
            len(a.get("lists") or []),
            a.get("name") or "",
        ),
        reverse=True,
    )
    picked: list[dict] = []
    per_title: dict[str, int] = defaultdict(int)
    for arch in ranked:
        title = arch.get("title") or ""
        if per_title[title] >= MAX_HOME_PER_TITLE:
            continue
        picked.append(arch)
        per_title[title] += 1
        if len(picked) >= HOME_RAID_LEADERS:
            break
    return picked


def build_character_search(
    published: list[dict],
    combo_arches: list[dict],
    cache: dict,
    features: dict,
) -> list[dict]:
    chars: dict[str, dict] = {}
    for entry in published:
        href = entry.get("href") or ""
        list_row = {
            "href": href,
            "title": uadb.no_em(entry.get("title") or ""),
            "sub": uadb.no_em(entry.get("subtitle") or ""),
            "date": entry.get("date") or "",
        }
        seen = set()
        for it in entry.get("items") or []:
            if it.get("group") == "AP cards":
                continue
            meta = cache.get(it.get("id") or "") or {}
            if not is_character_card(meta, it):
                continue
            name = card_character(meta.get("name") or it.get("name") or "")
            nkey = norm_name(name)
            if not nkey or nkey in COLOR_ONLY or nkey in seen:
                continue
            seen.add(nkey)
            rec = chars.setdefault(
                nkey,
                {"name": name, "norm": nkey, "hubs": [], "lists": [], "_hrefs": set()},
            )
            if href and href not in rec["_hrefs"]:
                rec["_hrefs"].add(href)
                rec["lists"].append(list_row)
    for arch in combo_arches:
        nkey = norm_name(arch.get("name") or "")
        if not nkey or nkey in COLOR_ONLY:
            continue
        feat = features.get(arch["key"]) or {}
        color = ((feat.get("meta") or {}).get("color") or arch.get("color") or "").strip()
        rec = chars.setdefault(
            nkey,
            {"name": arch.get("name") or nkey, "norm": nkey, "hubs": [], "lists": [], "_hrefs": set()},
        )
        rec["hubs"].append(
            {
                "href": f"/{arch['page']}",
                "label": arch.get("full") or arch.get("name") or "",
                "color": color,
                "n": len(arch.get("lists") or []),
            }
        )
    out = []
    for rec in chars.values():
        rec["lists"].sort(key=lambda r: r.get("date") or "", reverse=True)
        rec["lists"] = rec["lists"][:150]
        rec["hubs"].sort(key=lambda h: (-int(h.get("n") or 0), h.get("label") or ""))
        rec.pop("_hrefs", None)
        if rec["lists"] or rec["hubs"]:
            out.append(rec)
    out.sort(key=lambda r: (-len(r["lists"]), r["name"]))
    return out


def entry_series(entry: dict, cache: dict) -> str:
    title = entry.get("title") or ""
    if " - " in title:
        found = series_name(title.split(" - ", 1)[0])
        if found and found != "Other":
            return found
    counts: Counter[str] = Counter()
    for it in entry.get("items") or []:
        meta = cache.get(it.get("id") or "") or {}
        sname = series_name(meta.get("title") or "")
        if sname and sname != "Other":
            counts[sname] += int(it.get("count") or 0)
    return counts.most_common(1)[0][0] if counts else ""


def series_alias_list(name: str) -> list[str]:
    nkey = norm_name(name)
    aliases = {nkey}
    for alias, target in SERIES_ALIASES.items():
        if norm_name(target) == nkey:
            aliases.add(alias)
    return sorted(a for a in aliases if a)


def build_series_search(
    published: list[dict],
    combo_arches: list[dict],
    cache: dict,
    features: dict,
) -> list[dict]:
    series: dict[str, dict] = {}
    for entry in published:
        sname = entry_series(entry, cache)
        nkey = norm_name(sname)
        if not nkey:
            continue
        href = entry.get("href") or ""
        rec = series.setdefault(
            nkey,
            {
                "name": sname,
                "norm": nkey,
                "kind": "series",
                "aliases": [],
                "hubs": [],
                "lists": [],
                "_hrefs": set(),
            },
        )
        if href and href not in rec["_hrefs"]:
            rec["_hrefs"].add(href)
            rec["lists"].append(
                {
                    "href": href,
                    "title": uadb.no_em(entry.get("title") or ""),
                    "sub": uadb.no_em(entry.get("subtitle") or ""),
                    "date": entry.get("date") or "",
                }
            )
    for arch in combo_arches:
        sname = arch.get("title") or ""
        nkey = norm_name(sname)
        if not nkey:
            continue
        feat = features.get(arch["key"]) or {}
        color = ((feat.get("meta") or {}).get("color") or arch.get("color") or "").strip()
        rec = series.setdefault(
            nkey,
            {
                "name": sname,
                "norm": nkey,
                "kind": "series",
                "aliases": [],
                "hubs": [],
                "lists": [],
                "_hrefs": set(),
            },
        )
        rec["hubs"].append(
            {
                "href": f"/{arch['page']}",
                "label": arch.get("full") or arch.get("name") or "",
                "color": color,
                "n": len(arch.get("lists") or []),
            }
        )
    out = []
    for rec in series.values():
        rec["lists"].sort(key=lambda r: r.get("date") or "", reverse=True)
        rec["lists"] = rec["lists"][:150]
        rec["hubs"].sort(key=lambda h: (-int(h.get("n") or 0), h.get("label") or ""))
        rec["aliases"] = series_alias_list(rec["name"])
        rec["href"] = series_href(rec["name"])
        rec.pop("_hrefs", None)
        if rec["lists"] or rec["hubs"]:
            out.append(rec)
    out.sort(key=lambda r: (-len(r["lists"]), r["name"]))
    return out


def char_search_html() -> str:
    return """        <div class="char-search" data-char-search>
          <label class="char-search-label">Search a character or title
            <input type="search" placeholder="Sung Jinwoo, JJK, Solo Leveling…" autocomplete="off" aria-label="Search a character or title" />
          </label>
          <p class="muted char-search-hint">Characters or anime titles. Results are the lists from that faction.</p>
          <div class="char-search-results" data-char-results hidden></div>
        </div>"""


def series_name(title: str) -> str:
    pretty = pretty_anime(title)
    for raw in (pretty, title):
        key = re.sub(r"[^a-z0-9]+", " ", (raw or "").lower()).strip()
        if key in SERIES_ALIASES:
            return SERIES_ALIASES[key]
    return pretty or title or "Other"


def collector_num(cid: str) -> int:
    m = re.search(r"-(\d{3})$", cid or "")
    return int(m.group(1)) if m else 0


def namesake_copies(items: list[dict], character: str, color: str, cache: dict) -> int:
    want = norm_name(character)
    total = 0
    for it in items:
        meta = cache.get(it.get("id") or "") or {}
        if not is_character_card(meta, it):
            continue
        if card_color(meta) != color:
            continue
        name = card_character(meta.get("name") or it.get("name") or "")
        if norm_name(name) != want:
            continue
        total += int(it.get("count") or 0)
    return total


def list_has_character_color(items: list[dict], character: str, color: str, cache: dict) -> bool:
    return namesake_copies(items, character, color, cache) > 0


def four_cost_combos(items: list[dict], cache: dict) -> list[tuple[str, str, str, dict, str]]:
    """Unique (character, color) pairs that have a 4+ cost character in this list."""
    seen: set[tuple[str, str]] = set()
    out = []
    for it in items:
        cid = it.get("id") or ""
        meta = cache.get(cid) or {}
        if not is_character_card(meta, it):
            continue
        cost = card_cost(meta)
        if cost is None or cost < MIN_FACE_COST:
            continue
        color = card_color(meta)
        if not color:
            continue
        name = card_character(meta.get("name") or it.get("name") or "")
        if not name or norm_name(name) in COLOR_ONLY:
            continue
        pair = (norm_name(name), color)
        if pair in seen:
            continue
        seen.add(pair)
        out.append((name, color, series_name(meta.get("title") or ""), meta, cid))
    return out


def pick_combo_face(entries: list[dict], character: str, color: str, cache: dict) -> dict:
    best = None
    best_key = None
    want = norm_name(character)
    for entry in entries:
        for it in entry.get("items") or []:
            cid = it.get("id") or ""
            meta = cache.get(cid) or {}
            if not is_character_card(meta, it):
                continue
            if card_color(meta) != color:
                continue
            name = card_character(meta.get("name") or it.get("name") or "")
            if norm_name(name) != want:
                continue
            cost = card_cost(meta)
            if cost is None or cost < MIN_FACE_COST:
                continue
            key = (cost, 1 if "BT/" in cid else 0, 0 if cid.startswith("UEPR") else 1, collector_num(cid), cid)
            if best_key is None or key > best_key:
                best_key = key
                best = {
                    "id": cid,
                    "name": meta.get("name") or name,
                    "meta": meta,
                    "character": name,
                }
    return best or {}


def list_main_n(entry: dict) -> int:
    return sum(int(it.get("count") or 0) for it in (entry.get("items") or []) if it.get("group") != "AP cards")


def list_has_high_copies(entry: dict) -> bool:
    for it in entry.get("items") or []:
        num = uadb.legal_number(it.get("id") or "")
        if num in uadb.HIGH_COPY_NUMBERS and int(it.get("count") or 0) > 4:
            return True
    return False


def pick_combo_sample(entries: list[dict], display: str, color: str, cache: dict) -> dict:
    """Prefer a complete 50 that uses a special copy-cap card when lists play it that way."""
    special = [e for e in entries if list_has_high_copies(e) and list_main_n(e) >= uadb.MIN_CARDS]
    if special:
        special.sort(key=lambda e: (e.get("date") or "0000", list_main_n(e)), reverse=True)
        return special[0]
    cont = [
        e
        for e in entries
        if e.get("kind") == "contender" and list_has_character_color(e.get("items") or [], display, color, cache)
    ]
    if cont:
        return cont[0]
    return max(
        entries,
        key=lambda e: (
            namesake_copies(e.get("items") or [], display, color, cache),
            e.get("date") or "0000",
        ),
    )


def pick_feature(items: list[dict], cache: dict, prefer_name: str | None = None) -> dict:
    def char_of(it: dict) -> str:
        meta = cache.get(it.get("id") or "") or {}
        return card_character(meta.get("name") or it.get("name") or "")

    pool = [it for it in items if it.get("group") != "AP cards"]
    use = [it for it in pool if it.get("group") == "Characters"] or pool
    prefer_n = norm_name(prefer_name or "")
    if prefer_n and prefer_n not in COLOR_ONLY:
        matched = [it for it in use if prefer_n in norm_name(char_of(it))]
        if matched:
            use = matched
    totals: dict[str, int] = defaultdict(int)
    by_name: dict[str, list] = defaultdict(list)
    for it in use:
        name = char_of(it)
        if not name or norm_name(name) in COLOR_ONLY:
            continue
        totals[name] += int(it.get("count") or 0)
        by_name[name].append((it, cache.get(it["id"]) or {}))
    if not totals:
        if pool:
            it = pool[0]
            meta = cache.get(it["id"]) or {}
            return {
                "id": it["id"],
                "name": meta.get("name") or it.get("name") or "",
                "meta": meta,
                "character": card_character(meta.get("name") or it.get("name") or ""),
            }
        return {"id": "", "name": prefer_name or "", "meta": {}, "character": prefer_name or ""}
    best = max(totals, key=lambda n: (totals[n], len(n)))
    cands = by_name[best]
    cands.sort(
        key=lambda row: (
            (card_cost(row[1]) or -1) >= MIN_FACE_COST,
            card_cost(row[1]) or -1,
            *_feature_score(row[0]["id"], row[1]),
        ),
        reverse=True,
    )
    it, meta = cands[0]
    return {
        "id": it["id"],
        "name": meta.get("name") or it.get("name") or best,
        "meta": meta,
        "character": best,
    }


def face_card(character: str, title: str, cache: dict) -> dict:
    char_n = norm_name(character)
    if not char_n or char_n in COLOR_ONLY:
        return {}
    cands = []
    for cid, meta in cache.items():
        if "/" not in cid or cid.startswith("UEPR") or cid.endswith(("_p1", "_p2")):
            continue
        base, _num = uadb.parse_named_card(meta.get("name") or "")
        base_n = norm_name(base)
        if char_n not in base_n:
            continue
        if title and not title_matches(title, cid, meta.get("title") or ""):
            continue
        exact = 1 if base_n == char_n else 0
        cands.append((cid, meta, exact))
    if not cands:
        return {}
    costly = [row for row in cands if (card_cost(row[1]) or -1) >= MIN_FACE_COST]
    if costly:
        cands = costly
    cands.sort(
        key=lambda row: (
            row[2],
            card_cost(row[1]) or -1,
            *_feature_score(row[0], row[1]),
        ),
        reverse=True,
    )
    cid, meta, _exact = cands[0]
    return {"id": cid, "name": meta.get("name") or cid, "meta": meta, "character": character}


def apply_archetype(arch: dict, items: list[dict], cache: dict) -> dict:
    prefer = None if arch.get("from_color") else arch.get("name")
    from_list = pick_feature(items, cache, prefer)
    char = from_list.get("character") or arch.get("name") or ""
    anime = pretty_anime(arch.get("title") or "")
    if anime:
        arch["title"] = anime
    if char and norm_name(char) not in COLOR_ONLY:
        arch["name"] = char
        arch["full"] = f"{anime} - {char}" if anime and norm_name(anime) != norm_name(char) else char
    face = face_card(arch["name"], arch.get("title") or "", cache)
    return face if face.get("id") else from_list


def identity_for_list(items: list[dict], cache: dict, arch: dict) -> dict:
    from_list = pick_feature(items, cache, arch.get("name"))
    char = from_list.get("character") or arch.get("name") or ""
    face = face_card(char, arch.get("title") or "", cache)
    if face.get("id"):
        face["character"] = char
        return face
    return from_list


def unique_arches(arches: list[dict]) -> list[dict]:
    ordered = [a for a in arches if not a.get("from_color")] + [a for a in arches if a.get("from_color")]
    seen = set()
    picked = []
    for arch in ordered:
        ident = (norm_name(arch.get("title") or ""), norm_name(arch.get("name") or ""))
        if ident in seen:
            continue
        seen.add(ident)
        picked.append(arch)
    rank = {a["key"]: i for i, a in enumerate(arches)}
    picked.sort(key=lambda a: rank.get(a["key"], 10_000))
    return picked


def build_character_color_hubs(
    published: list[dict],
    cache: dict,
    source_arches: list[dict],
) -> tuple[list[dict], dict]:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    names: dict[tuple[str, str], str] = {}
    titles: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for entry in published:
        for name, color, title, _meta, _cid in four_cost_combos(entry.get("items") or [], cache):
            pair = (norm_name(name), color)
            names[pair] = name
            if title:
                titles[pair][title] += 1
            groups[pair].append(entry)

    combo_keys = set(groups)
    groups = defaultdict(list)
    seen_href: dict[tuple[str, str], set[str]] = defaultdict(set)
    for entry in published:
        items = entry.get("items") or []
        href = entry.get("href") or entry.get("slug") or ""
        found = set()
        for it in items:
            meta = cache.get(it.get("id") or "") or {}
            if not is_character_card(meta, it):
                continue
            color = card_color(meta)
            name = card_character(meta.get("name") or it.get("name") or "")
            pair = (norm_name(name), color)
            if pair not in combo_keys:
                continue
            found.add(pair)
        for pair in found:
            if href and href in seen_href[pair]:
                continue
            if href:
                seen_href[pair].add(href)
            groups[pair].append(entry)

    by_name: dict[str, list[tuple[str, list[dict]]]] = defaultdict(list)
    for (nkey, color), entries in groups.items():
        by_name[nkey].append((color, entries))

    meta_by_name: dict[str, list[dict]] = defaultdict(list)
    for arch in source_arches:
        if arch.get("from_color"):
            continue
        meta_by_name[norm_name(arch.get("name") or "")].append(arch)

    hubs = []
    features = {}
    used_keys = set()
    for nkey, color_rows in sorted(by_name.items()):
        color_rows.sort(key=lambda row: (-len(row[1]), row[0]))
        multi = len(color_rows) > 1
        display = names.get((nkey, color_rows[0][0]), color_rows[0][0])
        for i, (color, entries) in enumerate(color_rows):
            display = names.get((nkey, color), display)
            title_counts = titles.get((nkey, color)) or Counter()
            title = title_counts.most_common(1)[0][0] if title_counts else ""
            face = pick_combo_face(entries, display, color, cache)
            if not face.get("id"):
                continue
            if not title:
                title = series_name((face.get("meta") or {}).get("title") or "")
            base = uadb.slugify(display)
            key = base if not (multi and i) else f"{base}-{color}"
            if key in used_keys:
                key = f"{base}-{color}"
            if key in used_keys:
                key = f"{base}-{color}-{uadb.slugify(title)}"
            used_keys.add(key)
            entries = sorted(
                entries,
                key=lambda e: (e.get("date") or "0000", e.get("slug") or ""),
                reverse=True,
            )
            sample = pick_combo_sample(entries, display, color, cache)
            sample_items = sample.get("items") or []
            srcs = meta_by_name.get(nkey) or []
            same = [a for a in srcs if card_color({"color": a.get("color") or ""}) == color]
            src = (same or srcs or [None])[0]
            color_label = color.title()
            full = f"{title} - {display}" if title and norm_name(title) != nkey else display
            arch = {
                "id": key,
                "key": key,
                "name": display,
                "full": full,
                "from_color": False,
                "from_combo": True,
                "title": title,
                "color": (face.get("meta") or {}).get("color") or color_label,
                "page": f"decklists/{key}.html",
                "dir": f"decklists/{key}",
                "tier": (src or {}).get("tier") or "",
                "style": (src or {}).get("style") or "",
                "meta_share": float((src or {}).get("meta_share") or 0),
                "updated": (src or {}).get("updated") or "",
                "strengths": list((src or {}).get("strengths") or []),
                "weaknesses": list((src or {}).get("weaknesses") or []),
                "decklist": {},
                "lists": entries,
                "cons_items": sample.get("items") or [],
                "sample_label": "Consensus list" if sample.get("kind") == "contender" else "Featured list",
                "combo_blurb": (
                    f"Every list on this page plays {display} in {color_label}. "
                    f"{title or display} archetype, {len(entries)} public 50-card lists."
                ),
                "buy_url": uadb.tcgplayer_mass_entry_url(sample_items, cache),
            }
            hubs.append(arch)
            features[key] = face
    hubs.sort(
        key=lambda a: (
            (a.get("title") or "zzz").lower(),
            -len(a.get("lists") or []),
            a["name"].lower(),
            (a.get("color") or "").lower(),
        )
    )
    return hubs, features


def pretty_anime(name: str) -> str:
    return uadb.pretty_anime(name)


def series_slug(title: str) -> str:
    pretty = pretty_anime(title) or (title or "")
    slug = discord_board.theme_slug(pretty)
    compact = re.sub(r"[^a-z0-9]+", "", slug)
    return discord_board.THEME_ALIASES.get(compact) or discord_board.THEME_ALIASES.get(slug) or slug


def series_href(title: str) -> str:
    slug = series_slug(title)
    return f"/series/{slug}.html" if slug and slug != "title" else "/series.html"


def list_kind_label(kind: str) -> str:
    return {
        "contender": "consensus 50",
        "official": "official placing",
        "event": "event list",
        "youtube": "YouTube list",
        "web": "community list",
        "tournament": "tournament list",
        "twitter": "X list",
        "reddit": "Reddit list",
    }.get(kind or "", "decklist")


def list_doc_title(arch: dict, entry: dict) -> str:
    name = uadb.no_em(arch.get("name") or entry.get("title") or "Decklist")
    kind = list_kind_label(entry.get("kind") or "")
    date = entry.get("date") or ""
    blob = f"{entry.get('slug') or ''} {entry.get('subtitle') or ''}"
    place = ""
    m = re.search(r"(?i)\b(\d+(?:st|nd|rd|th)|winner|top\s*\d+)\b", blob)
    if m:
        place = m.group(1)
    primary = f"{name} {kind}".strip()
    if place:
        primary = f"{primary} {place}"
    if date:
        primary = f"{primary} ({date})"
    return uadb.page_title(primary)


def hub_doc_title(arch: dict) -> str:
    name = uadb.no_em(arch.get("name") or arch.get("full") or "Deck")
    key = arch.get("key") or ""
    color = (arch.get("color") or "").split(";")[0].split("/")[0].strip()
    tail = key.rsplit("-", 1)[-1].lower()
    if color and tail == color.lower() and tail in COLOR_ONLY:
        name = f"{name} {color}"
    return uadb.page_title(f"{name} decklist")


def list_doc_description(arch: dict, entry: dict) -> str:
    full = arch.get("full") or arch.get("name") or "Union Arena"
    sub = uadb.no_em(entry.get("subtitle") or "")
    kind = list_kind_label(entry.get("kind") or "")
    date = entry.get("date") or ""
    bits = [f"{full} {kind}"]
    if date:
        bits.append(date)
    if sub:
        bits.append(sub)
    bits.append("50-card Standard list with card pictures and TCGplayer links.")
    return uadb.clip_meta(" · ".join(bits))


def title_norm(arch: dict) -> str:
    return norm_name(pretty_anime(arch.get("title") or "") or arch.get("title") or "")


def hub_sort_key(arch: dict) -> tuple:
    return (
        1 if arch.get("from_color") else 0,
        1 if arch.get("from_combo") else 0,
        -len(arch.get("lists") or []),
        -float(arch.get("meta_share") or 0),
        (arch.get("name") or "").lower(),
    )


def build_title_catalog(hubs: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    order: list[str] = []
    for arch in hubs:
        title = pretty_anime(arch.get("title") or "") or arch.get("title") or ""
        key = norm_name(title)
        if not key:
            continue
        slug = series_slug(title)
        if not discord_board.is_real_theme(title, slug) or slug in COLOR_ONLY:
            continue
        rec = grouped.get(key)
        if rec is None:
            slug = series_slug(title)
            rec = {
                "name": title,
                "slug": slug,
                "page": f"series/{slug}.html",
                "href": f"/series/{slug}.html",
                "discord": f"/discord/{slug}.html",
                "hubs": [],
                "list_count": 0,
            }
            grouped[key] = rec
            order.append(key)
        rec["hubs"].append(arch)
        rec["list_count"] += len(arch.get("lists") or [])
    series = []
    for key in order:
        rec = grouped[key]
        rec["hubs"].sort(key=hub_sort_key)
        rec["characters"] = unique_arches(rec["hubs"])
        rec["hub_count"] = len(rec["characters"])
        series.append(rec)
    series.sort(key=lambda s: (-s["list_count"], s["name"]))
    return series


def catalog_for_arch(arch: dict, catalog: list[dict]) -> dict | None:
    key = title_norm(arch)
    if not key:
        return None
    for rec in catalog:
        if norm_name(rec.get("name") or "") == key:
            return rec
    return None


def related_character_hubs(arch: dict, catalog: list[dict], limit: int = 8) -> list[dict]:
    rec = catalog_for_arch(arch, catalog)
    if not rec:
        return []
    mine = norm_name(arch.get("name") or "")
    seen = {mine, arch.get("key")}
    out = []
    for other in rec.get("characters") or rec.get("hubs") or []:
        if other.get("from_color"):
            continue
        ident = norm_name(other.get("name") or "")
        if other.get("key") == arch.get("key") or ident in seen:
            continue
        seen.add(ident)
        out.append(other)
        if len(out) >= limit:
            break
    return out


def related_series(catalog: list[dict], current: dict | None, limit: int = 8) -> list[dict]:
    others = [s for s in catalog if not current or s.get("slug") != current.get("slug")]
    return others[:limit]


def render_related_hubs(heading: str, note: str, hubs: list[dict]) -> str:
    if not hubs:
        return ""
    items = []
    for arch in hubs:
        n = len(arch.get("lists") or [])
        note_line = f"{n} list" + ("" if n == 1 else "s")
        if arch.get("color"):
            note_line = f"{arch['color']} · {note_line}"
        items.append(
            f'<li><a href="/{html.escape(arch["page"])}">{html.escape(arch.get("name") or arch["page"])}'
            f'<span class="muted">{html.escape(note_line)}</span></a></li>'
        )
    return f"""        <section class="related-block" aria-label="{html.escape(heading)}">
          <div class="section-title">
            <h3>{html.escape(heading)}</h3>
            <div class="muted">{html.escape(note)}</div>
          </div>
          <ul class="related-grid">
{chr(10).join(items)}
          </ul>
        </section>"""


def render_sibling_lists(arch: dict, entry: dict, lists: list[dict]) -> str:
    others = [row for row in lists if (row.get("slug") or "") != (entry.get("slug") or "")]
    if not others:
        return ""
    items = []
    for row in others[:12]:
        href = row.get("href") or f"/{arch['dir']}/{row['slug']}.html"
        label = uadb.no_em(row.get("title") or row.get("slug") or "List")
        meta = " · ".join(bit for bit in (list_kind_label(row.get("kind") or ""), row.get("date") or "") if bit)
        items.append(
            f'<li><a href="{html.escape(href)}">{html.escape(label)}</a>'
            f'{f" <span class=\"muted\">{html.escape(meta)}</span>" if meta else ""}</li>'
        )
    return f"""        <section class="related-block">
          <div class="section-title">
            <h3>More {html.escape(arch.get("name") or "character")} lists</h3>
            <div class="muted">{len(others)} other public 50s</div>
          </div>
          <ul class="sibling-lists">
{chr(10).join(items)}
          </ul>
        </section>"""


def list_heading(arch: dict, character: str | None = None) -> str:
    anime = pretty_anime(arch.get("title") or "")
    char = (character or arch.get("name") or "").strip()
    if anime and char and norm_name(anime) != norm_name(char):
        return f"{anime} - {char}"
    return char or anime


def list_subtitle(entry: dict) -> str:
    player = strip_color_marks(entry.get("player") or "")
    if player.lower() in {"consensus", ""}:
        player = ""
    sub = strip_color_marks(entry.get("subtitle") or "")
    bits = []
    if player and player not in sub:
        bits.append(player)
    if sub:
        bits.append(sub)
    return " · ".join(bits)


def sim_text(items: list[dict]) -> str:
    return "\n".join(f"{it['count']}x{it['id']}" for it in items if it["group"] != "AP cards")


def render_text_deck(items: list[dict], cache: dict, heading: str = "Text list") -> str:
    grouped: dict[str, list] = defaultdict(list)
    for it in items:
        grouped[it["group"]].append(it)
    order = ["Characters", "Events", "Sites", "AP cards"]
    cols = []
    for group in order:
        rows = grouped.get(group) or []
        if not rows:
            continue
        rows.sort(key=lambda it: (it["id"], it["name"]))
        lines = []
        for it in rows:
            meta = cache.get(it["id"], {})
            name = uadb.display_name(meta.get("name") or it["name"])
            img = uadb.card_image_url(it["id"], cache)
            buy = uadb.buy_deck_button(uadb.tcgplayer_card_search_url(it["id"], name), "Buy")
            lines.append(
                f"""            <li class="text-line" tabindex="0">
              <span class="qty">{html.escape(str(it['count']))}x</span>
              <span class="card-title">{html.escape(name)}</span>
              <span class="muted card-id">{html.escape(it['id'])}</span>
              {buy}
              <img class="card-pop" src="{html.escape(img)}" alt="{html.escape(name)}" />
            </li>"""
            )
        cols.append(
            f"""          <div>
            <h4>{html.escape(group)}</h4>
            <ul class="text-lines">
{chr(10).join(lines)}
            </ul>
          </div>"""
        )
    actions = uadb.list_actions(uadb.copy_button(sim_text(items)))
    return f"""        <section class="text-deck">
          <div class="section-title">
            <h3>{html.escape(heading)}</h3>
            {actions}
          </div>
          <p class="muted">Hover or tap a name for the picture. Copy pastes <code>NxSET/CODE</code> lines.</p>
          <div class="text-deck-cols">
{chr(10).join(cols)}
          </div>
        </section>"""


def render_card_entry(item: dict, meta: dict, cache: dict) -> str:
    cid = item["id"]
    name = uadb.display_name(meta.get("name") or item.get("name") or cid)
    img = uadb.card_image_url(cid, cache)
    cat = meta.get("category") or item["group"].rstrip("s")
    bits = []
    if meta.get("cost"):
        bits.append(f"Energy {meta['cost']}")
    if meta.get("ap"):
        bits.append(f"AP {meta['ap']}")
    if meta.get("bp"):
        bits.append(f"{meta['bp']} BP")
    if meta.get("color"):
        bits.append(meta["color"])
    stats = " · ".join(bits)
    text = meta.get("effect") or meta.get("trigger") or ""
    buy = uadb.buy_card_link(uadb.tcgplayer_card_search_url(cid, name), "TCGplayer")
    return f"""        <article class="card-entry">
          <img src="{html.escape(img)}" alt="{html.escape(name)} {html.escape(cid)}" loading="lazy" />
          <div>
            <div class="id"><span class="qty">{html.escape(str(item['count']))}x</span>{html.escape(cid)} · {html.escape(cat)}</div>
            <h4>{html.escape(name)}</h4>
            {f'<div class="stats">{html.escape(stats)}</div>' if stats else ''}
            {f'<div class="text">{html.escape(text)}</div>' if text else ''}
            {f'<div class="card-buy">{buy}</div>' if buy else ''}
          </div>
        </article>"""


def render_deck_stats(items: list[dict], cache: dict) -> str:
    curve = {str(i): 0 for i in range(0, 8)}
    curve["8+"] = 0
    triggers = defaultdict(int)
    copies = 0
    for it in items:
        if it["group"] == "AP cards":
            continue
        n = int(it["count"])
        copies += n
        meta = cache.get(it["id"]) or {}
        try:
            cost = int(float(meta.get("cost") or 0))
        except (TypeError, ValueError):
            cost = 0
        key = "8+" if cost >= 8 else str(max(0, cost))
        curve[key] += n
        trig = (meta.get("trigger") or "none").split("]")[0].replace("[", "").strip() or "none"
        if len(trig) > 12:
            trig = trig[:12]
        triggers[trig] += n
    if copies <= 0:
        return ""
    max_c = max(curve.values()) or 1
    bars = []
    for key in [str(i) for i in range(0, 8)] + ["8+"]:
        h = int(round(56 * curve[key] / max_c)) if curve[key] else 2
        bars.append(
            f'<span style="height:{h}px" title="{html.escape(key)} energy · {curve[key]}"><em>{html.escape(key)}</em></span>'
        )
    pills = "".join(
        f'<span class="pill">{html.escape(k)} ×{v}</span>' for k, v in sorted(triggers.items(), key=lambda kv: -kv[1])[:6]
    )
    return f"""        <section class="deck-stats">
          <div class="kicker">List snapshot</div>
          <div class="stat-grid">
            <div>
              <div class="muted">Required energy curve</div>
              <div class="curve" aria-hidden="true">{"".join(bars)}</div>
            </div>
            <div>
              <div class="muted">Triggers in the 50</div>
              <div class="counter-pills">{pills}</div>
            </div>
          </div>
        </section>"""


def render_pictures(items: list[dict], cache: dict) -> str:
    grouped: dict[str, list] = defaultdict(list)
    totals: dict[str, int] = defaultdict(int)
    for it in items:
        grouped[it["group"]].append(it)
        totals[it["group"]] += it["count"]
    sections = []
    for group in ["Characters", "Events", "Sites", "AP cards"]:
        rows = grouped.get(group) or []
        if not rows:
            continue
        entries = "\n".join(
            render_card_entry(it, cache.get(it["id"], {"name": it["name"], "category": group.rstrip("s")}), cache)
            for it in rows
        )
        sections.append(
            f"""        <section class="picture-group" style="margin-top:22px">
          <div class="section-title">
            <h3>{html.escape(group)}</h3>
            <div class="muted">{totals[group]} cards</div>
          </div>
          <div class="card-grid">
{entries}
          </div>
        </section>"""
        )
    return f"""        <section class="picture-summary">
          <div class="section-title">
            <h3>Card pictures</h3>
            <div class="muted">Official Bandai art</div>
          </div>
{chr(10).join(sections)}
        </section>"""


def pretty_blurb(s: str) -> str:
    return uadb.no_em((s or "").replace("_", " "))


def take_text(arch: dict) -> str:
    if arch.get("combo_blurb"):
        return arch["combo_blurb"]
    bits = []
    if arch.get("style"):
        style = arch["style"].lower()
        article = "an" if style[:1] in "aeiou" else "a"
        bits.append(f"{arch['full']} is {article} {style} list")
    else:
        bits.append(arch["full"])
    if arch.get("tier"):
        bits.append(f"Standard tier {arch['tier']} on the latest TCG Contender snapshot")
    strengths = arch.get("strengths") or []
    if strengths:
        bits.append(pretty_blurb(strengths[0]))
    if len(strengths) > 1:
        bits.append(pretty_blurb(strengths[1]))
    return ". ".join(bits) + "."


def write_list_page(
    arch: dict,
    entry: dict,
    items: list[dict],
    cache: dict,
    feature: dict,
    siblings: list[dict] | None = None,
    catalog: list[dict] | None = None,
) -> None:
    color = uadb.color_class((feature.get("meta") or {}).get("color"))
    title = uadb.no_em(entry.get("title") or arch["name"])
    subtitle = uadb.no_em(entry.get("subtitle") or "")
    kind_note = {
        "contender": "Consensus constructed list from public Union Arena tournament results on TCG Contender. Same card numbers are merged and capped at 4 copies (1 if restricted; Shadow Soldiers up to 12).",
        "youtube": "List from a YouTube deck profile. Card pictures from the official Bandai cardlist.",
        "web": "Community list from a public deck page. Card pictures from the official Bandai cardlist.",
        "tournament": "Tournament list. Card pictures from the official Bandai cardlist.",
        "official": "Official Bandai top-placing constructed list from unionarena-tcg.com.",
        "event": "Public tournament list (TCG Contender / ExBurst and other event pages).",
        "twitter": "List posted on X.",
        "reddit": "List posted on Reddit.",
    }.get(entry.get("kind"), "Community Union Arena list.")
    source = entry.get("source_url") or "https://tcgcontender.com/unionarena/meta"
    over = [
        f"{it['id']}"
        for it in items
        if uadb.is_restricted(it["id"]) and int(it.get("count") or 0) > 1
    ]
    flag = ""
    if over:
        flag = (
            "<p class=\"muted\"><strong>Restricted:</strong> this list still plays more than one copy of "
            + ", ".join(html.escape(x) for x in over)
            + ". Bandai limited those cards to one copy each as of 17 April 2026.</p>"
        )
    main_n = sum(int(it.get("count") or 0) for it in items if it.get("group") != "AP cards")
    if entry.get("kind") == "contender" and main_n != uadb.TARGET:
        flag += (
            f"<p class=\"muted\"><strong>Copy limits:</strong> alt-art and stamp versions of the same card "
            f"number count as one card. Restricted cards are 1-ofs. Shadow Soldiers may be up to 12. "
            f"This snapshot is {main_n} cards after those caps.</p>"
        )
    buy = uadb.buy_deck_button(
        uadb.tcgplayer_mass_entry_url(items, cache),
        "Buy this list on TCGplayer",
    )
    series = catalog_for_arch(arch, catalog or [])
    series_link = series["href"] if series else (series_href(arch["title"]) if arch.get("title") else "")
    crumbs = [("/", "Home"), ("/characters.html", "Characters")]
    if series:
        crumbs.append((series["href"], series["name"]))
    crumbs.append((f"/{arch['page']}", arch["full"]))
    crumbs.append((None, "Decklist"))
    crumb_ld = [(href or f"/{arch['dir']}/{entry['slug']}.html", label) for href, label in crumbs[:-1]]
    crumb_ld.append((f"/{arch['dir']}/{entry['slug']}.html", title))
    related = render_related_hubs(
        f"More {series['name']} decks" if series else "Related decks",
        "Other character pages in this title",
        related_character_hubs(arch, catalog or []),
    )
    siblings_html = render_sibling_lists(arch, entry, siblings or [])
    more_links = [
        f'<a href="/{html.escape(arch["page"])}">{html.escape(arch["full"])} hub</a>',
        '<a href="/format.html">Standard format</a>',
        '<a href="/shop.html">Shop supplies</a>',
    ]
    if series_link:
        more_links.insert(0, f'<a href="{html.escape(series_link)}">{html.escape((series or {}).get("name") or arch.get("title") or "Title")} decks</a>')
    if series:
        more_links.append(f'<a href="{html.escape(series["discord"])}">{html.escape(series["name"])} Discord</a>')
    img = uadb.card_image_url(feature.get("id") or "", cache) if feature.get("id") else (entry.get("img") or "")
    body = f"""        {uadb.crumb_html(crumbs)}
        <h1>{html.escape(title)}</h1>
        <p>{html.escape(subtitle)}</p>
{flag}
        {f'<p class="deck-buy">{buy}</p>' if buy else ''}
{render_deck_stats(items, cache)}
{render_text_deck(items, cache)}
{render_pictures(items, cache)}
{siblings_html}
{related}
        <p class="hub-more">{' · '.join(more_links)}</p>
        <p class="muted" style="margin-top:22px">{html.escape(kind_note)} Source: <a href="{html.escape(source)}">{html.escape(source)}</a>. Images hosted by Bandai. Buy links are TCGplayer affiliate links. Fan site, not affiliated with Bandai.</p>"""
    page = uadb.page_chrome(
        list_doc_title(arch, entry),
        list_doc_description(arch, entry),
        color,
        body,
        path=f"{arch['dir']}/{entry['slug']}.html",
        image=img,
        json_ld=[uadb.website_ld(), uadb.breadcrumb_ld(crumb_ld)],
    )
    dest = uadb.ROOT / arch["dir"] / f"{entry['slug']}.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(page)


def write_hub(
    arch: dict,
    lists: list[dict],
    items: list[dict],
    cache: dict,
    feature: dict,
    catalog: list[dict] | None = None,
) -> None:
    color = uadb.color_class((feature.get("meta") or {}).get("color"))
    img = uadb.card_image_url(feature.get("id") or "", cache) if feature.get("id") else ""
    meta = feature.get("meta") or {}
    pills = []
    series = catalog_for_arch(arch, catalog or [])
    if arch.get("title"):
        href = series["href"] if series else series_href(arch["title"])
        pills.append(f'<a class="pill" href="{html.escape(href)}">{html.escape(arch["title"])}</a>')
    if meta.get("color"):
        pills.append(f'<span class="pill">{html.escape(str(meta["color"]))}</span>')
    if feature.get("id"):
        pills.append(f'<span class="pill">{html.escape(feature["id"])}</span>')
    if arch.get("tier"):
        pills.append(f'<span class="pill">Tier {html.escape(str(arch["tier"]))}</span>')
    if arch.get("style"):
        pills.append(f'<span class="pill">{html.escape(arch["style"])}</span>')
    pill_html = "".join(pills)
    effect = meta.get("effect") or meta.get("trigger") or ""
    rows = []
    for entry in lists:
        href = entry.get("href") or f"/{arch['dir']}/{entry['slug']}.html"
        right = entry.get("date") or entry.get("kind") or "View"
        copy_btn = uadb.copy_button(entry.get("sim_text") or "")
        rows.append(
            f"""            <li class="list-row">
              <a class="item" href="{html.escape(href)}">
                <div>
                  <div style="font-weight:700">{html.escape(uadb.no_em(entry.get('title') or entry['slug']))}</div>
                  <div class="muted" style="font-size:13px">{html.escape(uadb.no_em(entry.get('subtitle') or ''))}</div>
                </div>
                <div class="link">{html.escape(str(right))} →</div>
              </a>
              {uadb.list_actions(copy_btn)}
            </li>"""
        )
    filters = ""
    if len(lists) >= 8:
        filters = """          <div class="list-filters" data-hub-filters>
            <input type="search" data-filter="q" placeholder="Filter list" aria-label="Filter lists" />
          </div>
"""
    crumbs = [("/", "Home"), ("/characters.html", "Characters")]
    if series:
        crumbs.append((series["href"], series["name"]))
    crumbs.append((None, arch["full"]))
    crumb_ld = [("/", "Home"), ("/characters.html", "Characters")]
    if series:
        crumb_ld.append((series["href"], series["name"]))
    crumb_ld.append((f"/{arch['page']}", arch["full"]))
    related = render_related_hubs(
        f"More {series['name']} decks" if series else "Related decks",
        "Other characters in this anime or manga",
        related_character_hubs(arch, catalog or []),
    )
    more_links = ['<a href="/format.html">Standard format</a>', '<a href="/shop.html">Shop supplies</a>']
    if series:
        more_links.insert(0, f'<a href="{html.escape(series["href"])}">All {html.escape(series["name"])} decks</a>')
        more_links.append(f'<a href="{html.escape(series["discord"])}">{html.escape(series["name"])} on Discord</a>')
    n_lists = len(lists)
    desc = uadb.clip_meta(
        f"{arch['full']} Union Arena decklists: {n_lists} public 50-card Standard list"
        f"{'' if n_lists == 1 else 's'}"
        + (f" for {arch['title']}" if arch.get("title") else "")
        + ". Consensus core, card pictures, and related character decks."
    )
    body = f"""        {uadb.crumb_html(crumbs)}
        <div class="leader-hero">
          {f'<img src="{html.escape(img)}" alt="{html.escape(arch["full"])} Union Arena character card" />' if img else ''}
          <div>
            <h1>{html.escape(arch['full'])}</h1>
            <p>{html.escape(take_text(arch))}</p>
            <div class="stat-row">
              {pill_html}
            </div>
            {f'<div class="effect">{html.escape(effect)}</div>' if effect else ''}
            {uadb.buy_deck_button(arch.get('buy_url') or uadb.tcgplayer_mass_entry_url(items, cache), 'Buy this 50 on TCGplayer')}
          </div>
        </div>
        <section class="leader-analysis" style="margin-top:22px">
          <div class="section-title">
            <h2>How it plays</h2>
            <div class="muted">From public tournament lists</div>
          </div>
          <p class="leader-take">{html.escape(take_text(arch))}</p>
        </section>
{render_text_deck(items, cache, arch.get("sample_label") or "Consensus list")}
        <section class="deck-index" style="margin-top:22px">
          <div class="section-title">
            <h2>Decklists</h2>
            <div class="muted">{len(lists)} lists</div>
          </div>
          <p class="muted">{html.escape(arch.get("combo_blurb") or "Newest public lists first. Each row opens a separate 50-card list.")}</p>
{filters}          <ul class="list" aria-label="Decklists">
{chr(10).join(rows)}
          </ul>
        </section>
{related}
        <p class="hub-more">{' · '.join(more_links)}</p>"""
    page = uadb.page_chrome(
        hub_doc_title(arch),
        desc,
        color,
        body,
        "characters",
        path=arch["page"],
        image=img,
        json_ld=[uadb.website_ld(), uadb.breadcrumb_ld(crumb_ld)],
    )
    dest = uadb.ROOT / arch["page"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(page)


def best_in_format_card(arches: list[dict], features: dict, cache: dict) -> dict:
    ranked = [a for a in arches if a.get("meta_share")]
    ranked.sort(key=lambda a: (-float(a.get("meta_share") or 0), int(str(a.get("tier") or "99") or "99")))
    top = ranked[0] if ranked else (arches[0] if arches else None)
    if not top:
        return {}
    items = top.get("cons_items") or flatten_contender(top, cache)
    prefer = norm_name(top.get("name") or "")
    scored = []
    for it in items:
        if it.get("group") == "AP cards":
            continue
        cid = it.get("id") or ""
        if not cid or "UNRESOLVED" in cid:
            continue
        meta = cache.get(cid) or {}
        copies = int(it.get("count") or 0)
        cost = card_cost(meta) or 0
        name = norm_name(meta.get("name") or it.get("name") or "")
        cat = (meta.get("category") or it.get("group") or "").lower()
        if "character" in cat and cost < MIN_FACE_COST:
            continue
        score = copies * 10 + cost
        if prefer and prefer in name:
            score += 50
        if "character" in cat:
            score += 8
        if "BT/" in cid:
            score += 5
        if cid.startswith("UEPR"):
            score -= 20
        scored.append((score, copies, cost, cid, meta, it))
    if scored:
        scored.sort(key=lambda row: (row[0], row[2], row[1]), reverse=True)
        _score, copies, _cost, cid, meta, it = scored[0]
        return {
            "id": cid,
            "name": card_character(meta.get("name") or it.get("name") or cid),
            "meta": meta,
            "arch": top,
            "copies": copies,
        }
    feat = features.get(top["key"]) or {}
    return {
        "id": feat.get("id") or "",
        "name": card_character(feat.get("name") or top.get("name") or ""),
        "meta": feat.get("meta") or {},
        "arch": top,
        "copies": 4,
    }


def write_home(arches: list[dict], recent: list[dict], cache: dict, features: dict) -> None:
    def tile_html(arch: dict) -> str:
        f = features.get(arch["key"]) or {}
        img = uadb.card_image_url(f.get("id") or "", cache) if f.get("id") else ""
        color = ((f.get("meta") or {}).get("color") or arch.get("color") or "").strip()
        buy = uadb.buy_deck_button(arch.get("buy_url") or "", "TCGplayer")
        return f"""            <div class="leader-card">
              <a class="leader-card-link" href="/{html.escape(arch['page'])}">
                <img src="{html.escape(img)}" alt="{html.escape(arch['full'])} Union Arena character card" />
                <div class="caption">
                  <strong>{html.escape(arch['name'])}</strong>
                  <span class="hub-sub">{html.escape(color)}</span>
                </div>
              </a>
              {buy}
            </div>"""

    sections = []
    grouped: dict[str, list[dict]] = defaultdict(list)
    order = []
    for arch in arches:
        title = arch.get("title") or "Other"
        if title not in grouped:
            order.append(title)
        grouped[title].append(arch)
    for title in order:
        tiles = [tile_html(arch) for arch in grouped[title]]
        sections.append(
            f"""            <section class="home-ip">
              <h2 class="home-ip-title"><a href="{html.escape(series_href(title))}">{html.escape(title)}</a></h2>
              <div class="leader-cards home-cards" aria-label="{html.escape(title)} characters">
{chr(10).join(tiles)}
              </div>
            </section>"""
        )
    rec_items = []
    for row in recent[:100]:
        color = uadb.color_class((row.get("color") or ""))
        buy = uadb.buy_deck_button(row.get("buy_url") or "", "TCGplayer")
        rec_items.append(
            f"""            <li class="recent-row">
              <a class="recent-item {html.escape(color)}" href="{html.escape(row['href'])}">
                <img class="recent-leader" src="{html.escape(row['img'])}" alt="{html.escape(row['name'])} Union Arena decklist" />
                <div class="recent-copy">
                  <div class="who">{html.escape(row['who'])}</div>
                  <div class="muted meta">{html.escape(row['meta'])}</div>
                </div>
                <div class="when">{html.escape(row.get('when') or '')}</div>
              </a>
              {buy}
            </li>"""
        )
    best = best_in_format_card(arches, features, cache)
    splash_card = ""
    if best.get("id"):
        href = f"/{best['arch']['page']}" if best.get("arch") else "/characters.html"
        img = uadb.card_image_url(best["id"], cache)
        label = (best.get("arch") or {}).get("full") or best.get("name") or "Best in format"
        splash_card = f"""          <a class="home-splash-feature" href="{html.escape(href)}" title="{html.escape(label)}">
            <img src="{html.escape(img)}" alt="{html.escape(label)}" />
          </a>"""
    body = f"""        <section class="home-splash" aria-label="{html.escape(uadb.BRAND)}">
          <img class="home-splash-bg" src="/img/uadb-hero.png" alt="Union Arena Trading Card Game" />
{splash_card}
          <div class="home-splash-bar">
            <h1>{html.escape(uadb.BRAND)}</h1>
            <p>Jump a section, or keep scrolling into the characters.</p>
          </div>
        </section>

        <nav class="home-big3" aria-label="Main sections">
          <a class="home-big home-big-recent" href="#recent">
            <span class="home-big-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
                <path d="M8 7h11M8 12h11M8 17h11M4 7h.01M4 12h.01M4 17h.01"/>
              </svg>
            </span>
            <span class="home-big-title">Recent Lists</span>
            <span class="home-big-note">Newest published 50-card lists first</span>
          </a>
          <a class="home-big home-big-leaders" href="#characters">
            <span class="home-big-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="5" width="12" height="16" rx="2"/>
                <rect x="9" y="3" width="12" height="16" rx="2"/>
              </svg>
            </span>
            <span class="home-big-title">Characters</span>
            <span class="home-big-note">Top 20 Raiders right now</span>
          </a>
          <a class="home-big home-big-shop" href="/shop.html">
            <span class="home-big-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M6 8h12l-1 12H7L6 8z"/>
                <path d="M9 8V6a3 3 0 0 1 6 0v2"/>
              </svg>
            </span>
            <span class="home-big-title">Shop</span>
            <span class="home-big-note">Sleeves, playmats, and more</span>
          </a>
          <a class="home-big home-big-discord" href="/discord/welcome.html">
            <span class="home-big-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M19.3 5.2A17.4 17.4 0 0 0 14.9 4l-.2.4a15.2 15.2 0 0 1 3.6 1.1c-3.3-1.5-6.6-1.5-9.8 0 .4-.2.9-.4 1.3-.6l-.2-.4A17.3 17.3 0 0 0 4.7 5.2C1.9 9.4 1.1 13.5 1.5 17.5a17.7 17.7 0 0 0 5.4 2.7l.7-1.1a11.5 11.5 0 0 1-2.1-1l.2-.1c1.6.7 3.3 1.2 5.1 1.2s3.5-.4 5.1-1.2l.2.1a11.5 11.5 0 0 1-2.1 1l.7 1.1a17.7 17.7 0 0 0 5.4-2.7c.5-4.6-.7-8.7-3.8-12.3ZM8.8 14.8c-1 0-1.9-.9-1.9-2s.8-2 1.9-2 1.9.9 1.9 2-.8 2-1.9 2Zm6.4 0c-1 0-1.9-.9-1.9-2s.8-2 1.9-2 1.9.9 1.9 2-.8 2-1.9 2Z"/>
              </svg>
            </span>
            <span class="home-big-title">Discord</span>
            <span class="home-big-note">Welcome, roles, and title threads</span>
          </a>
        </nav>

        <section class="home-leaders-flow" id="characters">
          <div class="home-leaders-intro">
            <p class="home-leaders-kicker">The roster</p>
            <div class="home-leaders-intro-row">
              <div>
                <h2>Raiders</h2>
                <p>The 20 characters current Standard lists are built around. Click a picture for that character and color. Every list on the page plays them.</p>
              </div>
              <a class="home-leaders-search-link" href="/characters.html">Full roster →</a>
              <a class="home-leaders-search-link" href="/series.html">Browse titles →</a>
            </div>
{char_search_html()}
          </div>
          <div class="card home-panel home-leaders-grid">
{chr(10).join(sections)}
          </div>
        </section>

        <section class="card home-panel" id="recent">
          <div class="section-title">
            <h2>Recent lists</h2>
            <div class="muted">{len(recent)} lists</div>
          </div>
          <p class="muted">Newest published lists first.</p>
          <ul class="recent-list" aria-label="Recent decklists">
{chr(10).join(rec_items)}
          </ul>
        </section>
"""
    (uadb.ROOT / "index.html").write_text(uadb.home_chrome(body))


def write_characters_index(
    raiders: list[dict],
    features: dict,
    cache: dict,
    catalog: list[dict] | None = None,
) -> None:
    catalog = catalog or []
    series_items = []
    for rec in catalog:
        series_items.append(
            f'<li><a href="{html.escape(rec["href"])}">{html.escape(rec["name"])}'
            f'<span class="muted">{rec["hub_count"]} characters · {rec["list_count"]} lists</span></a></li>'
        )
    series_block = ""
    if series_items:
        series_block = f"""        <section class="related-block">
          <div class="section-title">
            <h2>Browse by title</h2>
            <div class="muted">{len(catalog)} anime and manga</div>
          </div>
          <p class="muted">Each title page lists every character hub and links the Discord thread.</p>
          <ul class="series-grid">{"".join(series_items)}</ul>
        </section>"""
    grouped: dict[str, list[dict]] = defaultdict(list)
    order = []
    for arch in raiders:
        title = arch.get("title") or "Other"
        if title not in grouped:
            order.append(title)
        grouped[title].append(arch)
    sections = []
    for title in order:
        tiles = []
        for arch in grouped[title]:
            f = features.get(arch["key"]) or {}
            img = uadb.card_image_url(f.get("id") or "", cache) if f.get("id") else ""
            color = uadb.color_class((f.get("meta") or {}).get("color"))
            color_label = ((f.get("meta") or {}).get("color") or arch.get("color") or "").strip()
            n_lists = len(arch.get("lists") or [])
            meta_bits = [color_label, f"{n_lists} list" + ("" if n_lists == 1 else "s")]
            if arch.get("meta_share"):
                meta_bits.append(f"{arch['meta_share']*100:.1f}% meta")
            tiles.append(
                f"""          <div class="leader-tile-wrap">
            <a class="leader-tile {html.escape(color)}" href="/{html.escape(arch['page'])}">
              <img src="{html.escape(img)}" alt="{html.escape(arch['full'])} Union Arena character card" />
              <div>
                <div class="name">{html.escape(arch['name'])}</div>
                <div class="meta">{html.escape(" · ".join(b for b in meta_bits if b))}</div>
              </div>
            </a>
            {uadb.buy_deck_button(arch.get("buy_url") or "", "TCGplayer")}
          </div>"""
            )
        sections.append(
            f"""        <section class="home-ip">
          <h2 class="home-ip-title"><a href="{html.escape(series_href(title))}">{html.escape(title)}</a></h2>
          <div class="leader-grid">
{chr(10).join(tiles)}
          </div>
        </section>"""
        )
    roster = []
    for rec in catalog:
        chars = []
        for arch in rec.get("characters") or []:
            n = len(arch.get("lists") or [])
            chars.append(
                f'<li><a href="/{html.escape(arch["page"])}">{html.escape(arch.get("name") or arch["page"])}'
                f'<span class="muted">{n} list{"" if n == 1 else "s"}</span></a></li>'
            )
        if chars:
            roster.append(
                f"""        <section class="related-block">
          <h2 class="home-ip-title"><a href="{html.escape(rec["href"])}">{html.escape(rec["name"])}</a></h2>
          <ul class="related-grid">{"".join(chars)}</ul>
        </section>"""
            )
    crumbs = [("/", "Home"), (None, "Characters")]
    body = f"""        {uadb.crumb_html(crumbs)}
        <h1>Union Arena characters</h1>
          <p>Search a character or title, jump a series page, or browse the current Raiders. The full roster below lists every public hub so crawlers and players can reach the 50s.</p>
{char_search_html()}
{series_block}
        <section>
          <h2>Raiders</h2>
          <p>The 20 characters current Standard lists are built around.</p>
{chr(10).join(sections)}
        </section>
        <section>
          <h2>Full roster by title</h2>
          <p class="muted">Every character hub on the site, grouped by anime or manga.</p>
{chr(10).join(roster)}
        </section>"""
    page = uadb.page_chrome(
        uadb.page_title("Union Arena characters and title decklists"),
        "Every Union Arena character hub and 50-card Standard list, grouped by anime and manga title. Search Raiders or browse a series.",
        "color-red",
        body,
        "characters",
        path="characters.html",
        json_ld=[
            uadb.website_ld(),
            uadb.breadcrumb_ld([("/", "Home"), ("/characters.html", "Characters")]),
        ],
    )
    (uadb.ROOT / "characters.html").write_text(page)


def write_series_index(catalog: list[dict]) -> None:
    items = []
    for rec in catalog:
        items.append(
            f'<li><a href="{html.escape(rec["href"])}">{html.escape(rec["name"])}'
            f'<span class="muted">{rec["hub_count"]} characters · {rec["list_count"]} lists</span></a></li>'
        )
    others = [
        '<a href="/characters.html">Characters</a>',
        '<a href="/format.html">Standard format</a>',
        '<a href="/discord/welcome.html">Discord</a>',
        '<a href="/shop.html">Shop</a>',
    ]
    body = f"""        {uadb.crumb_html([("/", "Home"), (None, "Titles")])}
        <h1>Union Arena titles</h1>
        <p>Every anime and manga IP with a public 50-card Standard list on this site. Open a title for character hubs, consensus lists, and the Discord thread.</p>
        <ul class="series-grid">{"".join(items)}</ul>
        <p class="hub-more">{' · '.join(others)}</p>"""
    page = uadb.page_chrome(
        uadb.page_title("Union Arena titles and anime decklists"),
        "Browse Union Arena TCG decks by anime and manga title: Solo Leveling, Yu Yu Hakusho, Evangelion, Chainsaw Man, and the rest of Standard.",
        "color-red",
        body,
        "characters",
        path="series.html",
        json_ld=[
            uadb.website_ld(),
            uadb.breadcrumb_ld([("/", "Home"), ("/series.html", "Titles")]),
            {
                "@context": "https://schema.org",
                "@type": "ItemList",
                "name": "Union Arena titles",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": i,
                        "url": uadb.absolute_url(rec["href"]),
                        "name": rec["name"],
                    }
                    for i, rec in enumerate(catalog, start=1)
                ],
            },
        ],
    )
    (uadb.ROOT / "series.html").write_text(page)


def write_series_pages(catalog: list[dict], features: dict, cache: dict) -> list[str]:
    dest = uadb.ROOT / "series"
    dest.mkdir(parents=True, exist_ok=True)
    keep = set()
    paths = ["series.html"]
    write_series_index(catalog)
    for rec in catalog:
        keep.add(f"{rec['slug']}.html")
        paths.append(rec["page"])
        write_series_page(rec, catalog, features, cache)
    for path in dest.iterdir():
        if path.is_file() and path.name not in keep:
            path.unlink()
    return paths


def write_series_page(rec: dict, catalog: list[dict], features: dict, cache: dict) -> None:
    name = rec["name"]
    hubs = [h for h in (rec.get("characters") or rec.get("hubs") or []) if not h.get("from_color")]
    tiles = []
    for arch in hubs:
        f = features.get(arch["key"]) or {}
        img = uadb.card_image_url(f.get("id") or "", cache) if f.get("id") else ""
        color = uadb.color_class((f.get("meta") or {}).get("color"))
        n = len(arch.get("lists") or [])
        img_html = (
            f'<img src="{html.escape(img)}" alt="{html.escape(arch.get("full") or arch.get("name") or name)} Union Arena character card" />'
            if img
            else ""
        )
        tiles.append(
            f"""          <div class="leader-tile-wrap">
            <a class="leader-tile {html.escape(color)}" href="/{html.escape(arch["page"])}">
              {img_html}
              <div>
                <div class="name">{html.escape(arch.get("name") or arch["page"])}</div>
                <div class="meta">{n} list{"" if n == 1 else "s"}</div>
              </div>
            </a>
          </div>"""
        )
    other_series = related_series(catalog, rec)
    other_html = ""
    if other_series:
        items = [
            f'<li><a href="{html.escape(s["href"])}">{html.escape(s["name"])}'
            f'<span class="muted">{s["hub_count"]} characters</span></a></li>'
            for s in other_series
        ]
        other_html = f"""        <section class="related-block">
          <div class="section-title">
            <h2>Other titles</h2>
            <div class="muted">More Union Arena IPs</div>
          </div>
          <ul class="series-grid">{"".join(items)}</ul>
        </section>"""
    crumbs = [("/", "Home"), ("/series.html", "Titles"), (None, name)]
    desc = uadb.clip_meta(
        f"{name} Union Arena decks: {rec['hub_count']} character hubs and {rec['list_count']} public 50-card Standard lists, plus the Discord title thread."
    )
    img = ""
    if hubs:
        feat = features.get(hubs[0]["key"]) or {}
        if feat.get("id"):
            img = uadb.card_image_url(feat["id"], cache)
    more_links = [
        f'<a href="{html.escape(rec["discord"])}">{html.escape(name)} Discord thread</a>',
        '<a href="/characters.html">All characters</a>',
        '<a href="/format.html">Standard format</a>',
        '<a href="/shop.html">Shop supplies</a>',
    ]
    body = f"""        {uadb.crumb_html(crumbs)}
        <h1>{html.escape(name)} Union Arena decks</h1>
        <p>{html.escape(name)} character pages and public 50-card Standard lists. English events are single-title, so these hubs stay in this IP.</p>
        <div class="leader-grid">
{chr(10).join(tiles)}
        </div>
{other_html}
        <p class="hub-more">{' · '.join(more_links)}</p>"""
    page = uadb.page_chrome(
        uadb.page_title(f"{name} Union Arena decks"),
        desc,
        "color-red",
        body,
        "characters",
        path=rec["page"],
        image=img,
        json_ld=[
            uadb.website_ld(),
            uadb.breadcrumb_ld([("/", "Home"), ("/series.html", "Titles"), (rec["href"], name)]),
            {
                "@context": "https://schema.org",
                "@type": "ItemList",
                "name": f"{name} Union Arena decks",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": i,
                        "url": uadb.absolute_url(f"/{arch['page']}"),
                        "name": arch.get("full") or arch.get("name") or name,
                    }
                    for i, arch in enumerate(hubs, start=1)
                ],
            },
        ],
    )
    (uadb.ROOT / rec["page"]).write_text(page)


def write_format(arches: list[dict]) -> None:
    blurbs = []
    for arch in arches[:8]:
        blurbs.append(
            f"""            <li>
              <a href="/{html.escape(arch['page'])}">{html.escape(arch['full'])}</a>
              <span class="muted">{html.escape(arch.get('style') or '')} · Tier {html.escape(arch.get('tier') or '?')}</span>
              <p>{html.escape(pretty_blurb((arch.get('strengths') or ['Public Standard list.'])[0]))}</p>
            </li>"""
        )
    body = f"""        {uadb.crumb_html([("/", "Home"), (None, "Format")])}
        <h1>Standard format</h1>
        <p>Lists on this site are 50-card constructed Union Arena decks. English events are single-title Standard. A deck is usually one IP (<a href="/series/solo-leveling.html">Solo Leveling</a>, <a href="/series/sakamoto-days.html">Sakamoto Days</a>, <a href="/series/evangelion.html">Evangelion</a>, <a href="/series/chainsaw-man.html">Chainsaw Man</a>) plus up to 4 copies of each card number. Browse every title on the <a href="/series.html">titles index</a>.</p>

        <section class="meta-take" id="meta" style="margin-top:22px">
          <div class="section-title">
            <h3>Current metagame</h3>
            <div class="muted">From lists on this site</div>
          </div>
          <p>The snapshot follows public Union Arena tournaments. Sung Jinwoo, Hajime Saito, Shin Asakura, and Rei Ayanami are the names that keep showing up. Everything else is a step down or a title specialist.</p>
          <ul class="meta-blurbs">
{chr(10).join(blurbs)}
          </ul>
        </section>

        <section style="margin-top:22px">
          <div class="section-title">
            <h3>Restricted in constructed</h3>
            <div class="muted">Effective 17 April 2026</div>
          </div>
          <p>Bandai limited <strong>Asuka Shikinami Langley <code>UE15BT/EVA-1-051</code></strong> and <strong>Spear of Gaius <code>UE15BT/EVA-1-063</code></strong> to one copy each. This site flags lists that still play more than one.</p>
          <p class="muted">Official notice: <a href="https://www.unionarena-tcg.com/na/rules/limited.php">About Banned/Restricted Cards</a>.</p>
        </section>

        <section style="margin-top:22px">
          <div class="section-title">
            <h3>Deck construction</h3>
            <div class="muted">50 cards</div>
          </div>
          <p>Exactly 50 cards in the main deck. AP cards sit next to the list, not inside the 50. Most sanctioned events are single-title. Confirm the event before mixing IPs.</p>
          <p class="muted">Official events: <a href="https://www.unionarena-tcg.com/na/events/">Bandai events hub</a>.</p>
        </section>
        <p class="hub-more"><a href="/characters.html">Characters</a> · <a href="/series.html">Titles</a> · <a href="/shop.html">Shop</a></p>"""
    page = uadb.page_chrome(
        "Union Arena format and restricted cards | Union Arena Decklists",
        "Standard constructed rules for Union Arena: 50-card lists, restricted Evangelion cards, current-format characters.",
        "color-red",
        body,
        "format",
        path="format.html",
        json_ld=[
            uadb.website_ld(),
            uadb.breadcrumb_ld([("/", "Home"), ("/format.html", "Format")]),
        ],
    )
    (uadb.ROOT / "format.html").write_text(page)


def amazon_note_html() -> str:
    return (
        f'<p class="amazon-note">{html.escape(AMAZON_SHORT)} '
        f'<a href="/privacy.html">Privacy</a></p>'
    )


def shop_cards_html(items: list[dict] | None = None) -> list[str]:
    cards = []
    for item in items or SHOP_ITEMS:
        img = f"/img/shop/{item['asin']}.jpg"
        cards.append(
            f"""            <a class="shop-card" href="{html.escape(item['href'])}" target="_blank" rel="nofollow sponsored noopener">
              <img src="{html.escape(img)}" alt="{html.escape(item['name'])}" />
              <div class="shop-card-copy">
                <div class="muted shop-kicker">{html.escape(item['group'])}</div>
                <h3>{html.escape(item['name'])}</h3>
                <p class="muted">{html.escape(item['note'])}</p>
              </div>
              <span class="buy-deck">View on Amazon</span>
            </a>"""
        )
    return cards


def write_shop() -> None:
    sections = []
    for group, unit, aria in SHOP_GROUP_META:
        rows = [it for it in SHOP_ITEMS if it["group"] == group]
        if not rows:
            continue
        sections.append(
            f"""        <section class="shop-section" style="margin-top:22px">
          <div class="section-title">
            <h3>{html.escape(group)}</h3>
            <div class="muted">{len(rows)} {html.escape(unit)}</div>
          </div>
          <div class="shop-grid" aria-label="{html.escape(aria)}">
{chr(10).join(shop_cards_html(rows))}
          </div>
        </section>"""
        )
    body = f"""        {uadb.crumb_html([("/", "Home"), (None, "Shop")])}
        <h1>Shop</h1>
        <p>Sleeves, playmats, deck boxes, and extras for Union Arena lists. Pair these with a <a href="/characters.html">character deck</a> or the <a href="/series.html">title pages</a>.</p>
{chr(10).join(sections)}
        {amazon_note_html()}
        <p class="muted" style="margin-top:12px">Prices, stock, and shipping are set by Amazon. This site does not sell these products directly.</p>"""
    page = uadb.page_chrome(
        "Shop sleeves, playmats, and more | Union Arena Decklists",
        "Dragon Shield sleeves, playmats, deck boxes, and extras for Union Arena. Amazon Associate shop links.",
        "color-red",
        body,
        "shop",
        path="shop.html",
        json_ld=[
            uadb.website_ld(),
            uadb.breadcrumb_ld([("/", "Home"), ("/shop.html", "Shop")]),
        ],
    )
    (uadb.ROOT / "shop.html").write_text(page)


def write_privacy() -> None:
    body = f"""        {uadb.crumb_html([("/", "Home"), (None, "Privacy Policy")])}
        <h1>Privacy Policy</h1>
        <p class="muted">Last updated: August 26, 2026</p>
        <p>Union Arena Decklists ("we," "us," or "this site") respects your privacy. This Privacy Policy explains what information we collect when you visit unionarenadecklists.com, how we use it, and the choices you have.</p>
        <section>
          <h3>Information We Collect</h3>
          <p><strong>Automatically collected information:</strong> Like most websites, we automatically collect certain information when you visit, including your IP address, browser type, device type, pages viewed, and time spent on the site. This is collected through cookies, log files, and similar technologies.</p>
          <p>We do not require account creation or collect personal information such as your name, email address, or payment details through this site.</p>
        </section>
        <section>
          <h3>Cookies</h3>
          <p>We use cookies and similar tracking technologies to understand how visitors use the site, remember basic preferences, and support advertising if ads are enabled.</p>
        </section>
        <section>
          <h3>Advertising</h3>
          <p>This site may display advertisements served by third-party providers, including Google AdSense. You can opt out of personalized advertising at <a href="https://adssettings.google.com/" target="_blank" rel="noopener">Google's Ads Settings</a>.</p>
        </section>
        <section>
          <h3>TCGplayer</h3>
          <p>Buy buttons on this site are TCGplayer affiliate links. If you buy through them, this site may earn a commission, at no extra cost to you.</p>
        </section>
        <section>
          <h3>Amazon</h3>
          <p>As an Amazon Associate I earn from qualifying purchases. Shop links for sleeves, playmats, and other supplies go to Amazon. A purchase through those links may earn this site a commission, at no extra cost to you. This site is not Amazon, and Amazon does not sponsor it.</p>
        </section>
        <section>
          <h3>Third-Party Links</h3>
          <p>Our site links to third-party content, including tournament results, the official Bandai cardlist, TCGplayer, Amazon, and Discord. We are not responsible for the privacy practices of these external sites.</p>
        </section>
        <section>
          <h3>Contact</h3>
          <p>Questions about this policy can go through the Discord linked in the header.</p>
        </section>"""
    page = uadb.page_chrome(
        "Privacy Policy | Union Arena Decklists",
        "Privacy Policy for Union Arena Decklists: cookies, Amazon Associate links, and TCGplayer affiliates.",
        "color-red",
        body,
        path="privacy.html",
        json_ld=[uadb.website_ld(), uadb.breadcrumb_ld([("/", "Home"), ("/privacy.html", "Privacy")])],
    )
    # privacy uses policy class
    page = page.replace('<div class="card hero">', '<div class="card hero policy">')
    (uadb.ROOT / "privacy.html").write_text(page)


def write_404() -> None:
    body = """        <nav class="crumb" aria-label="Breadcrumb"><a href="/">Home</a> / Missing page</nav>
        <h1>That page is not here</h1>
        <p>Try the <a href="/">home splash</a>, <a href="/characters.html">character pages</a>, <a href="/series.html">title pages</a>, <a href="/shop.html">shop</a>, or <a href="/#recent">recent lists</a>.</p>"""
    page = uadb.page_chrome(
        "Page not found | Union Arena Decklists",
        "That Union Arena Decklists page is missing.",
        "color-red",
        body,
        path="404.html",
        robots="noindex, follow",
    )
    (uadb.ROOT / "404.html").write_text(page)


def write_sitemap(paths: list[str], lastmod: str = "") -> None:
    stamp = lastmod or date.today().isoformat()
    skip = re.compile(r"(^discord/board\.json$|^discord/threads/|^discord/?$)")
    seen: set[str] = set()
    rows = []
    for raw in paths:
        p = (raw or "").lstrip("/")
        if p in seen or skip.search(p):
            continue
        seen.add(p)
        loc = uadb.SITE + "/" if not p else f"{uadb.SITE}/{p}"
        rows.append(f"  <url><loc>{loc}</loc><lastmod>{stamp}</lastmod></url>")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(rows)}
</urlset>
"""
    (uadb.ROOT / "sitemap.xml").write_text(xml)


_COMMUNITY: list[dict] | None = None


def load_community(cache: dict, arches: list[dict]) -> list[dict]:
    global _COMMUNITY
    if _COMMUNITY is not None:
        return _COMMUNITY
    from scrape_community import canonical_key, key_from_counts

    have = {a["key"] for a in arches}
    rows = uadb.load_json("data/community-decks.json", [])
    mash = re.compile(r"(opm|bcv|kj8|htr|csm|slg).{0,8}(opm|bcv|kj8|htr|csm|slg)")
    for row in rows:
        key = canonical_key(row.get("key") or "", row.get("title") or row.get("archetype") or "")
        row["key"] = key
        label = row.get("archetype") or ""
        messy = key not in have and (
            len(key) > 48 or key.count("-") > 8 or mash.search(key) or len(label) > 48
        )
        if messy:
            new = key_from_counts(row.get("counts") or {}, cache)
            if new:
                row["key"] = new
    _COMMUNITY = rows
    return rows


def community_for(key: str) -> list[dict]:
    rows = _COMMUNITY if _COMMUNITY is not None else uadb.load_json("data/community-decks.json", [])
    return [r for r in rows if r.get("key") == key]


def extra_arches(existing: list[dict]) -> list[dict]:
    have = {a["key"] for a in existing}
    grouped: dict[str, list] = defaultdict(list)
    for row in _COMMUNITY if _COMMUNITY is not None else uadb.load_json("data/community-decks.json", []):
        key = row.get("key") or ""
        if not key or key in have:
            continue
        if sum((row.get("counts") or {}).values()) < uadb.MIN_CARDS:
            continue
        grouped[key].append(row)
    extra = []
    for key, rows in grouped.items():
        rows.sort(key=lambda r: r.get("date") or "0000", reverse=True)
        sample = rows[0]
        label = sample.get("archetype") or ""
        if " - " in label:
            title_name, char_name = split_arch(label)
        else:
            title_name = pretty_anime(sample.get("anime") or "")
            char_name = sample.get("character") or key
        title_name = pretty_anime(title_name) or title_name
        if len(char_name) > 36 or key.count("-") > 8:
            continue
        if re.search(r"(opm|bcv|kj8|htr|csm|slg).{0,8}(opm|bcv|kj8|htr|csm|slg)", key):
            continue
        if re.search(r"mommy|i-don-t-know|dont-know", key):
            continue
        extra.append(
            {
                "id": key,
                "key": key,
                "name": char_name,
                "full": f"{title_name} - {char_name}" if title_name else char_name,
                "from_color": char_name.lower() in COLOR_ONLY,
                "title": title_name,
                "page": f"decklists/{key}.html",
                "dir": f"decklists/{key}",
                "tier": "",
                "style": "",
                "meta_share": 0.0,
                "updated": sample.get("date") or "",
                "strengths": [],
                "weaknesses": [],
                "decklist": {},
            }
        )
    extra.sort(key=lambda a: a["full"])
    return extra


def main() -> None:
    pages_only = "--pages-only" in sys.argv
    cache = load_cache()
    arches = archetypes_from_contender()
    load_community(cache, arches)
    extra = extra_arches(arches)
    if extra:
        arches.extend(extra)
        uadb.log("extra community archetypes", len(extra))
    uadb.log("generate archetypes", len(arches), "cards in cache", len(cache))
    features = {}
    recent = []
    published = []
    sitemap = ["", "characters.html", "series.html", "format.html", "shop.html", "privacy.html"]
    index = {}
    board_decks = []
    hub_jobs = []
    for arch in arches:
        items = flatten_contender(arch, cache)
        comm_rows = community_for(arch["key"])
        if not items and comm_rows:
            items = flatten_counts(comm_rows[0].get("counts") or {}, cache)
        feature = apply_archetype(arch, items, cache)
        features[arch["key"]] = feature
        arch["color"] = (feature.get("meta") or {}).get("color") or ""
        arch["buy_url"] = uadb.tcgplayer_mass_entry_url(items, cache)
        lists = []
        if arch.get("decklist"):
            cons_entry = {
                "slug": "contender-consensus",
                "kind": "contender",
                "title": list_heading(arch),
                "subtitle": f"TCG Contender Standard snapshot · {arch.get('updated') or ''}",
                "player": "",
                "date": arch.get("updated") or "",
                "source_url": f"https://tcgcontender.com/unionarena/decks/standard/{arch['key']}",
                "sim_text": sim_text(items),
                "buy_url": uadb.tcgplayer_mass_entry_url(items, cache),
                "img": uadb.card_image_url(feature.get("id") or "", cache),
                "color": (feature.get("meta") or {}).get("color") or "",
                "href": f"/{arch['dir']}/contender-consensus.html",
                "items": items,
            }
            cons_entry["_feat"] = feature
            lists.append(cons_entry)
            published.append(cons_entry)
        for comm in comm_rows:
            counts = comm.get("counts") or {}
            if sum(counts.values()) < uadb.MIN_CARDS:
                continue
            c_items = flatten_counts(counts, cache)
            c_feat = identity_for_list(c_items, cache, arch)
            comm_entry = {
                "slug": comm.get("slug") or uadb.slugify(comm.get("title") or "community"),
                "kind": comm.get("kind") or "web",
                "title": list_heading(arch, c_feat.get("character") or arch["name"]),
                "subtitle": list_subtitle(
                    {
                        "player": comm.get("player") or "",
                        "subtitle": comm.get("subtitle") or "",
                    }
                ),
                "player": comm.get("player") or "",
                "date": comm.get("date") or "",
                "source_url": comm.get("source_url") or "",
                "sim_text": sim_text(c_items),
                "buy_url": uadb.tcgplayer_mass_entry_url(c_items, cache),
                "img": uadb.card_image_url(c_feat.get("id") or "", cache),
                "color": (c_feat.get("meta") or {}).get("color") or "",
            }
            comm_entry["href"] = f"/{arch['dir']}/{comm_entry['slug']}.html"
            comm_entry["items"] = c_items
            comm_entry["_feat"] = c_feat
            lists.append(comm_entry)
            published.append(comm_entry)
        lists.sort(key=lambda e: e.get("date") or "0000", reverse=True)
        hub_jobs.append((arch, lists, items, feature, True))
        sitemap.append(arch["page"])
        for entry in lists:
            sitemap.append(f"{arch['dir']}/{entry['slug']}.html")
            recent.append(
                {
                    "href": entry.get("href") or f"/{arch['dir']}/{entry['slug']}.html",
                    "img": entry.get("img") or uadb.card_image_url(feature.get("id") or "", cache),
                    "name": entry.get("title") or arch["name"],
                    "who": entry.get("title") or arch["name"],
                    "meta": entry.get("subtitle") or arch["full"],
                    "when": entry.get("date") or "",
                    "color": entry.get("color") or arch.get("color") or "",
                    "key": arch["key"],
                    "buy_url": entry.get("buy_url") or "",
                }
            )
        index[arch["key"]] = [
            {"slug": e["slug"], "kind": e["kind"], "title": e["title"], "date": e.get("date")} for e in lists
        ]
        board_decks.append(discord_board.deck_record(arch, items, cache, feature, lists))
        uadb.log("hub", arch["key"], "lists", len(lists), "feature", feature.get("id"))

    combo_arches, combo_features = build_character_color_hubs(published, cache, arches)
    features.update(combo_features)
    for arch in combo_arches:
        feat = features.get(arch["key"]) or {}
        hub_jobs.append((arch, arch.get("lists") or [], arch.get("cons_items") or [], feat, False))
        if arch["page"] not in sitemap:
            sitemap.append(arch["page"])
        index[arch["key"]] = [
            {"slug": e["slug"], "kind": e["kind"], "title": e["title"], "date": e.get("date")} for e in (arch.get("lists") or [])
        ]
        uadb.log("combo-hub", arch["key"], "lists", len(arch.get("lists") or []), "feature", feat.get("id"))

    catalog = build_title_catalog([job[0] for job in hub_jobs])
    if not pages_only:
        for arch, lists, items, feature, write_lists in hub_jobs:
            if write_lists:
                for entry in lists:
                    write_list_page(
                        arch,
                        entry,
                        entry.get("items") or items,
                        cache,
                        entry.get("_feat") or feature,
                        siblings=lists,
                        catalog=catalog,
                    )
            write_hub(arch, lists, items, cache, feature, catalog=catalog)

    recent.sort(key=lambda r: r.get("when") or "0000", reverse=True)
    prices = uadb.load_tcgplayer_prices()
    home_roster = pick_home_raid_leaders(combo_arches, cache, features, prices=prices)
    search = build_character_search(published, combo_arches, cache, features)
    series = build_series_search(published, combo_arches, cache, features)
    uadb.save_json("data/character-search.json", {"characters": search, "series": series})
    uadb.log("home raid leaders", len(home_roster), "search characters", len(search), "titles", len(series))
    write_home(home_roster, recent, cache, features)
    write_characters_index(home_roster, features, cache, catalog)
    sitemap.extend(write_series_pages(catalog, features, cache))
    write_format(unique_arches([a for a in arches if not a.get("from_color")]))
    write_shop()
    write_privacy()
    board = discord_board.build_board(board_decks)
    sitemap.extend(discord_board.write_pages(board))
    lastmod = (recent[0].get("when") if recent else "") or date.today().isoformat()
    write_sitemap(sitemap, lastmod=lastmod[:10] if lastmod else "")
    write_404()
    uadb.save_json("data/site-index.json", index)
    uadb.log("wrote site", "pages", len(sitemap), "discord themes", board.get("theme_count"))


if __name__ == "__main__":
    main()
