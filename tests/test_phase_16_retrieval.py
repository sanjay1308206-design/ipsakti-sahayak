"""
Phase 16 tests: unified retrieval evaluation interface over Phase 5/6/7's
real BM25/dense/RRF/reranker pipeline (docs/PHASE_16_EVALUATION_AND_RED_TEAM.md
Sections H, I, J, K). Reuses the exact same synthetic corpus/query/
relevance protocol as tests/test_phase_07_evaluation.py (comparison
fairness) - this file does not reimplement retrieval or its metrics, it
only wraps the real calls into a Phase 16 ComponentBenchmarkReport.

BGE-M3/bge-reranker-v2-m3 REAL-MODEL QUALITY IS NOT VALIDATED anywhere in
this file - only FakeEmbeddingModel/FakeReranker are used, exactly like
Phase 6/7's own disclosed limitation.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _hybrid_fixtures import make_fake_model, make_fake_reranker, make_single_chunk

from evaluation.benchmark import score_retrieval_condition
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
def corpus(authority_matrix):
    fixtures = [
        ("SYNTHETIC-BENCH-16-TM-1", "Trademark registration requires filing an application with the trademark registry."),
        ("SYNTHETIC-BENCH-16-TM-2", "The trademark registry processes each registration application for distinctiveness review."),
        ("SYNTHETIC-BENCH-16-PT-1", "Patent applications require a complete technical specification of the invention."),
        ("SYNTHETIC-BENCH-16-PT-2", "Patent examiners assess novelty and inventive step during examination."),
        ("SYNTHETIC-BENCH-16-AY-1", "Ayurveda formulation registration follows AYUSH ministry compliance rules."),
        ("SYNTHETIC-BENCH-16-IRRELEVANT", "Weather patterns and rainfall data for agricultural planning purposes."),
    ]
    chunks = {doc_id: make_single_chunk(text, doc_id, authority_matrix) for doc_id, text in fixtures}
    bm25_index = build_index(list(chunks.values()))
    model = make_fake_model(dimension=64)
    dense_index = build_dense_index(list(chunks.values()), model)
    reranker = make_fake_reranker()
    return chunks, bm25_index, dense_index, model, reranker


BENCHMARK_QUERIES = [
    ("trademark registration", {"SYNTHETIC-BENCH-16-TM-1", "SYNTHETIC-BENCH-16-TM-2"}),
    ("patent examination novelty", {"SYNTHETIC-BENCH-16-PT-2"}),
    ("ayurveda formulation compliance", {"SYNTHETIC-BENCH-16-AY-1"}),
]


def _relevant_ids(chunks, doc_ids):
    return {chunks[doc_id].chunk_id for doc_id in doc_ids}


def _bm25_results(corpus):
    chunks, bm25_index, dense_index, model, reranker = corpus
    out = []
    for query_text, relevant_docs in BENCHMARK_QUERIES:
        resp = bm25_query(bm25_index, query_text, top_k=6)
        out.append((query_text, [r.chunk_id for r in resp.results], _relevant_ids(chunks, relevant_docs)))
    return out


def _dense_results(corpus):
    chunks, bm25_index, dense_index, model, reranker = corpus
    out = []
    for query_text, relevant_docs in BENCHMARK_QUERIES:
        resp = dense_query(dense_index, model, query_text, top_k=6)
        out.append((query_text, [r.chunk_id for r in resp.results], _relevant_ids(chunks, relevant_docs)))
    return out


def _rrf_results(corpus):
    chunks, bm25_index, dense_index, model, reranker = corpus
    out = []
    for query_text, relevant_docs in BENCHMARK_QUERIES:
        bm25_resp = bm25_query(bm25_index, query_text, top_k=6)
        dense_resp = dense_query(dense_index, model, query_text, top_k=6)
        rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=6)
        out.append((query_text, [r.chunk_id for r in rrf_resp.results], _relevant_ids(chunks, relevant_docs)))
    return out


def _reranked_results(corpus):
    chunks, bm25_index, dense_index, model, reranker = corpus
    out = []
    for query_text, relevant_docs in BENCHMARK_QUERIES:
        bm25_resp = bm25_query(bm25_index, query_text, top_k=6)
        dense_resp = dense_query(dense_index, model, query_text, top_k=6)
        rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=6)
        hybrid_resp = rerank_candidates(rrf_resp, reranker, top_k=6)
        out.append((query_text, [r.chunk_id for r in hybrid_resp.results], _relevant_ids(chunks, relevant_docs)))
    return out


def test_bm25_retrieval_report(corpus):
    report = score_retrieval_condition("BM25_RETRIEVAL", _bm25_results(corpus), CUTOFF_K)
    assert report.component == "BM25_RETRIEVAL"
    metrics = {r.metric_name: r for r in report.results}
    assert metrics[f"PRECISION_AT_{CUTOFF_K}"].applicable is True
    assert 0.0 <= metrics[f"RECALL_AT_{CUTOFF_K}"].value <= 1.0
    assert metrics["REAL_MODEL_RETRIEVAL_QUALITY"].applicable is False


def test_dense_retrieval_report_discloses_bge_m3_not_validated(corpus):
    report = score_retrieval_condition(
        "DENSE_RETRIEVAL", _dense_results(corpus), CUTOFF_K,
        real_model_validated=False, not_validated_reason="BGE-M3 real-model quality is not validated - FakeEmbeddingModel was used",
    )
    metrics = {r.metric_name: r for r in report.results}
    assert "BGE-M3" in metrics["REAL_MODEL_RETRIEVAL_QUALITY"].explanation


def test_hybrid_rrf_retrieval_report(corpus):
    report = score_retrieval_condition("HYBRID_RRF_RETRIEVAL", _rrf_results(corpus), CUTOFF_K)
    metrics = {r.metric_name: r for r in report.results}
    assert metrics["MEAN_RECIPROCAL_RANK"].applicable is True


def test_reranked_retrieval_report(corpus):
    report = score_retrieval_condition("RERANKED_RETRIEVAL", _reranked_results(corpus), CUTOFF_K)
    metrics = {r.metric_name: r for r in report.results}
    assert metrics[f"PRECISION_AT_{CUTOFF_K}"].applicable is True


def test_four_way_comparison_does_not_claim_unmeasured_improvement(corpus):
    """
    Mirrors test_phase_07_evaluation.py's own four-way comparison, wrapped
    through Phase 16's reporting layer - no assertion here claims RRF or
    reranking improves over BM25 unless the numbers actually show it.
    """
    reports = {
        "BM25_RETRIEVAL": score_retrieval_condition("BM25_RETRIEVAL", _bm25_results(corpus), CUTOFF_K),
        "DENSE_RETRIEVAL": score_retrieval_condition("DENSE_RETRIEVAL", _dense_results(corpus), CUTOFF_K),
        "HYBRID_RRF_RETRIEVAL": score_retrieval_condition("HYBRID_RRF_RETRIEVAL", _rrf_results(corpus), CUTOFF_K),
        "RERANKED_RETRIEVAL": score_retrieval_condition("RERANKED_RETRIEVAL", _reranked_results(corpus), CUTOFF_K),
    }
    for name, report in reports.items():
        recall = next(r for r in report.results if r.metric_name == f"RECALL_AT_{CUTOFF_K}")
        assert recall.applicable and recall.value > 0.0, f"{name} found zero relevant results"


def test_empty_query_set_is_not_applicable():
    report = score_retrieval_condition("BM25_RETRIEVAL", [], CUTOFF_K)
    for result in report.results:
        if result.metric_name.startswith(("PRECISION", "RECALL", "MEAN")):
            assert result.applicable is False
