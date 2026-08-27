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
