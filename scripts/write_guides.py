#!/usr/bin/env python3
"""Tier list and strategy guides, adapted from One Piece Deck Base for Union Arena.

Ranks use TCG Contender's numbered snapshot plus hosted event 50s on this site.
Does not invent tournament results or matchup percentages.
"""

from __future__ import annotations

import html
import re
from collections import defaultdict
from datetime import date, timedelta

import generate_site as gen
import uadb

RECENT_DAYS = 45
BOARD_LIMIT = 22
GUIDE_MIN_LISTS = 3
TITLE_GUIDE_MIN_LISTS = 10
RESULT_KINDS = {"event", "official", "tournament"}
CONTENDER_LETTER = {"1": "A", "2": "B", "3": "C", "4": "D", "5": "D"}
PLACE_WORDS = {
    "winner": 1,
    "1st": 1,
    "first": 1,
    "2nd": 2,
    "second": 2,
    "3rd": 3,
    "third": 3,
}
PLACE_RE = re.compile(
    r"\b(winner|1st|2nd|3rd|[4-8]th|first|second|third|top\s*8|top\s*4)\b",
    re.I,
)
TIER_ORDER = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}

HOME_TIER_TILE = """          <a class="home-big home-big-tier" href="/tier-list.html">
            <span class="home-big-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2.1 13.85 5.2h-3.7L12 2.1Z"/>
                <rect x="10.15" y="5.35" width="3.7" height="1.85" rx="0.4"/>
                <path d="M9 20.6V8.9h6v11.7H9Z"/>
                <path d="M3.6 20.6v-6.4H9v6.4H3.6Z" opacity=".88"/>
                <path d="M15 20.6v-4.7h5.4v4.7H15Z" opacity=".72"/>
              </svg>
            </span>
            <span class="home-big-title">Tier List</span>
            <span class="home-big-note">S through D with character pictures</span>
          </a>
"""


def recent_cutoff(today: date | None = None) -> str:
    day = today or date.today()
    return (day - timedelta(days=RECENT_DAYS)).isoformat()


def placement_of(entry: dict) -> int | None:
    blob = " ".join(
        [
            str(entry.get("player") or ""),
            str(entry.get("title") or ""),
            str(entry.get("subtitle") or ""),
            str(entry.get("slug") or "").replace("-", " "),
        ]
    )
    m = PLACE_RE.search(blob)
    if not m:
        return None
    token = re.sub(r"\s+", " ", m.group(1).lower())
    if token == "top 8":
        return 8
    if token == "top 4":
        return 4
    if token in PLACE_WORDS:
        return PLACE_WORDS[token]
    if token.endswith("th") and token[0].isdigit():
        return int(token[0])
    return None


def is_result_list(entry: dict) -> bool:
    kind = (entry.get("kind") or "").lower()
    if kind in RESULT_KINDS:
        return True
    return placement_of(entry) is not None


def list_names_character(entry: dict, name: str) -> bool:
    """True when the file is filed under this character, not just sharing the 50."""
    want = gen.norm_name(name)
    if not want:
        return False
    blob = gen.norm_name(
        " ".join(
            [
                str(entry.get("title") or ""),
                str(entry.get("subtitle") or ""),
                str(entry.get("player") or ""),
                str(entry.get("slug") or "").replace("-", " "),
                str(entry.get("key") or "").replace("-", " "),
            ]
        )
    )
    return want in blob


def _unique_lists(rows: list[dict]) -> list[dict]:
    out = []
    seen = set()
    for entry in rows:
        href = entry.get("href") or entry.get("slug") or ""
        key = href or f"{entry.get('date')}|{entry.get('title')}|{entry.get('slug')}"
        if key in seen:
            continue
        seen.add(key)
        out.append(entry)
    return out


def _non_ap(items: list[dict]) -> list[dict]:
    return [it for it in items if (it.get("group") or "") != "AP cards"]


def _count(it: dict) -> int:
    try:
        return int(it.get("count") or 0)
    except (TypeError, ValueError):
        return 0


def _card_name(it: dict, cache: dict) -> str:
    meta = cache.get(it.get("id") or "") or {}
    return uadb.display_name(meta.get("name") or it.get("name") or it.get("id") or "card")


def _card_label(it: dict, cache: dict) -> str:
    name = _card_name(it, cache)
    name = re.sub(r"\s+\((?:P-\d{2,3}|\d{3}|Release Event[^)]*)\)\s*$", "", name, flags=re.I)
    cid = it.get("id") or ""
    return f"{name} ({cid})" if cid else name


def _join_and(parts: list[str]) -> str:
    clean = [p for p in parts if p]
    if not clean:
        return ""
    if len(clean) == 1:
        return clean[0]
    if len(clean) == 2:
        return f"{clean[0]} and {clean[1]}"
    return f"{', '.join(clean[:-1])}, and {clean[-1]}"


def _face_item(items: list[dict], cache: dict, name: str) -> dict:
    want = gen.norm_name(name)
    scored = []
    for it in _non_ap(items):
        cid = it.get("id") or ""
        if not cid or "UNRESOLVED" in cid:
            continue
        meta = cache.get(cid) or {}
        card = gen.norm_name(meta.get("name") or it.get("name") or "")
        if want and want not in card and card not in want:
            continue
        cost = gen.card_cost(meta) or 0
        raid = 8 if gen.is_raid_meta(meta) else 0
        scored.append((raid, cost, _count(it), cid, it, meta))
    if not scored:
        return {}
    scored.sort(reverse=True)
    _raid, _cost, _n, cid, it, meta = scored[0]
    return {"id": cid, "item": it, "meta": meta}


def score_row(row: dict) -> float:
    tier = str(row.get("contender_tier") or "")
    tier_pts = {"1": 12.0, "2": 7.0, "3": 4.0, "4": 2.0, "5": 1.0}.get(tier, 0.0)
    return (
        row.get("recent_top8", 0) * 4.0
        + row.get("recent_wins", 0) * 2.0
        + row.get("recent_results", 0) * 1.2
        + row.get("recent_lists", 0) * 0.3
        + float(row.get("meta_share") or 0) * 60.0
        + tier_pts
        + min(row.get("list_count", 0), 20) * 0.05
    )


def assign_letters(rows: list[dict]) -> list[dict]:
    """Map Contender 1-5 onto S-D, then place everyone else from hosted 50s."""
    for row in rows:
        letter = CONTENDER_LETTER.get(str(row.get("contender_tier") or ""), "")
        top8 = int(row.get("recent_top8") or 0)
        wins = int(row.get("recent_wins") or 0)
        share = float(row.get("meta_share") or 0)
        results = int(row.get("recent_results") or 0)
        lists_n = int(row.get("list_count") or 0)
        recent_n = int(row.get("recent_lists") or 0)
        if letter == "A":
            if top8 >= 2 or wins >= 1 or (top8 >= 1 and share >= 0.03):
                letter = "S"
        elif letter == "B" and top8 >= 3:
            letter = "A"
        elif letter == "C" and top8 >= 2:
            letter = "B"
        elif letter == "D" and top8 >= 2:
            letter = "C"
        if letter == "D" and share >= 0.02 and top8 >= 1:
            letter = "C"
        if not letter:
            volume = recent_n * 2 + lists_n
            if top8 >= 2 or wins >= 1 or results >= 5:
                letter = "B"
            elif top8 >= 1 or results >= 2 or volume >= 50:
                letter = "C"
            else:
                letter = "D"
        row["tier"] = letter
    return rows


def _character_rec(name: str, arch: dict | None = None) -> dict:
    arch = arch or {}
    return {
        "nkey": gen.norm_name(name),
        "name": name,
        "title": arch.get("title") or "",
        "hubs": [],
        "lists": [],
        "items": [],
        "feature": {},
        "page": arch.get("page") or "",
        "key": arch.get("key") or "",
        "full": arch.get("full") or name,
        "color": arch.get("color") or "",
        "style": arch.get("style") or "",
        "contender_tier": str(arch.get("tier") or ""),
        "meta_share": float(arch.get("meta_share") or 0),
        "strengths": list(arch.get("strengths") or []),
        "weaknesses": list(arch.get("weaknesses") or []),
        "updated": arch.get("updated") or "",
    }


def _is_series_name(name: str) -> bool:
    raw = (name or "").strip()
    if not raw:
        return True
    pretty = gen.pretty_anime(raw)
    return pretty != raw


def _is_board_name(name: str) -> bool:
    raw = (name or "").strip()
    if not raw or gen.looks_like_cid(raw) or gen.norm_name(raw) in gen.COLOR_ONLY:
        return False
    return not _is_series_name(raw)


def _first_card_feature(lists: list[dict]) -> dict:
    for entry in lists or []:
        for it in entry.get("items") or []:
            cid = (it.get("id") or "").strip()
            if cid and "/" in cid and "UNRESOLVED" not in cid:
                return {"id": cid}
    return {}


def _fold_named_faces(groups: dict[str, dict], hub_jobs: list) -> None:
    """File titled 50s under the character they name, not only the hub key."""
    pool = gen.character_name_pool([job[0] for job in hub_jobs])
    for job in hub_jobs:
        pack = _hub_from_job(job)
        arch = pack["arch"]
        series = gen.pretty_anime(arch.get("title") or "") or gen.pretty_anime(arch.get("key") or "")
        for entry in pack["lists"]:
            face = gen.attribute_list_face(entry, pool)
            if not face or not _is_board_name(face):
                continue
            nkey = gen.norm_name(face)
            rec = groups.get(nkey)
            if rec is None:
                rec = _character_rec(face, {"title": series, "full": f"{series} - {face}" if series else face})
                groups[nkey] = rec
            rec["lists"].append(entry)
            if series and not rec.get("title"):
                rec["title"] = series
            if _is_board_name(arch.get("name") or "") and gen.norm_name(arch.get("name") or "") == nkey:
                rec["hubs"].append(arch)
                if pack["items"] and len(pack["items"]) > len(rec.get("items") or []):
                    rec["items"] = pack["items"]
                if pack["feature"].get("id") and not rec["feature"].get("id"):
                    rec["feature"] = pack["feature"]
                if arch.get("page"):
                    rec["page"] = arch["page"]
                    rec["key"] = arch.get("key") or rec.get("key") or ""


def _hub_from_job(job) -> dict:
    arch, lists, items, feature, _write = job
    return {
        "arch": arch,
        "lists": lists or [],
        "items": items or arch.get("cons_items") or [],
        "feature": feature or {},
    }


def collect_characters(hub_jobs: list, cache: dict, today: date | None = None) -> list[dict]:
    cutoff = recent_cutoff(today)
    groups: dict[str, dict] = {}
    for job in hub_jobs:
        pack = _hub_from_job(job)
        arch = pack["arch"]
        name = arch.get("name") or ""
        nkey = gen.norm_name(name)
        if not nkey or nkey in gen.COLOR_ONLY or not _is_board_name(name):
            continue
        rec = groups.get(nkey)
        if rec is None:
            rec = _character_rec(name, arch)
            groups[nkey] = rec
        rec["hubs"].append(arch)
        rec["lists"].extend(pack["lists"])
        if len(pack["items"]) > len(rec["items"]):
            rec["items"] = pack["items"]
        if pack["feature"].get("id") and not rec["feature"].get("id"):
            rec["feature"] = pack["feature"]
        hub_n = len(pack["lists"])
        best_n = int(rec.get("_hub_lists") or 0)
        take_hub = hub_n > best_n or (hub_n == best_n and arch.get("from_combo") and not rec.get("_from_combo"))
        if take_hub and (arch.get("page") or not rec["page"]):
            rec["page"] = arch.get("page") or rec["page"]
            rec["key"] = arch.get("key") or rec["key"]
            rec["full"] = arch.get("full") or rec["full"]
            rec["color"] = arch.get("color") or rec["color"]
            rec["name"] = name or rec["name"]
            rec["title"] = arch.get("title") or rec["title"]
            rec["_hub_lists"] = hub_n
            rec["_from_combo"] = bool(arch.get("from_combo"))
        rec["meta_share"] = max(rec["meta_share"], float(arch.get("meta_share") or 0))
        if arch.get("tier") and (
            not rec["contender_tier"]
            or int(str(arch.get("tier") or "9") or "9") < int(rec["contender_tier"] or "9")
        ):
            rec["contender_tier"] = str(arch.get("tier"))
            rec["style"] = arch.get("style") or rec["style"]
            rec["strengths"] = list(arch.get("strengths") or rec["strengths"])
            rec["weaknesses"] = list(arch.get("weaknesses") or rec["weaknesses"])
        rec["updated"] = rec["updated"] or arch.get("updated") or ""

    _fold_named_faces(groups, hub_jobs)

    rows = []
    for rec in groups.values():
        if not _is_board_name(rec.get("name") or ""):
            continue
        lists = _unique_lists(rec["lists"])
        lists.sort(key=lambda e: e.get("date") or "0000", reverse=True)
        rec["lists"] = lists
        if not rec["feature"].get("id"):
            rec["feature"] = _first_card_feature(lists)
        if not rec.get("page"):
            rec["page"] = gen.series_href(rec.get("title") or "").lstrip("/") or "characters.html"
        named = [e for e in lists if list_names_character(e, rec["name"])]
        recent = [e for e in named if (e.get("date") or "") >= cutoff]
        results = [e for e in recent if is_result_list(e)]
        places = [(e, placement_of(e)) for e in results]
        top8 = [e for e, place in places if place is not None and place <= 8]
        wins = [e for e, place in places if place == 1]
        rec["list_count"] = len(lists)
        rec["recent_lists"] = len(recent)
        rec["recent_results"] = len(results)
        rec["recent_top8"] = len(top8)
        rec["recent_wins"] = len(wins)
        rec["recent_result_rows"] = results
        rec["score"] = score_row(rec)
        if rec["list_count"] < 1:
            continue
        if rec["recent_lists"] < 1 and rec["meta_share"] < 0.008 and not rec["contender_tier"]:
            continue
        rows.append(rec)
    assign_letters(rows)
    rows.sort(key=lambda r: (TIER_ORDER.get(r["tier"], 9), -r["score"], r["name"]))
    return rows


def _force_board_names() -> set[str]:
    return {gen.norm_name(n) for n in gen.EXTRA_FACES}


def pick_board(rows: list[dict]) -> list[dict]:
    kept = []
    for row in rows:
        if not _is_board_name(row.get("name") or ""):
            continue
        if row["tier"] in "SABC" or row["recent_top8"] or row["meta_share"] >= 0.01:
            kept.append(row)
        if len(kept) >= BOARD_LIMIT:
            break
    if len(kept) < 12:
        for row in rows:
            if row in kept:
                continue
            if not _is_board_name(row.get("name") or ""):
                continue
            kept.append(row)
            if len(kept) >= 16:
                break
    have = {row["nkey"] for row in kept}
    force = _force_board_names()
    for row in rows:
        if row["nkey"] in have:
            continue
        if row["nkey"] in force and int(row.get("list_count") or 0) >= 3:
            kept.append(row)
            have.add(row["nkey"])
    kept.sort(key=lambda r: (TIER_ORDER.get(r["tier"], 9), -r["score"], r["name"]))
    return kept


def _guide_slug(name: str) -> str:
    return f"{uadb.slugify(name)}-strategy"


def _guide_record(row: dict, kind: str = "character") -> dict:
    name = row["name"]
    slug = _guide_slug(name)
    href = f"/guides/{slug}.html"
    if kind == "title":
        slug = _guide_slug(row["title"])
        href = f"/guides/{slug}.html"
        title = f"{row['title']} strategy"
        blurb = f"{row['list_count']} hosted lists · current Standard names"
    else:
        title = f"{name} strategy"
        bits = []
        if row.get("title"):
            bits.append(row["title"])
        if row.get("recent_top8"):
            bits.append(f"{row['recent_top8']} recent top 8s")
        elif row.get("list_count"):
            bits.append(f"{row['list_count']} hosted lists")
        if row.get("tier"):
            bits.append(f"{row['tier']} tier")
        blurb = " · ".join(bits) or "How the 50 plays"
    return {
        "kind": kind,
        "name": name,
        "title": title,
        "href": href,
        "slug": slug,
        "path": href.lstrip("/"),
        "blurb": blurb,
        "nkey": row.get("nkey") or gen.norm_name(name),
        "row": row,
    }


def topic_guides() -> list[dict]:
    return [
        {
            "kind": "topic",
            "name": "How to read a 50",
            "title": "How to read a Union Arena 50",
            "href": "/guides/how-to-read-a-50.html",
            "slug": "how-to-read-a-50",
            "path": "guides/how-to-read-a-50.html",
            "blurb": "Consensus cores, raid faces, and what the numbers mean",
        },
        {
            "kind": "topic",
            "name": "Restricted cards",
            "title": "Restricted cards in Standard",
            "href": "/guides/restricted-cards.html",
            "slug": "restricted-cards",
            "path": "guides/restricted-cards.html",
            "blurb": "Asuka and Spear of Gaius, one copy each",
        },
        {
            "kind": "topic",
            "name": "Single-title Standard",
            "title": "Single-title Standard",
            "href": "/guides/single-title-standard.html",
            "slug": "single-title-standard",
            "path": "guides/single-title-standard.html",
            "blurb": "English events, one IP, 50 cards",
        },
        {
            "kind": "topic",
            "name": "Raid triggers",
            "title": "Raid triggers and the energy line",
            "href": "/guides/raid-triggers.html",
            "slug": "raid-triggers",
            "path": "guides/raid-triggers.html",
            "blurb": "Add this card to your hand, or perform Raid",
        },
    ]


def build_plan(hub_jobs: list, cache: dict, features: dict | None = None, today: date | None = None) -> dict:
    features = features or {}
    day = today or date.today()
    rows = collect_characters(hub_jobs, cache, today=day)
    board = pick_board(rows)
    char_guides = []
    for row in board:
        if row["list_count"] >= GUIDE_MIN_LISTS:
            char_guides.append(_guide_record(row))
    seen_href = set()
    unique_guides = []
    for g in char_guides:
        if g["href"] in seen_href:
            continue
        seen_href.add(g["href"])
        unique_guides.append(g)
    char_guides = unique_guides

    by_title: dict[str, dict] = {}
    for row in rows:
        title = row.get("title") or ""
        tkey = gen.norm_name(title)
        if not tkey:
            continue
        bucket = by_title.get(tkey)
        if bucket is None:
            bucket = {
                "nkey": tkey,
                "name": title,
                "title": title,
                "list_count": 0,
                "recent_top8": 0,
                "meta_share": 0.0,
                "chars": [],
                "tier": "",
            }
            by_title[tkey] = bucket
        bucket["list_count"] += row["list_count"]
        bucket["recent_top8"] += row["recent_top8"]
        bucket["meta_share"] = max(bucket["meta_share"], row["meta_share"])
        bucket["chars"].append(row)
    board_titles = {gen.norm_name(r.get("title") or "") for r in board if r.get("title")}
    title_guides = []
    for bucket in by_title.values():
        if bucket["nkey"] not in board_titles:
            continue
        if bucket["list_count"] < TITLE_GUIDE_MIN_LISTS:
            continue
        if len(bucket["chars"]) < 2 and bucket["meta_share"] < 0.04:
            continue
        title_guides.append(_guide_record(bucket, kind="title"))
    title_guides.sort(key=lambda g: (-g["row"]["list_count"], g["title"]))

    topics = topic_guides()
    by_key: dict[str, dict] = {}
    for g in char_guides:
        row = g["row"]
        by_key[g["nkey"]] = g
        by_key[row.get("key") or ""] = g
        for hub in row.get("hubs") or []:
            if hub.get("key"):
                by_key[hub["key"]] = g
    return {
        "today": day.isoformat(),
        "recent_from": recent_cutoff(day),
        "rows": rows,
        "board": board,
        "character_guides": char_guides,
        "title_guides": title_guides,
        "topic_guides": topics,
        "by_key": by_key,
        "features": features,
    }


def guide_for_arch(plan: dict, arch: dict) -> dict | None:
    by_key = plan.get("by_key") or {}
    return by_key.get(arch.get("key") or "") or by_key.get(gen.norm_name(arch.get("name") or ""))


def strategy_link_html(guide: dict | None) -> str:
    if not guide:
        return ""
    return (
        '          <p class="leader-strategy">'
        f'<a href="{html.escape(guide["href"])}">{html.escape(guide["title"])}</a>'
        f'<span class="muted">{html.escape(guide["blurb"])}</span>'
        "</p>"
    )


def _img_for_row(row: dict, cache: dict) -> str:
    feat = row.get("feature") or {}
    cid = feat.get("id") or ""
    if not cid:
        face = _face_item(row.get("items") or [], cache, row.get("name") or "")
        cid = face.get("id") or ""
    return uadb.card_image_url(cid, cache) if cid else ""


def render_tier_board(board: list[dict], cache: dict) -> str:
    groups = {letter: [] for letter in "SABCD"}
    for row in board:
        groups.get(row["tier"], groups["D"]).append(row)
    chunks = []
    for letter in "SABCD":
        tiles = []
        for row in groups[letter]:
            img = _img_for_row(row, cache)
            href = f"/{row['page']}" if row.get("page") else "/characters.html"
            meta = []
            if row.get("recent_top8"):
                n = row["recent_top8"]
                meta.append(f"{n} recent top 8{'s' if n != 1 else ''}")
            elif row.get("recent_results"):
                meta.append(f"{row['recent_results']} recent results")
            elif row.get("list_count"):
                meta.append(f"{row['list_count']} lists")
            note = meta[0] if meta else (row.get("title") or "")
            img_tag = (
                f'<img src="{html.escape(img)}" alt="{html.escape(row["name"])} Union Arena character" loading="lazy" decoding="async" />'
                if img
                else ""
            )
            tiles.append(
                f"""            <a class="tier-leader" href="{html.escape(href)}">
              {img_tag}
              <span class="name">{html.escape(row["name"])}</span>
              <span class="meta">{html.escape(note)}</span>
            </a>"""
            )
        body = "\n".join(tiles) if tiles else '            <p class="muted" style="margin:12px">No names in this row from the current snapshot.</p>'
        chunks.append(
            f"""          <div class="tier-row tier-{letter.lower()}" id="tier-{letter.lower()}">
            <div class="tier-label" aria-label="Tier {letter}">{letter}</div>
            <div class="tier-leaders">
{body}
            </div>
          </div>"""
        )
    return "\n".join(chunks)


def render_tier_table(board: list[dict]) -> str:
    rows = []
    for row in board:
        href = f"/{row['page']}" if row.get("page") else "/characters.html"
        share = f"{row['meta_share'] * 100:.1f}%" if row.get("meta_share") else "—"
        cont = row.get("contender_tier") or "—"
        rows.append(
            f"""            <tr>
              <td><strong>{html.escape(row['tier'])}</strong></td>
              <td><a href="{html.escape(href)}">{html.escape(row['name'])}</a></td>
              <td>{html.escape(row.get('title') or '')}</td>
              <td>{row['recent_top8']}</td>
              <td>{row['recent_results']}</td>
              <td>{html.escape(share)}</td>
              <td>{html.escape(str(cont))}</td>
            </tr>"""
        )
    return f"""        <section class="tier-table" id="table">
          <div class="section-title">
            <h2>The numbers</h2>
            <div class="muted">Hosted results + Contender share</div>
          </div>
          <table>
            <thead>
              <tr>
                <th>Tier</th>
                <th>Character</th>
                <th>Title</th>
                <th>Recent top 8s</th>
                <th>Recent results</th>
                <th>Contender share</th>
                <th>Contender #</th>
              </tr>
            </thead>
            <tbody>
{chr(10).join(rows)}
            </tbody>
          </table>
        </section>"""


def write_tier_list(plan: dict, cache: dict) -> str:
    board = plan.get("board") or []
    today = plan.get("today") or date.today().isoformat()
    recent_from = plan.get("recent_from") or recent_cutoff()
    s_names = [r["name"] for r in board if r["tier"] == "S"]
    intro = (
        "This board starts from the public TCG Contender Standard snapshot, then promotes names "
        f"that hosted event 50s on this site keep posting from {recent_from} through {today}. "
        "Characters Contender has not numbered yet still get S through D from the hosted 50s "
        "available here. English events are single-title Standard. Pictures link to the character hub."
    )
    if s_names:
        intro = f"{_join_and(s_names)} sit in S. {intro}"
    faq = [
        (
            "How is this Union Arena tier list built?",
            "TCG Contender publishes numbered Standard tiers and meta share. This page maps those numbers onto S through D, then promotes characters with recent top 8s in the 50-card lists hosted here. Names with no Contender number are still lettered from hosted list volume and any event 50s on this site. It does not invent results.",
        ),
        (
            "What format is the tier list?",
            "English Union Arena Standard. Events are usually one anime or manga title, 50 cards, four copies of a number unless a card is restricted or printed as a high-copy exception.",
        ),
        (
            "Why does a name move up from Contender's number?",
            "A Contender tier 1 list becomes S when this site also has recent wins or top 8s for that character. A quieter tier 1 stays A.",
        ),
    ]
    s_count = sum(1 for r in board if r["tier"] == "S")
    desc = uadb.clip_meta(
        f"Union Arena Standard tier list: {s_count} names in S, then A through D. "
        "Built from TCG Contender plus hosted event 50s, with character pictures."
    )
    title = uadb.page_title("Standard tier list")
    body = f"""        {uadb.crumb_html([("/", "Home"), (None, "Tier list")])}
        <h1>Standard tier list</h1>
        <p>{html.escape(intro)}</p>
        <p class="muted">Updated {html.escape(today)}. Character pictures open the hub on this site.</p>
        <div class="tier-board" aria-label="Union Arena Standard character tier list">
{render_tier_board(board, cache)}
        </div>
{render_tier_table(board)}
        <section class="tier-sources" id="sources">
          <div class="section-title">
            <h2>Sources</h2>
            <div class="muted">Public only</div>
          </div>
          <ol>
            <li><a href="https://tcgcontender.com/unionarena/meta">TCG Contender Union Arena Standard snapshot</a> - numbered tiers and meta share used as the starting rank.</li>
            <li>Hosted official, event, and tournament 50s on this site dated {html.escape(recent_from)} to {html.escape(today)}. Top 8s are read from the list title, player line, or slug.</li>
          </ol>
        </section>
        <section class="faq" id="faq">
          <div class="section-title">
            <h2>How to read it</h2>
            <div class="muted">Short answers</div>
          </div>
{chr(10).join(
    f'''          <details{" open" if i == 0 else ""}>
            <summary>{html.escape(q)}</summary>
            <p>{html.escape(a)}</p>
          </details>'''
    for i, (q, a) in enumerate(faq)
)}
        </section>
        <p class="hub-more"><a href="/guides/">Strategy guides</a> · <a href="/format.html">Format</a> · <a href="/characters.html">Characters</a> · <a href="/#recent">Recent lists</a></p>"""
    items = [(f"/{r['page']}", r["name"]) for r in board if r.get("page")]
    page = uadb.page_chrome(
        title,
        desc,
        "color-red",
        body,
        "tier",
        path="tier-list.html",
        json_ld=[
            uadb.website_ld(),
            uadb.breadcrumb_ld([("/", "Home"), ("/tier-list.html", "Tier list")]),
            uadb.item_list_ld("Union Arena Standard tier list", items, url="/tier-list.html"),
            uadb.faq_ld(faq),
        ],
    )
    (uadb.ROOT / "tier-list.html").write_text(page)
    payload = {
        "updated": today,
        "recent_from": recent_from,
        "characters": [
            {
                "name": r["name"],
                "title": r.get("title") or "",
                "tier": r["tier"],
                "page": r.get("page") or "",
                "recent_top8": r["recent_top8"],
                "recent_results": r["recent_results"],
                "meta_share": r["meta_share"],
                "contender_tier": r.get("contender_tier") or "",
                "score": round(r["score"], 3),
            }
            for r in board
        ],
    }
    uadb.save_json("data/tier-list.json", payload)
    return "tier-list.html"


def _ofs(items: list[dict], n: int) -> list[dict]:
    return [it for it in _non_ap(items) if _count(it) == n]


def _high_copy(items: list[dict]) -> list[dict]:
    return [it for it in _non_ap(items) if _count(it) > 4]


def _raid_cards(items: list[dict], cache: dict) -> list[dict]:
    out = []
    for it in _non_ap(items):
        meta = cache.get(it.get("id") or "") or {}
        if gen.is_raid_meta(meta):
            out.append(it)
    out.sort(key=lambda it: (gen.card_cost(cache.get(it.get("id") or "") or {}) or 0, _count(it)), reverse=True)
    return out


def _by_cost(items: list[dict], cache: dict) -> dict[str, list[dict]]:
    buckets = {"0-2": [], "3-4": [], "5-6": [], "7+": []}
    for it in _non_ap(items):
        cost = gen.card_cost(cache.get(it.get("id") or "") or {})
        if cost is None:
            continue
        if cost <= 2:
            buckets["0-2"].append(it)
        elif cost <= 4:
            buckets["3-4"].append(it)
        elif cost <= 6:
            buckets["5-6"].append(it)
        else:
            buckets["7+"].append(it)
    return buckets


def _restricted_in(items: list[dict]) -> list[dict]:
    return [it for it in items if uadb.is_restricted(it.get("id") or "")]


def _result_lines(row: dict, limit: int = 6) -> list[str]:
    lines = []
    for entry in (row.get("recent_result_rows") or [])[:limit]:
        place = placement_of(entry)
        label = uadb.ordinal(place) if place else (entry.get("kind") or "result")
        when = entry.get("date") or ""
        href = entry.get("href") or ""
        title = uadb.no_em(entry.get("subtitle") or entry.get("title") or "list")
        bit = f"{label}" + (f" · {when}" if when else "")
        if href:
            lines.append(
                f'<li><a href="{html.escape(href)}">{html.escape(str(bit))}</a> - {html.escape(title)}</li>'
            )
        else:
            lines.append(f"<li>{html.escape(str(bit))} - {html.escape(title)}</li>")
    return lines


def character_guide_body(guide: dict, cache: dict) -> tuple[str, str, str]:
    row = guide["row"]
    name = row["name"]
    title = row.get("title") or ""
    items = row.get("items") or []
    lists = row.get("lists") or []
    face = _face_item(items, cache, name)
    if not face:
        feat = row.get("feature") or {}
        face = {"id": feat.get("id") or "", "meta": feat.get("meta") or {}, "item": {}}
    meta = face.get("meta") or {}
    cid = face.get("id") or ""
    color = (meta.get("color") or row.get("color") or "").split(";")[0].strip()
    cost = gen.card_cost(meta)
    bp = meta.get("bp") or ""
    trigger = uadb.no_em(meta.get("trigger") or "")
    hub = f"/{row['page']}" if row.get("page") else "/characters.html"
    fours = _ofs(items, 4)
    threes = _ofs(items, 3)
    twos = _ofs(items, 2)
    high = _high_copy(items)
    raids = _raid_cards(items, cache)
    buckets = _by_cost(items, cache)
    restricted = _restricted_in(items)
    n_lists = row["list_count"]
    style = (row.get("style") or "").lower()
    strengths = [gen.pretty_blurb(s) for s in (row.get("strengths") or [])[:2]]
    weaknesses = [gen.pretty_blurb(s) for s in (row.get("weaknesses") or [])[:2]]

    lead = f'<a href="{html.escape(hub)}">{html.escape(name)}</a>'
    if title:
        lead += f' in <a href="{html.escape(gen.series_href(title))}">{html.escape(title)}</a>'
    if color:
        lead = f"{html.escape(color)} {lead}"
    bits = [f"{lead} is the raid face this page is about."]
    if style:
        article = "an" if style[:1] in "aeiou" else "a"
        bits.append(f"TCG Contender files it as {article} {html.escape(style)} list")
        if row.get("contender_tier"):
            bits[-1] += f", Standard tier {html.escape(str(row['contender_tier']))}"
        bits[-1] += "."
    bits.append(
        f"This site is hosting {n_lists} public 50-card list{'s' if n_lists != 1 else ''}"
        + (f", including {row['recent_top8']} recent top 8s" if row.get("recent_top8") else "")
        + "."
    )
    if row.get("tier"):
        bits.append(
            f'The <a href="/tier-list.html">tier list</a> has {html.escape(name)} in {html.escape(row["tier"])}.'
        )
    intro = " ".join(bits)

    how_bits = []
    stat = " · ".join(
        x
        for x in (
            cid,
            f"cost {cost}" if cost is not None else "",
            f"{bp} BP" if bp else "",
            color,
        )
        if x
    )
    if trigger:
        face_label = _card_label({"id": cid, "name": name}, cache) if cid else name
        how_bits.append(f"The printed trigger on {html.escape(face_label)} is: {html.escape(trigger)}")
    else:
        how_bits.append(f"{html.escape(name)} is the character the hosted 50s keep building around.")
    if raids:
        raid_names = _join_and([_card_label(it, cache) for it in raids[:6]])
        how_bits.append(f"Raid printings in the current 50: {html.escape(raid_names)}.")
        how_bits.append(
            "In Union Arena, [Raid] lets you add the card to your hand or perform Raid if the energy is there. "
            "The expensive copy is the ceiling. The cheaper copies with the same name are the steps."
        )
    if strengths:
        take = strengths[0].rstrip(".")
        if take:
            take = take[0].lower() + take[1:]
        how_bits.append(f"Contender's snapshot calls out that {html.escape(take)}.")
    if weaknesses:
        take = weaknesses[0].rstrip(".")
        if take:
            take = take[0].lower() + take[1:]
        how_bits.append(f"The same snapshot flags that {html.escape(take)}.")

    core_bits = []
    if high:
        core_bits.append(
            "High-copy exceptions in the hosted 50: "
            + html.escape(_join_and([f"{_card_label(it, cache)} x{_count(it)}" for it in high]))
            + "."
        )
    if fours:
        core_bits.append(
            "Four-ofs: " + html.escape(_join_and([_card_label(it, cache) for it in fours[:10]])) + "."
        )
    if threes:
        core_bits.append(
            "Three-ofs: " + html.escape(_join_and([_card_label(it, cache) for it in threes[:8]])) + "."
        )
    if twos:
        core_bits.append(
            "Common two-ofs: " + html.escape(_join_and([_card_label(it, cache) for it in twos[:6]])) + "."
        )
    if not core_bits:
        core_bits.append("Open the hub for the current consensus 50. This page tracks the names that keep showing up.")
    core_bits.append(
        f'That average is taken from the featured list on <a href="{html.escape(hub)}">{html.escape(row.get("full") or name)}</a>, then checked against the {n_lists} hosted files.'
    )

    curve_bits = []
    cheap = buckets["0-2"]
    mid = buckets["3-4"]
    high_c = buckets["5-6"]
    late = buckets["7+"]
    if cheap:
        curve_bits.append(
            "<strong>Energy 0-2.</strong> "
            + html.escape(_join_and([_card_label(it, cache) for it in cheap[:6]]))
            + " keep the early turns honest."
        )
    if mid:
        curve_bits.append(
            "<strong>Energy 3-4.</strong> "
            + html.escape(_join_and([_card_label(it, cache) for it in mid[:6]]))
            + " are the mid-curve bodies."
        )
    if high_c:
        curve_bits.append(
            "<strong>Energy 5-6.</strong> "
            + html.escape(_join_and([_card_label(it, cache) for it in high_c[:5]]))
            + "."
        )
    if late:
        curve_bits.append(
            "<strong>Energy 7+.</strong> "
            + html.escape(_join_and([_card_label(it, cache) for it in late[:5]]))
            + " wait on the line. Do not keep a hand of only these."
        )
    if not curve_bits:
        curve_bits.append("The hub 50 is the curve. Cheap setup, then the raid face once the energy is there.")
    curve_bits.append(
        "This is read off the hosted 50, not a hidden playbook. If your locals file plays a different 3-of, trust that file."
    )

    keep = []
    if raids:
        keep.append(f"a Raid {name}")
    if cheap:
        keep.append("at least one 0-2 cost setup card")
    if mid:
        keep.append(f"one {_card_name(mid[0], cache)} if the cheap card missed")
    ship = ["a hand of only 7+ cost finishers"]
    if late and not cheap:
        ship.append("double copies of the most expensive raid with nothing to enable it")
    mull = (
        f"<strong>Keep</strong> {_join_and(keep) or 'the raid face plus a cheap setup card'}. "
        f"<strong>Ship</strong> {_join_and(ship)}."
    )

    flex = []
    if twos:
        flex.append(
            html.escape(_join_and([_card_label(it, cache) for it in twos[:5]]))
            + " are the first slots to shave if your room is all one matchup."
        )
    if threes and len(threes) > 3:
        flex.append(
            html.escape(_card_label(threes[-1], cache)) + " is the 3-of most lists will argue about."
        )
    if restricted:
        flex.append(
            "Restricted in this 50: "
            + html.escape(_join_and([_card_label(it, cache) for it in restricted]))
            + ". Bandai capped those on 17 April 2026. This site flags lists that still play more than one."
        )
    elif title and "evangelion" in title.lower():
        flex.append(
            'Evangelion still has to respect <a href="/guides/restricted-cards.html">Asuka UE15BT/EVA-1-051 and Spear of Gaius UE15BT/EVA-1-063</a> at one copy each.'
        )
    if not flex:
        flex.append("Flex is whatever the latest event 50 on the hub is playing that the consensus is not.")

    results = _result_lines(row)
    if results:
        result_html = "<ul class=\"guide-results\">\n" + "\n".join(f"            {ln}" for ln in results) + "\n          </ul>"
        result_lead = "Recent official and event 50s on this site, not an invented pairing table:"
    else:
        result_html = f'<p>No dated top 8 in the last {RECENT_DAYS} days is on this site yet. Use the hub list and the Contender snapshot, not a guessed win rate.</p>'
        result_lead = ""

    more = [
        f'<a href="{html.escape(hub)}">{html.escape(name)} hub</a>',
        '<a href="/tier-list.html">Tier list</a>',
        '<a href="/guides/">All guides</a>',
        '<a href="/format.html">Format</a>',
    ]
    if title:
        more.insert(1, f'<a href="{html.escape(gen.series_href(title))}">{html.escape(title)}</a>')

    desc = uadb.clip_meta(
        f"{name} Union Arena strategy: "
        + (f"{title} 50-card core, " if title else "")
        + f"raid line, mulligan, and {n_lists} hosted lists."
    )
    page_title = uadb.page_title(f"{name} strategy")
    body = f"""        {uadb.crumb_html([("/", "Home"), ("/guides/", "Guides"), (None, f"{name} strategy")])}
        <h1>{html.escape(name)} strategy</h1>
        <p>{intro}</p>

        <section style="margin-top:22px">
          <div class="section-title">
            <h2>How the raid face works</h2>
            <div class="muted">{html.escape(stat or name)}</div>
          </div>
          <p>{" ".join(how_bits)}</p>
        </section>

        <section style="margin-top:22px">
          <div class="section-title">
            <h2>The current 50-card core</h2>
            <div class="muted">From {n_lists} lists on this site</div>
          </div>
          <p>{" ".join(core_bits)}</p>
        </section>

        <section style="margin-top:22px">
          <div class="section-title">
            <h2>The curve</h2>
            <div class="muted">Energy line · hosted 50</div>
          </div>
          <p>{" ".join(curve_bits)}</p>
        </section>

        <section style="margin-top:22px">
          <div class="section-title">
            <h2>Mulligan</h2>
            <div class="muted">What the 50 implies</div>
          </div>
          <p>{mull} That is inferred from costs in the hosted list, not a coach sheet from a hidden room.</p>
        </section>

        <section style="margin-top:22px">
          <div class="section-title">
            <h2>Tech and flex</h2>
            <div class="muted">First cards to argue about</div>
          </div>
          <p>{" ".join(flex)}</p>
        </section>

        <section style="margin-top:22px">
          <div class="section-title">
            <h2>Recent results</h2>
            <div class="muted">Hosted on this site</div>
          </div>
          {f"<p>{result_lead}</p>" if result_lead else ""}
          {result_html}
          <p class="muted">No matchup percentages here. Union Arena English tables are single-title, so the "meta" is other {html.escape(title or "lists")} in the room, not a cross-IP pairing matrix.</p>
        </section>
        <p class="hub-more">{" · ".join(more)}</p>"""
    return page_title, desc, body


def title_guide_body(guide: dict, cache: dict, plan: dict) -> tuple[str, str, str]:
    row = guide["row"]
    title = row["title"]
    chars = sorted(row.get("chars") or [], key=lambda r: (-r.get("score", 0), r["name"]))
    href = gen.series_href(title)
    names = _join_and([c["name"] for c in chars[:6]])
    top = chars[0] if chars else {}
    n = row["list_count"]
    intro = (
        f'<a href="{html.escape(href)}">{html.escape(title)}</a> is one of the titles current Standard lists keep posting. '
        f"This site has {n} public 50s under that IP. The names that keep showing up are {html.escape(names)}."
    )
    if top:
        intro += (
            f' {html.escape(top["name"])} is the heaviest of those on the '
            f'<a href="/tier-list.html">tier list</a>'
            + (f' ({html.escape(top.get("tier") or "")} tier)' if top.get("tier") else "")
            + "."
        )
    cards = []
    for c in chars[:8]:
        g = None
        for item in plan.get("character_guides") or []:
            if item.get("nkey") == c.get("nkey"):
                g = item
                break
        hub = f"/{c['page']}" if c.get("page") else href
        label = html.escape(c["name"])
        if g:
            cards.append(
                f'<li><a href="{html.escape(g["href"])}">{label} strategy</a> - {c["list_count"]} lists'
                + (f', {c["recent_top8"]} recent top 8s' if c.get("recent_top8") else "")
                + f' · <a href="{html.escape(hub)}">hub</a></li>'
            )
        else:
            cards.append(f'<li><a href="{html.escape(hub)}">{label}</a> - {c["list_count"]} lists</li>')
    restrict = ""
    if "evangelion" in title.lower():
        restrict = (
            '<p>Constructed still limits <strong>Asuka Shikinami Langley <code>UE15BT/EVA-1-051</code></strong> '
            "and <strong>Spear of Gaius <code>UE15BT/EVA-1-063</code></strong> to one copy each. "
            'See the <a href="/guides/restricted-cards.html">restricted cards</a> note.</p>'
        )
    desc = uadb.clip_meta(
        f"{title} Union Arena strategy: the characters current Standard 50s play, hosted list counts, and the title hub."
    )
    page_title = uadb.page_title(f"{title} strategy")
    body = f"""        {uadb.crumb_html([("/", "Home"), ("/guides/", "Guides"), (None, f"{title} strategy")])}
        <h1>{html.escape(title)} strategy</h1>
        <p>{intro}</p>
        <section style="margin-top:22px">
          <div class="section-title">
            <h2>Characters in the title</h2>
            <div class="muted">{len(chars)} names with hosted lists</div>
          </div>
          <ul class="guide-results">
            {chr(10).join(cards)}
          </ul>
          {restrict}
          <p>English events are single-title. You are pairing {html.escape(title)} against {html.escape(title)}, not against every IP on the internet. Build the 50 for the room in front of you.</p>
        </section>
        <p class="hub-more"><a href="{html.escape(href)}">{html.escape(title)} decks</a> · <a href="/tier-list.html">Tier list</a> · <a href="/guides/">All guides</a> · <a href="/format.html">Format</a></p>"""
    return page_title, desc, body


def topic_guide_body(guide: dict, plan: dict) -> tuple[str, str, str]:
    slug = guide["slug"]
    today = plan.get("today") or date.today().isoformat()
    if slug == "how-to-read-a-50":
        title = uadb.page_title("How to read a Union Arena 50")
        desc = "How Union Arena Decklists writes a 50-card list: consensus cores, raid faces, copy caps, and what the hub numbers mean."
        body = f"""        {uadb.crumb_html([("/", "Home"), ("/guides/", "Guides"), (None, "How to read a 50")])}
        <h1>How to read a Union Arena 50</h1>
        <p>Every public list on this site is a 50-card constructed file. The hub at the top of a character page is the consensus or featured 50. The rows under it are individual event, official, and community lists. Updated {html.escape(today)}.</p>
        <section style="margin-top:22px">
          <div class="section-title"><h2>The number on the left</h2><div class="muted">Copies</div></div>
          <p>Most card numbers cap at 4. Restricted Evangelion cards cap at 1. Shadow Soldiers can go to 12. AP cards sit next to the 50, not inside it, and the buy button skips them.</p>
        </section>
        <section style="margin-top:22px">
          <div class="section-title"><h2>The raid face</h2><div class="muted">Why the picture is that character</div></div>
          <p>The picture is the 4-cost-or-higher character the list actually plays, usually a [Raid] card. Click it for that character and color. <a href="/guides/raid-triggers.html">Raid triggers</a> explain the energy line.</p>
        </section>
        <section style="margin-top:22px">
          <div class="section-title"><h2>Consensus versus a single 50</h2><div class="muted">TCG Contender + hosted files</div></div>
          <p>A Contender consensus merges public tournament files and caps copies. A named event row is one player's 50 from one day. If they disagree, the event row wins for that room. The consensus is the starting 50, not law.</p>
        </section>
        <p class="hub-more"><a href="/guides/">Guides</a> · <a href="/tier-list.html">Tier list</a> · <a href="/format.html">Format</a></p>"""
        return title, desc, body
    if slug == "restricted-cards":
        title = uadb.page_title("Restricted cards in Standard")
        desc = "Union Arena restricted cards: Asuka Shikinami Langley UE15BT/EVA-1-051 and Spear of Gaius UE15BT/EVA-1-063, one copy each since 17 April 2026."
        body = f"""        {uadb.crumb_html([("/", "Home"), ("/guides/", "Guides"), (None, "Restricted cards")])}
        <h1>Restricted cards in Standard</h1>
        <p>Bandai limited two Evangelion cards to one copy each, effective 17 April 2026. This site flags any hosted 50 that still plays more than one.</p>
        <section style="margin-top:22px">
          <div class="section-title"><h2>The two cards</h2><div class="muted">Official notice</div></div>
          <ul>
            <li><strong>Asuka Shikinami Langley</strong> <code>UE15BT/EVA-1-051</code></li>
            <li><strong>Spear of Gaius</strong> <code>UE15BT/EVA-1-063</code></li>
          </ul>
          <p class="muted">Official page: <a href="https://www.unionarena-tcg.com/na/rules/limited.php">About Banned/Restricted Cards</a>.</p>
        </section>
        <section style="margin-top:22px">
          <div class="section-title"><h2>What that does to Evangelion 50s</h2><div class="muted">Single-title rooms</div></div>
          <p>Rei and the EVA units still post. They just cannot lean on four Askuas or four Spears. If you are copying an older photo, count those two numbers first.</p>
        </section>
        <p class="hub-more"><a href="/series/evangelion.html">Evangelion decks</a> · <a href="/format.html">Format</a> · <a href="/guides/">Guides</a></p>"""
        return title, desc, body
    if slug == "single-title-standard":
        title = uadb.page_title("Single-title Standard")
        desc = "English Union Arena events are single-title Standard: one anime or manga IP, 50 cards, four copies of a number."
        body = f"""        {uadb.crumb_html([("/", "Home"), ("/guides/", "Guides"), (None, "Single-title Standard")])}
        <h1>Single-title Standard</h1>
        <p>English Union Arena events are almost always one title. A Solo Leveling 50 plays Solo Leveling cards. A Sakamoto Days 50 plays Sakamoto Days cards. Confirm the event before you mix IPs.</p>
        <section style="margin-top:22px">
          <div class="section-title"><h2>What "meta" means here</h2><div class="muted">Not a cross-IP pairing table</div></div>
          <p>The <a href="/tier-list.html">tier list</a> ranks characters that keep showing up across public Standard tables. Your locals pairing is still inside one IP. A Sung Jinwoo guide is about other Solo Leveling 50s, not about beating Rei at the same table.</p>
        </section>
        <section style="margin-top:22px">
          <div class="section-title"><h2>Construction</h2><div class="muted">50 cards</div></div>
          <p>Exactly 50 in the main deck. AP cards sit next to it. Four copies of a number, unless the card is restricted or printed as a high-copy exception. Official events: <a href="https://www.unionarena-tcg.com/na/events/">Bandai events hub</a>.</p>
        </section>
        <p class="hub-more"><a href="/format.html">Format FAQ</a> · <a href="/series.html">Titles</a> · <a href="/guides/">Guides</a></p>"""
        return title, desc, body
    title = uadb.page_title("Raid triggers and the energy line")
    desc = "How Union Arena Raid triggers work on this site: add the card to your hand, or perform Raid when the energy is there."
    body = f"""        {uadb.crumb_html([("/", "Home"), ("/guides/", "Guides"), (None, "Raid triggers")])}
        <h1>Raid triggers and the energy line</h1>
        <p>A lot of the characters on the homepage are Raid faces. The printed line is usually: [Raid] Add this card to your hand, or if you have the required energy, perform Raid with it.</p>
        <section style="margin-top:22px">
          <div class="section-title"><h2>Why lists play four printings of one name</h2><div class="muted">Steps, then the ceiling</div></div>
          <p>Sung Jinwoo, Rei, Saito, and Shin all have cheaper copies and an expensive copy. The cheap ones get you through the early energy. The 7+ cost copy is the raid you actually want to perform. Strategy pages on this site list those printings from the hosted 50, not from memory.</p>
        </section>
        <section style="margin-top:22px">
          <div class="section-title"><h2>How we pick the picture</h2><div class="muted">Home and hubs</div></div>
          <p>The homepage picture is a 4-cost-or-higher Raid character the list plays. If a 50 plays several raiders, the face is the one with the highest listed-median TCGplayer price in that cluster. The hub still lists every public 50 that plays the name.</p>
        </section>
        <p class="hub-more"><a href="/guides/">Guides</a> · <a href="/tier-list.html">Tier list</a> · <a href="/#recent">Recent lists</a></p>"""
    return title, desc, body


def _write_guide_page(guide: dict, title: str, desc: str, body: str, image: str = "") -> str:
    path = guide["path"]
    crumbs = [("/", "Home"), ("/guides/", "Guides"), (f"/{path}", guide["title"])]
    dest = uadb.ROOT / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        uadb.page_chrome(
            title,
            desc,
            "color-red",
            body,
            "guides",
            path=path,
            image=image,
            image_alt=guide["title"],
            json_ld=[
                uadb.website_ld(),
                uadb.breadcrumb_ld(crumbs),
                uadb.webpage_ld(path, title, desc, page_type="Article", date_modified=date.today().isoformat(), image=image),
            ],
        )
    )
    if image:
        gen.remember_image(path, image, guide.get("name") or guide["title"])
    return path


def write_guides_index(plan: dict) -> str:
    def cards(items: list[dict]) -> str:
        rows = []
        for g in items:
            rows.append(
                f"""            <a class="guide-card" href="{html.escape(g['href'])}">
              <strong>{html.escape(g['title'])}</strong>
              <span class="muted">{html.escape(g.get('blurb') or '')}</span>
            </a>"""
            )
        return "\n".join(rows)

    chars = plan.get("character_guides") or []
    titles = plan.get("title_guides") or []
    topics = plan.get("topic_guides") or []
    desc = uadb.clip_meta(
        "Union Arena strategy guides: popular raid faces, title notes, restricted cards, and how to read a 50."
    )
    body = f"""        {uadb.crumb_html([("/", "Home"), (None, "Guides")])}
        <h1>Guides</h1>
        <p>Writeups for the characters current Standard lists actually play, plus the format notes people ask for. These are built from hosted 50s and the TCG Contender snapshot, not empty character stubs.</p>
        <p class="muted"><a href="/tier-list.html">Standard tier list</a> · <a href="/format.html">Format FAQ</a></p>

        <section style="margin-top:22px">
          <div class="section-title">
            <h2>Popular characters</h2>
            <div class="muted">{len(chars)} writeups</div>
          </div>
          <div class="guides-grid" aria-label="Character strategy guides">
{cards(chars)}
          </div>
        </section>

        <section style="margin-top:22px">
          <div class="section-title">
            <h2>Titles</h2>
            <div class="muted">{len(titles)} notes</div>
          </div>
          <div class="guides-grid" aria-label="Title strategy guides">
{cards(titles)}
          </div>
        </section>

        <section style="margin-top:22px">
          <div class="section-title">
            <h2>Format notes</h2>
            <div class="muted">{len(topics)} pages</div>
          </div>
          <div class="guides-grid" aria-label="Format guides">
{cards(topics)}
          </div>
        </section>"""
    dest = uadb.ROOT / "guides" / "index.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        uadb.page_chrome(
            uadb.page_title("Guides"),
            desc,
            "color-red",
            body,
            "guides",
            path="guides/",
            json_ld=[
                uadb.website_ld(),
                uadb.breadcrumb_ld([("/", "Home"), ("/guides/", "Guides")]),
                uadb.item_list_ld(
                    "Union Arena strategy guides",
                    [(g["href"], g["title"]) for g in chars + titles + topics],
                    url="/guides/",
                ),
            ],
        )
    )
    return "guides/"


def write_pages(plan: dict, cache: dict, features: dict | None = None) -> list[str]:
    features = features or {}
    guides_dir = uadb.ROOT / "guides"
    if guides_dir.exists():
        for old in guides_dir.glob("*.html"):
            old.unlink()
    paths = [write_tier_list(plan, cache), write_guides_index(plan)]
    for g in plan.get("character_guides") or []:
        title, desc, body = character_guide_body(g, cache)
        img = _img_for_row(g["row"], cache)
        paths.append(_write_guide_page(g, title, desc, body, image=img))
    for g in plan.get("title_guides") or []:
        title, desc, body = title_guide_body(g, cache, plan)
        paths.append(_write_guide_page(g, title, desc, body))
    for g in plan.get("topic_guides") or []:
        title, desc, body = topic_guide_body(g, plan)
        paths.append(_write_guide_page(g, title, desc, body))
    return paths
