"""The local web app. One page per project, everything happens in the browser.

Binds to localhost only; nothing leaves the machine except the edge-tts
requests. Every user-facing failure is a plain sentence, never a traceback.
"""

import io
import subprocess
import threading
import urllib.request
from pathlib import Path

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image

from . import engine, projects, voices
from .script_parser import parse
from .themes import THEMES, DEFAULT_THEME

HERE = Path(__file__).resolve().parent
app = FastAPI(title="script to vid")
templates = Jinja2Templates(directory=HERE / "templates")
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
projects.PROJECTS_DIR.mkdir(exist_ok=True)
app.mount("/files", StaticFiles(directory=projects.PROJECTS_DIR), name="files")

MUSIC_DIR = projects.ROOT / "assets" / "music"
if MUSIC_DIR.is_dir():
    app.mount("/library", StaticFiles(directory=MUSIC_DIR), name="library")
voices.SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/voices", StaticFiles(directory=voices.SAMPLE_DIR), name="voices")

STAGES = {"voice": ("1", "generating the voiceover"),
          "slides": ("2", "drawing slides"),
          "segments": ("3", "building video segments"),
          "final": ("4", "final encode: logo, music and subtitles")}

# one render at a time per project; the page polls /status
RENDERS = {}


def fail(message, code=400):
    return JSONResponse({"error": message}, status_code=code)


def _valid(name):
    return projects.slugify(name) and projects.exists(name)


def _music_seconds(path):
    try:
        return engine.duration(path)
    except Exception:
        return None


def _mmss(sec):
    return f"{int(sec // 60)}:{int(sec % 60):02d}"


def _analysis(name, text):
    r = parse(text)
    cfg = projects.settings(name)
    est = engine.estimate_seconds(r["beats"], cfg["rate"])
    theme = THEMES.get(cfg["theme"], THEMES[DEFAULT_THEME])
    p = engine.plan(projects.path_of(name), r["beats"], theme,
                    cfg["voice"], cfg["rate"])
    m, s = divmod(int(est), 60)
    music = projects.path_of(name) / "music.mp3"
    msec = _music_seconds(music) if music.exists() else None
    return {
        "words": r["words"],
        "estimate": f"{r['words']} words, about {m} min {s} sec",
        "seconds": est,
        "warnings": r["warnings"],
        "beats": len(r["beats"]),
        "voices_cached": p["voices_cached"],
        "segments_cached": p["segments_cached"],
        "music_loops": bool(msec and msec < est),
    }


# ----------------------------------------------------------------------
# pages
# ----------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {
        "projects": projects.list_projects(),
        "theme": THEMES[DEFAULT_THEME],
    })


@app.post("/projects")
def new_project(name: str = Form(...), example: str = Form("")):
    slug = projects.slugify(name)
    if not slug:
        return fail("The project needs a name. Letters and numbers are fine.")
    projects.create(slug, with_example=bool(example))
    return RedirectResponse(f"/p/{slug}", status_code=303)


@app.get("/p/{name}", response_class=HTMLResponse)
def project_page(request: Request, name: str):
    if not _valid(name):
        return RedirectResponse("/", status_code=303)
    cfg = projects.settings(name)
    theme = THEMES.get(cfg["theme"], THEMES[DEFAULT_THEME])
    p = projects.path_of(name)
    music = p / "music.mp3"
    msec = _music_seconds(music) if music.exists() else None
    tracks = []
    for f in sorted(MUSIC_DIR.glob("*.mp3")) if MUSIC_DIR.is_dir() else []:
        sec = _music_seconds(f)
        tracks.append({"file": f.name,
                       "name": f.stem.replace("-", " ").title(),
                       "length": _mmss(sec) if sec else "?"})
    return templates.TemplateResponse(request, "project.html", {
        "name": name,
        "script": projects.script(name),
        "theme": theme,
        "themes": THEMES,
        "voices": voices.listing(),
        "voice": cfg["voice"],
        "rates": voices.RATES,
        "rate": cfg["rate"],
        "has_logo": (p / "logo.png").exists(),
        "has_music": music.exists(),
        "music_length": _mmss(msec) if msec else None,
        "has_video": (p / "out" / "final.mp4").exists(),
        "tracks": tracks,
    })


@app.post("/p/{name}/duplicate")
def duplicate(name: str, new_name: str = Form(...)):
    if not _valid(name):
        return RedirectResponse("/", status_code=303)
    slug = projects.slugify(new_name)
    if not slug:
        return fail("The new project needs a name.")
    projects.duplicate(name, slug)
    return RedirectResponse(f"/p/{slug}", status_code=303)


# ----------------------------------------------------------------------
# script and settings
# ----------------------------------------------------------------------

@app.post("/p/{name}/script")
async def save_script(name: str, request: Request):
    if not _valid(name):
        return fail("That project no longer exists.", 404)
    body = await request.json()
    text = body.get("script", "")
    projects.save_script(name, text)
    return _analysis(name, text)


@app.post("/p/{name}/voice")
def set_voice(name: str, voice: str = Form(...), rate: str = Form(...)):
    if not _valid(name):
        return fail("That project no longer exists.", 404)
    projects.save_settings(name, {"voice": voices.valid_voice(voice),
                                  "rate": voices.valid_rate(rate)})
    cfg = projects.settings(name)
    return {"message": f"Narration will use {voices.rate_label(cfg['rate']).lower()} "
                       "speed. Lines already made in another voice will be "
                       "made again.",
            "voice": cfg["voice"], "rate": cfg["rate"]}


@app.post("/p/{name}/theme")
def set_theme(name: str, theme: str = Form(...)):
    if not _valid(name):
        return RedirectResponse("/", status_code=303)
    if theme in THEMES:
        projects.save_settings(name, {"theme": theme})
    return RedirectResponse(f"/p/{name}#look", status_code=303)


# ----------------------------------------------------------------------
# logo
# ----------------------------------------------------------------------

@app.post("/p/{name}/logo")
async def upload_logo(name: str, file: UploadFile = File(...)):
    if not _valid(name):
        return fail("That project no longer exists.", 404)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".png", ".jpg", ".jpeg"):
        return fail(f"That file is a {suffix or 'file with no extension'}. "
                    "The logo needs to be a .png or .jpg image.")
    data = await file.read()
    p = projects.path_of(name)
    try:
        img = Image.open(io.BytesIO(data))
        img.convert("RGBA").save(p / "logo.png")
    except Exception:
        return fail("That file could not be read as an image. Try exporting "
                    "it again as a .png.")
    work = p / "cache" / "work"
    work.mkdir(parents=True, exist_ok=True)
    engine.make_round_logo(p / "logo.png", work / "logo_preview.png", 300)
    return {"message": "Saved your logo as logo.png. If you ever run this "
                       "from the folder directly, the file needs that exact "
                       "name.",
            "preview": f"/files/{name}/cache/work/logo_preview.png"}


@app.post("/p/{name}/logo/remove")
def remove_logo(name: str):
    if _valid(name):
        (projects.path_of(name) / "logo.png").unlink(missing_ok=True)
    return {"message": "Logo removed."}


# ----------------------------------------------------------------------
# music
# ----------------------------------------------------------------------

def _save_music(name, src_path):
    """Convert whatever arrived into the project's music.mp3."""
    dst = projects.path_of(name) / "music.mp3"
    r = subprocess.run(["ffmpeg", "-y", "-i", str(src_path), "-vn",
                        "-c:a", "libmp3lame", "-q:a", "3", str(dst)],
                       capture_output=True)
    if r.returncode != 0 or not dst.exists():
        dst.unlink(missing_ok=True)
        return None
    return _music_seconds(dst)


def _music_reply(name, sec):
    if sec is None:
        return fail("That file could not be read as audio. MP3, WAV and M4A "
                    "files work.")
    return {"message": f"Saved as music.mp3, {_mmss(sec)} long. If it is "
                       "shorter than the video it will loop with a smooth "
                       "crossfade.",
            "length": _mmss(sec)}


@app.post("/p/{name}/music/upload")
async def upload_music(name: str, file: UploadFile = File(...)):
    if not _valid(name):
        return fail("That project no longer exists.", 404)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".mp3", ".wav", ".m4a"):
        return fail(f"That file is a {suffix or 'file with no extension'}. "
                    "Music needs to be an .mp3, .wav or .m4a file.")
    tmp = projects.path_of(name) / f"upload_tmp{suffix}"
    tmp.write_bytes(await file.read())
    sec = _save_music(name, tmp)
    tmp.unlink(missing_ok=True)
    return _music_reply(name, sec)


@app.post("/p/{name}/music/library")
def pick_music(name: str, track: str = Form(...)):
    if not _valid(name):
        return fail("That project no longer exists.", 404)
    src = MUSIC_DIR / Path(track).name
    if not src.exists():
        return fail("That track is not in the library any more. Pick another.")
    return _music_reply(name, _save_music(name, src))


@app.post("/p/{name}/music/url")
def music_from_url(name: str, url: str = Form(...)):
    if not _valid(name):
        return fail("That project no longer exists.", 404)
    clean = url.split("?")[0].lower()
    if not clean.startswith(("http://", "https://")):
        return fail("That doesn't look like a link. Paste a full web address "
                    "starting with https://")
    if not clean.endswith((".mp3", ".wav", ".m4a")):
        return fail("That link doesn't point at an audio file. It needs to "
                    "end in .mp3, .wav or .m4a. Links to YouTube or "
                    "streaming pages won't work.")
    tmp = projects.path_of(name) / ("url_tmp" + Path(clean).suffix)
    try:
        with urllib.request.urlopen(url, timeout=30) as r, open(tmp, "wb") as f:
            f.write(r.read(100 * 1024 * 1024))
    except Exception:
        tmp.unlink(missing_ok=True)
        return fail("The file could not be downloaded from that link. Check "
                    "the address, or download it yourself and use Upload.")
    sec = _save_music(name, tmp)
    tmp.unlink(missing_ok=True)
    return _music_reply(name, sec)


@app.post("/p/{name}/music/remove")
def remove_music(name: str):
    if _valid(name):
        (projects.path_of(name) / "music.mp3").unlink(missing_ok=True)
    return {"message": "Music removed. The video will be voice only."}


# ----------------------------------------------------------------------
# generate
# ----------------------------------------------------------------------

def _render_worker(name, beats, theme, voice, rate):
    status = RENDERS[name]

    def progress(stage, done, total):
        n, label = STAGES[stage]
        beat = f" ({min(done + 1, total)} of {total})" if total > 1 else ""
        status.update(state="running", stage=stage, done=done, total=total,
                      message=f"Stage {n} of 4: {label}{beat}")

    try:
        r = engine.render_video(projects.path_of(name), beats, theme,
                                voice=voice, rate=rate, progress=progress)
        status.update(state="done", seconds=r["seconds"],
                      message="Done. Your video is ready below.")
    except engine.RenderError as e:
        status.update(state="error", message=str(e))
    except Exception:
        status.update(state="error", message=(
            "Something went wrong while rendering. Press Generate to try "
            "again; everything already finished will be reused."))


@app.post("/p/{name}/generate")
async def generate(name: str, request: Request):
    if not _valid(name):
        return fail("That project no longer exists.", 404)
    if RENDERS.get(name, {}).get("state") == "running":
        return fail("A render is already running for this project.")
    body = await request.json()
    text = body.get("script", "")
    projects.save_script(name, text)
    r = parse(text)
    if not r["beats"]:
        return fail("The script is empty. Write some narration first.")
    cfg = projects.settings(name)
    theme = THEMES.get(cfg["theme"], THEMES[DEFAULT_THEME])
    RENDERS[name] = {"state": "running", "message": "Starting..."}
    threading.Thread(target=_render_worker,
                     args=(name, r["beats"], theme, cfg["voice"], cfg["rate"]),
                     daemon=True).start()
    return {"ok": True, "warnings": r["warnings"]}


@app.get("/p/{name}/status")
def status(name: str):
    return RENDERS.get(name, {"state": "idle", "message": ""})
