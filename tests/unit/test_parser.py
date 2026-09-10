from pathlib import Path

from app.script_parser import parse, ROTATION

EXAMPLE = (Path(__file__).resolve().parents[2] / "example-script.txt").read_text()


def test_the_example_script_has_no_markup_in_it():
    """It is the first thing a new user sees, and the interface used to imply
    markup was required. It is not, so the example does not use any."""
    lines = [ln.strip() for ln in EXAMPLE.splitlines() if ln.strip()]
    assert lines, "the example is empty"
    assert not any(ln.startswith(("#", ">")) for ln in lines), \
        "the example teaches syntax before saying it is optional"

    r = parse(EXAMPLE)
    assert r["warnings"] == [] and r["skipped"] == []
    assert len(r["beats"]) >= 4, "too short to show what the tool does"
    assert all(b.get("caption") or b.get("headline") for b in r["beats"])
    assert r["words"] > 0


def test_a_fully_marked_up_script_still_works():
    """The example no longer covers the directions, so this does."""
    r = parse("""# How to boil an egg

> character: happy, cheer
> caption: Cover them by an inch

Start with eggs straight from the fridge.

> bubbles: soft?, medium?, hard?

Six minutes gives you a runny yolk.

> split: Straight from the pan | Into cold water

Lift them out into cold water when the time is up.

> chart: growth

The difference adds up over a lot of breakfasts.
""")
    assert r["warnings"] == []
    visuals = [b["visual"] for b in r["beats"]]
    assert visuals[0] == "chapter" and r["beats"][0]["num"] == "01"
    assert {"scene_character", "scene_bubbles", "scene_split",
            "scene_chart"} <= set(visuals)


def test_character_direction_fields():
    r = parse("> character: worried, think, triangle\n\nSome narration.")
    b = r["beats"][0]
    assert (b["expr"], b["pose"], b["head"]) == ("worried", "think", "triangle")


def test_character_tokens_in_any_order():
    r = parse("> character: triangle, worried\n\nSome narration.")
    b = r["beats"][0]
    assert b["head"] == "triangle" and b["expr"] == "worried"


def test_unknown_direction_becomes_caption_with_warning():
    r = parse("> hologram: spinning\n\nSome narration.")
    assert r["beats"][0]["visual"] == "caption"
    assert any("hologram" in w for w in r["warnings"])


def test_unknown_character_token_warns_but_parses():
    r = parse("> character: worried, moonwalk\n\nSome narration.")
    assert r["beats"][0]["visual"] == "scene_character"
    assert any("moonwalk" in w for w in r["warnings"])


def test_unknown_prop_warns():
    r = parse("> character: happy\n> prop: yacht\n\nSome narration.")
    assert "prop" not in r["beats"][0]
    assert any("yacht" in w for w in r["warnings"])


def test_rotation_never_repeats_layout():
    text = "\n\n".join(f"Paragraph number {i} with plain narration." for i in range(8))
    visuals = [b["visual"] for b in parse(text)["beats"]]
    assert all(a != b for a, b in zip(visuals, visuals[1:]))
    assert set(visuals) <= set(ROTATION)


def test_direction_without_narration_is_skipped():
    r = parse("Some narration first.\n\n> gauge")
    assert len(r["beats"]) == 1
    assert any("no narration" in w for w in r["warnings"])


def test_two_primary_directions_keeps_first():
    r = parse("> gauge\n> growth\n\nSome narration.")
    assert r["beats"][0]["visual"] == "gauge"
    assert any("growth" in w for w in r["warnings"])


def test_empty_script():
    r = parse("")
    assert r["beats"] == []
    assert r["warnings"]


def test_never_raises_on_garbage():
    for text in (None, ">", "> :", "#", "\x00\x01\x02", "> character:,,,\n\nx",
                 "> split: |\n\nx", 10000 * "a ", "> terms:\n\nwords here"):
        parse(text)


def test_beats_carry_no_line_numbers():
    a = parse("Some narration here.")
    b = parse("\n\n\n\nSome narration here.")
    assert a["beats"] == b["beats"]


def test_cast_rotates_by_chapter():
    text = ("# One\n\n> character: happy\n\nFirst.\n\n"
            "# Two\n\n> character: happy\n\nSecond.")
    beats = [b for b in parse(text)["beats"] if b["visual"] == "scene_character"]
    assert beats[0]["cast_i"] != beats[1]["cast_i"]
