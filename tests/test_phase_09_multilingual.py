"""
Phase 9 tests: multilingual citation validation
(docs/PHASE_09_CITATION_VALIDATION.md Section R). Evidence ID resolution
must behave identically regardless of the underlying evidence text's
script/language - citation validation itself is language-neutral, and
evidence text is never touched.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _citation_fixtures import make_pack_from_texts, make_reference

from citation.validator import validate_citation, validate_citations

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def test_english_evidence_citation_resolves(authority_matrix):
    pack = make_pack_from_texts([("D-ML-EN", "Trademark registration application process.")], authority_matrix)
    result = validate_citation(make_reference(pack.evidence_items[0].evidence_id), pack)
    assert result.status == "VALID"
    assert result.resolved_evidence.evidence_id == pack.evidence_items[0].evidence_id


def test_devanagari_evidence_citation_resolves(authority_matrix):
    pack = make_pack_from_texts([("D-ML-HI", "आयुर्वेद औषधि पंजीकरण के लिए आवेदन आवश्यक है")], authority_matrix)
    result = validate_citation(make_reference(pack.evidence_items[0].evidence_id), pack)
    assert result.status == "VALID"


def test_tamil_evidence_citation_resolves(authority_matrix):
    pack = make_pack_from_texts([("D-ML-TA", "மருந்து பதிவு விண்ணப்பம் தேவை")], authority_matrix)
    result = validate_citation(make_reference(pack.evidence_items[0].evidence_id), pack)
    assert result.status == "VALID"


def test_mixed_script_evidence_citation_resolves(authority_matrix):
    pack = make_pack_from_texts([("D-ML-MIX", "Ayurveda आयुर्वेद மருந்து registration requires an application.")], authority_matrix)
    result = validate_citation(make_reference(pack.evidence_items[0].evidence_id), pack)
    assert result.status == "VALID"


def test_evidence_text_is_never_touched_by_validation(authority_matrix):
    text = "आयுர்वेद मिश्रित content preserved exactly."
    pack = make_pack_from_texts([("D-ML-PRESERVE", text)], authority_matrix)
    original_text = pack.evidence_items[0].evidence_text
    result = validate_citation(make_reference(pack.evidence_items[0].evidence_id), pack)
    assert result.status == "VALID"
    # evidence_text on the pack itself remains byte-for-byte unchanged -
    # validation never normalizes/rewrites it.
    assert pack.evidence_items[0].evidence_text == original_text


def test_multilingual_corpus_all_citations_resolve_identically_regardless_of_script(authority_matrix):
    docs = [
        ("D-ML-CORPUS-1", "English only trademark content here."),
        ("D-ML-CORPUS-2", "केवल हिंदी सामग्री यहाँ पंजीकरण के बारे में है"),
        ("D-ML-CORPUS-3", "தமிழ் மொழி மட்டும் உள்ளடக்கம் இங்கே பதிவு பற்றியது"),
        ("D-ML-CORPUS-4", "Mixed English आयुर्वेद மருந்து content together."),
    ]
    pack = make_pack_from_texts(docs, authority_matrix, query="registration பதிவு पंजीकरण")
    real_ids = [e.evidence_id for e in pack.evidence_items]
    results = validate_citations([make_reference(rid) for rid in real_ids], pack)
    assert all(r.status == "VALID" for r in results)


def test_unicode_evidence_id_like_string_that_is_not_a_real_id_is_unresolved(authority_matrix):
    # A citation_ref_id / evidence_id containing non-ASCII content that is
    # NOT a real evidence_id must resolve exactly like any other fabricated
    # ID - UNRESOLVED, never a crash, never a fuzzy match.
    pack = make_pack_from_texts([("D-ML-UNICODE", "Content for unicode id test.")], authority_matrix)
    result = validate_citation(make_reference("आयुर्वेद-नकली-आईडी"), pack)
    assert result.status == "UNRESOLVED"
