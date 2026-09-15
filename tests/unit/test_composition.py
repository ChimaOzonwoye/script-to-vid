"""Composition rules every scene has to keep, whatever the framing.

Written against the layout as it stood before framings were added, so that
the change could only alter what it meant to alter. A composition bug is
invisible in a test that only checks a file was written, so these look at
where things actually landed: text extents in display pixels, and the
pixels in the corner the logo needs.
"""

import numpy as np
import pytest
from matplotlib.text import Text
from PIL import Image

from app import engine, scenes
from app.themes import THEMES

W, H = engine.W, engine.H
SAFE = 0.05                       # nothing important within 5% of an edge
LOGO_BOX = (engine.W - engine.LOGO_MARGIN_PX - engine.LOGO_CORNER_PX,
            engine.LOGO_MARGIN_PX,
            engine.W - engine.LOGO_MARGIN_PX,
            engine.LOGO_MARGIN_PX + engine.LOGO_CORNER_PX)

BEATS = {
    "scene_character": {"expr": "happy", "pose": "cheer", "caption": "A caption"},
    "scene_caption": {"caption": "Never assume, always ask"},
    "scene_duo": {"bubble": "Pay yourself first", "caption": "A caption"},
    "scene_bubbles": {"words": ["soft?", "medium?", "hard?"], "caption": "A caption"},
    "scene_split": {"left": "Before", "right": "After", "caption": "A caption"},
    "scene_chart": {"chart": "growth", "caption": "A caption"},
}


# every combination a real script can produce: framed scenes in each
# framing and on each side, fixed scenes as they come
CASES = []
for _v in sorted(BEATS):
    if _v in ("scene_character", "scene_caption"):
        for _f in scenes.FRAMINGS:
            for _flip in (False, True):
                CASES.append((_v, {"framing": _f, "flip": _flip}))
    else:
        CASES.append((_v, {}))
IDS = [f"{v}-{e.get('framing', 'fixed')}-{'r' if e.get('flip') else 'l'}"
       for v, e in CASES]


def render(visual, extra=None, theme="cream"):
    """Draw one scene and hand back the figure with its renderer ready."""
    beat = {"visual": visual, "say": "narration", "cast_i": 0,
            **BEATS[visual], **(extra or {})}
    fig = engine._fig(THEMES[theme])
    scenes.VISUALS[visual](fig, beat, THEMES[theme])
    fig.canvas.draw()
    return fig


def text_boxes(fig):
    r = fig.canvas.get_renderer()
    out = []
    for t in fig.findobj(Text):
        # matplotlib keeps a hidden tick label for the opposite side of each
        # axis; those report a 1x1 box at the origin
        if not t.get_text().strip() or not t.get_visible():
            continue
        bb = t.get_window_extent(r)
        if bb.width > 0 and bb.height > 0:
            out.append(bb)
    return out


def to_image(fig):
    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())
    return Image.fromarray(buf[..., :3])


@pytest.mark.parametrize("visual,extra", CASES, ids=IDS)
def test_text_stays_inside_the_safe_area(visual, extra):
    fig = render(visual, extra)
    try:
        for bb in text_boxes(fig):
            assert bb.x0 >= W * SAFE - 1, (visual, "text off the left", bb.x0)
            assert bb.x1 <= W * (1 - SAFE) + 1, (visual, "text off the right", bb.x1)
            assert bb.y0 >= H * SAFE - 1, (visual, "text off the bottom", bb.y0)
            assert bb.y1 <= H * (1 - SAFE) + 1, (visual, "text off the top", bb.y1)
    finally:
        import matplotlib.pyplot as plt
        plt.close(fig)


@pytest.mark.parametrize("visual,extra", CASES, ids=IDS)
def test_logo_corner_is_left_clear(visual, extra):
    """The corner logo is drawn over the finished video, so nothing in the
    scene may sit under it."""
    fig = render(visual, extra)
    try:
        im = to_image(fig)
        corner = np.asarray(im.crop(LOGO_BOX)).astype(int)
        bg = np.array([int(THEMES["cream"].bg[i:i + 2], 16) for i in (1, 3, 5)])
        assert np.abs(corner - bg).max() <= 6, f"{visual} draws under the logo"
    finally:
        import matplotlib.pyplot as plt
        plt.close(fig)


@pytest.mark.parametrize("visual", sorted(BEATS))
@pytest.mark.parametrize("theme", sorted(THEMES))
def test_every_scene_renders_in_every_theme(visual, theme, tmp_path):
    fig = render(visual, theme=theme)
    try:
        p = tmp_path / f"{visual}_{theme}.png"
        fig.savefig(p, facecolor=THEMES[theme].bg, dpi=100)
        assert p.stat().st_size > 0
        assert Image.open(p).size == (W, H)
    finally:
        import matplotlib.pyplot as plt
        plt.close(fig)


def test_figure_height_matches_what_is_actually_drawn():
    """figure_height restates draw_character's layout so scenes can scale
    without drawing first. If the body layout moves, this catches it."""
    import matplotlib.pyplot as plt
    from app import characters as ch
    for head in ch.HEADS:
        for body in ch.BODIES:
            fig = engine._fig(THEMES["cream"])
            ax = scenes._stage(fig)
            a = ch.draw_character(ax, 0, 0, s=1.3, head=head, body=body)
            assert abs(a["top"] - ch.figure_height(1.3, head)) < 1e-9
            assert abs(a["head"][1] - ch.HEAD_CENTRE_H * 1.3) < 1e-9
            plt.close(fig)


def test_scale_for_height_is_the_inverse():
    from app import characters as ch
    for head in ch.HEADS:
        s = ch.scale_for_height(9.0, head)
        assert abs(ch.figure_height(s, head) - 9.0) < 1e-9


def test_a_framing_never_repeats_back_to_back():
    """Framings are for beats that ask for a layout by name. Plain narration
    is the presenter now, which holds one position on purpose."""
    from app.script_parser import parse, FRAMED
    text = "\n\n".join(f"> character: happy\n\nParagraph number {i} here."
                       for i in range(12))
    framings = [b["framing"] for b in parse(text)["beats"]
                if b["visual"] in FRAMED]
    assert len(framings) >= 4
    assert all(a != b for a, b in zip(framings, framings[1:]))
    assert len(set(framings)) == len(scenes.FRAMINGS), "all framings get used"


def test_the_layout_choice_travels_on_the_beat_so_the_cache_covers_it():
    """Picked at render time instead, a rebuild would look different from
    the first run while reusing the same cached segments. True of the framing
    on a named beat and of the side the presenter stands on.
    """
    from app import engine
    from app.script_parser import parse, FRAMED

    named = parse("> character: happy\n\nFirst paragraph here.")["beats"]
    framed = [b for b in named if b["visual"] in FRAMED]
    assert framed and all("framing" in b and "flip" in b for b in framed)
    a = dict(framed[0])
    assert engine.segment_key(a, THEMES["cream"], "audio") != \
        engine.segment_key({**a, "framing": "close"}, THEMES["cream"], "audio")

    plain = parse("First paragraph here.\n\nSecond paragraph here.")["beats"]
    assert all("side" in b for b in plain), "the presenter's side is not on the beat"
    b = dict(plain[0])
    assert engine.segment_key(b, THEMES["cream"], "audio") != \
        engine.segment_key({**b, "side": "right"}, THEMES["cream"], "audio")


def test_every_head_shape_fills_the_same_share_of_the_frame():
    """The scale is computed from the figure's height, so a triangle head
    does not come out taller than a square one at the same framing."""
    from app import characters as ch
    for framing, f in scenes.FRAMINGS.items():
        heights = []
        for i in range(len(scenes._CAST)):
            beat = {"visual": "scene_caption", "cast_i": i, "framing": framing}
            head, _ = scenes._shape(beat)
            _, _, s = scenes._place(beat)
            heights.append(ch.figure_height(s, head, ch.HEAD_RATIO))
        want = f["height"] * scenes.STAGE_H
        assert max(abs(h - want) for h in heights) < 1e-9, framing


def test_figures_are_off_centre():
    """Dead centre with a caption underneath is the look being avoided."""
    for framing in scenes.FRAMINGS:
        for flip in (False, True):
            beat = {"visual": "scene_caption", "cast_i": 0,
                    "framing": framing, "flip": flip}
            x, _, _ = scenes._place(beat)
            assert abs(x) > scenes.STAGE_W * 0.08, (framing, flip, x)


def test_the_page_serves_its_own_fonts():
    """Vendored so the app never reaches the network for a typeface and
    there is no flash of unstyled text."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    css = (root / "app" / "static" / "style.css").read_text()
    assert "fonts.googleapis" not in css and "fonts.gstatic" not in css
    for face in ("inter-latin", "fraunces-latin"):
        assert f"/static/fonts/{face}.woff2" in css
        assert (root / "app" / "static" / "fonts" / f"{face}.woff2").exists()
    assert (root / "app" / "static" / "fonts" / "OFL.txt").exists()


def test_the_bare_frame_draws_nothing_in_the_middle():
    """The complaint that produced it: the middle held the first nine words of
    the paragraph, set large, while the subtitle ran the same paragraph along
    the bottom. That is not a picture of anything, it is the sentence cut
    short and made big.
    """
    import numpy as np
    from PIL import Image
    import tempfile
    from pathlib import Path
    from dataclasses import replace
    from app import engine
    from app.themes import THEMES

    beat = {"visual": "scene_story", "cast_i": 1, "say": "",
            "caption": "Mistake number three: ignoring fees", "rolling": ["x"]}
    T = replace(THEMES["nightfall"], effect="none")
    with tempfile.TemporaryDirectory() as d:
        a = Path(d) / "with_words.png"
        b = Path(d) / "bare.png"
        engine.render_slide(dict(beat), a, replace(T, composition="type"))
        engine.render_slide(dict(beat), b, T)
        ink = lambda p: np.asarray(Image.open(p).convert("L")).astype(int)
        # the headline version puts bright type across the middle band
        mid = slice(340, 740)
        assert ink(a)[mid].max() > 200
        assert ink(b)[mid].max() < 120, "something is still drawn in the middle"


def test_no_composition_prints_the_beat_twice():
    """Every shape built out of the headline has to suppress the burned
    subtitle, or the opening of the beat appears in two sizes at once. Card
    was the one left off that list and it was the one that shipped doing it.
    """
    from app import scenes
    assert set(scenes.COMPOSITIONS) - set(scenes.TYPE_LED) == {"bare"}
