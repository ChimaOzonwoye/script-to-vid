"""What a background may and may not do to the frame it is drawn in.

A background is the one thing in a scene that is drawn everywhere, so the
rules it has to keep are about staying out of the way: off the logo, off the
caption, behind the figure, and quiet enough in every theme that the figure
still reads as the subject.
"""

import numpy as np
import pytest
from matplotlib.colors import to_rgba
from PIL import Image

from app import backgrounds as bg, engine, scenes
from app.themes import THEMES

NAMED = [n for n in bg.BACKGROUNDS if n != "plain"]
LOGO_BOX = (engine.W - engine.LOGO_MARGIN_PX - engine.LOGO_CORNER_PX,
            engine.LOGO_MARGIN_PX,
            engine.W - engine.LOGO_MARGIN_PX,
            engine.LOGO_MARGIN_PX + engine.LOGO_CORNER_PX)

BEAT = {"visual": "scene_character", "say": "narration", "expr": "happy",
        "pose": "offer", "caption": "A caption", "cast_i": 0,
        "framing": "medium", "flip": False}


def render(name, tmp_path, theme="cream", beat=None, framing="medium"):
    b = {**BEAT, **(beat or {}), "framing": framing, "background": name}
    p = tmp_path / f"{name}_{theme}_{framing}.png"
    engine.render_slide(b, p, THEMES[theme])
    return np.asarray(Image.open(p).convert("RGB")).astype(int)


@pytest.mark.parametrize("name", NAMED)
@pytest.mark.parametrize("theme", sorted(THEMES))
def test_a_background_never_reaches_the_logo(name, theme, tmp_path):
    im = render(name, tmp_path, theme)
    x0, y0, x1, y1 = LOGO_BOX
    corner = im[y0:y1, x0:x1]
    page = np.array([int(THEMES[theme].bg[i:i + 2], 16) for i in (1, 3, 5)])
    assert np.abs(corner - page).max() <= 6, f"{name} draws under the logo"


def stage_boxes(name):
    """Every patch the background drew, in stage units."""
    fig = engine._fig(THEMES["cream"])
    ax = scenes._stage(fig, {"background": name}, THEMES["cream"])
    out = []
    for artist in list(ax.patches) + list(ax.lines):
        bb = artist.get_window_extent()
        (x0, y0), (x1, y1) = ax.transData.inverted().transform(
            [(bb.x0, bb.y0), (bb.x1, bb.y1)])
        face = getattr(artist, "get_facecolor", lambda: (0, 0, 0, 0))()
        # a shape filled with the page colour is a hole, not ink on the wall
        page = to_rgba(THEMES["cream"].bg)
        filled = face[3] > 0 and max(abs(a - b) for a, b in zip(face, page)) > 0.01
        out.append((x0, y0, x1, y1, filled))
    import matplotlib.pyplot as plt
    plt.close(fig)
    return out


@pytest.mark.parametrize("name", NAMED)
def test_wall_furniture_leaves_the_middle_clear(name):
    """A wide framing puts a head at about two thirds height in the middle
    third of the frame, and a filled shape hung on the wall right behind one
    reads as a mistake rather than as depth. Anything standing on the floor
    is exempt: it is below the head, and a sofa that stopped short of the
    middle would not look like a room.
    """
    for x0, y0, x1, y1, filled in stage_boxes(name):
        if not filled or y0 < scenes.GROUND_Y + 3.2:
            continue
        assert x0 >= bg.WALL_GAP or x1 <= -bg.WALL_GAP, (
            name, "a filled shape on the wall crosses the middle", (x0, x1))


@pytest.mark.parametrize("name", NAMED)
def test_a_background_stays_below_the_caption(name, tmp_path):
    fig = engine._fig(THEMES["cream"])
    ax = scenes._stage(fig, {"background": name}, THEMES["cream"])
    ys = []
    for artist in list(ax.patches) + list(ax.lines):
        bb = artist.get_window_extent()
        ys.append(ax.transData.inverted().transform((bb.x1, bb.y1))[1])
    assert max(ys) <= bg.TOP + 0.4, (name, max(ys))
    import matplotlib.pyplot as plt
    plt.close(fig)


@pytest.mark.parametrize("name", NAMED)
def test_a_background_is_quieter_than_the_figure(name, tmp_path):
    """Drawn as dark as the character it would compete with it, so the ink
    a background puts on the page is checked against the ink a figure does."""
    plain = render("plain", tmp_path)
    room = render(name, tmp_path)
    page = np.array([int(THEMES["cream"].bg[i:i + 2], 16) for i in (1, 3, 5)])
    figure_ink = (np.abs(plain - page).max(axis=2) > 90).sum()
    added = (np.abs(room - page).max(axis=2) > 90) & \
            ~(np.abs(plain - page).max(axis=2) > 90)
    assert added.sum() < figure_ink, (name, added.sum(), figure_ink)


def test_plain_draws_nothing_at_all(tmp_path):
    """The default has to leave every existing scene byte for byte as it was."""
    b = {**BEAT}
    without = tmp_path / "without.png"
    engine.render_slide(b, without, THEMES["cream"])
    with_plain = tmp_path / "with.png"
    engine.render_slide({**b, "background": "plain"}, with_plain, THEMES["cream"])
    assert without.read_bytes() == with_plain.read_bytes()


def test_an_unknown_name_falls_back_to_plain(tmp_path):
    assert (render("nonsense", tmp_path) == render("plain", tmp_path)).all()


@pytest.mark.parametrize("name", NAMED)
def test_a_close_up_shows_the_wall_and_no_floor(name, tmp_path):
    """A close-up stands the figure far below the frame, so the room has to
    come apart: the wall behind the head stays, and the floor and everything
    standing on it goes, rather than a floor line crossing a chin."""
    close = render(name, tmp_path, framing="close")
    plain = render("plain", tmp_path, framing="close")
    changed = np.abs(close - plain).max(axis=2) > 8
    # the bottom third of a close-up is all character; a room may not draw there
    assert changed[720:].sum() == 0, (name, "the floor is still in frame")
