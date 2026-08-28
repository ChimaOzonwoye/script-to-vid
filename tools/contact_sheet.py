"""Renders every scene at every framing onto one sheet, to look at.

    python tools/contact_sheet.py [theme] [out.png]

A composition problem is obvious in a grid and invisible in a test that
only checks a file was written. Worth running after touching scenes.py or
adding a layout.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from app import engine, scenes  # noqa: E402
from app.themes import THEMES  # noqa: E402

CAPTION = "Stop the cooking"

# what to draw in each cell, and which framings each scene can take
CELLS = [
    ("scene_character", {"expr": "happy", "pose": "cheer", "prop": "piggy",
                         "caption": CAPTION}, ("wide", "medium", "close")),
    ("scene_caption", {"caption": "Never assume, always ask"},
     ("wide", "medium", "close")),
    ("scene_duo", {"bubble": "Pay yourself first", "caption": CAPTION}, (None,)),
    ("scene_bubbles", {"words": ["soft?", "medium?", "hard?"],
                       "caption": CAPTION}, (None,)),
    ("scene_split", {"left": "Straight from the pan", "right": "Into cold water",
                     "caption": CAPTION}, (None,)),
    ("scene_chart", {"chart": "growth", "caption": CAPTION}, (None,)),
]

THUMB = (480, 270)


def main():
    theme = THEMES[sys.argv[1] if len(sys.argv) > 1 else "cream"]
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "contact-sheet.png")

    shots = []
    for i, (visual, extra, framings) in enumerate(CELLS):
        for j, framing in enumerate(framings):
            beat = {"visual": visual, "say": "narration", "cast_i": i,
                    "flip": bool(j % 2), **extra}
            if framing:
                beat["framing"] = framing
            tmp = out.with_name(f".cell_{visual}_{framing}.png")
            engine.render_slide(beat, tmp, theme)
            shots.append((f"{visual}  {framing or 'fixed'}", tmp))

    cols = 3
    rows = (len(shots) + cols - 1) // cols
    pad, label = 12, 22
    sheet = Image.new("RGB", (cols * (THUMB[0] + pad) + pad,
                              rows * (THUMB[1] + label + pad) + pad), "#222222")
    draw = ImageDraw.Draw(sheet)
    for k, (name, path) in enumerate(shots):
        im = Image.open(path).resize(THUMB, Image.LANCZOS)
        x = pad + (k % cols) * (THUMB[0] + pad)
        y = pad + (k // cols) * (THUMB[1] + label + pad)
        sheet.paste(im, (x, y))
        draw.text((x + 2, y + THUMB[1] + 4), name, fill="#dddddd")
        path.unlink()
    sheet.save(out)
    print(f"{out}  {len(shots)} shots")


if __name__ == "__main__":
    main()
