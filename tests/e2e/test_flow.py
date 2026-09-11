"""Drives a real browser from paste to download against a live server."""

import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import uuid

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from app import projects  # noqa: E402

SCRIPT = """# Browser test

> character: happy, cheer
> caption: From the browser

This video was made entirely from the browser, start to finish.
"""


@pytest.fixture(scope="module")
def server():
    port = 8777
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**os.environ, "STV_FAKE_TTS": "1"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(port)],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            urllib.request.urlopen(base, timeout=1)
            break
        except OSError:
            time.sleep(0.5)
    else:
        proc.terminate()
        pytest.fail("server did not start")
    yield base
    proc.terminate()
    proc.wait(timeout=10)


def test_paste_to_download(server):
    name = f"e2e-{uuid.uuid4().hex[:8]}"
    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=os.environ.get("CHROMIUM_PATH") or None)
        page = browser.new_page()
        page.goto(server)

        page.fill('input[name="name"]', name)
        page.click('button:has-text("Create")')
        page.wait_for_url(f"**/p/{name}")

        page.fill("#script", SCRIPT)
        page.wait_for_selector("#script-info:has-text('words')")

        # the theme swatch is a form, so clicking it reloads the page. The
        # page is already at this URL, so waiting on the URL returns at once
        # and the next click races the navigation; wait for the navigation
        # itself instead.
        with page.expect_navigation():
            page.click('button[aria-label="Use the Sky template"]')
        page.wait_for_selector("#script-info:has-text('words')")
        assert "browser" in page.input_value("#script"), \
            "the script must survive the reload the theme click causes"

        page.click("#generate")
        page.wait_for_selector(
            ".progress:has-text('Done. Your video is ready below.')",
            timeout=300_000)

        video_url = page.get_attribute("#player", "src")
        assert "final.mp4" in video_url
        r = urllib.request.urlopen(server + video_url.replace(server, ""))
        assert r.status == 200 and int(r.headers["Content-Length"]) > 100_000

        srt = urllib.request.urlopen(server + f"/files/{name}/out/final.srt")
        assert b"-->" in srt.read()
        browser.close()
    shutil.rmtree(projects.path_of(name), ignore_errors=True)


NOTEY = """[Scene 1 - a desk]
0:00 - 0:15
// re-record this bit
Saving money is simple but not easy, and everyone knows it already.
"""


def test_the_review_panel_puts_a_line_back(server):
    """The panel is the whole answer to lines this cannot judge from the
    text, so it has to work in a browser, not just in the analysis."""
    name = f"e2e-review-{uuid.uuid4().hex[:8]}"
    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=os.environ.get("CHROMIUM_PATH") or None)
        page = browser.new_page()
        page.goto(server)
        page.fill("input[name=name]", name)
        with page.expect_navigation():
            page.click("button[type=submit]")

        page.fill("#script", NOTEY)
        page.wait_for_selector("#review:not([hidden])")
        assert "3 lines" in page.inner_text("#review-count")
        # the bare timecode is shown, the bracketed line and comment folded
        shown = page.eval_on_selector_all(
            "#review-list li .review-text", "e => e.map(x => x.textContent)")
        assert shown == ["0:00 - 0:15"]
        assert "2 bracketed" in page.inner_text("#review-notes-summary")

        page.locator("#review-list li").first.get_by_role("button").click()
        page.wait_for_selector("#review-kept:not([hidden])")
        assert "1 line you put back" in page.inner_text("#review-kept-head")

        page.reload()
        page.wait_for_selector("#review-kept:not([hidden])")
        assert "1 line you put back" in page.inner_text("#review-kept-head")

        page.locator("#review-kept li").first.get_by_role("button").click()
        # waiting on the element would time out: it is still attached, and
        # wait_for_selector wants it visible
        page.wait_for_function(
            "() => document.getElementById('review-kept').hidden")
        assert "3 lines" in page.inner_text("#review-count")
        browser.close()
    shutil.rmtree(projects.path_of(name), ignore_errors=True)


def test_the_shell_carries_the_way_back_and_the_action(server):
    """A form is a page you scroll; an app has a bar you can always reach.
    The way back used to be a text link, and Generate sat below a music
    library tall enough that you had to hunt for it.
    """
    name = f"e2e-shell-{uuid.uuid4().hex[:8]}"
    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=os.environ.get("CHROMIUM_PATH") or None)
        page = browser.new_page(viewport={"width": 1100, "height": 900})
        page.goto(server)
        page.fill("input[name=name]", name)
        with page.expect_navigation():
            page.click("button[type=submit]")

        # the bar stays put and names the project
        page.mouse.wheel(0, 1200)
        page.wait_for_timeout(300)
        assert page.locator(".appbar").is_visible()
        assert name in page.inner_text(".appbar-name")

        # each step says what it is set to, without opening it
        assert page.inner_text("#chip-voice").strip()
        assert page.inner_text("#chip-look").strip()

        # the action follows you, and stands down where the real one is
        assert page.locator("#actionbar").is_visible()
        page.locator("#generate").scroll_into_view_if_needed()
        page.wait_for_timeout(400)
        assert page.locator("#actionbar").is_hidden(), \
            "two of the same button on screen at once"

        # one shared player for the library, not a control on every row
        assert page.locator("ul.tracks audio").count() == 0
        assert page.locator(".playbtn").count() > 0

        with page.expect_navigation():
            page.click(".backbtn")
        assert page.url.rstrip("/").endswith(server.rstrip("/").split("/")[-1]) \
            or page.url.rstrip("/") == server.rstrip("/")
        browser.close()
    shutil.rmtree(projects.path_of(name), ignore_errors=True)


def test_the_margin_scene_stays_out_of_the_way(server):
    """The margins are set dressing. It has to be impossible for them to
    cover the column, catch a click, or appear on a screen with no margins
    to put them in."""
    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=os.environ.get("CHROMIUM_PATH") or None)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(server)
        page.wait_for_timeout(300)
        assert page.locator(".stage").is_visible()
        assert page.evaluate(
            "getComputedStyle(document.querySelector('.stage')).pointerEvents"
        ) == "none"

        card = page.locator("section.step").first.bounding_box()
        for side in (".stage-left", ".stage-right"):
            box = page.locator(side).bounding_box()
            assert box["x"] + box["width"] <= card["x"] + 1 \
                or box["x"] >= card["x"] + card["width"] - 1, \
                f"{side} runs under the column"

        # no margins, no scene
        page.set_viewport_size({"width": 1000, "height": 900})
        page.wait_for_timeout(200)
        assert page.locator(".stage").is_hidden()
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(200)
        assert page.locator(".stage").is_hidden()
        assert not page.evaluate(
            "document.documentElement.scrollWidth > window.innerWidth + 1")
        browser.close()
