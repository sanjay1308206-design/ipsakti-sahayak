"""
Phase 7 tests: the critical Phase 7 invariant (provenance survives all
four stages - BM25, dense, RRF, reranking), synthetic flag propagation,
and the machine-readable config/hybrid_retrieval_contract.yaml /
config/hybrid_result_schema.yaml contracts.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml
from _hybrid_fixtures import make_fake_model, make_fake_reranker, make_single_chunk
from _hybrid_schema import (
    HybridSchemaValidationError,
    validate_hybrid_result_schema,
    validate_hybrid_retrieval_contract,
)

from retrieval.faiss_index import build_dense_index, dense_query
from retrieval.hybrid import rerank_candidates
from retrieval.index import build_index, query as bm25_query
from retrieval.rrf import fuse_rrf

REPO_ROOT = Path(__file__).resolve().parent.parent
HYBRID_CONTRACT_PATH = REPO_ROOT / "config" / "hybrid_retrieval_contract.yaml"
HYBRID_SCHEMA_PATH = REPO_ROOT / "config" / "hybrid_result_schema.yaml"


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# THE critical Phase 7 invariant: provenance survives all four stages
# ---------------------------------------------------------------------------


def test_provenance_survives_bm25_dense_rrf_and_reranking(authority_matrix):
    chunk = make_single_chunk(
        "Clause one describes trademark registration procedure in detail.",
        "SYNTHETIC-HYBRID-TRACE-0001",
        authority_matrix,
        source_family_id="SF-04",
        jurisdiction="INDIA",
    )
    bm25_index = build_index([chunk])
    model = make_fake_model()
    dense_index = build_dense_index([chunk], model)

    # 1. BM25 alone
    bm25_resp = bm25_query(bm25_index, "trademark registration procedure", top_k=1)
    bm25_result = bm25_resp.results[0]
    assert bm25_result.chunk_id == chunk.chunk_id
    assert bm25_result.block_ids == chunk.block_ids
    assert bm25_result.document_id == "SYNTHETIC-HYBRID-TRACE-0001"
    assert bm25_result.source_family_id == "SF-04"
    assert bm25_result.jurisdiction == "INDIA"
    assert bm25_result.content_hash == chunk.content_hash

    # 2. Dense alone
    dense_resp = dense_query(dense_index, model, "trademark registration procedure", top_k=1)
    dense_result = dense_resp.results[0]
    assert dense_result.chunk_id == chunk.chunk_id
    assert dense_result.block_ids == chunk.block_ids
    assert dense_result.document_id == "SYNTHETIC-HYBRID-TRACE-0001"

    # 3. RRF
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=1)
    rrf_result = rrf_resp.results[0]
    assert rrf_result.chunk_id == chunk.chunk_id
    assert rrf_result.block_ids == chunk.block_ids
    assert rrf_result.page_numbers == chunk.page_numbers
    assert rrf_result.document_id == "SYNTHETIC-HYBRID-TRACE-0001"
    assert rrf_result.source_family_id == "SF-04"
    assert rrf_result.jurisdiction == "INDIA"
    assert rrf_result.content_hash == chunk.content_hash

    # 4. Reranking
    reranker = make_fake_reranker()
    hybrid_resp = rerank_candidates(rrf_resp, reranker, top_k=1)
    hybrid_result = hybrid_resp.results[0]
    assert hybrid_result.chunk_id == chunk.chunk_id
    assert hybrid_result.block_ids == chunk.block_ids
    assert hybrid_result.page_numbers == chunk.page_numbers
    assert hybrid_result.document_id == "SYNTHETIC-HYBRID-TRACE-0001"
    assert hybrid_result.source_family_id == "SF-04"
    assert hybrid_result.jurisdiction == "INDIA"
    assert hybrid_result.content_hash == chunk.content_hash
    assert hybrid_result.chunk_text == chunk.text


def test_faiss_and_bm25_internal_positions_never_appear_as_chunk_identity(authority_matrix):
    chunks = [make_single_chunk(f"Trademark document {i}.", f"D-POS-{i}", authority_matrix) for i in range(5)]
    bm25_index = build_index(chunks)
    model = make_fake_model()
    dense_index = build_dense_index(chunks, model)
    bm25_resp = bm25_query(bm25_index, "trademark", top_k=5)
    dense_resp = dense_query(dense_index, model, "trademark", top_k=5)
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=5)
    reranker = make_fake_reranker()
    hybrid_resp = rerank_candidates(rrf_resp, reranker, top_k=5)

    real_ids = {c.chunk_id for c in chunks}
    for result in hybrid_resp.results:
        assert result.chunk_id in real_ids
        assert not result.chunk_id.isdigit()


# ---------------------------------------------------------------------------
# Synthetic-flag propagation
# ---------------------------------------------------------------------------


def test_synthetic_flag_propagates_true_through_all_stages(authority_matrix):
    chunk = make_single_chunk("Synthetic flag propagation text sample.", "D-SYN-07-01", authority_matrix, synthetic=True)
    bm25_index = build_index([chunk])
    model = make_fake_model()
    dense_index = build_dense_index([chunk], model)
    bm25_resp = bm25_query(bm25_index, "synthetic flag propagation", top_k=1)
    dense_resp = dense_query(dense_index, model, "synthetic flag propagation", top_k=1)
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=1)
    assert rrf_resp.results[0].synthetic is True
    reranker = make_fake_reranker()
    hybrid_resp = rerank_candidates(rrf_resp, reranker, top_k=1)
    assert hybrid_resp.results[0].synthetic is True


def test_synthetic_flag_propagates_false_through_all_stages(authority_matrix):
    chunk = make_single_chunk("Non-synthetic flag propagation text sample.", "D-SYN-07-02", authority_matrix, synthetic=False)
    bm25_index = build_index([chunk])
    model = make_fake_model()
    dense_index = build_dense_index([chunk], model)
    bm25_resp = bm25_query(bm25_index, "non-synthetic flag propagation", top_k=1)
    dense_resp = dense_query(dense_index, model, "non-synthetic flag propagation", top_k=1)
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=1)
    assert rrf_resp.results[0].synthetic is False
    reranker = make_fake_reranker()
    hybrid_resp = rerank_candidates(rrf_resp, reranker, top_k=1)
    assert hybrid_resp.results[0].synthetic is False


def test_score_fields_are_never_collapsed(authority_matrix):
    chunk = make_single_chunk("Trademark registration content.", "D-SCORES", authority_matrix)
    bm25_index = build_index([chunk])
    model = make_fake_model()
    dense_index = build_dense_index([chunk], model)
    bm25_resp = bm25_query(bm25_index, "trademark registration", top_k=1)
    dense_resp = dense_query(dense_index, model, "trademark registration", top_k=1)
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=1)
    reranker = make_fake_reranker()
    hybrid_resp = rerank_candidates(rrf_resp, reranker, top_k=1)
    result = hybrid_resp.results[0]
    # four distinct fields, all present
    assert hasattr(result, "bm25_score")
    assert hasattr(result, "dense_score")
    assert hasattr(result, "rrf_score")
    assert hasattr(result, "reranker_score")


# ---------------------------------------------------------------------------
# config/hybrid_retrieval_contract.yaml
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def hybrid_contract_raw_text() -> str:
    return HYBRID_CONTRACT_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def hybrid_contract_data(hybrid_contract_raw_text: str) -> dict:
    return yaml.safe_load(hybrid_contract_raw_text)


@pytest.fixture()
def valid_hybrid_contract_copy(hybrid_contract_data: dict) -> dict:
    return copy.deepcopy(hybrid_contract_data)


def test_hybrid_contract_file_exists_and_nonempty():
    assert HYBRID_CONTRACT_PATH.stat().st_size > 0


def test_hybrid_contract_yaml_parses(hybrid_contract_raw_text: str):
    assert isinstance(yaml.safe_load(hybrid_contract_raw_text), dict)


def test_hybrid_contract_passes_validation(hybrid_contract_data: dict):
    validate_hybrid_retrieval_contract(hybrid_contract_data)


def test_hybrid_contract_default_rrf_k_matches_implementation(hybrid_contract_data: dict):
    from retrieval.models import RrfConfig

    assert hybrid_contract_data["default_rrf_k"] == RrfConfig().k


def test_hybrid_contract_default_reranker_model_matches_implementation(hybrid_contract_data: dict):
    from retrieval.reranker import DEFAULT_RERANKER_MODEL_NAME

    assert hybrid_contract_data["default_reranker_model"] == DEFAULT_RERANKER_MODEL_NAME


def test_hybrid_contract_malformed_root_is_rejected():
    with pytest.raises(HybridSchemaValidationError):
        validate_hybrid_retrieval_contract(["not", "a", "mapping"])


def test_hybrid_contract_missing_key_is_rejected(valid_hybrid_contract_copy: dict):
    del valid_hybrid_contract_copy["safety_invariants"]
    with pytest.raises(HybridSchemaValidationError):
        validate_hybrid_retrieval_contract(valid_hybrid_contract_copy)


def test_hybrid_contract_wrong_rank_convention_is_rejected(valid_hybrid_contract_copy: dict):
    valid_hybrid_contract_copy["rank_convention"] = "ZERO_BASED"
    with pytest.raises(HybridSchemaValidationError):
        validate_hybrid_retrieval_contract(valid_hybrid_contract_copy)


# ---------------------------------------------------------------------------
# config/hybrid_result_schema.yaml
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def hybrid_schema_raw_text() -> str:
    return HYBRID_SCHEMA_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def hybrid_schema_data(hybrid_schema_raw_text: str) -> dict:
    return yaml.safe_load(hybrid_schema_raw_text)


@pytest.fixture()
def valid_hybrid_schema_copy(hybrid_schema_data: dict) -> dict:
    return copy.deepcopy(hybrid_schema_data)


def test_hybrid_schema_file_exists_and_nonempty():
    assert HYBRID_SCHEMA_PATH.stat().st_size > 0


def test_hybrid_schema_yaml_parses(hybrid_schema_raw_text: str):
    assert isinstance(yaml.safe_load(hybrid_schema_raw_text), dict)


def test_hybrid_schema_passes_validation(hybrid_schema_data: dict):
    validate_hybrid_result_schema(hybrid_schema_data)


def test_hybrid_schema_malformed_root_is_rejected():
    with pytest.raises(HybridSchemaValidationError):
        validate_hybrid_result_schema(["not", "a", "mapping"])


def test_hybrid_schema_missing_result_key_is_rejected(valid_hybrid_schema_copy: dict):
    del valid_hybrid_schema_copy["hybrid_retrieval_result"]
    with pytest.raises(HybridSchemaValidationError):
        validate_hybrid_result_schema(valid_hybrid_schema_copy)


def test_hybrid_schema_duplicate_field_name_is_rejected(valid_hybrid_schema_copy: dict):
    fields = valid_hybrid_schema_copy["hybrid_retrieval_result"]["fields"]
    fields.append(fields[0])
    with pytest.raises(HybridSchemaValidationError):
        validate_hybrid_result_schema(valid_hybrid_schema_copy)


def test_hybrid_schema_field_names_match_result_dataclass(hybrid_schema_data: dict):
    import dataclasses

    from retrieval.models import HybridRetrievalResult

    schema_field_names = {f["name"] for f in hybrid_schema_data["hybrid_retrieval_result"]["fields"]}
    dataclass_field_names = {f.name for f in dataclasses.fields(HybridRetrievalResult)}
    assert schema_field_names == dataclass_field_names


def test_hybrid_schema_rrf_result_field_names_match_dataclass(hybrid_schema_data: dict):
    import dataclasses

    from retrieval.models import RrfResult

    schema_field_names = {f["name"] for f in hybrid_schema_data["rrf_result"]["fields"]}
    dataclass_field_names = {f.name for f in dataclasses.fields(RrfResult)}
    assert schema_field_names == dataclass_field_names


def test_hybrid_schema_score_fields_document_they_are_not_legal_authority(hybrid_schema_data: dict):
    result_section = hybrid_schema_data["hybrid_retrieval_result"]
    result_fields = result_section["fields"]
    all_descriptions = " ".join(
        [result_section.get("description", "")] + [f.get("description", "") for f in result_fields]
    ).lower()
    assert "legal authority" in all_descriptions or "citation" in all_descriptions
