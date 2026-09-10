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
