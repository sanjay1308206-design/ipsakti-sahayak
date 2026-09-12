"""
Phase 10 tests: multilingual query/evidence handling
(docs/PHASE_10_GROUNDED_GENERATION.md Section P). Unicode is preserved
correctly; no translation occurs anywhere in this phase.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _generation_fixtures import citing_provider, make_pack_from_texts

from generation.generator import generate_grounded_response
from generation.prompts import build_prompt

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def test_devanagari_query_and_evidence_ground_correctly(authority_matrix):
    pack = make_pack_from_texts([("D-ML-1", "आयुर्वेद औषधि पंजीकरण के लिए आवेदन आवश्यक है")], authority_matrix, query="पंजीकरण")
    real_id = pack.evidence_items[0].evidence_id
    response = generate_grounded_response("पंजीकरण कैसे करें?", pack, citing_provider(real_id))
    assert response.grounding_status == "GROUNDED"
    assert response.query == "पंजीकरण कैसे करें?"


def test_tamil_query_and_evidence_ground_correctly(authority_matrix):
    pack = make_pack_from_texts([("D-ML-2", "மருந்து பதிவு விண்ணப்பம் தேவை")], authority_matrix, query="பதிவு")
    real_id = pack.evidence_items[0].evidence_id
    response = generate_grounded_response("பதிவு எப்படி?", pack, citing_provider(real_id))
    assert response.grounding_status == "GROUNDED"


def test_mixed_script_evidence_text_appears_byte_faithful_in_prompt(authority_matrix):
    text = "Ayurveda आयुर्वेद மருந்து registration requires an application."
    pack = make_pack_from_texts([("D-ML-3", text)], authority_matrix)
    prompt = build_prompt("query", None, pack)
    assert text in prompt


def test_evidence_text_is_never_translated_or_normalized(authority_matrix):
    text = "केवल हिंदी सामग्री यहाँ पंजीकरण के बारे में है"
    pack = make_pack_from_texts([("D-ML-4", text)], authority_matrix)
    original_text = pack.evidence_items[0].evidence_text
    real_id = pack.evidence_items[0].evidence_id
    generate_grounded_response("q", pack, citing_provider(real_id))
    # Phase 10 must never mutate the underlying Evidence object.
    assert pack.evidence_items[0].evidence_text == original_text


def test_canonical_query_with_different_script_is_preserved(authority_matrix):
    pack = make_pack_from_texts([("D-ML-5", "Trademark content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    response = generate_grounded_response(
        "How to register a trademark?", pack, citing_provider(real_id), canonical_query="व्यापार चिह्न पंजीकरण"
    )
    assert response.canonical_query == "व्यापार चिह्न पंजीकरण"
    assert response.query == "How to register a trademark?"


def test_multilingual_citation_marker_extraction_is_unaffected_by_script(authority_matrix):
    docs = [
        ("D-ML-6", "English only trademark content here."),
        ("D-ML-7", "தமிழ் மொழி மட்டும் உள்ளடக்கம் இங்கே பதிவு பற்றியது"),
    ]
    pack = make_pack_from_texts(docs, authority_matrix, query="registration பதிவு")
    ids = [e.evidence_id for e in pack.evidence_items]
    from generation.providers import FakeGenerationProvider

    provider = FakeGenerationProvider(response_text=f"[[CITE:{ids[0]}]] [[CITE:{ids[1]}]]")
    response = generate_grounded_response("registration பதிவு", pack, provider)
    assert set(response.cited_evidence_ids) == set(ids)
