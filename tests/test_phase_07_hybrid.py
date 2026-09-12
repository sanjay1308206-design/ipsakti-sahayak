"""
Phase 7 tests: hybrid pipeline integration - rerank_candidates(),
run_hybrid_pipeline(), reranking top-N/candidate-depth behavior
(docs/PHASE_07_HYBRID_FUSION_AND_RERANKING.md Sections F, O, P).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _hybrid_fixtures import make_fake_model, make_fake_reranker, make_single_chunk

from retrieval.faiss_index import build_dense_index, dense_query
from retrieval.hybrid import rerank_candidates, run_hybrid_pipeline
from retrieval.index import build_index, query as bm25_query
from retrieval.rrf import fuse_rrf

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def _build_indexes(chunks, dimension=32):
    bm25_index = build_index(chunks)
    model = make_fake_model(dimension=dimension)
    dense_index = build_dense_index(chunks, model)
    return bm25_index, dense_index, model


# ---------------------------------------------------------------------------
# rerank_candidates()
# ---------------------------------------------------------------------------


def test_rerank_candidates_reorders_by_reranker_score(authority_matrix):
    chunks = [
        make_single_chunk("Trademark trademark trademark application filing.", "D-STRONG", authority_matrix),
        make_single_chunk("Trademark mentioned once only in passing text.", "D-WEAK", authority_matrix),
    ]
    bm25_index, dense_index, model = _build_indexes(chunks)
    bm25_resp = bm25_query(bm25_index, "trademark", top_k=5)
    dense_resp = dense_query(dense_index, model, "trademark", top_k=5)
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=5)

    reranker = make_fake_reranker()
    hybrid_resp = rerank_candidates(rrf_resp, reranker, top_k=5)
    assert hybrid_resp.results[0].chunk_id in (chunks[0].chunk_id, chunks[1].chunk_id)
    scores = [r.reranker_score for r in hybrid_resp.results]
    assert scores == sorted(scores, reverse=True)


def test_rerank_candidates_preserves_bm25_and_dense_scores_unchanged(authority_matrix):
    chunks = [make_single_chunk("Trademark registration content.", "D1", authority_matrix)]
    bm25_index, dense_index, model = _build_indexes(chunks)
    bm25_resp = bm25_query(bm25_index, "trademark registration", top_k=5)
    dense_resp = dense_query(dense_index, model, "trademark registration", top_k=5)
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=5)
    reranker = make_fake_reranker()
    hybrid_resp = rerank_candidates(rrf_resp, reranker, top_k=5)

    result = hybrid_resp.results[0]
    rrf_candidate = rrf_resp.results[0]
    assert result.bm25_rank == rrf_candidate.bm25_rank
    assert result.bm25_score == rrf_candidate.bm25_score
    assert result.dense_rank == rrf_candidate.dense_rank
    assert result.dense_score == rrf_candidate.dense_score
    assert result.rrf_score == rrf_candidate.rrf_score


def test_rerank_candidates_rejects_unloaded_reranker(authority_matrix):
    chunks = [make_single_chunk("Some content.", "D1", authority_matrix)]
    bm25_index, dense_index, model = _build_indexes(chunks)
    bm25_resp = bm25_query(bm25_index, "content", top_k=5)
    dense_resp = dense_query(dense_index, model, "content", top_k=5)
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=5)

    from retrieval.reranker import FakeReranker

    unloaded = FakeReranker()
    with pytest.raises(RuntimeError):
        rerank_candidates(rrf_resp, unloaded, top_k=5)


def test_rerank_candidates_empty_rrf_response_returns_no_results(authority_matrix):
    bm25_index, dense_index, model = _build_indexes([])
    bm25_resp = bm25_query(bm25_index, "anything", top_k=5)
    dense_resp = dense_query(dense_index, model, "anything", top_k=5)
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=5)
    reranker = make_fake_reranker()
    hybrid_resp = rerank_candidates(rrf_resp, reranker, top_k=5)
    assert hybrid_resp.results == []


# ---------------------------------------------------------------------------
# Candidate depth: top_k smaller/larger than available candidates
# ---------------------------------------------------------------------------


def test_top_k_smaller_than_candidate_set_truncates(authority_matrix):
    chunks = [make_single_chunk(f"Trademark document {i}.", f"D-{i}", authority_matrix) for i in range(5)]
    bm25_index, dense_index, model = _build_indexes(chunks)
    bm25_resp = bm25_query(bm25_index, "trademark", top_k=5)
    dense_resp = dense_query(dense_index, model, "trademark", top_k=5)
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=5)
    reranker = make_fake_reranker()
    hybrid_resp = rerank_candidates(rrf_resp, reranker, top_k=2)
    assert len(hybrid_resp.results) == 2


def test_top_k_larger_than_candidate_set_returns_all_candidates(authority_matrix):
    chunks = [make_single_chunk("Only one trademark document.", "D-SOLO", authority_matrix)]
    bm25_index, dense_index, model = _build_indexes(chunks)
    bm25_resp = bm25_query(bm25_index, "trademark", top_k=5)
    dense_resp = dense_query(dense_index, model, "trademark", top_k=5)
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=5)
    reranker = make_fake_reranker()
    hybrid_resp = rerank_candidates(rrf_resp, reranker, top_k=1000)
    assert len(hybrid_resp.results) == 1


def test_all_candidates_tied_reranker_score_ties_broken_deterministically(authority_matrix):
    chunks = [
        make_single_chunk("Identical content for tie testing purposes here.", f"D-TIE-{i}", authority_matrix)
        for i in range(3)
    ]
    bm25_index, dense_index, model = _build_indexes(chunks)
    bm25_resp = bm25_query(bm25_index, "identical content tie testing", top_k=5)
    dense_resp = dense_query(dense_index, model, "identical content tie testing", top_k=5)
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=5)
    reranker = make_fake_reranker()
    hybrid_resp = rerank_candidates(rrf_resp, reranker, top_k=3)
    reranker_scores = {r.reranker_score for r in hybrid_resp.results}
    assert len(reranker_scores) == 1  # genuinely tied (identical text -> identical overlap count)
    assert [r.chunk_id for r in hybrid_resp.results] == sorted(r.chunk_id for r in hybrid_resp.results)


def test_zero_candidates_after_rrf_produces_empty_hybrid_response():
    from retrieval.models import DenseRetrievalResponse, RetrievalResponse

    bm25_resp = RetrievalResponse(query="q", normalized_query_tokens=["q"], top_k=5, index_signature="sig", results=[])
    dense_resp = DenseRetrievalResponse(query="q", top_k=5, index_signature="sig", model_identity="fake", results=[])
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=5)
    reranker = make_fake_reranker()
    hybrid_resp = rerank_candidates(rrf_resp, reranker, top_k=5)
    assert hybrid_resp.results == []


# ---------------------------------------------------------------------------
# run_hybrid_pipeline() - the full target pipeline
# ---------------------------------------------------------------------------


def test_run_hybrid_pipeline_end_to_end(authority_matrix):
    chunks = [
        make_single_chunk("Trademark registration process explained in detail.", "D1", authority_matrix),
        make_single_chunk("Patent filing requires a detailed specification document.", "D2", authority_matrix),
        make_single_chunk("Ayurveda formulation compliance with AYUSH rules.", "D3", authority_matrix),
    ]
    bm25_index, dense_index, model = _build_indexes(chunks)
    reranker = make_fake_reranker()

    hybrid_resp = run_hybrid_pipeline(
        bm25_index, dense_index, model, reranker, "trademark registration",
        bm25_top_k=3, dense_top_k=3, candidate_k=3, reranker_top_k=2,
    )
    assert len(hybrid_resp.results) == 2
    assert hybrid_resp.results[0].chunk_id == chunks[0].chunk_id


def test_run_hybrid_pipeline_matches_manual_composition(authority_matrix):
    chunks = [make_single_chunk("Trademark registration content sample.", "D1", authority_matrix)]
    bm25_index, dense_index, model = _build_indexes(chunks)
    reranker = make_fake_reranker()

    manual_bm25 = bm25_query(bm25_index, "trademark registration", top_k=2)
    manual_dense = dense_query(dense_index, model, "trademark registration", top_k=2)
    manual_rrf = fuse_rrf(manual_bm25, manual_dense, candidate_k=2)
    manual_hybrid = rerank_candidates(manual_rrf, reranker, top_k=1)

    piped = run_hybrid_pipeline(
        bm25_index, dense_index, model, reranker, "trademark registration",
        bm25_top_k=2, dense_top_k=2, candidate_k=2, reranker_top_k=1,
    )

    from retrieval.serialize import hybrid_response_to_json

    assert hybrid_response_to_json(manual_hybrid) == hybrid_response_to_json(piped)
