"""A real render of a two-beat script, through the engine and the routes.

Voice audio is the engine's offline stand-in (see STV_FAKE_TTS in
conftest), so the test needs ffmpeg but not the network.
"""

import time

from fastapi.testclient import TestClient

from app import engine, projects
from app.main import app
from app.script_parser import parse
from app.themes import THEMES

SCRIPT = """# Two beat test

> character: happy, cheer
> caption: It renders

Hello there, this is the first beat of the test video.
"""


def test_engine_renders_and_caches(project):
    p = projects.path_of(project)
    beats = parse(SCRIPT)["beats"]
    assert len(beats) == 2

    stages = []
    r = engine.render_video(p, beats, THEMES["cream"],
                            progress=lambda s, d, t: stages.append(s))
    assert r["video"].exists() and r["srt"].exists()
    assert set(stages) == {"voice", "slides", "segments", "final"}
    assert abs(engine.duration(r["video"]) - r["seconds"]) < 1.5

    # the estimate the page shows must be within 10% of the finished video
    est = engine.estimate_seconds(beats)
    assert abs(est - r["seconds"]) / r["seconds"] < 0.10

    plan = engine.plan(p, beats, THEMES["cream"])
    assert plan["voices_cached"] == 2 and plan["segments_cached"] == 2

    # a theme change keeps every voice line but no segment
    plan = engine.plan(p, beats, THEMES["mint"])
    assert plan["voices_cached"] == 2 and plan["segments_cached"] == 0

    # editing one line invalidates exactly one voice and one segment
    edited = [dict(beats[0]), {**beats[1], "say": "A different line now."}]
    plan = engine.plan(p, edited, THEMES["cream"])
    assert plan["voices_cached"] == 1 and plan["segments_cached"] == 1

    srt = r["srt"].read_text()
    assert srt.startswith("1\n00:00:00,350")


def test_generate_route_end_to_end(project):
    client = TestClient(app)
    r = client.post(f"/p/{project}/generate", json={"script": SCRIPT})
    assert r.json().get("ok")

    for _ in range(300):
        s = client.get(f"/p/{project}/status").json()
        if s["state"] in ("done", "error"):
            break
        time.sleep(1)
    assert s["state"] == "done", s
    assert client.get(f"/files/{project}/out/final.mp4").status_code == 200
    assert client.get(f"/files/{project}/out/final.srt").status_code == 200
