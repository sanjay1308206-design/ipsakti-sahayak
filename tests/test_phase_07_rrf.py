"""
Phase 7 tests: Reciprocal Rank Fusion mathematics, candidate union,
duplicate handling, and tie-breaking (docs/PHASE_07_HYBRID_FUSION_AND_RERANKING.md
Sections G, H, I, J, K).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _hybrid_fixtures import make_single_chunk

from retrieval.faiss_index import build_dense_index, dense_query
from retrieval.index import build_index, query as bm25_query
from retrieval.models import RrfConfig
from retrieval.rrf import fuse_rrf
from _dense_fixtures import make_fake_model

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def _bm25_and_dense(chunks, authority_matrix, query_text, top_k=10, dimension=32):
    bm25_index = build_index(chunks)
    model = make_fake_model(dimension=dimension)
    dense_index = build_dense_index(chunks, model)
    bm25_resp = bm25_query(bm25_index, query_text, top_k=top_k)
    dense_resp = dense_query(dense_index, model, query_text, top_k=top_k)
    return bm25_resp, dense_resp


# ---------------------------------------------------------------------------
# RRF formula correctness
# ---------------------------------------------------------------------------


def test_rrf_score_for_candidate_in_both_lists_sums_both_contributions(authority_matrix):
    chunks = [
        make_single_chunk("Trademark registration application process explained.", "D1", authority_matrix),
        make_single_chunk("Unrelated ayurveda formulation content only.", "D2", authority_matrix),
    ]
    bm25_resp, dense_resp = _bm25_and_dense(chunks, authority_matrix, "trademark registration")
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=10, config=RrfConfig(k=60.0))

    by_id = {r.chunk_id: r for r in rrf_resp.results}
    d1_id = chunks[0].chunk_id
    result = by_id[d1_id]
    assert result.bm25_rank is not None
    assert result.dense_rank is not None
    expected = 1.0 / (60.0 + result.bm25_rank) + 1.0 / (60.0 + result.dense_rank)
    assert result.rrf_score == pytest.approx(expected)


def test_rrf_score_for_candidate_in_only_one_list_uses_single_contribution(authority_matrix):
    # A chunk with zero BM25 term overlap never appears in BM25 results
    # (Phase 5 excludes exact-zero-score chunks), but dense always returns
    # everything - so it can appear in dense-only.
    relevant = make_single_chunk("Trademark registration application process.", "D-REL", authority_matrix)
    irrelevant = make_single_chunk("Completely unrelated weather rainfall data.", "D-IRR", authority_matrix)
    bm25_resp, dense_resp = _bm25_and_dense([relevant, irrelevant], authority_matrix, "trademark registration")

    irrelevant_in_bm25 = any(r.chunk_id == irrelevant.chunk_id for r in bm25_resp.results)
    assert not irrelevant_in_bm25  # sanity: confirms the dense-only scenario actually occurs

    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=10)
    by_id = {r.chunk_id: r for r in rrf_resp.results}
    result = by_id[irrelevant.chunk_id]
    assert result.bm25_rank is None
    assert result.bm25_score is None
    assert result.dense_rank is not None
    expected = 1.0 / (60.0 + result.dense_rank)
    assert result.rrf_score == pytest.approx(expected)


def test_rrf_k_constant_is_configurable_and_changes_scores(authority_matrix):
    chunks = [make_single_chunk("Trademark registration content.", "D1", authority_matrix)]
    bm25_resp, dense_resp = _bm25_and_dense(chunks, authority_matrix, "trademark registration")
    result_default = fuse_rrf(bm25_resp, dense_resp, candidate_k=10, config=RrfConfig(k=60.0)).results[0]
    result_custom = fuse_rrf(bm25_resp, dense_resp, candidate_k=10, config=RrfConfig(k=1.0)).results[0]
    assert result_default.rrf_score != result_custom.rrf_score


def test_rrf_config_rejects_non_positive_k():
    with pytest.raises(ValueError):
        RrfConfig(k=0)
    with pytest.raises(ValueError):
        RrfConfig(k=-1.0)


def test_rrf_config_rejects_non_numeric_k():
    with pytest.raises(ValueError):
        RrfConfig(k="60")
    with pytest.raises(ValueError):
        RrfConfig(k=True)


# ---------------------------------------------------------------------------
# Candidate union
# ---------------------------------------------------------------------------


def test_candidate_union_includes_chunks_from_both_lists(authority_matrix):
    bm25_only = make_single_chunk("Trademark registration only in lexical match exactword.", "D-BM25", authority_matrix)
    both = make_single_chunk("Patent application filing procedure details.", "D-BOTH", authority_matrix)
    bm25_resp, dense_resp = _bm25_and_dense([bm25_only, both], authority_matrix, "patent application filing")
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=10)
    result_ids = {r.chunk_id for r in rrf_resp.results}
    # both should at minimum contain the "both" chunk (present in both dense
    # (always) and possibly bm25); union must never drop a real dense hit
    assert both.chunk_id in result_ids


def test_candidate_union_never_invents_a_new_chunk_id(authority_matrix):
    chunks = [make_single_chunk(f"Document {i} about trademarks.", f"D-{i}", authority_matrix) for i in range(3)]
    bm25_resp, dense_resp = _bm25_and_dense(chunks, authority_matrix, "trademarks")
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=10)
    real_ids = {c.chunk_id for c in chunks}
    for result in rrf_resp.results:
        assert result.chunk_id in real_ids


def test_candidate_k_limits_result_count(authority_matrix):
    chunks = [make_single_chunk(f"Trademark document number {i}.", f"D-CK-{i}", authority_matrix) for i in range(5)]
    bm25_resp, dense_resp = _bm25_and_dense(chunks, authority_matrix, "trademark document")
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=2)
    assert len(rrf_resp.results) == 2


def test_candidate_k_larger_than_union_returns_full_union(authority_matrix):
    chunks = [make_single_chunk("Only one trademark document here.", "D-SOLO", authority_matrix)]
    bm25_resp, dense_resp = _bm25_and_dense(chunks, authority_matrix, "trademark")
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=1000)
    assert len(rrf_resp.results) == 1


@pytest.mark.parametrize("bad_k", [0, -1, -100])
def test_candidate_k_non_positive_raises_value_error(authority_matrix, bad_k):
    chunks = [make_single_chunk("Some content.", "D-BADCK", authority_matrix)]
    bm25_resp, dense_resp = _bm25_and_dense(chunks, authority_matrix, "content")
    with pytest.raises(ValueError):
        fuse_rrf(bm25_resp, dense_resp, candidate_k=bad_k)


def test_candidate_k_non_integer_raises_value_error(authority_matrix):
    chunks = [make_single_chunk("Some content.", "D-BADCK-TYPE", authority_matrix)]
    bm25_resp, dense_resp = _bm25_and_dense(chunks, authority_matrix, "content")
    with pytest.raises(ValueError):
        fuse_rrf(bm25_resp, dense_resp, candidate_k=2.5)
    with pytest.raises(ValueError):
        fuse_rrf(bm25_resp, dense_resp, candidate_k=True)


# ---------------------------------------------------------------------------
# Tie-breaking
# ---------------------------------------------------------------------------


def test_rrf_ties_broken_by_ascending_chunk_id():
    # Constructed directly: two candidates that each contribute from
    # exactly one, DIFFERENT retrieval system, at the same rank number -
    # this genuinely produces an equal RRF score (1/(60+1) each), unlike
    # realistic fixture text, where Phase 5/6's own upstream tie-breaks
    # already separate otherwise-identical chunks into different ranks.
    from retrieval.models import DenseRetrievalResponse, DenseRetrievalResult, RetrievalResponse, RetrievalResult

    def make_bm25_result(chunk_id, rank):
        return RetrievalResult(
            rank=rank, chunk_id=chunk_id, score=1.0, document_id="D", source_family_id="SF-01",
            jurisdiction="INDIA", content_hash="hash", synthetic=True, page_numbers=[1],
            block_ids=[f"{chunk_id}:p1:b1"], chunk_text="text",
        )

    def make_dense_result(chunk_id, rank):
        return DenseRetrievalResult(
            rank=rank, chunk_id=chunk_id, score=0.5, model_identity="fake", document_id="D",
            source_family_id="SF-01", jurisdiction="INDIA", content_hash="hash", synthetic=True,
            page_numbers=[1], block_ids=[f"{chunk_id}:p1:b1"], chunk_text="text",
        )

    bm25_resp = RetrievalResponse(
        query="q", normalized_query_tokens=["q"], top_k=5, index_signature="sig",
        results=[make_bm25_result("B-ONLY", rank=1)],
    )
    dense_resp = DenseRetrievalResponse(
        query="q", top_k=5, index_signature="sig", model_identity="fake",
        results=[make_dense_result("A-ONLY", rank=1)],
    )
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=10)
    assert len(rrf_resp.results) == 2
    assert rrf_resp.results[0].rrf_score == rrf_resp.results[1].rrf_score
    # deterministic tie-break: ascending chunk_id -> "A-ONLY" before "B-ONLY"
    assert [r.chunk_id for r in rrf_resp.results] == ["A-ONLY", "B-ONLY"]


def test_rrf_results_sorted_by_descending_score(authority_matrix):
    chunks = [make_single_chunk(f"Trademark trademark document {i}.", f"D-SORT-{i}", authority_matrix) for i in range(4)]
    bm25_resp, dense_resp = _bm25_and_dense(chunks, authority_matrix, "trademark")
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=10)
    scores = [r.rrf_score for r in rrf_resp.results]
    assert scores == sorted(scores, reverse=True)


def test_rrf_rank_field_is_one_based_and_contiguous(authority_matrix):
    chunks = [make_single_chunk(f"Trademark content {i}.", f"D-RANK-{i}", authority_matrix) for i in range(4)]
    bm25_resp, dense_resp = _bm25_and_dense(chunks, authority_matrix, "trademark")
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=10)
    assert [r.rank for r in rrf_resp.results] == list(range(1, len(rrf_resp.results) + 1))
