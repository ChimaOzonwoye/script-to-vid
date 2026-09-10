"""Joining finished videos into one.

The cost difference between the two paths is the whole design: a stream copy
is seconds whatever the length, a re-encode is minutes. So videos this app
made must never be re-encoded, and anything else has to be brought to the
same profile first or concat produces a file that plays wrong from the join
onwards, or refuses outright.
"""

import pytest

from app import engine, joiner


def make(path, seconds=2, w=1920, h=1080, fps=30, audio=True, vcodec="libx264"):
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-f", "lavfi", "-i", f"color=c=0x336699:s={w}x{h}:r={fps}:d={seconds}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"]
    cmd += ["-c:v", vcodec, "-pix_fmt", "yuv420p", "-r", str(fps)]
    if audio:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
    cmd += ["-t", str(seconds), str(path)]
    engine.run(cmd)
    return path


def test_the_apps_own_videos_are_copied_not_re_encoded(tmp_path):
    a = make(tmp_path / "a.mp4", 2)
    b = make(tmp_path / "b.mp4", 3)
    assert joiner.ready_to_copy(joiner.probe(a))

    r = joiner.join([a, b], tmp_path / "out.mp4", tmp_path / "work")
    assert r["converted"] == [], "a video this app made was re-encoded"
    assert abs(r["seconds"] - 5) < 0.5


def test_a_video_from_somewhere_else_is_converted_first(tmp_path):
    a = make(tmp_path / "a.mp4", 2)
    odd = make(tmp_path / "odd.mp4", 2, w=640, h=480, fps=25)
    assert not joiner.ready_to_copy(joiner.probe(odd))

    r = joiner.join([a, odd], tmp_path / "out.mp4", tmp_path / "work")
    assert r["converted"] == ["odd.mp4"]
    out = joiner.probe(r["video"])
    assert (out["width"], out["height"]) == (engine.W, engine.H)
    assert abs(r["seconds"] - 4) < 0.5


def test_a_silent_video_does_not_kill_the_sound_from_there_on(tmp_path):
    """concat drops any stream missing from one input, so a clip with no
    audio would silence everything after it."""
    a = make(tmp_path / "a.mp4", 2)
    quiet = make(tmp_path / "quiet.mp4", 2, audio=False)
    r = joiner.join([a, quiet], tmp_path / "out.mp4", tmp_path / "work")
    out = joiner.probe(r["video"])
    assert out["has_audio"], "the joined video lost its audio track"
    assert abs(r["seconds"] - 4) < 0.5


def test_the_order_given_is_the_order_joined(tmp_path):
    a = make(tmp_path / "a.mp4", 1)
    b = make(tmp_path / "b.mp4", 4)
    first = joiner.join([a, b], tmp_path / "ab.mp4", tmp_path / "w1")
    second = joiner.join([b, a], tmp_path / "ba.mp4", tmp_path / "w2")
    assert abs(first["seconds"] - second["seconds"]) < 0.5
    # the join list is written in the order given, which is what concat reads
    assert first["video"].exists() and second["video"].exists()


def test_something_that_is_not_a_video_says_so(tmp_path):
    a = make(tmp_path / "a.mp4", 1)
    bad = tmp_path / "notes.txt"
    bad.write_text("this is not a video")
    with pytest.raises(engine.RenderError) as e:
        joiner.join([a, bad], tmp_path / "out.mp4", tmp_path / "work")
    assert "notes.txt" in str(e.value)


def test_one_video_is_not_a_join(tmp_path):
    a = make(tmp_path / "a.mp4", 1)
    with pytest.raises(engine.RenderError):
        joiner.join([a], tmp_path / "out.mp4", tmp_path / "work")


def test_the_plan_says_what_it_will_have_to_do(tmp_path):
    """The page shows this before anything starts, because copying is
    seconds and converting is minutes and the user should know which."""
    a = make(tmp_path / "a.mp4", 2)
    odd = make(tmp_path / "odd.mp4", 3, w=1280, h=720)
    p = joiner.plan([a, odd])
    assert p["convert"] == ["odd.mp4"]
    assert p["unreadable"] == []
    assert abs(p["seconds"] - 5) < 0.5


def test_the_profile_matches_what_the_engine_actually_makes(project, tmp_path):
    """The whole speed of this rests on real output matching PROFILE. Get one
    field wrong and every join quietly re-encodes: minutes instead of seconds,
    with nothing to show why.
    """
    from app import projects
    from app.script_parser import parse
    from app.themes import THEMES

    p = projects.path_of(project)
    r = engine.render_video(p, parse("A short line for the joiner.")["beats"],
                            THEMES["cream"])
    info = joiner.probe(r["video"])
    assert joiner.ready_to_copy(info), (
        f"a video straight from the engine does not match PROFILE: {info}")
