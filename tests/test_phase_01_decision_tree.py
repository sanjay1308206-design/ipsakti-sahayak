"""
Phase 1 tests: docs/PHASE_01_REGULATORY_DECISION_TREE.md,
config/regulatory_decision_tree.yaml, and the deterministic reference
evaluator (tests/_decision_tree_reference_impl.py) that proves the
contract's rule set actually behaves as documented.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from _decision_tree_reference_impl import (
    ClassificationInput,
    evaluate,
)
from _taxonomy_schema import TaxonomyValidationError, validate_decision_tree

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "PHASE_01_REGULATORY_DECISION_TREE.md"
TREE_YAML_PATH = REPO_ROOT / "config" / "regulatory_decision_tree.yaml"
TAXONOMY_YAML_PATH = REPO_ROOT / "config" / "domain_taxonomy.yaml"

VALID_TERMINAL_STATES = {"KNOWN", "UNKNOWN", "AMBIGUOUS", "NEEDS_EVIDENCE"}


@pytest.fixture(scope="module")
def doc_text() -> str:
    assert DOC_PATH.is_file()
    return DOC_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def tree_raw_text() -> str:
    assert TREE_YAML_PATH.is_file()
    return TREE_YAML_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def tree_data(tree_raw_text: str) -> dict:
    return yaml.safe_load(tree_raw_text)


@pytest.fixture(scope="module")
def taxonomy_data() -> dict:
    return yaml.safe_load(TAXONOMY_YAML_PATH.read_text(encoding="utf-8"))


@pytest.fixture()
def valid_tree_copy(tree_data: dict) -> dict:
    return copy.deepcopy(tree_data)


def _base_inputs(**overrides) -> ClassificationInput:
    defaults = dict(
        user_intent="GENERAL_INFORMATION_REQUEST",
        formulation_regulatory_track="UNDETERMINED",
        jurisdiction="INDIA",
        regulatory_question_type="AYUSH_POLICY",
        evidence_state="NOT_YET_EVALUATED",
    )
    defaults.update(overrides)
    return ClassificationInput(**defaults)


# ---------------------------------------------------------------------------
# Document structure
# ---------------------------------------------------------------------------


def test_doc_exists_and_nonempty():
    assert DOC_PATH.stat().st_size > 0


@pytest.mark.parametrize(
    "section",
    [
        "1. Purpose",
        "2. Design Requirements",
        "3. Input Fields",
        "4. Branches (Conceptual)",
        "5. Ordered Deterministic Rules",
        "6. Escalation / Uncertainty Derivation",
        "7. Safety Boundary",
        "8. Terminal States",
        "9. Non-Goals",
    ],
)
def test_doc_has_required_section(doc_text: str, section: str):
    assert section in doc_text


def test_doc_declares_all_four_terminal_states(doc_text: str):
    for state in VALID_TERMINAL_STATES:
        assert state in doc_text


def test_doc_declares_no_llm_or_external_calls(doc_text: str):
    lowered = doc_text.lower()
    assert "no llm call" in lowered
    assert "no external api call" in lowered


# ---------------------------------------------------------------------------
# YAML schema validation
# ---------------------------------------------------------------------------


def test_tree_yaml_parses_correctly(tree_raw_text: str):
    data = yaml.safe_load(tree_raw_text)
    assert isinstance(data, dict)


def test_tree_passes_schema_validation(tree_data: dict):
    validate_decision_tree(tree_data)  # should not raise


def test_tree_terminal_states_are_exactly_the_four_required(tree_data: dict):
    assert set(tree_data["terminal_states"]) == VALID_TERMINAL_STATES


def test_tree_rule_order_matches_reference_implementation(tree_data: dict):
    rule_ids_in_yaml = [s["rule_id"] for s in tree_data["stages"]]
    assert rule_ids_in_yaml == ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"]


def test_evidence_requiring_intents_consistent_with_taxonomy(tree_data: dict, taxonomy_data: dict):
    tree_intents = set(tree_data["evidence_requiring_intents"])
    taxonomy_intents = {
        c["name"]
        for c in taxonomy_data["user_intent_categories"]["categories"]
        if c.get("evidence_requiring") is True
    }
    assert tree_intents == taxonomy_intents


# ---------------------------------------------------------------------------
# Reference-implementation behavioral tests (one per rule, positive cases)
# ---------------------------------------------------------------------------


def test_r1_missing_user_intent():
    result = evaluate(_base_inputs(user_intent="UNDETERMINED"))
    assert result.classification_state == "UNKNOWN"
    assert result.rule_id == "R1"
    assert "MISSING_USER_INTENT" in result.reason_codes


def test_r2_missing_jurisdiction():
    result = evaluate(_base_inputs(jurisdiction="UNSPECIFIED"))
    assert result.classification_state == "UNKNOWN"
    assert result.rule_id == "R2"


def test_r3_missing_formulation_info_for_evidence_requiring_intent():
    result = evaluate(
        _base_inputs(
            user_intent="DETERMINE_REGULATORY_CLASSIFICATION",
            formulation_regulatory_track="UNDETERMINED",
            regulatory_question_type="AYURVEDA_AAHARA_FOOD_LAW",
        )
    )
    assert result.classification_state == "UNKNOWN"
    assert result.rule_id == "R3"


def test_r4_conflicting_formulation_signals():
    result = evaluate(
        _base_inputs(
            user_intent="DETERMINE_REGULATORY_CLASSIFICATION",
            formulation_regulatory_track="CONFLICTING",
            regulatory_question_type="AYURVEDA_AAHARA_FOOD_LAW",
            evidence_state="SUFFICIENT_EVIDENCE",
        )
    )
    assert result.classification_state == "AMBIGUOUS"
    assert result.rule_id == "R4"
    assert result.requires_escalation is True


def test_r5_ambiguous_user_intent():
    result = evaluate(_base_inputs(user_intent="AMBIGUOUS_INTENT"))
    assert result.classification_state == "AMBIGUOUS"
    assert result.rule_id == "R5"
    assert result.requires_escalation is True


def test_r6_unrecognized_regulatory_question_type():
    result = evaluate(_base_inputs(regulatory_question_type="UNDETERMINED"))
    assert result.classification_state == "UNKNOWN"
    assert result.rule_id == "R6"


def test_r6_rejects_value_outside_enum_entirely():
    result = evaluate(_base_inputs(regulatory_question_type="MADE_UP_CATEGORY"))
    assert result.classification_state == "UNKNOWN"
    assert result.rule_id == "R6"


def test_r7_evidence_not_available():
    result = evaluate(
        _base_inputs(
            user_intent="DETERMINE_REGULATORY_CLASSIFICATION",
            formulation_regulatory_track="AYURVEDA_AAHARA_FOOD",
            regulatory_question_type="AYURVEDA_AAHARA_FOOD_LAW",
            evidence_state="NOT_YET_EVALUATED",
        )
    )
    assert result.classification_state == "NEEDS_EVIDENCE"
    assert result.rule_id == "R7"
    assert result.requires_evidence is True


def test_r7_fires_for_every_non_sufficient_evidence_state():
    for state in ("INSUFFICIENT_EVIDENCE", "NO_EVIDENCE_AVAILABLE", "NOT_YET_EVALUATED"):
        result = evaluate(
            _base_inputs(
                user_intent="LOOKUP_AUTHORITATIVE_SOURCE",
                formulation_regulatory_track="COSMETIC",
                regulatory_question_type="INDIA_LEGISLATIVE",
                evidence_state=state,
            )
        )
        assert result.classification_state == "NEEDS_EVIDENCE", f"failed for evidence_state={state}"


def test_r8_default_known_when_all_inputs_clean():
    result = evaluate(
        _base_inputs(
            user_intent="GENERAL_INFORMATION_REQUEST",
            regulatory_question_type="AYUSH_POLICY",
            jurisdiction="INDIA",
        )
    )
    assert result.classification_state == "KNOWN"
    assert result.rule_id == "R8"
    assert result.reason_codes == []


def test_r8_known_still_requires_evidence_false_and_escalation_false():
    result = evaluate(_base_inputs())
    assert result.requires_evidence is False
    assert result.requires_escalation is False


# ---------------------------------------------------------------------------
# Critical negative / safety tests
# ---------------------------------------------------------------------------


def test_known_result_still_carries_disclaimer():
    # Negative test #11: an uncertain/engineering-only result must never be
    # presented as legally certain - enforced here by requiring the fixed
    # disclaimer on every result, including KNOWN.
    result = evaluate(_base_inputs())
    assert result.classification_state == "KNOWN"
    assert result.disclaimer
    assert "not legal advice" in result.disclaimer.lower()
    assert "not an authoritative legal determination" in result.disclaimer.lower() or (
        "not" in result.disclaimer.lower() and "legal determination" in result.disclaimer.lower()
    )


def test_every_result_state_is_one_of_the_four_terminal_states():
    scenarios = [
        _base_inputs(user_intent="UNDETERMINED"),
        _base_inputs(jurisdiction="UNSPECIFIED"),
        _base_inputs(
            user_intent="DETERMINE_IP_PROTECTION_PATHWAY",
            formulation_regulatory_track="UNDETERMINED",
        ),
        _base_inputs(formulation_regulatory_track="CONFLICTING"),
        _base_inputs(user_intent="AMBIGUOUS_INTENT"),
        _base_inputs(regulatory_question_type="UNDETERMINED"),
        _base_inputs(user_intent="CHECK_COMPLIANCE_REQUIREMENT", formulation_regulatory_track="COSMETIC"),
        _base_inputs(),
    ]
    for inp in scenarios:
        result = evaluate(inp)
        assert result.classification_state in VALID_TERMINAL_STATES


def test_conservative_under_uncertainty_no_input_never_reaches_known():
    # Fully empty/undetermined input must never resolve to KNOWN.
    result = evaluate(
        ClassificationInput(
            user_intent="UNDETERMINED",
            formulation_regulatory_track="UNDETERMINED",
            jurisdiction="UNSPECIFIED",
            regulatory_question_type="UNDETERMINED",
            evidence_state="NOT_YET_EVALUATED",
        )
    )
    assert result.classification_state != "KNOWN"


def test_rule_priority_order_is_respected_missing_intent_beats_missing_jurisdiction():
    # Both user_intent and jurisdiction are missing - R1 must win because it
    # is evaluated first (proves deterministic ordering, not just correctness
    # of each rule in isolation).
    result = evaluate(_base_inputs(user_intent="UNDETERMINED", jurisdiction="UNSPECIFIED"))
    assert result.rule_id == "R1"


# ---------------------------------------------------------------------------
# Negative tests: malformed contract / invalid transitions / duplicates
# ---------------------------------------------------------------------------


def test_malformed_tree_root_is_rejected():
    with pytest.raises(TaxonomyValidationError):
        validate_decision_tree(["not", "a", "mapping"])


def test_tree_missing_top_level_key_is_rejected(valid_tree_copy: dict):
    del valid_tree_copy["stages"]
    with pytest.raises(TaxonomyValidationError):
        validate_decision_tree(valid_tree_copy)


def test_tree_duplicate_rule_id_is_rejected(valid_tree_copy: dict):
    valid_tree_copy["stages"][1]["rule_id"] = valid_tree_copy["stages"][0]["rule_id"]
    with pytest.raises(TaxonomyValidationError):
        validate_decision_tree(valid_tree_copy)


def test_tree_out_of_order_stage_numbers_rejected(valid_tree_copy: dict):
    valid_tree_copy["stages"][2]["stage"] = 99  # invalid transition/ordering
    with pytest.raises(TaxonomyValidationError):
        validate_decision_tree(valid_tree_copy)


def test_tree_invalid_result_state_is_rejected(valid_tree_copy: dict):
    # Illegal/unsupported classification state (negative test #10).
    valid_tree_copy["stages"][0]["result_state"] = "PROBABLY_FINE"
    with pytest.raises(TaxonomyValidationError):
        validate_decision_tree(valid_tree_copy)


def test_tree_missing_catchall_stage_is_rejected(valid_tree_copy: dict):
    valid_tree_copy["stages"][-1]["condition"] = "user_intent == 'SOMETHING'"
    with pytest.raises(TaxonomyValidationError):
        validate_decision_tree(valid_tree_copy)


def test_tree_catchall_not_last_is_rejected(valid_tree_copy: dict):
    valid_tree_copy["stages"][3]["condition"] = "otherwise"
    with pytest.raises(TaxonomyValidationError):
        validate_decision_tree(valid_tree_copy)


def test_tree_wrong_terminal_state_set_is_rejected(valid_tree_copy: dict):
    valid_tree_copy["terminal_states"] = ["KNOWN", "UNKNOWN"]  # incomplete set
    with pytest.raises(TaxonomyValidationError):
        validate_decision_tree(valid_tree_copy)


def test_tree_missing_stage_field_is_rejected(valid_tree_copy: dict):
    del valid_tree_copy["stages"][0]["reason_code"]  # reason_code is optional...
    # ...so instead remove a genuinely required field:
    del valid_tree_copy["stages"][0]["condition"]
    with pytest.raises(TaxonomyValidationError):
        validate_decision_tree(valid_tree_copy)
