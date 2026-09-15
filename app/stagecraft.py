"""The ground a scene stands on and the light falling across it.

A template is more than a palette. Two videos in the same four colours read as
different films if one is a flat field and the other is a lit stage, so ground
and light are separate layers under every scene, and light is a choice of its
own rather than something baked into each palette.

Both are drawn below everything else, and neither may compete with the figure
or the words. That is the constraint the whole module is built around: a ground
is a flat pattern blended most of the way back to the page colour, and a light
is a wash of alpha rather than a shape with an edge. The one exception is the
floor of the "stage" ground, which is allowed to be solid because the figure
stands on it and nothing is ever written there.

Each function is handed the normalised x of whatever the scene has made its
subject, so the arch lands behind the figure and the spotlight falls on it
rather than on the caption beside it.
"""

import numpy as np
from matplotlib.patches import (Circle, Ellipse, FancyBboxPatch,
                                Polygon, Rectangle)

from .themes import mix

Z_GROUND, Z_LIGHT = -6.0, -4.0
FIELD = (90, 160)       # rows and columns of the lighting gradient


def _box(ax):
    (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
    return x0, y0, x1 - x0, y1 - y0


def _at(ax, focus):
    """Where the subject is, in axis units."""
    x0, _, w, _ = _box(ax)
    return x0 + focus * w


def _step(T, amount):
    """One step further from the ground colour, whichever way there is room.

    Mixing towards an accent to make a floor was the obvious thing and it is
    wrong: mustard mixed towards teal is olive. A ground and the shapes on it
    have to be the same colour at different depths, so this only ever moves
    towards black or white, and picks whichever the ground is further from.
    """
    from .themes import _luminance
    return mix(T.bg, "#000000" if _luminance(T.bg) > 0.28 else "#ffffff", amount)


# ----------------------------------------------------------------------
# GROUNDS


def plain(ax, T, focus, ground):
    """The page colour and nothing else, which is what shipped first."""


def stage(ax, T, focus, ground):
    """A solid floor to the horizon, the way a flat illustration sets a scene."""
    x0, y0, w, _ = _box(ax)
    if ground <= y0:
        return
    ax.add_patch(Rectangle((x0, y0), w, ground - y0, zorder=Z_GROUND,
                           facecolor=_step(T, 0.16), edgecolor="none"))


def arch(ax, T, focus, ground):
    """A tall rounded panel behind the subject, so the figure has a backdrop
    to stand against instead of floating on an empty field."""
    from .themes import _luminance
    x0, y0, w, h = _box(ax)
    aw, ah = w * 0.44, h * 0.78
    x = min(max(_at(ax, focus) - aw / 2, x0 + w * 0.02), x0 + w * 0.98 - aw)
    # A panel this size has to be almost nothing on a pale ground and a good
    # deal more on a dark one. Going the same distance both ways looks even in
    # the numbers and is not: a step towards black off a light page is a much
    # larger change to the eye than the same step towards white off a dark one.
    depth = 0.11 if _luminance(T.bg) > 0.28 else 0.22
    ax.add_patch(FancyBboxPatch(
        (x, y0 + h * 0.06), aw, ah, zorder=Z_GROUND,
        boxstyle=f"round,pad=0,rounding_size={aw / 2:.3f}",
        facecolor=_step(T, depth), edgecolor="none"))


def dots(ax, T, focus, ground):
    """A halftone field, the texture a printed explainer would have."""
    x0, y0, w, h = _box(ax)
    step = w / 34
    xs, ys = np.meshgrid(np.arange(x0, x0 + w, step),
                         np.arange(y0, y0 + h, step))
    # every other row offset by half a step, or the field reads as a grid
    xs[1::2] += step / 2
    ax.scatter(xs, ys, s=34, marker="o", zorder=Z_GROUND,
               color=mix(T.bg, T.a1, 0.22), edgecolors="none")


def rays(ax, T, focus, ground):
    """A sunburst from behind the subject. The wedges are drawn long enough to
    leave the frame from wherever the subject is standing, so the fan never
    ends in mid air."""
    x0, y0, w, h = _box(ax)
    cx, cy = _at(ax, focus), ground + h * 0.24
    reach = (w + h) * 1.2
    tone = _step(T, 0.09)
    for k in range(12):
        a = np.deg2rad(k * 30 + 8)
        b = np.deg2rad(k * 30 + 23)
        ax.add_patch(Polygon(
            [(cx, cy), (cx + reach * np.cos(a), cy + reach * np.sin(a)),
             (cx + reach * np.cos(b), cy + reach * np.sin(b))],
            closed=True, facecolor=tone, edgecolor="none", zorder=Z_GROUND))


def bars(ax, T, focus, ground):
    """Wide horizontal bands. Flat, graphic, and the one ground that reads at
    a glance in a thumbnail."""
    x0, y0, w, h = _box(ax)
    for k, t in enumerate((0.17, 0.11, 0.06)):
        y = y0 + h * (0.06 + k * 0.29)
        ax.add_patch(Rectangle((x0, y), w, h * 0.20, zorder=Z_GROUND,
                               facecolor=_step(T, t), edgecolor="none"))


GROUNDS = {"plain": plain, "stage": stage, "arch": arch,
           "dots": dots, "rays": rays, "bars": bars}


# ----------------------------------------------------------------------
# LIGHT


def _poles(T):
    """A brighter and a darker version of the ground for light to work with.

    Light in a flat illustration is warm, so the lift goes towards the
    template's warm accent rather than towards white, which reads as a grey
    filter dropped on top of the film. Shadow always goes towards black.
    _step is the wrong tool here: it moves away from the ground colour, which
    on a dark template means a shadow lighter than the thing it falls on.
    """
    return mix(T.a1, "#ffffff", 0.32), mix(T.bg, "#000000", 0.55)


def _wash(ax, colour, field):
    """Paint one colour over the stage with per-pixel alpha."""
    from matplotlib.colors import to_rgb
    x0, y0, w, h = _box(ax)
    img = np.zeros((*field.shape, 4))
    img[..., :3] = to_rgb(colour)
    img[..., 3] = np.clip(field, 0.0, 1.0)
    ax.imshow(img, extent=(x0, x0 + w, y0, y0 + h), origin="lower",
              interpolation="bilinear", zorder=Z_LIGHT, aspect="auto")


def _uv():
    rows, cols = FIELD
    return (np.linspace(0, 1, cols)[None, :],
            np.linspace(0, 1, rows)[:, None])


def _pool(focus, y=0.42, rx=0.42, ry=0.46):
    """An elliptical falloff centred on the subject, 1 at the middle."""
    u, v = _uv()
    d = np.sqrt(((u - focus) / rx) ** 2 + ((v - y) / ry) ** 2)
    return np.clip(1.0 - d, 0.0, 1.0) ** 1.5


def flat(ax, T, focus):
    """Even light, which is what every template shipped with."""


def glow(ax, T, focus):
    """A soft pool of warmth behind the subject."""
    _wash(ax, _poles(T)[0], _pool(focus, rx=0.60, ry=0.70) * 0.42)


def vignette(ax, T, focus):
    """Darker towards the corners, so the frame closes in on the middle."""
    u, v = _uv()
    d = np.sqrt((u - 0.5) ** 2 + ((v - 0.5) * 0.9) ** 2) / 0.72
    _wash(ax, _poles(T)[1], np.clip(d - 0.35, 0, 1) ** 1.6 * 0.55)


def warm(ax, T, focus):
    """Light from above, the way a room with one window looks."""
    _, v = _uv()
    up, down = _poles(T)
    _wash(ax, up, np.clip(v - 0.35, 0, 1) ** 1.3 * 0.55 + np.zeros(FIELD))
    _wash(ax, down, np.clip(0.42 - v, 0, 1) ** 1.4 * 0.45 + np.zeros(FIELD))


def spot(ax, T, focus):
    """A hard pool on the subject and shadow everywhere else. The strongest of
    the five, and the reason light is a separate choice: it turns the same
    palette into a stage rather than a page."""
    _wash(ax, _poles(T)[1], (1.0 - _pool(focus, y=0.40, rx=0.50, ry=0.62)) * 0.62)
    _wash(ax, _poles(T)[0], _pool(focus, y=0.46, rx=0.30, ry=0.36) * 0.38)


LIGHTS = {"flat": flat, "glow": glow, "vignette": vignette,
          "warm": warm, "spot": spot}


def backdrop(ax, T):
    """A full frame wash, for a shot with nothing standing in it.

    The grounds above are set: a floor, a panel, a sunburst, all of them
    drawn to sit behind a figure and a headline that cover most of them. With
    an empty frame in front they stop being background and become the
    subject, and every one of them puts a hard horizontal edge across the
    middle where the floor meets the wall. Nobody would choose that as a
    picture.

    This is what an empty frame gets instead: a gradient down the whole
    height and one soft bloom of the accent off centre. No edges, nothing
    that reads as an object, and it takes the light and the weather over the
    top the same way a ground does.
    """
    u, v = _uv()
    up, down = _poles(T)
    # deeper along the bottom and lifted along the top, which is how a lit
    # room falls whichever colour the room is
    _wash(ax, down, np.clip(0.55 - v, 0, 1) ** 1.25 * 0.42 + np.zeros(FIELD))
    _wash(ax, up, np.clip(v - 0.42, 0, 1) ** 1.35 * 0.20 + np.zeros(FIELD))
    # off centre, because a bloom in the middle of an empty frame is a
    # spotlight on nothing
    d = np.sqrt(((u - 0.36) / 0.52) ** 2 + ((v - 0.62) / 0.46) ** 2)
    _wash(ax, mix(T.a1, T.bg, 0.45), np.clip(1.0 - d, 0, 1) ** 1.8 * 0.30)


# ----------------------------------------------------------------------
# DRESSING
#
# One object standing beside the speaker. Rooms already exist in
# backgrounds.py, but a room is furniture across the whole frame and is
# chosen per beat; this is a single thing a template carries everywhere, and
# it has to live where neither the figure nor the headline is.
#
# The presenter stands on one side and the words sit on the other, and the
# side alternates at a chapter, so the object follows the figure to the outer
# edge of the frame. Everything is drawn a step off the ground colour rather
# than in the accents: it is scenery, and the moment it holds colour it starts
# competing with the person talking.


def _behind(ax, focus):
    """The outer edge on the speaker's side, for things that hang on a wall.

    A wall object is allowed to pass behind the figure, because it is on the
    wall and the figure is in the room: that overlap is the depth. It is the
    floor objects that have to stay clear of everything.
    """
    x0, _, w, _ = _box(ax)
    return (x0 + w * 0.04, 1.0) if focus < 0.5 else (x0 + w * 0.96, -1.0)


def _corner(ax, focus):
    """The floor in the corner on the speaker's side.

    Across the frame, past the words, was the first try and it reads better on
    paper than on screen: the headline runs most of the way to that edge, so
    anything tall enough to be worth drawing lands on top of the sentence. The
    corner behind the speaker is the only space in this layout that is
    genuinely empty, and a plant in the corner of a room is where a plant is.
    """
    x0, _, w, _ = _box(ax)
    return (x0 + w * 0.105, 1.0) if focus < 0.5 else (x0 + w * 0.895, -1.0)


def _pens(T):
    """Outline and fill for scenery.

    Backgrounds already answered this: a room draws in the ink's own hue
    pulled back towards the page, not in grey. _step goes to pure black, which
    is right for a ground and wrong here, because on a warm page it gives a
    dead neutral that reads as a placeholder rather than as distance.
    """
    return mix(T.ink, T.bg, 0.52), mix(T.bg, T.ink, 0.07)


def no_dressing(ax, T, focus, ground):
    """Nothing beside the speaker, which is what every template shipped with."""


def _frame(ax, T, focus, ground):
    """The panel a board and a chart are both drawn inside."""
    x, inward = _behind(ax, focus)
    w, h = 5.8, 4.4
    left = x if inward > 0 else x - w
    # high enough to be on the wall behind the shoulder rather than a slab
    # leaning against the speaker
    y = ground + 5.8
    ink, face = _pens(T)
    ax.add_patch(Rectangle((left, y), w, h, facecolor=face, edgecolor=ink,
                           linewidth=2.8, zorder=Z_GROUND + 0.5))
    return left, y, w, h, ink


def board(ax, T, focus, ground):
    """A board on the wall, with writing too small to read as words."""
    left, y, w, h, ink = _frame(ax, T, focus, ground)
    for i, run in enumerate((0.78, 0.48, 0.66, 0.36)):
        yy = y + h - 0.95 - i * 1.0
        ax.plot([left + 0.6, left + 0.6 + (w - 1.2) * run], [yy, yy],
                color=ink, lw=2.0, solid_capstyle="round",
                zorder=Z_GROUND + 0.6)


def growth(ax, T, focus, ground):
    """A framed chart with the line going up, for anything about money."""
    left, y, w, h, ink = _frame(ax, T, focus, ground)
    xs = [left + 0.8 + i * (w - 1.6) / 3 for i in range(4)]
    ys = [y + 0.9 + t * (h - 2.0) for t in (0.06, 0.38, 0.28, 1.0)]
    ax.plot(xs, ys, color=ink, lw=3.0, solid_capstyle="round",
            solid_joinstyle="round", zorder=Z_GROUND + 0.6)
    for xx in xs:
        ax.plot([xx, xx], [y + 0.5, y + 0.75], color=ink, lw=1.8,
                zorder=Z_GROUND + 0.6)


def plant(ax, T, focus, ground):
    """A plant in a pot, across the frame from the speaker."""
    x, inward = _corner(ax, focus)
    ink, face = _pens(T)
    pot_w, pot_h = 3.0, 2.6
    left = x - pot_w / 2 if inward > 0 else x - pot_w / 2
    cx = left + pot_w / 2
    ax.add_patch(Polygon([(left, ground), (left + pot_w, ground),
                          (left + pot_w - 0.46, ground + pot_h),
                          (left + 0.46, ground + pot_h)],
                         closed=True, facecolor=face, edgecolor=ink,
                         linewidth=3.0, zorder=Z_GROUND + 0.5))
    for lean, rise in ((-1.0, 4.6), (0.0, 6.4), (1.0, 5.1)):
        tip = (cx + lean * 1.20, ground + pot_h + rise)
        ax.plot([cx, tip[0]], [ground + pot_h, tip[1]], color=ink, lw=3.0,
                solid_capstyle="round", zorder=Z_GROUND + 0.55)
        ax.add_patch(Ellipse((tip[0] + lean * 0.35, tip[1] + 0.55), 2.4, 1.5,
                             angle=lean * 34, facecolor=face, edgecolor=ink,
                             linewidth=2.8, zorder=Z_GROUND + 0.6))


def flowers(ax, T, focus, ground):
    """A vase of flowers. The only dressing that keeps any colour, and only in
    the heads, which are small enough not to pull the eye off the speaker."""
    x, inward = _corner(ax, focus)
    ink, face = _pens(T)
    vase_w = 2.6
    left = x - vase_w / 2
    cx = left + vase_w / 2
    ax.add_patch(Polygon([(left + 0.3, ground), (left + vase_w - 0.3, ground),
                          (left + vase_w, ground + 3.0), (left, ground + 3.0)],
                         closed=True, facecolor=face, edgecolor=ink,
                         linewidth=3.0, zorder=Z_GROUND + 0.5))
    for lean, rise, tone in ((-1.0, 3.2, T.a1), (0.05, 4.6, T.a2),
                             (1.05, 3.6, T.a1)):
        tip = (cx + lean * 1.25, ground + 3.0 + rise)
        ax.plot([cx, tip[0]], [ground + 3.0, tip[1]], color=ink, lw=2.8,
                solid_capstyle="round", zorder=Z_GROUND + 0.55)
        ax.add_patch(Circle(tip, 1.1, facecolor=mix(T.bg, tone, 0.52),
                            edgecolor=ink, linewidth=2.7,
                            zorder=Z_GROUND + 0.6))


def cat(ax, T, focus, ground):
    """An animal sitting across the frame, facing the speaker."""
    x, inward = _corner(ax, focus)
    ink, face = _pens(T)
    cx = x
    ax.add_patch(Polygon([(cx - inward * 2.3, ground),
                          (cx + inward * 2.0, ground),
                          (cx + inward * 1.1, ground + 4.4),
                          (cx - inward * 1.1, ground + 4.4)],
                         closed=True, facecolor=face, edgecolor=ink,
                         linewidth=3.0, zorder=Z_GROUND + 0.5))
    hx, hy = cx, ground + 5.5
    ax.add_patch(Circle((hx, hy), 1.6, facecolor=face, edgecolor=ink,
                        linewidth=3.0, zorder=Z_GROUND + 0.6))
    for ear in (-0.86, 0.86):
        ax.add_patch(Polygon([(hx + ear - 0.48, hy + 1.2),
                              (hx + ear + 0.48, hy + 1.2),
                              (hx + ear, hy + 2.45)],
                             closed=True, facecolor=face, edgecolor=ink,
                             linewidth=2.8, zorder=Z_GROUND + 0.6))
    # the tail curls away from the speaker, so the shape reads at a glance
    tail = [(cx - inward * 2.1, ground + 0.25),
            (cx - inward * 3.1, ground + 0.2),
            (cx - inward * 3.4, ground + 2.2)]
    ax.plot([p[0] for p in tail], [p[1] for p in tail], color=ink, lw=3.2,
            solid_capstyle="round", zorder=Z_GROUND + 0.45)


DRESSING = {"none": no_dressing, "board": board, "growth": growth,
            "plant": plant, "flowers": flowers, "cat": cat}


def draw(ax, T, focus, ground, empty=False):
    """Lay the template's ground, dressing and light under a scene.

    Dressing goes on before the light, so the object standing beside the
    speaker is lit by the same pool or vignette as everything else rather
    than sitting on top of it looking cut out.

    `empty` is a frame with nothing standing in it. The ground and the
    dressing are both set built to sit behind a figure, so they are swapped
    for the full frame backdrop; the light is the one part that works either
    way and is kept, because it is most of what separates one template from
    another.
    """
    if empty:
        backdrop(ax, T)
    else:
        GROUNDS.get(getattr(T, "ground", "plain"), plain)(ax, T, focus, ground)
        DRESSING.get(getattr(T, "dressing", "none"), no_dressing)(
            ax, T, focus, ground)
    LIGHTS.get(getattr(T, "light", "flat"), flat)(ax, T, focus)


# ----------------------------------------------------------------------
# LETTERING


def _slab_ink(T):
    """Text that can be read on a slab of the warm accent."""
    from .themes import _luminance
    return "#14120d" if _luminance(T.a1) > 0.35 else "#ffffff"


def plain_type(t, T):
    """Bold caps and nothing else, which is what shipped first."""


def halo(t, T):
    """A thick ring of the ground colour around the letters. Not decoration:
    a sunburst or a halftone field runs behind the words, and without this the
    pattern reads through the counters of the type."""
    import matplotlib.patheffects as pe
    t.set_path_effects([pe.withStroke(linewidth=10, foreground=T.bg)])


def drop(t, T):
    """A hard offset shadow, no blur, the way flat illustration does depth."""
    import matplotlib.patheffects as pe
    t.set_path_effects([pe.withSimplePatchShadow(
        offset=(5, -5), shadow_rgbFace=_step(T, 0.40), alpha=1.0, rho=1.0)])


def slab(t, T):
    """The words sitting in a block of the warm accent."""
    t.set_color(_slab_ink(T))
    t.set_bbox(dict(boxstyle="square,pad=0.34", facecolor=T.a1,
                    edgecolor=T.ink, linewidth=3.0))


LETTERING = {"plain": plain_type, "halo": halo, "drop": drop, "slab": slab}


def letter(t, T):
    """Give a placed text the template's type treatment.

    Called after the text has been fitted, because a slab changes the measured
    width and fitting against that would shrink the type to fit its own box.
    """
    LETTERING.get(getattr(T, "lettering", "plain"), plain_type)(t, T)
