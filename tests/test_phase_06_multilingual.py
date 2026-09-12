"""
Phase 6 tests: multilingual Unicode plumbing - English, Devanagari, Tamil,
mixed-script text (docs/PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md Section P).

IMPORTANT: these tests use FakeEmbeddingModel, which has NO real semantic
understanding. They prove the dense-retrieval *plumbing* (index build,
query, provenance, ranking) handles multilingual Unicode correctly - they
are NOT a claim of real multilingual retrieval quality. See
docs/PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md Section P/X for the explicit
distinction and what was NOT validated.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _dense_fixtures import make_fake_model, make_single_chunk

from retrieval.faiss_index import build_dense_index, dense_query

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# English
# ---------------------------------------------------------------------------


def test_english_query_and_corpus_round_trip(authority_matrix):
    chunk = make_single_chunk("Trademark registration application process.", "D-EN", authority_matrix)
    model = make_fake_model()
    idx = build_dense_index([chunk], model)
    resp = dense_query(idx, model, "trademark registration", top_k=1)
    assert resp.results[0].chunk_id == chunk.chunk_id


# ---------------------------------------------------------------------------
# Devanagari
# ---------------------------------------------------------------------------


def test_devanagari_query_and_corpus_round_trip(authority_matrix):
    chunk = make_single_chunk(
        "आयुर्वेद औषधि पंजीकरण के लिए आवेदन आवश्यक है", "D-HI", authority_matrix
    )
    model = make_fake_model()
    idx = build_dense_index([chunk], model)
    resp = dense_query(idx, model, "औषधि पंजीकरण", top_k=1)
    assert resp.results[0].chunk_id == chunk.chunk_id
    assert resp.results[0].chunk_text == chunk.text  # verbatim, unmodified


def test_devanagari_documents_are_distinguishable_by_content(authority_matrix):
    a = make_single_chunk("आयुर्वेद औषधि पंजीकरण नियम", "D-HI-A", authority_matrix)
    b = make_single_chunk("पेटेंट आवेदन तकनीकी विवरण", "D-HI-B", authority_matrix)
    model = make_fake_model(dimension=64)
    idx = build_dense_index([a, b], model)
    resp = dense_query(idx, model, "आयुर्वेद औषधि पंजीकरण", top_k=2)
    assert resp.results[0].chunk_id == a.chunk_id


# ---------------------------------------------------------------------------
# Tamil
# ---------------------------------------------------------------------------


def test_tamil_query_and_corpus_round_trip(authority_matrix):
    chunk = make_single_chunk("மருந்து பதிவு விண்ணப்பம் தேவை", "D-TA", authority_matrix)
    model = make_fake_model()
    idx = build_dense_index([chunk], model)
    resp = dense_query(idx, model, "மருந்து பதிவு", top_k=1)
    assert resp.results[0].chunk_id == chunk.chunk_id


def test_tamil_documents_are_distinguishable_by_content(authority_matrix):
    a = make_single_chunk("மருந்து பதிவு விதிமுறைகள்", "D-TA-A", authority_matrix)
    b = make_single_chunk("காப்புரிமை விண்ணப்ப நடைமுறை", "D-TA-B", authority_matrix)
    model = make_fake_model(dimension=64)
    idx = build_dense_index([a, b], model)
    resp = dense_query(idx, model, "மருந்து பதிவு", top_k=2)
    assert resp.results[0].chunk_id == a.chunk_id


# ---------------------------------------------------------------------------
# Mixed-script
# ---------------------------------------------------------------------------


def test_mixed_script_query_matches_mixed_script_document(authority_matrix):
    chunk = make_single_chunk(
        "Ayurveda आयुर्वेद மருந்து registration requires an application.", "D-MIXED", authority_matrix
    )
    model = make_fake_model()
    idx = build_dense_index([chunk], model)
    resp = dense_query(idx, model, "Ayurveda आयुर्वेद மருந்து", top_k=1)
    assert resp.results[0].chunk_id == chunk.chunk_id


def test_mixed_script_corpus_all_indexed_and_retrievable(authority_matrix):
    docs = [
        ("D-MX-1", "English only trademark content here."),
        ("D-MX-2", "केवल हिंदी सामग्री यहाँ पंजीकरण के बारे में है"),
        ("D-MX-3", "தமிழ் மொழி மட்டும் உள்ளடக்கம் இங்கே பதிவு பற்றியது"),
        ("D-MX-4", "Mixed English आयुर्वेद மருந்து content together."),
    ]
    chunks = [make_single_chunk(text, doc_id, authority_matrix) for doc_id, text in docs]
    model = make_fake_model(dimension=32)
    idx = build_dense_index(chunks, model)
    assert idx.chunk_count == 4
    resp = dense_query(idx, model, "registration பதிவு पंजीकरण", top_k=4)
    assert len(resp.results) == 4
    retrieved_ids = {r.chunk_id for r in resp.results}
    assert retrieved_ids == {c.chunk_id for c in chunks}


def test_multilingual_provenance_preserved_across_scripts(authority_matrix):
    chunk = make_single_chunk(
        "आयुर्वेद पंजीकरण", "D-MULTI-PROV", authority_matrix, source_family_id="SF-04", jurisdiction="INDIA"
    )
    model = make_fake_model()
    idx = build_dense_index([chunk], model)
    resp = dense_query(idx, model, "पंजीकरण", top_k=1)
    result = resp.results[0]
    assert result.document_id == "D-MULTI-PROV"
    assert result.source_family_id == "SF-04"
    assert result.jurisdiction == "INDIA"
    assert result.block_ids == chunk.block_ids
