#!/usr/bin/env python3
"""Pull public English Union Arena 50s from the ExBurst decklist catalog.

Reads only is_public=1 rows from the same catalog the ExBurst site shows.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

import uadb

GAME_TABLE = "uaen_decklists"
PAGE_SIZE = 100
MAX_LISTS = 300
MAX_PAGES = 80
SKIP_SLUGS = {
    "reddit-pic-does-anyone-know-the-most-optimal-purple-sao-song-deck-1qls",
}
JS_BUNDLE_RE = re.compile(r"/ua/en/js/en\.[A-Za-z0-9]+\.js")
JWT_RE = re.compile(r"(eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,})")
EN_CID_RE = re.compile(r"(?i)\b(?:UE|UEX|ST|PR)[A-Z0-9]{2,8}/")


def discover_anon_key() -> str:
    status, html = uadb.fetch("https://exburst.dev/ua/en/decklists", timeout=22, browser=True)
    if status != 200:
        raise RuntimeError(f"exburst html {status}")
    bundle = JS_BUNDLE_RE.search(html)
    if not bundle:
        raise RuntimeError("exburst js bundle not found")
    url = "https://exburst.dev" + bundle.group(0)
    st2, js = uadb.fetch(url, timeout=30, browser=True)
    if st2 != 200:
        raise RuntimeError(f"exburst js {st2}")
    idx = js.find("auth.exburst.dev")
    window = js[max(0, idx) : idx + 400] if idx >= 0 else js
    m = JWT_RE.search(window) or JWT_RE.search(js)
    if not m:
        raise RuntimeError("exburst public key not found")
    return m.group(1)


def rest_rows(key: str, offset: int, limit: int = PAGE_SIZE) -> list[dict]:
    start = offset
    end = offset + limit - 1
    url = (
        "https://auth.exburst.dev/rest/v1/"
        f"{GAME_TABLE}?is_public=eq.1"
        "&select=id,decklist_name,modified_date,archetype,decklist_content"
        "&order=modified_date.desc"
    )
    req = urllib.request.Request(
        url,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "Range": f"{start}-{end}",
            "User-Agent": uadb.UA,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=28) as resp:
            raw = resp.read().decode()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode() if exc.fp else ""
        uadb.log("exburst rest", exc.code, offset, body[:120])
        return []
    if not raw.startswith("["):
        return []
    try:
        rows = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return rows if isinstance(rows, list) else []


def english_enough(counts: dict[str, int]) -> bool:
    if not counts:
        return False
    english = sum(n for cid, n in counts.items() if EN_CID_RE.search(cid))
    return english >= max(30, int(0.8 * sum(counts.values())))


def known_exburst_ids(found: list[dict]) -> set[int]:
    out: set[int] = set()
    for row in found:
        slug = row.get("slug") or ""
        src = row.get("source_url") or ""
        m = re.search(r"exburst\.dev/ua/en/decklists/(\d+)", src)
        if not m:
            m = re.search(r"(?:^|-)exburst-(?:.+-)?(\d{4,})$", slug)
        if m:
            out.add(int(m.group(1)))
    return out


def scrape_exburst(found: list[dict], seen: set[str], cache: dict, arches: list[dict], limit: int | None = None) -> int:
    from scrape_community import guess_key, item_from_counts, key_from_counts, record

    cap = MAX_LISTS if limit is None else limit
    if cap < 1:
        return 0
    key = discover_anon_key()
    have = known_exburst_ids(found)
    have_raw = {row.get("raw") for row in found if row.get("raw")}
    added = 0
    skipped = 0
    offset = 0
    for page in range(MAX_PAGES):
        if added >= cap:
            break
        rows = rest_rows(key, offset)
        uadb.log("exburst page", page + 1, "offset", offset, "rows", len(rows), "added", added)
        if not rows:
            break
        for row in rows:
            if added >= cap:
                break
            did = int(row.get("id") or 0)
            if not did or did in have:
                skipped += 1
                continue
            text = row.get("decklist_content") or ""
            counts = uadb.parse_counts(text)
            if not uadb.list_is_complete(counts) or not english_enough(counts):
                skipped += 1
                continue
            name = (row.get("decklist_name") or "").strip() or "Public list"
            blob = f"{name} {row.get('archetype') or ''} {text[:800]}"
            arch_key = guess_key(blob, counts, cache, arches) or key_from_counts(counts, cache)
            if not arch_key:
                skipped += 1
                continue
            date = (row.get("modified_date") or "")[:10]
            slug = uadb.slugify(f"exburst-{name}-{arch_key}-{did}")[:70]
            if slug in SKIP_SLUGS:
                continue
            item = item_from_counts(
                counts,
                key=arch_key,
                kind="web",
                player=name[:40] or "ExBurst",
                title=name[:90],
                subtitle="Public ExBurst 50-card list",
                source_url=f"https://exburst.dev/ua/en/decklists/{did}",
                slug=slug,
                date=date,
            )
            if item.get("raw") in have_raw:
                skipped += 1
                continue
            if record(found, item, seen):
                have.add(did)
                have_raw.add(item.get("raw"))
                added += 1
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(0.08)
    uadb.log("exburst lists added", added, "skipped", skipped)
    return added


def main() -> None:
    from scrape_community import archetypes, collapse_by_slug, seed_existing

    cache = uadb.load_json("data/card-cache.json", {})
    extra = uadb.load_json("data/contender-cards.json", {})
    for cid, card in extra.items():
        cache.setdefault(cid, {}).update({k: v for k, v in card.items() if v})
    found: list[dict] = []
    seen: set[str] = set()
    seed_existing(found, seen)
    scrape_exburst(found, seen, cache, archetypes())
    stored = collapse_by_slug(found)
    for item in stored:
        item["counts"] = item.get("counts") or {}
    uadb.save_json("data/community-decks.json", stored)
    uadb.log("community lists", len(stored))


if __name__ == "__main__":
    main()
