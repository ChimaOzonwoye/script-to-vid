"""Pictures a user brings to a project.

This project draws everything from code and will not generate images, because
that needs a graphics card or a bill. It can still use images somebody made
elsewhere, and that is the honest answer to wanting photographic or model
generated figures in a video: bring your own.

The whole job here is fitting. An image dropped into a 1920x1080 frame is
almost never 1920x1080, and the two usual answers are both bad: stretching
distorts faces, and cropping to fill throws away the top and bottom of a
portrait, which is exactly where a face is. So:

  * close to 16:9 already: scale to cover and crop the small overhang
  * anything else: sit the whole image in the middle of the frame over a
    blurred, enlarged copy of itself

The second is what phones and streaming apps do with the wrong shape, and it
works because the backdrop is the same picture, so the colours always agree.
Fitting happens once at upload, so every image on disk is already the frame
size and nothing at render time has to think about it.
"""

import re

from PIL import Image, ImageFilter

W, H = 1920, 1080
FRAME = W / H
COVER_TOLERANCE = 0.12      # how far from 16:9 still crops rather than pads
SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")
MAX_PIXELS = 50_000_000     # refuse a decompression bomb before resizing it


def safe_name(name):
    """A filename that cannot climb out of the project's images folder."""
    stem = re.sub(r"[^a-z0-9]+", "-", (name or "").lower().rsplit(".", 1)[0])
    return (stem.strip("-") or "image")[:48]


def fit(src, dst):
    """Write `src` into `dst` as exactly one 1920x1080 frame."""
    with Image.open(src) as im:
        if im.width * im.height > MAX_PIXELS:
            raise ValueError("that image is too large to use")
        im = im.convert("RGB")
        ratio = im.width / im.height
        if abs(ratio - FRAME) / FRAME <= COVER_TOLERANCE:
            scale = max(W / im.width, H / im.height)
            big = im.resize((max(W, int(im.width * scale + 0.5)),
                             max(H, int(im.height * scale + 0.5))),
                            Image.LANCZOS)
            left, top = (big.width - W) // 2, (big.height - H) // 2
            out = big.crop((left, top, left + W, top + H))
        else:
            # backdrop first: the same picture, filling the frame and blurred
            # far enough that no edge of it reads as a second image
            scale = max(W / im.width, H / im.height)
            back = im.resize((max(W, int(im.width * scale + 0.5)),
                             max(H, int(im.height * scale + 0.5))),
                            Image.LANCZOS)
            left, top = (back.width - W) // 2, (back.height - H) // 2
            out = back.crop((left, top, left + W, top + H)).filter(
                ImageFilter.GaussianBlur(38))
            fitted = min(W / im.width, H / im.height)
            card = im.resize((int(im.width * fitted + 0.5),
                              int(im.height * fitted + 0.5)), Image.LANCZOS)
            out.paste(card, ((W - card.width) // 2, (H - card.height) // 2))
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst, "PNG")
    return dst


def listing(project):
    """The project's images, in the order beats will use them."""
    d = project / "images"
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir() if p.suffix.lower() == ".png")


def assign(beats, project):
    """Give each beat an image, in order, cycling when there are fewer.

    In order is the only rule a person can hold in their head: the first
    picture goes with the first paragraph. Cycling rather than stopping means
    a single image works as a backdrop for a whole script.
    """
    files = listing(project)
    if not files:
        return beats
    return [{**b, "image": str(files[i % len(files)])}
            for i, b in enumerate(beats)]
