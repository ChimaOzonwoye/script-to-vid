from app import engine, voices
from app.themes import THEMES


def test_curated_list_is_a_usable_size():
    """Hundreds of voices is a worse choice than none, so the list is picked
    rather than published. It grew past a dozen deliberately: the American
    neural voices people recognise from narrated video elsewhere are worth
    having even though they crowd the menu."""
    assert 8 <= len(voices.VOICES) <= 24


def test_accents_and_both_genders_are_covered():
    accents = {a for _, _, a, _ in voices.VOICES}
    genders = {g for _, _, _, g in voices.VOICES}
    assert len(accents) >= 4, accents
    assert genders == {"male", "female"}
    # every accent offers both, so nobody has to change accent to change gender
    for accent in accents:
        have = {g for _, _, a, g in voices.VOICES if a == accent}
        assert have == {"male", "female"}, (accent, have)


def test_ids_are_unique_and_look_like_edge_tts_english_voices():
    ids = voices.VOICE_IDS
    assert len(set(ids)) == len(ids)
    for vid in ids:
        assert vid.startswith("en-") and vid.endswith("Neural"), vid


def test_defaults_are_in_the_lists():
    assert voices.DEFAULT_VOICE in voices.VOICE_IDS
    assert voices.DEFAULT_RATE in voices.RATE_VALUES


def test_rates_are_three_signed_percentages():
    assert len(voices.RATES) == 3
    for value, label in voices.RATES:
        assert value[0] in "+-" and value.endswith("%"), value
        assert label


def test_unknown_saved_values_fall_back_rather_than_break():
    assert voices.valid_voice("en-XX-GoneNeural") == voices.DEFAULT_VOICE
    assert voices.valid_voice(None) == voices.DEFAULT_VOICE
    assert voices.valid_rate("+999%") == voices.DEFAULT_RATE


def test_listing_reports_whether_a_sample_exists():
    for v in voices.listing():
        assert set(v) == {"id", "name", "accent", "gender", "label", "has_sample"}
        assert isinstance(v["has_sample"], bool)


def test_changing_voice_invalidates_the_cached_narration():
    """The whole point: pick a new voice, hear the new voice."""
    a = engine.voice_key("a line", voices.VOICE_IDS[0], "-4%")
    b = engine.voice_key("a line", voices.VOICE_IDS[1], "-4%")
    assert a != b


def test_changing_rate_invalidates_the_cached_narration():
    a = engine.voice_key("a line", voices.DEFAULT_VOICE, "-4%")
    b = engine.voice_key("a line", voices.DEFAULT_VOICE, "+10%")
    assert a != b


def test_segment_key_follows_the_audio_so_a_voice_change_redraws_nothing_else():
    beat = {"visual": "caption", "say": "x", "caption": "X"}
    k1 = engine.segment_key(beat, THEMES["cream"],
                            engine.voice_key("x", voices.VOICE_IDS[0], "-4%"))
    k2 = engine.segment_key(beat, THEMES["cream"],
                            engine.voice_key("x", voices.VOICE_IDS[1], "-4%"))
    assert k1 != k2


def test_estimate_follows_the_speaking_rate():
    beats = [{"say": " ".join(["word"] * 155)}]
    slow = engine.estimate_seconds(beats, "-18%")
    normal = engine.estimate_seconds(beats, "-4%")
    fast = engine.estimate_seconds(beats, "+10%")
    assert slow > normal > fast
    # the default rate is the one WPM was measured at
    assert abs(normal - engine.estimate_seconds(beats)) < 0.01
