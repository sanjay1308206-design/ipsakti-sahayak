"""
Phase 14 tests: deterministic JSON serialization round-trip safety for
MultilingualInputContext and MultilingualDeliveryResult
(docs/PHASE_14_MULTILINGUAL_DELIVERY.md Section AC), and rejection of
malformed serialized data.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from _multilingual_fixtures import make_context, make_safe_grounded_response

from multilingual.delivery import deliver_response
from multilingual.models import MultilingualSchemaError
from multilingual.providers import FakeTranslationProvider
from multilingual.serialize import (
    delivery_result_from_dict,
    delivery_result_to_dict,
    delivery_result_to_json,
    input_context_from_dict,
    input_context_to_dict,
    input_context_to_json,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# MultilingualInputContext round-trip
# ---------------------------------------------------------------------------


def test_input_context_round_trips_through_dict():
    ctx = make_context("SERC1", "आयुर्वेद औषधि पंजीकरण", requested_language="hi")
    reloaded = input_context_from_dict(input_context_to_dict(ctx))
    assert reloaded == ctx


def test_input_context_round_trips_through_json():
    ctx = make_context("SERC2", "What license do I need?", requested_language="en")
    parsed = json.loads(input_context_to_json(ctx))
    reloaded = input_context_from_dict(parsed["content"])
    assert reloaded == ctx


def test_input_context_round_trips_with_none_requested_language():
    ctx = make_context("SERC3", "text with no language request")
    reloaded = input_context_from_dict(input_context_to_dict(ctx))
    assert reloaded == ctx
    assert reloaded.requested_language is None


def test_input_context_from_dict_rejects_non_dict():
    with pytest.raises(MultilingualSchemaError):
        input_context_from_dict("not a dict")
    with pytest.raises(MultilingualSchemaError):
        input_context_from_dict([1, 2, 3])


def test_input_context_from_dict_rejects_missing_field():
    ctx = make_context("SERC4", "text")
    data = input_context_to_dict(ctx)
    del data["detected_script"]
    with pytest.raises(MultilingualSchemaError):
        input_context_from_dict(data)


def test_input_context_from_dict_rejects_invalid_detected_script():
    ctx = make_context("SERC5", "text")
    data = input_context_to_dict(ctx)
    data["detected_script"] = "KLINGON"
    with pytest.raises(MultilingualSchemaError):
        input_context_from_dict(data)


# ---------------------------------------------------------------------------
# MultilingualDeliveryResult round-trip
# ---------------------------------------------------------------------------


def test_delivered_result_round_trips_through_dict(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("SERD1-D1", "Content.")], "SERD1-q")
    ctx = make_context("SERD1", "query", requested_language="hi")
    provider = FakeTranslationProvider(response_text="translated")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety, translation_provider=provider)
    reloaded = delivery_result_from_dict(delivery_result_to_dict(result))
    assert reloaded == result


def test_upstream_blocked_result_round_trips_through_dict(authority_matrix):
    ctx = make_context("SERD2", "query")
    result = deliver_response(ctx)  # no grounded_response/safety_decision supplied
    assert result.delivery_status == "UPSTREAM_BLOCKED"
    reloaded = delivery_result_from_dict(delivery_result_to_dict(result))
    assert reloaded == result


def test_unsupported_language_result_round_trips_through_dict(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("SERD3-D1", "Content.")], "SERD3-q")
    ctx = make_context("SERD3", "query", requested_language="fr")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety)
    assert result.delivery_status == "UNSUPPORTED_LANGUAGE"
    reloaded = delivery_result_from_dict(delivery_result_to_dict(result))
    assert reloaded == result


def test_translation_failed_result_round_trips_through_dict(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("SERD4-D1", "Content.")], "SERD4-q")
    ctx = make_context("SERD4", "query", requested_language="hi")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety)  # no provider
    assert result.delivery_status == "TRANSLATION_FAILED"
    reloaded = delivery_result_from_dict(delivery_result_to_dict(result))
    assert reloaded == result


def test_delivery_result_round_trips_through_json(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("SERD5-D1", "Content.")], "SERD5-q")
    ctx = make_context("SERD5", "query", requested_language="ta")
    provider = FakeTranslationProvider(response_text="தமிழ் மொழிபெயர்ப்பு")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety, translation_provider=provider)
    parsed = json.loads(delivery_result_to_json(result))
    reloaded = delivery_result_from_dict(parsed["content"])
    assert reloaded == result


def test_delivery_result_json_preserves_unicode_without_escaping(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("SERD6-D1", "Content.")], "SERD6-q")
    ctx = make_context("SERD6", "query", requested_language="hi")
    provider = FakeTranslationProvider(response_text="अनुमोदित")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety, translation_provider=provider)
    raw_json = delivery_result_to_json(result)
    assert "अनुमोदित" in raw_json  # ensure_ascii=False - never \uXXXX-escaped


# ---------------------------------------------------------------------------
# Malformed serialization rejection
# ---------------------------------------------------------------------------


def test_delivery_result_from_dict_rejects_non_dict():
    with pytest.raises(MultilingualSchemaError):
        delivery_result_from_dict("not a dict")
    with pytest.raises(MultilingualSchemaError):
        delivery_result_from_dict(None)


def test_delivery_result_from_dict_rejects_missing_field(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("SERD7-D1", "Content.")], "SERD7-q")
    ctx = make_context("SERD7", "query")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety)
    data = delivery_result_to_dict(result)
    del data["delivery_status"]
    with pytest.raises(MultilingualSchemaError):
        delivery_result_from_dict(data)


def test_delivery_result_from_dict_rejects_wrong_type_field(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("SERD8-D1", "Content.")], "SERD8-q")
    ctx = make_context("SERD8", "query")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety)
    data = delivery_result_to_dict(result)
    data["cited_evidence_ids"] = "not a list"
    with pytest.raises(MultilingualSchemaError):
        delivery_result_from_dict(data)


def test_delivery_result_from_dict_rejects_invalid_delivery_status(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("SERD9-D1", "Content.")], "SERD9-q")
    ctx = make_context("SERD9", "query")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety)
    data = delivery_result_to_dict(result)
    data["delivery_status"] = "FORGED_STATUS"
    with pytest.raises(MultilingualSchemaError):
        delivery_result_from_dict(data)


def test_delivery_result_from_dict_rejects_inconsistent_reason_code(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("SERD10-D1", "Content.")], "SERD10-q")
    ctx = make_context("SERD10", "query")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety)
    data = delivery_result_to_dict(result)
    data["reason_code"] = "TRANSLATION_SUCCEEDED"  # not permitted for DELIVERED/LANGUAGE_UNSPECIFIED path mismatch
    data["delivery_status"] = "UPSTREAM_BLOCKED"
    with pytest.raises(MultilingualSchemaError):
        delivery_result_from_dict(data)


def test_delivery_result_from_dict_rejects_duplicate_cited_evidence_ids(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("SERD11-D1", "Content.")], "SERD11-q")
    ctx = make_context("SERD11", "query")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety)
    data = delivery_result_to_dict(result)
    data["cited_evidence_ids"] = data["cited_evidence_ids"] + data["cited_evidence_ids"]
    if len(data["cited_evidence_ids"]) < 2:
        pytest.skip("no cited evidence ids on this synthetic fixture to duplicate")
    with pytest.raises(MultilingualSchemaError):
        delivery_result_from_dict(data)


def test_delivery_result_from_dict_rejects_wrong_delivery_metadata_type(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("SERD12-D1", "Content.")], "SERD12-q")
    ctx = make_context("SERD12", "query")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety)
    data = delivery_result_to_dict(result)
    data["delivery_metadata"] = "not a dict"
    with pytest.raises(MultilingualSchemaError):
        delivery_result_from_dict(data)
