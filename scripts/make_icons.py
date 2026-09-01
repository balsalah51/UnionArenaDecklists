#!/usr/bin/env python3
"""Build the square UA brand marks Google Search can show as a favicon."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BG = (122, 46, 46, 255)  # #7a2e2e
FG = (244, 239, 234, 255)  # #f4efea
FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
MARK = "UA"


def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT), size)


def make_mark(size: int) -> Image.Image:
    """Solid square so Google's circular search mask stays filled."""
    scale = 8
    canvas = size * scale
    im = Image.new("RGBA", (canvas, canvas), BG)
    draw = ImageDraw.Draw(im)
    lo, hi = 8, canvas
    chosen = _font(max(8, canvas // 2))
    for _ in range(18):
        mid = (lo + hi) // 2
        font = _font(mid)
        bbox = draw.textbbox((0, 0), MARK, font=font)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        if width <= canvas * 0.78 and height <= canvas * 0.72:
            chosen = font
            lo = mid + 1
        else:
            hi = mid - 1
    bbox = draw.textbbox((0, 0), MARK, font=chosen)
    x = (canvas - (bbox[2] - bbox[0])) / 2 - bbox[0]
    y = (canvas - (bbox[3] - bbox[1])) / 2 - bbox[1]
    draw.text((x, y), MARK, font=chosen, fill=FG)
    return im.resize((size, size), Image.Resampling.LANCZOS)


def write_svg(path: Path) -> None:
    path.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="Union Arena Decklists">
  <rect width="64" height="64" fill="#7a2e2e"/>
  <text x="32" y="44" text-anchor="middle" font-family="Arial Black, DejaVu Sans, sans-serif" font-size="26" font-weight="700" fill="#f4efea">UA</text>
</svg>
""",
        encoding="utf-8",
    )


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
    ico = images[48]
    ico.save(
        ROOT / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48)],
    )
    write_svg(ROOT / "favicon.svg")
    (ROOT / "site.webmanifest").write_text(
        """{
  "name": "Union Arena Decklists",
  "short_name": "UAD",
  "description": "Union Arena Standard metagame: tier list, top decks, and 50-card lists by anime and manga title.",
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
    print("wrote", ", ".join(p.name for p in [ROOT / "favicon.ico", ROOT / "favicon.svg", *sizes.values()]))


if __name__ == "__main__":
    main()
