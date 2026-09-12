"""
Phase 11 tests: core model invariants and end-to-end classification
(docs/PHASE_11_FORMULATION_CLASSIFICATION.md Sections F, G, H).
Reproduces Phase 1's own four worked examples
(docs/PHASE_01_DOMAIN_TAXONOMY.md Section K) end-to-end through the real
Phase 11 classifier, to prove Phase 11 actually implements what Phase 1
only specified.
"""

from __future__ import annotations

import dataclasses

import pytest
from _classification_fixtures import make_input

from classification.classifier import classify
from classification.models import (
    CLASSIFICATION_STATES,
    ClassificationConfig,
    ClassificationInput,
    ClassificationProvenance,
    ClassificationResult,
    DimensionResult,
    FIXED_DISCLAIMER,
    FormulationClassificationValues,
)


# ---------------------------------------------------------------------------
# Phase 1's own worked examples, reproduced end-to-end
# ---------------------------------------------------------------------------


def test_example_1_needs_evidence():
    result = classify(make_input(
        "EX1",
        raw_query="What regulatory category does my Ayurveda Aahara food product fall under in India under FSSAI rules?",
    ))
    assert result.classification_state == "NEEDS_EVIDENCE"
    assert result.reason_codes == ["EVIDENCE_NOT_AVAILABLE"]
    assert result.requires_evidence is True
    assert result.requires_escalation is False


def test_example_2_unknown_missing_jurisdiction():
    result = classify(make_input(
        "EX2",
        raw_query="What regulatory category does my formulation fall under, under FSSAI rules?",
        formulation_description="This is an Ayurveda Aahara food product.",
    ))
    assert result.classification_state == "UNKNOWN"
    assert result.reason_codes == ["MISSING_JURISDICTION"]


def test_example_3_ambiguous_conflicting_formulation_signals():
    result = classify(make_input(
        "EX3",
        raw_query="What regulatory category applies in India under FSSAI rules?",
        formulation_description="This is both an Ayurveda Aahara product and a Phytopharmaceutical.",
    ))
    assert result.classification_state == "AMBIGUOUS"
    assert result.reason_codes == ["CONFLICTING_FORMULATION_SIGNALS"]
    assert result.formulation_classification.regulatory_track == "CONFLICTING"
    assert result.requires_escalation is True


def test_example_4_known_general_information_with_disclaimer():
    result = classify(make_input("EX4", raw_query="Tell me about Ministry of Ayush policy in India."))
    assert result.classification_state == "KNOWN"
    assert result.reason_codes == []
    assert result.disclaimer == FIXED_DISCLAIMER
    assert result.requires_evidence is False
    assert result.requires_escalation is False


# ---------------------------------------------------------------------------
# ClassificationInput
# ---------------------------------------------------------------------------


def test_classification_input_rejects_non_string_raw_query():
    with pytest.raises(ValueError):
        ClassificationInput(input_id="X", raw_query=12345)


def test_classification_input_accepts_empty_raw_query():
    ClassificationInput(input_id="X", raw_query="")  # must not raise


def test_classification_input_rejects_empty_input_id():
    with pytest.raises(ValueError):
        ClassificationInput(input_id="", raw_query="q")


# ---------------------------------------------------------------------------
# classify() type discipline
# ---------------------------------------------------------------------------


def test_classify_rejects_non_classification_input():
    with pytest.raises(TypeError):
        classify("not a ClassificationInput")


def test_classify_rejects_wrong_config_type():
    with pytest.raises(TypeError):
        classify(make_input("X", raw_query="q"), config="not a config")


def test_classify_accepts_explicit_config():
    result = classify(make_input("X", raw_query="q"), config=ClassificationConfig())
    assert result.schema_version == "1.0.0"


# ---------------------------------------------------------------------------
# ClassificationResult invariants (SAFE-01..SAFE-06 from classification_contract.yaml)
# ---------------------------------------------------------------------------


def test_result_disclaimer_always_present_and_fixed():
    for state_query in ("", "What regulatory category in India under FSSAI?", "unrelated text"):
        result = classify(make_input("X", raw_query=state_query))
        assert result.disclaimer == FIXED_DISCLAIMER


def test_result_rejects_altered_disclaimer():
    result = classify(make_input("X", raw_query="q"))
    with pytest.raises(ValueError):
        dataclasses.replace(result, disclaimer="a different disclaimer")


def test_result_rejects_requires_evidence_mismatch():
    result = classify(make_input("EX1", raw_query="What regulatory category does my Ayurveda Aahara food product fall under in India under FSSAI rules?"))
    assert result.classification_state == "NEEDS_EVIDENCE"
    with pytest.raises(ValueError):
        dataclasses.replace(result, requires_evidence=False)


def test_result_rejects_requires_escalation_mismatch():
    result = classify(make_input(
        "EX3", raw_query="What category in India under FSSAI?",
        formulation_description="Ayurveda Aahara product and Phytopharmaceutical.",
    ))
    assert result.classification_state == "AMBIGUOUS"
    with pytest.raises(ValueError):
        dataclasses.replace(result, requires_escalation=False)


def test_result_rejects_reason_codes_empty_when_not_known():
    result = classify(make_input("X", raw_query=""))
    assert result.classification_state != "KNOWN"
    with pytest.raises(ValueError):
        dataclasses.replace(result, reason_codes=[])


def test_result_rejects_invalid_enum_value():
    result = classify(make_input("X", raw_query="q"))
    with pytest.raises(ValueError):
        dataclasses.replace(result, jurisdiction_input="NOT_A_REAL_VALUE")


def test_result_rejects_empty_basis():
    result = classify(make_input("X", raw_query="q"))
    with pytest.raises(ValueError):
        dataclasses.replace(result, basis=[])


def test_classification_states_closed_vocabulary():
    assert CLASSIFICATION_STATES == {"KNOWN", "UNKNOWN", "AMBIGUOUS", "NEEDS_EVIDENCE"}


def test_result_never_contains_a_legal_conclusion_field():
    field_names = {f.name for f in dataclasses.fields(ClassificationResult)}
    forbidden = {"legally_certain", "is_legally_valid", "legal_determination", "legal_conclusion"}
    assert field_names.isdisjoint(forbidden)


def test_result_never_contains_a_jurisdiction_decision_field():
    # Phase 11 supplies jurisdiction_input (an opaque routing value) - it
    # must never contain a field implying a firewall/routing DECISION
    # (that is Phase 12's exclusive job).
    field_names = {f.name for f in dataclasses.fields(ClassificationResult)}
    forbidden = {"jurisdiction_decision", "corpus_selected", "index_selected", "allowed_jurisdiction"}
    assert field_names.isdisjoint(forbidden)


def test_result_never_contains_a_confidence_score_field():
    field_names = {f.name for f in dataclasses.fields(ClassificationResult)}
    forbidden = {"confidence_score", "probability", "confidence"}
    assert field_names.isdisjoint(forbidden)


def test_dimension_result_state_never_needs_evidence():
    from classification.models import DIMENSION_STATES

    assert DIMENSION_STATES == {"KNOWN", "UNKNOWN", "AMBIGUOUS"}
    assert "NEEDS_EVIDENCE" not in DIMENSION_STATES


def test_provenance_versions_present():
    result = classify(make_input("X", raw_query="q"))
    assert result.provenance == ClassificationProvenance(
        taxonomy_version="1.0.0", decision_tree_version="1.0.0", contract_version="1.0.0"
    )
