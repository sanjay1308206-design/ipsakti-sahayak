"""
Phase 12 tests: core model invariants and end-to-end jurisdiction
resolution (docs/PHASE_12_JURISDICTION_FIREWALL.md Sections F, G, H, J).
"""

from __future__ import annotations

import dataclasses

import pytest
from _jurisdiction_fixtures import classify_query

from jurisdiction.firewall import resolve_jurisdiction
from jurisdiction.models import (
    EVIDENCE_JURISDICTION_VALUES,
    JURISDICTION_REASON_CODES,
    JURISDICTION_STATES,
    REQUEST_JURISDICTION_VALUES,
    JurisdictionDecision,
    JurisdictionFirewallConfig,
)


# ---------------------------------------------------------------------------
# Vocabularies - reused, never redefined
# ---------------------------------------------------------------------------


def test_request_jurisdiction_vocabulary_matches_phase_1():
    assert REQUEST_JURISDICTION_VALUES == {"INDIA", "INTERNATIONAL", "BOTH", "UNSPECIFIED"}


def test_evidence_jurisdiction_vocabulary_matches_phase_2():
    assert EVIDENCE_JURISDICTION_VALUES == {"INDIA", "INTERNATIONAL", "NOT_APPLICABLE", "OTHER_UNSPECIFIED"}


def test_the_two_vocabularies_are_distinct():
    assert REQUEST_JURISDICTION_VALUES != EVIDENCE_JURISDICTION_VALUES
    assert "BOTH" in REQUEST_JURISDICTION_VALUES and "BOTH" not in EVIDENCE_JURISDICTION_VALUES
    assert "NOT_APPLICABLE" in EVIDENCE_JURISDICTION_VALUES and "NOT_APPLICABLE" not in REQUEST_JURISDICTION_VALUES


def test_jurisdiction_states_closed_vocabulary():
    assert JURISDICTION_STATES == {"KNOWN", "UNKNOWN", "AMBIGUOUS", "NEEDS_EVIDENCE"}


def test_reason_codes_closed_vocabulary():
    assert JURISDICTION_REASON_CODES == {
        "EXPLICIT_JURISDICTION_ACCEPTED",
        "JURISDICTION_UNKNOWN",
        "JURISDICTION_AMBIGUOUS",
        "JURISDICTION_NOT_SUPPORTED",
        "JURISDICTION_METADATA_INVALID",
        "CORPUS_NOT_PERMITTED",
        "CROSS_JURISDICTION_EVIDENCE_BLOCKED",
    }


# ---------------------------------------------------------------------------
# End-to-end resolution via Phase 11's ClassificationResult
# ---------------------------------------------------------------------------


def test_explicit_india_via_classification_result_is_known():
    cls = classify_query("Q1", "What category applies in India under FSSAI?")
    assert cls.jurisdiction_input == "INDIA"
    decision = resolve_jurisdiction("D1", classification_result=cls)
    assert decision.state == "KNOWN"
    assert decision.reason_code == "EXPLICIT_JURISDICTION_ACCEPTED"
    assert decision.allowed_jurisdictions == frozenset({"INDIA"})
    assert decision.blocked_jurisdictions == frozenset({"INTERNATIONAL", "NOT_APPLICABLE", "OTHER_UNSPECIFIED"})


def test_explicit_international_via_classification_result_is_known():
    cls = classify_query("Q2", "This is an international matter under WIPO.")
    assert cls.jurisdiction_input == "INTERNATIONAL"
    decision = resolve_jurisdiction("D2", classification_result=cls)
    assert decision.state == "KNOWN"
    assert decision.allowed_jurisdictions == frozenset({"INTERNATIONAL"})


def test_unspecified_jurisdiction_fails_closed_to_unknown():
    cls = classify_query("Q3", "Tell me about Ministry of Ayush policy.")  # no jurisdiction signal
    assert cls.jurisdiction_input == "UNSPECIFIED"
    decision = resolve_jurisdiction("D3", classification_result=cls)
    assert decision.state == "UNKNOWN"
    assert decision.reason_code == "JURISDICTION_UNKNOWN"
    assert decision.allowed_jurisdictions == frozenset()


def test_both_jurisdictions_resolves_known_with_union():
    cls = classify_query("Q4", "This concerns India and also international matters under WIPO.")
    assert cls.jurisdiction_input == "BOTH"
    decision = resolve_jurisdiction("D4", classification_result=cls)
    assert decision.state == "KNOWN"
    assert decision.allowed_jurisdictions == frozenset({"INDIA", "INTERNATIONAL"})


def test_explicit_override_alone_works_without_classification_result():
    decision = resolve_jurisdiction("D5", explicit_jurisdiction="india")
    assert decision.state == "KNOWN"
    assert decision.normalized_jurisdiction == "INDIA"


def test_no_signal_at_all_fails_closed():
    decision = resolve_jurisdiction("D6")
    assert decision.state == "UNKNOWN"
    assert decision.reason_code == "JURISDICTION_UNKNOWN"
    assert decision.allowed_jurisdictions == frozenset()


def test_unsupported_specific_country_is_unknown_not_known():
    decision = resolve_jurisdiction("D7", explicit_jurisdiction="FRANCE")
    assert decision.state == "UNKNOWN"
    assert decision.reason_code == "JURISDICTION_NOT_SUPPORTED"
    assert decision.allowed_jurisdictions == frozenset()


def test_conflicting_explicit_and_classification_signals_are_ambiguous():
    cls = classify_query("Q8", "What category applies in India under FSSAI?")
    decision = resolve_jurisdiction("D8", classification_result=cls, explicit_jurisdiction="INTERNATIONAL")
    assert decision.state == "AMBIGUOUS"
    assert decision.reason_code == "JURISDICTION_AMBIGUOUS"
    assert decision.requires_escalation is True
    assert decision.allowed_jurisdictions == frozenset()


def test_agreeing_explicit_and_classification_signals_are_known():
    cls = classify_query("Q9", "What category applies in India under FSSAI?")
    decision = resolve_jurisdiction("D9", classification_result=cls, explicit_jurisdiction="INDIA")
    assert decision.state == "KNOWN"
    assert decision.allowed_jurisdictions == frozenset({"INDIA"})


# ---------------------------------------------------------------------------
# Type discipline
# ---------------------------------------------------------------------------


def test_resolve_jurisdiction_rejects_empty_input_id():
    with pytest.raises(ValueError):
        resolve_jurisdiction("")


def test_resolve_jurisdiction_rejects_wrong_classification_result_type():
    with pytest.raises(TypeError):
        resolve_jurisdiction("D10", classification_result="not a ClassificationResult")


def test_resolve_jurisdiction_rejects_wrong_config_type():
    with pytest.raises(TypeError):
        resolve_jurisdiction("D11", config="not a config")


# ---------------------------------------------------------------------------
# JurisdictionDecision invariants
# ---------------------------------------------------------------------------


def test_decision_rejects_allowed_jurisdictions_when_not_known():
    with pytest.raises(ValueError):
        JurisdictionDecision(
            schema_version="1.0.0", decision_id="a" * 64, input_id="X", requested_jurisdiction=None,
            normalized_jurisdiction=None, state="UNKNOWN", reason_code="JURISDICTION_UNKNOWN",
            explanation="x", allowed_jurisdictions=frozenset({"INDIA"}),
            blocked_jurisdictions=frozenset({"INTERNATIONAL", "NOT_APPLICABLE", "OTHER_UNSPECIFIED"}),
            allowed_corpora=frozenset({"INDIA"}), blocked_corpora=frozenset({"INTERNATIONAL", "NOT_APPLICABLE", "OTHER_UNSPECIFIED"}),
            requires_evidence=False, requires_escalation=False, basis=["X"], config_signature="sig",
        )


def test_decision_rejects_empty_allowed_jurisdictions_when_known():
    with pytest.raises(ValueError):
        JurisdictionDecision(
            schema_version="1.0.0", decision_id="a" * 64, input_id="X", requested_jurisdiction="INDIA",
            normalized_jurisdiction="INDIA", state="KNOWN", reason_code="EXPLICIT_JURISDICTION_ACCEPTED",
            explanation="x", allowed_jurisdictions=frozenset(), blocked_jurisdictions=EVIDENCE_JURISDICTION_VALUES,
            allowed_corpora=frozenset(), blocked_corpora=EVIDENCE_JURISDICTION_VALUES,
            requires_evidence=False, requires_escalation=False, basis=["X"], config_signature="sig",
        )


def test_decision_rejects_reason_code_not_permitted_for_state():
    with pytest.raises(ValueError):
        JurisdictionDecision(
            schema_version="1.0.0", decision_id="a" * 64, input_id="X", requested_jurisdiction="INDIA",
            normalized_jurisdiction="INDIA", state="KNOWN", reason_code="JURISDICTION_UNKNOWN",
            explanation="x", allowed_jurisdictions=frozenset({"INDIA"}),
            blocked_jurisdictions=frozenset({"INTERNATIONAL", "NOT_APPLICABLE", "OTHER_UNSPECIFIED"}),
            allowed_corpora=frozenset({"INDIA"}), blocked_corpora=frozenset({"INTERNATIONAL", "NOT_APPLICABLE", "OTHER_UNSPECIFIED"}),
            requires_evidence=False, requires_escalation=False, basis=["X"], config_signature="sig",
        )


def test_decision_rejects_mismatched_allowed_corpora():
    decision = resolve_jurisdiction("D12", explicit_jurisdiction="INDIA")
    with pytest.raises(ValueError):
        dataclasses.replace(decision, allowed_corpora=frozenset({"INTERNATIONAL"}))


def test_needs_evidence_state_is_unconstructable():
    # No reason code is permitted for NEEDS_EVIDENCE (docs Section F) -
    # any attempt raises, proving the state is genuinely unreachable, not
    # merely undocumented.
    with pytest.raises(ValueError):
        JurisdictionDecision(
            schema_version="1.0.0", decision_id="a" * 64, input_id="X", requested_jurisdiction=None,
            normalized_jurisdiction=None, state="NEEDS_EVIDENCE", reason_code="EXPLICIT_JURISDICTION_ACCEPTED",
            explanation="x", allowed_jurisdictions=frozenset(), blocked_jurisdictions=EVIDENCE_JURISDICTION_VALUES,
            allowed_corpora=frozenset(), blocked_corpora=EVIDENCE_JURISDICTION_VALUES,
            requires_evidence=True, requires_escalation=False, basis=["X"], config_signature="sig",
        )


def test_decision_never_contains_a_legal_conclusion_field():
    field_names = {f.name for f in dataclasses.fields(JurisdictionDecision)}
    forbidden = {"legally_certain", "is_legally_valid", "legal_determination", "governing_law", "compliance_status"}
    assert field_names.isdisjoint(forbidden)


def test_config_signature_is_stable():
    assert JurisdictionFirewallConfig().signature == JurisdictionFirewallConfig().signature
