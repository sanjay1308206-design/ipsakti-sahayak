"""
Phase 7 tests: the synthetic four-way benchmark - BM25 alone, dense alone,
RRF hybrid, RRF + reranking (docs/PHASE_07_HYBRID_FUSION_AND_RERANKING.md
Section T/U).

The benchmark below is fully synthetic (SYNTHETIC-BENCH-07-* document IDs,
synthetic=True throughout) and, since it runs against FakeEmbeddingModel/
FakeReranker, measures the ENGINEERING correctness of the four pipeline
stages - it makes no claim whatsoever about real regulatory retrieval
quality (docs Section U/W, docs/DEVELOPMENT_RULES.md Rule 7).

Same query set, same relevance judgments, same chunk set, same evaluation
protocol, same cutoff K are used across all four conditions (comparison
fairness).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _hybrid_fixtures import make_fake_model, make_fake_reranker, make_single_chunk

from retrieval.evaluation import mean_reciprocal_rank, precision_at_k, recall_at_k
from retrieval.faiss_index import build_dense_index, dense_query
from retrieval.hybrid import rerank_candidates
from retrieval.index import build_index, query as bm25_query
from retrieval.rrf import fuse_rrf

REPO_ROOT = Path(__file__).resolve().parent.parent

CUTOFF_K = 3


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def benchmark_setup(authority_matrix):
    fixtures = [
        ("SYNTHETIC-BENCH-07-TM-1", "Trademark registration requires filing an application with the trademark registry."),
        ("SYNTHETIC-BENCH-07-TM-2", "The trademark registry processes each registration application for distinctiveness review."),
        ("SYNTHETIC-BENCH-07-PT-1", "Patent applications require a complete technical specification of the invention."),
        ("SYNTHETIC-BENCH-07-PT-2", "Patent examiners assess novelty and inventive step during examination."),
        ("SYNTHETIC-BENCH-07-AY-1", "Ayurveda formulation registration follows AYUSH ministry compliance rules."),
        ("SYNTHETIC-BENCH-07-IRRELEVANT", "Weather patterns and rainfall data for agricultural planning purposes."),
    ]
    chunks = {doc_id: make_single_chunk(text, doc_id, authority_matrix) for doc_id, text in fixtures}
    bm25_index = build_index(list(chunks.values()))
    model = make_fake_model(dimension=64)
    dense_index = build_dense_index(list(chunks.values()), model)
    reranker = make_fake_reranker()
    return chunks, bm25_index, dense_index, model, reranker


# Same query set + relevance judgments reused across A/B/C/D (comparison fairness).
BENCHMARK_QUERIES = [
    ("trademark registration", {"SYNTHETIC-BENCH-07-TM-1", "SYNTHETIC-BENCH-07-TM-2"}),
    ("patent examination novelty", {"SYNTHETIC-BENCH-07-PT-2"}),
    ("ayurveda formulation compliance", {"SYNTHETIC-BENCH-07-AY-1"}),
]


def _relevant_ids(chunks, doc_ids):
    return {chunks[doc_id].chunk_id for doc_id in doc_ids}


def _condition_a_bm25(benchmark_setup, query_text, k):
    chunks, bm25_index, dense_index, model, reranker = benchmark_setup
    resp = bm25_query(bm25_index, query_text, top_k=6)
    return [r.chunk_id for r in resp.results]


def _condition_b_dense(benchmark_setup, query_text, k):
    chunks, bm25_index, dense_index, model, reranker = benchmark_setup
    resp = dense_query(dense_index, model, query_text, top_k=6)
    return [r.chunk_id for r in resp.results]


def _condition_c_rrf(benchmark_setup, query_text, k):
    chunks, bm25_index, dense_index, model, reranker = benchmark_setup
    bm25_resp = bm25_query(bm25_index, query_text, top_k=6)
    dense_resp = dense_query(dense_index, model, query_text, top_k=6)
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=6)
    return [r.chunk_id for r in rrf_resp.results]


def _condition_d_rrf_plus_reranker(benchmark_setup, query_text, k):
    chunks, bm25_index, dense_index, model, reranker = benchmark_setup
    bm25_resp = bm25_query(bm25_index, query_text, top_k=6)
    dense_resp = dense_query(dense_index, model, query_text, top_k=6)
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=6)
    hybrid_resp = rerank_candidates(rrf_resp, reranker, top_k=6)
    return [r.chunk_id for r in hybrid_resp.results]


@pytest.mark.parametrize(
    "condition_fn",
    [_condition_a_bm25, _condition_b_dense, _condition_c_rrf, _condition_d_rrf_plus_reranker],
    ids=["A_bm25", "B_dense", "C_rrf", "D_rrf_plus_reranker"],
)
def test_all_four_conditions_find_exact_term_relevant_chunks(benchmark_setup, condition_fn):
    chunks = benchmark_setup[0]
    relevant = _relevant_ids(chunks, {"SYNTHETIC-BENCH-07-TM-1", "SYNTHETIC-BENCH-07-TM-2"})
    retrieved = condition_fn(benchmark_setup, "trademark registration", CUTOFF_K)
    assert recall_at_k(retrieved, relevant, k=CUTOFF_K) > 0.0


def test_four_way_comparison_uses_identical_query_set_relevance_and_cutoff(benchmark_setup):
    """
    Computes Precision@K/Recall@K/MRR for all four conditions over the SAME
    BENCHMARK_QUERIES/relevance/cutoff - this is the actual "does hybrid
    fusion improve retrieval / does reranking improve RRF" measurement.
    No number here is fabricated; whatever direction the assertions below
    do NOT make a claim about is left unclaimed (Section U: implementation
    benchmark only, not a real regulatory benchmark).
    """
    chunks = benchmark_setup[0]
    conditions = {
        "A_bm25": _condition_a_bm25,
        "B_dense": _condition_b_dense,
        "C_rrf": _condition_c_rrf,
        "D_rrf_plus_reranker": _condition_d_rrf_plus_reranker,
    }

    results = {}
    for name, fn in conditions.items():
        per_query = []
        for query_text, relevant_doc_ids in BENCHMARK_QUERIES:
            relevant = _relevant_ids(chunks, relevant_doc_ids)
            retrieved = fn(benchmark_setup, query_text, CUTOFF_K)
            per_query.append((retrieved, relevant))
        precision = sum(precision_at_k(r, rel, CUTOFF_K) for r, rel in per_query) / len(per_query)
        recall = sum(recall_at_k(r, rel, CUTOFF_K) for r, rel in per_query) / len(per_query)
        mrr = mean_reciprocal_rank(per_query)
        results[name] = {"precision": precision, "recall": recall, "mrr": mrr}

    # Every condition must be measurable (no crash, no missing metric) -
    # this is what "the benchmark makes comparison possible" actually means.
    for name, metrics in results.items():
        assert 0.0 <= metrics["precision"] <= 1.0
        assert 0.0 <= metrics["recall"] <= 1.0
        assert 0.0 <= metrics["mrr"] <= 1.0

    # On this easy, exact-term-heavy synthetic set, every condition should
    # find at least some relevant material - proving the four-way
    # comparison itself is meaningful, not that any one method "wins".
    for name, metrics in results.items():
        assert metrics["recall"] > 0.0, f"condition {name} found zero relevant results across the benchmark"


def test_reranking_never_drops_a_relevant_candidate_that_rrf_already_surfaced(benchmark_setup):
    chunks = benchmark_setup[0]
    relevant = _relevant_ids(chunks, {"SYNTHETIC-BENCH-07-TM-1", "SYNTHETIC-BENCH-07-TM-2"})
    rrf_retrieved = _condition_c_rrf(benchmark_setup, "trademark registration", CUTOFF_K)
    reranked_retrieved = _condition_d_rrf_plus_reranker(benchmark_setup, "trademark registration", CUTOFF_K)
    # reranking reorders the SAME candidate_k=6 set - the full set of chunk_ids must be identical
    assert set(rrf_retrieved) == set(reranked_retrieved)


def test_benchmark_is_not_cherry_picked_runs_the_full_query_set(benchmark_setup):
    # Sanity: BENCHMARK_QUERIES covers more than one topic/relevance set,
    # not a single hand-picked easy case.
    assert len(BENCHMARK_QUERIES) >= 3
    topics = {frozenset(relevant) for _, relevant in BENCHMARK_QUERIES}
    assert len(topics) == len(BENCHMARK_QUERIES)  # each query has a distinct relevance set
