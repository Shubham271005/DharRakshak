"""
Unit tests for the Groq client helpers that don't need the network (C9).
"""

from backend.services.llm import clean_transcript


def test_real_speech_is_kept():
    payload = {"text": "लोन के लिए कौन से कागज़ बाकी हैं?", "segments": [
        {"text": " लोन के लिए कौन से कागज़ बाकी हैं?", "no_speech_prob": 0.02}]}
    assert clean_transcript(payload) == "लोन के लिए कौन से कागज़ बाकी हैं?"


def test_segments_flagged_as_non_speech_are_dropped():
    payload = {"segments": [
        {"text": " नमस्ते", "no_speech_prob": 0.95},
        {"text": " मेरी फसल में धब्बे हैं", "no_speech_prob": 0.1}]}
    assert clean_transcript(payload) == "मेरी फसल में धब्बे हैं"


def test_all_noise_gives_empty_text():
    payload = {"segments": [{"text": " Thank you.", "no_speech_prob": 0.9}]}
    assert clean_transcript(payload) == ""


def test_repeated_single_word_is_treated_as_hallucination():
    # What Whisper produced from a plain beep during testing.
    assert clean_transcript({"text": "प्रस्तुति प्रस्तुति प्रस्तुति"}) == ""
    assert clean_transcript({"text": "you you you."}) == ""


def test_plain_json_without_segments_still_works():
    assert clean_transcript({"text": " Why should I inspect nearby plants? "}) == "Why should I inspect nearby plants?"
