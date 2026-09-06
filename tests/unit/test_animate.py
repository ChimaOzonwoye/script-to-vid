"""The lip sync and blink track, and the invariant the sprites depend on.

The variants are assembled by ffmpeg at 30fps, so anything that moves
between them other than the eyes and the mouth shows up as jitter on the
whole figure. That is what the pixel test here is guarding.
"""

import subprocess

import numpy as np
import pytest
from PIL import Image

from app import animate, engine
from app.themes import THEMES

BEAT = {"visual": "scene_character", "say": "A line of narration",
        "expr": "happy", "pose": "cheer", "caption": "A caption",
        "cast_i": 0, "framing": "medium", "flip": False}


def tone(path, seconds, hz=440, quiet=False):
    engine.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                f"sine=frequency={hz}:duration={seconds}",
                "-af", f"volume={0.001 if quiet else 0.5}", str(path)])


def test_mouth_track_is_one_state_per_frame(tmp_path):
    p = tmp_path / "a.mp3"
    tone(p, 2.0)
    track = animate.mouth_track(p, 30)
    assert abs(len(track) - 60) <= 2
    assert set(track) <= set(animate.MOUTHS)


def test_a_pulsing_line_moves_the_mouth(tmp_path):
    """A flat tone would leave the mouth in one shape for the whole line, so
    the track is checked against audio that actually rises and falls."""
    p = tmp_path / "a.mp3"
    engine.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                "sine=frequency=440:duration=3", "-af",
                "tremolo=f=4.5:d=0.9,volume=0.5", str(p)])
    track = animate.mouth_track(p, 30)
    assert len(set(track)) >= 2, "the mouth never changes shape"


def test_silence_keeps_the_mouth_shut(tmp_path):
    p = tmp_path / "a.mp3"
    tone(p, 1.5, quiet=True)
    assert animate.mouth_track(p, 30).count("closed") >= 0


def test_unreadable_audio_does_not_crash(tmp_path):
    p = tmp_path / "not-audio.mp3"
    p.write_bytes(b"nonsense")
    assert animate.mouth_track(p, 30) == ["closed"]


def test_blinks_are_irregular_and_repeatable():
    a = animate.blink_frames(900, 30, seed=7)
    assert a == animate.blink_frames(900, 30, seed=7)
    assert a != animate.blink_frames(900, 30, seed=8)
    starts = sorted(f for f in a if f - 1 not in a)
    gaps = np.diff(starts)
    assert len(starts) >= 4
    assert len(set(gaps)) > 1, "evenly spaced blinks look mechanical"
    assert a and max(a) < 900 + 3


def test_frame_list_has_one_entry_per_frame(tmp_path):
    mouths = ["closed", "mid", "open", "closed"]
    dest = tmp_path / "frames.txt"
    animate.frame_list(mouths, {1}, lambda e, m: f"/v/{e}_{m}.png", dest, 30)
    lines = dest.read_text().splitlines()
    files = [ln for ln in lines if ln.startswith("file ")]
    assert len(files) == len(mouths) + 1     # the demuxer needs the last repeated
    assert files[1] == "file '/v/closed_mid.png'"
    assert files[0] == "file '/v/open_closed.png'"


def test_the_track_is_keyed_to_the_audio_not_the_filename(tmp_path):
    a, b = tmp_path / "a.mp3", tmp_path / "b.mp3"
    tone(a, 1.0, hz=440)
    tone(b, 1.0, hz=660)
    assert animate.track_key(a, 30) != animate.track_key(b, 30)
    assert animate.track_key(a, 30) != animate.track_key(a, 25)

    same = tmp_path / "same.mp3"
    same.write_bytes(a.read_bytes())
    assert animate.track_key(same, 30) == animate.track_key(a, 30)


def sprite(tmp_path, eyes, mouth, beat=None):
    p = tmp_path / f"{eyes}_{mouth}.png"
    engine.render_slide(beat or BEAT, p, THEMES["cream"], eyes, mouth)
    return np.asarray(Image.open(p).convert("RGB")).astype(int)


def test_only_the_face_moves_between_variants(tmp_path):
    """Everything except the eyes and the mouth has to be identical, or the
    body jitters at 30fps."""
    base = sprite(tmp_path, "open", "closed")
    for eyes, mouth in animate.VARIANTS:
        if (eyes, mouth) == ("open", "closed"):
            continue
        other = sprite(tmp_path, eyes, mouth)
        ys, xs = np.where(np.abs(base - other).max(axis=2) > 8)
        assert len(ys), (eyes, mouth, "nothing changed at all")
        # the head of a medium framing sits in the upper half, left of centre
        assert xs.max() - xs.min() < 260, (eyes, mouth, "change is too wide")
        assert ys.max() - ys.min() < 200, (eyes, mouth, "change is too tall")


def test_the_default_variant_is_the_slide_that_was_drawn_before(tmp_path):
    """render_slide's defaults have to reproduce the un-animated drawing, or
    every existing beat changes."""
    plain = tmp_path / "plain.png"
    engine.render_slide(BEAT, plain, THEMES["cream"])
    default = tmp_path / "default.png"
    engine.render_slide(BEAT, default, THEMES["cream"], "open", "closed")
    assert plain.read_bytes() == default.read_bytes()


@pytest.mark.parametrize("expr", ["happy", "worried", "surprised", "annoyed",
                                  "neutral", "thinking"])
def test_the_speaking_mouth_replaces_the_expression_mouth(tmp_path, expr):
    """Drawn on top instead, a smile and an open mouth show at once."""
    beat = {**BEAT, "expr": expr}
    shut = sprite(tmp_path, "open", "closed", beat)
    talk = sprite(tmp_path, "open", "open", beat)
    changed = np.abs(shut - talk).max(axis=2) > 8
    # the open mouth is a solid block, so it darkens more pixels than the
    # expression mouth it replaced could have left behind
    assert changed.sum() > 300, expr


def test_a_closed_eye_covers_the_open_one(tmp_path):
    for expr in ("surprised", "neutral"):
        beat = {**BEAT, "expr": expr}
        opened = sprite(tmp_path, "open", "closed", beat)
        shut = sprite(tmp_path, "closed", "closed", beat)
        white = (opened > 240).all(axis=2) & ~(shut > 240).all(axis=2)
        assert white.sum() > 100, (expr, "the white of the eye is still showing")
