"""The rules that decide what a line in a pasted script is.

Real scripts are not written for this tool. They arrive with stage
directions, timecodes and `Narration:` labels down the left margin, and the
cost of reading one of those aloud is a video the user cannot publish. The
cost of skipping a real line is worse, which is why nothing is skipped
silently: every one of these comes back in `skipped` for the page to show.
"""

import pytest

from app.script_parser import MARKER, NOTE, classify, parse


def kinds(text, **kw):
    return [(b["visual"], b["say"]) for b in parse(text, **kw)["beats"]]


def spoken(text, **kw):
    return " ".join(b["say"] for b in parse(text, **kw)["beats"])


# ----------------------------------------------------------------------
# the table
# ----------------------------------------------------------------------
@pytest.mark.parametrize("line", [
    "[Scene 1 - man at a desk]",
    "[0:00 - 0:15]",
    "[End card]",
    "// a note to self",
    "Music: upbeat piano",
    "Audio: fade in",
    "SFX: coins dropping",
])
def test_notes_are_skipped(line):
    assert classify(line)[0] == NOTE


@pytest.mark.parametrize("line", [
    "Scene 3", "Script 1", "Part 2", "Chapter 4", "Section 5", "Act 2",
    "0:00", "00:15", "1:23:45", "0:00 - 0:15", "0:00-0:15", "(0:30)",
])
def test_bare_markers_are_skipped(line):
    assert classify(line)[0] == MARKER


@pytest.mark.parametrize("line", [
    "Step one. Spend every dollar you earn.",
    "Scene 3 shows the kitchen.",
    "Here is the point: saving is hard.",
    "Part 2 is where it gets interesting.",
    "I woke up at 6:30 and went straight out.",
])
def test_a_marker_only_counts_as_the_whole_line(line):
    """The commonest way to get this wrong is to match anywhere in the line
    and silently delete somebody's narration."""
    assert classify(line) == ("narration", line)


@pytest.mark.parametrize("label,kind", [
    ("Narration", "narration"), ("Voiceover", "narration"),
    ("Title", "chapter"),
    ("Visual", "caption"), ("Visuals", "caption"), ("On-screen", "caption"),
    ("Text", "caption"), ("B-roll", "caption"),
])
def test_labels_are_stripped_and_routed(label, kind):
    assert classify(f"{label}: Save ten percent.") == (kind, "Save ten percent.")


def test_explicit_syntax_always_wins():
    assert classify("> character: happy")[0] == "direction"
    assert classify("# Scene 3") == ("chapter", "Scene 3")


@pytest.mark.parametrize("line,want", [
    ('"Saving is simple."', "Saving is simple."),
    ("'Saving is simple.'", "Saving is simple."),
    ("“Saving is simple.”", "Saving is simple."),
    ("'Tis the season to overspend.", "'Tis the season to overspend."),
])
def test_surrounding_quotes_come_off_narration(line, want):
    """Scripts wrap spoken lines in quotes and the voice reads them out."""
    assert classify(line) == ("narration", want)


# ----------------------------------------------------------------------
# what the page is told
# ----------------------------------------------------------------------
def test_every_skipped_line_is_reported():
    text = "[a note]\n0:00\n// hidden\nReal narration here.\n"
    r = parse(text)
    assert [k["text"] for k in r["skipped"]] == ["[a note]", "0:00", "// hidden"]
    assert [k["kind"] for k in r["skipped"]] == [NOTE, MARKER, NOTE]
    assert [k["line"] for k in r["skipped"]] == [1, 2, 3]
    assert spoken(text) == "Real narration here."


def test_a_line_put_back_is_spoken():
    text = "Scene 3\n\nReal narration here.\n"
    assert "Scene 3" not in spoken(text)
    assert "Scene 3" in spoken(text, keep=["Scene 3"])
    assert parse(text, keep=["Scene 3"])["skipped"] == []


def test_lines_are_put_back_by_text_not_by_number():
    """Keyed on the line number, editing the script above a restored line
    would quietly restore a different one."""
    text = "An opening line of narration.\nScene 3\n\nMore narration.\n"
    edited = "An opening line.\nAnd another one added above.\nScene 3\n\nMore.\n"
    assert "Scene 3" in spoken(text, keep=["Scene 3"])
    assert "Scene 3" in spoken(edited, keep=["Scene 3"])


# ----------------------------------------------------------------------
# the reported crash
# ----------------------------------------------------------------------
def test_a_bare_hash_makes_no_beat():
    """It names no chapter and says nothing. Left as a beat it went to the
    voice service, came back empty, and the render died measuring it."""
    assert parse("#\n\nReal narration here.")["beats"] == \
        parse("Real narration here.")["beats"]


@pytest.mark.parametrize("text", [
    "#\n#\n#\n", "# \n\n# \n", ">\n>\n", "> :\n\nWords.\n", "#", ">", "",
    "   \n\t\n", "\"\"\n\nWords.\n", "''\n\nWords.\n",
])
def test_no_beat_is_ever_left_with_nothing_to_say(text):
    for b in parse(text)["beats"]:
        assert b["say"].strip(), b


def test_a_script_of_headings_becomes_narration():
    text = "# Introduction\n# Why it matters\n# The first step\n# In closing\n"
    beats = parse(text)["beats"]
    assert not any(b["visual"] == "chapter" for b in beats), \
        "a video of nothing but chapter cards"
    assert len(beats) == 4, "each heading is its own thought, not one paragraph"
    assert parse(text)["warnings"], "the user is not told what happened"


@pytest.mark.parametrize("text", [
    "# Real chapter\n\nA paragraph of narration goes here.\n",
    "# A chapter heading",
    "# One\n\nSome narration.\n\n# Two\n\nMore narration.\n",
])
def test_a_normal_script_keeps_its_chapters(text):
    """The flood rule needs a pattern to act on. A short script that opens
    with a heading is not somebody misunderstanding the format."""
    assert any(b["visual"] == "chapter" for b in parse(text)["beats"]), text


HOSTILE = [
    "#" * 500, ">" * 500, "[" * 200, "Narration:" * 80, "\x00\x01\x02",
    "a" * 10000, "\n" * 500, "> character: " + "x," * 200,
    "[unclosed bracket", "unopened bracket]", "//", "Title:", "0:",
    ":" * 50, "“" * 40, "> scene: " + "é" * 50, "\r\n\r\n\r\n",
]


@pytest.mark.parametrize("text", HOSTILE)
def test_the_parser_never_raises(text):
    """A script is user input, and the page must never show a traceback."""
    r = parse(text)
    assert isinstance(r["beats"], list) and isinstance(r["skipped"], list)


# ----------------------------------------------------------------------
# what the interface claims
# ----------------------------------------------------------------------
def _read(*parts):
    from pathlib import Path
    return (Path(__file__).resolve().parents[2].joinpath(*parts)).read_text()


def test_the_script_step_leads_with_pasting_not_with_syntax():
    """A user asked a chatbot how to use this and was told to add # headings,
    because the page taught # and > before saying they were optional."""
    page = _read("app", "templates", "project.html")
    step = page.split('<h2><span class="stepnum">2</span>Script</h2>', 1)[1]
    hint = step.split('<p class="hint">', 1)[1].split("</p>", 1)[0]
    assert "Paste your script" in hint
    assert "#" not in hint and "&gt;" not in hint, \
        "the first thing said about the script box is still syntax"


def test_the_direction_syntax_is_folded_away():
    page = _read("app", "templates", "project.html")
    assert '<details class="fmt">' in page
    fmt = page.split('<details class="fmt">', 1)[1].split("</details>", 1)[0]
    assert "None of this is required" in fmt
    assert "&gt; character" in fmt, "the syntax is not in the panel"
    assert "<details class=\"fmt\" open" not in page, "the panel starts open"


def test_the_placeholder_shows_plain_narration():
    page = _read("app", "templates", "project.html")
    ph = page.split('placeholder="', 1)[1].split('"', 1)[0]
    assert "#" not in ph and "&gt;" not in ph


def test_the_readme_says_formatting_is_optional_before_teaching_it():
    readme = _read("README.md")
    section = readme.split("## The script format", 1)[1]
    assert section.lstrip().startswith("**No special formatting is required.**")
    # the syntax may only appear after the optional heading
    optional = section.index("### Optional formatting")
    assert "> character:" not in section[:optional]
    assert "> character:" in section[optional:]
