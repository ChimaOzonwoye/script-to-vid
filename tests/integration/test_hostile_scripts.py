"""Scripts that broke the tool, rendered end to end.

A user asked a chatbot how to use this, was told to add `#` headings, and
got a tool that failed and kept failing. The parse stage was never the
problem: a heading with no title became a beat with nothing to say, the
voice service returned an empty file for it, and the render died measuring
that file. The empty file stayed in a cache keyed on the line, so pressing
Generate again failed in exactly the same way for ever.
"""

import pytest

from app import engine, projects
from app.script_parser import parse
from app.themes import THEMES

MARKED_UP = """# How to save money
> character: happy, cheer
> caption: Start here

Saving money is simple but not easy.

# Step one
> character: neutral, offer

Put ten percent aside before you spend anything else.

#
>
"""

CHATGPT = """[Scene 1 - man at a desk]
0:00 - 0:15
Title: How to save money
Narration: Saving money is simple but not easy.
Visual: a jar of coins on a table
Music: upbeat piano

Scene 2
// re-record this bit
"Start with ten percent of every paycheck."

[End card]
"""

ALL_HEADINGS = "# Introduction\n# Why it matters\n# The first step\n# In closing\n"


@pytest.mark.parametrize("script,name", [
    (MARKED_UP, "marked up"),
    (CHATGPT, "chatbot formatted"),
    (ALL_HEADINGS, "all headings"),
])
def test_it_produces_a_video(project, script, name):
    p = projects.path_of(project)
    beats = parse(script)["beats"]
    assert beats, name
    r = engine.render_video(p, beats, THEMES["cream"])
    assert r["video"].exists() and r["video"].stat().st_size > 0, name
    assert engine.duration(r["video"]) > 0, name


def test_a_line_the_voice_service_answers_with_nothing(project, monkeypatch):
    """It can answer without failing and still send back nothing. Cached,
    that line can never be regenerated and the project is stuck."""
    p = projects.path_of(project)
    beats = parse("A line nobody has spoken before now.")["beats"]
    monkeypatch.setattr(engine, "_fake_voice",
                        lambda text, path: path.write_bytes(b""))
    with pytest.raises(engine.RenderError) as e:
        engine.render_video(p, beats, THEMES["cream"])
    assert "Generate again" in str(e.value)
    assert not list((p / "cache" / "voice").glob("*.mp3")), \
        "an unusable file was left in the cache, so a retry cannot help"


def test_a_damaged_file_is_named_rather_than_raising_ffprobe(tmp_path):
    bad = tmp_path / "broken.mp3"
    bad.write_bytes(b"not audio")
    with pytest.raises(engine.RenderError) as e:
        engine.duration(bad)
    assert "broken.mp3" in str(e.value)


def test_the_stuck_project_recovers_on_the_next_run(project, monkeypatch):
    """The whole point of not caching the bad file: pressing Generate again
    has to be able to work.

    The stand-in is put back by hand rather than with monkeypatch.undo(),
    which would also undo the fixture that keeps this test off the network.
    """
    p = projects.path_of(project)
    beats = parse("A line nobody has spoken before now.")["beats"]
    working = engine._fake_voice
    monkeypatch.setattr(engine, "_fake_voice",
                        lambda text, path: path.write_bytes(b""))
    with pytest.raises(engine.RenderError):
        engine.render_video(p, beats, THEMES["cream"])
    monkeypatch.setattr(engine, "_fake_voice", working)
    r = engine.render_video(p, beats, THEMES["cream"])
    assert r["video"].exists()
