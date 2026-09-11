import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import projects
from app.main import app
from app.script_parser import parse


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


def test_first_project_is_seeded_with_the_example(client):
    """A new user must be able to press Generate without writing a script."""
    import shutil
    from app.script_parser import parse
    try:
        r = client.post("/projects", data={"name": "seeded demo", "example": "1"},
                        follow_redirects=False)
        assert r.status_code == 303
        text = projects.script("seeded-demo")
        assert text.strip(), "the first project should open with a script in it"
        assert parse(text)["warnings"] == []
    finally:
        shutil.rmtree(projects.path_of("seeded-demo"), ignore_errors=True)


def test_project_without_example_starts_blank(client):
    import shutil
    try:
        client.post("/projects", data={"name": "blank one"},
                    follow_redirects=False)
        assert projects.script("blank-one") == ""
    finally:
        shutil.rmtree(projects.path_of("blank-one"), ignore_errors=True)


def test_empty_state_explains_projects_and_offers_the_example(client, tmp_path,
                                                              monkeypatch):
    """With no projects yet, the page has to do the explaining itself."""
    empty = tmp_path / "projects"
    empty.mkdir()
    monkeypatch.setattr(projects, "PROJECTS_DIR", empty)
    body = client.get("/").text
    assert "project" in body.lower()
    assert 'name="example"' in body, "the first-run form should seed the example"


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


def test_voice_picker_is_on_the_page(client, project):
    from app import voices
    body = client.get(f"/p/{project}").text
    assert "Voice" in body
    for vid, name, _accent, _gender in voices.VOICES:
        assert vid in body, f"{name} missing from the picker"
    for value, label in voices.RATES:
        assert label in body


def test_voice_and_rate_persist(client, project):
    from app import voices
    other = voices.VOICE_IDS[1]
    r = client.post(f"/p/{project}/voice",
                    data={"voice": other, "rate": "+10%"})
    assert r.status_code == 200
    cfg = projects.settings(project)
    assert cfg["voice"] == other and cfg["rate"] == "+10%"
    # and the page comes back with it selected
    assert f'value="{other}" selected' in client.get(f"/p/{project}").text


def test_unknown_voice_is_refused_not_stored(client, project):
    r = client.post(f"/p/{project}/voice",
                    data={"voice": "en-XX-NopeNeural", "rate": "wrong"})
    assert r.status_code == 200
    cfg = projects.settings(project)
    from app import voices
    assert cfg["voice"] == voices.DEFAULT_VOICE
    assert cfg["rate"] == voices.DEFAULT_RATE


def test_changing_rate_changes_the_runtime_estimate(client, project):
    script = "Some narration with a reasonable number of words in it here."
    client.post(f"/p/{project}/voice", data={"voice": projects.DEFAULTS["voice"],
                                             "rate": "-18%"})
    slow = client.post(f"/p/{project}/script", json={"script": script}).json()
    client.post(f"/p/{project}/voice", data={"voice": projects.DEFAULTS["voice"],
                                             "rate": "+10%"})
    fast = client.post(f"/p/{project}/script", json={"script": script}).json()
    assert slow["seconds"] > fast["seconds"]


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


# ----------------------------------------------------------------------
# the review panel
# ----------------------------------------------------------------------
NOTEY = ('[Scene 1 - a desk]\n0:00 - 0:15\n// re-record\n'
         'Saving money is simple but not easy.\n')


def test_the_analysis_reports_what_will_not_be_spoken(project):
    client = TestClient(app)
    a = client.post(f"/p/{project}/script", json={"script": NOTEY}).json()
    assert [s["text"] for s in a["skipped"]] == \
        ["[Scene 1 - a desk]", "0:00 - 0:15", "// re-record"]
    assert [s["kind"] for s in a["skipped"]] == ["note", "marker", "note"]
    assert a["kept"] == []


def test_putting_a_line_back_survives_a_reload(project):
    """The choice lives with the project, not in the page, or it is lost the
    moment the user closes the tab."""
    client = TestClient(app)
    client.post(f"/p/{project}/script", json={"script": NOTEY})
    a = client.post(f"/p/{project}/keep",
                    json={"text": "0:00 - 0:15", "keep": True}).json()
    assert [k["text"] for k in a["kept"]] == ["0:00 - 0:15"]
    assert "0:00 - 0:15" not in [s["text"] for s in a["skipped"]]

    # a fresh analysis, as a reload would do
    b = client.post(f"/p/{project}/script", json={"script": NOTEY}).json()
    assert [k["text"] for k in b["kept"]] == ["0:00 - 0:15"]

    c = client.post(f"/p/{project}/keep",
                    json={"text": "0:00 - 0:15", "keep": False}).json()
    assert c["kept"] == []
    assert "0:00 - 0:15" in [s["text"] for s in c["skipped"]]


def test_a_line_put_back_reaches_the_render(project):
    client = TestClient(app)
    client.post(f"/p/{project}/script", json={"script": NOTEY})
    client.post(f"/p/{project}/keep", json={"text": "0:00 - 0:15", "keep": True})
    cfg = projects.settings(project)
    beats = parse(projects.script(project), keep=cfg["keep"])["beats"]
    assert any("0:00" in b["say"] for b in beats)


def test_putting_back_a_line_that_is_not_there_is_harmless(project):
    client = TestClient(app)
    client.post(f"/p/{project}/script", json={"script": NOTEY})
    a = client.post(f"/p/{project}/keep",
                    json={"text": "nothing like this in the script",
                          "keep": True}).json()
    assert a["kept"] == []
    assert client.post(f"/p/{project}/keep", json={"text": "  "}).status_code == 400


def test_the_look_controls_save_and_a_template_choice_clears_them(client, project):
    """Picking a template has to clear the overrides: the light and lettering
    it ships with are part of what was just chosen."""
    client.post(f"/p/{project}/look", data={
        "light": "spot", "lettering": "slab", "dressing": "cat"})
    cfg = projects.settings(project)
    assert (cfg["light"], cfg["lettering"], cfg["dressing"]) == \
        ("spot", "slab", "cat")

    client.post(f"/p/{project}/theme", data={"theme": "mustard"})
    cfg = projects.settings(project)
    assert cfg["theme"] == "mustard"
    assert (cfg["light"], cfg["lettering"], cfg["dressing"]) == ("", "", "")


def test_a_made_up_look_is_dropped(client, project):
    client.post(f"/p/{project}/look", data={
        "light": "disco", "lettering": "x", "dressing": "dragon"})
    cfg = projects.settings(project)
    assert (cfg["light"], cfg["lettering"], cfg["dressing"]) == ("", "", "")


def test_a_template_preview_is_drawn_once_and_reused(client, tmp_path,
                                                     monkeypatch):
    """A template is the one setting nobody can judge from a name and three
    colour dots, so the picker shows a real still. Drawing one costs about a
    second, so it has to be cached, and keyed on the template itself rather
    than on its name: a change to a ground has to show without anything to
    invalidate by hand."""
    from app import main
    monkeypatch.setattr(main, "PREVIEW_DIR", tmp_path / "previews")
    assert client.get("/template/coral.png").status_code == 200
    made = sorted((tmp_path / "previews").glob("*.png"))
    assert len(made) == 1
    stamp = made[0].stat().st_mtime_ns

    assert client.get("/template/coral.png").status_code == 200
    assert made[0].stat().st_mtime_ns == stamp, "drew it a second time"

    # a different light is a different template and a different file
    assert client.get("/template/coral.png?light=spot").status_code == 200
    assert len(sorted((tmp_path / "previews").glob("*.png"))) == 2


def test_an_unknown_template_preview_is_not_found(client):
    assert client.get("/template/nope.png").status_code == 404
