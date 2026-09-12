"""
Phase 12 tests: multilingual input and the language ≠ jurisdiction
invariant (docs/PHASE_12_JURISDICTION_FIREWALL.md Sections R, S). Writing
a query in Devanagari or Tamil must never, by itself, be treated as an
India jurisdiction signal - jurisdiction comes only from the structured
jurisdiction contract (Phase 11's keyword-matched jurisdiction_input, or
an explicit override), never from script/language detection.
"""

from __future__ import annotations

from _jurisdiction_fixtures import classify_query

from jurisdiction.firewall import resolve_jurisdiction


def test_devanagari_query_without_india_keyword_is_not_india():
    # Devanagari text about Ayurveda/registration but with NO recognized
    # English jurisdiction keyword ("india"/"international") anywhere.
    cls = classify_query("ML1", "आयुर्वेद औषधि पंजीकरण के लिए आवेदन आवश्यक है")
    assert cls.jurisdiction_input == "UNSPECIFIED"
    decision = resolve_jurisdiction("MLD1", classification_result=cls)
    assert decision.state == "UNKNOWN"
    assert decision.normalized_jurisdiction != "INDIA"
    assert decision.allowed_jurisdictions == frozenset()


def test_tamil_query_without_india_keyword_is_not_india():
    cls = classify_query("ML2", "மருந்து பதிவு விண்ணப்பம் தேவை")
    assert cls.jurisdiction_input == "UNSPECIFIED"
    decision = resolve_jurisdiction("MLD2", classification_result=cls)
    assert decision.state == "UNKNOWN"


def test_mixed_script_query_still_requires_an_explicit_jurisdiction_keyword():
    cls = classify_query("ML3", "Ayurveda आयுர்वेद மருந்து query with no jurisdiction word")
    assert cls.jurisdiction_input == "UNSPECIFIED"
    decision = resolve_jurisdiction("MLD3", classification_result=cls)
    assert decision.state == "UNKNOWN"


def test_devanagari_query_with_explicit_india_keyword_resolves_to_india():
    # The English word "India" appearing alongside Devanagari text is a
    # genuine structured signal (Phase 11's own keyword match) - this is
    # NOT language-based inference, it is the same literal keyword rule
    # applied regardless of surrounding script.
    cls = classify_query("ML4", "आयुर्वेद औषधि पंजीकरण India के लिए")
    assert cls.jurisdiction_input == "INDIA"
    decision = resolve_jurisdiction("MLD4", classification_result=cls)
    assert decision.state == "KNOWN"
    assert decision.allowed_jurisdictions == frozenset({"INDIA"})


def test_english_query_about_india_topic_without_word_india_is_not_known():
    # Explicitly avoiding the word "India"/"Indian" even though the topic
    # (Ministry of Ayush) is India-specific in reality - jurisdiction is
    # never inferred from topic/source-family association either.
    cls = classify_query("ML5", "Tell me about Ministry of Ayush policy.")
    assert cls.jurisdiction_input == "UNSPECIFIED"
    decision = resolve_jurisdiction("MLD5", classification_result=cls)
    assert decision.state == "UNKNOWN"


def test_language_is_never_used_as_jurisdiction_inference_regression_guard():
    # A direct, explicit regression test for the "language != jurisdiction"
    # invariant: identical semantic content in three different
    # scripts/languages, none containing an explicit jurisdiction
    # keyword, must all resolve identically to UNKNOWN - never differently
    # based on which script/language was used.
    queries = [
        "What license do I need for my formulation?",
        "मुझे अपने फॉर्मूलेशन के लिए किस लाइसेंस की आवश्यकता है?",
        "எனது சூத்திரத்திற்கு எந்த உரிமம் தேவை?",
    ]
    decisions = []
    for i, q in enumerate(queries):
        cls = classify_query(f"ML6-{i}", q)
        decisions.append(resolve_jurisdiction(f"MLD6-{i}", classification_result=cls).state)
    assert decisions == ["UNKNOWN", "UNKNOWN", "UNKNOWN"]


def test_unicode_emoji_input_does_not_crash_and_does_not_resolve_jurisdiction():
    cls = classify_query("ML7", "What license do I need? 😀🙏")
    decision = resolve_jurisdiction("MLD7", classification_result=cls)
    assert decision.state == "UNKNOWN"
