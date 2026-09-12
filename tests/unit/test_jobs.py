"""Running the encodes several at a time has to change the clock and nothing
else.

One ffmpeg does not fill a machine: the zoom runs on a frame four times the
size of the output and that filter is single threaded, so the encoder spends
much of its time waiting on it. Measured on four cores, one ten second
segment took 12.0s alone and 3.2s each with four in flight. The risk in
taking that speedup is that concurrency changes what comes out, so these pin
the parts that make it safe.
"""
import os

import pytest

from app import engine


def test_the_pool_is_capped_at_the_cores_it_has(monkeypatch):
    monkeypatch.delenv("STV_JOBS", raising=False)
    monkeypatch.setattr(os, "cpu_count", lambda: 1)
    assert engine.workers() == 1
    monkeypatch.setattr(os, "cpu_count", lambda: 2)
    assert engine.workers() == 2
    # past four the measured curve is flat and the only cost is memory, since
    # every worker holds frames at four times the output size
    monkeypatch.setattr(os, "cpu_count", lambda: 32)
    assert engine.workers() == 4


def test_the_job_count_can_be_set_by_hand(monkeypatch):
    """A machine that is doing something else wants its cores back."""
    monkeypatch.setenv("STV_JOBS", "1")
    assert engine.workers() == 1
    monkeypatch.setenv("STV_JOBS", "8")
    assert engine.workers() == 8
    monkeypatch.setenv("STV_JOBS", "nonsense")
    assert engine.workers() >= 1


def test_every_job_runs_once_and_progress_counts_them_all():
    seen, counts = [], []
    engine.in_flight(seen.append, range(9), counts.append)
    assert sorted(seen) == list(range(9))
    # the pool reports as each one lands, so the numbers arrive in order even
    # though the work does not
    assert counts == list(range(1, 10))


def test_a_failing_job_is_not_swallowed():
    """A pool that eats exceptions turns a broken render into a silent one."""
    def boom(i):
        if i == 3:
            raise engine.RenderError("ffmpeg fell over")
    with pytest.raises(engine.RenderError):
        engine.in_flight(boom, range(8))


def test_nothing_two_workers_touch_is_named_the_same(tmp_path):
    """Every scratch file in the concurrent stages carries its own index.

    This is the bug the speedup would have introduced: two encodes writing
    one seg_tmp.mp4, or two parts writing one part.txt, and the second
    overwriting the first halfway through.
    """
    import inspect
    src = inspect.getsource(engine.render_video) + inspect.getsource(engine.encode_part)
    for name in ("seg_tmp", "part_tmp", "part_joined"):
        for line in src.splitlines():
            if name in line and "work /" in line:
                assert "f\"" in line and "{" in line, \
                    f"{name} is a fixed name and two workers would collide on it"
