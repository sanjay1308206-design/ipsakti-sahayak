"""
Phase 6 tests: index-build determinism, query determinism, index signature
stability, and persistence round-trip determinism
(docs/PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md Section M/N).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _dense_fixtures import make_chunks, make_fake_model, make_single_chunk

from retrieval.embeddings import EmbeddingConfig
from retrieval.faiss_index import build_dense_index, dense_query
from retrieval.models import DenseIndexConfig
from retrieval.serialize import dense_index_metadata_to_json, dense_response_to_json, load_dense_index, save_dense_index

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def _sample_chunks(authority_matrix):
    return [
        make_single_chunk("Trademark registration process explained in detail.", "D-DET-1", authority_matrix),
        make_single_chunk("Patent filing requires a detailed specification document.", "D-DET-2", authority_matrix),
        make_single_chunk("Ayurveda formulation compliance with AYUSH rules.", "D-DET-3", authority_matrix),
    ]


def test_building_the_same_index_twice_produces_identical_metadata(authority_matrix):
    chunks = _sample_chunks(authority_matrix)
    model = make_fake_model()
    idx1 = build_dense_index(chunks, model)
    idx2 = build_dense_index(chunks, model)
    assert idx1.chunk_ids == idx2.chunk_ids
    assert idx1.signature == idx2.signature
    assert dense_index_metadata_to_json(idx1) == dense_index_metadata_to_json(idx2)


def test_running_the_same_query_twice_produces_identical_response(authority_matrix):
    chunks = _sample_chunks(authority_matrix)
    model = make_fake_model()
    idx = build_dense_index(chunks, model)
    resp1 = dense_query(idx, model, "trademark registration", top_k=3)
    resp2 = dense_query(idx, model, "trademark registration", top_k=3)
    assert [r.chunk_id for r in resp1.results] == [r.chunk_id for r in resp2.results]
    assert [r.score for r in resp1.results] == [r.score for r in resp2.results]


def test_running_the_same_query_ten_times_produces_byte_identical_json(authority_matrix):
    chunks = _sample_chunks(authority_matrix)
    model = make_fake_model()
    idx = build_dense_index(chunks, model)
    outputs = {dense_response_to_json(dense_query(idx, model, "trademark patent formulation", top_k=3)) for _ in range(10)}
    assert len(outputs) == 1


def test_index_signature_changes_when_normalize_flag_changes(authority_matrix):
    chunks = _sample_chunks(authority_matrix)
    model_norm = make_fake_model()
    model_raw = make_fake_model()
    model_raw.config = EmbeddingConfig(model_name=model_raw.model_identity, normalize=False)
    idx_norm = build_dense_index(chunks, model_norm)
    idx_raw = build_dense_index(chunks, model_raw)
    assert idx_norm.signature != idx_raw.signature


def test_index_signature_changes_when_chunk_set_changes(authority_matrix):
    chunks = _sample_chunks(authority_matrix)
    model = make_fake_model()
    idx_full = build_dense_index(chunks, model)
    idx_partial = build_dense_index(chunks[:2], model)
    assert idx_full.signature != idx_partial.signature


def test_index_signature_changes_when_dense_index_config_changes(authority_matrix):
    chunks = _sample_chunks(authority_matrix)
    model = make_fake_model()
    idx_a = build_dense_index(chunks, model, dense_index_config=DenseIndexConfig(contract_version="1.0.0"))
    idx_b = build_dense_index(chunks, model, dense_index_config=DenseIndexConfig(contract_version="1.0.1"))
    assert idx_a.signature != idx_b.signature


def test_index_signature_identical_for_identical_inputs(authority_matrix):
    chunks = _sample_chunks(authority_matrix)
    model = make_fake_model(dimension=24)
    idx1 = build_dense_index(chunks, model)
    idx2 = build_dense_index(chunks, model)
    assert idx1.signature == idx2.signature


def test_multi_chunk_document_indexing_is_also_deterministic(authority_matrix):
    chunks = make_chunks(
        "1. Heading One\n\nBody one about trademarks.\n\n2. Heading Two\n\nBody two about patents.\n",
        "D-DET-MULTI",
        authority_matrix,
    )
    model = make_fake_model()
    outputs = {dense_index_metadata_to_json(build_dense_index(chunks, model)) for _ in range(5)}
    assert len(outputs) == 1


# ---------------------------------------------------------------------------
# Persistence round-trip determinism
# ---------------------------------------------------------------------------


def test_persisted_and_reloaded_index_produces_identical_query_results(authority_matrix, tmp_path):
    chunks = _sample_chunks(authority_matrix)
    model = make_fake_model()
    idx = build_dense_index(chunks, model)
    original_response = dense_query(idx, model, "trademark registration", top_k=3)

    faiss_path = tmp_path / "index.faiss"
    metadata_path = tmp_path / "index.json"
    save_dense_index(idx, faiss_path, metadata_path)
    reloaded = load_dense_index(faiss_path, metadata_path)

    assert reloaded.signature == idx.signature
    reloaded_response = dense_query(reloaded, model, "trademark registration", top_k=3)
    assert dense_response_to_json(reloaded_response) == dense_response_to_json(original_response)


def test_persisted_metadata_json_is_deterministic_across_saves(authority_matrix, tmp_path):
    chunks = _sample_chunks(authority_matrix)
    model = make_fake_model()
    idx = build_dense_index(chunks, model)

    contents = set()
    for i in range(3):
        faiss_path = tmp_path / f"index_{i}.faiss"
        metadata_path = tmp_path / f"index_{i}.json"
        save_dense_index(idx, faiss_path, metadata_path)
        contents.add(metadata_path.read_text(encoding="utf-8"))
    assert len(contents) == 1
