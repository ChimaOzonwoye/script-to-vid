"""Burned in captions that change through a beat.

A beat is a whole paragraph, and a paragraph set as one block of text at the
bottom of the frame runs off the bottom of it. Shrinking it to fit makes it
unreadable, and trimming it drops words the voice is saying. Neither is
acceptable, and both were what the first version did.

What people actually watch has a couple of lines at a time, changing with the
speech. So the line is split into short pieces and each one is shown for its
share of the beat. There are no word timings from the voice, so the share is
taken from how much text each piece holds, which is close enough that nobody
notices: speech rate is far more even than sentence length.

The pieces are drawn as their own transparent frames and laid over the video
rather than baked into the slide. That matters for a beat with a speaking
figure in it, where the slide already exists in six versions for the mouth and
the eyes: baking the caption in would multiply those by the number of pieces,
while an overlay costs one small image each.
"""

import re
import textwrap

MAX_WORDS = 9           # about as much as anyone reads in one glance
MAX_CHARS = 46          # a piece that would wrap past two lines is too long
MIN_SECONDS = 0.7       # never flash a piece up faster than it can be read


def split(say):
    """Break a beat's words into caption sized pieces.

    Sentences are split first, because a caption that changes at a full stop
    reads as deliberate and one that changes mid clause reads as broken. A
    sentence too long for one piece is then divided evenly rather than by
    taking nine words at a time, which is what leaves a stray "match." on
    screen by itself while the piece before it is full.
    """
    text = " ".join((say or "").split())
    if not text:
        return []
    pieces = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        words = sentence.split()
        if not words:
            continue
        need = max(-(-len(words) // MAX_WORDS),
                   -(-len(sentence) // MAX_CHARS), 1)
        size = -(-len(words) // need)
        pieces += [" ".join(words[i:i + size])
                   for i in range(0, len(words), size)]
    return pieces


def timings(pieces, start, seconds):
    """When each piece appears and disappears, over `seconds` from `start`.

    Shared out by length rather than evenly, so a four word piece is not held
    as long as a nine word one. A piece too short to read borrows time from
    the one after it.
    """
    if not pieces or seconds <= 0:
        return []
    weights = [max(len(p), 1) for p in pieces]
    total = sum(weights)
    spans, at = [], start
    for i, w in enumerate(weights):
        last = i == len(pieces) - 1
        span = seconds - (at - start) if last else seconds * w / total
        spans.append([at, at + span])
        at += span
    # a piece nobody could read borrows from its neighbour rather than being
    # dropped, because dropping one loses words the voice is saying
    for i in range(len(spans) - 1):
        short = MIN_SECONDS - (spans[i][1] - spans[i][0])
        if short > 0:
            take = min(short, max(0.0, (spans[i + 1][1] - spans[i + 1][0]) - MIN_SECONDS))
            spans[i][1] += take
            spans[i + 1][0] += take
    return [(round(a, 3), round(b, 3)) for a, b in spans]


def wrapped(piece, width=34):
    """The piece as it is set, at most two lines."""
    return "\n".join(textwrap.wrap(piece, width)[:2])
