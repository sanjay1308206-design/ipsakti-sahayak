"""
Phase 16 tests: Phase 11 deterministic classification evaluation
(docs/PHASE_16_EVALUATION_AND_RED_TEAM.md Section L). Calls the REAL
`classification.classifier.classify` - never a re-derived rule engine.
"""

from __future__ import annotations

from _evaluation_fixtures import make_case

from classification.classifier import classify
from classification.models import ClassificationInput
from evaluation.benchmark import score_exact_match_cases

# (case_id, raw_query, formulation_description, expected_classification_state)
CLASSIFICATION_CASES = [
    ("CLS-KNOWN", "Tell me about Ministry of Ayush policy in India.", None, "KNOWN"),
    ("CLS-UNKNOWN", "", None, "UNKNOWN"),
    ("CLS-AMBIGUOUS", "how can i protect this and what compliance requirement applies in India", None, "AMBIGUOUS"),
    (
        "CLS-NEEDS-EVIDENCE",
        "what is the compliance requirement for my new ayurvedic drug in India and what license from CDSCO or state authority do I need",
        None,
        "NEEDS_EVIDENCE",
    ),
    ("CLS-CONFLICTING-TRACK", "general information in India", "This is a classical ayurvedic drug but also a cosmetic product", "AMBIGUOUS"),
]


def _run_case(case_id, raw_query, formulation_description, expected_state):
    result = classify(ClassificationInput(input_id=case_id, raw_query=raw_query, formulation_description=formulation_description))
    case = make_case(
        case_id, "CLASSIFICATION", "STRUCTURAL_EXPECTATION", raw_query or "(empty query)",
        f"classification_state == {expected_state}", expected_classification_state=expected_state,
    )
    return case, result


def test_classification_state_exact_accuracy_over_known_unknown_ambiguous_needs_evidence_conflicting():
    entries = []
    for case_id, raw_query, formulation_description, expected_state in CLASSIFICATION_CASES:
        case, result = _run_case(case_id, raw_query, formulation_description, expected_state)
        entries.append((case, result.classification_state == expected_state))

    report = score_exact_match_cases("CLASSIFICATION", "CLASSIFICATION_STATE_EXACT_ACCURACY", entries)
    assert report.results[0].applicable is True
    # Every case above is drawn from the real decision tree's own documented rules - all must match.
    assert report.failed_case_ids == [], f"unexpected classification mismatches: {report.failed_case_ids}"
    assert report.results[0].value == 1.0


def test_classification_is_deterministically_repeatable():
    case_id, raw_query, formulation_description, expected_state = CLASSIFICATION_CASES[2]
    results = [
        classify(ClassificationInput(input_id=case_id, raw_query=raw_query, formulation_description=formulation_description))
        for _ in range(10)
    ]
    assert all(r == results[0] for r in results)


def test_regulatory_track_conflicting_case_is_a_distinct_signal_from_ambiguous_intent():
    case, result = _run_case(*CLASSIFICATION_CASES[4])
    assert result.formulation_classification.regulatory_track == "CONFLICTING"
    assert "CONFLICTING_FORMULATION_SIGNALS" in result.reason_codes


def test_no_probabilistic_calibration_field_exists_on_classification_result():
    _, result = _run_case(*CLASSIFICATION_CASES[0])
    assert not hasattr(result, "confidence")
    assert not hasattr(result, "probability")
