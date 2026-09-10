import re

from app.themes import THEMES, DEFAULT_THEME, mix

HEX = re.compile(r"^#[0-9a-f]{6}$")


def test_the_quiet_family_is_still_there():
    """The four the tool shipped with are a family, not a leftover: pale
    ground, even light, palette doing all the work. Templates were added
    beside them, not instead of them."""
    assert {"cream", "paper", "sky", "mint"} <= set(THEMES)
    assert DEFAULT_THEME in THEMES
    for name in ("cream", "paper", "sky", "mint"):
        assert THEMES[name].ground == "plain" and THEMES[name].light == "flat"


def test_every_template_names_a_ground_and_a_light_that_exist():
    from app.stagecraft import GROUNDS, LIGHTS
    for T in THEMES.values():
        assert T.ground in GROUNDS, (T.name, T.ground)
        assert T.light in LIGHTS, (T.name, T.light)


def test_a_dark_template_still_leaves_the_page_light():
    """The page took the template's colours straight while every template was
    pale. A dark ground would otherwise have taken the whole app dark."""
    from app.themes import _luminance, page_palette
    dark = [T for T in THEMES.values() if _luminance(T.bg) < 0.3]
    assert dark, "no dark template to check"
    for T in dark:
        page = page_palette(T)
        assert _luminance(page["bg"]) > 0.75, (T.name, page["bg"])
        assert _luminance(page["ink"]) < 0.1, (T.name, page["ink"])


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


def test_every_template_has_a_legible_control_colour():
    """Two palettes lead with amber, and white text on amber is unreadable.
    The page accent is derived rather than picked, so this has to hold for any
    template added later too, dark ones included."""
    from app.themes import contrast_on_white, page_palette
    for T in THEMES.values():
        accent = page_palette(T)["accent"]
        assert HEX.match(accent.lower()), (T.name, accent)
        assert contrast_on_white(accent) >= 4.5, (T.name, accent,
                                                  contrast_on_white(accent))


def test_the_control_colour_still_belongs_to_the_theme():
    """It is a darkened accent, not a colour from nowhere."""
    from app.themes import mix
    for T in THEMES.values():
        options = [mix(a, T.ink, i / 20)
                   for a in (T.a1, T.a2) for i in range(21)]
        assert T.ui in options, (T.name, T.ui)
