"""Generates the voice samples the picker plays.

Run once by the installer:  python tools/generate_voices.py

Each curated voice reads one short line into assets/voices/<voice-id>.mp3,
so the picker previews instantly and offline. Existing samples are kept, so
re-running is cheap and a partial run can be resumed.

The curated ids are checked against what the service actually offers, because
Microsoft retires voices occasionally and a stale id would otherwise fail
silently at render time.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.voices import VOICES, SAMPLE_DIR, SAMPLE_LINE, sample_name  # noqa: E402


async def _available_ids():
    import edge_tts
    try:
        return {v["ShortName"] for v in await edge_tts.list_voices()}
    except Exception:
        return None      # offline: trust the curated list rather than stop


async def main():
    import edge_tts
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    available = await _available_ids()
    made = skipped = failed = 0

    for vid, name, accent, _gender in VOICES:
        dst = SAMPLE_DIR / sample_name(vid)
        if dst.exists() and dst.stat().st_size > 0:
            skipped += 1
            continue
        if available is not None and vid not in available:
            print(f"  {name} ({accent}): '{vid}' is no longer offered, skipped")
            failed += 1
            continue
        try:
            await edge_tts.Communicate(SAMPLE_LINE, vid).save(str(dst))
            print(f"  {name} ({accent}) ready")
            made += 1
        except Exception as e:
            dst.unlink(missing_ok=True)
            print(f"  {name} ({accent}) could not be made: {type(e).__name__}")
            failed += 1

    print(f"voice samples: {made} made, {skipped} already there, {failed} missing")
    # a missing sample only costs the preview, so this is never a failed install
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
