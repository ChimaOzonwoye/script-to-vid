"""Symbols drawn from what the narration actually says.

The wish this answers is "show the thing, not the words": a paycheck when the
line is about a paycheck, a clock when it is about waiting. The general form
of that needs a model that understands the sentence, which this project does
not have and will not get, because the whole point is that it runs on a laptop
with no graphics card and no bill.

What is possible without understanding anything is matching. A line that says
"salary" almost certainly wants a banknote beside it. So this is a vocabulary
of words and the shapes they stand for, and nothing cleverer than that.

Matching has to be timid or it is worse than nothing. A symbol that is wrong
is more distracting than an empty space, so:

  * whole words only, because "bank" must not fire on "riverbank"
  * one symbol per beat, taken from the earliest match in the line, because a
    frame with three icons in it is a slide and not a shot
  * short, common words are left out entirely when they have a second meaning
    that is more common than the first

Everything is drawn in the same line art as the rest, from the theme's own
colours, so a symbol never looks pasted on.
"""

import re

import numpy as np
from matplotlib.patches import (Arc, Circle, FancyBboxPatch, Polygon,
                                Rectangle, Wedge)

from .themes import mix

# The vocabulary. Each symbol has strong words and weak ones.
#
# A strong word is one whose presence is what the line is about: "salary",
# "mortgage", "compound". A weak word is one that usually turns up in passing:
# "day" in "the same day", "year" in "five years later". Taking the earliest
# match regardless of strength puts a clock beside a line about a paycheck,
# because the sentence happened to say "day" first. So a weak word only wins
# when nothing strong matched anywhere in the line.
#
# Words with a common second meaning are left out rather than weakened:
# "pay" is in "pay attention", "fine" is in "that is fine", "return" is in
# "return home", "pound" is in "a pound of flour", "moved" is in "nobody
# moved", "left" is in "turn left", "nobody" is a negation and not a crowd.
# "payday", "penalty" and "abroad" carry the same ideas and cannot misfire.
VOCABULARY = [
    ("money",
     ("money", "cash", "salary", "paycheck", "paycheque", "wage", "wages",
      "income", "dollar", "dollars", "euro", "euros", "naira", "payday",
      "savings", "budget", "rent", "invoice", "refund", "overdraft",
      "mortgage"),
     ("save", "saving",
      "afford", "price", "cost", "costs", "expensive", "cheap", "bill",
      "bills", "deposit", "spend", "spending", "spent", "earn", "earns",
      "earning", "earned")),
    ("growth",
     ("compound", "compounding", "interest", "profit", "portfolio",
      "invest", "investing", "invested", "investment", "returns"),
     ("growth", "grow", "grows", "growing", "grew", "increase", "increases",
      "increased", "rise", "rises", "rising", "rose", "gain", "gains",
      "doubled", "doubling")),
    ("loss",
     ("debt", "debts", "overdrawn", "bankrupt", "repossessed"),
     ("loss", "losses", "lose", "loses", "losing", "lost", "falls",
      "falling", "fell", "drop", "drops", "dropped", "decline", "declines",
      "owe", "owes", "owing")),
    ("time",
     ("retire", "retires", "retirement", "deadline", "decade", "decades",
      "overnight", "anniversary"),
     ("year", "years", "month", "months", "week", "weeks", "day", "days",
      "hour", "hours", "minute", "minutes", "wait", "waiting", "waited",
      "later", "sooner", "eventually", "meanwhile")),
    ("mail",
     ("email", "emails", "inbox", "envelope", "newsletter", "letter",
      "letters"),
     ("message", "messages", "reply", "replied", "notification",
      "notifications")),
    ("home",
     ("house", "houses", "home", "homes", "apartment", "landlord", "tenant",
      "property"),
     ("flat", "rented")),
    ("idea",
     ("realise", "realised", "realize", "realized", "discover", "discovered",
      "trick", "secret"),
     ("idea", "ideas", "understand", "understood", "learn", "learned",
      "learnt", "figured", "notice", "noticed", "clever")),
    ("warning",
     ("mistake", "mistakes", "danger", "dangerous", "risky", "beware",
      "warning", "trap", "scam", "penalty", "fines"),
     ("wrong", "risk", "risks", "careful")),
    ("person",
     ("someone", "somebody", "person", "yourself", "myself", "himself",
      "herself", "stranger", "neighbour", "neighbor"),
     ("man", "woman", "people", "friend", "friends", "family")),
    ("group",
     ("everyone", "everybody", "crowd", "team", "audience", "community",
      "company", "companies", "employer", "employers", "colleagues"),
     ("together", "others", "anyone")),
    ("question",
     ("question", "questions", "why", "wonder", "wondered", "asking",
      "unclear", "confusing", "confused"),
     ("ask", "asked", "maybe", "perhaps")),
    ("yes",
     ("correct", "works", "agreed", "approved", "passed",
      "succeeded", "success"), ("yes", "sure", "good", "better")),
    ("no",
     ("refused", "rejected", "failed", "failure", "denied", "cancelled",
      "canceled", "stopped", "banned"), ("no", "never", "cannot", "without")),
    ("book",
     ("book", "books", "chapter", "story", "stories", "read", "reading",
      "study", "studying", "school", "college", "university", "course",
      "lesson", "lessons", "history"), ("wrote", "written", "page", "pages")),
    ("phone",
     ("phone", "phones", "called", "calling", "text", "texted", "app",
      "apps", "mobile"), ("call", "ring", "rang")),
    ("screen",
     ("computer", "laptop", "website", "online", "internet", "software",
      "browser", "screen", "video", "videos", "channel"),
     ("watch", "watched", "watching", "click", "clicked")),
    ("heart",
     ("love", "loved", "health", "healthy", "doctor", "hospital", "heart",
      "care", "kindness"), ("feel", "felt", "happy", "sad", "hurt")),
    ("place",
     ("city", "town", "country", "street", "journey", "travel", "travelled",
      "traveled", "abroad", "airport", "distance"),
     ("went", "going", "arrive", "arrived", "far", "near")),
    ("work",
     ("job", "jobs", "work", "working", "worked", "career", "office",
      "manager", "boss", "interview", "hired", "meeting"),
     ("business", "role", "shift")),
    ("calendar",
     ("schedule", "appointment", "monday", "tuesday", "wednesday",
      "thursday", "friday", "saturday", "sunday", "birthday", "plan",
      "planned", "planning"), ("date", "dates", "booked")),
    ("search",
     ("search", "searched", "searching", "looked", "looking", "found",
      "finding", "research", "investigate", "evidence", "proof"),
     ("find", "check", "checked", "spot", "spotted")),
    ("lock",
     ("password", "security", "secure", "private", "privacy", "safe",
      "safety", "protect", "protected", "locked", "account", "accounts"),
     ("lock", "key", "keys", "shut")),
    ("star",
     ("best", "favourite", "favorite", "award", "awards", "rated", "rating",
      "quality", "premium", "review", "reviews"),
     ("great", "brilliant", "excellent", "top")),
    ("target",
     ("goal", "goals", "target", "targets", "aim", "purpose",
      "strategy", "ambition", "achieve", "achieved"),
     ("want", "wanted", "trying", "tried")),
    ("chat",
     ("conversation", "argued", "argument", "explained", "explaining",
      "told", "telling", "advice", "advise", "interrupted"),
     ("said", "says", "talk", "talked", "talking", "speak", "spoke")),
]

SYMBOLS = tuple(name for name, _, _ in VOCABULARY)

# built once: word -> (symbol, strong), the first entry in the vocabulary
# winning a word that appears in two of them
_WORD_TO_SYMBOL = {}
for _name, _strong, _weak in VOCABULARY:
    for _w in _strong:
        _WORD_TO_SYMBOL.setdefault(_w, (_name, True))
    for _w in _weak:
        _WORD_TO_SYMBOL.setdefault(_w, (_name, False))

_WORDS = re.compile(r"[a-z']+")


def match(say):
    """The symbol this line asks for, or None.

    A strong word anywhere in the line beats a weak word earlier in it. Within
    a tier the earliest wins, because what a line is about is usually named
    before the thing being said about it.
    """
    first_weak = None
    for word in _WORDS.findall((say or "").lower()):
        found = _WORD_TO_SYMBOL.get(word)
        if not found:
            continue
        name, strong = found
        if strong:
            return name
        if first_weak is None:
            first_weak = name
    return first_weak


# ----------------------------------------------------------------------
# DRAWING
#
# Every symbol is built to the same rules so a run of them reads as one set:
# drawn inside a unit box centred on the origin, so the caller places and
# scales it; a heavy outline in the theme's ink and one flat accent fill; and
# nothing smaller than the outline weight, because these are seen for a few
# seconds at a time and detail turns to mush.

LW = 5.0                # matches the character outline
BOX = 1.0               # symbols are drawn inside -BOX..BOX and scaled by the caller


def _pen(T):
    """Outline, warm fill, cool fill."""
    return T.ink, mix(T.bg, T.a1, 0.55), mix(T.bg, T.a2, 0.55)


def _add(ax, patch, ink, lw=LW, z=6):
    patch.set_edgecolor(ink)
    patch.set_linewidth(lw)
    patch.set_joinstyle("round")
    patch.set_zorder(z)
    ax.add_patch(patch)
    return patch


def money(ax, T, x, y, s):
    """A banknote, with a second one behind it so it reads as an amount."""
    ink, warm, cool = _pen(T)
    for k, (dx, dy) in enumerate(((-0.16, 0.18), (0.0, 0.0))):
        _add(ax, FancyBboxPatch((x - 0.95 * s + dx * s, y - 0.56 * s + dy * s),
                                1.9 * s, 1.05 * s, facecolor=cool if k else warm,
                                boxstyle="round,pad=0,rounding_size=0.10"),
             ink, LW * s, z=6 + k)
    _add(ax, Circle((x, y), 0.30 * s, facecolor=warm), ink, LW * s, z=8)
    ax.plot([x, x], [y - 0.44 * s, y + 0.44 * s], color=ink, lw=LW * s * 0.7,
            solid_capstyle="round", zorder=9)


def growth(ax, T, x, y, s):
    """A line going up, with the arrow head that says which way to read it."""
    ink, warm, _ = _pen(T)
    xs = [x - 0.92 * s, x - 0.30 * s, x + 0.18 * s, x + 0.80 * s]
    ys = [y - 0.62 * s, y - 0.10 * s, y - 0.34 * s, y + 0.62 * s]
    ax.plot(xs, ys, color=ink, lw=LW * s * 1.25, solid_capstyle="round",
            solid_joinstyle="round", zorder=7)
    _add(ax, Polygon([(x + 0.92 * s, y + 0.78 * s),
                      (x + 0.30 * s, y + 0.66 * s),
                      (x + 0.78 * s, y + 0.16 * s)],
                     closed=True, facecolor=warm), ink, LW * s, z=8)


def loss(ax, T, x, y, s):
    """The same line, going the other way."""
    ink, _, cool = _pen(T)
    xs = [x - 0.92 * s, x - 0.30 * s, x + 0.18 * s, x + 0.80 * s]
    ys = [y + 0.62 * s, y + 0.10 * s, y + 0.34 * s, y - 0.62 * s]
    ax.plot(xs, ys, color=ink, lw=LW * s * 1.25, solid_capstyle="round",
            solid_joinstyle="round", zorder=7)
    _add(ax, Polygon([(x + 0.92 * s, y - 0.78 * s),
                      (x + 0.30 * s, y - 0.66 * s),
                      (x + 0.78 * s, y - 0.16 * s)],
                     closed=True, facecolor=cool), ink, LW * s, z=8)


def time(ax, T, x, y, s):
    """A clock. Hands at ten past ten, which is where clocks are drawn."""
    ink, _, cool = _pen(T)
    _add(ax, Circle((x, y), 0.82 * s, facecolor=cool), ink, LW * s * 1.1)
    for ang, length in ((np.pi / 2, 0.52), (np.pi * 0.16, 0.40)):
        ax.plot([x, x + length * s * np.cos(ang)],
                [y, y + length * s * np.sin(ang)],
                color=ink, lw=LW * s * 0.8, solid_capstyle="round", zorder=8)
    for k in range(12):
        a = k * np.pi / 6
        r0, r1 = 0.66, 0.74
        ax.plot([x + r0 * s * np.cos(a), x + r1 * s * np.cos(a)],
                [y + r0 * s * np.sin(a), y + r1 * s * np.sin(a)],
                color=ink, lw=LW * s * 0.35, solid_capstyle="round", zorder=8)


def mail(ax, T, x, y, s):
    """An envelope, flap open, because a closed one is just a rectangle."""
    ink, warm, _ = _pen(T)
    _add(ax, Rectangle((x - 0.95 * s, y - 0.62 * s), 1.9 * s, 1.24 * s,
                       facecolor=warm), ink, LW * s)
    ax.plot([x - 0.95 * s, x, x + 0.95 * s],
            [y + 0.62 * s, y - 0.12 * s, y + 0.62 * s],
            color=ink, lw=LW * s * 0.85, solid_capstyle="round",
            solid_joinstyle="round", zorder=8)


def home(ax, T, x, y, s):
    """A house: box, roof, door."""
    ink, warm, cool = _pen(T)
    _add(ax, Rectangle((x - 0.72 * s, y - 0.85 * s), 1.44 * s, 1.12 * s,
                       facecolor=cool), ink, LW * s)
    _add(ax, Polygon([(x - 0.95 * s, y + 0.26 * s), (x, y + 0.92 * s),
                      (x + 0.95 * s, y + 0.26 * s)],
                     closed=True, facecolor=warm), ink, LW * s, z=7)
    _add(ax, Rectangle((x - 0.22 * s, y - 0.85 * s), 0.44 * s, 0.62 * s,
                       facecolor=warm), ink, LW * s * 0.7, z=8)


def idea(ax, T, x, y, s):
    """A bulb. The rays are what stop it reading as a light switch."""
    ink, warm, _ = _pen(T)
    _add(ax, Circle((x, y + 0.14 * s), 0.56 * s, facecolor=warm), ink, LW * s)
    _add(ax, Rectangle((x - 0.26 * s, y - 0.82 * s), 0.52 * s, 0.42 * s,
                       facecolor=warm), ink, LW * s * 0.8, z=7)
    ax.plot([x - 0.26 * s, x + 0.26 * s], [y - 0.60 * s, y - 0.60 * s],
            color=ink, lw=LW * s * 0.6, solid_capstyle="round", zorder=8)
    for a in (0.35, 0.9, 1.45, 2.0, 2.55):
        a = a * np.pi / 3
        ax.plot([x + 0.74 * s * np.cos(a), x + 1.0 * s * np.cos(a)],
                [y + 0.14 * s + 0.74 * s * np.sin(a),
                 y + 0.14 * s + 1.0 * s * np.sin(a)],
                color=ink, lw=LW * s * 0.55, solid_capstyle="round", zorder=6)


def warning(ax, T, x, y, s):
    """A triangle with a bar and a dot. Read as a warning everywhere."""
    ink, warm, _ = _pen(T)
    _add(ax, Polygon([(x - 0.95 * s, y - 0.68 * s), (x + 0.95 * s, y - 0.68 * s),
                      (x, y + 0.88 * s)], closed=True, facecolor=warm),
         ink, LW * s * 1.1)
    ax.plot([x, x], [y - 0.14 * s, y + 0.36 * s], color=ink,
            lw=LW * s * 0.9, solid_capstyle="round", zorder=8)
    _add(ax, Circle((x, y - 0.38 * s), 0.09 * s, facecolor=ink), ink,
         LW * s * 0.4, z=8)


def _ring(ax, T, x, y, s, fill):
    """The disc several of the signs are set in."""
    ink = _pen(T)[0]
    _add(ax, Circle((x, y), 0.88 * s, facecolor=fill), ink, LW * s * 1.1)
    return ink


def _bust(ax, T, x, y, s, scale=1.0):
    """Head and shoulders, the shape a person is drawn as at this size."""
    ink, warm, _ = _pen(T)
    _add(ax, Circle((x, y + 0.34 * s * scale), 0.34 * s * scale,
                    facecolor=warm), ink, LW * s * 0.9 * scale)
    _add(ax, Wedge((x, y - 0.30 * s * scale), 0.62 * s * scale, 0, 180,
                   facecolor=warm), ink, LW * s * 0.9 * scale)


def person(ax, T, x, y, s):
    """One figure, for a line about somebody."""
    _bust(ax, T, x, y, s, 1.5)


def group(ax, T, x, y, s):
    """Two figures, for a line about people rather than a person."""
    _bust(ax, T, x - 0.52 * s, y - 0.08 * s, s, 1.05)
    _bust(ax, T, x + 0.52 * s, y - 0.08 * s, s, 1.05)


def question(ax, T, x, y, s):
    ink = _ring(ax, T, x, y, s, _pen(T)[2])
    ax.text(x, y - 0.06 * s, "?", ha="center", va="center", color=ink,
            fontsize=62 * s, fontweight="bold", zorder=9)


def yes(ax, T, x, y, s):
    ink = _ring(ax, T, x, y, s, _pen(T)[1])
    ax.plot([x - 0.40 * s, x - 0.10 * s, x + 0.44 * s],
            [y + 0.02 * s, y - 0.32 * s, y + 0.38 * s], color=ink,
            lw=LW * s * 1.5, solid_capstyle="round",
            solid_joinstyle="round", zorder=9)


def no(ax, T, x, y, s):
    ink = _ring(ax, T, x, y, s, _pen(T)[2])
    for dx in (-1, 1):
        ax.plot([x - dx * 0.34 * s, x + dx * 0.34 * s],
                [y - 0.34 * s, y + 0.34 * s], color=ink, lw=LW * s * 1.5,
                solid_capstyle="round", zorder=9)


def book(ax, T, x, y, s):
    """An open book, which reads as reading where a closed one reads as a
    brick."""
    ink, warm, cool = _pen(T)
    for side in (-1, 1):
        _add(ax, Polygon([(x, y - 0.62 * s), (x + side * 0.92 * s, y - 0.44 * s),
                          (x + side * 0.92 * s, y + 0.58 * s), (x, y + 0.40 * s)],
                         closed=True, facecolor=warm if side < 0 else cool),
             ink, LW * s)
    ax.plot([x, x], [y - 0.62 * s, y + 0.40 * s], color=ink, lw=LW * s * 0.8,
            solid_capstyle="round", zorder=9)


def phone(ax, T, x, y, s):
    ink, _, cool = _pen(T)
    _add(ax, FancyBboxPatch((x - 0.50 * s, y - 0.88 * s), 1.0 * s, 1.76 * s,
                            facecolor=cool,
                            boxstyle="round,pad=0,rounding_size=0.16"),
         ink, LW * s)
    ax.plot([x - 0.16 * s, x + 0.16 * s], [y + 0.66 * s, y + 0.66 * s],
            color=ink, lw=LW * s * 0.6, solid_capstyle="round", zorder=9)
    _add(ax, Circle((x, y - 0.62 * s), 0.11 * s, facecolor=ink), ink,
         LW * s * 0.4, z=9)


def screen(ax, T, x, y, s):
    ink, _, cool = _pen(T)
    _add(ax, FancyBboxPatch((x - 0.95 * s, y - 0.30 * s), 1.9 * s, 1.24 * s,
                            facecolor=cool,
                            boxstyle="round,pad=0,rounding_size=0.12"),
         ink, LW * s)
    ax.plot([x - 0.55 * s, x + 0.55 * s], [y - 0.72 * s, y - 0.72 * s],
            color=ink, lw=LW * s * 1.1, solid_capstyle="round", zorder=9)
    ax.plot([x, x], [y - 0.30 * s, y - 0.72 * s], color=ink, lw=LW * s * 0.9,
            solid_capstyle="round", zorder=8)


def heart(ax, T, x, y, s):
    ink, warm, _ = _pen(T)
    for dx in (-1, 1):
        _add(ax, Circle((x + dx * 0.36 * s, y + 0.30 * s), 0.46 * s,
                        facecolor=warm), ink, LW * s * 0.9, z=6)
    _add(ax, Polygon([(x - 0.79 * s, y + 0.36 * s), (x + 0.79 * s, y + 0.36 * s),
                      (x, y - 0.80 * s)], closed=True, facecolor=warm),
         ink, LW * s * 0.9, z=7)
    _add(ax, Circle((x - 0.36 * s, y + 0.30 * s), 0.40 * s, facecolor=warm),
         warm, 0.1, z=8)
    _add(ax, Circle((x + 0.36 * s, y + 0.30 * s), 0.40 * s, facecolor=warm),
         warm, 0.1, z=8)


def place(ax, T, x, y, s):
    """A map pin, which says somewhere without saying where."""
    ink, warm, _ = _pen(T)
    _add(ax, Polygon([(x - 0.62 * s, y + 0.22 * s),
                      (x + 0.62 * s, y + 0.22 * s), (x, y - 0.86 * s)],
                     closed=True, facecolor=warm), ink, LW * s, z=6)
    _add(ax, Circle((x, y + 0.30 * s), 0.64 * s, facecolor=warm), ink,
         LW * s, z=7)
    _add(ax, Circle((x, y + 0.30 * s), 0.24 * s, facecolor=T.bg), ink,
         LW * s * 0.8, z=8)


def work(ax, T, x, y, s):
    """A case, for a line about a job."""
    ink, _, cool = _pen(T)
    _add(ax, FancyBboxPatch((x - 0.95 * s, y - 0.62 * s), 1.9 * s, 1.12 * s,
                            facecolor=cool,
                            boxstyle="round,pad=0,rounding_size=0.14"),
         ink, LW * s, z=7)
    ax.plot([x - 0.34 * s, x - 0.34 * s, x + 0.34 * s, x + 0.34 * s],
            [y + 0.50 * s, y + 0.84 * s, y + 0.84 * s, y + 0.50 * s],
            color=ink, lw=LW * s * 0.9, solid_capstyle="round",
            solid_joinstyle="round", zorder=6)
    ax.plot([x - 0.95 * s, x + 0.95 * s], [y + 0.02 * s, y + 0.02 * s],
            color=ink, lw=LW * s * 0.7, zorder=8)


def calendar(ax, T, x, y, s):
    ink, _, cool = _pen(T)
    _add(ax, FancyBboxPatch((x - 0.86 * s, y - 0.82 * s), 1.72 * s, 1.54 * s,
                            facecolor=cool,
                            boxstyle="round,pad=0,rounding_size=0.12"),
         ink, LW * s)
    ax.plot([x - 0.86 * s, x + 0.86 * s], [y + 0.26 * s, y + 0.26 * s],
            color=ink, lw=LW * s * 0.9, zorder=9)
    for dx in (-0.40, 0.40):
        ax.plot([x + dx * s, x + dx * s], [y + 0.56 * s, y + 0.96 * s],
                color=ink, lw=LW * s * 0.9, solid_capstyle="round", zorder=9)
    for dx in (-0.42, 0.0, 0.42):
        _add(ax, Circle((x + dx * s, y - 0.24 * s), 0.11 * s, facecolor=ink),
             ink, LW * s * 0.3, z=9)


def search(ax, T, x, y, s):
    ink, _, cool = _pen(T)
    _add(ax, Circle((x - 0.16 * s, y + 0.20 * s), 0.60 * s, facecolor=cool),
         ink, LW * s * 1.2, z=8)
    ax.plot([x + 0.28 * s, x + 0.82 * s], [y - 0.24 * s, y - 0.78 * s],
            color=ink, lw=LW * s * 1.5, solid_capstyle="round", zorder=7)


def lock(ax, T, x, y, s):
    ink, warm, _ = _pen(T)
    ax.add_patch(Arc((x, y + 0.26 * s), 0.94 * s, 0.94 * s, theta1=0,
                     theta2=180, color=ink, lw=LW * s * 1.2, zorder=6))
    for dx in (-0.47, 0.47):
        ax.plot([x + dx * s, x + dx * s], [y + 0.26 * s, y - 0.04 * s],
                color=ink, lw=LW * s * 1.2, zorder=6)
    _add(ax, FancyBboxPatch((x - 0.76 * s, y - 0.78 * s), 1.52 * s, 0.92 * s,
                            facecolor=warm,
                            boxstyle="round,pad=0,rounding_size=0.12"),
         ink, LW * s, z=7)


def star(ax, T, x, y, s):
    ink, warm, _ = _pen(T)
    pts = []
    for k in range(10):
        a = np.pi / 2 + k * np.pi / 5
        r = (0.92 if k % 2 == 0 else 0.40) * s
        pts.append((x + r * np.cos(a), y + r * np.sin(a)))
    _add(ax, Polygon(pts, closed=True, facecolor=warm), ink, LW * s)


def target(ax, T, x, y, s):
    ink, warm, cool = _pen(T)
    # the big ring has to go underneath, or it covers the ones inside it
    for r, fill in ((0.90, cool), (0.56, T.bg), (0.22, warm)):
        _add(ax, Circle((x, y), r * s, facecolor=fill), ink, LW * s * 0.95,
             z=6 + int((1 - r) * 10))


def chat(ax, T, x, y, s):
    ink, warm, cool = _pen(T)
    _add(ax, FancyBboxPatch((x - 0.92 * s, y - 0.22 * s), 1.6 * s, 1.0 * s,
                            facecolor=warm,
                            boxstyle="round,pad=0,rounding_size=0.22"),
         ink, LW * s, z=7)
    _add(ax, Polygon([(x - 0.52 * s, y - 0.18 * s), (x - 0.14 * s, y - 0.18 * s),
                      (x - 0.46 * s, y - 0.74 * s)], closed=True,
                     facecolor=warm), ink, LW * s, z=6)
    _add(ax, FancyBboxPatch((x - 0.30 * s, y + 0.30 * s), 1.2 * s, 0.76 * s,
                            facecolor=cool,
                            boxstyle="round,pad=0,rounding_size=0.20"),
         ink, LW * s, z=8)


DRAW = {"money": money, "growth": growth, "loss": loss, "time": time,
        "mail": mail, "home": home, "idea": idea, "warning": warning,
        "person": person, "group": group, "question": question, "yes": yes,
        "no": no, "book": book, "phone": phone, "screen": screen,
        "heart": heart, "place": place, "work": work, "calendar": calendar,
        "search": search, "lock": lock, "star": star, "target": target,
        "chat": chat}


def draw(ax, name, T, x, y, s):
    """Draw one symbol, centred on (x, y), scaled by s in stage units."""
    fn = DRAW.get(name)
    if fn:
        fn(ax, T, x, y, s)
