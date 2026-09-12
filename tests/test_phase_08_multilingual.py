"""
Phase 8 tests: multilingual evidence text preservation - English,
Devanagari, Tamil, mixed-script (docs/PHASE_08_EVIDENCE_OBJECT_AND_CITATION_ARCHITECTURE.md
Section AA). Evidence text must never be normalized/rewritten in a way
that changes the original source representation.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _evidence_fixtures import make_hybrid_response, make_single_chunk

from evidence.builder import build_evidence_pack
from evidence.serialize import evidence_pack_from_dict, evidence_pack_to_dict

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def test_english_evidence_text_preserved_exactly(authority_matrix):
    text = "Trademark registration application process must be followed exactly."
    chunk = make_single_chunk(text, "D-EN", authority_matrix)
    resp = make_hybrid_response([chunk], "trademark registration", top_k=1)
    pack = build_evidence_pack(resp.results, "trademark registration")
    assert pack.evidence_items[0].evidence_text == text


def test_devanagari_evidence_text_preserved_exactly(authority_matrix):
    text = "आयुर्वेद औषधि पंजीकरण के लिए आवेदन आवश्यक है"
    chunk = make_single_chunk(text, "D-HI", authority_matrix)
    resp = make_hybrid_response([chunk], "औषधि पंजीकरण", top_k=1)
    pack = build_evidence_pack(resp.results, "औषधि पंजीकरण")
    assert pack.evidence_items[0].evidence_text == text


def test_tamil_evidence_text_preserved_exactly(authority_matrix):
    text = "மருந்து பதிவு விண்ணப்பம் தேவை"
    chunk = make_single_chunk(text, "D-TA", authority_matrix)
    resp = make_hybrid_response([chunk], "மருந்து பதிவு", top_k=1)
    pack = build_evidence_pack(resp.results, "மருந்து பதிவு")
    assert pack.evidence_items[0].evidence_text == text


def test_mixed_script_evidence_text_preserved_exactly(authority_matrix):
    text = "Ayurveda आयुर्वेद மருந்து registration requires an application."
    chunk = make_single_chunk(text, "D-MIXED", authority_matrix)
    resp = make_hybrid_response([chunk], "Ayurveda आयुर्वेद மருந்து", top_k=1)
    pack = build_evidence_pack(resp.results, "unrelated query string for this test")
    # note: query text intentionally slightly different from the chunk's
    # own mixed text - proving evidence_text is copied from the CANDIDATE,
    # never derived from or altered by the query.
    assert pack.evidence_items[0].evidence_text == text


def test_multilingual_evidence_text_survives_serialization_round_trip(authority_matrix):
    text = "आयुर्वेद பதிவு trademark मिश्रित content."
    chunk = make_single_chunk(text, "D-MIXED-SER", authority_matrix)
    resp = make_hybrid_response([chunk], "trademark", top_k=1)
    pack = build_evidence_pack(resp.results, "trademark")
    reloaded = evidence_pack_from_dict(evidence_pack_to_dict(pack))
    assert reloaded.evidence_items[0].evidence_text == text


def test_multilingual_evidence_ids_are_still_deterministic(authority_matrix):
    text = "நிலையான பதிவு சோதனை உள்ளடக்கம்."
    chunk = make_single_chunk(text, "D-TA-DET", authority_matrix)
    resp1 = make_hybrid_response([chunk], "பதிவு", top_k=1)
    resp2 = make_hybrid_response([chunk], "பதிவு", top_k=1)
    pack1 = build_evidence_pack(resp1.results, "பதிவு")
    pack2 = build_evidence_pack(resp2.results, "பதிவு")
    assert pack1.evidence_items[0].evidence_id == pack2.evidence_items[0].evidence_id


def test_multilingual_corpus_all_evidence_items_traceable(authority_matrix):
    docs = [
        ("D-MX-1", "English only trademark content here."),
        ("D-MX-2", "केवल हिंदी सामग्री यहाँ पंजीकरण के बारे में है"),
        ("D-MX-3", "தமிழ் மொழி மட்டும் உள்ளடக்கம் இங்கே பதிவு பற்றியது"),
        ("D-MX-4", "Mixed English आयुर्वेद மருந்து content together."),
    ]
    chunks = [make_single_chunk(text, doc_id, authority_matrix) for doc_id, text in docs]
    resp = make_hybrid_response(chunks, "registration பதிவு पंजीकरण", top_k=4)
    pack = build_evidence_pack(resp.results, "registration பதிவு पंजीकरण")

    real_chunk_ids = {c.chunk_id for c in chunks}
    for evidence in pack.evidence_items:
        assert evidence.chunk_id in real_chunk_ids
        assert evidence.block_ids
        assert evidence.page_numbers
