"""
Phase 11 tests: ambiguity handling and the UNKNOWN vs NEEDS_EVIDENCE
distinction (docs/PHASE_11_FORMULATION_CLASSIFICATION.md Sections L, M).
The classifier must never force a value when input supports multiple
plausible categories, and must never collapse UNKNOWN into NEEDS_EVIDENCE
or vice versa.
"""

from __future__ import annotations

from _classification_fixtures import make_input

from classification.classifier import classify


# ---------------------------------------------------------------------------
# Ambiguity is never arbitrarily resolved
# ---------------------------------------------------------------------------


def test_conflicting_formulation_signals_never_arbitrarily_pick_one():
    result = classify(make_input(
        "AMB1",
        raw_query="What category in India under FSSAI?",
        formulation_description="This looks like a classical ayurvedic drug but also a proprietary ayurvedic drug.",
    ))
    assert result.classification_state == "AMBIGUOUS"
    assert result.formulation_classification.regulatory_track == "CONFLICTING"
    # Neither candidate is silently chosen.
    assert result.formulation_classification.regulatory_track not in ("CLASSICAL_AYURVEDIC_DRUG", "PROPRIETARY_AYURVEDIC_DRUG")


def test_ambiguous_intent_never_arbitrarily_pick_one():
    text = "how can i protect this and what compliance requirement applies to it in India under FSSAI?"
    result = classify(make_input("AMB2", raw_query=text))
    assert result.classification_state == "AMBIGUOUS"
    assert result.user_intent == "AMBIGUOUS_INTENT"
    assert result.requires_escalation is True


def test_ambiguity_reason_is_recorded_not_silent():
    result = classify(make_input(
        "AMB3", raw_query="q in India under FSSAI",
        formulation_description="cosmetic and phytopharmaceutical",
    ))
    detail = result.dimension_details["regulatory_track"]
    assert "cosmetic" in detail.reason.lower() or "COSMETIC" in detail.matched_rule_ids or len(detail.matched_rule_ids) > 1
    assert detail.matched_rule_ids  # the specific conflicting rule IDs are recorded


def test_dimension_without_own_conflicting_state_falls_back_to_undetermined_not_a_guess():
    # ip_protection_category has no CONFLICTING member in the taxonomy -
    # multiple matches must resolve to its own UNDETERMINED, never an
    # arbitrary pick of PATENT or TRADEMARK.
    result = classify(make_input(
        "AMB4", raw_query="I want a patent and also a trademark for this in India under FSSAI",
    ))
    assert result.formulation_classification.ip_protection_category == "UNDETERMINED"
    detail = result.dimension_details["ip_protection_category"]
    assert detail.state == "UNKNOWN"
    assert len(detail.matched_rule_ids) == 2


# ---------------------------------------------------------------------------
# UNKNOWN vs NEEDS_EVIDENCE distinction is never collapsed
# ---------------------------------------------------------------------------


def test_missing_input_is_unknown_not_needs_evidence():
    # No jurisdiction supplied at all -> the classifier does not know
    # enough to even attempt the evidence question yet.
    result = classify(make_input(
        "UNK1", raw_query="What category applies under FSSAI?",
        formulation_description="Ayurveda Aahara product.",
    ))
    assert result.classification_state == "UNKNOWN"
    assert result.classification_state != "NEEDS_EVIDENCE"
    assert result.requires_evidence is False


def test_complete_unambiguous_input_needing_evidence_is_needs_evidence_not_unknown():
    # Every input dimension is resolved and unambiguous; only evidence is
    # outstanding.
    result = classify(make_input(
        "NE1", raw_query="What category does my Ayurveda Aahara product fall under in India under FSSAI rules?",
    ))
    assert result.classification_state == "NEEDS_EVIDENCE"
    assert result.classification_state != "UNKNOWN"
    assert result.requires_evidence is True


def test_needs_evidence_becomes_known_once_sufficient_evidence_is_supplied():
    base_query = "What category does my Ayurveda Aahara product fall under in India under FSSAI rules?"
    without_evidence = classify(make_input("NE2A", raw_query=base_query))
    with_evidence = classify(make_input("NE2B", raw_query=base_query, evidence_state="SUFFICIENT_EVIDENCE"))
    assert without_evidence.classification_state == "NEEDS_EVIDENCE"
    assert with_evidence.classification_state == "KNOWN"


def test_insufficient_evidence_still_needs_evidence_not_known():
    result = classify(make_input(
        "NE3", raw_query="What category does my Ayurveda Aahara product fall under in India under FSSAI rules?",
        evidence_state="INSUFFICIENT_EVIDENCE",
    ))
    assert result.classification_state == "NEEDS_EVIDENCE"


def test_no_evidence_available_still_needs_evidence_not_known():
    result = classify(make_input(
        "NE4", raw_query="What category does my Ayurveda Aahara product fall under in India under FSSAI rules?",
        evidence_state="NO_EVIDENCE_AVAILABLE",
    ))
    assert result.classification_state == "NEEDS_EVIDENCE"


def test_non_evidence_requiring_intent_never_needs_evidence():
    # GENERAL_INFORMATION_REQUEST does not require evidence at all - even
    # with NOT_YET_EVALUATED, it must reach KNOWN, never NEEDS_EVIDENCE.
    result = classify(make_input("NE5", raw_query="Tell me about Ministry of Ayush policy in India."))
    assert result.classification_state == "KNOWN"
