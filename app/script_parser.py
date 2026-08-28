"""Parses the plain-text script format into beats the engine can render.

The format, in full: blank lines separate paragraphs, `#` starts a chapter,
`>` is a visual direction, everything else is narration. Directions apply
to the next narration paragraph, however many blank lines sit between.

Parsing never raises. Anything it does not understand becomes a plain
caption slide plus a warning the page shows above the Generate button.
Beats carry only content, never source positions, so an edit higher up the
script does not invalidate the cache of the beats below it.
"""

import textwrap

from .characters import EXPRESSIONS, POSES, HEADS

PROPS = ("piggy", "coin", "coins", "jar")

# layouts that read well with nothing but narration, cycled so the same one
# never appears twice in a row
ROTATION = ("scene_caption", "caption", "scene_character", "quiet")

# Single figure scenes are drawn wide, medium or close, cycled so no two beats
# in a row are framed alike, and flipped so the figure changes sides. The
# choice lives on the beat rather than being picked at render time, so it is
# part of the segment cache key and a rebuild looks the same as the first run.
# Two figure scenes are two-shots by nature, and the chart and bubble scenes
# need their space for the chart and the words.
FRAMED = ("scene_character", "scene_caption")
FRAMING_CYCLE = ("medium", "wide", "close")

# directions that decorate a beat rather than pick its layout
MODIFIERS = ("caption", "prop", "sub")

SLIDES = ("sweep", "title", "gauge", "callout", "timeline", "jars", "terms",
          "path", "growth", "quiet", "recap", "outro")
SCENES = ("character", "duo", "bubbles", "split", "chart")


# a caption cut to a word limit often lands on a word that cannot end a
# phrase, giving captions like "START WITH EGGS STRAIGHT FROM THE"
_DANGLING = {"a", "an", "and", "as", "at", "but", "by", "for", "from", "in",
             "into", "of", "on", "or", "so", "than", "that", "the", "then",
             "to", "with", "your"}


def _auto_headline(say, limit=6):
    words = say.replace("\n", " ").split()[:limit]
    while len(words) > 2 and words[-1].strip(".,;:!?").lower() in _DANGLING:
        words.pop()
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
        else:
            warnings.append(
                f"Line {line_no}: '{tok}' isn't a pose, an expression or a "
                "head shape, so it was ignored.")
    return fields


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

    if b["visual"].startswith("scene_"):
        b["cast_i"] = cast_i
    if b["visual"] in ("scene_character",) and "caption" not in b:
        b["caption"] = _auto_headline(say)
    return b


def _rotated_beat(say, cast_i, rot_i, prev_visual):
    visual = ROTATION[rot_i % len(ROTATION)]
    if visual == prev_visual:
        rot_i += 1
        visual = ROTATION[rot_i % len(ROTATION)]
    b = {"say": say, "visual": visual}
    if visual in ("scene_caption", "caption", "scene_character"):
        b["caption"] = _auto_headline(say)
    if visual == "quiet":
        b["headline"] = _auto_headline(say)
    if visual.startswith("scene_"):
        b["cast_i"] = cast_i
        b["expr"] = ("neutral", "happy", "thinking")[rot_i % 3]
        b["pose"] = ("stand", "offer", "think")[rot_i % 3]
    return b, rot_i + 1


def parse(text):
    """Returns {"beats": [...], "warnings": [...], "words": int}."""
    beats, warnings = [], []
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
            for mname, mpayload, _ in modifiers:
                if mname == "caption":
                    b["caption"] = mpayload
                elif mname == "prop":
                    b["visual"] = "scene_character"
                    b["cast_i"] = cast_i
                    if mpayload.strip().lower() in PROPS:
                        b["prop"] = mpayload.strip().lower()
            add(b)
            return
        b, rot_i = _rotated_beat(say, cast_i, rot_i, prev_visual())
        add(b)

    for line_no, raw in enumerate((text or "").splitlines(), 1):
        s = raw.strip()
        if not s:
            flush_para()
        elif s.startswith("#"):
            flush_para()
            chapter_n += 1
            title = s.lstrip("#").strip()
            beats.append({
                "visual": "chapter", "num": f"{chapter_n:02d}", "say": title,
                "headline": "\n".join(textwrap.wrap(title.upper(), 22)[:3]),
            })
        elif s.startswith(">"):
            flush_para()
            name, payload = _split_direction(s)
            if name:
                pending.append((name, payload, line_no))
            else:
                warnings.append(f"Line {line_no}: empty direction, ignored.")
        else:
            para.append(s)
    flush_para()

    for name, _, line_no in pending:
        warnings.append(f"Line {line_no}: the '{name}' direction has no "
                        "narration after it, so it was skipped.")

    if not beats:
        warnings.append("The script is empty. Write some narration first.")

    words = sum(len(b["say"].split()) for b in beats)
    return {"beats": beats, "warnings": warnings, "words": words}
