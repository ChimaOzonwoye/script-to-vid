"""Composed character scenes, one function per layout.

The stage is 32x18 units on a 1920x1080 figure, so one unit is 60 px.
Everything stays inside a safe area 5% in from each edge, and nothing is
drawn in the top-right logo zone.

Two things keep a run of beats from looking like one shot repeated. The
cast is fixed, so the same index always gives the same head, body and
shirt and a recurring character stays recognisable. The framing is not:
each beat is drawn wide, medium or close, and off centre, so consecutive
beats cut rather than sit still.

Figures are never placed by hand. A framing says what share of the frame
height the figure should fill, and the scale comes from
characters.scale_for_height, so a triangle head or a tall body lands
correctly without per-scene tweaking.
"""

import textwrap

import numpy as np

from . import backgrounds as bg
from . import characters as ch
from .themes import mix

STAGE_W, STAGE_H = 32.0, 18.0
X_MIN, Y_MIN = -16.0, -1.0
GROUND_Y = 3.0
PX_PER_UNIT = 60

# Each framing is the share of frame height the figure fills, how far off
# centre it stands as a share of the half width, and where its caption goes.
# Dead centre with a caption underneath reads as a template, so every framing
# is off centre. "close" places the figure by its head instead of its feet,
# and the legs run off the bottom of the frame.
FRAMINGS = {
    "wide":   {"height": 0.40, "x": 0.38, "caption": "above"},
    "medium": {"height": 0.68, "x": 0.30, "caption": "below"},
    "close":  {"height": 1.35, "x": 0.42, "caption": "beside", "head_y": 0.58},
}
DEFAULT_FRAMING = "medium"

# two figures need more room each, so they sit between wide and medium
TWO_SHOT_HEIGHT = 0.56

_CAST = [("square", "box"), ("round", "tall"), ("triangle", "round")]


def cast_member(i, T):
    head, body = _CAST[i % len(_CAST)]
    shirt = [T.a2, T.a1, ch.PINK][i % 3]
    return head, body, shirt


def _shape(b):
    """The head and body this beat will actually be drawn with."""
    head, body = _CAST[b.get("cast_i", 0) % len(_CAST)]
    return b.get("head", head), b.get("body", body)


def _framing(b):
    return FRAMINGS.get(b.get("framing"), FRAMINGS[DEFAULT_FRAMING])


def _side(b):
    """Which side of the frame the figure stands on."""
    return 1 if b.get("flip") else -1


def _place(b, height=None, side=None):
    """Where a figure goes and how big, computed from its framing."""
    f = _framing(b)
    head, _ = _shape(b)
    s = ch.scale_for_height((height or f["height"]) * STAGE_H, head)
    if "head_y" in f and height is None:
        ground = Y_MIN + f["head_y"] * STAGE_H - ch.HEAD_CENTRE_H * s
    else:
        ground = GROUND_Y
    if side is None:
        side = _side(b)
    return side * f["x"] * (STAGE_W / 2), ground, s


def _stage(fig, b=None, T=None, ground=GROUND_Y):
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.set_xlim(X_MIN, X_MIN + STAGE_W)
    ax.set_ylim(Y_MIN, Y_MIN + STAGE_H)
    if b is not None:
        bg.draw(ax, b.get("background"), T, ground)
    return ax


def _fit(fig, t, max_px):
    fig.canvas.draw()
    w = t.get_window_extent(fig.canvas.get_renderer()).width
    if w > max_px:
        t.set_fontsize(max(22, t.get_fontsize() * max_px / w))


def _caption(fig, T, b, text, side=None):
    """Put the caption where this beat's framing wants it."""
    if not text:
        return
    where = _framing(b)["caption"]
    if where == "beside":
        # the empty half, opposite the figure
        side = _side(b) if side is None else side
        t = fig.text(0.5 - side * 0.26, 0.5,
                     "\n".join(textwrap.wrap(text.upper(), 13)),
                     ha="center", va="center", fontsize=44, color=T.ink,
                     fontweight="bold", linespacing=1.2)
        _fit(fig, t, 620)
    elif where == "above":
        # clear of the logo, which starts higher up the right hand side
        t = fig.text(0.5, 0.76, text.upper(), ha="center", va="center",
                     fontsize=46, color=T.ink, fontweight="bold")
        _fit(fig, t, 1728)
    else:
        t = fig.text(0.5, 0.105, text.upper(), ha="center", va="center",
                     fontsize=42, color=T.ink, fontweight="bold")
        _fit(fig, t, 1728)


def _draw(ax, b, T, x, ground, s, pose=None, expr=None, cast_i=None,
          speaks=True):
    """`speaks` is off for a figure that is not the one delivering the line,
    so a two-shot does not have both mouths moving to the same words."""
    i = b.get("cast_i", 0) if cast_i is None else cast_i
    head, body = _CAST[i % len(_CAST)]
    shirt = [T.a2, T.a1, ch.PINK][i % 3]
    return ch.draw_character(
        ax, x, ground, s=s,
        pose=pose or b.get("pose", "stand"),
        expr=expr or b.get("expr", "neutral"),
        head=b.get("head", head), body=b.get("body", body), shirt=shirt,
        eyes=b.get("eyes", "open") if speaks else "open",
        mouth=b.get("mouth", "closed") if speaks else "closed")


def _prop(ax, name, x, ground, s, hand=None):
    """Props scale with the figure so they never look pasted on."""
    ps = 0.65 * s
    if name == "piggy":
        ch.prop_piggy(ax, x, ground, s=ps, label="SAVE")
    elif name == "coin":
        if hand:
            ch.prop_coin(ax, hand[0] + 0.25 * s, hand[1] + 0.1 * s, r=0.24 * s)
        else:
            ch.prop_coin(ax, x, ground + 0.4 * s, r=0.26 * s)
    elif name == "coins":
        ch.prop_coin_stack(ax, x, ground + 0.24 * s, n=5, r=0.24 * s)
    elif name == "jar":
        ch.prop_jar(ax, x, ground, s=0.7 * s, fill=0.65)


def scene_character(fig, b, T):
    """One figure, an optional prop, framed wide, medium or close."""
    x, ground, s = _place(b)
    ax = _stage(fig, b, T, ground)
    if ground >= Y_MIN:
        ch.ground(ax, ground)
    anchors = _draw(ax, b, T, x, ground, s)
    prop = b.get("prop")
    if prop and _framing(b)["caption"] != "beside":
        _prop(ax, prop, -_side(b) * 5.0, ground, s, hand=anchors["hand_r"])
    _caption(fig, T, b, b.get("caption"))


def scene_caption(fig, b, T):
    """One figure and a large caption, the caption carrying the beat."""
    x, ground, s = _place(b)
    ax = _stage(fig, b, T, ground)
    if ground >= Y_MIN:
        ch.ground(ax, ground)
    _draw(ax, b, T, x, ground, s)
    _caption(fig, T, b, b.get("caption") or b.get("headline"))


def scene_duo(fig, b, T):
    """Two figures facing each other, the left one speaking."""
    ax = _stage(fig, b, T)
    ch.ground(ax, GROUND_Y)
    lx, ground, s = _place(b, height=TWO_SHOT_HEIGHT, side=-1)
    rx, _, rs = _place({**b, "cast_i": b.get("cast_i", 0) + 1},
                       height=TWO_SHOT_HEIGHT, side=1)
    left = _draw(ax, b, T, lx, ground, s, pose=b.get("pose", "offer"))
    _draw(ax, b, T, rx, ground, rs, pose="stand",
          expr=b.get("expr2", "happy"), cast_i=b.get("cast_i", 0) + 1,
          speaks=False)
    text = b.get("bubble") or ""
    if text:
        bs = min(1.4, 36 / max(len(text), 12))
        ch.prop_bubble(ax, lx + 3.0, left["top"] + 1.8, text, s=bs,
                       tail_to=(left["head"][0] + 0.8 * s, left["top"] + 0.2))
    _caption(fig, T, {**b, "framing": "medium"}, b.get("caption"))


def scene_bubbles(fig, b, T):
    """One figure puzzling at floating words."""
    ax = _stage(fig, b, T)
    ch.ground(ax, GROUND_Y)
    x, ground, s = _place(b, height=0.58, side=-1)
    _draw(ax, b, T, x, ground, s, pose=b.get("pose", "think"),
          expr=b.get("expr", "worried"))
    words = b.get("words") or []
    spots = [(3.0, 12.0), (9.5, 9.6), (2.6, 7.2), (9.0, 5.4), (5.4, 3.9)]
    for i, ((wx, wy), word) in enumerate(zip(spots, words)):
        t = ax.text(wx, wy, word.upper(), ha="center", va="center", fontsize=26,
                    color=T.a2_hi if i % 2 else T.a1_hi, fontweight="bold",
                    zorder=8)
        t.set_bbox(dict(boxstyle="round,pad=0.55",
                        facecolor=T.a2_pale if i % 2 else ch.PAPER,
                        edgecolor=ch.INK, linewidth=3))
    _caption(fig, T, {**b, "framing": "medium"}, b.get("caption"))


def scene_split(fig, b, T):
    """Before on the left, after on the right.

    The two figures carry the contrast on their own, so a split works for any
    subject. Props are drawn only when the script asks for one, scattered on
    the left and gathered on the right.
    """
    ax = _stage(fig, b, T)
    ch.ground(ax, GROUND_Y)
    ax.plot([0, 0], [GROUND_Y, 14.5], color=T.grid, lw=3, zorder=1)

    # each figure stands in the middle of its own half, or further out when
    # props need the space between them
    _, ground, s = _place(b, height=TWO_SHOT_HEIGHT, side=-1)
    lx = -11.5 if b.get("prop") else -8.0
    rx = -lx
    _draw(ax, b, T, lx, ground, s, pose="shrug", expr="worried")
    _draw(ax, b, T, rx, ground, s, pose="cheer", expr="happy")

    prop = b.get("prop")
    if prop in ("coin", "coins"):
        rng = np.random.default_rng(11)
        for x, y in zip(rng.uniform(-7.5, -2.0, 6), rng.uniform(0.6, 2.2, 6)):
            ch.prop_coin(ax, x, GROUND_Y + y, r=0.5)
        ch.prop_coin_stack(ax, 6.0, GROUND_Y + 0.55, n=4, r=0.5)
    elif prop == "jar":
        ch.prop_jar(ax, -5.0, GROUND_Y, s=1.6, fill=0.1)
        ch.prop_jar(ax, 5.0, GROUND_Y, s=1.6, fill=0.85)
    elif prop == "piggy":
        ch.prop_piggy(ax, -5.0, GROUND_Y, s=1.3)
        ch.prop_piggy(ax, 5.0, GROUND_Y, s=1.3, label="FULL")

    # each label is centred over its own half and shrunk to stay inside it,
    # so two long labels cannot meet in the middle
    for x, text, col in ((-8.0, b.get("left", "Before"), T.dim),
                         (8.0, b.get("right", "After"), T.a2)):
        t = ax.text(x, 15.6, text.upper(), ha="center", va="center",
                    fontsize=30, color=col, fontweight="bold")
        _fit(fig, t, 860)   # a half is 960 px wide at this stage scale
    _caption(fig, T, {**b, "framing": "medium"}, b.get("caption"))


def scene_chart(fig, b, T):
    """A figure presenting a chart drawn by the engine."""
    ax = _stage(fig, b, T)
    ch.ground(ax, GROUND_Y)
    x, ground, s = _place(b, height=0.58, side=-1)
    _draw(ax, b, T, x, ground, s, pose=b.get("pose", "point"),
          expr=b.get("expr", "happy"))

    cax = fig.add_axes([0.44, 0.30, 0.44, 0.44])
    cax.set_facecolor(T.bg)
    for sp in cax.spines.values():
        sp.set_color(T.grid)
    cax.tick_params(colors=T.dim, labelsize=16)
    cax.grid(True, color=T.grid, linewidth=1)
    cax.set_axisbelow(True)
    if b.get("chart") == "timeline":
        xs = np.arange(0, 25)
        cax.plot(xs, 1 - np.exp(-xs / 8), color=T.a2, lw=6)
        cax.fill_between(xs, 0, 1 - np.exp(-xs / 8), color=T.a2, alpha=0.13)
    else:
        yrs = np.arange(1, 11)
        cols = [mix(T.a2, T.a1, i / 9) for i in range(10)]
        cax.bar(yrs, yrs ** 1.6, color=cols, width=0.68, edgecolor="none")
    cax.set_yticks([])
    _caption(fig, T, {**b, "framing": "medium"}, b.get("caption"))


VISUALS = {
    "scene_character": scene_character,
    "scene_caption": scene_caption,
    "scene_duo": scene_duo,
    "scene_bubbles": scene_bubbles,
    "scene_split": scene_split,
    "scene_chart": scene_chart,
}
