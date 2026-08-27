import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import projects
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_home_lists_projects(client, project):
    r = client.get("/")
    assert r.status_code == 200
    assert project in r.text


def test_create_project_redirects(client):
    r = client.post("/projects", data={"name": "Route Test 99"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/p/route-test-99"
    import shutil
    shutil.rmtree(projects.path_of("route-test-99"), ignore_errors=True)


def test_create_project_needs_a_name(client):
    r = client.post("/projects", data={"name": "!!!"})
    assert r.status_code == 400
    assert "name" in r.json()["error"]


def test_unknown_project_redirects_home(client):
    r = client.get("/p/does-not-exist", follow_redirects=False)
    assert r.status_code == 303


def test_script_analysis(client, project):
    r = client.post(f"/p/{project}/script",
                    json={"script": "# Chapter\n\n> wat\n\nHello world."})
    a = r.json()
    assert a["words"] == 3   # the chapter title is spoken, plus two words
    assert "about" in a["estimate"]
    assert any("wat" in w for w in a["warnings"])
    assert projects.script(project).startswith("# Chapter")


def test_theme_persists_and_page_uses_it(client, project):
    r = client.post(f"/p/{project}/theme", data={"theme": "sky"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert projects.settings(project)["theme"] == "sky"
    assert "#eaf4fb" in client.get(f"/p/{project}").text


def test_logo_upload_and_reject(client, project):
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), "#123456").save(buf, "PNG")
    r = client.post(f"/p/{project}/logo",
                    files={"file": ("brand.PNG", buf.getvalue(), "image/png")})
    a = r.json()
    assert "logo.png" in a["message"]
    assert client.get(a["preview"]).status_code == 200
    assert (projects.path_of(project) / "logo.png").exists()

    r = client.post(f"/p/{project}/logo",
                    files={"file": ("doc.pdf", b"%PDF", "application/pdf")})
    assert r.status_code == 400
    err = r.json()["error"]
    assert ".pdf" in err and ".png" in err and "Traceback" not in err

    client.post(f"/p/{project}/logo/remove")
    assert not (projects.path_of(project) / "logo.png").exists()


def test_music_from_library_and_remove(client, project):
    page = client.get(f"/p/{project}").text
    assert "starter" in page.lower()
    r = client.post(f"/p/{project}/music/library",
                    data={"track": "gentle-keys.mp3"})
    assert "music.mp3" in r.json()["message"]
    assert (projects.path_of(project) / "music.mp3").exists()
    client.post(f"/p/{project}/music/remove")
    assert not (projects.path_of(project) / "music.mp3").exists()


def test_music_url_validation(client, project):
    r = client.post(f"/p/{project}/music/url", data={"url": "not a link"})
    assert r.status_code == 400
    r = client.post(f"/p/{project}/music/url",
                    data={"url": "https://youtube.com/watch?v=x"})
    assert r.status_code == 400
    assert "YouTube" in r.json()["error"]


def test_music_upload_rejects_wrong_type(client, project):
    r = client.post(f"/p/{project}/music/upload",
                    files={"file": ("song.flac", b"x", "audio/flac")})
    assert r.status_code == 400
    assert ".flac" in r.json()["error"]


def test_generate_rejects_empty_script(client, project):
    r = client.post(f"/p/{project}/generate", json={"script": ""})
    assert r.status_code == 400
    assert "empty" in r.json()["error"]


def test_duplicate_route(client, project):
    r = client.post(f"/p/{project}/duplicate",
                    data={"new_name": project + " copy"},
                    follow_redirects=False)
    assert r.status_code == 303
    import shutil
    shutil.rmtree(projects.path_of(project + "-copy"), ignore_errors=True)
