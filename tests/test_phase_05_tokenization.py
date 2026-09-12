"""
Phase 5 tests: tokenization/normalization baseline - English, Devanagari,
Tamil, mixed Unicode, punctuation, numbers, hyphenated text, repeated
whitespace, empty text (docs/PHASE_05_BM25_BASELINE.md Sections C/D/F).
"""

from __future__ import annotations

import pytest

from retrieval.tokenizer import TOKENIZER_POLICY_VERSION, tokenize


# ---------------------------------------------------------------------------
# 8. English / general
# ---------------------------------------------------------------------------


def test_english_text_tokenizes_into_lowercase_words():
    assert tokenize("Trademark Registration Office") == ["trademark", "registration", "office"]


def test_case_is_normalized():
    assert tokenize("TRADEMARK") == tokenize("trademark") == ["trademark"]


# ---------------------------------------------------------------------------
# 9. Devanagari
# ---------------------------------------------------------------------------


def test_devanagari_text_tokenizes_without_crashing():
    tokens = tokenize("आयुर्वेद औषधि पंजीकरण आवश्यक है")
    assert tokens == ["आयुर्वेद", "औषधि", "पंजीकरण", "आवश्यक", "है"]


def test_devanagari_lower_is_a_no_op():
    text = "औषधि पंजीकरण"
    assert tokenize(text) == tokenize(text.lower())


# ---------------------------------------------------------------------------
# 10. Tamil
# ---------------------------------------------------------------------------


def test_tamil_text_tokenizes_without_crashing():
    tokens = tokenize("மருந்து பதிவு விண்ணப்பம்")
    assert tokens == ["மருந்து", "பதிவு", "விண்ணப்பம்"]


# ---------------------------------------------------------------------------
# 11. Mixed-language text
# ---------------------------------------------------------------------------


def test_mixed_script_text_tokenizes_each_script_correctly():
    tokens = tokenize("Ayurveda आयुर्वेद மருந்து registration")
    assert tokens == ["ayurveda", "आयुर्वेद", "மருந்து", "registration"]


# ---------------------------------------------------------------------------
# 12. Punctuation and numbers
# ---------------------------------------------------------------------------


def test_punctuation_is_stripped_as_a_separator():
    assert tokenize("Section 3.2.1, clause (b): applies.") == ["section", "3", "2", "1", "clause", "b", "applies"]


def test_numbers_tokenize_as_their_own_tokens():
    assert tokenize("PS 26045 filed in 2024") == ["ps", "26045", "filed", "in", "2024"]


def test_hyphenated_text_splits_into_separate_tokens():
    assert tokenize("well-known trademark") == ["well", "known", "trademark"]


# ---------------------------------------------------------------------------
# 13. Whitespace normalization
# ---------------------------------------------------------------------------


def test_repeated_whitespace_collapses_to_the_same_tokens():
    assert tokenize("one   two\t\tthree\n\nfour") == ["one", "two", "three", "four"]


def test_empty_text_tokenizes_to_empty_list():
    assert tokenize("") == []


def test_whitespace_only_text_tokenizes_to_empty_list():
    assert tokenize("   \t\n  ") == []


# ---------------------------------------------------------------------------
# Type safety / misc
# ---------------------------------------------------------------------------


def test_tokenize_rejects_non_string_input():
    with pytest.raises(TypeError):
        tokenize(None)
    with pytest.raises(TypeError):
        tokenize(12345)


def test_tokenizer_policy_version_is_a_fixed_stable_string():
    assert TOKENIZER_POLICY_VERSION == "v1"


def test_unicode_normalization_collapses_equivalent_representations():
    # "e-acute" as a single precomposed codepoint (U+00E9) vs a plain "e"
    # (U+0065) followed by a combining acute accent (U+0301) - visually
    # identical when rendered, but distinct underlying codepoint sequences
    # until NFKC-normalized (docs/PHASE_05_BM25_BASELINE.md Section D).
    precomposed = "café"
    decomposed = "café"
    assert precomposed != decomposed  # sanity: genuinely different source strings
    assert tokenize(precomposed) == tokenize(decomposed) == ["café"]
