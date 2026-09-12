"""
Phase 11 tests: serialization round-trip safety - ClassificationInput,
ClassificationResult (docs/PHASE_11_FORMULATION_CLASSIFICATION.md
Section S).
"""

from __future__ import annotations

import json

import pytest
from _classification_fixtures import make_input

from classification.classifier import classify
from classification.models import ClassificationSchemaError
from classification.serialize import (
    classification_input_from_dict,
    classification_input_to_dict,
    classification_input_to_json,
    classification_result_from_dict,
    classification_result_to_dict,
    classification_result_to_json,
)


# ---------------------------------------------------------------------------
# ClassificationInput round-trip
# ---------------------------------------------------------------------------


def test_classification_input_round_trips_through_dict():
    classification_input = make_input("SER1", raw_query="q", formulation_description="cosmetic", evidence_state="NOT_YET_EVALUATED")
    reloaded = classification_input_from_dict(classification_input_to_dict(classification_input))
    assert reloaded == classification_input


def test_classification_input_json_round_trips():
    classification_input = make_input("SER2", raw_query="q")
    parsed = json.loads(classification_input_to_json(classification_input))
    reloaded = classification_input_from_dict(parsed["content"])
    assert reloaded == classification_input


def test_classification_input_from_dict_rejects_non_dict():
    with pytest.raises(ClassificationSchemaError):
        classification_input_from_dict("not a dict")


def test_classification_input_from_dict_rejects_missing_field():
    with pytest.raises(ClassificationSchemaError):
        classification_input_from_dict({"input_id": "X"})


# ---------------------------------------------------------------------------
# ClassificationResult round-trip
# ---------------------------------------------------------------------------


def test_classification_result_round_trips_through_dict():
    result = classify(make_input("SER3", raw_query="What category in India under FSSAI?"))
    reloaded = classification_result_from_dict(classification_result_to_dict(result))
    assert reloaded == result


def test_classification_result_round_trips_for_every_terminal_state():
    cases = [
        make_input("SER4A", raw_query=""),  # UNKNOWN
        make_input("SER4B", raw_query="q in India under FSSAI", formulation_description="cosmetic and phytopharmaceutical"),  # AMBIGUOUS
        make_input("SER4C", raw_query="What category does my Ayurveda Aahara product fall under in India under FSSAI rules?"),  # NEEDS_EVIDENCE
        make_input("SER4D", raw_query="Tell me about Ministry of Ayush policy in India."),  # KNOWN
    ]
    for classification_input in cases:
        result = classify(classification_input)
        reloaded = classification_result_from_dict(classification_result_to_dict(result))
        assert reloaded == result


def test_classification_result_json_is_valid_json_and_round_trips():
    result = classify(make_input("SER5", raw_query="q"))
    parsed = json.loads(classification_result_to_json(result))
    reloaded = classification_result_from_dict(parsed["content"])
    assert reloaded == result


def test_classification_result_from_dict_rejects_non_dict():
    with pytest.raises(ClassificationSchemaError):
        classification_result_from_dict("not a dict")


def test_classification_result_from_dict_rejects_missing_field():
    result = classify(make_input("SER6", raw_query="q"))
    data = classification_result_to_dict(result)
    del data["classification_state"]
    with pytest.raises(ClassificationSchemaError):
        classification_result_from_dict(data)


def test_classification_result_from_dict_rejects_wrong_type_field():
    result = classify(make_input("SER7", raw_query="q"))
    data = classification_result_to_dict(result)
    data["reason_codes"] = "not a list"
    with pytest.raises(ClassificationSchemaError):
        classification_result_from_dict(data)


def test_classification_result_from_dict_rejects_invalid_status_combination():
    result = classify(make_input(
        "SER8", raw_query="What category does my Ayurveda Aahara product fall under in India under FSSAI rules?"
    ))
    data = classification_result_to_dict(result)
    assert data["classification_state"] == "NEEDS_EVIDENCE"
    data["requires_evidence"] = False  # now inconsistent
    with pytest.raises(ClassificationSchemaError):
        classification_result_from_dict(data)


def test_classification_result_from_dict_rejects_malformed_nested_formulation_classification():
    result = classify(make_input("SER9", raw_query="q"))
    data = classification_result_to_dict(result)
    data["formulation_classification"]["regulatory_track"] = "NOT_A_REAL_VALUE"
    with pytest.raises(ClassificationSchemaError):
        classification_result_from_dict(data)


def test_classification_result_from_dict_rejects_malformed_dimension_details():
    result = classify(make_input("SER10", raw_query="q"))
    data = classification_result_to_dict(result)
    data["dimension_details"]["user_intent"]["state"] = "NOT_A_REAL_STATE"
    with pytest.raises(ClassificationSchemaError):
        classification_result_from_dict(data)


def test_unicode_in_result_survives_json_round_trip():
    result = classify(make_input("SER11", raw_query="आयुर्वेद மருந்து query in India under FSSAI"))
    parsed = json.loads(classification_result_to_json(result))
    reloaded = classification_result_from_dict(parsed["content"])
    assert reloaded == result


def test_large_string_input_survives_serialization():
    long_text = "classification query text " * 3000
    result = classify(make_input("SER12", raw_query=long_text))
    reloaded = classification_result_from_dict(classification_result_to_dict(result))
    assert reloaded == result


def test_empty_values_survive_serialization():
    result = classify(make_input("SER13", raw_query="", formulation_description=None, evidence_state=None))
    reloaded = classification_result_from_dict(classification_result_to_dict(result))
    assert reloaded == result
