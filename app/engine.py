"""Turns a list of beats into a narrated explainer video.

No API keys. No paid services. Everything runs locally except the TTS call,
which uses Microsoft's free edge-tts endpoint.

Pipeline, per render:
  1. Each beat's narration is spoken by edge-tts   -> cache/voice/<hash>.mp3
  2. Real audio duration is measured with ffprobe
  3. A 1920x1080 slide is drawn for each beat with matplotlib
  4. ffmpeg pairs slide + audio into an intermediate segment
     (slow zoom, fade in and out)                  -> cache/segments/<hash>.mp4
  5. Segments are joined, then ONE final encode adds the corner logo,
     optional music, and the end card              -> out/final.mp4
  6. An .srt subtitle file is written alongside it

Voice files are keyed on the line text, the voice and the speaking rate, so
editing one line regenerates one line. Segments are keyed on everything the
segment depends on (the beat, the theme, the audio), so a theme change
redraws every slide but never goes back to the network.
"""

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import textwrap
from dataclasses import asdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import matplotlib.patheffects as pe
import numpy as np
from matplotlib.colors import to_rgb
from PIL import Image

from .themes import mix

VOICE = "en-US-AndrewMultilingualNeural"   # warm, conversational
RATE = "-4%"                                # slightly slowed for the "neighbor" tone
W, H = 1920, 1080
FPS = 30

LOGO_CORNER_PX = 150        # height of the small corner logo
LOGO_MARGIN_PX = 40         # distance from the top and right edges
MUSIC_DB = -20        # bed level when nobody is speaking
DUCK_RATIO = 6        # how hard the voice pushes the music down (~7 dB)
DUCK_THRESHOLD = 0.03 # voice level at which ducking starts
DUCK_RELEASE = 450    # ms for the music to come back up after a line
LOOP_XFADE = 2.0      # seconds of crossfade where the track loops
FADE = 0.4                  # seconds, video fade in/out per beat
LEAD_SILENCE = 0.35         # pause before each line, stops the first word clipping
ZOOM_RATE = 0.00022         # per frame; gentler than before so stepping is less visible
PRESCALE = 2                # render the zoom at 2x then shrink, kills pixel jitter
BREATH = 0.5                # seconds of pause after each beat
TTS_PARALLEL = 4            # how many voice requests to run at once

WPM = 155                   # matches the default voice at the default rate

ENGINE_V = "1"              # bump to invalidate every cached segment


class RenderError(Exception):
    """A stage of the pipeline failed. str() is safe to show a user."""


# ----------------------------------------------------------------------
# DRAWING HELPERS
# ----------------------------------------------------------------------

def _fig(T):
    return plt.figure(figsize=(W / 100, H / 100), dpi=100, facecolor=T.bg)


HEAD_MAX_W = 1480   # px; leaves the top right corner clear for the logo


def _headline(fig, T, text, y=0.87, size=58, color=None):
    """Draw a centred headline, shrinking it if it would reach the logo."""
    t = fig.text(0.5, y, text, ha="center", va="top", fontsize=size,
                 color=color or T.ink, fontweight="bold", linespacing=1.18)
    fig.canvas.draw()
    w = t.get_window_extent(fig.canvas.get_renderer()).width
    if w > HEAD_MAX_W:
        t.set_fontsize(max(28, size * HEAD_MAX_W / w))
    return t


def _sub(fig, T, text, y=0.17, size=30, color=None):
    if text:
        fig.text(0.5, y, text, ha="center", va="center", fontsize=size,
                 color=color or T.dim)


def _rule(fig, T, y=0.79, w=0.10, color=None, lw=4):
    ax = fig.add_axes([0.5 - w / 2, y, w, 0.002])
    ax.plot([0, 1], [0, 0], color=color or T.a1, lw=lw, solid_capstyle="round")
    ax.axis("off")


def _axes(fig, T, rect=(0.13, 0.22, 0.74, 0.48)):
    ax = fig.add_axes(rect)
    ax.set_facecolor(T.bg)
    for s in ax.spines.values():
        s.set_color(T.grid)
    ax.tick_params(colors=T.dim, labelsize=18)
    ax.grid(True, color=T.grid, linewidth=1)
    ax.set_axisbelow(True)
    return ax


def _glow(txt, color, n=6):
    """A pale halo so large type separates from the page colour."""
    txt.set_path_effects([pe.withStroke(linewidth=n, foreground=color, alpha=0.85)])


def make_round_logo(src, dst, size):
    """Crop the square logo to a circle with a transparent outside.

    Source PNGs often have opaque corners, which show as a dark square over
    the page, so we build an alpha channel from the distance to the centre
    and write a real RGBA file.
    """
    im = Image.open(src).convert("RGBA").resize((size, size), Image.LANCZOS)
    yy, xx = np.mgrid[0:size, 0:size]
    c = (size - 1) / 2
    r = np.hypot(xx - c, yy - c)
    edge = size / 2 - 1.5
    alpha = np.clip((edge - r) / 1.5 + 1, 0, 1)  # 1.5 px soft edge
    a = np.array(im)
    a[..., 3] = (a[..., 3] * alpha).astype(np.uint8)
    Image.fromarray(a, "RGBA").save(dst)


# ----------------------------------------------------------------------
# SLIDES
# Each takes (fig, beat, theme). Text content comes from the beat, with the
# defaults the first video shipped with.
# ----------------------------------------------------------------------

def v_sweep(fig, b, T):
    """Accent light sweeping across the page. Soft falloff on both axes."""
    from matplotlib.colors import LinearSegmentedColormap
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    xn = np.linspace(0, 1, 480)[None, :]
    yn = np.linspace(0, 1, 270)[:, None]
    field = (np.exp(-((xn - 0.50) ** 2) / 0.22)
             * np.exp(-((yn - 0.46) ** 2) / 0.045))
    cmap = LinearSegmentedColormap.from_list("g", [T.bg, T.a1_pale, T.a1])
    ax.imshow(field, aspect="auto", cmap=cmap, extent=[0, 1, 0, 1],
              vmin=0, vmax=1.35, interpolation="bilinear")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    lines = (b.get("headline") or "").split("\n")[:2] or [""]
    ys = [0.53, 0.40] if len(lines) > 1 else [0.47]
    for line, y in zip(lines, ys):
        fig.text(0.5, y, line, ha="center", va="center",
                 fontsize=64, color=T.ink, fontweight="bold")


def v_title(fig, b, T):
    _headline(fig, T, b["headline"], y=0.70, size=96)
    _rule(fig, T, y=0.40, w=0.16)
    _sub(fig, T, b.get("sub"), y=0.31, size=32)


def v_chapter(fig, b, T):
    t = fig.text(0.5, 0.72, b["num"], ha="center", va="center",
                 fontsize=150, color=T.a1, fontweight="bold")
    _glow(t, T.a1_pale, n=10)
    _rule(fig, T, y=0.55, w=0.08)
    _headline(fig, T, b["headline"], y=0.47, size=68)


def v_gauge(fig, b, T):
    _headline(fig, T, b["headline"])
    ax = fig.add_axes([0.26, 0.30, 0.48, 0.48], projection="polar")
    ax.set_facecolor("none")
    ax.set_theta_offset(np.pi)
    ax.set_theta_direction(-1)
    ax.set_thetamin(0); ax.set_thetamax(180)
    ax.set_rticks([]); ax.set_xticks([])
    ax.spines["polar"].set_visible(False)
    ax.grid(False)
    th = np.linspace(0, np.pi, 400)
    ax.plot(th, np.ones_like(th), color=T.grid, lw=40, solid_capstyle="round")
    # colour ramps along the arc so the gauge reads as a scale, not one block
    c1, c2 = to_rgb(T.a1), to_rgb(T.a2)
    fill = th[th <= np.pi * 0.78]
    for i in range(len(fill) - 1):
        f = i / max(len(fill) - 1, 1)
        col = tuple(c1[k] * (1 - f) + c2[k] * f for k in range(3))
        ax.plot(fill[i:i + 2], [1, 1], color=col, lw=40, solid_capstyle="butt")
    ax.set_ylim(0, 1.22)
    t = fig.text(0.5, 0.30, b.get("value", "742"), ha="center", va="center",
                 fontsize=104, color=T.a2, fontweight="bold")
    _glow(t, T.a1_pale, n=9)
    fig.text(0.26, 0.31, "300", ha="center", fontsize=24, color=T.dim)
    fig.text(0.74, 0.31, "850", ha="center", fontsize=24, color=T.dim)
    _sub(fig, T, b.get("caption"), y=0.17, size=24)


def v_callout(fig, b, T):
    ax = fig.add_axes([0.08, 0.40, 0.84, 0.20])
    ax.set_facecolor(T.a2_pale)
    for s in ax.spines.values():
        s.set_color(T.a2)
        s.set_linewidth(2.5)
    ax.set_xticks([]); ax.set_yticks([])
    txt = b["headline"]
    # bold caps run about 0.97 px per point per character at this dpi;
    # keep the line inside 1440 px of the 1613 px panel
    size = min(72, int(1440 / (max(len(txt), 1) * 0.97)))
    fig.text(0.5, 0.50, txt, ha="center", va="center",
             fontsize=size, color=T.a2_hi, fontweight="bold")


def v_caption(fig, b, T):
    """A plain caption slide: one large centred statement."""
    text = b.get("caption") or b.get("headline") or ""
    t = fig.text(0.5, 0.52, "\n".join(textwrap.wrap(text, 26)), ha="center",
                 va="center", fontsize=64, color=T.ink, fontweight="bold",
                 linespacing=1.25)
    fig.canvas.draw()
    w = t.get_window_extent(fig.canvas.get_renderer()).width
    if w > HEAD_MAX_W:
        t.set_fontsize(max(30, 64 * HEAD_MAX_W / w))
    _rule(fig, T, y=0.24, w=0.10)


def v_timeline(fig, b, T):
    _headline(fig, T, b["headline"])
    ax = _axes(fig, T)
    x = np.arange(0, 121)
    y = 300 + 550 * (1 - np.exp(-x / 34))
    ax.plot(x, y, color=T.a2, lw=6)
    ax.fill_between(x, 300, y, color=T.a2, alpha=0.13)
    ax.axvline(0, color=T.a1, lw=2.5, ls=":")
    ax.annotate("Day 1", xy=(0, 300), xytext=(9, 380),
                color=T.ink, fontsize=24, fontweight="bold")
    ax.set_xlabel("Months of credit history", color=T.dim, fontsize=22, labelpad=12)
    ax.set_ylabel("Score", color=T.dim, fontsize=22, labelpad=12)
    ax.set_ylim(250, 900)
    ax.set_xticks([0, 24, 48, 72, 96, 120])
    _sub(fig, T, b.get("caption",
         "Illustrative shape, not a prediction of your score"), y=0.09, size=19)


def v_jars(fig, b, T):
    _headline(fig, T, b["headline"])
    ax = fig.add_axes([0.08, 0.16, 0.84, 0.56]); ax.axis("off")
    ax.set_xlim(0, 10); ax.set_ylim(0, 6)
    rng = np.random.default_rng(7)

    ax.text(2.5, 5.4, b.get("left", "Save what's left"), ha="center",
            fontsize=30, color=T.dim, fontweight="bold")
    xs = rng.uniform(0.6, 4.4, 26); ys = rng.uniform(0.4, 4.2, 26)
    ax.scatter(xs, ys, s=340, color=T.a1_pale, alpha=0.9, edgecolors=T.dim, lw=1.5)

    ax.plot([5, 5], [0.2, 5.0], color=T.grid, lw=2.5)

    ax.text(7.5, 5.4, b.get("right", "Pay yourself first"), ha="center",
            fontsize=30, color=T.a2, fontweight="bold")
    ax.plot([6.3, 6.3, 8.7, 8.7], [4.4, 0.5, 0.5, 4.4], color=T.a2, lw=4, alpha=0.85)
    for row in range(7):
        for col in range(3):
            ax.scatter(6.85 + col * 0.6, 0.85 + row * 0.5, s=340,
                       color=T.a1, edgecolors=T.a1_hi, lw=1.5, zorder=3)


_TERM_SPOTS = [(0.22, 0.56), (0.50, 0.62), (0.78, 0.55), (0.34, 0.36), (0.68, 0.34)]


def v_terms(fig, b, T):
    _headline(fig, T, b["headline"])
    words = b.get("words") or ["APR?", "FICO?", "ESCROW?", "UTILIZATION?", "APY?"]
    for i, ((x, y), word) in enumerate(zip(_TERM_SPOTS, words)):
        col = T.a2 if i % 2 else T.a1_hi
        t = fig.text(x, y, word, ha="center", va="center", fontsize=44,
                     color=col, fontweight="bold")
        t.set_bbox(dict(boxstyle="round,pad=0.45",
                        facecolor=T.a2_pale if i % 2 else T.a1_pale,
                        edgecolor="none"))
    _sub(fig, T, b.get("caption"), y=0.17, size=28)


def v_path(fig, b, T):
    _headline(fig, T, b["headline"])
    ax = fig.add_axes([0.10, 0.20, 0.80, 0.50]); ax.axis("off")
    ax.set_xlim(-5, 5); ax.set_ylim(0, 5)
    VY = 4.05                       # vanishing point height

    def half_width(t):              # t = 0 at viewer, 1 at horizon
        return 4.3 * (1 - t) ** 1.6 + 0.02

    # horizon band, so the road sits on ground instead of floating as a shape
    ax.fill_between([-5, 5], VY, 5, color=T.a2_pale, alpha=0.55, zorder=0)
    ax.plot([-5, 5], [VY, VY], color=T.a2, lw=1.6, alpha=0.55, zorder=1)

    # soft glow at the vanishing point, drawn as a gradient so it has no hard rim
    from matplotlib.colors import LinearSegmentedColormap
    gx = np.linspace(-2.2, 2.2, 300)[None, :]
    gy = np.linspace(-1.4, 1.4, 200)[:, None]
    glow = np.exp(-(gx ** 2) / 0.65) * np.exp(-(gy ** 2) / 0.28)
    g1, g2 = to_rgb(T.a1), to_rgb(T.a1_pale)
    ax.imshow(glow, extent=[-2.2, 2.2, VY - 1.4, VY + 1.4], origin="lower",
              aspect="auto", zorder=0, interpolation="bilinear", vmin=0, vmax=2.2,
              cmap=LinearSegmentedColormap.from_list(
                  "gl", [(*g1, 0.0), (*g2, 0.75), (*g1, 0.95)]))

    # road surface: faint, fading out before the horizon
    road = mix(T.a1_pale, T.ink, 0.12)
    n = 60
    for i in range(n):
        t0, t1 = i / n, (i + 1) / n
        y0, y1 = t0 * VY, t1 * VY
        w0, w1 = half_width(t0), half_width(t1)
        ax.fill([-w0, w0, w1, -w1], [y0, y0, y1, y1],
                color=road, alpha=0.30 + 0.45 * (1 - t0), lw=0, zorder=1)

    # the two edges, brightening toward the viewer
    for i in range(n):
        t0, t1 = i / n, (i + 1) / n
        a = 0.20 + 0.75 * (1 - t0) ** 0.9
        for s in (-1, 1):
            ax.plot([s * half_width(t0), s * half_width(t1)], [t0 * VY, t1 * VY],
                    color=T.a2, lw=1.0 + 3.4 * (1 - t0), alpha=a,
                    solid_capstyle="round", zorder=3)

    # centre dashes
    for t in np.arange(0.03, 0.92, 0.105):
        seg = 0.055 * (1 - t) + 0.004
        ax.plot([0, 0], [t * VY, (t + seg) * VY], color=T.a1,
                lw=1.0 + 3.0 * (1 - t), alpha=0.30 + 0.55 * (1 - t),
                solid_capstyle="round", zorder=3)

    # signposts, shrinking as they recede
    for t, side in ((0.10, -1), (0.36, 1), (0.60, -1)):
        y, w = t * VY, half_width(t)
        x = side * (w + 0.40)
        h = 1.15 * (1 - t) ** 1.3 + 0.06
        ax.plot([x, x], [y, y + h], color=T.dim, lw=1.0 + 2.2 * (1 - t), zorder=4)
        ax.scatter([x], [y + h], s=420 * (1 - t) ** 1.6 + 25, color=T.a1_pale,
                   marker="s", edgecolors=T.a1_hi, lw=1.0 + 1.4 * (1 - t), zorder=4)

    _sub(fig, T, b.get("sub"), y=0.14, size=32, color=T.a2)


def v_growth(fig, b, T):
    _headline(fig, T, b["headline"])
    ax = _axes(fig, T, rect=(0.13, 0.24, 0.74, 0.44))
    yrs = np.arange(1, 21)
    r, monthly = 0.07, 250.0
    bal, vals = 0.0, []
    for _ in yrs:
        for _m in range(12):
            bal = bal * (1 + r / 12) + monthly
        vals.append(bal)
    vals = np.array(vals)
    # bars ramp accent2 -> accent1 left to right so the growth reads at a glance
    c1, c2 = to_rgb(T.a2), to_rgb(T.a1)
    cols = []
    for i in range(len(yrs)):
        f = i / (len(yrs) - 1)
        cols.append(tuple(c1[k] * (1 - f) + c2[k] * f for k in range(3)))
    ax.bar(yrs, vals / 1000, color=cols, width=0.68, edgecolor="none")
    ax.set_xlabel("Years", color=T.dim, fontsize=22, labelpad=12)
    ax.set_ylabel("Balance ($ thousands)", color=T.dim, fontsize=22, labelpad=12)
    ax.set_xticks([1, 5, 10, 15, 20])
    ax.text(1.2, vals[-1] / 1000 * 0.86, f"${vals[-1]:,.0f}\nafter 20 years",
            fontsize=28, color=T.a2_hi, fontweight="bold", va="top")
    _sub(fig, T, b.get("caption",
         "$250/month at a 7% average annual return, illustrative only"),
         y=0.11, size=19)


def v_quiet(fig, b, T):
    _headline(fig, T, b["headline"], y=0.62, size=76)
    _rule(fig, T, y=0.44, w=0.12)
    _sub(fig, T, b.get("sub"), y=0.34, size=32, color=T.a2)


def v_recap(fig, b, T):
    _headline(fig, T, b["headline"], y=0.88, size=56, color=T.a1_hi)
    items = b.get("items") or []
    for i, it in enumerate(items[:6]):
        y = 0.66 - i * 0.115
        fig.text(0.30, y, f"0{i + 1}", ha="right", va="center",
                 fontsize=38, color=T.a2 if i % 2 else T.a1_hi, fontweight="bold")
        fig.text(0.35, y, it, ha="left", va="center", fontsize=42, color=T.ink)


def v_outro(fig, b, T):
    big = b.get("logo_big")
    if big and Path(big).exists():
        img = mpimg.imread(big)
        # 62% of frame height, centred horizontally, sitting in the upper half
        h = 0.62
        w = h * H / W
        ax = fig.add_axes([0.5 - w / 2, 0.34, w, h]); ax.axis("off")
        ax.imshow(img)
    elif b.get("brand"):
        t = fig.text(0.5, 0.64, b["brand"], ha="center", va="center",
                     fontsize=90, color=T.a1_hi, fontweight="bold")
        _glow(t, T.a1_pale, n=10)
    _rule(fig, T, y=0.30, w=0.10)
    _headline(fig, T, b["headline"], y=0.265, size=36, color=T.dim)
    _sub(fig, T, b.get("sub"), y=0.175, size=40, color=T.ink)
    t = fig.text(0.5, 0.08, "SUBSCRIBE", ha="center", fontsize=28, color=T.bg,
                 fontweight="bold")
    t.set_bbox(dict(boxstyle="round,pad=0.6", facecolor=T.a2, edgecolor="none"))


VISUALS = {
    "sweep": v_sweep, "title": v_title, "chapter": v_chapter, "gauge": v_gauge,
    "callout": v_callout, "caption": v_caption, "timeline": v_timeline,
    "jars": v_jars, "terms": v_terms, "path": v_path, "growth": v_growth,
    "quiet": v_quiet, "recap": v_recap, "outro": v_outro,
}


def render_slide(beat, path, T):
    from . import scenes
    fig = _fig(T)
    draw = VISUALS.get(beat["visual"]) or scenes.VISUALS[beat["visual"]]
    draw(fig, beat, T)
    fig.savefig(path, facecolor=T.bg, dpi=100)
    plt.close(fig)


# ----------------------------------------------------------------------
# AUDIO
# ----------------------------------------------------------------------

def voice_key(text, voice, rate):
    return hashlib.sha1(f"{text}\x1f{voice}\x1f{rate}".encode()).hexdigest()


def _fake_voice(text, path):
    """Stand-in used when STV_FAKE_TTS is set: a quiet tone the length the
    real line would be. CI machines can't always reach the voice service,
    and tests must not depend on it."""
    d = max(1.0, len(text.split()) / (WPM / 60))
    run(["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"sine=frequency=440:duration={d:.2f}", "-af", "volume=0.2", str(path)])


async def _speak_all(lines, paths, voice, rate, on_line=None):
    import edge_tts
    sem = asyncio.Semaphore(TTS_PARALLEL)

    async def one(text, p):
        async with sem:
            c = edge_tts.Communicate(text, voice, rate=rate)
            await c.save(str(p))
            if on_line:
                on_line()

    await asyncio.gather(*(one(t, p) for t, p in zip(lines, paths)))


def speak_missing(lines, paths, voice, rate, on_line=None):
    todo = [(t, p) for t, p in zip(lines, paths) if not p.exists()]
    if not todo:
        return
    if os.environ.get("STV_FAKE_TTS"):
        for t, p in todo:
            _fake_voice(t, p)
            if on_line:
                on_line()
        return
    try:
        asyncio.run(_speak_all([t for t, _ in todo], [p for _, p in todo],
                               voice, rate, on_line))
    except Exception as e:
        # partial files must not poison the cache
        for _, p in todo:
            if p.exists() and p.stat().st_size == 0:
                p.unlink()
        raise RenderError(
            "Could not reach the voice service. Check your internet "
            "connection and press Generate again; finished lines are kept "
            f"and will not be redone. ({type(e).__name__})") from e


def duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def estimate_seconds(beats):
    words = sum(len(b.get("say", "").split()) for b in beats)
    return words / WPM * 60 + len(beats) * (LEAD_SILENCE + BREATH)


# ----------------------------------------------------------------------
# BUILD
# ----------------------------------------------------------------------

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RenderError(f"command failed:\n  {' '.join(map(str, cmd))}\n\n"
                          f"{r.stderr[-3000:]}")


def build_music_bed(src, dst, need, work):
    """Make a music track at least `need` seconds long.

    The song is shorter than the video, so it has to repeat. A hard repeat
    leaves an audible click at the seam, so each pass is crossfaded into the
    next. Each crossfade costs LOOP_XFADE seconds of total length.
    """
    src = Path(src).resolve()
    have = duration(src)
    if have >= need:
        shutil.copy(src, dst)
        return dst

    cur = work / "bed_00.wav"
    run(["ffmpeg", "-y", "-i", str(src), "-ar", "48000", "-ac", "2", str(cur)])
    total, n = have, 0
    while total < need:
        n += 1
        nxt = work / f"bed_{n:02d}.wav"
        run(["ffmpeg", "-y", "-i", str(cur), "-i", str(src),
             "-filter_complex",
             f"[1:a]aresample=48000,aformat=channel_layouts=stereo[b];"
             f"[0:a][b]acrossfade=d={LOOP_XFADE}:c1=tri:c2=tri[a]",
             "-map", "[a]", "-ar", "48000", "-ac", "2", str(nxt)])
        cur = nxt
        total += have - LOOP_XFADE
    shutil.move(str(cur), dst)
    return dst


def srt_time(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}"


def _file_hash(path):
    return hashlib.sha1(Path(path).read_bytes()).hexdigest() if Path(path).exists() else "none"


def _prepared(beats, project):
    """Copy of the beats with everything a slide depends on made explicit,
    so hashing a beat covers all of its inputs."""
    out = []
    logo = project / "logo.png"
    for b in beats:
        b = dict(b)
        if b["visual"] == "outro" and logo.exists():
            b["logo_hash"] = _file_hash(logo)
        out.append(b)
    return out


def segment_key(beat, theme, audio_key):
    ident = json.dumps([ENGINE_V, beat, asdict(theme), audio_key], sort_keys=True)
    return hashlib.sha1(ident.encode()).hexdigest()


def plan(project, beats, theme, voice=VOICE, rate=RATE):
    """What a render would reuse, so the page can say it before Generate."""
    project = Path(project)
    beats = _prepared(beats, project)
    vdir = project / "cache" / "voice"
    sdir = project / "cache" / "segments"
    voices_cached = segs_cached = 0
    for b in beats:
        vk = voice_key(b["say"], voice, rate)
        if (vdir / f"{vk}.mp3").exists():
            voices_cached += 1
        if (sdir / f"{segment_key(b, theme, vk)}.mp4").exists():
            segs_cached += 1
    return {"beats": len(beats),
            "voices_cached": voices_cached,
            "segments_cached": segs_cached}


def render_video(project, beats, theme, voice=VOICE, rate=RATE, progress=None):
    """Render `beats` into project/out/final.mp4 and final.srt.

    `progress(stage, done, total)` is called as work happens; stage is one of
    "voice", "slides", "segments", "final".
    """
    if not shutil.which("ffmpeg"):
        raise RenderError("ffmpeg was not found. Run the installer again, or "
                          "install ffmpeg and restart the app.")

    project = Path(project)
    out_dir = project / "out"
    cache = project / "cache"
    work = cache / "work"
    vdir = cache / "voice"
    sdir = cache / "segments"
    for d in (out_dir, work, vdir, sdir):
        d.mkdir(parents=True, exist_ok=True)

    def report(stage, done, total):
        if progress:
            progress(stage, done, total)

    beats = _prepared(beats, project)
    logo = project / "logo.png"
    music = project / "music.mp3"
    if logo.exists():
        make_round_logo(logo, work / "logo_big.png", 1080)
        make_round_logo(logo, work / "logo_small.png", LOGO_CORNER_PX)

    lines = [b["say"] for b in beats]
    keys = [voice_key(t, voice, rate) for t in lines]
    paths = [vdir / f"{k}.mp3" for k in keys]
    done = sum(1 for p in paths if p.exists())
    report("voice", done, len(beats))
    state = {"done": done}

    def on_line():
        state["done"] += 1
        report("voice", state["done"], len(beats))

    speak_missing(lines, paths, voice, rate, on_line)

    seg_keys = [segment_key(b, theme, k) for b, k in zip(beats, keys)]
    segs = [sdir / f"{sk}.mp4" for sk in seg_keys]
    missing = [i for i, s in enumerate(segs) if not s.exists()]

    for j, i in enumerate(missing):
        report("slides", j, len(missing))
        b = beats[i]
        if b["visual"] == "outro":
            b = {**b, "logo_big": str(work / "logo_big.png")}
        render_slide(b, work / f"slide_{i:02d}.png", theme)
    report("slides", len(missing), len(missing))

    for j, i in enumerate(missing):
        report("segments", j, len(missing))
        img = work / f"slide_{i:02d}.png"
        snd = paths[i]
        spoken = duration(snd)
        d = LEAD_SILENCE + spoken + BREATH
        frames = int(round(d * FPS))
        # zoompan works in whole pixels, so at 1080p the crop jumps a pixel at a
        # time and the slide looks shaky. Scaling up first makes each step a
        # fraction of an output pixel, and the downscale averages it away.
        zoom = (f"scale={W * PRESCALE}:{H * PRESCALE}:flags=bilinear,"
                f"zoompan=z='min(zoom+{ZOOM_RATE},1.06)':d={frames}"
                f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS}")
        # fades go to the page colour, not black, or the light theme flashes dark
        fade_col = theme.bg.lstrip("#")
        vf = (f"[0:v]{zoom},fade=t=in:st=0:d={FADE}:color=0x{fade_col},"
              f"fade=t=out:st={d - FADE:.3f}:d={FADE}:color=0x{fade_col},"
              f"format=yuv420p[v]")
        # lead-in silence stops the first consonant being clipped by mp3 padding
        af = (f"[1:a]adelay={int(LEAD_SILENCE * 1000)}|{int(LEAD_SILENCE * 1000)},"
              f"aresample=48000,apad,atrim=0:{d:.3f},"
              f"afade=t=out:st={d - 0.25:.3f}:d=0.25[a]")
        # fast intermediate encode; the final pass does the real compression
        tmp = work / "seg_tmp.mp4"
        run(["ffmpeg", "-y", "-loop", "1", "-i", str(img), "-i", str(snd),
             "-filter_complex", f"{vf};{af}",
             "-map", "[v]", "-map", "[a]",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
             "-r", str(FPS), "-c:a", "pcm_s16le", "-ac", "2",
             "-t", f"{d:.3f}", str(tmp)])
        shutil.move(str(tmp), segs[i])
    report("segments", len(missing), len(missing))

    report("final", 0, 1)
    clock, srt = 0.0, []
    outro_start = None
    for b, snd in zip(beats, paths):
        spoken = duration(snd)
        d = LEAD_SILENCE + spoken + BREATH
        if b["visual"] == "outro":
            outro_start = clock
        srt.append((clock + LEAD_SILENCE, clock + LEAD_SILENCE + spoken, b["say"]))
        clock += d

    lst = work / "concat.txt"
    lst.write_text("".join(f"file '{s.resolve()}'\n" for s in segs))
    joined = work / "joined.mkv"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c", "copy", str(joined)])

    final = out_dir / "final.mp4"
    inputs = ["-i", str(joined)]
    filters = []
    vin = "[0:v]"
    n = 1

    if logo.exists():
        inputs += ["-i", str(work / "logo_small.png")]
        # corner logo for the whole video except the outro, where the big one is
        show = f":enable='lt(t,{outro_start:.3f})'" if outro_start is not None else ""
        filters.append(f"{vin}[{n}:v]overlay=W-w-{LOGO_MARGIN_PX}:{LOGO_MARGIN_PX}{show}[v]")
        vin = "[v]"
        n += 1

    if music.exists():
        bed = build_music_bed(music, work / "bed.wav", clock + 2, work)
        inputs += ["-i", str(bed)]
        # The voice is used twice: once in the mix, once as the control signal
        # that pushes the music down. That is what sidechaincompress does, so
        # the bed lifts in the gaps between lines and drops under speech.
        filters.append(
            f"[{n}:a]volume={MUSIC_DB}dB,"
            f"afade=t=in:st=0:d=2,afade=t=out:st={clock - 3:.3f}:d=3[m];"
            f"[0:a]asplit=2[voice][key];"
            f"[m][key]sidechaincompress=threshold={DUCK_THRESHOLD}"
            f":ratio={DUCK_RATIO}:attack=15:release={DUCK_RELEASE}[duck];"
            f"[voice][duck]amix=inputs=2:duration=first"
            f":dropout_transition=0:normalize=0[a]")
        aout = "[a]"
    else:
        aout = "0:a"

    cmd = ["ffmpeg", "-y", *inputs]
    if filters:
        cmd += ["-filter_complex", ";".join(filters)]
    cmd += ["-map", vin if filters and logo.exists() else "0:v", "-map", aout,
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", "-shortest", str(final)]
    run(cmd)

    with open(out_dir / "final.srt", "w") as f:
        for k, (a, bb, txt) in enumerate(srt, 1):
            body = "\n".join(textwrap.wrap(txt, 52))
            f.write(f"{k}\n{srt_time(a)} --> {srt_time(bb)}\n{body}\n\n")

    report("final", 1, 1)
    return {"video": final, "srt": out_dir / "final.srt", "seconds": clock}
