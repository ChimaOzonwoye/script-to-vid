"""Rooms to stand the characters in, one function per setting.

A background is line art on the page colour, like the figures, but at half
their outline weight and in colours blended most of the way back to the page.
It has to say where a character is standing without pulling the eye off the
character or the caption.

Two things keep it out of the way. Nothing is drawn above TOP, which leaves
the caption line and the corner the logo sits in alone. Anything on the wall
stays outside WALL_GAP of the centre, because a figure's head lands in the
middle of the frame at every framing, and a filled shape directly behind a
head is the one overlap that reads as a mistake rather than as depth.

Each function is given the stage axes, the theme, and the y the figure stands
on, so the room lands under the figure whatever the framing. In a close-up the
ground is far below the frame and everything but the wall is clipped away,
which is what a close-up should show.
"""

from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle

from .themes import mix

LW = 2.2            # under half the character outline, so the room sits back
TOP = 11.8          # the caption and the logo live above this
WALL_GAP = 8.4      # half the width kept clear of wall furniture


def _pens(T):
    """Line, floor, cool fill and warm fill, all blended back to the page."""
    return (mix(T.ink, T.bg, 0.62), mix(T.bg, T.ink, 0.05),
            mix(T.bg, T.a2, 0.16), mix(T.bg, T.a1, 0.18))


def _box(ax, T, x, y, w, h, face=None, round_to=0.0, lw=LW):
    line = _pens(T)[0]
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, facecolor=face or "none",
        boxstyle=f"round,pad=0,rounding_size={round_to or 0.001}",
        edgecolor=line, linewidth=lw, zorder=0))


def _line(ax, T, x0, y0, x1, y1, lw=LW):
    ax.plot([x0, x1], [y0, y1], color=_pens(T)[0], lw=lw, zorder=0,
            solid_capstyle="round")


def _floor(ax, T, ground):
    (x0, x1), (y0, _) = ax.get_xlim(), ax.get_ylim()
    if ground <= y0:
        return
    ax.add_patch(Rectangle((x0, y0), x1 - x0, ground - y0,
                           facecolor=_pens(T)[1], edgecolor="none", zorder=0))


def _table(ax, T, x, w, ground, h, face=None, panel=False):
    """A slab on two legs: desk, counter top, workbench. `panel` closes the
    front in, which is the difference between a desk and a bench."""
    _box(ax, T, x, ground + h, w, 0.5, face=face, round_to=0.10)
    for lx in (x + 0.6, x + w - 0.6):
        _line(ax, T, lx, ground + h, lx, ground)
    if panel:
        _box(ax, T, x + 0.6, ground + 0.5, w - 1.2, h - 0.5, round_to=0.08)


def _window(ax, T, x, y, w, h, skyline=False):
    """Four panes, or a view out over rooftops.

    The skyline is a run of touching blocks rather than separated ones, and
    it gets no horizontal glazing bar, because a bar across the middle of
    spaced blocks turns the whole thing into a bar chart.
    """
    tint = _pens(T)[2]
    _box(ax, T, x, y, w, h, face=tint)
    if skyline:
        far = mix(tint, T.ink, 0.14)
        run = ((0.00, 0.16, 0.34), (0.16, 0.13, 0.58), (0.29, 0.18, 0.40),
               (0.47, 0.11, 0.66), (0.58, 0.17, 0.30), (0.75, 0.14, 0.52),
               (0.89, 0.11, 0.36))
        for dx, dw, bh in run:
            ax.add_patch(Rectangle((x + dx * w, y), w * dw, h * bh,
                                   facecolor=far, edgecolor="none", zorder=0))
        _box(ax, T, x, y, w, h)
    else:
        _line(ax, T, x, y + h / 2, x + w, y + h / 2)
    _line(ax, T, x + w / 2, y, x + w / 2, y + h)


def plain(ax, T, ground):
    """The page on its own, which is what every scene looked like before."""


def classroom(ax, T, ground):
    _floor(ax, T, ground)
    tint = _pens(T)[2]
    _box(ax, T, -15.0, 6.8, 6.4, TOP - 6.8, face=tint, round_to=0.12)
    for i, w in enumerate((4.6, 3.2, 5.2)):
        _line(ax, T, -14.2, 10.4 - i * 1.05, -14.2 + w, 10.4 - i * 1.05, lw=1.6)
    _table(ax, T, 4.6, 8.4, ground, 2.0, panel=True)


def office(ax, T, ground):
    _floor(ax, T, ground)
    _window(ax, T, -15.0, 6.6, 6.6, TOP - 6.6, skyline=True)
    _table(ax, T, 4.4, 10.2, ground, 2.2)
    tint = _pens(T)[2]
    _box(ax, T, 8.2, ground + 2.7, 4.4, 2.7, face=tint, round_to=0.18)
    _line(ax, T, 10.4, ground + 2.7, 10.4, ground + 2.2)


def kitchen(ax, T, ground):
    _floor(ax, T, ground)
    warm = _pens(T)[3]
    _box(ax, T, 3.4, ground, 11.4, 2.6, face=warm, round_to=0.10)
    for x in (7.2, 11.0):
        _line(ax, T, x, ground, x, ground + 2.6)
    for x in (5.0, 8.8, 12.6):                       # handles
        _line(ax, T, x, ground + 2.0, x + 0.9, ground + 2.0, lw=1.6)
    for x, w in ((8.6, 2.9), (11.9, 2.9)):
        _box(ax, T, x, 8.4, w, TOP - 8.4, round_to=0.10)
        _line(ax, T, x + w / 2, 8.4, x + w / 2, TOP)
        for hx in (x + w / 2 - 0.5, x + w / 2 + 0.5):
            _line(ax, T, hx, 9.0, hx, 9.7, lw=1.6)
    _window(ax, T, -14.6, 6.9, 6.0, TOP - 6.9)


def living_room(ax, T, ground):
    _floor(ax, T, ground)
    tint, warm = _pens(T)[2], _pens(T)[3]
    _box(ax, T, 3.0, ground + 0.4, 10.8, 1.9, face=tint, round_to=0.40)
    _box(ax, T, 3.6, ground + 2.1, 9.6, 2.0, face=tint, round_to=0.40)
    for x in (3.0, 12.6):
        _box(ax, T, x, ground + 0.4, 1.2, 3.1, face=tint, round_to=0.40)
    for lx in (3.8, 13.0):
        _line(ax, T, lx, ground + 0.4, lx, ground)

    _line(ax, T, -14.2, ground, -14.2, ground + 4.6)
    ax.add_patch(Polygon([[-15.5, ground + 4.6], [-12.9, ground + 4.6],
                          [-13.5, ground + 6.0], [-14.9, ground + 6.0]],
                         closed=True, facecolor=warm,
                         edgecolor=_pens(T)[0], linewidth=LW, zorder=0))
    _box(ax, T, -12.6, 8.2, 3.8, TOP - 8.6, round_to=0.08)
    _box(ax, T, -12.1, 8.7, 2.8, TOP - 9.6, face=tint, round_to=0.06, lw=1.4)


def street(ax, T, ground):
    _floor(ax, T, ground)
    line, _, tint, warm = _pens(T)
    kerb = ground + 1.0
    # a street has no back wall, so unlike a room it has nothing left to show
    # once the pavement is below the frame: drawing it anyway leaves a sliver
    # of rooftop along the bottom edge of a close-up
    if kerb <= ax.get_ylim()[0]:
        return
    _line(ax, T, -16.0, kerb, 16.0, kerb)
    fronts = ((-15.4, 5.4, 7.6, tint), (-9.6, 4.6, 5.4, None),
              (-4.6, 5.8, 8.2, warm), (1.6, 4.8, 5.0, None),
              (6.8, 4.4, 7.0, tint), (11.6, 4.6, 5.8, None))
    for x, w, h, face in fronts:
        top = min(kerb + h, TOP)
        _box(ax, T, x, kerb, w, top - kerb, face=face)
        cols = max(int(w // 1.7), 1)
        for r in range(int((top - kerb - 1.4) // 1.7)):
            for c in range(cols):
                ax.add_patch(Rectangle(
                    (x + 0.5 + c * 1.7, top - 1.3 - r * 1.7), 0.8, 0.8,
                    facecolor=T.bg, edgecolor=line, linewidth=1.4, zorder=0))


BACKGROUNDS = {
    "plain": plain,
    "classroom": classroom,
    "office": office,
    "kitchen": kitchen,
    "living_room": living_room,
    "street": street,
}
DEFAULT_BACKGROUND = "plain"


def draw(ax, name, T, ground):
    BACKGROUNDS.get(name, plain)(ax, T, ground)
