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
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle

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
    x0, y0, w, h = _box(ax)
    aw, ah = w * 0.44, h * 0.78
    x = min(max(_at(ax, focus) - aw / 2, x0 + w * 0.02), x0 + w * 0.98 - aw)
    ax.add_patch(FancyBboxPatch(
        (x, y0 + h * 0.06), aw, ah, zorder=Z_GROUND,
        boxstyle=f"round,pad=0,rounding_size={aw / 2:.3f}",
        facecolor=_step(T, 0.20), edgecolor="none"))


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


def draw(ax, T, focus, ground):
    """Lay the template's ground and light under a scene."""
    GROUNDS.get(getattr(T, "ground", "plain"), plain)(ax, T, focus, ground)
    LIGHTS.get(getattr(T, "light", "flat"), flat)(ax, T, focus)
