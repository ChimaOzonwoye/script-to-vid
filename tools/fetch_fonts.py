"""Vendors the two typefaces into app/static/fonts.

    python tools/fetch_fonts.py

Run once, by a developer, and the files are committed. The app never
fetches a font at runtime: everything is served from disk, so there is no
network dependency and no flash of unstyled text.

Both families are SIL Open Font License 1.1, which allows bundling and
redistribution. The licence text is written out next to them.
"""

import re
import sys
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "static" / "fonts"

# a modern user agent, or the API hands back .ttf instead of .woff2
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

FAMILIES = {
    # the reading and interface face
    "inter": "Inter:wght@400..700",
    # the display face, warm and a little wonky, to match the drawn look
    "fraunces": "Fraunces:opsz,wght@9..144,500..800",
}

WANT_SUBSETS = ("latin", "latin-ext")

OFL = """These fonts are licensed under the SIL Open Font License, Version 1.1.

Inter: Copyright (c) 2016 The Inter Project Authors.
Fraunces: Copyright (c) 2019 The Fraunces Project Authors.

The full licence is at https://openfontlicense.org and permits bundling and
redistribution with this software, including in commercial use, provided the
fonts are not sold on their own.
"""


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, spec in FAMILIES.items():
        css = get(f"https://fonts.googleapis.com/css2?family={spec}"
                  f"&display=swap").decode()
        # the API emits one @font-face per subset, each preceded by a comment
        blocks = re.split(r"/\*\s*([\w\-\[\]]+)\s*\*/", css)
        saved = 0
        for i in range(1, len(blocks) - 1, 2):
            subset, body = blocks[i], blocks[i + 1]
            if subset not in WANT_SUBSETS:
                continue
            m = re.search(r"url\((https://[^)]+\.woff2)\)", body)
            if not m:
                continue
            dst = OUT / f"{name}-{subset}.woff2"
            dst.write_bytes(get(m.group(1)))
            print(f"  {dst.name}  {dst.stat().st_size // 1024} KB")
            saved += 1
        if not saved:
            sys.exit(f"no woff2 found for {name}")
    (OUT / "OFL.txt").write_text(OFL)
    print("fonts vendored")


if __name__ == "__main__":
    main()
