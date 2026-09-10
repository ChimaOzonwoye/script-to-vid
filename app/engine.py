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

from . import animate
from .themes import mix
from .voices import DEFAULT_VOICE as VOICE, DEFAULT_RATE as RATE
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

ENGINE_V = "4"              # bump to invalidate every cached segment


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

    ax.text(2.5, 5.4, b.get("left", "Before"), ha="center",
            fontsize=30, color=T.dim, fontweight="bold")
    xs = rng.uniform(0.6, 4.4, 26); ys = rng.uniform(0.4, 4.2, 26)
    ax.scatter(xs, ys, s=340, color=T.a1_pale, alpha=0.9, edgecolors=T.dim, lw=1.5)

    ax.plot([5, 5], [0.2, 5.0], color=T.grid, lw=2.5)

    ax.text(7.5, 5.4, b.get("right", "After"), ha="center",
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


def render_slide(beat, path, T, eyes="open", mouth="closed"):
    from . import scenes
    fig = _fig(T)
    draw = VISUALS.get(beat["visual"]) or scenes.VISUALS[beat["visual"]]
    draw(fig, {**beat, "eyes": eyes, "mouth": mouth}, T)
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
    and tests must not depend on it.

    It pulses at roughly a syllable a beat, because the lip sync reads the
    loudness of this file and a flat tone would hold the mouth wide open for
    the whole line."""
    d = max(1.0, len(text.split()) / (WPM / 60))
    run(["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"sine=frequency=440:duration={d:.2f}",
         "-af", "tremolo=f=4.5:d=0.9,volume=0.2", str(path)])


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


def _drop_unusable(todo):
    """Remove any voice file that came back empty and say how many.

    The service can answer without failing and still return nothing, which
    leaves a zero byte file in a cache keyed on the line. Left there it is
    never regenerated, so the render fails on that line for ever. Nothing
    downstream can recover from it, so it must not survive this function.
    """
    bad = [p for _, p in todo if not p.exists() or p.stat().st_size == 0]
    for p in bad:
        p.unlink(missing_ok=True)
    return len(bad)


def speak_missing(lines, paths, voice, rate, on_line=None):
    todo = [(t, p) for t, p in zip(lines, paths) if not p.exists()]
    if not todo:
        return
    if os.environ.get("STV_FAKE_TTS"):
        for t, p in todo:
            _fake_voice(t, p)
            if on_line:
                on_line()
    else:
        try:
            asyncio.run(_speak_all([t for t, _ in todo], [p for _, p in todo],
                                   voice, rate, on_line))
        except Exception as e:
            _drop_unusable(todo)
            raise RenderError(
                "Could not reach the voice service. Check your internet "
                "connection and press Generate again; finished lines are kept "
                f"and will not be redone. ({type(e).__name__})") from e
    n = _drop_unusable(todo)
    if n:
        raise RenderError(
            f"The voice service returned nothing for {n} line"
            f"{'' if n == 1 else 's'}. Press Generate again to retry just "
            "those; every line that did come back is kept.")


def duration(path):
    """Length of an audio or video file in seconds.

    Raises RenderError rather than letting ffprobe's CalledProcessError out.
    An empty or truncated file reaching here used to surface as a traceback
    and, worse, stayed in the cache, so every retry failed the same way.
    """
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)], capture_output=True, text=True)
    try:
        if r.returncode != 0:
            raise ValueError(r.stderr.strip()[:200] or "ffprobe failed")
        return float(json.loads(r.stdout)["format"]["duration"])
    except (ValueError, KeyError, TypeError) as e:
        raise RenderError(
            f"The file {Path(path).name} is empty or damaged, so its length "
            "could not be measured. Delete it and press Generate again, and "
            f"it will be made afresh. ({e})") from e


def _rate_fraction(rate):
    try:
        return float(str(rate).strip().rstrip("%")) / 100
    except ValueError:
        return 0.0


def estimate_seconds(beats, rate=RATE):
    """WPM was measured at the default rate, so a different speaking rate
    scales the spoken part. The per-beat padding is fixed either way."""
    words = sum(len(b.get("say", "").split()) for b in beats)
    scale = (1 + _rate_fraction(RATE)) / (1 + _rate_fraction(rate))
    return words / WPM * 60 * scale + len(beats) * (LEAD_SILENCE + BREATH)


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
        # Each pass writes another full length uncompressed file, so keeping
        # them all costs the square of the video length: measured at 868 MB
        # of scratch for ten minutes, against 115 MB of actual bed. Dropping
        # the pass we have just consumed makes it linear. The audio is
        # untouched; this is bookkeeping, not a change to how it sounds.
        cur.unlink(missing_ok=True)
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


def animated(beat):
    """Whether this beat has a character in it to blink and speak."""
    from . import scenes
    return beat["visual"] in scenes.VISUALS


def variant_key(beat, theme):
    """Keyed on the drawing alone, with the narration left out, so rewording
    a line reuses its sprites and only the mouth track is measured again."""
    scene = {k: v for k, v in beat.items() if k != "say"}
    ident = json.dumps([ENGINE_V, scene, asdict(theme)], sort_keys=True)
    return hashlib.sha1(ident.encode()).hexdigest()


def segment_key(beat, theme, audio_key):
    ident = json.dumps([ENGINE_V, beat, asdict(theme), audio_key], sort_keys=True)
    return hashlib.sha1(ident.encode()).hexdigest()


PART_SECONDS = 150.0        # target length of one final-encode chunk
PART_FLOOR = 25.0           # shorter than this and the tail joins the part before


def part_ranges(seconds, target=None, floor=None):
    """Group beat durations into chunks of roughly `target` seconds.

    The final encode used to be one pass over the whole video, which is the
    longest single piece of work in a render and the one that has nothing
    finished to show if the machine gives up in the middle of it. Cutting it
    into parts caps that, and makes a second run resume rather than restart.

    Cuts land between beats and nowhere else, so a part can only end where the
    script had a paragraph break and the video already cut. A part cannot end
    part-way through a sentence, and rejoining is a stream copy across a seam
    that was there anyway. A short tail is folded back into the part before it
    rather than left as a two-second file.
    """
    target = PART_SECONDS if target is None else target
    floor = PART_FLOOR if floor is None else floor
    out, start, run = [], 0, 0.0
    for i, d in enumerate(seconds):
        run += d
        if run >= target and i + 1 < len(seconds):
            out.append((start, i + 1))
            start, run = i + 1, 0.0
    if start < len(seconds):
        out.append((start, len(seconds)))
    if len(out) > 1 and sum(seconds[out[-1][0]:]) < floor:
        out[-2:] = [(out[-2][0], out[-1][1])]
    return out


def _stamp(path):
    if not path or not path.exists():
        return "-"
    st = path.stat()
    return f"{st.st_size}:{int(st.st_mtime)}"


def part_key(seg_keys, logo, music, bed_at, first, last):
    """Everything the part's encode depends on, including where in the music
    bed it starts, so an edit that shifts a part along the track rebuilds it."""
    raw = json.dumps([ENGINE_V, list(seg_keys), _stamp(logo), _stamp(music),
                      round(bed_at, 2), first, last])
    return hashlib.sha1(raw.encode()).hexdigest()


def encode_part(dst, segs, work, logo, logo_until, bed, bed_at, length,
                fade_in, fade_out):
    """Compress one run of segments, with the corner logo and the slice of the
    music bed that belongs under it.

    The music fades up at the start of the video and down at the end of it, not
    at the end of every part: fading each part would put a hole in the track at
    every join. Everything in between reads its own stretch of one bed, so the
    music runs through the seam unbroken.
    """
    # The picture lands frame-exact across a join: parts of 17.633 and 25.500
    # seconds concatenate to the same 43.133 the unsplit render produces. The
    # audio ends a few milliseconds long on each part, because an aac frame is
    # 1024 samples and the stream has to end on one, so a join shifts sound
    # against picture by about four milliseconds. A frame is thirty-three.
    lst = work / "part.txt"
    lst.write_text("".join(f"file '{s.resolve()}'\n" for s in segs))
    joined = work / "part_joined.mkv"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c", "copy", str(joined)])

    inputs, filters, n = ["-i", str(joined)], [], 1
    vout = "0:v"
    if logo:
        inputs += ["-i", str(logo)]
        # the corner logo is hidden once the outro fills the frame with the big
        # one, and the outro time is measured from the start of this part
        show = (f":enable='lt(t,{logo_until:.3f})'"
                if logo_until is not None else "")
        filters.append(f"[{vout}][{n}:v]"
                       f"overlay=W-w-{LOGO_MARGIN_PX}:{LOGO_MARGIN_PX}{show}[v]")
        vout, n = "v", n + 1

    aout = "0:a"
    if bed:
        inputs += ["-ss", f"{bed_at:.3f}", "-t", f"{length:.3f}", "-i", str(bed)]
        fades = ["afade=t=in:st=0:d=2"] if fade_in else []
        if fade_out:
            fades.append(f"afade=t=out:st={max(length - 3, 0):.3f}:d=3")
        shape = "," + ",".join(fades) if fades else ""
        # The voice is used twice: once in the mix, once as the control signal
        # that pushes the music down. That is what sidechaincompress does, so
        # the bed lifts in the gaps between lines and drops under speech.
        filters.append(
            f"[{n}:a]volume={MUSIC_DB}dB{shape}[m];"
            f"[0:a]asplit=2[voice][key];"
            f"[m][key]sidechaincompress=threshold={DUCK_THRESHOLD}"
            f":ratio={DUCK_RATIO}:attack=15:release={DUCK_RELEASE}[duck];"
            f"[voice][duck]amix=inputs=2:duration=first"
            f":dropout_transition=0:normalize=0[a]")
        aout = "a"

    cmd = ["ffmpeg", "-y", *inputs]
    if filters:
        cmd += ["-filter_complex", ";".join(filters)]
    tmp = work / "part_tmp.mp4"
    cmd += ["-map", f"[{vout}]" if vout != "0:v" else vout,
            "-map", f"[{aout}]" if aout != "0:a" else aout,
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-shortest", str(tmp)]
    run(cmd)
    joined.unlink(missing_ok=True)
    shutil.move(str(tmp), dst)


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
    vardir = cache / "variants"
    mdir = cache / "mouth"
    for d in (out_dir, work, vdir, sdir, vardir, mdir):
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

    def variant(i, eyes, mouth):
        return vardir / f"{variant_key(beats[i], theme)}_{eyes}_{mouth}.png"

    for j, i in enumerate(missing):
        report("slides", j, len(missing))
        b = beats[i]
        if b["visual"] == "outro":
            b = {**b, "logo_big": str(work / "logo_big.png")}
        if animated(b):
            for eyes, mouth in animate.VARIANTS:
                p = variant(i, eyes, mouth)
                if not p.exists():
                    render_slide(b, p, theme, eyes, mouth)
        else:
            render_slide(b, work / f"slide_{i:02d}.png", theme)
    report("slides", len(missing), len(missing))

    for j, i in enumerate(missing):
        report("segments", j, len(missing))
        snd = paths[i]
        spoken = duration(snd)
        d = LEAD_SILENCE + spoken + BREATH
        frames = int(round(d * FPS))
        # zoompan works in whole pixels, so at 1080p the crop jumps a pixel at a
        # time and the slide looks shaky. Scaling up first makes each step a
        # fraction of an output pixel, and the downscale averages it away.
        prescale = f"scale={W * PRESCALE}:{H * PRESCALE}:flags=bilinear,"
        pan = f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS}"
        if animated(beats[i]):
            mouths = [*["closed"] * int(round(LEAD_SILENCE * FPS)),
                      *animate.cached_track(snd, FPS, mdir)]
            mouths = (mouths + ["closed"] * frames)[:frames]
            # the same line always blinks the same way, because the seed comes
            # from the line rather than from where it sits in the script
            blinks = animate.blink_frames(frames, FPS, int(keys[i][:8], 16))
            lst = work / f"frames_{i:02d}.txt"
            animate.frame_list(mouths, blinks,
                               lambda e, m: variant(i, e, m).resolve(), lst, FPS)
            src = ["-f", "concat", "-safe", "0", "-i", str(lst)]
            # zoompan holds each input frame for d output frames, so a sequence
            # needs d=1 or every frame after the first is dropped. At d=1 its
            # zoom accumulator restarts on each input frame, so the ramp is
            # counted from the output frame number instead.
            zoom = (prescale + f"zoompan=z='min(1+{ZOOM_RATE}*on,1.06)':d=1" + pan)
        else:
            src = ["-loop", "1", "-i", str(work / f"slide_{i:02d}.png")]
            zoom = (prescale
                    + f"zoompan=z='min(zoom+{ZOOM_RATE},1.06)':d={frames}" + pan)
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
        run(["ffmpeg", "-y", *src, "-i", str(snd),
             "-filter_complex", f"{vf};{af}",
             "-map", "[v]", "-map", "[a]",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
             "-r", str(FPS), "-c:a", "pcm_s16le", "-ac", "2",
             "-t", f"{d:.3f}", str(tmp)])
        shutil.move(str(tmp), segs[i])
    report("segments", len(missing), len(missing))
    clock, srt, seconds = 0.0, [], []
    outro_start = None
    for b, snd in zip(beats, paths):
        spoken = duration(snd)
        d = LEAD_SILENCE + spoken + BREATH
        if b["visual"] == "outro":
            outro_start = clock
        srt.append((clock + LEAD_SILENCE, clock + LEAD_SILENCE + spoken, b["say"]))
        seconds.append(d)
        clock += d

    ranges = part_ranges(seconds)
    report("final", 0, len(ranges))

    # One bed for the whole video, sliced per part, so the music carries across
    # a join instead of restarting. Building it once also keeps the loop and
    # crossfade cost the same as it was before parts existed.
    bed = (build_music_bed(music, work / "bed.wav", clock + 2, work)
           if music.exists() else None)

    pdir = cache / "parts"
    pdir.mkdir(parents=True, exist_ok=True)
    made, offset = [], 0.0
    for pi, (a, b) in enumerate(ranges):
        length, last = sum(seconds[a:b]), b == len(beats)
        key = part_key(seg_keys[a:b], logo, music, offset,
                       first=pi == 0, last=last)
        dst = pdir / f"{key}.mp4"
        if not dst.exists():
            encode_part(dst, segs[a:b], work,
                        logo=work / "logo_small.png" if logo.exists() else None,
                        logo_until=None if outro_start is None
                        else outro_start - offset,
                        bed=bed, bed_at=offset, length=length,
                        fade_in=pi == 0, fade_out=last)
        made.append(dst)
        offset += length
        report("final", pi + 1, len(ranges))

    final = out_dir / "final.mp4"
    if len(made) == 1:
        shutil.copy(made[0], final)
    else:
        # The parts were cut between beats and encoded to one profile, so the
        # join is a stream copy: no second generation of compression, and no
        # seam beyond the one the beat boundary already had.
        lst = work / "parts.txt"
        lst.write_text("".join(f"file '{s.resolve()}'\n" for s in made))
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
             "-c", "copy", "-movflags", "+faststart", str(final)])

    with open(out_dir / "final.srt", "w") as f:
        for k, (a, bb, txt) in enumerate(srt, 1):
            body = "\n".join(textwrap.wrap(txt, 52))
            f.write(f"{k}\n{srt_time(a)} --> {srt_time(bb)}\n{body}\n\n")

    return {"video": final, "srt": out_dir / "final.srt", "seconds": clock,
            "parts": len(made)}
