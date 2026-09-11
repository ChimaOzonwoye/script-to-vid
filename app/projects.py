"""Projects are folders under projects/, one per video.

Each holds script.txt, project.json (theme, voice, speaking rate), the
optional logo.png and music.mp3, the cache, and the finished out/final.mp4.
Nothing is shared between projects except the code.
"""

import json
import re
import shutil
from pathlib import Path

from .themes import DEFAULT_THEME
from .voices import DEFAULT_VOICE, DEFAULT_RATE, valid_voice, valid_rate

ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = ROOT / "projects"
MERGES_DIR = ROOT / "merges"
EXAMPLE_SCRIPT = ROOT / "example-script.txt"

# "keep" holds the exact text of lines the user put back from the review
# panel, so the choice survives a reload. "light", "lettering" and "dressing"
# stay empty until the user moves them off what the template ships with, so a
# template whose look is later revised carries the revision into every project
# that never overrode it.
DEFAULTS = {"theme": DEFAULT_THEME, "voice": DEFAULT_VOICE,
            "rate": DEFAULT_RATE, "keep": [], "light": "", "lettering": "",
            "dressing": "", "captions": "", "effect": "",
            "composition": ""}


def slugify(name):
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return slug[:60]


def path_of(name):
    # names are slugs, so a crafted name can never escape projects/
    slug = slugify(name)
    if not slug:
        raise ValueError("empty project name")
    return PROJECTS_DIR / slug


def exists(name):
    return path_of(name).is_dir()


def list_projects():
    PROJECTS_DIR.mkdir(exist_ok=True)
    out = []
    for p in sorted(PROJECTS_DIR.iterdir()):
        if p.is_dir() and (p / "project.json").exists():
            out.append({
                "name": p.name,
                "mtime": (p / "project.json").stat().st_mtime,
                "has_video": (p / "out" / "final.mp4").exists(),
            })
    out.sort(key=lambda x: -x["mtime"])
    return out


def create(name, with_example=False):
    p = path_of(name)
    p.mkdir(parents=True, exist_ok=True)
    if not (p / "project.json").exists():
        save_settings(p.name, DEFAULTS)
    if with_example and not (p / "script.txt").exists() and EXAMPLE_SCRIPT.exists():
        save_script(p.name, EXAMPLE_SCRIPT.read_text())
    return p


def duplicate(src, new_name):
    """Copy settings, script, logo and music, but not the cache or output."""
    s, d = path_of(src), create(new_name)
    for f in ("project.json", "script.txt", "logo.png", "music.mp3"):
        if (s / f).exists():
            shutil.copy(s / f, d / f)
    return d


def settings(name):
    p = path_of(name) / "project.json"
    try:
        cfg = {**DEFAULTS, **json.loads(p.read_text())}
    except (OSError, ValueError):
        return dict(DEFAULTS)
    cfg["voice"] = valid_voice(cfg.get("voice"))
    cfg["rate"] = valid_rate(cfg.get("rate"))
    kept = cfg.get("keep")
    cfg["keep"] = [k for k in kept if isinstance(k, str)] if isinstance(kept, list) else []
    for field in ("light", "lettering", "dressing", "captions",
                  "effect", "composition"):
        cfg[field] = cfg[field] if isinstance(cfg.get(field), str) else ""
    return cfg


def save_settings(name, updates):
    p = path_of(name)
    p.mkdir(parents=True, exist_ok=True)
    merged = {**settings(name), **updates}
    (p / "project.json").write_text(json.dumps(merged, indent=1))
    return merged


def script(name):
    p = path_of(name) / "script.txt"
    return p.read_text() if p.exists() else ""


def save_script(name, text):
    (path_of(name) / "script.txt").write_text(text)
