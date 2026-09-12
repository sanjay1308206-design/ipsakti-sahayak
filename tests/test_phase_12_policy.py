"""
Phase 12 tests: normalization and corpus-policy mapping
(docs/PHASE_12_JURISDICTION_FIREWALL.md Sections I, J).
"""

from __future__ import annotations

import pytest

from jurisdiction.models import EVIDENCE_JURISDICTION_VALUES
from jurisdiction.policy import (
    blocked_evidence_jurisdictions,
    normalize_requested_jurisdiction,
    permitted_evidence_jurisdictions,
)


# ---------------------------------------------------------------------------
# Normalization - case/whitespace folding of the four canonical tokens only
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw,expected", [
    ("INDIA", "INDIA"),
    ("india", "INDIA"),
    (" India ", "INDIA"),
    ("INTERNATIONAL", "INTERNATIONAL"),
    ("international", "INTERNATIONAL"),
    ("Both", "BOTH"),
    ("UNSPECIFIED", "UNSPECIFIED"),
    ("unspecified", "UNSPECIFIED"),
])
def test_normalize_recognizes_case_and_whitespace_variants(raw, expected):
    assert normalize_requested_jurisdiction(raw) == expected


@pytest.mark.parametrize("raw", ["FRANCE", "USA", "WORLD", "GLOBAL", "", "   ", "IND1A"])
def test_normalize_never_guesses_unrecognized_values(raw):
    assert normalize_requested_jurisdiction(raw) is None


def test_normalize_handles_none():
    assert normalize_requested_jurisdiction(None) is None


def test_normalize_handles_wrong_type():
    assert normalize_requested_jurisdiction(12345) is None
    assert normalize_requested_jurisdiction(["INDIA"]) is None


def test_normalize_never_maps_a_country_name_to_international():
    # Explicit instruction: do not collapse COUNTRY-X into INTERNATIONAL
    # merely because it is "foreign" - no country-level vocabulary exists.
    for country in ("FRANCE", "GERMANY", "JAPAN", "USA", "UNITED KINGDOM"):
        assert normalize_requested_jurisdiction(country) is None


# ---------------------------------------------------------------------------
# Corpus-policy mapping
# ---------------------------------------------------------------------------


def test_india_maps_to_india_only():
    assert permitted_evidence_jurisdictions("INDIA") == frozenset({"INDIA"})


def test_international_maps_to_international_only():
    assert permitted_evidence_jurisdictions("INTERNATIONAL") == frozenset({"INTERNATIONAL"})


def test_both_maps_to_union():
    assert permitted_evidence_jurisdictions("BOTH") == frozenset({"INDIA", "INTERNATIONAL"})


def test_unspecified_maps_to_empty_set():
    assert permitted_evidence_jurisdictions("UNSPECIFIED") == frozenset()


def test_unrecognized_value_maps_to_empty_set_fail_closed():
    assert permitted_evidence_jurisdictions("FRANCE") == frozenset()
    assert permitted_evidence_jurisdictions(None) == frozenset()


def test_permitted_never_includes_not_applicable_or_other_unspecified():
    for value in ("INDIA", "INTERNATIONAL", "BOTH"):
        allowed = permitted_evidence_jurisdictions(value)
        assert "NOT_APPLICABLE" not in allowed
        assert "OTHER_UNSPECIFIED" not in allowed


def test_blocked_is_exact_complement():
    allowed = frozenset({"INDIA"})
    blocked = blocked_evidence_jurisdictions(allowed)
    assert allowed | blocked == EVIDENCE_JURISDICTION_VALUES
    assert allowed & blocked == frozenset()


def test_blocked_of_empty_allowed_is_everything():
    assert blocked_evidence_jurisdictions(frozenset()) == EVIDENCE_JURISDICTION_VALUES


def test_blocked_of_full_allowed_is_empty():
    assert blocked_evidence_jurisdictions(EVIDENCE_JURISDICTION_VALUES) == frozenset()
