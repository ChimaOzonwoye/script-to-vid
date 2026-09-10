from pathlib import Path

from app.script_parser import DEFAULT_VISUAL, parse

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


def test_undirected_narration_is_the_presenter():
    """Rotating four layouts and moving the figure every beat is what made a
    run of beats read as a slideshow. One presenter, held in place."""
    text = "\n\n".join(f"Paragraph number {i} with plain narration."
                        for i in range(8))
    beats = parse(text)["beats"]
    assert {b["visual"] for b in beats} == {DEFAULT_VISUAL}
    assert all(b.get("caption") for b in beats), "nothing beside the presenter"


def test_the_presenter_holds_its_side_and_swaps_at_a_chapter():
    """Swapping per beat would be the figure hopping about. Swapping at a
    chapter reads as a cut to the other camera."""
    text = ("One.\n\nTwo.\n\nThree.\n\n# Next chapter\n\n"
            "Four.\n\nFive.\n\n# Third chapter\n\nSix.\n")
    sides = [b.get("side") for b in parse(text)["beats"] if b.get("side")]
    assert sides == ["left", "left", "left", "right", "right", "left"]


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


def test_the_headline_never_ends_mid_phrase():
    """A fixed word cut lands on "OUT BEFORE" or "FOR THE DAY AFTER" and the
    reader waits out the beat for an object that never comes."""
    from app.script_parser import _DANGLING, _auto_headline
    scripts = [
        "The trick is to take the money out before you can spend it.",
        "Set up a standing order for the day after your salary lands.",
        "This is a very long sentence with no punctuation at all that runs on",
        "Compound interest, the thing everyone mentions, is the force here.",
    ]
    for s in scripts:
        head = _auto_headline(s)
        assert head, s
        assert head.split()[-1].lower() not in _DANGLING, head


def test_a_short_sentence_is_the_headline_whole():
    """Cutting a sentence that already fits only loses meaning."""
    from app.script_parser import _auto_headline
    assert _auto_headline("Saving money is simple but not easy.") == \
        "SAVING MONEY IS SIMPLE BUT NOT EASY"
