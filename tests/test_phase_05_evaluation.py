"""
Phase 5 tests: the synthetic BM25 evaluation benchmark
(docs/PHASE_05_BM25_BASELINE.md Section P).

The benchmark below is fully synthetic (SYNTHETIC-BENCH-* document IDs,
synthetic=True throughout) and measures the ENGINEERING correctness of the
BM25 baseline implementation - it makes no claim whatsoever about real
regulatory retrieval quality (docs/DEVELOPMENT_RULES.md Rule 7).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _bm25_fixtures import make_single_chunk

from retrieval.evaluation import precision_at_k, recall_at_k
from retrieval.index import build_index, query

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Pure metric-function unit tests
# ---------------------------------------------------------------------------


def test_precision_at_k_all_relevant():
    assert precision_at_k(["a", "b", "c"], {"a", "b", "c"}, k=3) == 1.0


def test_precision_at_k_partial_relevant():
    assert precision_at_k(["a", "b", "c", "d"], {"a", "c"}, k=4) == 0.5


def test_precision_at_k_none_relevant():
    assert precision_at_k(["x", "y"], {"a", "b"}, k=2) == 0.0


def test_precision_at_k_zero_k():
    assert precision_at_k(["a", "b"], {"a"}, k=0) == 0.0


def test_recall_at_k_finds_all_relevant():
    assert recall_at_k(["a", "b", "c"], {"a", "c"}, k=3) == 1.0


def test_recall_at_k_partial():
    assert recall_at_k(["a"], {"a", "b"}, k=1) == 0.5


def test_recall_at_k_no_relevant_documents_known():
    assert recall_at_k(["a", "b"], set(), k=2) == 0.0


def test_recall_at_k_beyond_retrieved_list_length():
    assert recall_at_k(["a"], {"a", "b"}, k=10) == 0.5


# ---------------------------------------------------------------------------
# Synthetic benchmark: a small, fully known-relevance corpus
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def benchmark_index(authority_matrix):
    fixtures = [
        ("SYNTHETIC-BENCH-TM-1", "Trademark registration requires filing an application with the trademark registry."),
        ("SYNTHETIC-BENCH-TM-2", "The trademark registry processes each registration application for distinctiveness review."),
        ("SYNTHETIC-BENCH-PT-1", "Patent applications require a complete technical specification of the invention."),
        ("SYNTHETIC-BENCH-PT-2", "Patent examiners assess novelty and inventive step during examination."),
        ("SYNTHETIC-BENCH-AY-1", "Ayurveda formulation registration follows AYUSH ministry compliance rules."),
        ("SYNTHETIC-BENCH-IRRELEVANT", "Weather patterns and rainfall data for agricultural planning purposes."),
    ]
    chunks = {
        doc_id: make_single_chunk(text, doc_id, authority_matrix) for doc_id, text in fixtures
    }
    index = build_index(list(chunks.values()))
    return index, chunks


def test_benchmark_exact_term_retrieval_finds_all_relevant_chunks(benchmark_index):
    index, chunks = benchmark_index
    relevant = {chunks["SYNTHETIC-BENCH-TM-1"].chunk_id, chunks["SYNTHETIC-BENCH-TM-2"].chunk_id}
    resp = query(index, "trademark registration", top_k=6)
    retrieved = [r.chunk_id for r in resp.results]
    assert precision_at_k(retrieved, relevant, k=2) == 1.0
    assert recall_at_k(retrieved, relevant, k=2) == 1.0


def test_benchmark_partial_term_retrieval_ranks_stronger_match_first(benchmark_index):
    index, chunks = benchmark_index
    resp = query(index, "patent examination", top_k=6)
    retrieved = [r.chunk_id for r in resp.results]
    assert retrieved[0] == chunks["SYNTHETIC-BENCH-PT-2"].chunk_id  # matches both "patent" and "examin-"


def test_benchmark_irrelevant_chunk_is_never_retrieved_for_ip_queries(benchmark_index):
    index, chunks = benchmark_index
    resp = query(index, "trademark patent ayurveda formulation registration", top_k=6)
    retrieved = [r.chunk_id for r in resp.results]
    assert chunks["SYNTHETIC-BENCH-IRRELEVANT"].chunk_id not in retrieved


def test_benchmark_multilingual_unicode_matching(authority_matrix):
    devanagari_chunk = make_single_chunk(
        "आयुर्वेद औषधि पंजीकरण के लिए आवेदन आवश्यक है", "SYNTHETIC-BENCH-HI-1", authority_matrix
    )
    unrelated_chunk = make_single_chunk(
        "पेटेंट आवेदन के लिए तकनीकी विवरण आवश्यक है", "SYNTHETIC-BENCH-HI-2", authority_matrix
    )
    index = build_index([devanagari_chunk, unrelated_chunk])
    resp = query(index, "औषधि पंजीकरण", top_k=2)
    retrieved = [r.chunk_id for r in resp.results]
    assert retrieved[0] == devanagari_chunk.chunk_id


def test_benchmark_top_k_limits_result_count(benchmark_index):
    index, _ = benchmark_index
    resp = query(index, "registration application", top_k=1)
    assert len(resp.results) == 1


def test_benchmark_metrics_are_computed_correctly_end_to_end(benchmark_index):
    index, chunks = benchmark_index
    relevant = {chunks["SYNTHETIC-BENCH-TM-1"].chunk_id, chunks["SYNTHETIC-BENCH-TM-2"].chunk_id}
    resp = query(index, "trademark registration application", top_k=3)
    retrieved = [r.chunk_id for r in resp.results]
    precision = precision_at_k(retrieved, relevant, k=3)
    recall = recall_at_k(retrieved, relevant, k=3)
    # Both TM chunks should be in the top 3 of a 6-document corpus for this query.
    assert recall == 1.0
    assert precision == pytest.approx(2 / 3)
