"""
Phase 5 tests: core BM25 index/query correctness - empty corpus,
single/multiple documents, repeated terms, absent terms, exact term
matching, multiple query terms.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _bm25_fixtures import make_chunks, make_single_chunk

from retrieval.index import build_index, query
from retrieval.models import Bm25Config

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. Empty corpus
# ---------------------------------------------------------------------------


def test_build_index_on_empty_corpus_succeeds():
    idx = build_index([])
    assert idx.chunk_count == 0
    assert idx.average_document_length == 0.0
    assert idx.chunk_ids == []


def test_query_on_empty_corpus_returns_no_results():
    idx = build_index([])
    resp = query(idx, "any query text", top_k=5)
    assert resp.results == []


# ---------------------------------------------------------------------------
# 2. Single-document corpus
# ---------------------------------------------------------------------------


def test_single_document_corpus_retrieves_its_own_chunk(authority_matrix):
    chunk = make_single_chunk("The trademark office processes applications.", "D-SINGLE", authority_matrix)
    idx = build_index([chunk])
    resp = query(idx, "trademark applications", top_k=5)
    assert len(resp.results) == 1
    assert resp.results[0].chunk_id == chunk.chunk_id
    assert resp.results[0].score > 0.0


# ---------------------------------------------------------------------------
# 3. Multiple documents
# ---------------------------------------------------------------------------


def test_multiple_documents_rank_by_relevance(authority_matrix):
    c1 = make_single_chunk("Trademark registration requires an application to the registry.", "D1", authority_matrix)
    c2 = make_single_chunk("Patent filing requires a technical specification document.", "D2", authority_matrix)
    c3 = make_single_chunk("Ayurveda formulation must follow AYUSH ministry rules.", "D3", authority_matrix)
    idx = build_index([c1, c2, c3])
    resp = query(idx, "trademark registration application", top_k=3)
    assert resp.results[0].chunk_id == c1.chunk_id
    assert all(r.chunk_id != c3.chunk_id or r.score < resp.results[0].score for r in resp.results)


# ---------------------------------------------------------------------------
# 4. Repeated terms (term frequency)
# ---------------------------------------------------------------------------


def test_repeated_query_term_in_document_increases_score(authority_matrix):
    low = make_single_chunk("Formulation details are described once.", "D-LOW", authority_matrix)
    high = make_single_chunk(
        "Formulation formulation formulation formulation details repeated many times.", "D-HIGH", authority_matrix
    )
    idx = build_index([low, high])
    resp = query(idx, "formulation", top_k=2)
    scores = {r.chunk_id: r.score for r in resp.results}
    assert scores[high.chunk_id] > scores[low.chunk_id]


# ---------------------------------------------------------------------------
# 5. Absent terms
# ---------------------------------------------------------------------------


def test_query_term_absent_from_corpus_yields_no_results(authority_matrix):
    chunk = make_single_chunk("Some unrelated regulatory text about licensing.", "D-ABSENT", authority_matrix)
    idx = build_index([chunk])
    resp = query(idx, "zzznonexistentqueryterm", top_k=5)
    assert resp.results == []


def test_one_absent_term_among_several_does_not_break_scoring(authority_matrix):
    chunk = make_single_chunk("Trademark applications are examined by the registry.", "D-PARTIAL", authority_matrix)
    idx = build_index([chunk])
    resp = query(idx, "trademark zzznonexistentqueryterm", top_k=5)
    assert len(resp.results) == 1
    assert resp.results[0].score > 0.0


# ---------------------------------------------------------------------------
# 6. Exact term matching
# ---------------------------------------------------------------------------


def test_exact_single_term_match_retrieves_correct_chunk(authority_matrix):
    a = make_single_chunk("Patent claims must be novel and non-obvious.", "D-PATENT", authority_matrix)
    b = make_single_chunk("Copyright protects original literary works.", "D-COPYRIGHT", authority_matrix)
    idx = build_index([a, b])
    resp = query(idx, "patent", top_k=5)
    assert [r.chunk_id for r in resp.results] == [a.chunk_id]


# ---------------------------------------------------------------------------
# 7. Multiple query terms
# ---------------------------------------------------------------------------


def test_multi_term_query_scores_chunk_matching_more_terms_higher(authority_matrix):
    both = make_single_chunk("Trademark registration and patent filing are both regulated.", "D-BOTH", authority_matrix)
    one = make_single_chunk("Trademark registration is handled by the registry office.", "D-ONE", authority_matrix)
    idx = build_index([both, one])
    resp = query(idx, "trademark patent", top_k=2)
    scores = {r.chunk_id: r.score for r in resp.results}
    assert scores[both.chunk_id] > scores[one.chunk_id]


def test_build_index_uses_default_bm25_config_when_omitted(authority_matrix):
    chunk = make_single_chunk("Default configuration text sample.", "D-DEFAULT", authority_matrix)
    idx = build_index([chunk])
    assert idx.config.k1 == 1.5
    assert idx.config.b == 0.75


def test_build_index_accepts_explicit_bm25_config(authority_matrix):
    chunk = make_single_chunk("Custom configuration text sample.", "D-CUSTOM", authority_matrix)
    idx = build_index([chunk], config=Bm25Config(k1=2.0, b=0.5))
    assert idx.config.k1 == 2.0
    assert idx.config.b == 0.5
