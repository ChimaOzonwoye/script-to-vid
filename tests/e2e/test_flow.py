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
            page.click('button[aria-label="Use the Sky theme"]')
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
