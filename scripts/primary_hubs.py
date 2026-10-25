#!/usr/bin/env python3
"""File each published list under one character hub and one color sub-hub.

The character, color, and series come from Character-type cards in the list.
Event and other card types never choose the hub. Old paths are returned as
redirects; this module does not delete pages that are still being written.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

import uadb

RESULT_KINDS = {"event", "official", "tournament"}
_PLACE_SPLIT = re.compile(r"\s+[·|]\s+")


def snapshot_decklist_html(root: Path | None = None) -> set[str]:
    root = root or uadb.ROOT
    base = root / "decklists"
    if not base.is_dir():
        return set()
    return {p.relative_to(root).as_posix() for p in base.rglob("*.html")}


def _placement(entry: dict) -> int | None:
    import write_guides

    raw = entry.get("placing")
    if raw not in (None, ""):
        try:
            n = int(raw)
        except (TypeError, ValueError):
            n = None
        if n and 1 <= n <= 8:
            return n
    return write_guides.placement_of(entry)


def _event_name(entry: dict) -> str:
    if entry.get("event_name"):
        return str(entry["event_name"]).strip()
    sub = (entry.get("subtitle") or "").strip()
    parts = [p.strip() for p in _PLACE_SPLIT.split(sub) if p.strip()]
    if len(parts) >= 2:
        return parts[-1][:140]
    return ""


def decorate_entry(entry: dict, cache: dict) -> None:
    """Attach identity fields. Reads placing from the original title first."""
    import generate_site as gen

    if entry.get("placing") in (None, ""):
        place = _placement(entry)
        if place:
            entry["placing"] = int(place)
    event = _event_name(entry)
    if event:
        entry["event_name"] = event
    if not entry.get("event_date") and (entry.get("kind") or "") in RESULT_KINDS:
        entry["event_date"] = (entry.get("date") or "")[:10]

    original = entry.get("deck_name") or entry.get("title") or ""
    entry["deck_name"] = original
    ident = gen.assign_list_identity(entry.get("items") or [], cache)
    character = ident.get("character") or ""
    color = (ident.get("color") or "").strip().title()
    series = ident.get("title") or ""
    entry["character"] = character
    entry["deck_color"] = color
    if series:
        entry["series_name"] = series
    entry["identity"] = {
        "character": character,
        "color": color,
        "title": series,
        "face_id": (ident.get("face") or {}).get("id") or "",
    }
    if character:
        entry["title"] = f"{character} ({color})" if color else character
    elif original:
        entry["title"] = original
    bits = []
    kind = gen.list_kind_label(entry.get("kind") or "")
    if kind:
        bits.append(kind)
    if event and event not in bits:
        bits.append(event)
    player = (entry.get("player") or "").strip()
    if player and player.lower() not in {"consensus", ""} and player not in " ".join(bits):
        bits.append(player)
    when = (entry.get("date") or "")[:10]
    if when:
        bits.append(when)
    if bits:
        entry["subtitle"] = " · ".join(bits)


def _claim_slugs(names: dict[str, str], series: dict[str, str]) -> dict[str, str]:
    """Map character name -> directory slug. Disambiguate slug collisions with the series."""
    owner: dict[str, str] = {}
    out: dict[str, str] = {}
    for name in sorted(names):
        base = uadb.slugify(name) or "character"
        if owner.get(base) in (None, name):
            owner[base] = name
            out[name] = base
            continue
        alt = uadb.slugify(f"{series.get(name, '')}-{name}") or f"{base}-deck"
        n = 2
        candidate = alt
        while owner.get(candidate) not in (None, name):
            candidate = f"{alt}-{n}"
            n += 1
        owner[candidate] = name
        out[name] = candidate
    return out


def _source_meta(name: str, source_arches: list[dict]) -> dict:
    import generate_site as gen

    want = gen.norm_name(name)
    best = None
    best_share = -1.0
    for arch in source_arches:
        if arch.get("from_color"):
            continue
        n = gen.norm_name(arch.get("name") or "")
        full = gen.norm_name(arch.get("full") or "")
        if n != want and want not in full:
            continue
        share = float(arch.get("meta_share") or 0)
        if share > best_share:
            best = arch
            best_share = share
    return best or {}


def _suffix_for(entry: dict) -> str:
    player = (entry.get("player") or "").strip()
    if player and player.lower() not in {"consensus", ""}:
        return player[:48]
    event = (entry.get("event_name") or "").strip()
    if event:
        return event[:48]
    for it in entry.get("items") or []:
        if (it.get("group") or "") in {"AP cards", "Characters"}:
            continue
        name = uadb.display_name(it.get("name") or "")
        if name and "/" not in name and name != it.get("id"):
            return name[:48]
    kind = (entry.get("kind") or "").strip()
    return kind[:24]


def disambiguate_titles(published: list[dict]) -> None:
    import generate_site as gen

    buckets: dict[str, list[dict]] = defaultdict(list)
    for entry in published:
        arch = entry.get("_color_arch") or {}
        buckets[gen.deck_page_title(arch, entry)].append(entry)
    for rows in buckets.values():
        if len(rows) < 2:
            continue
        used: set[str] = set()
        for entry in rows:
            suffix = _suffix_for(entry)
            base = suffix
            n = 2
            while suffix.lower() in used:
                suffix = f"{base} {n}"
                n += 1
            used.add(suffix.lower())
            entry["title_suffix"] = suffix


def build(
    published: list[dict],
    cache: dict,
    source_arches: list[dict],
) -> tuple[list[dict], list[dict], dict, dict[str, str]]:
    """Return character hubs, color hubs, feature cards, and old->new redirects."""
    import generate_site as gen

    for entry in published:
        entry.setdefault("legacy_href", entry.get("href") or "")
        entry.setdefault("legacy_key", entry.get("key") or "")
        decorate_entry(entry, cache)

    series_for: dict[str, str] = {}
    for entry in published:
        name = entry.get("character") or ""
        if name and entry.get("series_name") and name not in series_for:
            series_for[name] = entry["series_name"]
    names = {entry.get("character") or "Unsorted": entry.get("character") or "Unsorted" for entry in published}
    # names keys are display names
    display_names = sorted({(entry.get("character") or "Unsorted") for entry in published})
    slug_of = _claim_slugs({n: n for n in display_names}, series_for)

    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for entry in published:
        display = entry.get("character") or "Unsorted"
        char_slug = slug_of[display]
        color_slug = uadb.slugify(entry.get("deck_color") or "") or "na"
        if color_slug in gen.COLOR_ONLY or color_slug == "na":
            pass
        entry["_char_slug"] = char_slug
        entry["_color_slug"] = color_slug
        entry["_display"] = display
        groups[(char_slug, color_slug)].append(entry)

    by_char: dict[str, list[tuple[str, list[dict]]]] = defaultdict(list)
    for (char_slug, color_slug), rows in groups.items():
        rows.sort(key=lambda e: (e.get("date") or "0000", e.get("slug") or ""), reverse=True)
        by_char[char_slug].append((color_slug, rows))

    features: dict[str, dict] = {}
    char_hubs: list[dict] = []
    color_hubs: list[dict] = []
    redirects: dict[str, str] = {}
    hub_votes: dict[str, Counter] = defaultdict(Counter)

    for char_slug, color_rows in sorted(by_char.items()):
        color_rows.sort(key=lambda row: (-len(row[1]), row[0]))
        display = color_rows[0][1][0].get("_display") or char_slug
        series_counts: Counter = Counter()
        color_counts: Counter = Counter()
        all_lists: list[dict] = []
        for color_slug, rows in color_rows:
            for entry in rows:
                if entry.get("series_name"):
                    series_counts[entry["series_name"]] += 1
                if entry.get("deck_color"):
                    color_counts[entry["deck_color"]] += 1
            all_lists.extend(rows)
        all_lists.sort(key=lambda e: (e.get("date") or "0000", e.get("slug") or ""), reverse=True)
        series = series_counts.most_common(1)[0][0] if series_counts else ""
        majority = color_counts.most_common(1)[0][0] if color_counts else ""
        src = _source_meta(display, source_arches)
        char_page = f"decklists/{char_slug}.html"
        char_key = char_slug
        sample = next((e for e in all_lists if e.get("kind") == "contender"), all_lists[0] if all_lists else {})
        face = (sample.get("identity") or {}) if sample else {}
        face_id = face.get("face_id") or ""
        face_meta = cache.get(face_id) or {}
        full = f"{series} - {display}" if series and gen.norm_name(series) != gen.norm_name(display) else display
        color_pages = []
        char_arch = {
            "id": char_key,
            "key": char_key,
            "name": display,
            "full": full,
            "from_color": False,
            "from_combo": True,
            "color_hub": False,
            "title": series,
            "color": majority,
            "colors": [c for c, _n in color_counts.most_common() if c],
            "page": char_page,
            "dir": f"decklists/{char_slug}",
            "tier": str(src.get("tier") or ""),
            "style": src.get("style") or "",
            "meta_share": float(src.get("meta_share") or 0),
            "updated": (all_lists[0].get("date") if all_lists else "") or src.get("updated") or "",
            "strengths": list(src.get("strengths") or []),
            "weaknesses": list(src.get("weaknesses") or []),
            "decklist": {},
            "lists": all_lists,
            "cons_items": (sample.get("items") if sample else []) or [],
            "buy_url": (sample.get("buy_url") if sample else "") or uadb.tcgplayer_mass_entry_url(
                (sample.get("items") if sample else []) or [], cache
            ),
            "sample_label": "Sample list",
        }
        if face_id:
            features[char_key] = {
                "id": face_id,
                "name": face_meta.get("name") or display,
                "meta": face_meta,
                "character": display,
            }
        else:
            features[char_key] = {"id": "", "name": display, "meta": {}, "character": display}

        for color_slug, rows in color_rows:
            used_slugs: set[str] = set()
            color_label = (rows[0].get("deck_color") or color_slug).title()
            if color_slug == "na":
                color_label = ""
            color_key = f"{char_slug}-{color_slug}"
            color_dir = f"decklists/{color_key}"
            color_page = f"{color_dir}.html"
            for entry in rows:
                base = uadb.slugify(entry.get("slug") or "") or "list"
                slug = base
                n = 2
                while slug in used_slugs:
                    slug = f"{base}-{n}"
                    n += 1
                used_slugs.add(slug)
                entry["slug"] = slug
                entry["href"] = f"/{color_dir}/{slug}.html"
                entry["character_page"] = char_page
                entry["color_page"] = color_page
                if not entry.get("buy_url"):
                    entry["buy_url"] = uadb.tcgplayer_mass_entry_url(entry.get("items") or [], cache)
                entry["go_href"] = uadb.write_tcg_go(
                    entry.get("buy_url") or "",
                    entry.get("legacy_href") or entry["href"],
                )
                old = (entry.get("legacy_href") or "").lstrip("/")
                new = entry["href"]
                if old and old != new.lstrip("/"):
                    redirects[old] = new
                legacy_key = entry.get("legacy_key") or ""
                if legacy_key:
                    hub_votes[legacy_key][char_page] += 1
            color_face_id = ""
            for entry in rows:
                color_face_id = (entry.get("identity") or {}).get("face_id") or ""
                if color_face_id and (entry.get("deck_color") or "").lower() == color_slug:
                    break
            if not color_face_id and rows:
                color_face_id = (rows[0].get("identity") or {}).get("face_id") or ""
            color_meta = cache.get(color_face_id) or {}
            color_full = f"{display} ({color_label})" if color_label else display
            color_arch = {
                "id": color_key,
                "key": color_key,
                "name": display,
                "full": color_full,
                "from_color": False,
                "from_combo": True,
                "color_hub": True,
                "title": series,
                "color": color_label or majority,
                "page": color_page,
                "dir": color_dir,
                "parent_page": char_page,
                "parent_name": display,
                "tier": char_arch["tier"],
                "style": char_arch["style"],
                "meta_share": char_arch["meta_share"],
                "updated": (rows[0].get("date") if rows else "") or "",
                "strengths": char_arch["strengths"],
                "weaknesses": char_arch["weaknesses"],
                "decklist": {},
                "lists": rows,
                "sibling_lists": all_lists,
                "cons_items": (rows[0].get("items") if rows else []) or [],
                "buy_url": (rows[0].get("buy_url") if rows else "") or "",
                "go_href": (rows[0].get("go_href") if rows else "") or "",
                "sample_label": f"{color_label} sample list".strip() if color_label else "Sample list",
            }
            for entry in rows:
                entry["_color_arch"] = color_arch
            features[color_key] = {
                "id": color_face_id,
                "name": color_meta.get("name") or display,
                "meta": color_meta or {"color": color_label},
                "character": display,
            }
            color_hubs.append(color_arch)
            color_pages.append(
                {
                    "href": f"/{color_page}",
                    "page": color_page,
                    "color": color_label or "Uncolored",
                    "n": len(rows),
                }
            )
        char_arch["color_pages"] = color_pages
        char_arch["go_href"] = (sample.get("go_href") if sample else "") or uadb.write_tcg_go(
            char_arch.get("buy_url") or "", char_page
        )
        char_hubs.append(char_arch)

    disambiguate_titles(published)
    for legacy_key, counter in hub_votes.items():
        if not counter:
            continue
        target = counter.most_common(1)[0][0]
        old = f"decklists/{legacy_key}.html"
        new = "/" + str(target).lstrip("/")
        if old != new.lstrip("/"):
            redirects.setdefault(old, new)
    return char_hubs, color_hubs, features, redirects


def recent_rows(published: list[dict], cache: dict) -> list[dict]:
    rows = []
    for entry in published:
        rows.append(
            {
                "href": entry.get("href") or "",
                "img": entry.get("img") or uadb.card_image_url((entry.get("identity") or {}).get("face_id") or "", cache),
                "name": entry.get("character") or entry.get("title") or "List",
                "who": entry.get("title") or entry.get("character") or "List",
                "meta": entry.get("subtitle") or "",
                "when": (entry.get("date") or "")[:10],
                "color": entry.get("deck_color") or entry.get("color") or "",
                "key": entry.get("_char_slug") or entry.get("key") or "",
                "kind": entry.get("kind") or "",
                "buy_url": entry.get("buy_url") or "",
                "go_href": entry.get("go_href") or "",
            }
        )
    rows.sort(key=lambda r: r.get("when") or "0000", reverse=True)
    return rows


_HUB_SUFFIXES = (
    "-box-topper-gold-foil",
    "-box-topper-silver-foil",
    "-box-topper-foil",
    "-gold-foil",
    "-silver-foil",
    "-promotion-pack",
    "-blue",
    "-green",
    "-yellow",
    "-purple",
    "-red",
    "-black",
    "-white",
    "-gold",
    "-judge",
    "-sr",
    "-u",
)
_PROMO_SUFFIX = re.compile(r"-(?:p-\d+|promotion-pack-\d+)$")


def _hub_pages(written: set[str]) -> list[str]:
    return [
        rel
        for rel in written
        if rel.startswith("decklists/") and rel.endswith(".html") and rel.count("/") == 1
    ]


def fallback_redirect_target(rel: str, written: set[str]) -> str:
    """Point a retired decklists URL at the closest hub that still exists.

    Color and foil-stamp suffixes peel off first. Then a hub whose slug sits
    inside the old slug (or the reverse, when only one hub matches) wins.
    Anything still ambiguous goes to the character index.
    """
    rel = rel.lstrip("/")
    parts = rel.split("/")
    if not parts or parts[0] != "decklists":
        return "/characters.html"
    slug = parts[1][: -len(".html")] if parts[1].endswith(".html") else parts[1]
    hubs = _hub_pages(written)
    hub_set = set(hubs)

    base = slug
    seen: set[str] = set()
    while base and base not in seen:
        seen.add(base)
        page = f"decklists/{base}.html"
        if page in hub_set and page != rel:
            return f"/{page}"
        nxt = ""
        promo = _PROMO_SUFFIX.search(base)
        if promo and promo.start() > 0:
            nxt = base[: promo.start()]
        else:
            for suf in _HUB_SUFFIXES:
                if base.endswith(suf) and len(base) > len(suf):
                    nxt = base[: -len(suf)]
                    break
        if not nxt:
            break
        base = nxt.rstrip("-")

    # Old folders were often "{series}-{character}". Peel a real series slug
    # only when the remainder is itself a hub. Do not match a shorter name
    # that merely shares a trailing token (Silva, Sesshomaru).
    series_dir = (uadb.ROOT / "series")
    series = {p.stem for p in series_dir.glob("*.html")} if series_dir.is_dir() else set()
    for series_slug in sorted(series, key=len, reverse=True):
        prefix = f"{series_slug}-"
        if not slug.startswith(prefix):
            continue
        rest = slug[len(prefix):]
        page = f"decklists/{rest}.html"
        if page in hub_set and page != rel:
            return f"/{page}"
    return "/characters.html"


def write_redirects(
    legacy_files: set[str],
    written: set[str],
    redirect_map: dict[str, str],
    root: Path | None = None,
) -> list[dict]:
    """Write noindex HTML stubs plus _redirects and data/redirects.json.

    GitHub Pages serves the HTML file. The _redirects file is for a host
    that can emit a real 301 (Cloudflare or Netlify). Pages with .nojekyll
    cannot.
    """
    root = root or uadb.ROOT
    payload: list[dict] = []
    lines: list[str] = []
    seen: set[str] = set()

    def add(old_rel: str, target: str) -> None:
        old_rel = old_rel.lstrip("/")
        if not old_rel or old_rel in seen or old_rel in written:
            return
        if not target:
            return
        target = target if target.startswith("/") or target.startswith("http") else f"/{target}"
        if old_rel == target.lstrip("/"):
            return
        seen.add(old_rel)
        dest = root / old_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(uadb.html_redirect(target, "Moved"))
        lines.append(f"/{old_rel} {target} 301")
        payload.append({"from": f"/{old_rel}", "to": target})

    for old, new in sorted(redirect_map.items()):
        add(old, new)
    for rel in sorted(legacy_files):
        if rel in written or rel in seen:
            continue
        add(rel, fallback_redirect_target(rel, written))
    note = (
        "GitHub Pages with .nojekyll cannot send an HTTP 301. "
        "Each old URL is an HTML file with a meta refresh and location.replace. "
        "The _redirects list is the same map for a host that supports 301s."
    )
    uadb.save_json("data/redirects.json", {"note": note, "count": len(payload), "redirects": payload})
    (root / "_redirects").write_text("\n".join(lines) + ("\n" if lines else ""))
    return payload


def persist_event_fields(published: list[dict]) -> int:
    """Write placing, event name, and event date back onto community rows."""
    rows = uadb.load_json("data/community-decks.json", [])
    if not isinstance(rows, list):
        return 0
    index: dict[tuple[str, str, str], dict] = {}
    for entry in published:
        slug = entry.get("slug") or ""
        # slug may have been disambiguated; match the legacy slug too
        for key in {slug, (entry.get("legacy_href") or "").rsplit("/", 1)[-1].removesuffix(".html")}:
            if not key:
                continue
            index[(key, (entry.get("date") or "")[:10], entry.get("kind") or "")] = entry
    changed = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        src = index.get(((row.get("slug") or ""), (row.get("date") or "")[:10], row.get("kind") or ""))
        if not src:
            continue
        for field in ("placing", "event_name", "event_date"):
            val = src.get(field)
            if val in (None, ""):
                continue
            if row.get(field) != val:
                row[field] = val
                changed += 1
    if changed:
        uadb.save_json("data/community-decks.json", rows)
    return changed
