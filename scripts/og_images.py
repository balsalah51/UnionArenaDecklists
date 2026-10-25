#!/usr/bin/env python3
"""Site-drawn Open Graph cards. These are not Bandai card art."""

from __future__ import annotations

from pathlib import Path

import uadb

W, H = 1200, 630
_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_COLORS = {
    "red": (176, 58, 46),
    "blue": (36, 84, 138),
    "green": (39, 110, 72),
    "yellow": (168, 122, 28),
    "purple": (92, 52, 122),
    "black": (42, 42, 42),
}


def _font(size: int, bold: bool = False):
    from PIL import ImageFont

    path = _FONT if bold else _FONT_REG
    if Path(path).is_file():
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def write_card(slug: str, name: str, series: str = "", color: str = "") -> str:
    """Draw one 1200x630 PNG and return the site path."""
    from PIL import Image, ImageDraw

    rel = f"img/og/{uadb.slugify(slug) or 'deck'}.png"
    dest = uadb.ROOT / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    ink = _COLORS.get((color or "").split()[0].lower(), (122, 46, 46))
    image = Image.new("RGB", (W, H), (27, 26, 23))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 28, H), fill=ink)
    draw.text((72, 70), "UNION ARENA DECKLISTS", font=_font(28, bold=True), fill=(243, 216, 210))
    title = (name or "Decklist").strip()
    if len(title) > 42:
        title = title[:41].rsplit(" ", 1)[0] + "…"
    draw.text((72, 220), title, font=_font(72, bold=True), fill=(255, 248, 244))
    sub_bits = [bit for bit in ((color or "").title(), series or "") if bit]
    sub = " · ".join(sub_bits) or "Character hub"
    draw.text((72, 340), sub, font=_font(36), fill=(220, 196, 188))
    draw.text((72, 520), "Fan list index. Not affiliated with Bandai.", font=_font(24), fill=(168, 150, 144))
    image.save(dest, "PNG", optimize=True)
    return f"/{rel}"


def write_for_hubs(hubs: list[dict]) -> int:
    written = 0
    try:
        import PIL  # noqa: F401
    except ImportError:
        uadb.log("og images skipped", "pillow is not installed")
        return 0
    for arch in hubs:
        slug = arch.get("key") or ""
        if not slug:
            continue
        try:
            path = write_card(
                slug,
                arch.get("name") or "Deck",
                arch.get("title") or "",
                arch.get("color") or "",
            )
        except Exception as exc:  # noqa: BLE001
            uadb.log("og image failed", slug, exc)
            continue
        arch["og_image"] = path
        written += 1
    uadb.log("og images", written)
    return written
