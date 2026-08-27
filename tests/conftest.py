import shutil
import uuid

import pytest

from app import projects


@pytest.fixture(autouse=True)
def fake_tts(monkeypatch):
    # tests must pass with no network; the engine swaps in tone audio the
    # length the real line would be
    monkeypatch.setenv("STV_FAKE_TTS", "1")


@pytest.fixture
def project():
    name = f"test-{uuid.uuid4().hex[:8]}"
    path = projects.create(name)
    yield name
    shutil.rmtree(path, ignore_errors=True)
