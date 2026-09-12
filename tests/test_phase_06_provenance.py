"""
Phase 6 tests: the critical Phase 6 invariant (dense result -> chunk_id ->
block_ids -> page_numbers -> document_id -> source_family_id ->
jurisdiction -> content_hash), synthetic flag propagation, and the
machine-readable config/dense_retrieval_contract.yaml /
config/dense_index_schema.yaml contracts.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml
from _dense_fixtures import make_fake_model, make_single_chunk
from _dense_schema import (
    DenseSchemaValidationError,
    validate_dense_index_schema,
    validate_dense_retrieval_contract,
)

from retrieval.faiss_index import build_dense_index, dense_query

REPO_ROOT = Path(__file__).resolve().parent.parent
DENSE_CONTRACT_PATH = REPO_ROOT / "config" / "dense_retrieval_contract.yaml"
DENSE_SCHEMA_PATH = REPO_ROOT / "config" / "dense_index_schema.yaml"


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# THE critical Phase 6 invariant: full dense-result -> source traceability
# ---------------------------------------------------------------------------


def test_dense_result_traces_back_to_chunk_block_page_document_source_jurisdiction_hash(authority_matrix):
    chunk = make_single_chunk(
        "Clause one describes trademark registration procedure in detail.",
        "SYNTHETIC-DENSE-TRACE-0001",
        authority_matrix,
        source_family_id="SF-04",
        jurisdiction="INDIA",
    )
    model = make_fake_model()
    idx = build_dense_index([chunk], model)
    resp = dense_query(idx, model, "trademark registration procedure", top_k=1)
    assert len(resp.results) == 1
    result = resp.results[0]

    assert result.chunk_id == chunk.chunk_id
    assert result.block_ids == chunk.block_ids
    assert result.page_numbers == chunk.page_numbers
    assert result.document_id == chunk.document_id == "SYNTHETIC-DENSE-TRACE-0001"
    assert result.source_family_id == chunk.source_family_id == "SF-04"
    assert result.jurisdiction == chunk.jurisdiction == "INDIA"
    assert result.content_hash == chunk.content_hash


def test_multiple_chunks_each_retain_their_own_full_provenance(authority_matrix):
    c1 = make_single_chunk("Patent applications require a specification.", "D-PROV-1", authority_matrix, source_family_id="SF-01")
    c2 = make_single_chunk("Patent examination follows a fixed timeline.", "D-PROV-2", authority_matrix, source_family_id="SF-04")
    model = make_fake_model()
    idx = build_dense_index([c1, c2], model)
    resp = dense_query(idx, model, "patent", top_k=2)
    by_id = {r.chunk_id: r for r in resp.results}
    assert by_id[c1.chunk_id].source_family_id == "SF-01"
    assert by_id[c1.chunk_id].document_id == "D-PROV-1"
    assert by_id[c2.chunk_id].source_family_id == "SF-04"
    assert by_id[c2.chunk_id].document_id == "D-PROV-2"


def test_result_chunk_text_matches_original_chunk_text_verbatim(authority_matrix):
    chunk = make_single_chunk("Verbatim evidence text must never be altered by retrieval.", "D-VERBATIM", authority_matrix)
    model = make_fake_model()
    idx = build_dense_index([chunk], model)
    resp = dense_query(idx, model, "verbatim evidence", top_k=1)
    assert resp.results[0].chunk_text == chunk.text


# ---------------------------------------------------------------------------
# Synthetic-flag propagation
# ---------------------------------------------------------------------------


def test_synthetic_flag_propagates_true_to_every_result(authority_matrix):
    chunk = make_single_chunk("Synthetic flag propagation text sample.", "D-SYN-06-01", authority_matrix, synthetic=True)
    model = make_fake_model()
    idx = build_dense_index([chunk], model)
    resp = dense_query(idx, model, "synthetic flag propagation", top_k=1)
    assert resp.results[0].synthetic is True


def test_synthetic_flag_propagates_false_to_every_result(authority_matrix):
    chunk = make_single_chunk("Non-synthetic flag propagation text sample.", "D-SYN-06-02", authority_matrix, synthetic=False)
    model = make_fake_model()
    idx = build_dense_index([chunk], model)
    resp = dense_query(idx, model, "non-synthetic flag propagation", top_k=1)
    assert resp.results[0].synthetic is False


# ---------------------------------------------------------------------------
# config/dense_retrieval_contract.yaml
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def dense_contract_raw_text() -> str:
    return DENSE_CONTRACT_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def dense_contract_data(dense_contract_raw_text: str) -> dict:
    return yaml.safe_load(dense_contract_raw_text)


@pytest.fixture()
def valid_dense_contract_copy(dense_contract_data: dict) -> dict:
    return copy.deepcopy(dense_contract_data)


def test_dense_contract_file_exists_and_nonempty():
    assert DENSE_CONTRACT_PATH.stat().st_size > 0


def test_dense_contract_yaml_parses(dense_contract_raw_text: str):
    assert isinstance(yaml.safe_load(dense_contract_raw_text), dict)


def test_dense_contract_passes_validation(dense_contract_data: dict):
    validate_dense_retrieval_contract(dense_contract_data)


def test_dense_contract_default_model_matches_implementation(dense_contract_data: dict):
    from retrieval.embeddings import DEFAULT_MODEL_NAME

    assert dense_contract_data["default_embedding_model"] == DEFAULT_MODEL_NAME


def test_dense_contract_index_type_matches_implementation(dense_contract_data: dict):
    from retrieval.models import DenseIndexConfig

    assert dense_contract_data["faiss_index_type"] == DenseIndexConfig().index_type


def test_dense_contract_malformed_root_is_rejected():
    with pytest.raises(DenseSchemaValidationError):
        validate_dense_retrieval_contract(["not", "a", "mapping"])


def test_dense_contract_missing_key_is_rejected(valid_dense_contract_copy: dict):
    del valid_dense_contract_copy["safety_invariants"]
    with pytest.raises(DenseSchemaValidationError):
        validate_dense_retrieval_contract(valid_dense_contract_copy)


def test_dense_contract_inconsistent_index_type_is_rejected(valid_dense_contract_copy: dict):
    valid_dense_contract_copy["faiss_index_type"] = "IVF"
    with pytest.raises(DenseSchemaValidationError):
        validate_dense_retrieval_contract(valid_dense_contract_copy)


# ---------------------------------------------------------------------------
# config/dense_index_schema.yaml
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def dense_schema_raw_text() -> str:
    return DENSE_SCHEMA_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def dense_schema_data(dense_schema_raw_text: str) -> dict:
    return yaml.safe_load(dense_schema_raw_text)


@pytest.fixture()
def valid_dense_schema_copy(dense_schema_data: dict) -> dict:
    return copy.deepcopy(dense_schema_data)


def test_dense_schema_file_exists_and_nonempty():
    assert DENSE_SCHEMA_PATH.stat().st_size > 0


def test_dense_schema_yaml_parses(dense_schema_raw_text: str):
    assert isinstance(yaml.safe_load(dense_schema_raw_text), dict)


def test_dense_schema_passes_validation(dense_schema_data: dict):
    validate_dense_index_schema(dense_schema_data)


def test_dense_schema_malformed_root_is_rejected():
    with pytest.raises(DenseSchemaValidationError):
        validate_dense_index_schema(["not", "a", "mapping"])


def test_dense_schema_missing_result_key_is_rejected(valid_dense_schema_copy: dict):
    del valid_dense_schema_copy["dense_retrieval_result"]
    with pytest.raises(DenseSchemaValidationError):
        validate_dense_index_schema(valid_dense_schema_copy)


def test_dense_schema_duplicate_field_name_is_rejected(valid_dense_schema_copy: dict):
    fields = valid_dense_schema_copy["dense_retrieval_result"]["fields"]
    fields.append(fields[0])
    with pytest.raises(DenseSchemaValidationError):
        validate_dense_index_schema(valid_dense_schema_copy)


def test_dense_schema_field_names_match_result_dataclass(dense_schema_data: dict):
    import dataclasses

    from retrieval.models import DenseRetrievalResult

    schema_field_names = {f["name"] for f in dense_schema_data["dense_retrieval_result"]["fields"]}
    dataclass_field_names = {f.name for f in dataclasses.fields(DenseRetrievalResult)}
    assert schema_field_names == dataclass_field_names


def test_dense_schema_score_field_documents_it_is_not_legal_authority(dense_schema_data: dict):
    score_field = next(f for f in dense_schema_data["dense_retrieval_result"]["fields"] if f["name"] == "score")
    description = score_field["description"].lower()
    assert "legal authority" in description
    assert "citation" in description
