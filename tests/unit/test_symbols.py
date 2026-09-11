"""The symbol vocabulary.

These are not about whether a given word is in the list. They are about the
rules that keep a wrong symbol off the screen, which is the only thing that
makes the feature worth having: an icon that does not match the line is more
distracting than an empty space.
"""

from app import symbols
from app.script_parser import parse


def test_a_word_inside_another_word_does_not_fire():
    """"bank" must not match "riverbank", or every third line gets an icon."""
    assert symbols.match("We sat by the riverbank until it got dark") is None
    assert symbols.match("She is a homeowner") is None


def test_a_strong_word_beats_a_weak_one_earlier_in_the_line():
    """The sentence usually mentions a day or a year in passing before it
    gets to what it is actually about."""
    line = "On the same day, after years of it, she was handed a salary."
    assert symbols.match(line) == "money"
    assert symbols.match("Five years later it was a twelve thousand dollar difference") == "money"


def test_a_weak_word_still_wins_when_nothing_strong_is_there():
    assert symbols.match("After three months you stop noticing") == "time"


def test_words_with_a_commoner_second_meaning_are_left_out():
    """Each of these would misfire more often than it would help."""
    assert symbols.match("Pay attention to what happens next") is None
    assert symbols.match("That is fine, and the return was quick") is None
    assert symbols.match("He bought a pound of flour") is None


def test_a_line_about_nothing_in_the_vocabulary_gets_no_symbol():
    assert symbols.match("The kettle had boiled and nothing else happened") is None
    assert symbols.match("He moved the chair an inch to the left") is None
    assert symbols.match("") is None
    assert symbols.match(None) is None


def test_every_symbol_in_the_vocabulary_can_be_drawn():
    """A word matching a symbol with no drawing would be a blank frame."""
    assert set(symbols.DRAW) == set(symbols.SYMBOLS)


def test_no_word_belongs_to_two_symbols_in_the_same_tier():
    """A word in two places resolves by vocabulary order, which is silent and
    arbitrary. Better to find them here."""
    seen = {}
    for name, strong, weak in symbols.VOCABULARY:
        for word in (*strong, *weak):
            assert word not in seen, f"{word!r} is in {seen[word]} and {name}"
            seen[word] = name


def test_the_symbol_rides_on_the_beat():
    """It has to be part of the beat, or it is not part of the segment cache
    key and a rebuild could quietly come out different."""
    beats = parse("It started with a boring HR email about the money.")["beats"]
    assert beats[0]["symbol"] == "mail"


def test_every_symbol_draws_something_distinguishable(tmp_path):
    """A drawing that comes out as a plain disc, or as nothing, is a symbol
    the viewer cannot tell from any other. Target was drawn with its widest
    ring on top, which hid the two inside it."""
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from PIL import Image
    from app.themes import THEMES

    T = THEMES["cream"]
    seen = {}
    for name in symbols.SYMBOLS:
        fig = plt.figure(figsize=(2.4, 2.4), dpi=100, facecolor=T.bg)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis("off")
        ax.set_xlim(-1.4, 1.4)
        ax.set_ylim(-1.4, 1.4)
        symbols.draw(ax, name, T, 0, 0, 1.0)
        out = tmp_path / f"{name}.png"
        fig.savefig(out, facecolor=T.bg)
        plt.close(fig)
        im = np.asarray(Image.open(out).convert("L")).astype(int)
        page = int(np.asarray(Image.new("L", (1, 1), 0)).sum())  # unused
        assert im.std() > 12, f"{name} is nearly blank"
        # a horizontal cut through the middle has to cross the outline more
        # than twice, or the shape is a single filled blob
        # several cuts, not one: a single row through the middle can miss a
        # detail that sits just above or below it and call a real drawing
        # blank
        edges = max(int((np.abs(np.diff(im[r])) > 28).sum())
                    for r in range(im.shape[0] // 4, 3 * im.shape[0] // 4, 6))
        assert edges >= 4, f"{name} reads as one plain blob ({edges} edges)"
        seen[name] = edges
    assert len(seen) == len(symbols.SYMBOLS)
