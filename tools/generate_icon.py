"""Draws the app icon: assets/icon.ico and assets/icon.png.

    python tools/generate_icon.py

The character's head on a brand tile. Thin full-body line art disappears at
16 px, so the icon is just the face, which still reads at tab and taskbar
size. Rerun after changing the palette.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"                  # icon.ico, for the desktop shortcut
STATIC = ROOT / "app" / "static"       # icon.png, for the browser tab
SIZES = [16, 24, 32, 48, 64, 128, 256]

TEAL = "#0f766e"
GOLD = "#c8912c"
INK = "#14120d"
SKIN = "#fffdf6"

S = 1024          # drawn large, then downsampled so the curves stay smooth


def draw(im):
    u = S / 256.0                      # so the numbers below read as 256ths

    # The tile is also the clip: the sill runs full width, so drawing it
    # straight on would square off the two rounded bottom corners.
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1],
                                           radius=58 * u, fill=255)
    tile = Image.new("RGBA", (S, S), TEAL)
    td = ImageDraw.Draw(tile)
    # a sill along the bottom, the ground line every scene stands on
    td.rectangle([0, S - 30 * u, S, S], fill=GOLD)
    td.rectangle([0, S - 30 * u, S, S - 22 * u], fill=INK)
    im.paste(tile, (0, 0), mask)

    d = ImageDraw.Draw(im)

    # head
    hx0, hy0, hx1, hy1 = 44 * u, 40 * u, 212 * u, 196 * u
    d.rounded_rectangle([hx0, hy0, hx1, hy1], radius=54 * u,
                        fill=SKIN, outline=INK, width=int(9 * u))

    cx = (hx0 + hx1) / 2
    ey = 112 * u
    er, pr = 27 * u, 12.5 * u
    for dx in (-38 * u, 38 * u):
        d.ellipse([cx + dx - er, ey - er, cx + dx + er, ey + er],
                  fill="#ffffff", outline=INK, width=int(6 * u))
        d.ellipse([cx + dx - pr, ey - pr, cx + dx + pr, ey + pr], fill=INK)

    # brows, the part that carries the expression
    for dx in (-38 * u, 38 * u):
        d.line([cx + dx - 26 * u, ey - 44 * u, cx + dx + 26 * u, ey - 44 * u],
               fill=INK, width=int(9 * u))

    # a small smile
    d.arc([cx - 40 * u, ey + 6 * u, cx + 40 * u, ey + 66 * u],
          start=20, end=160, fill=INK, width=int(9 * u))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw(im)

    png = STATIC / "icon.png"
    im.resize((512, 512), Image.LANCZOS).save(png)

    ico = OUT / "icon.ico"
    im.resize((256, 256), Image.LANCZOS).save(
        ico, sizes=[(s, s) for s in SIZES])
    print(f"{png} and {ico} written")


if __name__ == "__main__":
    main()
