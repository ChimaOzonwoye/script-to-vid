import re

from app.themes import THEMES, DEFAULT_THEME, mix

HEX = re.compile(r"^#[0-9a-f]{6}$")


def test_four_themes():
    assert set(THEMES) == {"cream", "paper", "sky", "mint"}
    assert DEFAULT_THEME in THEMES


def test_every_colour_is_valid_hex():
    for T in THEMES.values():
        for field in ("bg", "panel", "ink", "dim", "grid",
                      "a1", "a1_hi", "a1_pale", "a2", "a2_hi", "a2_pale"):
            assert HEX.match(getattr(T, field).lower()), (T.name, field)


def test_cream_keeps_the_original_engine_colours():
    T = THEMES["cream"]
    assert T.bg == "#faf6ec"
    assert T.ink == "#1d1b16"
    assert T.a1 == "#c8912c" and T.a1_hi == "#9c6d16" and T.a1_pale == "#f0dfae"
    assert T.a2 == "#0f766e" and T.a2_hi == "#0b524c" and T.a2_pale == "#cfe7e3"
    assert T.panel == "#f3ecdc" and T.dim == "#7a7266" and T.grid == "#e0d8c6"


def test_prd_table_values():
    assert THEMES["paper"].bg == "#ffffff"
    assert THEMES["paper"].a1 == "#2563eb" and THEMES["paper"].a2 == "#f97316"
    assert THEMES["sky"].bg == "#eaf4fb"
    assert THEMES["mint"].a1 == "#059669"


def test_mix():
    assert mix("#000000", "#ffffff", 0) == "#000000"
    assert mix("#000000", "#ffffff", 1) == "#ffffff"
    assert mix("#000000", "#ffffff", 0.5) == "#808080"


def test_every_theme_has_a_legible_control_colour():
    """Two palettes lead with amber, and white text on amber is unreadable.
    The UI accent is derived rather than picked, so this has to hold for any
    theme added later too."""
    from app.themes import contrast_on_white
    for T in THEMES.values():
        assert HEX.match(T.ui.lower()), (T.name, T.ui)
        assert contrast_on_white(T.ui) >= 4.5, (T.name, T.ui,
                                                contrast_on_white(T.ui))


def test_the_control_colour_still_belongs_to_the_theme():
    """It is a darkened accent, not a colour from nowhere."""
    from app.themes import mix
    for T in THEMES.values():
        options = [mix(a, T.ink, i / 20)
                   for a in (T.a1, T.a2) for i in range(21)]
        assert T.ui in options, (T.name, T.ui)
