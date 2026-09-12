"""
Phase 12 tests: serialization round-trip safety - JurisdictionDecision
(docs/PHASE_12_JURISDICTION_FIREWALL.md Section Y).
"""

from __future__ import annotations

import json

import pytest
from _jurisdiction_fixtures import classify_query

from jurisdiction.firewall import resolve_jurisdiction
from jurisdiction.models import JurisdictionSchemaError
from jurisdiction.serialize import jurisdiction_decision_from_dict, jurisdiction_decision_to_dict, jurisdiction_decision_to_json


def test_known_decision_round_trips_through_dict():
    decision = resolve_jurisdiction("SER1", explicit_jurisdiction="INDIA")
    reloaded = jurisdiction_decision_from_dict(jurisdiction_decision_to_dict(decision))
    assert reloaded == decision


def test_unknown_decision_round_trips_through_dict():
    decision = resolve_jurisdiction("SER2")
    reloaded = jurisdiction_decision_from_dict(jurisdiction_decision_to_dict(decision))
    assert reloaded == decision


def test_ambiguous_decision_round_trips_through_dict():
    cls = classify_query("SER3", "What category applies in India under FSSAI?")
    decision = resolve_jurisdiction("SER3D", classification_result=cls, explicit_jurisdiction="INTERNATIONAL")
    assert decision.state == "AMBIGUOUS"
    reloaded = jurisdiction_decision_from_dict(jurisdiction_decision_to_dict(decision))
    assert reloaded == decision


def test_both_decision_round_trips_through_dict():
    decision = resolve_jurisdiction("SER4", explicit_jurisdiction="BOTH")
    reloaded = jurisdiction_decision_from_dict(jurisdiction_decision_to_dict(decision))
    assert reloaded == decision


def test_not_supported_decision_round_trips_through_dict():
    decision = resolve_jurisdiction("SER5", explicit_jurisdiction="FRANCE")
    reloaded = jurisdiction_decision_from_dict(jurisdiction_decision_to_dict(decision))
    assert reloaded == decision


def test_json_is_valid_and_round_trips():
    decision = resolve_jurisdiction("SER6", explicit_jurisdiction="INDIA")
    parsed = json.loads(jurisdiction_decision_to_json(decision))
    reloaded = jurisdiction_decision_from_dict(parsed["content"])
    assert reloaded == decision


def test_json_output_is_deterministic():
    decision = resolve_jurisdiction("SER7", explicit_jurisdiction="INDIA")
    assert jurisdiction_decision_to_json(decision) == jurisdiction_decision_to_json(decision)


def test_from_dict_rejects_non_dict():
    with pytest.raises(JurisdictionSchemaError):
        jurisdiction_decision_from_dict("not a dict")
    with pytest.raises(JurisdictionSchemaError):
        jurisdiction_decision_from_dict([1, 2, 3])


def test_from_dict_rejects_missing_field():
    decision = resolve_jurisdiction("SER8", explicit_jurisdiction="INDIA")
    data = jurisdiction_decision_to_dict(decision)
    del data["state"]
    with pytest.raises(JurisdictionSchemaError):
        jurisdiction_decision_from_dict(data)


def test_from_dict_rejects_wrong_type_field():
    decision = resolve_jurisdiction("SER9", explicit_jurisdiction="INDIA")
    data = jurisdiction_decision_to_dict(decision)
    data["requires_escalation"] = "not a bool"
    with pytest.raises(JurisdictionSchemaError):
        jurisdiction_decision_from_dict(data)


def test_from_dict_rejects_invalid_state_reason_combination():
    decision = resolve_jurisdiction("SER10", explicit_jurisdiction="INDIA")
    data = jurisdiction_decision_to_dict(decision)
    data["reason_code"] = "JURISDICTION_UNKNOWN"  # inconsistent with state=KNOWN
    with pytest.raises(JurisdictionSchemaError):
        jurisdiction_decision_from_dict(data)


def test_from_dict_rejects_invalid_enum_state():
    decision = resolve_jurisdiction("SER11", explicit_jurisdiction="INDIA")
    data = jurisdiction_decision_to_dict(decision)
    data["state"] = "MAYBE"
    with pytest.raises(JurisdictionSchemaError):
        jurisdiction_decision_from_dict(data)


def test_unicode_in_explanation_survives_json_round_trip():
    cls = classify_query("SER12", "आयுर்वेद query with no jurisdiction signal")
    decision = resolve_jurisdiction("SER12D", classification_result=cls)
    parsed = json.loads(jurisdiction_decision_to_json(decision))
    reloaded = jurisdiction_decision_from_dict(parsed["content"])
    assert reloaded.explanation == decision.explanation


def test_malicious_string_in_requested_jurisdiction_survives_serialization():
    decision = resolve_jurisdiction("SER13", explicit_jurisdiction="'; DROP TABLE x; --")
    reloaded = jurisdiction_decision_from_dict(jurisdiction_decision_to_dict(decision))
    assert reloaded.requested_jurisdiction == decision.requested_jurisdiction
