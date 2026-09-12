"""
Phase 7 tests: multilingual Unicode plumbing through the full hybrid
pipeline - English, Devanagari, Tamil, mixed-script
(docs/PHASE_07_HYBRID_FUSION_AND_RERANKING.md Section S).

IMPORTANT: these tests use FakeEmbeddingModel and FakeReranker, neither of
which has real semantic/cross-encoder understanding. They prove pipeline
*plumbing* correctness only - NOT a claim of real multilingual retrieval
or reranking quality.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _hybrid_fixtures import make_fake_model, make_fake_reranker, make_single_chunk

from retrieval.faiss_index import build_dense_index, dense_query
from retrieval.hybrid import run_hybrid_pipeline
from retrieval.index import build_index, query as bm25_query
from retrieval.rrf import fuse_rrf

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def test_english_query_through_full_pipeline(authority_matrix):
    chunk = make_single_chunk("Trademark registration application process.", "D-EN", authority_matrix)
    bm25_index = build_index([chunk])
    model = make_fake_model()
    dense_index = build_dense_index([chunk], model)
    reranker = make_fake_reranker()

    hybrid_resp = run_hybrid_pipeline(
        bm25_index, dense_index, model, reranker, "trademark registration",
        bm25_top_k=1, dense_top_k=1, candidate_k=1, reranker_top_k=1,
    )
    assert hybrid_resp.results[0].chunk_id == chunk.chunk_id


def test_devanagari_query_through_full_pipeline(authority_matrix):
    chunk = make_single_chunk("आयुर्वेद औषधि पंजीकरण के लिए आवेदन आवश्यक है", "D-HI", authority_matrix)
    bm25_index = build_index([chunk])
    model = make_fake_model()
    dense_index = build_dense_index([chunk], model)
    reranker = make_fake_reranker()

    hybrid_resp = run_hybrid_pipeline(
        bm25_index, dense_index, model, reranker, "औषधि पंजीकरण",
        bm25_top_k=1, dense_top_k=1, candidate_k=1, reranker_top_k=1,
    )
    assert hybrid_resp.results[0].chunk_id == chunk.chunk_id
    assert hybrid_resp.results[0].chunk_text == chunk.text


def test_tamil_query_through_full_pipeline(authority_matrix):
    chunk = make_single_chunk("மருந்து பதிவு விண்ணப்பம் தேவை", "D-TA", authority_matrix)
    bm25_index = build_index([chunk])
    model = make_fake_model()
    dense_index = build_dense_index([chunk], model)
    reranker = make_fake_reranker()

    hybrid_resp = run_hybrid_pipeline(
        bm25_index, dense_index, model, reranker, "மருந்து பதிவு",
        bm25_top_k=1, dense_top_k=1, candidate_k=1, reranker_top_k=1,
    )
    assert hybrid_resp.results[0].chunk_id == chunk.chunk_id


def test_mixed_script_query_through_full_pipeline(authority_matrix):
    chunk = make_single_chunk(
        "Ayurveda आयुर्वेद மருந்து registration requires an application.", "D-MIXED", authority_matrix
    )
    bm25_index = build_index([chunk])
    model = make_fake_model()
    dense_index = build_dense_index([chunk], model)
    reranker = make_fake_reranker()

    hybrid_resp = run_hybrid_pipeline(
        bm25_index, dense_index, model, reranker, "Ayurveda आयुर्वेद மருந்து",
        bm25_top_k=1, dense_top_k=1, candidate_k=1, reranker_top_k=1,
    )
    assert hybrid_resp.results[0].chunk_id == chunk.chunk_id


def test_multilingual_corpus_all_stages_preserve_provenance(authority_matrix):
    docs = [
        ("D-MX-1", "English only trademark content here."),
        ("D-MX-2", "केवल हिंदी सामग्री यहाँ पंजीकरण के बारे में है"),
        ("D-MX-3", "தமிழ் மொழி மட்டும் உள்ளடக்கம் இங்கே பதிவு பற்றியது"),
        ("D-MX-4", "Mixed English आयुर्वेद மருந்து content together."),
    ]
    chunks = [make_single_chunk(text, doc_id, authority_matrix) for doc_id, text in docs]
    bm25_index = build_index(chunks)
    model = make_fake_model(dimension=32)
    dense_index = build_dense_index(chunks, model)
    reranker = make_fake_reranker()

    bm25_resp = bm25_query(bm25_index, "registration பதிவு पंजीकरण", top_k=4)
    dense_resp = dense_query(dense_index, model, "registration பதிவு पंजीकरण", top_k=4)
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=4)

    real_ids = {c.chunk_id for c in chunks}
    for r in rrf_resp.results:
        assert r.chunk_id in real_ids
        assert r.block_ids
        assert r.page_numbers

    hybrid_resp = run_hybrid_pipeline(
        bm25_index, dense_index, model, reranker, "registration பதிவு पंजीकरण",
        bm25_top_k=4, dense_top_k=4, candidate_k=4, reranker_top_k=4,
    )
    for r in hybrid_resp.results:
        assert r.chunk_id in real_ids
        assert r.block_ids
        assert r.page_numbers
