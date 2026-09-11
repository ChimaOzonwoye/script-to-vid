"""Weather and atmosphere: a layer of moving particles over the whole frame.

Everything else here is drawn once per beat and held still apart from a slow
zoom, because a still frame is cheap and a moving one is not. Rain cannot work
that way: it has to move every frame or it is a texture.

So the layer is generated once as a short loop of transparent frames and the
same loop plays under every beat. Seamlessness is the whole problem. A
particle has to arrive back exactly where it started after the last frame, and
that is not something you get by picking a nice-looking speed: the distance
travelled over the loop has to be a whole number of wrap periods. Laps are
therefore integers and speed is chosen by choosing laps, not the other way
round. Anything that sways or twinkles does it a whole number of times.

Each effect owns its frame count, because the loop length is what sets the
slowest believable speed: a mote of dust crossing the frame in two seconds is
not dust. Effects return a function of the frame number rather than a list, so
that frame(0) and frame(n) can be compared and the loop proved to close.

Frames are generated at half size and scaled up at composite time. Particles
are soft and out of focus by nature, so nothing is lost and it costs a quarter
of the memory.
"""

import hashlib

import numpy as np
from PIL import Image, ImageDraw

from .themes import mix

W, H = 960, 540
SEED = 20260911          # fixed, so a rebuild produces the same weather


def _rng():
    return np.random.default_rng(SEED)


def _blob(radius):
    """A soft round dot, built once and pasted wherever a particle goes."""
    n = int(radius * 2) + 1
    y, x = np.mgrid[0:n, 0:n]
    c = (n - 1) / 2
    d = np.sqrt((x - c) ** 2 + (y - c) ** 2) / max(radius, 0.5)
    return np.clip(1.0 - d, 0.0, 1.0) ** 1.6


def _paste(field, blob, cx, cy):
    """Add a dot into the alpha field, clipped at the edges."""
    n = blob.shape[0]
    x0, y0 = int(cx - n // 2), int(cy - n // 2)
    x1, y1 = x0 + n, y0 + n
    sx0, sy0 = max(0, -x0), max(0, -y0)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(W, x1), min(H, y1)
    if x1 <= x0 or y1 <= y0:
        return
    field[y0:y1, x0:x1] += blob[sy0:sy0 + y1 - y0, sx0:sx0 + x1 - x0]


def _falling(n_particles, laps_choices, rng):
    """Shared setup for anything that travels and wraps."""
    return {
        "x": rng.uniform(0, 1, n_particles) * W,
        "y": rng.uniform(0, 1, n_particles) * H,
        # laps are whole numbers, so speed varies in steps and the loop closes
        "laps": rng.choice(laps_choices, n_particles),
        "cycles": rng.integers(1, 4, n_particles),
        "phase": rng.uniform(0, 2 * np.pi, n_particles),
    }


# ----------------------------------------------------------------------
# Each effect returns (frames, colour, field) where field(f) is the alpha
# for frame f. field(frames) must equal field(0).


def rain(T):
    """Slanted streaks at two speeds, so the field has depth."""
    rng = _rng()
    n, frames, period = 210, 45, H + 60
    p = _falling(n, (2, 3, 4), rng)
    length = 14 + 11 * p["laps"]
    slant = 0.28
    colour = mix(T.bg, "#ffffff", 0.78)

    def field(f):
        t = f / frames
        im = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(im)
        for i in range(n):
            yy = (p["y"][i] + t * period * p["laps"][i]) % period - 30
            xx = (p["x"][i] + yy * slant) % (W + 120) - 60
            d.line([(xx, yy), (xx - length[i] * slant, yy - length[i])],
                   fill=int(45 + 34 * p["laps"][i]),
                   width=1 if p["laps"][i] < 4 else 2)
        return np.asarray(im, dtype=np.float32) / 255.0

    return frames, colour, field


def snow(T):
    """Flakes drifting down, swaying a whole number of times on the way."""
    rng = _rng()
    n, frames, period = 180, 90, H + 40
    p = _falling(n, (1, 2), rng)
    size = rng.uniform(1.2, 4.2, n)
    sway = rng.uniform(8, 26, n)
    blobs = [_blob(s) for s in size]
    colour = mix(T.bg, "#ffffff", 0.92)

    def field(f):
        t = f / frames
        out = np.zeros((H, W), dtype=np.float32)
        for i in range(n):
            yy = (p["y"][i] + t * period * p["laps"][i]) % period - 20
            xx = (p["x"][i] + sway[i] * np.sin(
                2 * np.pi * p["cycles"][i] * t + p["phase"][i])) % W
            _paste(out, blobs[i] * (0.30 + 0.12 * size[i]), xx, yy)
        return out

    return frames, colour, field


def dust(T):
    """Motes hanging in a shaft of light. The loop is long because one lap of
    the frame in two seconds is not dust, it is rain."""
    rng = _rng()
    n, frames, period = 140, 150, H
    p = _falling(n, (1,), rng)
    size = rng.uniform(1.0, 3.4, n)
    blobs = [_blob(s) for s in size]
    colour = mix(T.bg, T.a1, 0.85)

    def field(f):
        t = f / frames
        out = np.zeros((H, W), dtype=np.float32)
        for i in range(n):
            yy = (p["y"][i] - t * period * p["laps"][i]) % period
            xx = (p["x"][i] + 18 * np.sin(
                2 * np.pi * p["cycles"][i] * t + p["phase"][i])) % W
            _paste(out, blobs[i] * (0.16 + 0.10 * size[i]), xx, yy)
        return out

    return frames, colour, field


def embers(T):
    """Sparks rising and flickering, for anything with heat in it."""
    rng = _rng()
    n, frames, period = 110, 90, H + 40
    p = _falling(n, (1, 2), rng)
    size = rng.uniform(1.1, 3.1, n)
    blobs = [_blob(s) for s in size]
    colour = mix(T.a1, "#ffffff", 0.35)

    def field(f):
        t = f / frames
        out = np.zeros((H, W), dtype=np.float32)
        for i in range(n):
            yy = (p["y"][i] - t * period * p["laps"][i]) % period - 20
            xx = (p["x"][i] + 22 * np.sin(
                2 * np.pi * p["cycles"][i] * t + p["phase"][i])) % W
            flick = 0.55 + 0.45 * np.sin(
                2 * np.pi * (p["cycles"][i] + 1) * t + p["phase"][i])
            _paste(out, blobs[i] * (0.30 + 0.16 * size[i]) * flick, xx, yy)
        return out

    return frames, colour, field


def bokeh(T):
    """Big soft circles drifting out of focus, the way a shallow lens sees
    lights behind the subject."""
    rng = _rng()
    n, frames, period = 26, 150, H + 120
    p = _falling(n, (1,), rng)
    size = rng.uniform(14, 52, n)
    blobs = [_blob(s) for s in size]
    colour = mix(T.bg, T.a2, 0.8)

    def field(f):
        t = f / frames
        out = np.zeros((H, W), dtype=np.float32)
        for i in range(n):
            yy = (p["y"][i] - t * period * p["laps"][i]) % period - 60
            xx = (p["x"][i] + 30 * np.sin(
                2 * np.pi * p["cycles"][i] * t + p["phase"][i])) % W
            _paste(out, blobs[i] * 0.16, xx, yy)
        return out

    return frames, colour, field


def stars(T):
    """Fixed points that twinkle. Nothing travels, so the only thing that has
    to come back round is the brightness."""
    rng = _rng()
    n, frames = 200, 60
    rng_x = rng.uniform(0, 1, n) * W
    rng_y = rng.uniform(0, 1, n) * H
    size = rng.uniform(0.8, 2.6, n)
    cycles = rng.integers(1, 5, n)
    phase = rng.uniform(0, 2 * np.pi, n)
    blobs = [_blob(s) for s in size]
    colour = mix(T.bg, "#ffffff", 0.9)

    def field(f):
        t = f / frames
        out = np.zeros((H, W), dtype=np.float32)
        for i in range(n):
            bright = 0.35 + 0.65 * (0.5 + 0.5 * np.sin(
                2 * np.pi * cycles[i] * t + phase[i]))
            _paste(out, blobs[i] * bright, rng_x[i], rng_y[i])
        return out

    return frames, colour, field


EFFECTS = {"rain": rain, "snow": snow, "dust": dust, "embers": embers,
           "bokeh": bokeh, "stars": stars}


def key(name, T):
    """Everything the loop depends on, so a palette change regenerates it."""
    raw = f"{name}|{T.bg}|{T.a1}|{T.a2}|{W}x{H}|{SEED}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def _rgba(alpha, colour):
    r, g, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
    img = np.zeros((H, W, 4), dtype=np.uint8)
    img[..., 0], img[..., 1], img[..., 2] = r, g, b
    img[..., 3] = (np.clip(alpha, 0, 1) * 255).astype(np.uint8)
    return Image.fromarray(img, "RGBA")


def build(name, T, into):
    """Write the loop into `into` as frame_000.png onward, once.

    Returns (directory, frame count), or None when there is no effect. The
    caller feeds the directory to ffmpeg as an image sequence and loops it.
    """
    fn = EFFECTS.get(name)
    if not fn:
        return None
    frames, colour, field = fn(T)
    into.mkdir(parents=True, exist_ok=True)
    done = into / "done"
    if done.exists():
        return into, int(done.read_text())
    for f in range(frames):
        _rgba(field(f), colour).save(into / f"frame_{f:03d}.png")
    done.write_text(str(frames))
    return into, frames
