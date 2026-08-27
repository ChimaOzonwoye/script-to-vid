"""The narration voices offered in the app.

edge-tts publishes hundreds of voices. A list that long is a worse choice
than no list, so this is a curated dozen: six accents, both genders, all
of them clear at a conversational pace.

Samples are pre-generated into assets/voices/ by tools/generate_voices.py,
which the installer runs. The picker plays those local files, so choosing a
voice is instant and works with no network. If the samples are missing the
picker still works, it just cannot preview.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT / "assets" / "voices"

# the line every sample says, short enough to generate twelve of quickly
SAMPLE_LINE = ("Here is what your video will sound like with my voice "
               "reading your script.")

# (id, display name, accent, gender)
VOICES = [
    ("en-US-AndrewMultilingualNeural", "Andrew", "American", "male"),
    ("en-US-AvaMultilingualNeural",    "Ava",     "American", "female"),
    ("en-US-GuyNeural",                "Guy",     "American", "male"),
    ("en-US-JennyNeural",              "Jenny",   "American", "female"),
    ("en-GB-RyanNeural",               "Ryan",    "British",  "male"),
    ("en-GB-SoniaNeural",              "Sonia",   "British",  "female"),
    ("en-AU-WilliamNeural",            "William", "Australian", "male"),
    ("en-AU-NatashaNeural",            "Natasha", "Australian", "female"),
    ("en-IN-PrabhatNeural",            "Prabhat", "Indian",   "male"),
    ("en-IN-NeerjaNeural",             "Neerja",  "Indian",   "female"),
    ("en-NG-AbeoNeural",               "Abeo",    "Nigerian", "male"),
    ("en-NG-EzinneNeural",             "Ezinne",  "Nigerian", "female"),
]

DEFAULT_VOICE = VOICES[0][0]

# edge-tts wants a signed percentage. "Normal" keeps the engine's original
# -4%, which is a touch slower than the raw voice and reads as conversational.
RATES = [
    ("-18%", "Slower"),
    ("-4%",  "Normal"),
    ("+10%", "Faster"),
]

DEFAULT_RATE = "-4%"

RATE_VALUES = [r for r, _ in RATES]
VOICE_IDS = [v for v, _, _, _ in VOICES]


def sample_name(voice_id):
    return f"{voice_id}.mp3"


def listing():
    """The voices as the page needs them, each knowing if it can preview."""
    out = []
    for vid, name, accent, gender in VOICES:
        out.append({
            "id": vid,
            "name": name,
            "accent": accent,
            "gender": gender,
            "label": f"{name} ({accent}, {gender})",
            "has_sample": (SAMPLE_DIR / sample_name(vid)).exists(),
        })
    return out


def valid_voice(voice_id):
    """Fall back to the default rather than fail on an unknown saved voice."""
    return voice_id if voice_id in VOICE_IDS else DEFAULT_VOICE


def valid_rate(rate):
    return rate if rate in RATE_VALUES else DEFAULT_RATE


def rate_label(rate):
    return dict(RATES).get(rate, "Normal")
