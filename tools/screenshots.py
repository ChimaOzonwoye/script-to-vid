"""Retake the two screenshots the README shows.

    python tools/screenshots.py

Both are made the way a reader would see them, not mocked up: the page shot
comes from a real browser against a real server, and the still is pulled out
of a video this actually rendered. Run it after anything that changes the
look, or the README quietly starts describing an app that no longer exists.

Voice audio uses the engine's offline stand-in, so this needs no network.
"""

import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DOCS = ROOT / "docs"

# the still is rendered in this process, not by the server, so the stand-in
# has to be set here too or it goes looking for the network
os.environ.setdefault("STV_FAKE_TTS", "1")

# Long enough to fill the step index and show a real word count, short enough
# that the render is quick. The subject is deliberately not money, so the
# screenshots do not read as a tool for one topic.
SCRIPT = """Every recipe says to preheat the oven. Almost none of them say why.

A hot oven is not the same as an oven that has been on for ten minutes. The
air comes up to temperature long before the walls do.

Bread put into a cold-walled oven spreads before it sets. It comes out flat.
"""


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serve():
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(port)],
        env={**os.environ, "STV_FAKE_TTS": "1"},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            urllib.request.urlopen(base, timeout=1)
            return proc, base
        except OSError:
            time.sleep(0.5)
    proc.terminate()
    raise SystemExit("the server did not start")


def the_page(base, name):
    """The Look step, on the family the templates are actually about now."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=os.environ.get("CHROMIUM_PATH") or None)
        # a retina-ish shot, because the README renders it at half width
        page = browser.new_page(viewport={"width": 1600, "height": 1250},
                                device_scale_factor=2)
        page.goto(base)
        page.fill('input[name="name"]', name)
        page.click('button:has-text("Create")')
        page.wait_for_url(f"**/p/{name}")
        page.fill("#script", SCRIPT)
        page.wait_for_selector("#script-info:has-text('words')")
        # the picker opens on the family the current template is in, and that
        # is a presenter one, so the storytelling group is hidden until its
        # tab is picked
        page.click('.famtab[data-fam="story"]')
        page.wait_for_selector('#fam-story:not([hidden])')
        with page.expect_navigation():
            page.click('button[aria-label="Use the Downpour template"]')
        page.wait_for_selector("#script-info:has-text('words')")
        page.click('.famtab[data-fam="story"]')
        page.wait_for_selector('#fam-story:not([hidden])')
        # the shot is of the Look step. scrollIntoView puts its top at the
        # top of the viewport, which is underneath the sticky header, so back
        # off by more than the header is tall
        page.eval_on_selector(
            "#look",
            "e => window.scrollTo({top: e.getBoundingClientRect().top"
            " + window.scrollY - 96})")
        page.wait_for_timeout(900)      # the lazy previews and the scroll
        page.screenshot(path=str(DOCS / "the-page.png"))
        browser.close()


def a_still(tmp):
    """One frame out of a video this rendered, subtitle and weather included."""
    from app import engine, script_parser
    from app.themes import THEMES
    proj = tmp / "still"
    shutil.rmtree(proj, ignore_errors=True)
    proj.mkdir(parents=True)
    beats = script_parser.parse(SCRIPT)["beats"]
    T = THEMES["downpour"]
    out = engine.render_video(proj, beats, T)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{pick_moment(proj, beats, T):.3f}",
                    "-i", str(out["video"]), "-frames:v", "1",
                    str(DOCS / "a-still.png")], check=True)


def pick_moment(proj, beats, theme):
    """When to freeze it: the middle of a caption piece that is a whole
    sentence.

    Long sentences are split across pieces, so grabbing a fixed timestamp
    catches one mid-phrase as often as not, and a still of half a sentence
    reads as a bug in the subtitles rather than as the look.
    """
    from app import captions, engine
    from app.voices import DEFAULT_VOICE, DEFAULT_RATE
    vdir = proj / "cache" / "voice"
    clock = 0.0
    for b in engine._prepared([dict(x) for x in beats], proj, theme):
        key = engine.voice_key(b["say"], DEFAULT_VOICE, DEFAULT_RATE)
        spoken = engine.duration(vdir / f"{key}.mp3")
        pieces = b.get("rolling") or [b["say"]]
        for piece, (a, z) in zip(pieces,
                                 captions.timings(pieces, engine.LEAD_SILENCE, spoken)):
            if piece.strip().endswith((".", "!", "?")):
                return clock + (a + z) / 2
        clock += engine.LEAD_SILENCE + spoken + engine.BREATH
    return 2.0


def main():
    DOCS.mkdir(exist_ok=True)
    tmp = ROOT / ".screenshots"
    tmp.mkdir(exist_ok=True)
    # a real looking name, because it is printed in the header
    name = "preheat-the-oven"
    proc, base = serve()
    try:
        the_page(base, name)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            # uvicorn waits on its own workers and can outlast a TERM
            proc.kill()
            proc.wait(timeout=10)
    from app import projects
    shutil.rmtree(projects.path_of(name), ignore_errors=True)
    a_still(tmp)
    shutil.rmtree(tmp, ignore_errors=True)
    for f in ("the-page.png", "a-still.png"):
        print(f"docs/{f}  {(DOCS / f).stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
