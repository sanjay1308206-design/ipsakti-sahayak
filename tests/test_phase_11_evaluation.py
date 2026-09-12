"""
Phase 11 tests: fully synthetic classification evaluation suite
(docs/PHASE_11_FORMULATION_CLASSIFICATION.md Sections U, V). Hand-authored
fixtures with explicitly defined expected outputs. This measures
IMPLEMENTATION correctness against synthetic, hand-authored cases only -
it is explicitly NOT a real-world classification accuracy benchmark and
reports no fabricated accuracy percentage
(docs/DEVELOPMENT_RULES.md Rule 7).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _classification_fixtures import make_input

from classification.classifier import classify
from classification.serialize import classification_result_from_dict, classification_result_to_dict

REPO_ROOT = Path(__file__).resolve().parent.parent

# Each fixture: (case_id, raw_query, formulation_description, evidence_state, expected_classification_state)
SYNTHETIC_CASES = [
    ("EVAL-KNOWN-1", "Tell me about Ministry of Ayush policy in India.", None, None, "KNOWN"),
    (
        "EVAL-KNOWN-2",
        "What category does my cosmetic fall under in India under FSSAI rules?",
        None,
        "SUFFICIENT_EVIDENCE",
        "KNOWN",
    ),
    ("EVAL-UNKNOWN-1", "", None, None, "UNKNOWN"),
    (
        "EVAL-UNKNOWN-2",
        "What category does my formulation fall under under FSSAI rules?",
        "This is an Ayurveda Aahara food product.",
        None,
        "UNKNOWN",
    ),
    (
        "EVAL-AMBIGUOUS-1",
        "What category applies in India under FSSAI?",
        "This is both an Ayurveda Aahara product and a Phytopharmaceutical.",
        None,
        "AMBIGUOUS",
    ),
    (
        "EVAL-AMBIGUOUS-2",
        "how can i protect this and what compliance requirement applies in India under FSSAI?",
        None,
        None,
        "AMBIGUOUS",
    ),
    (
        "EVAL-NEEDS-EVIDENCE-1",
        "What category does my Ayurveda Aahara product fall under in India under FSSAI rules?",
        None,
        None,
        "NEEDS_EVIDENCE",
    ),
    (
        "EVAL-NEEDS-EVIDENCE-2",
        "What category does my Ayurveda Aahara product fall under in India under FSSAI rules?",
        None,
        "INSUFFICIENT_EVIDENCE",
        "NEEDS_EVIDENCE",
    ),
]


@pytest.mark.parametrize("case_id,raw_query,formulation_description,evidence_state,expected_state", SYNTHETIC_CASES)
def test_synthetic_case_matches_expected_state(case_id, raw_query, formulation_description, evidence_state, expected_state):
    result = classify(make_input(case_id, raw_query=raw_query, formulation_description=formulation_description, evidence_state=evidence_state))
    assert result.classification_state == expected_state


def test_benchmark_property_deterministic_repeated_classification():
    case = SYNTHETIC_CASES[4]
    _, raw_query, formulation_description, evidence_state, _ = case
    results = [
        classify(make_input("REPEAT", raw_query=raw_query, formulation_description=formulation_description, evidence_state=evidence_state))
        for _ in range(5)
    ]
    assert all(r == results[0] for r in results)


def test_benchmark_property_rule_ordering_r1_beats_r2():
    # R1 (missing user_intent) must fire before R2 (missing jurisdiction)
    # even when BOTH are missing - rule order is part of the contract.
    result = classify(make_input("EVAL-ORDER-1", raw_query=""))
    assert result.reason_codes == ["MISSING_USER_INTENT"]


def test_benchmark_property_rule_conflict_behavior_r4_beats_r7():
    # A conflicting formulation signal must be reported (R4) even though
    # evidence is also missing (R7 would otherwise fire later) - R4 is
    # strictly earlier in the fixed order.
    result = classify(make_input(
        "EVAL-ORDER-2", raw_query="What category applies in India under FSSAI?",
        formulation_description="classical ayurvedic and proprietary ayurvedic",
    ))
    assert result.classification_state == "AMBIGUOUS"
    assert result.reason_codes == ["CONFLICTING_FORMULATION_SIGNALS"]


def test_benchmark_property_missing_fields_handled_explicitly_not_crashed():
    result = classify(make_input("EVAL-MISSING-1", raw_query="q"))  # formulation_description and evidence_state absent
    assert result.formulation_classification.regulatory_track == "UNDETERMINED"
    assert result.evidence_state == "NOT_YET_EVALUATED"


def test_benchmark_property_multilingual_input():
    result = classify(make_input("EVAL-ML-1", raw_query="आयुर्वेद FSSAI query in India"))
    assert result.classification_state in {"KNOWN", "UNKNOWN", "AMBIGUOUS", "NEEDS_EVIDENCE"}


def test_benchmark_property_mixed_script_input():
    result = classify(make_input("EVAL-ML-2", raw_query="Ayurveda आयுர்वेद மருந்து query"))
    assert result.classification_state in {"KNOWN", "UNKNOWN", "AMBIGUOUS", "NEEDS_EVIDENCE"}


def test_benchmark_property_adversarial_input_does_not_crash():
    result = classify(make_input("EVAL-ADV-1", raw_query="'; DROP TABLE x; -- <script>alert(1)</script>"))
    assert result.classification_state in {"KNOWN", "UNKNOWN", "AMBIGUOUS", "NEEDS_EVIDENCE"}


def test_benchmark_property_serialization_round_trip():
    for case_id, raw_query, formulation_description, evidence_state, _ in SYNTHETIC_CASES:
        result = classify(make_input(case_id, raw_query=raw_query, formulation_description=formulation_description, evidence_state=evidence_state))
        reloaded = classification_result_from_dict(classification_result_to_dict(result))
        assert reloaded == result


def test_benchmark_property_taxonomy_config_mismatch_handled_safely():
    # An evidence_state value that is NOT a member of the Phase 1
    # vocabulary at all must never crash and must never be silently
    # treated as sufficient.
    result = classify(make_input("EVAL-MISMATCH-1", raw_query="q", evidence_state="COMPLETELY_UNKNOWN_VALUE"))
    assert result.evidence_state == "NOT_YET_EVALUATED"


def test_benchmark_regression_against_phase_1_semantics():
    # Every one of Phase 1's own four worked examples (docs/PHASE_01_DOMAIN_TAXONOMY.md
    # Section K) must still reproduce exactly through the real Phase 11
    # classifier - already asserted in test_phase_11_classification.py;
    # re-asserted here as an explicit evaluation-suite regression check.
    known = classify(make_input("REGR-KNOWN", raw_query="Tell me about Ministry of Ayush policy in India."))
    needs_evidence = classify(make_input(
        "REGR-NE", raw_query="What regulatory category does my Ayurveda Aahara food product fall under in India under FSSAI rules?"
    ))
    unknown = classify(make_input(
        "REGR-UNK", raw_query="What regulatory category does my formulation fall under, under FSSAI rules?",
        formulation_description="This is an Ayurveda Aahara food product.",
    ))
    ambiguous = classify(make_input(
        "REGR-AMB", raw_query="What regulatory category applies in India under FSSAI rules?",
        formulation_description="This is both an Ayurveda Aahara product and a Phytopharmaceutical.",
    ))
    assert (known.classification_state, needs_evidence.classification_state, unknown.classification_state, ambiguous.classification_state) == (
        "KNOWN", "NEEDS_EVIDENCE", "UNKNOWN", "AMBIGUOUS",
    )


def test_benchmark_does_not_claim_real_world_classification_accuracy():
    doc_path = REPO_ROOT / "docs" / "PHASE_11_FORMULATION_CLASSIFICATION.md"
    text = doc_path.read_text(encoding="utf-8")
    assert "does not measure" in text.lower() or "not a real-world" in text.lower()
