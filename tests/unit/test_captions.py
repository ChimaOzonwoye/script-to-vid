"""Burned in captions.

A beat is a whole paragraph. Set as one block at the bottom of the frame it
runs off the bottom of it, and every way of forcing it to fit is worse than
splitting it: shrink it and nobody can read it, trim it and the picture stops
saying what the voice is saying.
"""

import pytest

from app import captions

PARAGRAPH = (
    "Mistake number two: missing the employer match. Many companies add "
    "money to your 401k when you contribute. A common example is fifty "
    "cents for every dollar you put in, up to six percent of your salary."
)


def test_every_word_survives_the_split():
    """Losing a word here means the caption stops matching the narration."""
    assert " ".join(captions.split(PARAGRAPH)) == PARAGRAPH


def test_no_piece_is_too_long_to_set_in_two_lines():
    for piece in captions.split(PARAGRAPH):
        assert len(piece) <= captions.MAX_CHARS, piece
        assert len(piece.split()) <= captions.MAX_WORDS, piece


def test_a_sentence_is_divided_evenly_rather_than_greedily():
    """Taking nine words at a time leaves a stray "match." on screen by
    itself while the piece before it is full."""
    pieces = captions.split("Mistake number two: missing the employer match.")
    assert len(pieces) == 2
    shortest, longest = min(map(len, pieces)), max(map(len, pieces))
    assert longest - shortest < captions.MAX_CHARS / 2, pieces


def test_pieces_do_not_straddle_a_full_stop():
    for piece in captions.split(PARAGRAPH):
        assert "." not in piece[:-1].rstrip("."), piece


def test_the_timings_cover_the_whole_beat_and_do_not_overlap():
    pieces = captions.split(PARAGRAPH)
    spans = captions.timings(pieces, 0.35, 16.0)
    assert len(spans) == len(pieces)
    assert spans[0][0] == pytest.approx(0.35)
    assert spans[-1][1] == pytest.approx(16.35, abs=0.01)
    for (_, end), (start, _) in zip(spans, spans[1:]):
        assert start == pytest.approx(end, abs=0.01), "a gap or an overlap"


def test_no_piece_flashes_up_too_fast_to_read():
    spans = captions.timings(captions.split(PARAGRAPH), 0.35, 16.0)
    for a, b in spans[:-1]:
        assert b - a >= captions.MIN_SECONDS - 0.01, f"{b - a:.2f}s is a flash"


def test_a_short_beat_is_one_piece_and_needs_no_rolling():
    assert captions.split("Short one.") == ["Short one."]


def test_nothing_to_say_is_nothing_to_draw():
    assert captions.split("") == []
    assert captions.split(None) == []
    assert captions.timings([], 0, 5) == []
