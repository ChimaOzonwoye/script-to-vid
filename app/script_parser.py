"""Parses the plain-text script format into beats the engine can render.

No formatting is required. Paste the words you want spoken and every line
is narration. On top of that: blank lines separate paragraphs, `#` starts a
chapter, `>` is a visual direction, and directions apply to the next
narration paragraph however many blank lines sit between.

The rest of this module exists because real scripts are not written for this
tool. People paste what they wrote elsewhere, or what a chatbot wrote for
them, and that arrives full of stage directions, timecodes and `Narration:`
labels. Reading those aloud makes an unusable video, so they are skipped,
and every skipped line is handed back in `skipped` for the page to show with
a control to put it back. Guessing harder is not an option: `Scene 3` on its
own line is nearly always a note and occasionally a real line, and the text
alone cannot tell you which.

Parsing never raises. Anything it does not understand becomes narration.
Beats carry only content, never source positions, so an edit higher up the
script does not invalidate the cache of the beats below it, and a line put
back in the review panel changes only its own beat.
"""

import re
import textwrap

from .backgrounds import BACKGROUNDS
from .characters import EXPRESSIONS, HAIRS, HEADS, POSES

PROPS = ("piggy", "coin", "coins", "jar")

# layouts that read well with nothing but narration, cycled so the same one
# never appears twice in a row
# A narration paragraph with no direction on it is the presenter: one figure
# held in the same place with the words beside them. Fix list 4 rotated four
# layouts here and moved the figure every beat, which is what made a run of
# beats read as a slideshow. Variety comes from the content beside the
# presenter changing, and from the side swapping at chapters. The rotation
# layouts are all still reachable by naming them.
DEFAULT_VISUAL = "scene_presenter"

# Single figure scenes are drawn wide, medium or close, cycled so no two beats
# in a row are framed alike, and flipped so the figure changes sides. The
# choice lives on the beat rather than being picked at render time, so it is
# part of the segment cache key and a rebuild looks the same as the first run.
# Two figure scenes are two-shots by nature, and the chart and bubble scenes
# need their space for the chart and the words.
FRAMED = ("scene_character", "scene_caption")
FRAMING_CYCLE = ("medium", "wide", "close")

# directions that decorate a beat rather than pick its layout
MODIFIERS = ("caption", "prop", "sub", "scene")

SLIDES = ("sweep", "title", "gauge", "callout", "timeline", "jars", "terms",
          "path", "growth", "quiet", "recap", "outro")
SCENES = ("character", "duo", "bubbles", "split", "chart")


# ----------------------------------------------------------------------
# WHAT A LINE IS
# A marker only counts when it is the whole line. "Step one. Spend every
# dollar you earn." is narration, because the line carries content past the
# marker. Two kinds of skip, because they are not equally certain:
#   note    never wanted aloud, so the page collapses these
#   marker  probably a note, occasionally real, so the page shows them
# ----------------------------------------------------------------------
NOTE, MARKER = "note", "marker"

_COMMENT = re.compile(r"^//")
_BRACKETED = re.compile(r"^\[.*\]$", re.S)
_MARKER = re.compile(r"^(scene|script|part|chapter|section|act)"
                     r"\s*#?\s*\d+\s*[.:)\-]?$", re.I)
# escapes rather than the characters themselves, so the dash sweep stays clean
_SPAN = r"(?:\s*(?:[-\u2013\u2014]|to)\s*\d{1,2}:\d{2}(?::\d{2})?)?"
_TIMESTAMP = re.compile(r"^\(?\d{1,2}:\d{2}(?::\d{2})?" + _SPAN + r"\)?[.:]?$",
                        re.I)

# Labels a script carries down its left margin, and where each one's value
# belongs. Audio, music and sound effect notes have nowhere to go: the tool
# cannot act on "upbeat piano", so they are skipped and shown rather than
# read out or silently dropped.
_LABELS = {
    "narration": "say", "voiceover": "say", "voice over": "say",
    "title": "chapter",
    "visual": "caption", "visuals": "caption", "on-screen": "caption",
    "on screen": "caption", "onscreen": "caption", "text": "caption",
    "b-roll": "caption", "b roll": "caption", "broll": "caption",
    "audio": NOTE, "music": NOTE, "sfx": NOTE,
}
# short enough that "Here is the point: saving is hard" cannot match; the
# lookup above is what actually decides
_LABEL = re.compile(r"^([A-Za-z][A-Za-z \-]{0,11}):\s*(.*)$", re.S)

_QUOTE_PAIRS = (('"', '"'), ("'", "'"), ("\u201c", "\u201d"),
                ("\u2018", "\u2019"))


def _unquote(s):
    """Scripts often wrap spoken lines in quotes, and the voice reads them."""
    for open_q, close_q in _QUOTE_PAIRS:
        if len(s) > 2 and s.startswith(open_q) and s.endswith(close_q):
            return s[1:-1].strip()
    return s


def classify(s):
    """What one non-blank line is: (kind, payload).

    kind is "direction", "chapter", "caption", "narration", or one of the
    two skip kinds. Order matters: an explicit `>` or `#` always wins, so a
    user who has learned the format never has it second-guessed.
    """
    if s.startswith(">"):
        return "direction", s
    if s.startswith("#"):
        return "chapter", s.lstrip("#").strip()
    if _COMMENT.match(s) or _BRACKETED.match(s):
        return NOTE, s

    m = _LABEL.match(s)
    if m and m.group(1).strip().lower() in _LABELS:
        where = _LABELS[m.group(1).strip().lower()]
        value = _unquote(m.group(2).strip())
        if where is NOTE or not value:
            return NOTE, s
        return where if where != "say" else "narration", value

    if _MARKER.match(s) or _TIMESTAMP.match(s):
        return MARKER, s
    return "narration", _unquote(s)


# enough headings to be a pattern rather than a short script that happens
# to start with one. Two would call `# Title` over a single paragraph a
# misunderstanding, and it is not one.
_FLOOD_MIN = 3


def _headings_flood(lines):
    """More than half the lines being headings means the user was told to
    add markdown and did it to everything. Left alone that renders a video
    of nothing but chapter cards."""
    body = [s for s in lines if s.strip()]
    heads = [s for s in body if s.strip().startswith("#")]
    return len(heads) >= _FLOOD_MIN and len(heads) * 2 > len(body)


# A caption cut at a word count lands mid thought: "SAVING MONEY IS SIMPLE
# BUT NOT". Beside a presenter that caption is the only thing on screen, so
# it has to read as a title. Prefer the whole first sentence, fall back to
# its first clause, and only then cut at a word count, trimming any word that
# cannot end a phrase.
# Words that cannot be the last word of a headline. Cutting a sentence at a
# fixed word count lands on these constantly ("TAKE THE MONEY OUT BEFORE"),
# and the reader spends the beat waiting for the rest of a phrase that never
# arrives. Articles, conjunctions and auxiliaries are the obvious ones;
# prepositions matter more, because they promise an object.
_DANGLING = {"a", "an", "and", "as", "at", "but", "by", "for", "from", "in",
             "into", "of", "on", "or", "so", "than", "that", "the", "then",
             "to", "with", "your", "not", "will", "would", "can", "could",
             "should", "is", "are", "was", "were", "be", "been", "has",
             "have", "had", "do", "does", "did", "very", "just", "about",
             "after", "before", "during", "over", "under", "through",
             "without", "within", "against", "between", "among", "onto",
             "off", "up", "down", "out", "when", "while", "until", "since",
             "because", "unless", "though", "although", "if", "how", "what",
             "who", "which", "where", "why", "there", "here", "its", "their",
             "his", "her", "our", "my", "this", "these", "those", "every",
             "each", "some", "any", "more", "most", "much", "many", "own"}


def _trim(words):
    """Drop trailing words that leave the headline hanging mid-phrase."""
    while len(words) > 2 and words[-1].strip(".,;:!?").lower() in _DANGLING:
        words.pop()
    return words


def _auto_headline(say, limit=9):
    """A short title for the words being spoken, taken from their first sentence.

    Whole sentences read best, so a short one is used as it stands. Anything
    longer is cut at the first comma if that leaves a phrase short enough,
    because a comma is a boundary the writer already chose; only when that
    fails does it fall back to a word count, and then trailing function words
    are dropped so the cut lands somewhere a reader can stop.
    """
    first = re.split(r"(?<=[.!?])\s+", (say or "").replace("\n", " ").strip())[0]
    words = first.split()
    if not words:
        return ""
    if len(words) <= limit:
        return first.rstrip(".,;:!?").upper()
    clause = first.split(",")[0].split()
    words = _trim(clause if len(clause) <= limit else words[:limit])
    return " ".join(words).rstrip(".,;:!?").upper()


def _split_direction(s):
    body = s.lstrip(">").strip()
    name, _, payload = body.partition(":")
    return name.strip().lower(), payload.strip()


def _character_fields(payload, line_no, warnings):
    fields = {}
    for tok in filter(None, (t.strip().lower() for t in payload.split(","))):
        if tok in EXPRESSIONS:
            fields["expr"] = tok
        elif tok in POSES:
            fields["pose"] = tok
        elif tok in HEADS:
            fields["head"] = tok
        elif tok in HAIRS:
            fields["hair"] = tok
        else:
            warnings.append(
                f"Line {line_no}: '{tok}' isn't a pose, an expression, a head "
                f"shape or a hair style. Poses: {', '.join(POSES)}. "
                f"Expressions: {', '.join(EXPRESSIONS)}. "
                f"Heads: {', '.join(HEADS)}. Hair: {', '.join(HAIRS)}.")
    return fields


def _background(payload, line_no, warnings):
    """The setting a `> scene:` direction names, or None with a warning."""
    name = payload.strip().lower().replace(" ", "_")
    if name in BACKGROUNDS:
        return name
    warnings.append(f"Line {line_no}: there is no '{name}' setting. The "
                    f"settings are: {', '.join(sorted(BACKGROUNDS))}.")
    return None


def _build_beat(primary, modifiers, say, cast_i, warnings):
    name, payload, line_no = primary
    b = {"say": say}

    if name == "character":
        b["visual"] = "scene_character"
        b.update(_character_fields(payload, line_no, warnings))
    elif name == "duo":
        b["visual"] = "scene_duo"
        b["bubble"] = payload
    elif name == "bubbles":
        b["visual"] = "scene_bubbles"
        b["words"] = [w.strip() for w in payload.split(",") if w.strip()]
    elif name == "split":
        b["visual"] = "scene_split"
        left, _, right = payload.partition("|")
        if left.strip():
            b["left"] = left.strip()
        if right.strip():
            b["right"] = right.strip()
    elif name == "chart":
        b["visual"] = "scene_chart"
        if payload in ("growth", "timeline"):
            b["chart"] = payload
        elif payload:
            warnings.append(f"Line {line_no}: chart '{payload}' isn't one of "
                            "growth or timeline, using growth.")
    elif name == "terms":
        b["visual"] = "terms"
        if payload:
            b["words"] = [w.strip() for w in payload.split(",") if w.strip()][:5]
        b["headline"] = _auto_headline(say)
    elif name == "recap":
        b["visual"] = "recap"
        b["items"] = [i.strip() for i in payload.split("|") if i.strip()][:6]
        b["headline"] = "TO RECAP"
    elif name == "sweep":
        b["visual"] = "sweep"
        b["headline"] = "\n".join(p.strip() for p in payload.split("|")[:2]) \
            if payload else _auto_headline(say, 8)
    elif name in SLIDES:
        b["visual"] = name
        b["headline"] = payload.upper() if payload else _auto_headline(say)
    elif name == "caption":
        b["visual"] = "caption"
        b["caption"] = payload or _auto_headline(say)
    else:
        warnings.append(f"Line {line_no}: unknown direction '{name}', shown "
                        "as a caption slide.")
        b["visual"] = "caption"
        b["caption"] = payload or _auto_headline(say)

    for mname, mpayload, mline in modifiers:
        if mname == "caption":
            b["caption"] = mpayload
        elif mname == "sub":
            b["sub"] = mpayload
        elif mname == "prop":
            p = mpayload.strip().lower()
            if p in PROPS:
                b["prop"] = p
            else:
                warnings.append(f"Line {mline}: there is no '{p}' prop. The "
                                f"props are: {', '.join(PROPS)}.")
        elif mname == "scene":
            name = _background(mpayload, mline, warnings)
            if name and not b["visual"].startswith("scene_"):
                warnings.append(f"Line {mline}: a setting is only drawn behind "
                                "a character, and this beat has none, so it "
                                "was ignored.")
            elif name:
                b["background"] = name

    if b["visual"].startswith("scene_"):
        b["cast_i"] = cast_i
    if b["visual"] in ("scene_character",) and "caption" not in b:
        b["caption"] = _auto_headline(say)
    return b


def _presenter_beat(say, cast_i, rot_i, side):
    """The default beat: a presenter, and the words beside them.

    The side is settled by the chapter rather than by this counter, so the
    figure holds its place through a run of beats and the swap reads as a cut
    to the other camera.
    """
    return {
        "say": say,
        "visual": DEFAULT_VISUAL,
        "caption": _auto_headline(say),
        "cast_i": cast_i,
        "side": side,
        "expr": ("happy", "neutral", "happy", "thinking")[rot_i % 4],
        "pose": ("offer", "stand", "point", "think")[rot_i % 4],
    }, rot_i + 1


def parse(text, keep=()):
    """Returns {"beats", "warnings", "words", "skipped"}.

    `skipped` is every line that will not be spoken and `kept` is every line
    that would have been skipped but which the user put back. Both are
    reported so the page can offer the reverse of whatever it did.

    `keep` holds the exact text of lines the user has put back from the
    review panel. It is matched on the text rather than on a line number so
    that editing the script above a restored line cannot quietly restore a
    different one instead.
    """
    beats, warnings, skipped, kept = [], [], [], []
    keep = {k.strip() for k in (keep or ()) if k and k.strip()}
    pending, para = [], []
    chapter_n = 0
    rot_i = 0
    frame_i = 0

    def prev_visual():
        return beats[-1]["visual"] if beats else None

    def add(b):
        nonlocal frame_i
        if b["visual"] in FRAMED:
            b["framing"] = FRAMING_CYCLE[frame_i % len(FRAMING_CYCLE)]
            b["flip"] = bool(frame_i % 2)
            frame_i += 1
        beats.append(b)

    def flush_para():
        nonlocal rot_i
        if not para:
            return
        say = " ".join(para)
        para.clear()
        primaries = [d for d in pending if d[0] not in MODIFIERS]
        modifiers = [d for d in pending if d[0] in MODIFIERS]
        pending.clear()
        if len(primaries) > 1:
            kept = primaries[0][0]
            for name, _, line_no in primaries[1:]:
                warnings.append(f"Line {line_no}: this beat already has a "
                                f"'{kept}' direction, so '{name}' was ignored.")
        cast_i = max(chapter_n - 1, 0)
        if primaries:
            try:
                add(_build_beat(primaries[0], modifiers, say,
                                cast_i, warnings))
                return
            except Exception:
                # the page must never see a traceback; fall through to a
                # caption slide that always renders
                warnings.append(f"Line {primaries[0][2]}: the "
                                f"'{primaries[0][0]}' direction could not be "
                                "applied, shown as a caption slide.")
        if modifiers and not primaries:
            b = {"say": say, "visual": "caption",
                 "caption": _auto_headline(say)}
            for mname, mpayload, mline in modifiers:
                if mname == "caption":
                    b["caption"] = mpayload
                elif mname == "prop":
                    b["visual"] = "scene_character"
                    b["cast_i"] = cast_i
                    if mpayload.strip().lower() in PROPS:
                        b["prop"] = mpayload.strip().lower()
                elif mname == "scene":
                    name = _background(mpayload, mline, warnings)
                    if name:
                        b["visual"] = "scene_character"
                        b["cast_i"] = cast_i
                        b["background"] = name
            add(b)
            return
        b, rot_i = _presenter_beat(say, cast_i, rot_i,
                                   "left" if chapter_n % 2 == 0 else "right")
        add(b)

    lines = (text or "").splitlines()
    flood = _headings_flood(lines)
    if flood:
        warnings.append(
            "Nearly every line here starts with a #, so they were read as "
            "narration rather than chapter cards. Otherwise the video would "
            "be nothing but title cards. Take the # off any line you did "
            "want spoken as narration anyway, and leave it on real chapters.")

    for line_no, raw in enumerate(lines, 1):
        s = raw.strip()
        if not s:
            flush_para()
            continue
        try:
            kind, payload = classify(s)
        except Exception:
            # a script is user input and the page must never see a traceback;
            # anything this cannot read is simply spoken
            kind, payload = "narration", s
        if kind in (NOTE, MARKER):
            entry = {"line": line_no, "text": s, "kind": kind}
            if s in keep:
                # reported too, so putting a line back is not a one way door
                kept.append(entry)
                kind, payload = "narration", _unquote(s)
            else:
                skipped.append(entry)
                continue
        if flood and kind == "chapter":
            # each heading was its own line and is its own thought, so it
            # gets its own beat rather than being run into its neighbours
            # as one breathless paragraph
            if payload:
                flush_para()
                para.append(payload)
                flush_para()
            continue

        if kind == "direction":
            flush_para()
            name, dpayload = _split_direction(payload)
            if name:
                pending.append((name, dpayload, line_no))
            else:
                warnings.append(f"Line {line_no}: empty direction, ignored.")
        elif kind == "chapter":
            if not payload:
                continue        # a bare # names no chapter and says nothing
            flush_para()
            chapter_n += 1
            beats.append({
                "visual": "chapter", "num": f"{chapter_n:02d}", "say": payload,
                "headline": "\n".join(textwrap.wrap(payload.upper(), 22)[:3]),
            })
        elif kind == "caption":
            pending.append(("caption", payload, line_no))
        elif payload:
            para.append(payload)
    flush_para()

    for name, _, line_no in pending:
        warnings.append(f"Line {line_no}: the '{name}' direction has no "
                        "narration after it, so it was skipped.")

    # A beat with nothing to say still goes to the voice service, which
    # returns an empty file, which ffprobe then cannot measure. That is the
    # whole of the reported crash on scripts full of # headings.
    beats = [b for b in beats if b.get("say", "").strip()]

    if not beats:
        warnings.append("The script is empty. Write some narration first.")

    words = sum(len(b["say"].split()) for b in beats)
    return {"beats": beats, "warnings": warnings, "words": words,
            "skipped": skipped, "kept": kept}
