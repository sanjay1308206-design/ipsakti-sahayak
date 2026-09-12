"""
Phase 6 tests: the synthetic dense-retrieval evaluation benchmark
(docs/PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md Section Q), plus an
evaluation-ONLY comparison against Phase 5's BM25 baseline on the same
synthetic queries.

The benchmark below is fully synthetic (SYNTHETIC-BENCH-* document IDs,
synthetic=True throughout) and, since it runs against FakeEmbeddingModel,
measures the ENGINEERING correctness of the dense-retrieval baseline - it
makes no claim whatsoever about real (BGE-M3) multilingual semantic
retrieval quality (docs Section P/X).

This file does NOT implement, or even sketch, hybrid fusion (RRF) - it
only reports each baseline's own independent metrics side by side, which
is explicitly permitted (and Phase 7's actual fusion work is explicitly
NOT here).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _dense_fixtures import make_fake_model, make_single_chunk

from retrieval.bm25 import score_chunk  # noqa: F401 - imported only to prove Phase 5 module is untouched/importable
from retrieval.evaluation import mean_reciprocal_rank, precision_at_k, reciprocal_rank, recall_at_k
from retrieval.faiss_index import build_dense_index, dense_query
from retrieval.index import build_index, query

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Pure metric-function unit tests (reciprocal_rank/MRR are new for Phase 6)
# ---------------------------------------------------------------------------


def test_reciprocal_rank_first_result_relevant():
    assert reciprocal_rank(["a", "b", "c"], {"a"}) == 1.0


def test_reciprocal_rank_second_result_relevant():
    assert reciprocal_rank(["a", "b", "c"], {"b"}) == 0.5


def test_reciprocal_rank_no_relevant_result():
    assert reciprocal_rank(["a", "b"], {"z"}) == 0.0


def test_reciprocal_rank_empty_retrieved_list():
    assert reciprocal_rank([], {"a"}) == 0.0


def test_mean_reciprocal_rank_averages_across_queries():
    results = [
        (["a", "b"], {"a"}),  # RR = 1.0
        (["x", "y"], {"y"}),  # RR = 0.5
    ]
    assert mean_reciprocal_rank(results) == pytest.approx(0.75)


def test_mean_reciprocal_rank_empty_query_list():
    assert mean_reciprocal_rank([]) == 0.0


# ---------------------------------------------------------------------------
# Synthetic dense-retrieval benchmark: a small, fully known-relevance corpus
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def benchmark_chunks(authority_matrix):
    fixtures = [
        ("SYNTHETIC-BENCH-06-TM-1", "Trademark registration requires filing an application with the trademark registry."),
        ("SYNTHETIC-BENCH-06-TM-2", "The trademark registry processes each registration application for distinctiveness review."),
        ("SYNTHETIC-BENCH-06-PT-1", "Patent applications require a complete technical specification of the invention."),
        ("SYNTHETIC-BENCH-06-PT-2", "Patent examiners assess novelty and inventive step during examination."),
        ("SYNTHETIC-BENCH-06-AY-1", "Ayurveda formulation registration follows AYUSH ministry compliance rules."),
        ("SYNTHETIC-BENCH-06-IRRELEVANT", "Weather patterns and rainfall data for agricultural planning purposes."),
    ]
    return {doc_id: make_single_chunk(text, doc_id, authority_matrix) for doc_id, text in fixtures}


@pytest.fixture(scope="module")
def benchmark_dense_index(benchmark_chunks):
    model = make_fake_model(dimension=64)
    return build_dense_index(list(benchmark_chunks.values()), model), model


def test_benchmark_dense_exact_term_retrieval_ranks_relevant_chunks_first(benchmark_chunks, benchmark_dense_index):
    index, model = benchmark_dense_index
    relevant = {
        benchmark_chunks["SYNTHETIC-BENCH-06-TM-1"].chunk_id,
        benchmark_chunks["SYNTHETIC-BENCH-06-TM-2"].chunk_id,
    }
    resp = dense_query(index, model, "trademark registration", top_k=6)
    retrieved = [r.chunk_id for r in resp.results]
    assert precision_at_k(retrieved, relevant, k=2) == 1.0
    assert recall_at_k(retrieved, relevant, k=2) == 1.0


def test_benchmark_dense_irrelevant_chunk_ranks_lowest_for_ip_query(benchmark_chunks, benchmark_dense_index):
    index, model = benchmark_dense_index
    resp = dense_query(index, model, "trademark patent ayurveda formulation registration", top_k=6)
    retrieved = [r.chunk_id for r in resp.results]
    irrelevant_id = benchmark_chunks["SYNTHETIC-BENCH-06-IRRELEVANT"].chunk_id
    # dense retrieval always returns everything (docs Section N) - but the
    # irrelevant chunk must not outrank the actually-relevant chunks
    assert retrieved[-1] == irrelevant_id
    assert len(retrieved) == 6


def test_benchmark_dense_multilingual_matching(authority_matrix):
    devanagari_chunk = make_single_chunk(
        "आयुर्वेद औषधि पंजीकरण के लिए आवेदन आवश्यक है", "SYNTHETIC-BENCH-06-HI-1", authority_matrix
    )
    unrelated_chunk = make_single_chunk(
        "पेटेंट आवेदन के लिए तकनीकी विवरण आवश्यक है", "SYNTHETIC-BENCH-06-HI-2", authority_matrix
    )
    model = make_fake_model(dimension=64)
    index = build_dense_index([devanagari_chunk, unrelated_chunk], model)
    resp = dense_query(index, model, "औषधि पंजीकरण", top_k=2)
    retrieved = [r.chunk_id for r in resp.results]
    assert retrieved[0] == devanagari_chunk.chunk_id


def test_benchmark_dense_mrr_over_several_queries(benchmark_chunks, benchmark_dense_index):
    index, model = benchmark_dense_index
    queries = [
        ("trademark registration", {benchmark_chunks["SYNTHETIC-BENCH-06-TM-1"].chunk_id, benchmark_chunks["SYNTHETIC-BENCH-06-TM-2"].chunk_id}),
        ("patent examination", {benchmark_chunks["SYNTHETIC-BENCH-06-PT-2"].chunk_id}),
        ("ayurveda formulation", {benchmark_chunks["SYNTHETIC-BENCH-06-AY-1"].chunk_id}),
    ]
    query_results = []
    for query_text, relevant in queries:
        resp = dense_query(index, model, query_text, top_k=6)
        query_results.append(([r.chunk_id for r in resp.results], relevant))
    mrr = mean_reciprocal_rank(query_results)
    assert 0.0 < mrr <= 1.0


# ---------------------------------------------------------------------------
# Evaluation-ONLY comparison against Phase 5 BM25 (no fusion implemented)
# ---------------------------------------------------------------------------


def test_dense_and_bm25_baselines_can_be_evaluated_independently_on_the_same_corpus(benchmark_chunks, benchmark_dense_index):
    """
    Runs the exact same query through both Phase 5's BM25 index and Phase
    6's dense index and reports each baseline's own Recall@2, purely as an
    evaluation comparison. No fusion of the two result sets is computed or
    returned anywhere - that is explicitly Phase 7's job.
    """
    dense_index, dense_model = benchmark_dense_index
    bm25_index = build_index(list(benchmark_chunks.values()))

    relevant = {
        benchmark_chunks["SYNTHETIC-BENCH-06-TM-1"].chunk_id,
        benchmark_chunks["SYNTHETIC-BENCH-06-TM-2"].chunk_id,
    }

    dense_resp = dense_query(dense_index, dense_model, "trademark registration", top_k=6)
    bm25_resp = query(bm25_index, "trademark registration", top_k=6)

    dense_retrieved = [r.chunk_id for r in dense_resp.results]
    bm25_retrieved = [r.chunk_id for r in bm25_resp.results]

    dense_recall = recall_at_k(dense_retrieved, relevant, k=2)
    bm25_recall = recall_at_k(bm25_retrieved, relevant, k=2)

    # Both baselines are expected to do well on this easy exact-term query -
    # no claim that one is "better" is made; this only proves both can be
    # measured side by side without any fusion logic existing.
    assert dense_recall == 1.0
    assert bm25_recall == 1.0
