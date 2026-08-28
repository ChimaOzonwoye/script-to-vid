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


@pytest.mark.parametrize("visual", sorted(BEATS))
def test_text_stays_inside_the_safe_area(visual):
    fig = render(visual)
    try:
        for bb in text_boxes(fig):
            assert bb.x0 >= W * SAFE - 1, (visual, "text off the left", bb.x0)
            assert bb.x1 <= W * (1 - SAFE) + 1, (visual, "text off the right", bb.x1)
            assert bb.y0 >= H * SAFE - 1, (visual, "text off the bottom", bb.y0)
            assert bb.y1 <= H * (1 - SAFE) + 1, (visual, "text off the top", bb.y1)
    finally:
        import matplotlib.pyplot as plt
        plt.close(fig)


@pytest.mark.parametrize("visual", sorted(BEATS))
def test_logo_corner_is_left_clear(visual):
    """The corner logo is drawn over the finished video, so nothing in the
    scene may sit under it."""
    fig = render(visual)
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
