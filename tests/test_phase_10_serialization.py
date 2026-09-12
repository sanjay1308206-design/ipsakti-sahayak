"""
Phase 10 tests: serialization round-trip safety - GenerationOutput,
GroundedResponse (docs/PHASE_10_GROUNDED_GENERATION.md Section R).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from _generation_fixtures import citing_provider, make_pack_from_texts

from generation.generator import generate_grounded_response
from generation.models import GenerationOutput, GenerationSchemaError
from generation.providers import FakeGenerationProvider
from generation.serialize import (
    generation_output_from_dict,
    generation_output_to_dict,
    generation_output_to_json,
    grounded_response_from_dict,
    grounded_response_to_dict,
    grounded_response_to_json,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# GenerationOutput round-trip
# ---------------------------------------------------------------------------


def test_generation_output_round_trips_through_dict():
    output = GenerationOutput(
        raw_text="hello [[CITE:abc]]", provider_name="p", model_identifier="m", success=True, failure_reason=None,
        metadata={"tokens_used": 10},
    )
    reloaded = generation_output_from_dict(generation_output_to_dict(output))
    assert reloaded == output


def test_generation_output_json_round_trips():
    output = GenerationOutput(raw_text="x", provider_name="p", model_identifier="m", success=False, failure_reason="err", metadata={})
    parsed = json.loads(generation_output_to_json(output))
    reloaded = generation_output_from_dict(parsed["content"])
    assert reloaded == output


def test_generation_output_from_dict_rejects_missing_field():
    with pytest.raises(GenerationSchemaError):
        generation_output_from_dict({"raw_text": "x"})


def test_generation_output_from_dict_rejects_non_dict():
    with pytest.raises(GenerationSchemaError):
        generation_output_from_dict("not a dict")


# ---------------------------------------------------------------------------
# GroundedResponse round-trip
# ---------------------------------------------------------------------------


def test_grounded_response_round_trips_through_dict(authority_matrix):
    pack = make_pack_from_texts([("D-SER-1", "Trademark serialization content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    response = generate_grounded_response("q", pack, citing_provider(real_id))
    reloaded = grounded_response_from_dict(grounded_response_to_dict(response))
    assert reloaded == response


def test_abstained_response_round_trips_through_dict(authority_matrix):
    from evidence.builder import build_evidence_pack

    pack = build_evidence_pack([], "no evidence")
    response = generate_grounded_response("q", pack, citing_provider("x"))
    reloaded = grounded_response_from_dict(grounded_response_to_dict(response))
    assert reloaded == response


def test_generation_failed_response_round_trips_through_dict(authority_matrix):
    pack = make_pack_from_texts([("D-SER-2", "Content.")], authority_matrix)
    provider = FakeGenerationProvider(fail_with="outage")
    response = generate_grounded_response("q", pack, provider)
    reloaded = grounded_response_from_dict(grounded_response_to_dict(response))
    assert reloaded == response


def test_grounded_response_json_is_valid_json_and_round_trips(authority_matrix):
    pack = make_pack_from_texts([("D-SER-3", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    response = generate_grounded_response("q", pack, citing_provider(real_id))
    parsed = json.loads(grounded_response_to_json(response))
    reloaded = grounded_response_from_dict(parsed["content"])
    assert reloaded == response


def test_grounded_response_from_dict_rejects_non_dict():
    with pytest.raises(GenerationSchemaError):
        grounded_response_from_dict("not a dict")


def test_grounded_response_from_dict_rejects_missing_field(authority_matrix):
    pack = make_pack_from_texts([("D-SER-4", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    response = generate_grounded_response("q", pack, citing_provider(real_id))
    data = grounded_response_to_dict(response)
    del data["grounding_status"]
    with pytest.raises(GenerationSchemaError):
        grounded_response_from_dict(data)


def test_grounded_response_from_dict_rejects_invalid_status_combination(authority_matrix):
    pack = make_pack_from_texts([("D-SER-5", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    response = generate_grounded_response("q", pack, citing_provider(real_id))
    data = grounded_response_to_dict(response)
    data["grounding_status"] = "ABSTAINED"  # now inconsistent with answer_text/abstention_reason
    with pytest.raises(GenerationSchemaError):
        grounded_response_from_dict(data)


def test_grounded_response_from_dict_rejects_wrong_type_field(authority_matrix):
    pack = make_pack_from_texts([("D-SER-6", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    response = generate_grounded_response("q", pack, citing_provider(real_id))
    data = grounded_response_to_dict(response)
    data["cited_evidence_ids"] = "not a list"
    with pytest.raises(GenerationSchemaError):
        grounded_response_from_dict(data)


def test_grounded_response_from_dict_rejects_malformed_nested_citation_summary(authority_matrix):
    pack = make_pack_from_texts([("D-SER-7", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    response = generate_grounded_response("q", pack, citing_provider(real_id))
    data = grounded_response_to_dict(response)
    data["citation_validation_summary"]["total_references"] = 999  # breaks the sum invariant
    with pytest.raises(GenerationSchemaError):
        grounded_response_from_dict(data)


def test_malicious_strings_in_response_survive_serialization(authority_matrix):
    pack = make_pack_from_texts([("D-SER-8", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    provider = FakeGenerationProvider(response_text=f'<script>alert(1)</script> [[CITE:{real_id}]]')
    response = generate_grounded_response("q", pack, provider)
    reloaded = grounded_response_from_dict(grounded_response_to_dict(response))
    assert reloaded.answer_text == response.answer_text


def test_unicode_in_response_survives_json_round_trip(authority_matrix):
    pack = make_pack_from_texts([("D-SER-9", "आयुर्वेद content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    provider = FakeGenerationProvider(response_text=f"आयुर्वेद उत्तर [[CITE:{real_id}]]")
    response = generate_grounded_response("प्रश्न", pack, provider)
    parsed = json.loads(grounded_response_to_json(response))
    reloaded = grounded_response_from_dict(parsed["content"])
    assert reloaded.answer_text == response.answer_text
    assert reloaded.query == "प्रश्न"


def test_large_string_response_survives_serialization(authority_matrix):
    pack = make_pack_from_texts([("D-SER-10", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    huge_text = ("answer text segment " * 5000) + f" [[CITE:{real_id}]]"
    provider = FakeGenerationProvider(response_text=huge_text)
    response = generate_grounded_response("q", pack, provider)
    reloaded = grounded_response_from_dict(grounded_response_to_dict(response))
    assert reloaded.answer_text == huge_text
