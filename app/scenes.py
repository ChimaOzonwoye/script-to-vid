"""Composed character scenes, one function per layout.

The stage is 32x18 units on a 1920x1080 figure, so one unit is 60 px.
Everything stays inside a safe area 5% in from each edge, and nothing is
drawn in the top-right logo zone (x > 12, y > 13).

The cast is fixed: the same index always gives the same head, body and
shirt, so a recurring character looks identical in every scene. Shirts
come from the theme; outlines and skin stay the character palette so the
figures themselves never drift.
"""

import numpy as np

from . import characters as ch
from .themes import mix

GROUND_Y = 3.0

_CAST = [("square", "box"), ("round", "tall"), ("triangle", "round")]


def cast_member(i, T):
    head, body = _CAST[i % len(_CAST)]
    shirt = [T.a2, T.a1, ch.PINK][i % 3]
    return head, body, shirt


def _stage(fig):
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.set_xlim(-16, 16)
    ax.set_ylim(-1, 17)
    return ax


def _fit(fig, t, max_px):
    fig.canvas.draw()
    w = t.get_window_extent(fig.canvas.get_renderer()).width
    if w > max_px:
        t.set_fontsize(max(24, t.get_fontsize() * max_px / w))


def _caption(fig, T, text, y=0.105, size=42):
    if not text:
        return
    t = fig.text(0.5, y, text.upper(), ha="center", va="center", fontsize=size,
                 color=T.ink, fontweight="bold")
    _fit(fig, t, 1728)  # the 5% safe area at this width


def _character(ax, b, T, x=0.0, s=1.6, pose=None, expr=None):
    head, body, shirt = cast_member(b.get("cast_i", 0), T)
    return ch.draw_character(
        ax, x, GROUND_Y, s=s,
        pose=pose or b.get("pose", "stand"),
        expr=expr or b.get("expr", "neutral"),
        head=b.get("head", head), body=b.get("body", body), shirt=shirt)


def _prop(ax, name, x, y, hand=None):
    if name == "piggy":
        ch.prop_piggy(ax, x, y, s=1.5, label="CAN'T\nTOUCH")
    elif name == "coin":
        if hand:
            ch.prop_coin(ax, hand[0] + 0.35, hand[1] + 0.15, r=0.55)
        else:
            ch.prop_coin(ax, x, y + 0.6, r=0.6)
    elif name == "coins":
        ch.prop_coin_stack(ax, x, y + 0.55, n=5, r=0.55)
    elif name == "jar":
        ch.prop_jar(ax, x, y, s=1.6, fill=0.65)


def scene_character(fig, b, T):
    """One character, an optional prop beside them, caption below."""
    ax = _stage(fig)
    ch.ground(ax, GROUND_Y)
    prop = b.get("prop")
    cx = -3.5 if prop else 0.0
    anchors = _character(ax, b, T, x=cx)
    if prop:
        _prop(ax, prop, 4.0, GROUND_Y, hand=anchors["hand_r"])
    _caption(fig, T, b.get("caption"))


def scene_caption(fig, b, T):
    """One character alone with a large caption."""
    ax = _stage(fig)
    ch.ground(ax, GROUND_Y + 0.8)
    _character(ax, {**b, "cast_i": b.get("cast_i", 0)}, T, x=0.0, s=1.5)
    text = b.get("caption") or b.get("headline") or ""
    _caption(fig, T, text, y=0.115, size=52)


def scene_duo(fig, b, T):
    """Two characters facing each other, the left one speaking."""
    ax = _stage(fig)
    ch.ground(ax, GROUND_Y)
    left = _character(ax, b, T, x=-6.5, s=1.5, pose=b.get("pose", "offer"))
    other = {"cast_i": b.get("cast_i", 0) + 1}
    _character(ax, other, T, x=6.5, s=1.5, pose="stand",
               expr=b.get("expr2", "happy"))
    text = b.get("bubble") or ""
    if text:
        s = min(1.3, 34 / max(len(text), 12))
        ch.prop_bubble(ax, -3.5, left["top"] + 2.2, text, s=s,
                       tail_to=(left["head"][0] + 0.8, left["top"] + 0.3))
    _caption(fig, T, b.get("caption"))


def scene_bubbles(fig, b, T):
    """One character puzzling at floating term bubbles."""
    ax = _stage(fig)
    ch.ground(ax, GROUND_Y)
    _character(ax, b, T, x=-7.0, s=1.5, pose=b.get("pose", "think"),
               expr=b.get("expr", "worried"))
    words = b.get("words") or []
    spots = [(3.0, 11.5), (9.0, 9.2), (2.5, 7.0), (8.5, 5.2), (5.0, 3.9)]
    for i, ((x, y), word) in enumerate(zip(spots, words)):
        t = ax.text(x, y, word.upper(), ha="center", va="center", fontsize=26,
                    color=T.a2_hi if i % 2 else T.a1_hi, fontweight="bold",
                    zorder=8)
        t.set_bbox(dict(boxstyle="round,pad=0.55",
                        facecolor=T.a2_pale if i % 2 else ch.PAPER,
                        edgecolor=ch.INK, linewidth=3))
    _caption(fig, T, b.get("caption"))


def scene_split(fig, b, T):
    """Before on the left, after on the right."""
    ax = _stage(fig)
    ch.ground(ax, GROUND_Y)
    ax.plot([0, 0], [GROUND_Y, 14.5], color=T.grid, lw=3, zorder=1)

    _character(ax, {"cast_i": b.get("cast_i", 0)}, T, x=-11.5, s=1.35,
               pose="shrug", expr="worried")
    rng = np.random.default_rng(11)
    for x, y in zip(rng.uniform(-7.5, -2.0, 6), rng.uniform(0.6, 2.2, 6)):
        ch.prop_coin(ax, x, GROUND_Y + y, r=0.5)

    _character(ax, {"cast_i": b.get("cast_i", 0)}, T, x=11.5, s=1.35,
               pose="cheer", expr="happy")
    ch.prop_jar(ax, 4.5, GROUND_Y, s=1.6, fill=0.8)
    ch.prop_coin_stack(ax, 7.5, GROUND_Y + 0.55, n=4, r=0.5)

    for x, text, col in ((-8.0, b.get("left", "Before"), T.dim),
                         (8.0, b.get("right", "After"), T.a2)):
        ax.text(x, 15.6, text.upper(), ha="center", va="center",
                fontsize=30, color=col, fontweight="bold")
    _caption(fig, T, b.get("caption"))


def scene_chart(fig, b, T):
    """A character presenting a chart drawn by the engine."""
    ax = _stage(fig)
    ch.ground(ax, GROUND_Y)
    _character(ax, b, T, x=-11.0, s=1.5, pose=b.get("pose", "point"),
               expr=b.get("expr", "happy"))

    cax = fig.add_axes([0.42, 0.30, 0.46, 0.46])
    cax.set_facecolor(T.bg)
    for s in cax.spines.values():
        s.set_color(T.grid)
    cax.tick_params(colors=T.dim, labelsize=16)
    cax.grid(True, color=T.grid, linewidth=1)
    cax.set_axisbelow(True)
    if b.get("chart") == "timeline":
        x = np.arange(0, 25)
        cax.plot(x, 1 - np.exp(-x / 8), color=T.a2, lw=6)
        cax.fill_between(x, 0, 1 - np.exp(-x / 8), color=T.a2, alpha=0.13)
        cax.set_yticks([])
    else:
        yrs = np.arange(1, 11)
        vals = yrs ** 1.6
        cols = [mix(T.a2, T.a1, i / 9) for i in range(10)]
        cax.bar(yrs, vals, color=cols, width=0.68, edgecolor="none")
        cax.set_yticks([])
    _caption(fig, T, b.get("caption"))


VISUALS = {
    "scene_character": scene_character,
    "scene_caption": scene_caption,
    "scene_duo": scene_duo,
    "scene_bubbles": scene_bubbles,
    "scene_split": scene_split,
    "scene_chart": scene_chart,
}
