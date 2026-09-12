"""
Phase 6 tests: core dense build/query correctness - empty corpus,
single/multiple documents, ranking sanity, top-k behavior. All tests use
the deterministic FakeEmbeddingModel (see tests/_dense_fixtures.py) - no
download, no real model dependency.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _dense_fixtures import make_chunks, make_fake_model, make_single_chunk

from retrieval.faiss_index import build_dense_index, dense_query
from retrieval.models import DenseIndexConfig

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def test_build_dense_index_on_empty_corpus_succeeds():
    model = make_fake_model()
    idx = build_dense_index([], model)
    assert idx.chunk_count == 0
    assert idx.chunk_ids == []
    assert idx.dimension == model.dimension


def test_dense_query_on_empty_corpus_returns_no_results():
    model = make_fake_model()
    idx = build_dense_index([], model)
    resp = dense_query(idx, model, "any query text", top_k=5)
    assert resp.results == []


def test_single_document_corpus_retrieves_its_own_chunk(authority_matrix):
    chunk = make_single_chunk("The trademark office processes applications.", "D-SINGLE", authority_matrix)
    model = make_fake_model()
    idx = build_dense_index([chunk], model)
    resp = dense_query(idx, model, "trademark applications", top_k=5)
    assert len(resp.results) == 1
    assert resp.results[0].chunk_id == chunk.chunk_id


def test_multiple_documents_all_returned_ranked_by_similarity(authority_matrix):
    c1 = make_single_chunk("Trademark registration requires an application to the registry.", "D1", authority_matrix)
    c2 = make_single_chunk("Patent filing requires a technical specification document.", "D2", authority_matrix)
    c3 = make_single_chunk("Ayurveda formulation must follow AYUSH ministry rules.", "D3", authority_matrix)
    model = make_fake_model()
    idx = build_dense_index([c1, c2, c3], model)
    resp = dense_query(idx, model, "trademark registration application", top_k=3)
    # unlike BM25, dense retrieval always returns min(top_k, chunk_count)
    assert len(resp.results) == 3
    assert resp.results[0].chunk_id == c1.chunk_id
    scores = [r.score for r in resp.results]
    assert scores == sorted(scores, reverse=True)


def test_dense_index_uses_dense_index_config():
    model = make_fake_model()
    idx = build_dense_index([], model, dense_index_config=DenseIndexConfig())
    assert idx.dense_index_config.index_type == "FLAT_IP"


def test_dense_query_returns_all_chunks_for_top_k_covering_full_corpus(authority_matrix):
    chunks = make_chunks(
        "1. Heading One\n\nBody one about trademarks.\n\n2. Heading Two\n\nBody two about patents.\n",
        "D-MULTI",
        authority_matrix,
    )
    model = make_fake_model()
    idx = build_dense_index(chunks, model)
    resp = dense_query(idx, model, "trademark patent", top_k=len(chunks))
    assert len(resp.results) == len(chunks)


def test_model_identity_recorded_on_index_and_every_result(authority_matrix):
    chunk = make_single_chunk("Content for model identity check.", "D-IDENTITY", authority_matrix)
    model = make_fake_model()
    idx = build_dense_index([chunk], model)
    assert idx.model_identity == model.model_identity
    resp = dense_query(idx, model, "content model identity", top_k=1)
    assert resp.model_identity == model.model_identity
    assert resp.results[0].model_identity == model.model_identity
