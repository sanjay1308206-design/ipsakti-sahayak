"""
Phase 13 tests: serialization round-trip safety - SafetyDecision
(docs/PHASE_13_CONFIDENCE_SAFETY_ABSTENTION.md Section Z).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from _safety_fixtures import make_grounded_response, make_known_classification, make_known_jurisdiction

from safety.evaluator import evaluate_safety
from safety.models import SafetySchemaError
from safety.serialize import safety_decision_from_dict, safety_decision_to_dict, safety_decision_to_json

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def test_safe_decision_round_trips_through_dict(authority_matrix):
    cls = make_known_classification()
    jur = make_known_jurisdiction()
    pack, gr = make_grounded_response(authority_matrix, [("SER1-D1", "Content.")], "SER1-q")
    decision = evaluate_safety("SER1", classification_result=cls, jurisdiction_decision=jur, grounded_response=gr)
    reloaded = safety_decision_from_dict(safety_decision_to_dict(decision))
    assert reloaded == decision


def test_abstain_decision_round_trips_through_dict():
    decision = evaluate_safety("SER2")
    reloaded = safety_decision_from_dict(safety_decision_to_dict(decision))
    assert reloaded == decision


def test_escalate_decision_round_trips_through_dict():
    from _safety_fixtures import make_classification

    cls = make_classification("SER3", raw_query="how can i protect this and what compliance requirement applies in India")
    decision = evaluate_safety("SER3D", classification_result=cls)
    assert decision.safety_status == "ESCALATE"
    reloaded = safety_decision_from_dict(safety_decision_to_dict(decision))
    assert reloaded == decision


def test_json_is_valid_and_round_trips(authority_matrix):
    cls = make_known_classification()
    jur = make_known_jurisdiction()
    pack, gr = make_grounded_response(authority_matrix, [("SER4-D1", "Content.")], "SER4-q")
    decision = evaluate_safety("SER4", classification_result=cls, jurisdiction_decision=jur, grounded_response=gr)
    parsed = json.loads(safety_decision_to_json(decision))
    reloaded = safety_decision_from_dict(parsed["content"])
    assert reloaded == decision


def test_from_dict_rejects_non_dict():
    with pytest.raises(SafetySchemaError):
        safety_decision_from_dict("not a dict")
    with pytest.raises(SafetySchemaError):
        safety_decision_from_dict([1, 2, 3])


def test_from_dict_rejects_missing_field():
    decision = evaluate_safety("SER5")
    data = safety_decision_to_dict(decision)
    del data["safety_status"]
    with pytest.raises(SafetySchemaError):
        safety_decision_from_dict(data)


def test_from_dict_rejects_wrong_type_field():
    decision = evaluate_safety("SER6")
    data = safety_decision_to_dict(decision)
    data["abstained"] = "not a bool"
    with pytest.raises(SafetySchemaError):
        safety_decision_from_dict(data)


def test_from_dict_rejects_hard_gate_results_as_string_not_char_split():
    decision = evaluate_safety("SER7")
    data = safety_decision_to_dict(decision)
    data["hard_gate_results"] = "G1"  # would silently become ['G','1'] if mishandled
    with pytest.raises(SafetySchemaError):
        safety_decision_from_dict(data)


def test_from_dict_rejects_invalid_enum_status():
    decision = evaluate_safety("SER8")
    data = safety_decision_to_dict(decision)
    data["safety_status"] = "MAYBE"
    with pytest.raises(SafetySchemaError):
        safety_decision_from_dict(data)


def test_from_dict_rejects_engineering_band_mismatch(authority_matrix):
    cls = make_known_classification()
    jur = make_known_jurisdiction()
    pack, gr = make_grounded_response(authority_matrix, [("SER9-D1", "Content.")], "SER9-q")
    decision = evaluate_safety("SER9", classification_result=cls, jurisdiction_decision=jur, grounded_response=gr)
    data = safety_decision_to_dict(decision)
    data["safety_status"] = "ABSTAIN"  # now inconsistent with a real engineering_signal_band
    data["reason_code"] = "MISSING_GROUNDED_RESPONSE"
    data["abstained"] = True
    data["escalation_required"] = False
    with pytest.raises(SafetySchemaError):
        safety_decision_from_dict(data)


def test_unicode_in_explanation_survives_json_round_trip():
    from _safety_fixtures import make_classification

    cls = make_classification("SER10", raw_query="आयுர்वेद query with no jurisdiction signal")
    decision = evaluate_safety("SER10D", classification_result=cls)
    parsed = json.loads(safety_decision_to_json(decision))
    reloaded = safety_decision_from_dict(parsed["content"])
    assert reloaded.explanation == decision.explanation


def test_nested_object_corruption_in_input_status_summary_is_rejected_when_wrong_type():
    decision = evaluate_safety("SER11")
    data = safety_decision_to_dict(decision)
    data["input_status_summary"] = "not a dict"
    with pytest.raises(SafetySchemaError):
        safety_decision_from_dict(data)
