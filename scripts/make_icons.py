#!/usr/bin/env python3
"""Build the site mark: a fanned card stack with a 50-card list on the face."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BG = (122, 46, 46, 255)  # #7a2e2e
GOLD = (201, 163, 106, 255)  # #c9a36a
WARM = (228, 201, 160, 255)  # #e4c9a0
CREAM = (244, 239, 234, 255)  # #f4efea
INK = (122, 46, 46, 255)

# Shared 64-unit geometry so SVG and PNG stay aligned.
LEFT_CARD = (11.0, 14.0, 26.0, 38.0, -16)
RIGHT_CARD = (27.0, 14.0, 26.0, 38.0, 16)
FRONT_CARD = (19.0, 12.0, 26.0, 40.0, 0)
DIAMOND = ((32.0, 17.6), (35.5, 22.2), (32.0, 26.8), (28.5, 22.2))
LINES = ((24.0, 31.0, 16.0), (24.0, 36.2, 13.2), (24.0, 41.4, 10.4))
LINE_H = 2.2
CARD_RX = 3.4


def _card_layer(width: int, height: int, fill: tuple[int, int, int, int], radius: int) -> Image.Image:
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=radius, fill=fill)
    return layer


def _paste_card(
    canvas: Image.Image,
    unit: float,
    x: float,
    y: float,
    w: float,
    h: float,
    fill: tuple[int, int, int, int],
    angle: float,
) -> None:
    card = _card_layer(max(2, int(w * unit)), max(2, int(h * unit)), fill, max(1, int(CARD_RX * unit)))
    if angle:
        card = card.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
    cx = (x + w / 2) * unit
    cy = (y + h / 2) * unit
    canvas.alpha_composite(card, (int(cx - card.width / 2), int(cy - card.height / 2)))


def make_mark(size: int) -> Image.Image:
    """Solid square so Google's circular search mask stays filled."""
    work = 512
    unit = work / 64.0
    im = Image.new("RGBA", (work, work), BG)
    _paste_card(im, unit, *LEFT_CARD[:4], GOLD, LEFT_CARD[4])
    _paste_card(im, unit, *RIGHT_CARD[:4], WARM, RIGHT_CARD[4])
    _paste_card(im, unit, *FRONT_CARD[:4], CREAM, FRONT_CARD[4])
    draw = ImageDraw.Draw(im)
    draw.polygon([(x * unit, y * unit) for x, y in DIAMOND], fill=INK)
    for x, y, width in LINES:
        draw.rounded_rectangle(
            (x * unit, y * unit, (x + width) * unit, (y + LINE_H) * unit),
            radius=max(1, int(LINE_H * unit / 2)),
            fill=INK,
        )
    return im.resize((size, size), Image.Resampling.LANCZOS)


def mark_svg() -> str:
    def card(x: float, y: float, w: float, h: float, fill: str, angle: float) -> str:
        cx, cy = x + w / 2, y + h / 2
        transform = f' transform="rotate({angle} {cx:.1f} {cy:.1f})"' if angle else ""
        return (
            f'  <rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'rx="{CARD_RX}" fill="{fill}"{transform}/>'
        )

    diamond = " ".join(f"{x:.1f},{y:.1f}" for x, y in DIAMOND)
    lines = "\n".join(
        f'  <rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{LINE_H}" rx="1.1" fill="#7a2e2e"/>'
        for x, y, w in LINES
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" '
        'aria-label="Union Arena Decklists">\n'
        '  <rect width="64" height="64" fill="#7a2e2e"/>\n'
        f'{card(*LEFT_CARD[:4], "#c9a36a", LEFT_CARD[4])}\n'
        f'{card(*RIGHT_CARD[:4], "#e4c9a0", RIGHT_CARD[4])}\n'
        f'{card(*FRONT_CARD[:4], "#f4efea", FRONT_CARD[4])}\n'
        f'  <polygon points="{diamond}" fill="#7a2e2e"/>\n'
        f"{lines}\n"
        "</svg>\n"
    )


def write_svg(path: Path) -> None:
    path.write_text(mark_svg(), encoding="utf-8")


def main() -> None:
    img_dir = ROOT / "img"
    img_dir.mkdir(exist_ok=True)
    sizes = {
        48: img_dir / "icon-48.png",
        96: img_dir / "icon-96.png",
        180: img_dir / "apple-touch-icon.png",
        192: img_dir / "icon-192.png",
        512: img_dir / "icon-512.png",
    }
    images = {size: make_mark(size) for size in sizes}
    for size, dest in sizes.items():
        images[size].save(dest, "PNG", optimize=True)
    images[48].save(
        ROOT / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48)],
    )
    write_svg(ROOT / "favicon.svg")
    write_svg(img_dir / "logo.svg")
    (ROOT / "site.webmanifest").write_text(
        """{
  "name": "Union Arena Decklists",
  "short_name": "UAD",
  "description": "50-card Union Arena TCG decklists for Standard, grouped by anime and manga title.",
  "start_url": "/",
  "scope": "/",
  "display": "browser",
  "background_color": "#f7f5f3",
  "theme_color": "#7a2e2e",
  "icons": [
    {
      "src": "/img/icon-48.png",
      "sizes": "48x48",
      "type": "image/png"
    },
    {
      "src": "/img/icon-96.png",
      "sizes": "96x96",
      "type": "image/png"
    },
    {
      "src": "/img/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/img/icon-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any"
    }
  ]
}
""",
        encoding="utf-8",
    )
    print("wrote", ", ".join(p.name for p in [ROOT / "favicon.ico", ROOT / "favicon.svg", *sizes.values(), img_dir / "logo.svg"]))


if __name__ == "__main__":
    main()
