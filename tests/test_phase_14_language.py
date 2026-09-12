"""
Phase 14 tests: script detection, canonicalization, and the language-vs-
script distinction (docs/PHASE_14_MULTILINGUAL_DELIVERY.md Sections F,
K, L).
"""

from __future__ import annotations

import pytest

from multilingual.preservation import canonicalize_query, detect_script


# ---------------------------------------------------------------------------
# Script detection
# ---------------------------------------------------------------------------


def test_detect_script_latin():
    assert detect_script("What license do I need?") == "LATIN"


def test_detect_script_devanagari():
    assert detect_script("आयुर्वेद औषधि पंजीकरण") == "DEVANAGARI"


def test_detect_script_tamil():
    assert detect_script("மருந்து பதிவு விண்ணப்பம்") == "TAMIL"


def test_detect_script_mixed():
    assert detect_script("Ayurveda आयुर்वेद மருந்து") == "MIXED"


def test_detect_script_unknown_for_empty_string():
    assert detect_script("") == "UNKNOWN"


def test_detect_script_unknown_for_digits_and_punctuation_only():
    assert detect_script("123 !@# 456") == "UNKNOWN"


def test_detect_script_rejects_non_string():
    with pytest.raises(TypeError):
        detect_script(12345)


# ---------------------------------------------------------------------------
# Canonicalization
# ---------------------------------------------------------------------------


def test_canonicalize_is_unicode_nfc_normalization():
    # 'e' + combining acute accent (U+0301) NFC-normalizes to the single
    # precomposed character 'é' (U+00E9).
    decomposed = "é"
    canonical = canonicalize_query(decomposed)
    assert canonical == "é"


def test_canonicalize_never_translates():
    text = "आयुर्वेद औषधि पंजीकरण"
    assert canonicalize_query(text) == text  # already NFC; unchanged, never translated


def test_canonicalize_never_changes_ascii_text():
    text = "What license do I need?"
    assert canonicalize_query(text) == text


def test_canonicalize_rejects_non_string():
    with pytest.raises(TypeError):
        canonicalize_query(None)


# ---------------------------------------------------------------------------
# Script vs language - explicit distinction, per instruction
# ---------------------------------------------------------------------------


def test_devanagari_script_is_not_automatically_hindi_language():
    # detect_script has no concept of "language" at all - it returns a
    # SCRIPT tag only; nothing anywhere derives a language tag from it.
    script = detect_script("आयुर्वेद औषधि पंजीकरण")
    assert script == "DEVANAGARI"
    assert script != "hi"  # not even the same vocabulary/type


def test_tamil_script_is_not_automatically_a_jurisdiction():
    script = detect_script("மருந்து பதிவு")
    assert script == "TAMIL"
    assert script not in {"INDIA", "INTERNATIONAL", "BOTH", "UNSPECIFIED"}


def test_mixed_script_is_not_multiple_jurisdictions():
    script = detect_script("Ayurveda आயுர்वेद மருந்து")
    assert script == "MIXED"
    # MIXED describes SCRIPT composition only - it has no relationship to
    # Phase 12's jurisdiction vocabulary at all.
    from jurisdiction.models import EVIDENCE_JURISDICTION_VALUES, REQUEST_JURISDICTION_VALUES

    assert script not in REQUEST_JURISDICTION_VALUES
    assert script not in EVIDENCE_JURISDICTION_VALUES
