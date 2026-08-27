import pytest

from app import projects


def test_slugify():
    assert projects.slugify("My First Video!") == "my-first-video"
    assert projects.slugify("  ..  ") == ""
    assert projects.slugify("a" * 100) == "a" * 60


def test_path_never_escapes_projects_dir():
    p = projects.path_of("../../etc/passwd")
    assert projects.PROJECTS_DIR in p.parents


def test_create_list_settings(project):
    assert projects.exists(project)
    assert any(p["name"] == project for p in projects.list_projects())
    cfg = projects.settings(project)
    assert cfg["theme"] == "cream"
    projects.save_settings(project, {"theme": "sky"})
    assert projects.settings(project)["theme"] == "sky"


def test_script_roundtrip(project):
    assert projects.script(project) == ""
    projects.save_script(project, "hello")
    assert projects.script(project) == "hello"


def test_duplicate_copies_settings_not_output(project):
    projects.save_script(project, "text")
    projects.save_settings(project, {"theme": "mint"})
    src = projects.path_of(project)
    (src / "out").mkdir()
    (src / "out" / "final.mp4").write_bytes(b"x")
    (src / "cache").mkdir()
    (src / "cache" / "junk").write_bytes(b"x")

    d = projects.duplicate(project, project + "-copy")
    try:
        assert (d / "script.txt").read_text() == "text"
        assert projects.settings(d.name)["theme"] == "mint"
        assert not (d / "out").exists()
        assert not (d / "cache").exists()
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


def test_settings_survive_corrupt_json(project):
    (projects.path_of(project) / "project.json").write_text("{not json")
    assert projects.settings(project)["theme"] == "cream"


def test_empty_name_rejected():
    with pytest.raises(ValueError):
        projects.path_of("!!!")
