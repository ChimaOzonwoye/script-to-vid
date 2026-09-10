"""What a render costs in scratch disk, and how that scales with length.

A 10 minute video was reported failing on an 8 GB machine near the final
output. Peak memory turns out to be flat with length, about 640 MB for the
final pass whatever the video, so memory is not what runs out. Scratch disk
was quadratic: the music bed looped by crossfading into a new full length
uncompressed file each pass and kept every one of them, which is 868 MB for
ten minutes against 115 MB of actual bed.
"""

import shutil
from pathlib import Path

import pytest

from app import engine

TRACK = Path(__file__).resolve().parents[2] / "assets" / "music" / "evening-walk.mp3"


def bed_cost(tmp_path, seconds):
    work = tmp_path / f"w{seconds}"
    work.mkdir()
    out = engine.build_music_bed(TRACK, work / "bed.wav", seconds, work)
    left = sum(f.stat().st_size for f in work.iterdir())
    return Path(out).stat().st_size, left


@pytest.mark.skipif(not TRACK.exists(), reason="no bundled music")
def test_the_music_bed_does_not_hoard_its_working_files(tmp_path):
    """Each loop pass writes another full length file. Keeping them all is
    what made a long video cost the square of its length in scratch."""
    final, left = bed_cost(tmp_path, 240)
    assert left <= final * 1.4, (
        f"{left} bytes of scratch for a {final} byte bed; the intermediate "
        "passes are being kept again")


@pytest.mark.skipif(not TRACK.exists(), reason="no bundled music")
def test_scratch_grows_with_length_not_with_its_square(tmp_path):
    _, short = bed_cost(tmp_path, 120)
    _, long_ = bed_cost(tmp_path, 480)
    # four times the video, so at most about four times the scratch. Squared
    # growth would be nearer sixteen
    assert long_ < short * 6, f"{short} -> {long_} bytes for 4x the length"


@pytest.mark.skipif(not TRACK.exists(), reason="no bundled music")
def test_a_track_longer_than_the_video_is_just_copied(tmp_path):
    work = tmp_path / "w"
    work.mkdir()
    out = engine.build_music_bed(TRACK, work / "bed.mp3", 10, work)
    assert Path(out).stat().st_size == TRACK.stat().st_size
