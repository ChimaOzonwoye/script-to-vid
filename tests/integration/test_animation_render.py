"""A real render of an animated beat, checked frame by frame.

A unit test can show the sprites differ. Only pulling frames back out of the
encoded segment shows they survived the filter chain: the zoom filter holds
one input frame for the length of the clip unless it is told otherwise, which
throws the animation away without failing anything.
"""

import numpy as np
from PIL import Image

from app import animate, engine, projects
from app.script_parser import parse
from app.themes import THEMES

SCRIPT = """> character: happy, cheer
> caption: It moves

Hello there, this is a line long enough to open and close a mouth a few times.
"""


def frames_of(video, tmp_path, n=40):
    out = tmp_path / "px"
    out.mkdir(exist_ok=True)
    engine.run(["ffmpeg", "-v", "error", "-i", str(video), "-frames:v", str(n),
                "-f", "image2", str(out / "f%03d.png")])
    return [np.asarray(Image.open(q).convert("L"), dtype=float)
            for q in sorted(out.glob("*.png"))]


def mouth_box(beat, tmp_path):
    """Where the mouth lands, taken from the sprites rather than guessed, so
    a change to the framing or the head size cannot quietly aim this test at
    an empty patch of background."""
    shut, open_ = tmp_path / "shut.png", tmp_path / "open.png"
    engine.render_slide(beat, shut, THEMES["cream"], "open", "closed")
    engine.render_slide(beat, open_, THEMES["cream"], "open", "open")
    d = np.abs(np.asarray(Image.open(shut).convert("L"), dtype=float)
               - np.asarray(Image.open(open_).convert("L"), dtype=float)) > 8
    ys, xs = np.where(d)
    return ys.min() - 12, ys.max() + 12, xs.min() - 12, xs.max() + 12


def test_the_mouth_moves_in_the_encoded_segment(project, tmp_path):
    """Measured as ink inside the mouth, not as pixels that changed: the slow
    zoom shifts every outline in the frame by a fraction of a pixel, which is
    enough to make a "something changed here" test pass on a frozen clip.
    An open mouth is a solid block, so it shows up as area instead.
    """
    p = projects.path_of(project)
    beats = parse(SCRIPT)["beats"]
    box = mouth_box(beats[0], tmp_path)
    engine.render_video(p, beats, THEMES["cream"])

    seg = next((p / "cache" / "segments").glob("*.mp4"))
    # the fade in is still running over the first frames, which darkens
    # everything, so the count starts after it
    fs = frames_of(seg, tmp_path)[int(engine.FADE * engine.FPS) + 3:]
    assert len(fs) >= 15

    y0, y1, x0, x1 = box
    ink = [int((f[y0:y1, x0:x1] < 100).sum()) for f in fs]
    spread = max(ink) - min(ink)
    # a still clip of the same beat moves this by about 35, an animated one
    # by nearly 2000
    assert spread > 500, f"the mouth is not moving (ink spread {spread})"


def test_a_beat_with_no_character_stays_a_still(project, tmp_path):
    p = projects.path_of(project)
    beats = parse("# A chapter heading")["beats"]
    assert not engine.animated(beats[0])
    engine.render_video(p, beats, THEMES["cream"])
    assert not list((p / "cache" / "variants").glob("*.png"))


def test_rewording_a_line_reuses_the_drawing_but_not_the_mouth(project):
    """The sprites do not depend on the words, the mouth track does. Keyed
    the other way round, a rebuilt beat lip syncs to the old wording."""
    p = projects.path_of(project)
    beats = parse(SCRIPT)["beats"]
    engine.render_video(p, beats, THEMES["cream"])
    before = {q.name for q in (p / "cache" / "variants").glob("*.png")}
    tracks = {q.name for q in (p / "cache" / "mouth").glob("*.json")}

    edited = [{**beats[0], "say": "A completely different line of narration."}]
    engine.render_video(p, edited, THEMES["cream"])
    after = {q.name for q in (p / "cache" / "variants").glob("*.png")}
    assert after == before, "the sprites were redrawn for a wording change"
    assert (p / "cache" / "mouth").glob("*.json")
    assert {q.name for q in (p / "cache" / "mouth").glob("*.json")} > tracks


def test_editing_one_line_moves_only_that_beat_s_mouth_track(project):
    p = projects.path_of(project)
    two = parse(SCRIPT + "\n> character: neutral, offer\n> caption: Second\n\n"
                "And here is the second line of the script, also long enough.\n")
    beats = two["beats"]
    assert len(beats) == 2
    engine.render_video(p, beats, THEMES["cream"])

    vdir = p / "cache" / "voice"
    keys = [engine.voice_key(b["say"], engine.VOICE, engine.RATE) for b in beats]
    before = [animate.track_key(vdir / f"{k}.mp3", engine.FPS) for k in keys]

    edited = [beats[0], {**beats[1], "say": "The second line, now rewritten."}]
    engine.render_video(p, edited, THEMES["cream"])
    keys = [engine.voice_key(b["say"], engine.VOICE, engine.RATE) for b in edited]
    after = [animate.track_key(vdir / f"{k}.mp3", engine.FPS) for k in keys]

    assert after[0] == before[0], "an untouched beat's mouth track changed"
    assert after[1] != before[1], "an edited beat kept the old mouth track"
