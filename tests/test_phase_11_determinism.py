"""
Phase 11 tests: deterministic classification
(docs/PHASE_11_FORMULATION_CLASSIFICATION.md Section T). Given identical
input and identical configuration, classification result MUST be
identical.
"""

from __future__ import annotations

from _classification_fixtures import make_input

from classification.classifier import classify
from classification.serialize import classification_result_to_json


def test_repeated_classification_is_identical():
    # ClassificationResult holds list/dict fields (reason_codes, basis,
    # dimension_details) and so is deliberately not hashable - equality,
    # not set-membership, is the correct determinism check here.
    classification_input = make_input(
        "DET1", raw_query="What category does my Ayurveda Aahara product fall under in India under FSSAI rules?"
    )
    results = [classify(classification_input) for _ in range(10)]
    assert all(result == results[0] for result in results)


def test_repeated_classification_json_is_byte_identical():
    classification_input = make_input("DET2", raw_query="q in India under FSSAI")
    jsons = {classification_result_to_json(classify(classification_input)) for _ in range(10)}
    assert len(jsons) == 1


def test_different_input_ids_produce_different_results_only_in_input_id():
    text = "q in India under FSSAI"
    r1 = classify(make_input("DET3A", raw_query=text))
    r2 = classify(make_input("DET3B", raw_query=text))
    assert r1.input_id != r2.input_id
    assert r1.classification_state == r2.classification_state
    assert r1.formulation_classification == r2.formulation_classification


def test_classification_does_not_depend_on_dict_or_set_iteration_order():
    # Constructing the same logical input via different keyword-argument
    # orders must never change the result.
    from classification.models import ClassificationInput

    a = ClassificationInput(input_id="X", raw_query="q", formulation_description="cosmetic", evidence_state=None)
    b = ClassificationInput(evidence_state=None, formulation_description="cosmetic", raw_query="q", input_id="X")
    assert classify(a) == classify(b)


def test_ambiguous_dimension_matched_rule_ids_are_deterministically_ordered():
    result = classify(make_input(
        "DET4", raw_query="q in India under FSSAI",
        formulation_description="classical ayurvedic and proprietary ayurvedic",
    ))
    runs = [
        classify(make_input("DET4", raw_query="q in India under FSSAI", formulation_description="classical ayurvedic and proprietary ayurvedic"))
        for _ in range(5)
    ]
    assert len({tuple(r.dimension_details["regulatory_track"].matched_rule_ids) for r in runs}) == 1
