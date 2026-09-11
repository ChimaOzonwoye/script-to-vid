from app import engine
from app.themes import THEMES


def test_estimate_tracks_word_count():
    beats = [{"say": " ".join(["word"] * 155)}]
    est = engine.estimate_seconds(beats)
    assert 60 <= est <= 62   # a minute of speech plus per-beat padding


def test_voice_key_changes_with_text_voice_and_rate():
    k = engine.voice_key("hello", engine.VOICE, engine.RATE)
    assert k == engine.voice_key("hello", engine.VOICE, engine.RATE)
    assert k != engine.voice_key("hello there", engine.VOICE, engine.RATE)
    assert k != engine.voice_key("hello", "en-GB-RyanNeural", engine.RATE)
    assert k != engine.voice_key("hello", engine.VOICE, "-10%")


def test_segment_key_covers_theme_and_beat():
    b = {"visual": "caption", "say": "x", "caption": "X"}
    k = engine.segment_key(b, THEMES["cream"], "audiokey")
    assert k == engine.segment_key(dict(b), THEMES["cream"], "audiokey")
    assert k != engine.segment_key(b, THEMES["sky"], "audiokey")
    assert k != engine.segment_key({**b, "caption": "Y"}, THEMES["cream"], "audiokey")
    assert k != engine.segment_key(b, THEMES["cream"], "otherkey")


def test_srt_time():
    assert engine.srt_time(0) == "00:00:00,000"
    assert engine.srt_time(61.5) == "00:01:01,500"
    assert engine.srt_time(3599.25) == "00:59:59,250"


def test_every_slide_visual_renders(tmp_path):
    beats = {
        "sweep": {"headline": "One line|Two line"},
        "title": {"headline": "TITLE", "sub": "sub"},
        "chapter": {"num": "01", "headline": "CHAPTER"},
        "gauge": {"headline": "GAUGE"},
        "callout": {"headline": "CALLOUT"},
        "caption": {"caption": "A plain caption"},
        "timeline": {"headline": "TIMELINE"},
        "jars": {"headline": "JARS"},
        "terms": {"headline": "TERMS", "words": ["A?", "B?"]},
        "path": {"headline": "PATH", "sub": "sub"},
        "growth": {"headline": "GROWTH"},
        "quiet": {"headline": "QUIET", "sub": "sub"},
        "recap": {"headline": "RECAP", "items": ["one", "two", "three"]},
        "outro": {"headline": "NEXT", "sub": "sub", "brand": "NDN"},
    }
    assert set(beats) == set(engine.VISUALS)
    for visual, extra in beats.items():
        p = tmp_path / f"{visual}.png"
        engine.render_slide({"visual": visual, "say": "x", **extra}, p,
                            THEMES["paper"])
        assert p.stat().st_size > 0


def test_every_scene_visual_renders(tmp_path):
    from app import scenes
    beats = {
        "scene_presenter": {"caption": "Words beside them", "side": "left"},
        "scene_story": {"say": "Five years later it was money",
                        "symbol": "money"},
        # no image, so this falls back to the story frame, which is the case
        # worth pinning: a photo template on a project with no pictures
        "scene_photo": {"say": "Five years later it was money",
                        "symbol": "money"},
        "scene_character": {"expr": "happy", "pose": "cheer", "prop": "piggy",
                            "caption": "Cap"},
        "scene_caption": {"caption": "Big caption"},
        "scene_duo": {"bubble": "Hello", "caption": "Cap"},
        "scene_bubbles": {"words": ["APR?", "FICO?"], "caption": "Cap"},
        "scene_split": {"left": "Before", "right": "After", "caption": "Cap"},
        "scene_chart": {"chart": "timeline", "caption": "Cap"},
    }
    assert set(beats) == set(scenes.VISUALS)
    for visual, extra in beats.items():
        p = tmp_path / f"{visual}.png"
        engine.render_slide({"visual": visual, "say": "x", "cast_i": 1, **extra},
                            p, THEMES["mint"])
        assert p.stat().st_size > 0


def test_a_part_only_ever_ends_on_a_beat_boundary():
    """The seam between two parts has to land where the video already cut, or
    the join shows. Beats are paragraphs, so this is also what stops a part
    ending part-way through a sentence."""
    seconds = [3.0, 41.0, 7.5, 62.0, 19.0, 8.0, 30.0]
    ranges = engine.part_ranges(seconds, target=50.0, floor=0.0)
    assert ranges[0][0] == 0
    assert ranges[-1][1] == len(seconds)
    for (_, end), (start, _) in zip(ranges, ranges[1:]):
        assert end == start, "a beat fell between two parts or into both"
    assert sum(sum(seconds[a:b]) for a, b in ranges) == sum(seconds)


def test_a_short_tail_is_folded_into_the_part_before_it():
    """Splitting 160 seconds at 150 would leave a ten second file on its own."""
    assert engine.part_ranges([10.0] * 16, target=150.0, floor=25.0) == [(0, 16)]
    assert engine.part_ranges([10.0] * 18, target=150.0, floor=25.0) == \
        [(0, 15), (15, 18)]


def test_one_short_video_is_one_part():
    assert engine.part_ranges([4.0] * 5) == [(0, 5)]


def test_the_part_key_covers_where_it_sits_in_the_music():
    """Two parts can hold the same beats and still need different encodes: the
    music under them comes from a different stretch of the bed."""
    a = engine.part_key(["x", "y"], None, None, 0.0, first=True, last=False)
    b = engine.part_key(["x", "y"], None, None, 90.0, first=True, last=False)
    c = engine.part_key(["x", "y"], None, None, 0.0, first=False, last=False)
    assert len({a, b, c}) == 3


def test_a_storytelling_template_draws_no_figure(tmp_path):
    """The whole point of the layout: a frame with nobody in it. Skin is the
    one colour only a character is drawn in, so counting it answers this
    without caring how the figure is built."""
    import numpy as np
    from PIL import Image
    from app import characters as ch
    from app.script_parser import parse
    from app.themes import THEMES, resolve

    beat = parse("Five years later it was a twelve thousand dollar difference."
                 )["beats"][0]
    assert beat["symbol"] == "money"
    skin = np.array([int(ch.SKIN[i:i + 2], 16) for i in (1, 3, 5)])

    def skin_pixels(T):
        p = tmp_path / f"{T.name}_{T.layout}.png"
        engine.render_slide(beat, p, T)
        im = np.asarray(Image.open(p).convert("RGB")).astype(int)
        return int((np.abs(im - skin).max(axis=2) < 10).sum())

    assert skin_pixels(resolve("cream")) > 5000, "the presenter lost its figure"
    assert skin_pixels(THEMES["nightfall"]) == 0, "a story frame drew a figure"
