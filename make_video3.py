#!/usr/bin/env python3
"""
Builds "5 Things I Wish I Knew About Money" as a narrated explainer video.

No API keys. No paid services. Everything runs locally except the TTS call,
which uses Microsoft's free edge-tts endpoint.

Pipeline:
  1. Each beat of the script is spoken by edge-tts  -> beat_NN.mp3
  2. Real audio duration is measured with ffprobe
  3. A 1920x1080 slide is drawn for each beat with matplotlib
  4. ffmpeg pairs slide + audio into a fast intermediate segment
     (slow zoom, fade in and out on video and audio)
  5. Segments are joined, then ONE final encode adds the corner logo,
     optional music, and a subscribe end card
  6. An .srt subtitle file is written alongside it

Run:  python make_video3.py
Out:  out/final.mp4  and  out/final.srt

Optional files, dropped in the same folder:
  logo.png    masked to a circle, shown top right for the whole video
              and full size on the outro card
  music.mp3   mixed in quietly under the voice (voice level is preserved)
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import matplotlib.patheffects as pe
import numpy as np
from PIL import Image

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------

VOICE = "en-US-AndrewMultilingualNeural"   # warm, conversational
RATE = "-4%"                                # slightly slowed for the "neighbor" tone
W, H = 1920, 1080
FPS = 30
OUT = Path("out")
WORK = Path("work")

# Warm cream + gold and teal
BG      = "#faf6ec"   # page cream
PANEL   = "#f3ecdc"   # callout panel, slightly deeper than the page
FG      = "#1d1b16"   # near black body text
DIM     = "#7a7266"   # captions and axis labels
GOLD    = "#c8912c"   # primary accent
GOLD_HI = "#9c6d16"   # darker gold, for text that must stay readable
GOLD_PALE = "#f0dfae"  # fills and halos
TEAL    = "#0f766e"   # secondary accent
TEAL_HI = "#0b524c"
TEAL_PALE = "#cfe7e3"
GRID    = "#e0d8c6"

LOGO = "logo.png"
LOGO_CORNER_PX = 150        # height of the small corner logo
LOGO_MARGIN_PX = 40         # distance from the top and right edges
MUSIC = "music.mp3"
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

# ----------------------------------------------------------------------
# THE SCRIPT
# One beat = one slide + one chunk of narration.
# Edit the "say" text freely; nothing below depends on the wording.
# ----------------------------------------------------------------------

BEATS = [
    # ---- HOOK ----
    dict(visual="sweep",
         say="Nobody sat me down and explained money. I had to figure it out the hard "
             "way, through mistakes that cost me years, so you don't have to make them "
             "too."),

    dict(visual="title", headline="5 COSTLY\nMONEY MISTAKES",
         sub="Things nobody sat me down and explained",
         say="Five costly money mistakes."),

    # ---- LESSON 1 ----
    dict(visual="chapter", num="01", headline="YOUR CREDIT SCORE\nSTARTS EARLY",
         say="Here's the first thing nobody told me. Your credit score isn't something "
             "you deal with later. It starts building the moment you step into a new "
             "financial system, and if you wait, you're already behind."),

    dict(visual="gauge", headline="IT'S ALREADY RUNNING",
         say="I used to think that avoiding debt meant I had good credit. But no debt "
             "isn't the same as good credit."),

    dict(visual="callout", headline="NO CREDIT  \u2260  GOOD CREDIT",
         say="You actually need a track record of using credit responsibly and paying "
             "it back on time."),

    dict(visual="timeline", headline="THE CLOCK STARTS AT DAY ONE",
         say="Waiting to stay safe can leave you with zero credit history, which makes "
             "getting an apartment or a loan ten times harder."),

    # ---- LESSON 2 ----
    dict(visual="chapter", num="02", headline='"SAVE WHAT\'S LEFT OVER"\nIS NOT A PLAN',
         say="Second lesson. Saving whatever happens to be left at the end of the month "
             "is backwards. That's not a plan. That's an accident waiting to happen."),

    dict(visual="jars", headline="FLIP THE ORDER",
         say="What actually works is deciding your savings amount first. Treat your "
             "savings like a non-negotiable bill you have to pay on payday."),

    dict(visual="callout", headline="PAY YOURSELF FIRST",
         say="Let whatever remains after that be your actual spending money. Flip the "
             "order, and everything changes."),

    # ---- LESSON 3 ----
    dict(visual="chapter", num="03", headline="NEW FINANCIAL SYSTEMS\nTAKE TIME",
         say="If you've ever moved somewhere new, a new state, a new country, or just a "
             "new stage of life, you know financial systems don't come with an "
             "instruction manual."),

    dict(visual="terms", headline="A BRAND NEW VOCABULARY",
         say="Terms like A.P.R., credit utilization, or escrow get thrown at you like "
             "you're already supposed to know them."),

    dict(visual="path", headline="YOU'RE NOT BAD WITH MONEY",
         sub="You're learning a language.",
         say="It is completely normal to feel lost at first. You aren't bad with money. "
             "You're just learning a brand new vocabulary."),

    # ---- LESSON 4 ----
    dict(visual="chapter", num="04", headline="BORING CONSISTENCY BEATS\nEXCITING RISKS",
         say="Fourth lesson. The boring stuff always wins. Not the hot stock tip from a "
             "friend. Not the trending side hustle everyone's talking about this week."),

    dict(visual="growth", headline="SMALL, AUTOMATIC, EVERY PAYCHECK",
         say="Consistently setting aside a small, manageable amount automatically every "
             "single paycheck. That's what actually builds wealth."),

    dict(visual="callout", headline="AUTOMATION  >  EMOTION",
         say="Quiet consistency isn't exciting content, but it works."),

    # ---- LESSON 5 ----
    dict(visual="chapter", num="05", headline="ASKING QUESTIONS\nIS STRENGTH",
         say="And finally. Asking questions about money isn't embarrassing."),

    dict(visual="quiet", headline="SILENCE IS EXPENSIVE",
         say="I used to nod along in conversations I didn't understand because I didn't "
             "want to look behind. That silence cost me far more than just asking would "
             "have."),

    dict(visual="callout", headline="NEVER ASSUME. ALWAYS ASK.",
         say="There are no basic or silly questions when it comes to your financial "
             "future."),

    # ---- RECAP ----
    dict(visual="recap", headline="THE FIVE",
         say="To wrap it up. Build your credit early. Save first instead of last. Give "
             "yourself grace when learning new systems. Pick boring consistency over "
             "hype. And never be afraid to ask questions."),

    # ---- OUTRO ----
    dict(visual="outro", headline="NEXT WEEK", sub="How credit scores actually work",
         say="Next week, we're breaking down step by step how credit scores actually "
             "work, and how to build yours from scratch. Hit subscribe so you don't "
             "miss it, and I'll see you next door."),
]

# ----------------------------------------------------------------------
# DRAWING HELPERS
# ----------------------------------------------------------------------

def _fig():
    return plt.figure(figsize=(W / 100, H / 100), dpi=100, facecolor=BG)


HEAD_MAX_W = 1480   # px; leaves the top right corner clear for the logo


def _headline(fig, text, y=0.87, size=58, color=FG):
    """Draw a centred headline, shrinking it if it would reach the logo."""
    t = fig.text(0.5, y, text, ha="center", va="top", fontsize=size,
                 color=color, fontweight="bold", linespacing=1.18)
    fig.canvas.draw()
    w = t.get_window_extent(fig.canvas.get_renderer()).width
    if w > HEAD_MAX_W:
        t.set_fontsize(max(28, size * HEAD_MAX_W / w))
    return t


def _sub(fig, text, y=0.17, size=30, color=DIM):
    if text:
        fig.text(0.5, y, text, ha="center", va="center", fontsize=size, color=color)


def _rule(fig, y=0.79, w=0.10, color=GOLD, lw=4):
    ax = fig.add_axes([0.5 - w / 2, y, w, 0.002])
    ax.plot([0, 1], [0, 0], color=color, lw=lw, solid_capstyle="round")
    ax.axis("off")


def _axes(fig, rect=(0.13, 0.22, 0.74, 0.48)):
    ax = fig.add_axes(rect)
    ax.set_facecolor(BG)
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.tick_params(colors=DIM, labelsize=18)
    ax.grid(True, color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    return ax


def _glow(txt, color=GOLD_PALE, n=6):
    """A pale halo so large type separates from the cream page."""
    txt.set_path_effects([pe.withStroke(linewidth=n, foreground=color, alpha=0.85)])


def make_round_logo(src, dst, size):
    """Crop the square logo to a circle with a transparent outside.

    The source PNG has solid black corners. Over the charcoal background those
    show as a dark square, so we build an alpha channel from the distance to
    the centre and write a real RGBA file.
    """
    im = Image.open(src).convert("RGBA").resize((size, size), Image.LANCZOS)
    yy, xx = np.mgrid[0:size, 0:size]
    c = (size - 1) / 2
    r = np.hypot(xx - c, yy - c)
    edge = size / 2 - 1.5                       # just inside the gold ring
    alpha = np.clip((edge - r) / 1.5 + 1, 0, 1)  # 1.5 px soft edge
    a = np.array(im)
    a[..., 3] = (a[..., 3] * alpha).astype(np.uint8)
    Image.fromarray(a, "RGBA").save(dst)


# ----------------------------------------------------------------------
# SLIDES
# ----------------------------------------------------------------------

def v_sweep(fig, b):
    """Gold light sweeping across a dark surface. Soft falloff on both axes."""
    from matplotlib.colors import LinearSegmentedColormap
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    xn = np.linspace(0, 1, 480)[None, :]
    yn = np.linspace(0, 1, 270)[:, None]
    field = (np.exp(-((xn - 0.50) ** 2) / 0.22)
             * np.exp(-((yn - 0.46) ** 2) / 0.045))
    cmap = LinearSegmentedColormap.from_list("g", [BG, GOLD_PALE, GOLD])
    ax.imshow(field, aspect="auto", cmap=cmap, extent=[0, 1, 0, 1],
              vmin=0, vmax=1.35, interpolation="bilinear")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    fig.text(0.5, 0.53, "Nobody sat me down", ha="center", va="center",
             fontsize=64, color=FG, fontweight="bold")
    fig.text(0.5, 0.40, "and explained money.", ha="center", va="center",
             fontsize=64, color=FG, fontweight="bold")


def v_title(fig, b):
    ax = fig.add_axes([0, 0.44, 1, 0.02]); ax.axis("off")
    _headline(fig, b["headline"], y=0.70, size=96, color=FG)
    _rule(fig, y=0.40, w=0.16)
    _sub(fig, b.get("sub"), y=0.31, size=32)


def v_chapter(fig, b):
    t = fig.text(0.5, 0.72, b["num"], ha="center", va="center",
                 fontsize=150, color=GOLD, fontweight="bold")
    _glow(t, n=10)
    _rule(fig, y=0.55, w=0.08)
    _headline(fig, b["headline"], y=0.47, size=68)


def v_gauge(fig, b):
    _headline(fig, b["headline"])
    ax = fig.add_axes([0.26, 0.30, 0.48, 0.48], projection="polar")
    ax.set_facecolor("none")
    ax.set_theta_offset(np.pi)
    ax.set_theta_direction(-1)
    ax.set_thetamin(0); ax.set_thetamax(180)
    ax.set_rticks([]); ax.set_xticks([])
    ax.spines["polar"].set_visible(False)
    ax.grid(False)
    th = np.linspace(0, np.pi, 400)
    ax.plot(th, np.ones_like(th), color=GRID, lw=40, solid_capstyle="round")
    # colour ramps along the arc so the gauge reads as a scale, not one block
    fill = th[th <= np.pi * 0.78]
    for i in range(len(fill) - 1):
        f = i / max(len(fill) - 1, 1)
        col = (0.78 * (1 - f) + 0.06 * f,     # gold -> teal
               0.57 * (1 - f) + 0.46 * f,
               0.17 * (1 - f) + 0.43 * f)
        ax.plot(fill[i:i + 2], [1, 1], color=col, lw=40, solid_capstyle="butt")
    ax.set_ylim(0, 1.22)
    t = fig.text(0.5, 0.30, "742", ha="center", va="center",
                 fontsize=104, color=TEAL, fontweight="bold")
    _glow(t, n=9)
    fig.text(0.26, 0.31, "300", ha="center", fontsize=24, color=DIM)
    fig.text(0.74, 0.31, "850", ha="center", fontsize=24, color=DIM)
    fig.text(0.5, 0.17, "Building from the day you start, not the day you need it",
             ha="center", fontsize=24, color=DIM)


def v_callout(fig, b):
    ax = fig.add_axes([0.08, 0.40, 0.84, 0.20])
    ax.set_facecolor(TEAL_PALE)
    for s in ax.spines.values():
        s.set_color(TEAL)
        s.set_linewidth(2.5)
    ax.set_xticks([]); ax.set_yticks([])
    txt = b["headline"]
    # bold caps run about 0.97 px per point per character at this dpi;
    # keep the line inside 1440 px of the 1613 px panel
    size = min(72, int(1440 / (max(len(txt), 1) * 0.97)))
    t = fig.text(0.5, 0.50, txt, ha="center", va="center",
                 fontsize=size, color=TEAL_HI, fontweight="bold")


def v_timeline(fig, b):
    _headline(fig, b["headline"])
    ax = _axes(fig)
    x = np.arange(0, 121)
    y = 300 + 550 * (1 - np.exp(-x / 34))
    ax.plot(x, y, color=TEAL, lw=6)
    ax.fill_between(x, 300, y, color=TEAL, alpha=0.13)
    ax.axvline(0, color=GOLD, lw=2.5, ls=":")
    ax.annotate("Day 1", xy=(0, 300), xytext=(9, 380),
                color=FG, fontsize=24, fontweight="bold")
    ax.set_xlabel("Months of credit history", color=DIM, fontsize=22, labelpad=12)
    ax.set_ylabel("Score", color=DIM, fontsize=22, labelpad=12)
    ax.set_ylim(250, 900)
    ax.set_xticks([0, 24, 48, 72, 96, 120])
    fig.text(0.5, 0.09, "Illustrative shape, not a prediction of your score",
             ha="center", fontsize=19, color=DIM)


def v_jars(fig, b):
    _headline(fig, b["headline"])
    ax = fig.add_axes([0.08, 0.16, 0.84, 0.56]); ax.axis("off")
    ax.set_xlim(0, 10); ax.set_ylim(0, 6)
    rng = np.random.default_rng(7)

    # left: scattered
    ax.text(2.5, 5.4, "Save what's left", ha="center", fontsize=30, color=DIM,
            fontweight="bold")
    xs = rng.uniform(0.6, 4.4, 26); ys = rng.uniform(0.4, 4.2, 26)
    ax.scatter(xs, ys, s=340, color=GOLD_PALE, alpha=0.9, edgecolors=DIM, lw=1.5)

    ax.plot([5, 5], [0.2, 5.0], color=GRID, lw=2.5)

    # right: stacked in a jar
    ax.text(7.5, 5.4, "Pay yourself first", ha="center", fontsize=30,
            color=TEAL, fontweight="bold")
    ax.plot([6.3, 6.3, 8.7, 8.7], [4.4, 0.5, 0.5, 4.4], color=TEAL, lw=4, alpha=0.85)
    for row in range(7):
        for col in range(3):
            ax.scatter(6.85 + col * 0.6, 0.85 + row * 0.5, s=340,
                       color=GOLD, edgecolors=GOLD_HI, lw=1.5, zorder=3)


def v_terms(fig, b):
    _headline(fig, b["headline"])
    spots = [(0.22, 0.56, "APR?"), (0.50, 0.62, "FICO?"), (0.78, 0.55, "ESCROW?"),
             (0.34, 0.36, "UTILIZATION?"), (0.68, 0.34, "APY?")]
    for i, (x, y, word) in enumerate(spots):
        col = TEAL if i % 2 else GOLD_HI
        t = fig.text(x, y, word, ha="center", va="center", fontsize=44,
                     color=col, fontweight="bold")
        t.set_bbox(dict(boxstyle="round,pad=0.45",
                        facecolor=TEAL_PALE if i % 2 else GOLD_PALE,
                        edgecolor="none"))
    fig.text(0.5, 0.17, "None of this was ever explained",
             ha="center", fontsize=28, color=DIM)


def v_path(fig, b):
    _headline(fig, b["headline"])
    ax = fig.add_axes([0.10, 0.20, 0.80, 0.50]); ax.axis("off")
    ax.set_xlim(-5, 5); ax.set_ylim(0, 5)
    VY = 4.05                       # vanishing point height

    def half_width(t):              # t = 0 at viewer, 1 at horizon
        return 4.3 * (1 - t) ** 1.6 + 0.02

    # horizon band, so the road sits on ground instead of floating as a shape
    ax.fill_between([-5, 5], VY, 5, color=TEAL_PALE, alpha=0.55, zorder=0)
    ax.plot([-5, 5], [VY, VY], color=TEAL, lw=1.6, alpha=0.55, zorder=1)

    # soft glow at the vanishing point, drawn as a gradient so it has no hard rim
    from matplotlib.colors import LinearSegmentedColormap
    gx = np.linspace(-2.2, 2.2, 300)[None, :]
    gy = np.linspace(-1.4, 1.4, 200)[:, None]
    glow = np.exp(-(gx ** 2) / 0.65) * np.exp(-(gy ** 2) / 0.28)
    ax.imshow(glow, extent=[-2.2, 2.2, VY - 1.4, VY + 1.4], origin="lower",
              aspect="auto", zorder=0, interpolation="bilinear", vmin=0, vmax=2.2,
              cmap=LinearSegmentedColormap.from_list(
                  "gl", [(0.784, 0.569, 0.173, 0.0),
                         (0.941, 0.875, 0.682, 0.75),
                         (0.784, 0.569, 0.173, 0.95)]))

    # road surface: faint, fading out before the horizon
    n = 60
    for i in range(n):
        t0, t1 = i / n, (i + 1) / n
        y0, y1 = t0 * VY, t1 * VY
        w0, w1 = half_width(t0), half_width(t1)
        ax.fill([-w0, w0, w1, -w1], [y0, y0, y1, y1],
                color="#d8cdb4", alpha=0.30 + 0.45 * (1 - t0), lw=0, zorder=1)

    # the two edges, brightening toward the viewer
    for i in range(n):
        t0, t1 = i / n, (i + 1) / n
        a = 0.20 + 0.75 * (1 - t0) ** 0.9
        for s in (-1, 1):
            ax.plot([s * half_width(t0), s * half_width(t1)], [t0 * VY, t1 * VY],
                    color=TEAL, lw=1.0 + 3.4 * (1 - t0), alpha=a,
                    solid_capstyle="round", zorder=3)

    # centre dashes
    for t in np.arange(0.03, 0.92, 0.105):
        seg = 0.055 * (1 - t) + 0.004
        ax.plot([0, 0], [t * VY, (t + seg) * VY], color=GOLD,
                lw=1.0 + 3.0 * (1 - t), alpha=0.30 + 0.55 * (1 - t),
                solid_capstyle="round", zorder=3)

    # signposts, shrinking as they recede
    for t, side in ((0.10, -1), (0.36, 1), (0.60, -1)):
        y, w = t * VY, half_width(t)
        x = side * (w + 0.40)
        h = 1.15 * (1 - t) ** 1.3 + 0.06
        ax.plot([x, x], [y, y + h], color=DIM, lw=1.0 + 2.2 * (1 - t), zorder=4)
        ax.scatter([x], [y + h], s=420 * (1 - t) ** 1.6 + 25, color=GOLD_PALE,
                   marker="s", edgecolors=GOLD_HI, lw=1.0 + 1.4 * (1 - t), zorder=4)

    _sub(fig, b.get("sub"), y=0.14, size=32, color=TEAL)


def v_growth(fig, b):
    _headline(fig, b["headline"])
    ax = _axes(fig, rect=(0.13, 0.24, 0.74, 0.44))
    yrs = np.arange(1, 21)
    r, monthly = 0.07, 250.0
    bal, vals = 0.0, []
    for _ in yrs:
        for _m in range(12):
            bal = bal * (1 + r / 12) + monthly
        vals.append(bal)
    vals = np.array(vals)
    # bars ramp teal -> gold left to right so the growth reads at a glance
    cols = []
    for i in range(len(yrs)):
        f = i / (len(yrs) - 1)
        cols.append((0.06 * (1 - f) + 0.78 * f,
                     0.46 * (1 - f) + 0.57 * f,
                     0.43 * (1 - f) + 0.17 * f))
    ax.bar(yrs, vals / 1000, color=cols, width=0.68, edgecolor="none")
    ax.set_xlabel("Years", color=DIM, fontsize=22, labelpad=12)
    ax.set_ylabel("Balance ($ thousands)", color=DIM, fontsize=22, labelpad=12)
    ax.set_xticks([1, 5, 10, 15, 20])
    ax.text(1.2, vals[-1] / 1000 * 0.86, f"${vals[-1]:,.0f}\nafter 20 years",
            fontsize=28, color=TEAL_HI, fontweight="bold", va="top")
    fig.text(0.5, 0.11, "$250/month at a 7% average annual return, illustrative only",
             ha="center", fontsize=19, color=DIM)


def v_quiet(fig, b):
    _headline(fig, b["headline"], y=0.62, size=76, color=FG)
    _rule(fig, y=0.44, w=0.12)
    fig.text(0.5, 0.34, "Nodding along is not understanding.",
             ha="center", fontsize=32, color=TEAL)


def v_recap(fig, b):
    _headline(fig, b["headline"], y=0.88, size=56, color=GOLD_HI)
    items = [
        "Build your credit early",
        "Save first, not last",
        "Give yourself grace",
        "Boring beats hype",
        "Always ask",
    ]
    for i, it in enumerate(items):
        y = 0.66 - i * 0.115
        fig.text(0.30, y, f"0{i + 1}", ha="right", va="center",
                 fontsize=38, color=TEAL if i % 2 else GOLD_HI, fontweight="bold")
        fig.text(0.35, y, it, ha="left", va="center", fontsize=42, color=FG)


def v_outro(fig, b):
    big = WORK / "logo_big.png"
    if big.exists():
        img = mpimg.imread(big)
        # 62% of frame height, centred horizontally, sitting in the upper half
        h = 0.62
        w = h * H / W
        ax = fig.add_axes([0.5 - w / 2, 0.34, w, h]); ax.axis("off")
        ax.imshow(img)
    else:
        t = fig.text(0.5, 0.68, "NDN", ha="center", va="center",
                     fontsize=110, color=GOLD_HI, fontweight="bold")
        _glow(t, n=10)
        fig.text(0.5, 0.575, "NEXT DOOR NEIGHBOR", ha="center",
                 fontsize=24, color=DIM)
    _rule(fig, y=0.30, w=0.10)
    _headline(fig, b["headline"], y=0.265, size=36, color=DIM)
    _sub(fig, b.get("sub"), y=0.175, size=40, color=FG)
    t = fig.text(0.5, 0.08, "SUBSCRIBE", ha="center", fontsize=28, color="#ffffff",
                 fontweight="bold")
    t.set_bbox(dict(boxstyle="round,pad=0.6", facecolor=TEAL, edgecolor="none"))


VISUALS = {
    "sweep": v_sweep, "title": v_title, "chapter": v_chapter, "gauge": v_gauge,
    "callout": v_callout, "timeline": v_timeline, "jars": v_jars, "terms": v_terms,
    "path": v_path, "growth": v_growth, "quiet": v_quiet, "recap": v_recap,
    "outro": v_outro,
}


def render_slide(beat, path):
    fig = _fig()
    VISUALS[beat["visual"]](fig, beat)
    fig.savefig(path, facecolor=BG, dpi=100)
    plt.close(fig)


# ----------------------------------------------------------------------
# AUDIO
# ----------------------------------------------------------------------

async def _speak_all(beats, paths):
    import edge_tts
    sem = asyncio.Semaphore(TTS_PARALLEL)

    async def one(beat, p):
        async with sem:
            c = edge_tts.Communicate(beat["say"], VOICE, rate=RATE)
            await c.save(str(p))
            print(f"  voiced {p.name}")

    await asyncio.gather(*(one(b, p) for b, p in zip(beats, paths)))


def duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


# ----------------------------------------------------------------------
# BUILD
# ----------------------------------------------------------------------

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"command failed:\n  {' '.join(cmd)}\n\n{r.stderr[-3000:]}")


def build_music_bed(src, dst, need):
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

    cur = WORK / "bed_00.wav"
    run(["ffmpeg", "-y", "-i", str(src), "-ar", "48000", "-ac", "2", str(cur)])
    total, n = have, 0
    while total < need:
        n += 1
        nxt = WORK / f"bed_{n:02d}.wav"
        run(["ffmpeg", "-y", "-i", str(cur), "-i", str(src),
             "-filter_complex",
             f"[1:a]aresample=48000,aformat=channel_layouts=stereo[b];"
             f"[0:a][b]acrossfade=d={LOOP_XFADE}:c1=tri:c2=tri[a]",
             "-map", "[a]", "-ar", "48000", "-ac", "2", str(nxt)])
        cur = nxt
        total += have - LOOP_XFADE
        print(f"  music bed now {total:.0f}s of {need:.0f}s")
    shutil.move(str(cur), dst)
    return dst


def srt_time(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}"


def main():
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found. Run: sudo apt update && sudo apt install -y ffmpeg")

    for d in (OUT, WORK):
        d.mkdir(exist_ok=True)

    have_logo = Path(LOGO).exists()
    if have_logo:
        make_round_logo(LOGO, WORK / "logo_big.png", 1080)
        make_round_logo(LOGO, WORK / "logo_small.png", LOGO_CORNER_PX)
    else:
        print(f"  note: {LOGO} not found, using text fallback on the outro")

    audio = [WORK / f"beat_{i:02d}.mp3" for i in range(len(BEATS))]
    print("1/4  generating voiceover")
    asyncio.run(_speak_all(BEATS, audio))

    print("2/4  drawing slides")
    slides = []
    for i, beat in enumerate(BEATS):
        p = WORK / f"slide_{i:02d}.png"
        render_slide(beat, p)
        slides.append(p)

    print("3/4  building segments")
    segs, clock, srt = [], 0.0, []
    outro_start = None
    for i, (beat, img, snd) in enumerate(zip(BEATS, slides, audio)):
        spoken = duration(snd)
        d = LEAD_SILENCE + spoken + BREATH
        if beat["visual"] == "outro":
            outro_start = clock
        seg = WORK / f"seg_{i:02d}.mp4"
        frames = int(round(d * FPS))
        # zoompan works in whole pixels, so at 1080p the crop jumps a pixel at a
        # time and the slide looks shaky. Scaling up first makes each step a
        # fraction of an output pixel, and the downscale averages it away.
        zoom = (f"scale={W * PRESCALE}:{H * PRESCALE}:flags=bilinear,"
                f"zoompan=z='min(zoom+{ZOOM_RATE},1.06)':d={frames}"
                f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS}")
        # fades go to the page colour, not black, or the light theme flashes dark
        fade_col = BG.lstrip("#")
        vf = (f"[0:v]{zoom},fade=t=in:st=0:d={FADE}:color=0x{fade_col},"
              f"fade=t=out:st={d - FADE:.3f}:d={FADE}:color=0x{fade_col},"
              f"format=yuv420p[v]")
        # lead-in silence stops the first consonant being clipped by mp3 padding
        af = (f"[1:a]adelay={int(LEAD_SILENCE * 1000)}|{int(LEAD_SILENCE * 1000)},"
              f"aresample=48000,apad,atrim=0:{d:.3f},"
              f"afade=t=out:st={d - 0.25:.3f}:d=0.25[a]")
        # fast intermediate encode; the final pass does the real compression
        run(["ffmpeg", "-y", "-loop", "1", "-i", str(img), "-i", str(snd),
             "-filter_complex", f"{vf};{af}",
             "-map", "[v]", "-map", "[a]",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
             "-r", str(FPS), "-c:a", "pcm_s16le", "-ac", "2",
             "-t", f"{d:.3f}", str(seg)])
        segs.append(seg)
        srt.append((clock + LEAD_SILENCE, clock + LEAD_SILENCE + spoken, beat["say"]))
        clock += d
        print(f"  segment {i + 1}/{len(BEATS)}  ({d:.1f}s)")

    print("4/4  final encode (logo, music, fades)")
    lst = WORK / "concat.txt"
    lst.write_text("".join(f"file '{s.resolve()}'\n" for s in segs))
    joined = WORK / "joined.mkv"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c", "copy", str(joined)])

    final = OUT / "final.mp4"
    inputs = ["-i", str(joined)]
    filters = []
    vin = "[0:v]"
    n = 1

    if have_logo:
        inputs += ["-i", str(WORK / "logo_small.png")]
        # corner logo for the whole video except the outro, where the big one is
        show = f":enable='lt(t,{outro_start:.3f})'" if outro_start is not None else ""
        filters.append(f"{vin}[{n}:v]overlay=W-w-{LOGO_MARGIN_PX}:{LOGO_MARGIN_PX}{show}[v]")
        vin = "[v]"
        n += 1

    if Path(MUSIC).exists():
        bed = build_music_bed(MUSIC, WORK / "bed.wav", clock + 2)
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
    cmd += ["-map", vin if filters and have_logo else "0:v", "-map", aout,
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", "-shortest", str(final)]
    run(cmd)

    with open(OUT / "final.srt", "w") as f:
        for k, (a, bb, txt) in enumerate(srt, 1):
            body = "\n".join(textwrap.wrap(txt, 52))
            f.write(f"{k}\n{srt_time(a)} --> {srt_time(bb)}\n{body}\n\n")

    print(f"\ndone  {final}  ({clock / 60:.1f} min)")
    print(f"      {OUT / 'final.srt'}")


if __name__ == "__main__":
    main()
