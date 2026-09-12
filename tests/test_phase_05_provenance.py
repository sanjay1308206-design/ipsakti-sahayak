"""
Phase 5 tests: the critical Phase 5 invariant (retrieval result -> chunk_id
-> block_ids -> page_numbers -> document_id -> source_family_id ->
jurisdiction -> content_hash), synthetic flag propagation, and the
machine-readable config/bm25_contract.yaml / config/retrieval_result_schema.yaml
contracts.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml
from _bm25_fixtures import make_single_chunk
from _bm25_schema import Bm25SchemaValidationError, validate_bm25_contract, validate_retrieval_result_schema

from retrieval.index import build_index, query

REPO_ROOT = Path(__file__).resolve().parent.parent
BM25_CONTRACT_PATH = REPO_ROOT / "config" / "bm25_contract.yaml"
RETRIEVAL_SCHEMA_PATH = REPO_ROOT / "config" / "retrieval_result_schema.yaml"


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# THE critical Phase 5 invariant: full retrieval -> source traceability
# ---------------------------------------------------------------------------


def test_retrieval_result_traces_back_to_chunk_block_page_document_source_jurisdiction_hash(authority_matrix):
    chunk = make_single_chunk(
        "Clause one describes trademark registration procedure in detail.",
        "SYNTHETIC-RETRIEVAL-TRACE-0001",
        authority_matrix,
        source_family_id="SF-04",
        jurisdiction="INDIA",
    )
    idx = build_index([chunk])
    resp = query(idx, "trademark registration procedure", top_k=1)
    assert len(resp.results) == 1
    result = resp.results[0]

    # result -> chunk_id
    assert result.chunk_id == chunk.chunk_id
    # -> block_ids
    assert result.block_ids == chunk.block_ids
    # -> page_numbers
    assert result.page_numbers == chunk.page_numbers
    # -> document_id
    assert result.document_id == chunk.document_id == "SYNTHETIC-RETRIEVAL-TRACE-0001"
    # -> source_family_id
    assert result.source_family_id == chunk.source_family_id == "SF-04"
    # -> jurisdiction
    assert result.jurisdiction == chunk.jurisdiction == "INDIA"
    # -> content_hash
    assert result.content_hash == chunk.content_hash


def test_multiple_chunks_each_retain_their_own_full_provenance(authority_matrix):
    c1 = make_single_chunk("Patent applications require a specification.", "D-PROV-1", authority_matrix, source_family_id="SF-01")
    c2 = make_single_chunk("Patent examination follows a fixed timeline.", "D-PROV-2", authority_matrix, source_family_id="SF-04")
    idx = build_index([c1, c2])
    resp = query(idx, "patent", top_k=2)
    by_id = {r.chunk_id: r for r in resp.results}
    assert by_id[c1.chunk_id].source_family_id == "SF-01"
    assert by_id[c1.chunk_id].document_id == "D-PROV-1"
    assert by_id[c2.chunk_id].source_family_id == "SF-04"
    assert by_id[c2.chunk_id].document_id == "D-PROV-2"


def test_result_chunk_text_matches_original_chunk_text_verbatim(authority_matrix):
    chunk = make_single_chunk("Verbatim evidence text must never be altered by retrieval.", "D-VERBATIM", authority_matrix)
    idx = build_index([chunk])
    resp = query(idx, "verbatim evidence", top_k=1)
    assert resp.results[0].chunk_text == chunk.text


# ---------------------------------------------------------------------------
# Synthetic-flag propagation
# ---------------------------------------------------------------------------


def test_synthetic_flag_propagates_true_to_every_result(authority_matrix):
    chunk = make_single_chunk("Synthetic flag propagation text sample.", "D-SYN-05-01", authority_matrix, synthetic=True)
    idx = build_index([chunk])
    resp = query(idx, "synthetic flag propagation", top_k=1)
    assert resp.results[0].synthetic is True


def test_synthetic_flag_propagates_false_to_every_result(authority_matrix):
    chunk = make_single_chunk("Non-synthetic flag propagation text sample.", "D-SYN-05-02", authority_matrix, synthetic=False)
    idx = build_index([chunk])
    resp = query(idx, "non-synthetic flag propagation", top_k=1)
    assert resp.results[0].synthetic is False


# ---------------------------------------------------------------------------
# config/bm25_contract.yaml
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def bm25_contract_raw_text() -> str:
    return BM25_CONTRACT_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def bm25_contract_data(bm25_contract_raw_text: str) -> dict:
    return yaml.safe_load(bm25_contract_raw_text)


@pytest.fixture()
def valid_bm25_contract_copy(bm25_contract_data: dict) -> dict:
    return copy.deepcopy(bm25_contract_data)


def test_bm25_contract_file_exists_and_nonempty():
    assert BM25_CONTRACT_PATH.stat().st_size > 0


def test_bm25_contract_yaml_parses(bm25_contract_raw_text: str):
    assert isinstance(yaml.safe_load(bm25_contract_raw_text), dict)


def test_bm25_contract_passes_validation(bm25_contract_data: dict):
    validate_bm25_contract(bm25_contract_data)


def test_bm25_contract_default_parameters_match_implementation(bm25_contract_data: dict):
    from retrieval.models import Bm25Config

    default = Bm25Config()
    assert bm25_contract_data["default_parameters"]["k1"] == default.k1
    assert bm25_contract_data["default_parameters"]["b"] == default.b


def test_bm25_contract_tokenizer_version_matches_implementation(bm25_contract_data: dict):
    from retrieval.tokenizer import TOKENIZER_POLICY_VERSION

    assert bm25_contract_data["tokenizer_policy_version"] == TOKENIZER_POLICY_VERSION


def test_bm25_contract_malformed_root_is_rejected():
    with pytest.raises(Bm25SchemaValidationError):
        validate_bm25_contract(["not", "a", "mapping"])


def test_bm25_contract_missing_key_is_rejected(valid_bm25_contract_copy: dict):
    del valid_bm25_contract_copy["safety_invariants"]
    with pytest.raises(Bm25SchemaValidationError):
        validate_bm25_contract(valid_bm25_contract_copy)


def test_bm25_contract_invalid_b_bound_is_rejected(valid_bm25_contract_copy: dict):
    valid_bm25_contract_copy["default_parameters"]["b"] = 1.5
    with pytest.raises(Bm25SchemaValidationError):
        validate_bm25_contract(valid_bm25_contract_copy)


# ---------------------------------------------------------------------------
# config/retrieval_result_schema.yaml
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def retrieval_schema_raw_text() -> str:
    return RETRIEVAL_SCHEMA_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def retrieval_schema_data(retrieval_schema_raw_text: str) -> dict:
    return yaml.safe_load(retrieval_schema_raw_text)


@pytest.fixture()
def valid_retrieval_schema_copy(retrieval_schema_data: dict) -> dict:
    return copy.deepcopy(retrieval_schema_data)


def test_retrieval_schema_file_exists_and_nonempty():
    assert RETRIEVAL_SCHEMA_PATH.stat().st_size > 0


def test_retrieval_schema_yaml_parses(retrieval_schema_raw_text: str):
    assert isinstance(yaml.safe_load(retrieval_schema_raw_text), dict)


def test_retrieval_schema_passes_validation(retrieval_schema_data: dict):
    validate_retrieval_result_schema(retrieval_schema_data)


def test_retrieval_schema_malformed_root_is_rejected():
    with pytest.raises(Bm25SchemaValidationError):
        validate_retrieval_result_schema(["not", "a", "mapping"])


def test_retrieval_schema_missing_result_key_is_rejected(valid_retrieval_schema_copy: dict):
    del valid_retrieval_schema_copy["retrieval_result"]
    with pytest.raises(Bm25SchemaValidationError):
        validate_retrieval_result_schema(valid_retrieval_schema_copy)


def test_retrieval_schema_duplicate_field_name_is_rejected(valid_retrieval_schema_copy: dict):
    fields = valid_retrieval_schema_copy["retrieval_result"]["fields"]
    fields.append(fields[0])
    with pytest.raises(Bm25SchemaValidationError):
        validate_retrieval_result_schema(valid_retrieval_schema_copy)


def test_retrieval_schema_field_names_match_result_dataclass(retrieval_schema_data: dict):
    import dataclasses

    from retrieval.models import RetrievalResult

    schema_field_names = {f["name"] for f in retrieval_schema_data["retrieval_result"]["fields"]}
    dataclass_field_names = {f.name for f in dataclasses.fields(RetrievalResult)}
    assert schema_field_names == dataclass_field_names
