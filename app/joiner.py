"""Joins finished videos into one.

Two jobs, one mechanism. A long script can be made as several projects and
the parts joined at the end, which is how a machine that cannot manage a ten
minute render in one go still gets a ten minute video. And the same page
takes video files from anywhere, so the app doubles as a plain joiner.

Whether the join re-encodes is the whole cost difference: copying is seconds
for any length, re-encoding is minutes. So the videos this app makes are
never re-encoded, because they already share one profile, and anything else
is converted to that profile first. The page says which is happening rather
than leaving the user watching a bar with no idea why.
"""

import json
import shutil
import subprocess
from pathlib import Path

from .engine import FPS, H, W, RenderError, duration, run

# What render_video's final pass produces. Inputs matching this can be
# concatenated without being decoded at all.
PROFILE = {"width": W, "height": H, "fps": FPS, "vcodec": "h264",
           "acodec": "aac", "sample_rate": 48000}


def probe(path):
    """Shape of a video file, or None if it is not one we can read."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format",
         "-of", "json", str(path)], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        data = json.loads(r.stdout)
    except ValueError:
        return None
    video = next((s for s in data.get("streams", [])
                  if s.get("codec_type") == "video"), None)
    if not video:
        return None
    audio = next((s for s in data.get("streams", [])
                  if s.get("codec_type") == "audio"), None)
    num, _, den = (video.get("avg_frame_rate") or "0/1").partition("/")
    try:
        fps = round(float(num) / float(den or 1), 3)
    except (ValueError, ZeroDivisionError):
        fps = 0
    return {
        "width": video.get("width") or 0,
        "height": video.get("height") or 0,
        "fps": fps,
        "vcodec": video.get("codec_name") or "",
        "acodec": (audio or {}).get("codec_name") or "",
        "sample_rate": int((audio or {}).get("sample_rate") or 0),
        "has_audio": audio is not None,
        "seconds": float(data.get("format", {}).get("duration") or 0),
    }


def ready_to_copy(info):
    """Whether this file can go straight into a stream copy."""
    return bool(info) and (
        info["width"] == PROFILE["width"]
        and info["height"] == PROFILE["height"]
        and abs(info["fps"] - PROFILE["fps"]) < 0.01
        and info["vcodec"] == PROFILE["vcodec"]
        and info["has_audio"]
        and info["acodec"] == PROFILE["acodec"]
        and info["sample_rate"] == PROFILE["sample_rate"])


def plan(paths):
    """What joining these would involve, before committing to it."""
    items, unreadable = [], []
    for p in paths:
        info = probe(p)
        if info is None:
            unreadable.append(Path(p).name)
        else:
            items.append({"path": Path(p), "info": info,
                          "copy": ready_to_copy(info)})
    return {
        "items": items,
        "unreadable": unreadable,
        "convert": [i["path"].name for i in items if not i["copy"]],
        "seconds": sum(i["info"]["seconds"] for i in items),
    }


def _normalise(src, dst):
    """Bring one file to the profile so it can be joined with the others.

    Letterboxed rather than stretched, and silence is added where a file has
    no audio at all, because concat drops a stream that is missing from any
    input and the sound would cut out from that point on.
    """
    scale = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
             f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,"
             f"setsar=1,fps={FPS},format=yuv420p")
    info = probe(src) or {}
    cmd = ["ffmpeg", "-y", "-i", str(src)]
    if not info.get("has_audio"):
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest"]
    cmd += ["-vf", scale,
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            str(dst)]
    run(cmd)


def join(paths, dest, work, progress=None):
    """Join `paths` in order into `dest`. Returns what it had to do."""
    paths = [Path(p) for p in paths]
    if len(paths) < 2:
        raise RenderError("Pick at least two videos to join.")
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    p = plan(paths)
    if p["unreadable"]:
        raise RenderError(
            "These could not be read as video: "
            + ", ".join(p["unreadable"])
            + ". MP4 and MOV files from this app or a camera work.")

    def say(stage, done, total):
        if progress:
            progress(stage, done, total)

    ready = []
    todo = [i for i in p["items"] if not i["copy"]]
    done = 0
    for n, item in enumerate(p["items"]):
        if item["copy"]:
            ready.append(item["path"].resolve())
            continue
        say("convert", done, len(todo))
        out = work / f"part_{n:03d}.mp4"
        _normalise(item["path"], out)
        done += 1
        ready.append(out.resolve())
    say("join", 0, 1)

    lst = work / "join.txt"
    lst.write_text("".join(f"file '{q}'\n" for q in ready))
    tmp = work / "joined.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c", "copy", "-movflags", "+faststart", str(tmp)])
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(tmp), dest)
    for q in work.glob("part_*.mp4"):
        q.unlink(missing_ok=True)
    lst.unlink(missing_ok=True)
    say("join", 1, 1)
    return {"video": Path(dest), "converted": p["convert"],
            "seconds": duration(dest)}
