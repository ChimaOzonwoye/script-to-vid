"""The final encode runs in parts, and the joins have to be inaudible.

The seam between two parts is a stream copy across a beat boundary, so the
picture is fine by construction. The music is not: a bed built per part would
fade down at the end of one and up at the start of the next, putting a hole in
the track at every join. These tests render the same script whole and split and
compare what comes out.

Voice audio is the engine's offline stand-in (see STV_FAKE_TTS in conftest).
"""

import shutil
import subprocess
import wave
from pathlib import Path

import pytest

from app import engine, projects
from app.script_parser import parse
from app.themes import THEMES

TRACK = Path(__file__).resolve().parents[2] / "assets" / "music" / "gentle-keys.mp3"

SCRIPT = """Money left in a current account is money you have already spent.

The only reliable trick is to move it somewhere else on payday.

Ten percent is a reasonable place to begin, and you can raise it later.

After three months of this you stop noticing that it ever left.
"""

WINDOW = 4000   # half a second at 8kHz


def loudness(video, tmp):
    """Loudness of the finished mix, half a second at a time."""
    wav = tmp / f"{video.parent.parent.name}.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video),
                    "-ac", "1", "-ar", "8000", "-f", "wav", str(wav)], check=True)
    with wave.open(str(wav)) as w:
        raw = w.readframes(w.getnframes())
    import array
    a = array.array("h")
    a.frombytes(raw[:len(raw) // 2 * 2])
    out = []
    for i in range(0, len(a) - WINDOW, WINDOW):
        chunk = a[i:i + WINDOW]
        out.append((sum(v * v for v in chunk) / WINDOW) ** 0.5)
    return out


def render(tmp_path, name, part_seconds, monkeypatch):
    d = tmp_path / name
    d.mkdir()
    shutil.copy(TRACK, d / "music.mp3")
    monkeypatch.setattr(engine, "PART_SECONDS", part_seconds)
    monkeypatch.setattr(engine, "PART_FLOOR", 1.0)
    return engine.render_video(d, parse(SCRIPT)["beats"], THEMES["cream"])


@pytest.mark.skipif(not TRACK.exists(), reason="no bundled music")
def test_splitting_the_final_encode_does_not_change_the_video(tmp_path, monkeypatch):
    """Same beats, same picture, whether it went out in one piece or four.

    Rendering in parts exists so a weak machine has something finished to show
    if it gives up part-way. It is only worth having if the result is the same
    video, so this pins the frame count rather than trusting the seam to look
    fine.
    """
    whole = render(tmp_path, "whole", 10_000.0, monkeypatch)
    split = render(tmp_path, "split", 12.0, monkeypatch)
    assert whole["parts"] == 1
    assert split["parts"] > 1, "the script was too short to split"
    frames = [subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0",
         str(r["video"])], capture_output=True, text=True).stdout.strip()
        for r in (whole, split)]
    assert frames[0] == frames[1], f"whole {frames[0]} frames, split {frames[1]}"


@pytest.mark.skipif(not TRACK.exists(), reason="no bundled music")
def test_the_music_does_not_dip_at_a_join(tmp_path, monkeypatch):
    """The failure this guards against is loud and local: fading each part
    drops the seam to near silence for about a second and a half while the
    unsplit render stays up around its normal level. Comparing the two
    loudness curves catches it wherever the seam happens to land, without the
    test needing to know the beat durations."""
    whole = loudness(render(tmp_path, "whole", 10_000.0, monkeypatch)["video"], tmp_path)
    split = loudness(render(tmp_path, "split", 12.0, monkeypatch)["video"], tmp_path)
    n = min(len(whole), len(split))
    worst = max((whole[i] - split[i], i) for i in range(n))
    # A faded seam measures around 90% quieter than the unsplit render; the
    # slack here is the second aac encode and half a frame of timing drift.
    assert worst[0] < 0.35 * whole[worst[1]], (
        f"the mix drops at {worst[1] / 2:.1f}s: "
        f"whole {whole[worst[1]]:.0f}, split {split[worst[1]]:.0f}")


@pytest.mark.skipif(not TRACK.exists(), reason="no bundled music")
def test_the_video_carries_a_subtitle_track(tmp_path, monkeypatch):
    """A sidecar .srt only helps somebody who knows to look for it. A track is
    the switch every player already has, which is what people mean when they
    say subtitles, and it stays switchable because the words are not burned
    into the picture."""
    r = render(tmp_path, "subs", 10_000.0, monkeypatch)
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=index,codec_type,codec_name:stream_tags=language",
         "-of", "csv=p=0", str(r["video"])],
        capture_output=True, text=True).stdout
    assert "subtitle" in out, out
    assert "mov_text" in out, out
    assert r["srt"].exists(), "the sidecar file should still be written too"


LONG = ("Mistake number two: missing the employer match. Many companies add "
        "money to your 401k when you contribute. A common example is fifty "
        "cents for every dollar you put in, up to six percent of your salary.")


def test_a_long_beat_does_not_run_its_caption_off_the_frame(tmp_path):
    """A paragraph set as one block at the bottom loses its last line off the
    edge of the picture. The pieces have to change through the beat, which is
    also what stops a story frame being one still image held for fifteen
    seconds."""
    import dataclasses
    from app import captions as cap
    from app.script_parser import parse
    from app.themes import THEMES

    beats = parse(LONG + "\n")["beats"]
    T = dataclasses.replace(THEMES["downpour"], effect="none")
    d = tmp_path / "long"
    d.mkdir()
    prepared = engine._prepared(beats, d, T)
    pieces = prepared[0].get("rolling")
    assert pieces and len(pieces) > 3, "a paragraph this long has to be split"
    assert " ".join(pieces) == " ".join(LONG.split())

    r = engine.render_video(d, beats, T)
    # sample across the beat: the bottom of the frame has to change, or the
    # caption is one static block again
    bottoms = []
    for at in (1.0, 5.0, 9.0, 13.0):
        out = tmp_path / f"f{at}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-ss", str(at),
                        "-i", str(r["video"]), "-frames:v", "1",
                        "-vf", "crop=iw:ih/5:0:ih*4/5,scale=160:-1",
                        str(out)], check=True)
        bottoms.append(out.read_bytes())
    assert len(set(bottoms)) >= 3, "the caption did not change through the beat"


def test_a_figureless_template_does_not_render_face_variants(tmp_path):
    """The template can take the cast away, and then there is no mouth to
    move. Without this the beat is drawn once per mouth and eye position for
    a face that is never there."""
    from app.script_parser import parse
    from app.themes import THEMES
    beat = parse("He read the letter twice.\n")["beats"][0]
    assert engine.animated(beat, THEMES["cream"]) is True
    assert engine.animated(beat, THEMES["downpour"]) is False
    assert engine.animated(beat, THEMES["album"]) is False
