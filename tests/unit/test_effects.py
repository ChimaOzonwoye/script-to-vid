"""The weather layer.

One property matters more than everything else here: the loop has to close.
The same short sequence of frames plays over and over under a ten minute
video, so if the last frame does not lead back into the first, the picture
hiccups once a second for the whole thing.

That is not something you get by picking a speed that looks right. The
distance a particle travels over the loop has to be a whole number of wrap
periods, which is why laps are integers and speed is chosen by choosing laps.
The first version of this module picked nice-looking speeds and five of the
six effects landed mid-fall.
"""

import numpy as np
import pytest

from app import effects
from app.themes import THEMES


@pytest.mark.parametrize("name", sorted(effects.EFFECTS))
def test_the_loop_closes(name):
    """Frame n has to be frame 0 again, exactly."""
    frames, _, field = effects.EFFECTS[name](THEMES["nightfall"])
    first, wrapped = field(0), field(frames)
    assert np.allclose(first, wrapped, atol=1e-9), (
        f"{name} jumps: largest difference {np.abs(first - wrapped).max():.4f}")


@pytest.mark.parametrize("name", sorted(effects.EFFECTS))
def test_something_actually_moves(name):
    """A loop that closes because nothing ever moved would pass the test
    above and be a texture."""
    frames, _, field = effects.EFFECTS[name](THEMES["nightfall"])
    a, b = field(0), field(frames // 3)
    assert np.abs(a - b).mean() > 1e-4, f"{name} is static"


@pytest.mark.parametrize("name", sorted(effects.EFFECTS))
def test_the_layer_is_mostly_transparent(name):
    """It goes over the whole frame. Anything dense enough to hide what is
    behind it is not weather, it is a wall."""
    frames, _, field = effects.EFFECTS[name](THEMES["nightfall"])
    covered = (field(0) > 0.5).mean()
    assert covered < 0.25, f"{name} covers {covered:.0%} of the frame"


def test_the_key_follows_the_palette():
    """The particles are drawn in the template's colours, so two templates
    cannot share one cached loop."""
    a = effects.key("rain", THEMES["nightfall"])
    b = effects.key("rain", THEMES["cream"])
    c = effects.key("snow", THEMES["nightfall"])
    assert len({a, b, c}) == 3


def test_an_unknown_effect_is_nothing_rather_than_an_error(tmp_path):
    assert effects.build("none", THEMES["cream"], tmp_path) is None
    assert effects.build("hurricane", THEMES["cream"], tmp_path) is None
