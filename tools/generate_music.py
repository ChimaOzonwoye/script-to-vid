"""Generates the starter music library in assets/music.

Every track is synthesised here, from scratch, so the library is original
work shippable under the repo's MIT licence and safe to use in monetised
videos. Rerun after editing:  python tools/generate_music.py

Each track is a chord loop with up to three voices: a soft pad, a plucked
arpeggio and a bass root. The last chord crossfades back into the first,
so the engine's own loop crossfade lands on a musical seam.
"""

import subprocess
import sys
from pathlib import Path

import numpy as np

SR = 44100
OUT = Path(__file__).resolve().parent.parent / "assets" / "music"

A4 = 440.0


def hz(semis_from_a4):
    return A4 * 2 ** (semis_from_a4 / 12)


# semitone offsets from A4 for the chords we use, one octave down
CHORDS = {
    "C":  [-21, -17, -14], "G": [-14, -10, -7], "Am": [-12, -9, -5],
    "F":  [-16, -12, -9],  "Dm": [-19, -15, -12], "Em": [-17, -14, -10],
    "Bb": [-23, -19, -16], "Gm": [-14, -11, -7],
}


def _env(n, a, r):
    """Linear attack, exponential release."""
    e = np.ones(n)
    an = min(int(a * SR), n)
    e[:an] = np.linspace(0, 1, an)
    rn = min(int(r * SR), n)
    e[-rn:] *= np.exp(-np.linspace(0, 5, rn))
    return e


def _tone(freq, dur, harmonics, a, r, detune=0.0):
    t = np.arange(int(dur * SR)) / SR
    y = np.zeros_like(t)
    for i, amp in enumerate(harmonics, start=1):
        for d in ((-detune, detune) if detune else (0.0,)):
            y += amp * np.sin(2 * np.pi * freq * i * (1 + d) * t)
    return y * _env(len(t), a, r)


PAD = [1.0, 0.35, 0.12, 0.05]
PLUCK = [1.0, 0.5, 0.18]
BASS = [1.0, 0.25]


def _place(mix, y, at):
    i = int(at * SR)
    n = min(len(y), len(mix) - i)
    if n > 0:
        mix[i:i + n] += y[:n]


def render(name, bpm, bars, progression, pad=True, arp=None, bass=True,
           arp_rate=2, seed=0):
    """One track. `progression` is a chord name per bar, repeated to `bars`."""
    rng = np.random.default_rng(seed)
    beat = 60 / bpm
    bar = 4 * beat
    total = bars * bar + 3
    mix = np.zeros(int(total * SR))

    for b in range(bars):
        chord = CHORDS[progression[b % len(progression)]]
        t0 = b * bar
        if pad:
            for s in chord:
                _place(mix, 0.16 * _tone(hz(s), bar * 1.05, PAD,
                                         a=0.8, r=1.2, detune=0.0012), t0)
        if bass:
            _place(mix, 0.22 * _tone(hz(chord[0] - 12), bar * 0.95, BASS,
                                     a=0.02, r=1.5), t0)
        if arp:
            notes = chord + [chord[0] + 12, chord[1] + 12]
            for k in range(int(4 * arp_rate)):
                s = notes[int(rng.integers(0, len(notes)))] if arp == "random" \
                    else notes[k % len(notes)]
                _place(mix, 0.13 * _tone(hz(s + 12), beat * 1.6, PLUCK,
                                         a=0.004, r=beat * 1.4),
                       t0 + k * beat / arp_rate)

    # the tail folds back onto the start so the loop seam is musical
    seam = int(2.5 * SR)
    mix[:seam] += mix[len(mix) - seam:]
    mix = mix[:len(mix) - seam]

    mix *= 0.5 / max(np.max(np.abs(mix)), 1e-9)
    wav = OUT / f"{name}.wav"
    mp3 = OUT / f"{name}.mp3"
    pcm = (mix * 32767).astype(np.int16)
    import wave
    with wave.open(str(wav), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(pcm.tobytes())
    r = subprocess.run(["ffmpeg", "-y", "-i", str(wav), "-ac", "2",
                        "-c:a", "libmp3lame", "-b:a", "128k", str(mp3)],
                       capture_output=True)
    wav.unlink()
    if r.returncode != 0:
        sys.exit(f"ffmpeg failed for {name}")
    print(f"  {mp3.name}  {len(mix) / SR:.0f}s")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    render("gentle-keys", 72, 16, ["C", "G", "Am", "F"],
           arp="up", arp_rate=1, seed=1)
    render("warm-morning", 84, 16, ["F", "C", "Dm", "Bb"],
           arp="up", arp_rate=2, seed=2)
    render("steady-focus", 96, 20, ["Am", "F", "C", "G"],
           arp="random", arp_rate=2, seed=3)
    render("quiet-thought", 60, 12, ["Dm", "Bb", "F", "C"],
           arp=None, seed=4)
    render("small-steps", 104, 20, ["C", "Em", "F", "G"],
           arp="up", arp_rate=4, bass=True, seed=5)
    render("evening-walk", 66, 14, ["Gm", "Bb", "F", "C"],
           arp="random", arp_rate=1, seed=6)


if __name__ == "__main__":
    main()
