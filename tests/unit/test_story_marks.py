"""The matched symbol is a guess, so it is never the subject of the frame.

symbols.match reads keywords. "future growth that money could have earned"
matches money, and a line about the money that was never spent then renders
as a banknote. That is fine as a mark the size of a stamp and wrong as the
picture the video is showing, and it came back as the picture three times, so
this measures the drawn pixels rather than reading the constants.
"""
import numpy as np
import pytest
from PIL import Image

from app import engine, scenes, symbols
from app.themes import THEMES

W, H = 1920, 1080
# the middle of the frame, where the eye goes. Nothing guessed may land here.
CX0, CX1, CY0, CY1 = 0.30, 0.70, 0.25, 0.72
STORY = [k for k, T in THEMES.items() if T.layout in ("story", "photo")]
BEAT = {"visual": "scene_story", "cast_i": 1,
        "say": "future growth that money could have earned",
        "caption": "future growth that money could have earned"}


def _pixels(tmp_path, T, beat, name):
    p = tmp_path / f"{name}.png"
    engine.render_slide(dict(beat), p, T)
    return np.asarray(Image.open(p).convert("RGB")).astype(int)


def _mark_mask(tmp_path, key):
    """The pixels the symbol alone is responsible for, and how hard it hit."""
    T = THEMES[key]
    with_it = _pixels(tmp_path, T, {**BEAT, "symbol": "money"}, f"{key}_y")
    without = _pixels(tmp_path, T, BEAT, f"{key}_n")
    delta = np.abs(with_it - without).max(axis=2)
    return delta


@pytest.mark.parametrize("key", STORY)
def test_a_guessed_symbol_is_never_the_middle_of_the_frame(tmp_path, key):
    delta = _mark_mask(tmp_path, key)
    ys, xs = np.nonzero(delta > 40)
    if len(xs) == 0:
        return
    x0, x1 = xs.min() / W, xs.max() / W
    y0, y1 = 1 - ys.max() / H, 1 - ys.min() / H
    assert (x1 - x0) * (y1 - y0) < 0.05, (
        f"{key}: the mark covers {(x1 - x0) * (y1 - y0):.0%} of the frame")
    overlaps = x0 < CX1 and x1 > CX0 and y0 < CY1 and y1 > CY0
    assert not overlaps, (
        f"{key}: the mark sits at x {x0:.2f}-{x1:.2f} y {y0:.2f}-{y1:.2f}, "
        "which is the middle of the frame")


def test_no_shipped_template_centres_a_match_by_default():
    """The composition that put the guess in the middle is gone. Keep it gone:
    every template's default has to be one the words carry."""
    assert "icon" not in scenes.COMPOSITIONS
    assert "watermark" not in scenes.COMPOSITIONS
    from app.themes import COMPOSITION_LABELS
    for key, T in THEMES.items():
        assert T.composition in scenes.COMPOSITIONS, \
            f"{key} asks for a composition that does not exist"
        # the Look step prints the shipped composition's label, so a theme
        # set to one the picker does not list raises on the project page
        assert T.composition in COMPOSITION_LABELS, \
            f"{key} ships a composition the picker cannot name"


def test_the_mark_only_follows_the_words_where_there_is_a_slot_for_it():
    """Every composition the caption overlay is allowed to draw a mark on has
    to be one whose slide leaves that corner empty."""
    for shape in scenes.MARKED:
        assert shape in scenes.COMPOSITIONS
    assert "band" not in scenes.MARKED
    assert "type" not in scenes.MARKED
    assert "split" not in scenes.MARKED


def test_the_line_that_started_this_still_matches_money():
    """Not a bug to fix. The sentence is about the growth that never happened,
    and the match reads the word and returns growth. It is right about the
    word and wrong about the sentence, every time, which is the whole reason
    the mark is the size it is."""
    assert symbols.match("future growth that money could have earned") == "growth"
