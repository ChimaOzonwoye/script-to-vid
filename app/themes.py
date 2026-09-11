"""The four looks a video can ship in.

A theme is every colour the pipeline needs, resolved up front: slides,
character shirts, the web page, and the fade colour all read from the same
object, so nothing mixes colours at draw time.
"""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Theme:
    name: str
    label: str
    bg: str        # page background; also the fade colour
    panel: str     # callout panels, slightly deeper than the page
    ink: str       # body text and outlines
    dim: str       # captions and axis labels
    grid: str      # chart grid lines
    a1: str        # primary accent
    a1_hi: str     # darker primary, for text that must stay readable
    a1_pale: str   # fills and halos
    a2: str        # secondary accent
    a2_hi: str
    a2_pale: str
    ui: str        # accent for solid controls, dark enough for white text
    ground: str = "plain"   # the pattern laid under every scene
    light: str = "flat"     # the gradient laid over the ground
    lettering: str = "plain"   # how headline type is treated
    dressing: str = "none"     # one object standing beside the speaker
    captions: str = "headline"  # where the words go, if anywhere
    layout: str = "presenter"   # "presenter" has a cast, "story" has none
    blurb: str = ""         # one line describing the look, shown on the page


def _luminance(c):
    v = [int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]


def contrast_on_white(c):
    return 1.05 / (_luminance(c) + 0.05)


def _ui_accent(a1, a2, ink):
    """The accent a solid button can be built from.

    Two of the four palettes lead with amber, and white text on amber is
    unreadable. Start from whichever accent is already darker and deepen it
    until white text on it clears 4.5 to 1, so every theme has a usable
    control colour rather than a pretty one.
    """
    base = a1 if _luminance(a1) < _luminance(a2) else a2
    for step in range(0, 21):
        c = mix(base, ink, step / 20)
        if contrast_on_white(c) >= 4.5:
            return c
    return ink


PAGE_INK = "#1b1a17"


def _readable(c, ink, floor=3.0):
    """Deepen a colour until it can be read on a near-white page."""
    for step in range(0, 21):
        candidate = mix(c, ink, step / 20)
        if contrast_on_white(candidate) >= floor:
            return candidate
    return ink


def page_palette(T):
    """The app page for a template: its own colours when they suit a page.

    Taking the template's colours straight is a nice piece of feedback, and
    while every template was pale it was also safe. A template built on a dark
    ground would have taken the whole app dark with it, and a dark app was
    never designed. So a pale template still hands its palette over unchanged,
    and a dark one lends its hue to a light page instead of its lightness.
    """
    if _luminance(T.bg) > 0.55:
        return {"bg": T.bg, "panel": T.panel, "ink": T.ink, "dim": T.dim,
                "grid": T.grid, "accent": T.ui, "accent2": T.a1,
                "accent_pale": T.a2_pale, "accent2_pale": T.a1_pale}

    ink, bg = PAGE_INK, mix("#ffffff", T.a1, 0.10)
    a1, a2 = _readable(T.a1, ink), _readable(T.a2, ink)
    return {
        "bg": bg, "panel": mix(bg, ink, 0.045), "ink": ink,
        "dim": mix(ink, bg, 0.42), "grid": mix(ink, bg, 0.86),
        "accent": _ui_accent(a1, a2, ink), "accent2": a1,
        "accent_pale": mix(a2, bg, 0.74), "accent2_pale": mix(a1, bg, 0.74),
    }


def mix(c1, c2, t):
    """Linear blend of two hex colours, `t` of the way from c1 to c2."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def _theme(name, label, bg, ink, a1, a2, ground="plain", light="flat",
           lettering="plain", dressing="none", captions="headline",
           layout="presenter", blurb="", **fixed):
    derived = dict(
        bg=bg, ink=ink, a1=a1, a2=a2,
        panel=mix(bg, ink, 0.04),
        dim=mix(ink, bg, 0.42),
        grid=mix(ink, bg, 0.86),
        a1_hi=mix(a1, ink, 0.30), a1_pale=mix(a1, bg, 0.68),
        a2_hi=mix(a2, ink, 0.30), a2_pale=mix(a2, bg, 0.68),
    )
    derived.update(fixed)
    derived["ui"] = _ui_accent(derived["a1"], derived["a2"], ink)
    return Theme(name=name, label=label, ground=ground, light=light,
                 lettering=lettering, dressing=dressing,
                 captions=captions, layout=layout, blurb=blurb,
                 **derived)


# Cream keeps the hand-picked values the engine shipped with. The blends
# above land close but not identical, and this theme is the reference look.
THEMES = {
    "cream": _theme("cream", "Cream", "#faf6ec", "#1d1b16", "#c8912c", "#0f766e",
                    panel="#f3ecdc", dim="#7a7266", grid="#e0d8c6",
                    a1_hi="#9c6d16", a1_pale="#f0dfae",
                    a2_hi="#0b524c", a2_pale="#cfe7e3"),
    "paper": _theme("paper", "Paper white", "#ffffff", "#111111", "#2563eb", "#f97316"),
    "sky":   _theme("sky", "Sky", "#eaf4fb", "#0f172a", "#0284c7", "#f59e0b"),
    "mint":  _theme("mint", "Mint", "#f0f7f2", "#14231a", "#059669", "#d97706"),
}

# The four above are the quiet family the tool shipped with: pale ground, even
# light, the palette doing all the work. The five below are what a template is
# for. Each one commits to a ground and a light as well as a palette, because
# a look is not a set of colours: the same four colours flat on a page and the
# same four on a lit stage are two different films.
THEMES.update({
    "mustard": _theme(
        "mustard", "Mustard", "#e6b23c", "#17140d", "#d0472a", "#0e6b60",
        ground="stage", light="glow", lettering="slab",
        blurb="Saturated yellow, a solid floor, warm light on the speaker."),
    "riso": _theme(
        "riso", "Riso print", "#f2ece0", "#16120e", "#d8443a", "#2a4fbf",
        ground="dots", light="flat", lettering="drop",
        blurb="Two ink colours on paper stock, flat and printed."),
    "coral": _theme(
        "coral", "Coral", "#ef8f6c", "#2a1410", "#f3cd68", "#1a6b74",
        ground="rays", light="warm", lettering="halo",
        blurb="Warm ground, a sunburst behind the speaker, light from above."),
    "slate": _theme(
        "slate", "Slate", "#212c3a", "#f1eee4", "#efa531", "#4fb3a5",
        ground="arch", light="spot", lettering="drop",
        blurb="Dark room, one panel behind the speaker, a pool of light."),
    "forest": _theme(
        "forest", "Deep forest", "#134339", "#f0f2e4", "#e8c46a", "#7cbd99",
        ground="bars", light="vignette", lettering="halo", dressing="plant",
        blurb="Deep green, banded ground, a plant in the corner."),
    "ledger": _theme(
        "ledger", "Ledger", "#1d3a4d", "#f4f1e6", "#e0a33a", "#5aa9a0",
        ground="stage", light="glow", lettering="drop", dressing="growth",
        blurb="For money: a lit desk, a chart on the wall behind."),
    "nightfall": _theme(
        "nightfall", "Nightfall", "#171a2b", "#eeeaf2", "#c9a2e8", "#5fa8d3",
        ground="plain", light="vignette", lettering="plain",
        captions="bottom", layout="story",
        blurb="Storytelling: no figure, the words at the bottom, the middle "
              "left for the picture."),
    "studio": _theme(
        "studio", "Studio", "#f1e7d8", "#1a1712", "#c2603f", "#3f6f82",
        ground="arch", light="warm", lettering="plain", dressing="board",
        blurb="A warm room with a board on the wall, for teaching."),
})

DEFAULT_THEME = "cream"


# Light and lettering ship as part of a template but are not locked to it. A
# template is a starting point, and the two axes most worth moving on their own
# are how the frame is lit and how the type is set: the same palette under a
# spotlight is a different film, and the same film with the words in a slab is
# a different channel. Ground stays with the template, because a ground and a
# palette are chosen together or they fight.
LIGHT_LABELS = {"flat": "Even", "glow": "Warm pool", "vignette": "Closing in",
                "warm": "From above", "spot": "Spotlight"}

LETTERING_LABELS = {"plain": "Plain", "halo": "Haloed", "drop": "Drop shadow",
                    "slab": "In a slab"}

DRESSING_LABELS = {"none": "Nothing", "board": "A board on the wall",
                   "growth": "A chart on the wall", "plant": "A plant",
                   "flowers": "Flowers", "cat": "An animal"}

# Where the spoken words go on screen. The big centred headline was the only
# option and it gets read as a subtitle, which it is not: it is a design
# element competing with the thing the beat is about. "bottom" puts the words
# where a subtitle belongs and leaves the middle of the frame for a picture.
# "none" leaves the burned in words out entirely; final.srt still carries them
# and any player can switch them on.
CAPTION_LABELS = {"headline": "A headline beside the speaker",
                  "bottom": "Small, at the bottom",
                  "none": "None on screen, subtitle file only"}


def resolve(name, light=None, lettering=None, dressing=None,
            captions=None):
    """The template to render with, after any choices made on top of it."""
    T = THEMES.get(name, THEMES[DEFAULT_THEME])
    changes = {}
    if light in LIGHT_LABELS:
        changes["light"] = light
    if lettering in LETTERING_LABELS:
        changes["lettering"] = lettering
    if dressing in DRESSING_LABELS:
        changes["dressing"] = dressing
    if captions in CAPTION_LABELS:
        changes["captions"] = captions
    return replace(T, **changes) if changes else T
