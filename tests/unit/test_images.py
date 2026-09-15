"""Pictures the user brings.

The only real work is fitting. An image dropped into a 1920x1080 frame is
almost never that shape, and the two obvious answers are both wrong:
stretching distorts faces, and cropping to fill throws away the top and bottom
of a portrait, which is where the face is.
"""

import pytest
from PIL import Image

from app import images


def make(tmp_path, w, h, name="in.png"):
    im = Image.new("RGB", (w, h), (40, 60, 90))
    for x in range(0, w, 2):                    # a pattern, to spot a stretch
        for y in range(0, h, 2):
            im.putpixel((x, y), (200, 90, 60))
    p = tmp_path / name
    im.save(p)
    return p


@pytest.mark.parametrize("w,h", [(1080, 1920), (1600, 900), (1000, 1000),
                                 (3000, 1680), (400, 300), (2048, 512)])
def test_anything_comes_out_frame_shaped(tmp_path, w, h):
    out = images.fit(make(tmp_path, w, h), tmp_path / "out.png")
    assert Image.open(out).size == (images.W, images.H)


def test_a_portrait_keeps_all_of_itself(tmp_path):
    """Cropping a portrait to fill 16:9 cuts the head off. The whole picture
    has to survive, sitting over a blurred copy of itself."""
    src = Image.new("RGB", (600, 1200), (0, 0, 0))
    src.putpixel((300, 20), (255, 0, 0))        # a mark near the very top
    src.putpixel((300, 1180), (0, 255, 0))      # and the very bottom
    p = tmp_path / "tall.png"
    src.save(p)
    out = Image.open(images.fit(p, tmp_path / "out.png")).convert("RGB")
    px = list(out.getdata())  # noqa: the flattened accessor is Pillow 14
    assert any(r > 150 and g < 90 for r, g, b in px), "lost the top of the image"
    assert any(g > 150 and r < 90 for r, g, b in px), "lost the bottom"


def test_a_sixteen_by_nine_image_is_not_padded(tmp_path):
    """Already the right shape means fill the frame, not sit in the middle of
    a blurred version of itself."""
    p = make(tmp_path, 1280, 720)
    out = Image.open(images.fit(p, tmp_path / "out.png")).convert("RGB")
    # a padded result has a blurred band at the edges; a covered one does not
    assert out.getpixel((4, images.H // 2)) != out.getpixel((images.W - 5, images.H // 2)) \
        or out.getpixel((4, 4)) != (0, 0, 0)
    assert out.size == (images.W, images.H)


def test_a_crafted_name_cannot_climb_out_of_the_folder(tmp_path):
    for bad in ("../../etc/passwd", "..\\\\windows\\\\system32", "/etc/shadow", ""):
        name = images.safe_name(bad)
        assert "/" not in name and "\\\\" not in name and ".." not in name
        assert name


def test_a_huge_image_is_refused_before_it_is_resized(tmp_path):
    """A small file can decode to an enormous bitmap. Better a plain refusal
    than the machine swapping."""
    class Fake:
        width, height = 30000, 30000
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def convert(self, mode): raise AssertionError("should never get here")
    import app.images as mod
    real = mod.Image.open
    mod.Image.open = lambda *a, **k: Fake()
    try:
        with pytest.raises(ValueError):
            mod.fit("anything", tmp_path / "out.png")
    finally:
        mod.Image.open = real


def test_beats_take_the_pictures_in_order_and_repeat(tmp_path):
    """First picture, first paragraph. Cycling means one picture can carry a
    whole script."""
    (tmp_path / "images").mkdir()
    for n in ("00-a.png", "01-b.png"):
        Image.new("RGB", (16, 9)).save(tmp_path / "images" / n)
    beats = [{"say": str(i)} for i in range(5)]
    got = [images.assign(beats, tmp_path)[i]["image"] for i in range(5)]
    assert [p.split("/")[-1] for p in got] == \
        ["00-a.png", "01-b.png", "00-a.png", "01-b.png", "00-a.png"]


def test_no_pictures_leaves_the_beats_alone(tmp_path):
    beats = [{"say": "hello"}]
    assert images.assign(beats, tmp_path) == beats


def test_the_commonest_photo_aspect_fills_the_frame(tmp_path):
    """3:2 is what cameras and phones shoot. At the tolerance this shipped
    with it was 15.6% off 16:9 and so arrived with bars down both sides,
    which is the opposite of fitting. Cropping takes 7.8% off the top and the
    bottom instead.
    """
    from PIL import Image
    import numpy as np
    from app import images

    for w, h in ((2100, 1400), (3000, 2000), (1200, 800)):
        src = tmp_path / f"p{w}.png"
        Image.new("RGB", (w, h), (40, 90, 200)).save(src)
        out = np.asarray(Image.open(images.fit(src, tmp_path / f"o{w}.png")))
        # a pillarboxed frame has a blurred band down each edge, so the
        # columns at the sides would not be the flat colour of the picture
        assert out.shape[:2] == (1080, 1920)
        for col in (2, 40, 1879, 1917):
            assert abs(int(out[:, col].mean()) - int(out[:, 960].mean())) < 3, \
                f"{w}x{h} came back with a band at column {col}"


def test_an_aspect_too_far_off_is_sat_inside_the_frame(tmp_path):
    """The tolerance has to stop somewhere. Cropping a 4:3 or a portrait hard
    enough to fill 16:9 takes a quarter or more off the height, which is where
    heads come off, so those keep all of themselves over a blurred copy.
    """
    from PIL import Image
    import numpy as np
    from app import images

    for w, h in ((1200, 900), (1080, 1080), (900, 1600)):
        src = tmp_path / f"q{w}x{h}.png"
        Image.new("RGB", (w, h), (240, 60, 30)).save(src)
        out = np.asarray(Image.open(images.fit(src, tmp_path / f"r{w}x{h}.png")))
        assert out.shape[:2] == (1080, 1920)
        # all of it is still there: the tallest run of the original colour
        # spans the full height of the frame
        hit = (np.abs(out.astype(int) - [240, 60, 30]).max(axis=2) < 6)
        assert hit[:, 960].sum() == 1080, f"{w}x{h} lost part of itself"
