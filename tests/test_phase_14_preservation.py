"""
Phase 14 tests: original-input preservation and MultilingualInputContext
invariants (docs/PHASE_14_MULTILINGUAL_DELIVERY.md Sections J, K, L).
"""

from __future__ import annotations

import pytest

from multilingual.models import MultilingualInputContext
from multilingual.preservation import build_input_context


def test_original_query_recoverable_from_context():
    text = "What license do I need?"
    ctx = build_input_context("P1", text, requested_language="en")
    assert ctx.original_query == text


def test_original_query_never_overwritten_by_canonical_query():
    text = "आयुर्वेद औषधि पंजीकरण"
    ctx = build_input_context("P2", text)
    assert ctx.original_query == text
    assert ctx.canonical_query == text  # already NFC-normalized, but stored as a SEPARATE field either way


def test_canonical_and_original_are_distinguishable_fields():
    ctx = build_input_context("P3", "é")  # 'e' + combining acute accent
    assert ctx.original_query == "é"
    assert ctx.canonical_query == "é"
    assert ctx.original_query != ctx.canonical_query


def test_requested_language_defaults_to_none_never_guessed():
    ctx = build_input_context("P4", "आयुर्वेद औषधि पंजीकरण")
    assert ctx.requested_language is None


def test_build_input_context_rejects_empty_input_id():
    with pytest.raises(ValueError):
        build_input_context("", "query")


def test_build_input_context_rejects_non_string_query():
    with pytest.raises(TypeError):
        build_input_context("P5", 12345)


def test_build_input_context_rejects_non_string_requested_language():
    with pytest.raises(TypeError):
        build_input_context("P6", "query", requested_language=12345)


def test_build_input_context_accepts_empty_query():
    ctx = build_input_context("P7", "")
    assert ctx.original_query == ""
    assert ctx.detected_script == "UNKNOWN"


def test_input_context_rejects_invalid_detected_script_directly():
    with pytest.raises(ValueError):
        MultilingualInputContext(
            schema_version="1.0.0", input_id="X", original_query="q", canonical_query="q",
            detected_script="KLINGON", requested_language=None,
        )


def test_input_context_permissive_of_arbitrary_requested_language_string():
    # requested_language is untrusted, permissive input (like Phase 9's
    # CitationReference) - classification as supported/unsupported
    # happens later, in delivery.deliver_response, never at construction.
    ctx = MultilingualInputContext(
        schema_version="1.0.0", input_id="X", original_query="q", canonical_query="q",
        detected_script="LATIN", requested_language="totally-unsupported-value",
    )
    assert ctx.requested_language == "totally-unsupported-value"
