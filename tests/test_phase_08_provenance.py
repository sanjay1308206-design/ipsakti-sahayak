"""
Phase 8 tests: the critical Phase 8 invariant (evidence_id -> chunk_id ->
block_id(s) -> page(s) -> document_id -> source_family_id -> jurisdiction
-> content_hash), synthetic flag propagation, authoritativeness/jurisdiction
passthrough, and the machine-readable config/evidence_contract.yaml /
config/evidence_schema.yaml contracts.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml
from _evidence_fixtures import make_hybrid_response, make_single_chunk
from _evidence_schema import EvidenceSchemaValidationError, validate_evidence_contract, validate_evidence_schema

from evidence.builder import build_evidence_pack

REPO_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_CONTRACT_PATH = REPO_ROOT / "config" / "evidence_contract.yaml"
EVIDENCE_SCHEMA_PATH = REPO_ROOT / "config" / "evidence_schema.yaml"


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# THE critical Phase 8 invariant: full evidence -> source traceability
# ---------------------------------------------------------------------------


def test_evidence_traces_back_to_chunk_block_page_document_source_jurisdiction_hash(authority_matrix):
    chunk = make_single_chunk(
        "Clause one describes trademark registration procedure in detail.",
        "SYNTHETIC-EVIDENCE-TRACE-0001",
        authority_matrix,
        source_family_id="SF-04",
        jurisdiction="INDIA",
    )
    resp = make_hybrid_response([chunk], "trademark registration procedure", top_k=1)
    pack = build_evidence_pack(resp.results, "trademark registration procedure")
    assert len(pack.evidence_items) == 1
    evidence = pack.evidence_items[0]

    assert evidence.chunk_id == chunk.chunk_id
    assert evidence.block_ids == chunk.block_ids
    assert evidence.page_numbers == chunk.page_numbers
    assert evidence.document_id == chunk.document_id == "SYNTHETIC-EVIDENCE-TRACE-0001"
    assert evidence.source_family_id == chunk.source_family_id == "SF-04"
    assert evidence.jurisdiction == chunk.jurisdiction == "INDIA"
    assert evidence.content_hash == chunk.content_hash


def test_source_location_property_matches_flat_fields(authority_matrix):
    chunk = make_single_chunk("Patent content.", "D-LOC", authority_matrix, source_family_id="SF-01", jurisdiction="INDIA")
    resp = make_hybrid_response([chunk], "patent", top_k=1)
    pack = build_evidence_pack(resp.results, "patent")
    evidence = pack.evidence_items[0]
    location = evidence.source_location
    assert location.document_id == evidence.document_id
    assert location.source_family_id == evidence.source_family_id
    assert location.jurisdiction == evidence.jurisdiction
    assert location.content_hash == evidence.content_hash
    assert location.page_numbers == evidence.page_numbers
    assert location.block_ids == evidence.block_ids


def test_multiple_evidence_items_each_retain_their_own_full_provenance(authority_matrix):
    c1 = make_single_chunk("Patent applications require a specification.", "D-PROV-1", authority_matrix, source_family_id="SF-01")
    c2 = make_single_chunk("Patent examination follows a fixed timeline.", "D-PROV-2", authority_matrix, source_family_id="SF-04")
    resp = make_hybrid_response([c1, c2], "patent", top_k=2)
    pack = build_evidence_pack(resp.results, "patent")
    by_document = {e.document_id: e for e in pack.evidence_items}
    assert by_document["D-PROV-1"].source_family_id == "SF-01"
    assert by_document["D-PROV-2"].source_family_id == "SF-04"


def test_pack_jurisdictions_and_source_family_ids_properties(authority_matrix):
    c1 = make_single_chunk("Trademark content one.", "D-J1", authority_matrix, source_family_id="SF-01", jurisdiction="INDIA")
    c2 = make_single_chunk("Trademark content two.", "D-J2", authority_matrix, source_family_id="SF-04", jurisdiction="INDIA")
    resp = make_hybrid_response([c1, c2], "trademark content", top_k=2)
    pack = build_evidence_pack(resp.results, "trademark content")
    assert pack.jurisdictions == frozenset({"INDIA"})
    assert pack.source_family_ids == frozenset({"SF-01", "SF-04"})


# ---------------------------------------------------------------------------
# Synthetic-flag propagation
# ---------------------------------------------------------------------------


def test_synthetic_flag_propagates_true_through_evidence_and_pack(authority_matrix):
    chunk = make_single_chunk("Synthetic flag propagation text.", "D-SYN-08-01", authority_matrix, synthetic=True)
    resp = make_hybrid_response([chunk], "synthetic flag propagation", top_k=1)
    pack = build_evidence_pack(resp.results, "synthetic flag propagation")
    assert pack.evidence_items[0].synthetic is True


def test_synthetic_flag_propagates_false_through_evidence_and_pack(authority_matrix):
    chunk = make_single_chunk("Non-synthetic flag propagation text.", "D-SYN-08-02", authority_matrix, synthetic=False)
    resp = make_hybrid_response([chunk], "non-synthetic flag propagation", top_k=1)
    pack = build_evidence_pack(resp.results, "non-synthetic flag propagation")
    assert pack.evidence_items[0].synthetic is False


# ---------------------------------------------------------------------------
# config/evidence_contract.yaml
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def evidence_contract_raw_text() -> str:
    return EVIDENCE_CONTRACT_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def evidence_contract_data(evidence_contract_raw_text: str) -> dict:
    return yaml.safe_load(evidence_contract_raw_text)


@pytest.fixture()
def valid_evidence_contract_copy(evidence_contract_data: dict) -> dict:
    return copy.deepcopy(evidence_contract_data)


def test_evidence_contract_file_exists_and_nonempty():
    assert EVIDENCE_CONTRACT_PATH.stat().st_size > 0


def test_evidence_contract_yaml_parses(evidence_contract_raw_text: str):
    assert isinstance(yaml.safe_load(evidence_contract_raw_text), dict)


def test_evidence_contract_passes_validation(evidence_contract_data: dict):
    validate_evidence_contract(evidence_contract_data)


def test_evidence_contract_default_max_items_matches_implementation(evidence_contract_data: dict):
    from evidence.models import EvidenceSelectionConfig

    assert evidence_contract_data["default_max_evidence_items"] == EvidenceSelectionConfig().max_evidence_items


def test_evidence_contract_schema_version_matches_implementation(evidence_contract_data: dict):
    from evidence.models import EVIDENCE_SCHEMA_VERSION

    assert evidence_contract_data["evidence_schema_version"] == EVIDENCE_SCHEMA_VERSION


def test_evidence_contract_malformed_root_is_rejected():
    with pytest.raises(EvidenceSchemaValidationError):
        validate_evidence_contract(["not", "a", "mapping"])


def test_evidence_contract_missing_key_is_rejected(valid_evidence_contract_copy: dict):
    del valid_evidence_contract_copy["safety_invariants"]
    with pytest.raises(EvidenceSchemaValidationError):
        validate_evidence_contract(valid_evidence_contract_copy)


def test_evidence_contract_wrong_evidence_types_is_rejected(valid_evidence_contract_copy: dict):
    valid_evidence_contract_copy["evidence_types"] = ["ANSWER"]
    with pytest.raises(EvidenceSchemaValidationError):
        validate_evidence_contract(valid_evidence_contract_copy)


# ---------------------------------------------------------------------------
# config/evidence_schema.yaml
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def evidence_schema_raw_text() -> str:
    return EVIDENCE_SCHEMA_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def evidence_schema_data(evidence_schema_raw_text: str) -> dict:
    return yaml.safe_load(evidence_schema_raw_text)


@pytest.fixture()
def valid_evidence_schema_copy(evidence_schema_data: dict) -> dict:
    return copy.deepcopy(evidence_schema_data)


def test_evidence_schema_file_exists_and_nonempty():
    assert EVIDENCE_SCHEMA_PATH.stat().st_size > 0


def test_evidence_schema_yaml_parses(evidence_schema_raw_text: str):
    assert isinstance(yaml.safe_load(evidence_schema_raw_text), dict)


def test_evidence_schema_passes_validation(evidence_schema_data: dict):
    validate_evidence_schema(evidence_schema_data)


def test_evidence_schema_malformed_root_is_rejected():
    with pytest.raises(EvidenceSchemaValidationError):
        validate_evidence_schema(["not", "a", "mapping"])


def test_evidence_schema_missing_evidence_key_is_rejected(valid_evidence_schema_copy: dict):
    del valid_evidence_schema_copy["evidence"]
    with pytest.raises(EvidenceSchemaValidationError):
        validate_evidence_schema(valid_evidence_schema_copy)


def test_evidence_schema_duplicate_field_name_is_rejected(valid_evidence_schema_copy: dict):
    fields = valid_evidence_schema_copy["evidence"]["fields"]
    fields.append(fields[0])
    with pytest.raises(EvidenceSchemaValidationError):
        validate_evidence_schema(valid_evidence_schema_copy)


def test_evidence_schema_field_names_match_dataclass(evidence_schema_data: dict):
    import dataclasses

    from evidence.models import Evidence

    schema_field_names = {f["name"] for f in evidence_schema_data["evidence"]["fields"]}
    dataclass_field_names = {f.name for f in dataclasses.fields(Evidence)}
    assert schema_field_names == dataclass_field_names


def test_evidence_schema_pack_field_names_match_dataclass(evidence_schema_data: dict):
    import dataclasses

    from evidence.models import EvidencePack

    schema_field_names = {f["name"] for f in evidence_schema_data["evidence_pack"]["fields"]}
    dataclass_field_names = {f.name for f in dataclasses.fields(EvidencePack)}
    assert schema_field_names == dataclass_field_names


def test_evidence_schema_retrieval_metadata_never_documented_as_legal_authority(evidence_schema_data: dict):
    section = evidence_schema_data["retrieval_metadata"]
    text = section.get("description", "").lower()
    assert "legal" in text or "authority" in text
