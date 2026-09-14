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
from matplotlib.patches import FancyBboxPatch, Rectangle

from . import backgrounds as bg
from . import characters as ch
from . import stagecraft
from . import captions
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

# The cast is fixed so a recurring character stays recognisable: the same
# index always gives the same silhouette, hair, skin and shirt. Skin tones
# vary because a cast that is all one tone is a choice too, and it is not one
# worth shipping as the default.
_CAST = [
    {"head": "square", "body": "box", "hair": "short", "skin": "#f3d3b3"},
    {"head": "round", "body": "tall", "hair": "bun", "skin": "#8a5a3b"},
    {"head": "triangle", "body": "round", "hair": "crop", "skin": "#d8a875"},
    {"head": "square", "body": "tall", "hair": "curls", "skin": "#5c3a24"},
    {"head": "round", "body": "box", "hair": "cap", "skin": "#f0c9a0"},
    {"head": "triangle", "body": "tall", "hair": "long", "skin": "#a8714a"},
]


def cast_member(i, T):
    c = _CAST[i % len(_CAST)]
    return c["head"], c["body"], [T.a2, T.a1, ch.PINK][i % 3]


def _cast(b, i=None):
    """This beat's character, with anything the script named winning."""
    i = b.get("cast_i", 0) if i is None else i
    c = dict(_CAST[i % len(_CAST)])
    for field in ("head", "body", "hair", "skin"):
        if b.get(field):
            c[field] = b[field]
    return c


def _shape(b):
    """The head and body this beat will actually be drawn with."""
    c = _cast(b)
    return c["head"], c["body"]


def _framing(b):
    return FRAMINGS.get(b.get("framing"), FRAMINGS[DEFAULT_FRAMING])


def _side(b):
    """Which side of the frame the figure stands on."""
    return 1 if b.get("flip") else -1


def _place(b, height=None, side=None):
    """Where a figure goes and how big, computed from its framing."""
    f = _framing(b)
    head, _ = _shape(b)
    s = ch.scale_for_height((height or f["height"]) * STAGE_H, head, ch.HEAD_RATIO)
    if "head_y" in f and height is None:
        ground = Y_MIN + f["head_y"] * STAGE_H - ch.head_centre_h(ch.HEAD_RATIO) * s
    else:
        ground = GROUND_Y
    if side is None:
        side = _side(b)
    return side * f["x"] * (STAGE_W / 2), ground, s


def focus_of(x):
    """A stage x as a share of the frame width, for whatever is lighting it."""
    return (x - X_MIN) / STAGE_W


def _stage(fig, b=None, T=None, ground=GROUND_Y, focus=0.5, empty=False):
    """The axes every scene draws into, with the template already laid down.

    The template's ground and light go on first and the room on top of them,
    so a scene that names a background gets that room lit by the template
    rather than a room drawn over a treatment it knows nothing about.
    """
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.set_xlim(X_MIN, X_MIN + STAGE_W)
    ax.set_ylim(Y_MIN, Y_MIN + STAGE_H)
    if T is not None:
        stagecraft.draw(ax, T, focus, ground, empty)
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
        stagecraft.letter(t, T)
    elif where == "above":
        # clear of the logo, which starts higher up the right hand side
        t = fig.text(0.5, 0.76, text.upper(), ha="center", va="center",
                     fontsize=46, color=T.ink, fontweight="bold")
        _fit(fig, t, 1728)
        stagecraft.letter(t, T)
    else:
        t = fig.text(0.5, 0.105, text.upper(), ha="center", va="center",
                     fontsize=42, color=T.ink, fontweight="bold")
        _fit(fig, t, 1728)
        stagecraft.letter(t, T)


def _draw(ax, b, T, x, ground, s, pose=None, expr=None, cast_i=None,
          speaks=True):
    """`speaks` is off for a figure that is not the one delivering the line,
    so a two-shot does not have both mouths moving to the same words."""
    i = b.get("cast_i", 0) if cast_i is None else cast_i
    c = _cast(b, i)
    return ch.draw_character(
        ax, x, ground, s=s,
        pose=pose or b.get("pose", "stand"),
        expr=expr or b.get("expr", "neutral"),
        head=c["head"], body=c["body"], shirt=[T.a2, T.a1, ch.PINK][i % 3],
        hair=c["hair"], skin=c["skin"], head_ratio=ch.HEAD_RATIO,
        collar=True, shade=True,
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


# The presenter stands in one third of the frame and stays there. Content
# fills the rest and is the only thing that changes between beats, which is
# what makes a run of them feel like a host talking rather than a slideshow.
# The side alternates at chapters, not per beat, so it reads as a cut to the
# other camera rather than the figure hopping about.
PRESENTER = {"height": 0.66, "x": 0.54}


def presenter_x(side):
    return side * PRESENTER["x"] * (STAGE_W / 2)


# Where the words are put when the template does not want them across the
# middle of the frame. A caption bar sits below the action, which is where a
# viewer looks for a subtitle, and it is small enough to read as one.
CAPTION_BAR_Y = 0.045


def caption_piece(b):
    """The words the slide itself should carry.

    A beat whose paragraph was split into pieces has them overlaid instead,
    and this is only reached when there is one piece, or when something is
    drawing a slide outside a render, like the template picker. Taking the
    first piece rather than the whole line means a long one is cut at a word
    boundary rather than disappearing off the bottom of the frame.
    """
    pieces = captions.split(b.get("say"))
    return pieces[0] if pieces else ""


def bottom_caption(fig, T, text):
    """One caption piece, small, at the bottom, the way a subtitle is set.

    This takes a piece rather than the whole beat. A paragraph set here runs
    off the bottom of the frame, and the answers to that are all bad: shrink
    it and nobody can read it, trim it and the picture stops saying what the
    voice is saying. captions.split does the dividing.
    """
    line = captions.wrapped(" ".join((text or "").split()))
    if not line:
        return
    t = fig.text(0.5, CAPTION_BAR_Y, line, ha="center", va="bottom",
                 fontsize=37, color=T.ink, linespacing=1.22)
    # a halo in the page colour whatever the template's lettering is, because
    # small text over rain or a photograph is the one place this cannot be
    # decorative
    import matplotlib.patheffects as pe
    t.set_path_effects([pe.withStroke(linewidth=8, foreground=T.bg)])
    _fit(fig, t, 1560)


def _presenter_content(fig, T, b, side):
    """What fills the half of the frame the figure is not standing in.

    The words, or nothing. Subtitles at the bottom free the middle, and what
    went in it was a shape matched from the line by keyword. That was never
    accurate enough to be worth looking at, so the half is left to the room
    and the light instead of being filled for the sake of filling it.
    """
    where = getattr(T, "captions", "headline")
    if where == "headline":
        text = (b.get("caption") or b.get("headline") or "").strip()
        if not text:
            return
        t = fig.text(0.5 - side * 0.17, 0.54,
                     "\n".join(textwrap.wrap(text.upper(), 15)),
                     ha="center", va="center", fontsize=56, color=T.ink,
                     fontweight="bold", linespacing=1.16)
        _fit(fig, t, 980)
        stagecraft.letter(t, T)
        return

    if where == "bottom" and not b.get("rolling"):
        bottom_caption(fig, T, caption_piece(b))


# ----------------------------------------------------------------------
# STORY COMPOSITIONS
#
# A frame with no cast in it needs a shape of its own or every template is
# the same template in a different colour. An icon in the middle was the
# first and only one, and it has a second problem: whatever the icon happens
# to be becomes what the template looks like, so a set of them all previewing
# a banknote reads as six ways of making a video about money.
#
# These are shapes rather than subjects. Each one is built from the headline,
# which any script has, so none of them is about anything in particular.


def _story_head(b, width=16, lines=4):
    text = (b.get("caption") or "").strip().upper()
    return "\n".join(textwrap.wrap(text, width)[:lines]) if text else ""


def comp_bare(fig, ax, b, T):
    """Nothing in the middle. The ground, the light, the weather, the words
    along the bottom, and that is the whole frame.

    The other compositions are built from the headline, and the headline is
    the first nine words of the paragraph. Set large in the middle while the
    subtitle runs the same paragraph underneath, that is the narration twice
    in two sizes. It is not a picture of anything, it is the sentence cut
    short and made big. This is the honest version: the background carries
    the shot and the words stay where subtitles go.
    """
    return


def comp_type(fig, ax, b, T):
    """The headline at the size of the frame. Works for any topic because it
    is only ever the words the script already wrote."""
    head = _story_head(b, 14, 4)
    if not head:
        return
    t = fig.text(0.5, 0.54, head, ha="center", va="center", fontsize=104,
                 color=T.ink, fontweight="bold", linespacing=1.06)
    _fit(fig, t, 1640)
    stagecraft.letter(t, T)


def comp_card(fig, ax, b, T):
    """A panel with the words mounted in it, the way a print is framed.

    The panel is what makes the middle of the frame feel composed rather than
    empty. What sits in it is the line the script wrote, which is always
    right, and not the symbol a keyword matched, which is often not.
    """
    step = 0.16 if _pale(T) else 0.13
    ax.add_patch(FancyBboxPatch(
        (-9.6, 3.6), 19.2, 10.8, zorder=1,
        boxstyle="round,pad=0,rounding_size=0.9",
        facecolor=mix(T.bg, "#000000" if _pale(T) else "#ffffff", step),
        edgecolor=mix(T.ink, T.bg, 0.45), linewidth=3.6))
    head = _story_head(b, 17, 4)
    if head:
        t = fig.text(0.5, 0.545, head, ha="center", va="center",
                     fontsize=70, color=T.ink, fontweight="bold",
                     linespacing=1.12)
        _fit(fig, t, 1020)


def comp_band(fig, ax, b, T):
    """A solid bar across the frame carrying the words. The most graphic of
    them and the one that reads at thumbnail size."""
    ax.add_patch(Rectangle((-16, 5.6), 32, 7.4, zorder=1, facecolor=T.a1,
                           edgecolor="none"))
    head = _story_head(b, 20, 3)
    if head:
        t = fig.text(0.5, 0.515, head, ha="center", va="center", fontsize=78,
                     color=_on(T.a1), fontweight="bold", linespacing=1.10)
        _fit(fig, t, 1700)


def comp_split(fig, ax, b, T):
    """A colour block down one side and the words in the rest of it, so the
    frame has a weight to it rather than being centred on nothing."""
    ax.add_patch(Rectangle((-16, -1), 11.5, 18, zorder=1, facecolor=T.a2,
                           edgecolor="none"))
    head = _story_head(b, 15, 4)
    if head:
        t = fig.text(0.66, 0.54, head, ha="center", va="center", fontsize=72,
                     color=T.ink, fontweight="bold", linespacing=1.10)
        _fit(fig, t, 1000)


COMPOSITIONS = {"bare": comp_bare, "type": comp_type, "card": comp_card,
                "band": comp_band, "split": comp_split}

# A composition built out of the headline already has the words in it, large.
# Running the caption underneath as well prints the opening of the beat twice
# in two sizes, which reads as a bug rather than as a subtitle. Every
# composition except the bare one is in here, because every one of them is
# built from the headline. Card was the one left out, and it was the one that
# shipped printing the beat twice.
TYPE_LED = ("type", "card", "band", "split")


def _pale(T):
    from .themes import _luminance
    return _luminance(T.bg) > 0.45


def _on(colour):
    """Ink that can be read on a solid block of `colour`."""
    from .themes import _luminance
    return "#14120d" if _luminance(colour) > 0.42 else "#fdfcf9"


def scene_story(fig, b, T):
    """No figure at all: a lit ground, a composition, and the words.

    The drawn cast is what makes this look like an explainer. Plenty of what
    people watch has nobody in it, and this is that shape.
    """
    shape = getattr(T, "composition", "bare")
    ax = _stage(fig, b, T, GROUND_Y, 0.5, empty=shape == "bare")
    COMPOSITIONS.get(shape, comp_bare)(fig, ax, b, T)
    # this layout has no headline slot beside a figure, so "headline" and
    # "bottom" both mean the bar. Only "none" leaves the frame silent.
    if (getattr(T, "captions", "headline") != "none"
            and shape not in TYPE_LED and not b.get("rolling")):
        bottom_caption(fig, T, caption_piece(b))


def scene_photo(fig, b, T):
    """A picture you brought, filling the frame, with the words under it.

    The template's light still goes over the top, so a spotlight or a vignette
    grades the photograph the same way it grades a drawn scene and the video
    holds together. With no picture to show this falls back to the story
    frame rather than rendering an empty rectangle.
    """
    path = b.get("image")
    if not path:
        return scene_story(fig, b, T)
    import matplotlib.image as mpimg
    ax = _stage(fig, b, T, GROUND_Y, 0.5)
    ax.imshow(mpimg.imread(path),
              extent=(X_MIN, X_MIN + STAGE_W, Y_MIN, Y_MIN + STAGE_H),
              aspect="auto", zorder=-5, interpolation="bilinear")
    if getattr(T, "captions", "headline") != "none" and not b.get("rolling"):
        bottom_caption(fig, T, caption_piece(b))


def scene_presenter(fig, b, T):
    """One figure held in place, the content beside them changing.

    A template can say it has no cast, in which case an undirected beat is
    drawn as a story frame instead. Doing the swap here rather than in the
    parser keeps the choice with the look, where it belongs: the same script
    renders with a presenter or without one depending only on the template.
    """
    kind = getattr(T, "layout", "presenter")
    if kind == "story":
        return scene_story(fig, b, T)
    if kind == "photo":
        return scene_photo(fig, b, T)
    side = -1 if b.get("side", "left") == "left" else 1
    head, _ = _shape(b)
    s = ch.scale_for_height(PRESENTER["height"] * STAGE_H, head, ch.HEAD_RATIO)
    px = presenter_x(side)
    ax = _stage(fig, b, T, GROUND_Y, focus_of(px))
    ch.ground(ax, GROUND_Y)
    _draw(ax, b, T, px, GROUND_Y, s)
    _presenter_content(fig, T, b, side)


def scene_character(fig, b, T):
    """One figure, an optional prop, framed wide, medium or close."""
    x, ground, s = _place(b)
    ax = _stage(fig, b, T, ground, focus_of(x))
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
    ax = _stage(fig, b, T, ground, focus_of(x))
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
    "scene_presenter": scene_presenter,
    "scene_story": scene_story,
    "scene_photo": scene_photo,
    "scene_character": scene_character,
    "scene_caption": scene_caption,
    "scene_duo": scene_duo,
    "scene_bubbles": scene_bubbles,
    "scene_split": scene_split,
    "scene_chart": scene_chart,
}
