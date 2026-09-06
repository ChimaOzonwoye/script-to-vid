"""Blinking and lip sync for the characters, driven by the narration audio.

A beat with a character is rendered as six sprites rather than one slide:
eyes open or shut, crossed with a mouth that is closed, half open or open.
ffmpeg assembles them into a frame sequence, so the cost is six matplotlib
draws per beat instead of one, not one draw per frame.
"""

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

SR = 16000                  # mono rate the loudness envelope is measured at

EYES = ("open", "closed")
MOUTHS = ("closed", "mid", "open")
VARIANTS = [(e, m) for e in EYES for m in MOUTHS]


def mouth_track(audio_path, fps, quiet=0.08, loud=0.35):
    """Per-frame mouth state from narration loudness: closed, mid or open.

    Three fixed shapes, not a mouth scaled by amplitude. A continuously
    scaled mouth reads as a rubber band; discrete shapes read as speech.
    """
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(audio_path),
         "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
        capture_output=True).stdout
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    n = int(len(a) / SR * fps)
    if n < 1:
        return ["closed"]
    edges = (np.arange(n + 1) * SR / fps).astype(int)
    env = np.array([np.abs(a[i:j]).mean() for i, j in zip(edges, edges[1:])])
    env = env / max(env.max(), 1e-6)
    return ["closed" if v < quiet else "mid" if v < loud else "open" for v in env]


def blink_frames(n, fps, seed, low=2.6, high=5.0, hold=3):
    """Frame indices where the eyes are shut.

    Intervals are random because evenly spaced blinks look mechanical, and
    seeded so a line blinks the same way every time it is rendered.
    """
    rng = np.random.default_rng(seed)
    out, t = set(), 0.0
    while True:
        t += rng.uniform(low, high)
        f = int(t * fps)
        if f >= n:
            return out
        out.update(range(f, min(f + hold, n)))


def frame_list(mouths, blinks, variant_path, dest, fps):
    """Write an ffmpeg concat list, one entry per frame."""
    with open(dest, "w") as f:
        for i, m in enumerate(mouths):
            e = "closed" if i in blinks else "open"
            f.write(f"file '{variant_path(e, m)}'\nduration {1 / fps:.5f}\n")
        # the demuxer ignores the last duration, so the final frame is repeated
        f.write(f"file '{variant_path('open', mouths[-1])}'\n")


def track_key(audio_path, fps):
    """Keyed on the audio bytes, so a mouth track can never survive an edit
    to the line it was measured from."""
    h = hashlib.sha1(Path(audio_path).read_bytes()).hexdigest()
    return hashlib.sha1(f"{h}\x1f{fps}".encode()).hexdigest()


def cached_track(audio_path, fps, cache_dir):
    p = Path(cache_dir) / f"{track_key(audio_path, fps)}.json"
    if p.exists():
        return json.loads(p.read_text())
    track = mouth_track(audio_path, fps)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(track))
    return track
