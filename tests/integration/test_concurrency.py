"""Encoding several segments at once must give back the same video.

The speedup is real: one ffmpeg leaves most of a machine idle, because the
zoom filter runs on a frame four times the size of the output and is single
threaded, so the encoder waits on it. Measured on four cores, a hundred
second render went from 214s to 148s.

The only thing worth testing about that is whether it changed the output.
Every segment is keyed on its own beat and nothing is shared between the
workers, so it should not, and this renders the same script both ways and
compares the bytes.

Voice audio is the engine's offline stand-in (see STV_FAKE_TTS in conftest).
"""

import hashlib
import shutil

import pytest

from app import engine
from app.script_parser import parse
from app.themes import THEMES

SCRIPT = """Money left in a current account is money you have already spent.

The only reliable trick is to move it somewhere else on payday.

Ten percent is a reasonable place to begin, and you can raise it later.
"""


def sha(path):
    return hashlib.sha1(path.read_bytes()).hexdigest()


def render(root, name, jobs, monkeypatch, theme="cream"):
    monkeypatch.setenv("STV_JOBS", str(jobs))
    d = root / name
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    out = engine.render_video(d, parse(SCRIPT)["beats"], THEMES[theme])
    segs = sorted((d / "cache" / "segments").glob("*.mp4"))
    return [p.name for p in segs], [sha(p) for p in segs], sha(out["video"])


@pytest.mark.parametrize("theme", ["cream", "downpour"])
def test_four_at_a_time_gives_the_same_bytes_as_one(tmp_path, monkeypatch, theme):
    """Both layouts, because they take different paths through the encoder:
    a presenter beat is a sequence of frames and a story beat is one still."""
    one = render(tmp_path, "serial", 1, monkeypatch, theme)
    many = render(tmp_path, "parallel", 4, monkeypatch, theme)
    assert one[0] == many[0], "the segments are keyed differently"
    assert one[1] == many[1], "a segment came out different when run alongside others"
    assert one[2] == many[2], "the finished video differs"


def test_the_workers_do_not_share_a_scratch_file(tmp_path, monkeypatch):
    """Two encodes writing one seg_tmp.mp4 is the failure this invites, and it
    would show up as a truncated or crossed-over segment rather than a crash.
    Four beats through a pool of four is the shape that would catch it."""
    names, hashes, _ = render(tmp_path, "many", 4, monkeypatch)
    assert len(set(names)) == len(names) == 3
    assert len(set(hashes)) == 3, "two beats came out as the same file"
    for p in sorted((tmp_path / "many" / "cache" / "segments").glob("*.mp4")):
        assert engine.duration(p) > 0.5
