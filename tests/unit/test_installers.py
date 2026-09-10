"""What the installers must never do to a working install.

Both of them replace the code in place. The videos live in projects/ inside
that same folder, so the order of operations is the whole safety story: the
new copy has to be complete on disk before anything existing is touched, and
the user's projects have to be carried across rather than deleted with the
rest of the folder.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SH = (ROOT / "install.sh").read_text()
PS1 = (ROOT / "install.ps1").read_text()


@pytest.mark.parametrize("name,src", [("install.sh", SH), ("install.ps1", PS1)])
def test_a_reinstall_keeps_the_videos_already_made(name, src):
    """This deleted the whole install folder, projects and all, every time
    the install command was pasted a second time."""
    assert "projects" in src, f"{name} does not mention projects at all"
    lowered = src.lower()
    assert "kept the videos you had already made" in lowered, \
        f"{name} does not carry projects across a reinstall"


def test_the_shell_installer_stages_before_it_deletes():
    """It used to delete the install folder and then download into it, so a
    download that failed half way left nothing behind."""
    stage = SH.index('STAGE="$(mktemp -d)"')
    save = SH.index('mv "$DEST/projects" "$STAGE/projects"')
    wipe = SH.index('rm -rf "$DEST"')
    assert stage < save < wipe, \
        "the install folder is removed before the new copy is staged"


def test_the_windows_installer_stages_before_it_deletes():
    unpack = PS1.index("Expand-Archive $tmp")
    save = PS1.index("if (Test-Path $mine) { Move-Item $mine $saved }")
    wipe = PS1.index("if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }")
    assert unpack < save < wipe, \
        "the install folder is removed before the archive is unpacked"


@pytest.mark.parametrize("name,src,token", [
    ("install.sh", SH, "${STV_BRANCH:-main}"),
    ("install.ps1", PS1, '$env:STV_BRANCH'),
])
def test_a_branch_can_be_installed_without_editing_anything(name, src, token):
    """A change has to be installable on a real machine before it is merged,
    and main stays the default so nothing changes for anyone else."""
    assert token in src, name
    assert "main" in src, f"{name} lost its default"
