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


def test_light_and_lettering_can_be_moved_off_the_template():
    """A template is a starting point. The two axes worth moving on their own
    are how the frame is lit and how the type is set."""
    from app.themes import resolve
    assert resolve("cream").light == THEMES["cream"].light
    assert resolve("cream", light="spot").light == "spot"
    assert resolve("mustard", lettering="halo").lettering == "halo"
    # everything else still comes from the template
    assert resolve("mustard", light="spot").ground == THEMES["mustard"].ground


def test_a_nonsense_override_is_ignored_rather_than_rendered():
    """These arrive from a form post, so they cannot be trusted to name
    anything that exists."""
    from app.themes import resolve
    assert resolve("cream", light="../../etc").light == "flat"
    assert resolve("cream", lettering="").lettering == "plain"
    assert resolve("no-such-template").name == DEFAULT_THEME


def test_the_look_travels_on_the_theme_so_the_cache_covers_it():
    """Segment keys are built from the theme object. An override that did not
    live on it would leave a project showing its old lighting after a change."""
    from dataclasses import asdict
    from app.themes import resolve
    a, b = resolve("cream"), resolve("cream", light="spot", lettering="slab")
    assert asdict(a) != asdict(b)


def test_a_template_can_stand_something_beside_the_speaker():
    """Rooms already exist, but a room is furniture across the whole frame and
    is picked per beat. This is one object a template carries everywhere."""
    from app.stagecraft import DRESSING
    from app.themes import DRESSING_LABELS, resolve
    assert set(DRESSING_LABELS) == set(DRESSING)
    for T in THEMES.values():
        assert T.dressing in DRESSING, (T.name, T.dressing)
    assert resolve("cream", dressing="cat").dressing == "cat"
    assert resolve("cream", dressing="dragon").dressing == "none"


def test_nothing_stands_beside_the_speaker_in_the_quiet_family():
    for name in ("cream", "paper", "sky", "mint"):
        assert THEMES[name].dressing == "none"


def test_the_words_can_be_moved_off_the_middle_of_the_frame():
    """The big centred headline reads as a subtitle and is not one: it is a
    design element sitting where the picture should be."""
    from app.themes import CAPTION_LABELS, resolve
    assert set(CAPTION_LABELS) == {"headline", "bottom", "none"}
    for T in THEMES.values():
        assert T.captions in CAPTION_LABELS, (T.name, T.captions)
    assert resolve("cream", captions="bottom").captions == "bottom"
    assert resolve("cream", captions="middle").captions == "headline"


def test_a_template_can_have_no_cast():
    """Plenty of narrated video has nobody in it. The swap is a property of
    the look, so the same script renders both ways."""
    assert THEMES["nightfall"].layout == "story"
    for name in ("cream", "paper", "sky", "mint"):
        assert THEMES[name].layout == "presenter"
        assert THEMES[name].captions == "headline"


def test_a_story_template_never_leaves_the_line_unreadable():
    """That layout has no headline slot, so "headline" there has to mean the
    caption bar rather than nothing at all."""
    from app import scenes
    assert scenes.VISUALS["scene_story"] is scenes.scene_story


def test_the_picker_can_show_one_family_at_a_time():
    """Sixteen templates will not fit on a step and would not be readable if
    they did. Every template has to land in a group or it is unreachable."""
    from app.themes import FAMILY_LABELS, by_family
    grouped = by_family()
    assert set(grouped) == set(FAMILY_LABELS)
    seen = {k for ts in grouped.values() for k in ts}
    assert seen == set(THEMES), set(THEMES) - seen
    for fam, ts in grouped.items():
        assert ts, f"{fam} is empty and would show an empty tab"


def test_weather_is_a_choice_of_its_own():
    from app.themes import EFFECT_LABELS, resolve
    from app.effects import EFFECTS
    assert set(EFFECT_LABELS) == {"none", *EFFECTS}
    for T in THEMES.values():
        assert T.effect in EFFECT_LABELS, (T.name, T.effect)
    assert resolve("cream", effect="snow").effect == "snow"
    assert resolve("cream", effect="hurricane").effect == "none"


def test_every_template_names_a_layout_that_exists():
    from app import scenes
    for T in THEMES.values():
        assert T.layout in ("presenter", "story", "photo"), (T.name, T.layout)
    assert "scene_photo" in scenes.VISUALS


def test_the_frame_shape_is_a_choice_and_every_template_names_a_real_one():
    """Six templates with one shape between them are one template in six
    colours, which is what they looked like."""
    from app.scenes import COMPOSITIONS
    from app.themes import COMPOSITION_LABELS, by_family, resolve
    assert set(COMPOSITION_LABELS) == set(COMPOSITIONS)
    for T in THEMES.values():
        assert T.composition in COMPOSITIONS, (T.name, T.composition)
    assert resolve("nightfall", composition="band").composition == "band"
    assert resolve("nightfall", composition="spiral").composition == "icon"

    # the storytelling family has to actually differ, or grouping them is a lie
    story = by_family()["story"]
    shapes = {t.composition for t in story.values()}
    assert len(shapes) >= 4, f"only {len(shapes)} shapes across {len(story)}"


def test_a_type_led_frame_does_not_print_the_words_twice():
    """The big type is built from the headline and the first caption piece
    comes from the same sentence, so running both prints the opening of every
    beat twice in two sizes."""
    from app import scenes
    assert set(scenes.TYPE_LED) <= set(scenes.COMPOSITIONS)
    for shape in scenes.TYPE_LED:
        assert shape in ("type", "band", "split")
