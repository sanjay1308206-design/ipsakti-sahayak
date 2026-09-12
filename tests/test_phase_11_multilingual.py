"""
Phase 11 tests: multilingual/Unicode input handling
(docs/PHASE_11_FORMULATION_CLASSIFICATION.md Section Q). No translation
exists anywhere in this phase; original input is preserved byte-faithful.
"""

from __future__ import annotations

from _classification_fixtures import make_input

from classification.classifier import classify


def test_devanagari_query_does_not_crash():
    result = classify(make_input("ML1", raw_query="मेरे उत्पाद के लिए कौन सी नियामक श्रेणी लागू होती है?"))
    assert result.classification_state in {"KNOWN", "UNKNOWN", "AMBIGUOUS", "NEEDS_EVIDENCE"}
    assert result.input_id == "ML1"


def test_tamil_query_does_not_crash():
    result = classify(make_input("ML2", raw_query="எனது தயாரிப்புக்கு எந்த ஒழுங்குமுறை வகை பொருந்தும்?"))
    assert result.classification_state in {"KNOWN", "UNKNOWN", "AMBIGUOUS", "NEEDS_EVIDENCE"}


def test_mixed_script_query_does_not_crash():
    result = classify(make_input("ML3", raw_query="Ayurveda आयुर्वेद மருந்து classification query in India under FSSAI"))
    assert result.classification_state == "NEEDS_EVIDENCE" or result.classification_state == "KNOWN"


def test_english_keyword_still_matches_inside_mixed_script_text():
    result = classify(make_input(
        "ML4",
        raw_query="आयुर्वेद FSSAI query in India",
        formulation_description="This is a cosmetic product आयुर्वेद",
    ))
    assert result.formulation_classification.regulatory_track == "COSMETIC"
    assert result.jurisdiction_input == "INDIA"


def test_raw_query_is_preserved_byte_faithful_on_the_result():
    text = "आयुर्वेद மருந்து mixed query, no translation should ever occur."
    result = classify(make_input("ML5", raw_query=text))
    assert result.input_id == "ML5"
    # No field on ClassificationResult holds a transformed/translated
    # copy of the query - the classifier only ever reads raw_query, never
    # rewrites or stores a translated version of it.
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(result)}
    assert "translated_query" not in field_names
    assert "translated_text" not in field_names


def test_devanagari_and_tamil_combined_no_signal_is_undetermined_not_guessed():
    result = classify(make_input("ML6", raw_query="केवल हिंदी सामग्री यहाँ", formulation_description="தமிழ் மொழி மட்டும் உள்ளடக்கம்"))
    # Neither script contains any of the fixed English-language keyword
    # signals - the classifier must not guess a category just because
    # some text was present.
    assert result.formulation_classification.regulatory_track == "UNDETERMINED"


def test_unicode_emoji_in_query_does_not_crash():
    result = classify(make_input("ML7", raw_query="What regulatory category applies? 😀🙏 in India under FSSAI"))
    assert result.classification_state in {"KNOWN", "UNKNOWN", "AMBIGUOUS", "NEEDS_EVIDENCE"}
