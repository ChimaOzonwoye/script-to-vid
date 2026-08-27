"""The launcher run.sh and run.bat both start, is the path every user takes.

The e2e test starts uvicorn directly, which imports the app a different way,
so it did not notice when tools/serve.py could not import the app package at
all. This covers the real launch path.
"""

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_launcher_serves_a_page():
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "tools" / "serve.py")],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for _ in range(60):
            if proc.poll() is not None:
                raise AssertionError(
                    "the launcher exited instead of serving:\n"
                    + (proc.stdout.read() or "")[-2000:])
            for port in range(8000, 8020):
                try:
                    with urllib.request.urlopen(
                            f"http://127.0.0.1:{port}", timeout=1) as r:
                        assert r.status == 200
                        return
                except OSError:
                    continue
            time.sleep(0.5)
        raise AssertionError("the launcher never served a page")
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_launcher_binds_only_to_localhost():
    """Nothing on the network should be able to reach it."""
    src = (ROOT / "tools" / "serve.py").read_text()
    assert '"127.0.0.1"' in src
    assert "0.0.0.0" not in src
