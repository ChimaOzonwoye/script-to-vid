"""Hair, skin, shading, collars and the head to body ratio.

Everything here is a parameter that was added after the figures already
looked a certain way, so the first thing each test is really checking is
that asking for nothing still draws what it always drew.
"""

import numpy as np
import pytest
from PIL import Image

from app import characters as ch, engine, scenes
from app.themes import THEMES


def draw(tmp_path, name, **kw):
    fig = engine._fig(THEMES["cream"])
    ax = scenes._stage(fig)
    kw.setdefault("shirt", THEMES["cream"].a2)
    anchors = ch.draw_character(ax, 0, 2, s=2.6, **kw)
    p = tmp_path / f"{name}.png"
    fig.savefig(p, facecolor=THEMES["cream"].bg, dpi=100)
    import matplotlib.pyplot as plt
    plt.close(fig)
    return np.asarray(Image.open(p).convert("RGB")).astype(int), anchors


@pytest.mark.parametrize("head", ch.HEADS)
@pytest.mark.parametrize("body", ch.BODIES)
def test_asking_for_nothing_draws_what_it_always_drew(tmp_path, head, body):
    """Each new parameter defaults to the figure as it was, so a script
    written before any of this renders identically."""
    plain, _ = draw(tmp_path, "plain", head=head, body=body)
    explicit, _ = draw(tmp_path, "explicit", head=head, body=body,
                       hair="none", skin=ch.SKIN, head_ratio=1.0,
                       collar=False, shade=False)
    assert (plain == explicit).all()


DARK_SKIN = "#8a5a3b"      # so the whites of the eyes stand out from the face


def eye_whites(im):
    return ((im > 245).all(axis=2)).sum()


@pytest.mark.parametrize("hair", ch.HAIRS)
@pytest.mark.parametrize("head", ch.HEADS)
def test_hair_never_covers_the_eyes(tmp_path, hair, head):
    """A fringe over the brows is a haircut; a fringe over the eyes is a bug.
    It is a real risk here because the hairline is one measurement shared by
    three head shapes, and a pointed head carries its face lower.
    """
    bare, _ = draw(tmp_path, "bare", head=head, hair="none", skin=DARK_SKIN)
    with_hair, _ = draw(tmp_path, "hair", head=head, hair=hair, skin=DARK_SKIN)
    if hair == "none":
        assert (bare == with_hair).all()
        return
    assert np.abs(bare - with_hair).max() > 8, (hair, head, "no hair was drawn")
    before, after = eye_whites(bare), eye_whites(with_hair)
    assert before > 400, "the test cannot see the eyes"
    assert after > before * 0.98, (hair, head,
                                   f"hair covers the eyes ({after}/{before})")


def brow_band(anchors, head, s=2.6):
    """The rows the brows are drawn on, from the layout rather than by eye."""
    fdy = ch._HEAD_FACE[head][0]
    y = anchors["head"][1] + (fdy + 0.10 + 0.44) * s
    row = engine.H - int((y - scenes.Y_MIN) / scenes.STAGE_H * engine.H)
    half = int(0.16 * s / scenes.STAGE_H * engine.H)
    return row - half, row + half


@pytest.mark.parametrize("hair", ch.HAIRS)
@pytest.mark.parametrize("head", ch.HEADS)
def test_hair_leaves_the_brows_showing(tmp_path, hair, head):
    """The brows carry most of the expression: covered by a fringe, happy,
    worried and annoyed become the same face with a different mouth.

    Measured inside the brow band only. Across the whole figure the mouths
    alone would separate the expressions, and the test would pass on hair
    pulled right down over the eyebrows, which is how this was missed the
    first time: a fringe that low renders 0 differing pixels here and about
    1300 when the brows show.
    """
    faces, anchors = {}, None
    for expr in ("happy", "worried", "annoyed"):
        faces[expr], anchors = draw(tmp_path, expr, expr=expr, hair=hair,
                                    head=head, skin=DARK_SKIN)
    top, bottom = brow_band(anchors, head)
    for a, b in (("happy", "worried"), ("worried", "annoyed"),
                 ("happy", "annoyed")):
        d = np.abs(faces[a][top:bottom] - faces[b][top:bottom]).max(axis=2) > 8
        assert d.sum() > 400, (hair, head, a, b,
                               f"the brows are hidden ({d.sum()} pixels differ)")


def test_a_head_ratio_shrinks_the_head_and_leaves_the_body(tmp_path):
    small, a = draw(tmp_path, "small", head_ratio=0.7)
    big, b = draw(tmp_path, "big", head_ratio=1.0)
    assert a["head"][1] < b["head"][1], "a smaller head sits lower on the neck"
    assert a["hand_r"] == b["hand_r"], "the body moved with the head"
    assert ch.figure_height(2.6, "square", 0.7) < ch.figure_height(2.6, "square")


@pytest.mark.parametrize("head", ch.HEADS)
@pytest.mark.parametrize("ratio", [0.7, 0.86, 1.0, 1.2])
def test_figure_height_still_matches_what_is_drawn(tmp_path, head, ratio):
    _, a = draw(tmp_path, "r", head=head, head_ratio=ratio)
    assert abs(a["top"] - (2 + ch.figure_height(2.6, head, ratio))) < 1e-9
    assert abs(a["head"][1] - (2 + ch.head_centre_h(ratio) * 2.6)) < 1e-9


@pytest.mark.parametrize("ratio", [0.7, 0.86, 1.0, 1.2])
def test_scale_for_height_is_still_the_inverse(ratio):
    for head in ch.HEADS:
        s = ch.scale_for_height(9.0, head, ratio)
        assert abs(ch.figure_height(s, head, ratio) - 9.0) < 1e-9


def silhouette_rows(im):
    """The left and right edge of the figure on each row it occupies."""
    page = np.array([int(THEMES["cream"].bg[i:i + 2], 16) for i in (1, 3, 5)])
    mask = np.abs(im - page).max(axis=2) > 10
    out = {}
    for r in range(im.shape[0]):
        xs = np.where(mask[r])[0]
        if len(xs):
            out[r] = (xs.min(), xs.max())
    return out


def test_shade_stays_inside_the_outline(tmp_path):
    """The shaded side is a copy of the shape clipped to itself, so it can
    only ever repaint pixels the figure already covered. Drawn as a second
    shape laid on top, it would widen the silhouette wherever it stuck out.

    Compared as edges rather than as ink, because the shaded fill is darker
    than the lit one and any test that counts dark pixels would call that a
    difference.
    """
    flat, _ = draw(tmp_path, "flat", shade=False)
    lit, _ = draw(tmp_path, "lit", shade=True)
    assert silhouette_rows(flat) == silhouette_rows(lit), \
        "shading moved the edge of the figure"
    assert (flat != lit).any(), "shade=True changed nothing"


def test_skin_reaches_the_hands_as_well_as_the_head(tmp_path):
    pale, _ = draw(tmp_path, "pale", skin="#f3d3b3", pose="cheer")
    dark, _ = draw(tmp_path, "dark", skin="#5c3a24", pose="cheer")
    changed = np.abs(pale - dark).max(axis=2) > 8
    ys, _ = np.where(changed)
    # a cheering figure has its hands up beside its head and its head above
    # them, so a skin colour that only reached the head would change one band
    assert ys.max() - ys.min() > 60, "the hands did not follow the skin colour"


def test_a_collar_marks_the_shirt_without_touching_the_head(tmp_path):
    without, anchors = draw(tmp_path, "without", collar=False)
    with_, _ = draw(tmp_path, "with", collar=True)
    changed = np.abs(without - with_).max(axis=2) > 8
    assert changed.sum() > 40
    head_row = engine.H - int((anchors["head"][1] - scenes.Y_MIN)
                              / scenes.STAGE_H * engine.H)
    assert changed[:head_row].sum() == 0, "the collar reached the head"


def test_the_cast_is_a_set_of_distinct_people(tmp_path):
    seen = set()
    for c in scenes._CAST:
        seen.add((c["head"], c["body"], c["hair"], c["skin"]))
    assert len(seen) == len(scenes._CAST), "two cast members are identical"
    assert len({c["skin"] for c in scenes._CAST}) >= 4
    assert len({c["hair"] for c in scenes._CAST}) >= 4
    assert all(c["hair"] in ch.HAIRS for c in scenes._CAST)
    assert all(c["head"] in ch.HEADS and c["body"] in ch.BODIES
               for c in scenes._CAST)


def test_a_script_can_name_a_hair_style():
    from app.script_parser import parse
    b = parse("> character: happy, curls\n\nSome narration here.")["beats"][0]
    assert b["hair"] == "curls"


def test_the_cast_uses_the_new_look(tmp_path):
    """The parameters default to the old drawing, so the cast is what has to
    turn them on for videos made from now on."""
    beat = {"visual": "scene_character", "say": "x", "caption": "c",
            "cast_i": 0, "framing": "medium", "flip": False}
    p = tmp_path / "cast.png"
    engine.render_slide(beat, p, THEMES["cream"])
    im = np.asarray(Image.open(p).convert("RGB")).astype(int)
    hair = np.array([int(ch.HAIR[i:i + 2], 16) for i in (1, 3, 5)])
    assert (np.abs(im - hair).max(axis=2) < 12).sum() > 300, "the cast has no hair"
    assert ch.HEAD_RATIO < 1.0, "the cast still has the original head size"
