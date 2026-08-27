"""The four looks a video can ship in.

A theme is every colour the pipeline needs, resolved up front: slides,
character shirts, the web page, and the fade colour all read from the same
object, so nothing mixes colours at draw time.
"""

from dataclasses import dataclass


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


def mix(c1, c2, t):
    """Linear blend of two hex colours, `t` of the way from c1 to c2."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def _theme(name, label, bg, ink, a1, a2, **fixed):
    derived = dict(
        bg=bg, ink=ink, a1=a1, a2=a2,
        panel=mix(bg, ink, 0.04),
        dim=mix(ink, bg, 0.42),
        grid=mix(ink, bg, 0.86),
        a1_hi=mix(a1, ink, 0.30), a1_pale=mix(a1, bg, 0.68),
        a2_hi=mix(a2, ink, 0.30), a2_pale=mix(a2, bg, 0.68),
    )
    derived.update(fixed)
    return Theme(name=name, label=label, **derived)


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

DEFAULT_THEME = "cream"
