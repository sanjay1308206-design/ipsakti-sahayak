"""
Phase 23.3.4: real BM25 retrieval -> real EvidencePack -> real citation
validation, over the first real, admitted corpus document (SF-05,
Phase 23.3.2E/23.3.3).

Connects, unmodified: `retrieval.index.query()` ->
`RetrievalResponse.results` -> `evidence.builder.build_evidence_pack()`
-> `citation.validator.validate_citation()`. `RetrievalResult` already
carries every field `build_evidence_pack`'s candidate-shape validation
requires (verified directly below) - no adapter/glue code exists between
the two, by design of the existing Phase 5/8 contracts.

No dense retrieval, hybrid fusion, reranking, generation, or translation
is introduced anywhere in this file. No legal conclusion is drawn from
any retrieval/evidence result - only that real retrieved source material
converts into traceable, citation-ready evidence without fabrication.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ingestion.admission import load_authority_matrix  # noqa: E402
from ingestion.pipeline import ingest_bytes  # noqa: E402
from chunking.chunker import chunk_document  # noqa: E402
from retrieval.index import build_index, query  # noqa: E402
from evidence.builder import build_evidence_pack  # noqa: E402
from evidence.validation import EvidenceIntegrityError, verify_evidence_identity, verify_pack_identity  # noqa: E402
from citation.models import CitationReference  # noqa: E402
from citation.validator import validate_citation  # noqa: E402

DOCUMENT_ID = "SF05-FSSAI-AYURVEDA-AAHARA-REGULATIONS-2022"
RAW_PDF_PATH = REPO_ROOT / "data" / "raw" / "SF-05" / f"{DOCUMENT_ID}.pdf"
MANIFEST_PATH = REPO_ROOT / "data" / "manifest" / "SF-05" / f"{DOCUMENT_ID}.json"

REAL_QUERIES = [
    "आयुर्वेद आहार",  # Ayurveda Aahara
    "आयुर्वेद आहार परिभाषा",  # definition of Ayurveda Aahara
    "लेबडलंग अपेक्षा",  # labelling requirements
    "संोटक अनुमत",  # permitted ingredients
    "अनुसूची क",  # Schedule A
]


def _skip_if_not_admitted():
    if not RAW_PDF_PATH.is_file() or not MANIFEST_PATH.is_file():
        pytest.skip("real SF-05 document has not been admitted in this checkout (Phase 23.3.2E)")


@pytest.fixture(scope="module")
def real_provenance() -> dict:
    _skip_if_not_admitted()
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return load_authority_matrix()


@pytest.fixture(scope="module")
def real_chunks(real_provenance, authority_matrix):
    data = RAW_PDF_PATH.read_bytes()
    result = ingest_bytes(data, real_provenance, ".pdf", authority_matrix)
    assert result.pipeline_state == "EXTRACTION_SUCCESS"
    return chunk_document(result.document).chunks


@pytest.fixture(scope="module")
def real_bm25_index(real_chunks):
    return build_index(real_chunks)


# ---------------------------------------------------------------------------
# 1. Real BM25 retrieval -> real EvidencePack, for every required query
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("query_text", REAL_QUERIES)
def test_real_query_produces_real_retrieval_and_evidence_pack(real_bm25_index, query_text):
    response = query(real_bm25_index, query_text, top_k=3)
    assert len(response.results) > 0

    pack = build_evidence_pack(response.results, query_text)
    assert pack.query == query_text
    assert len(pack.evidence_items) > 0
    assert len(pack.evidence_items) <= len(response.results)  # dedup/filter never invents extra items


def test_retrieval_results_already_carry_every_field_evidence_pack_requires(real_bm25_index):
    # Proves the connection is direct - RetrievalResult -> build_evidence_pack
    # needs no adapter/glue code, per the existing Phase 5/8 contract.
    from evidence.builder import REQUIRED_CANDIDATE_ATTRS

    response = query(real_bm25_index, REAL_QUERIES[0], top_k=3)
    for result in response.results:
        for attr in REQUIRED_CANDIDATE_ATTRS:
            assert hasattr(result, attr)


# ---------------------------------------------------------------------------
# 2-3. Evidence provenance preserved exactly; item count sane
# ---------------------------------------------------------------------------


def test_evidence_provenance_matches_the_real_document_exactly(real_bm25_index, real_provenance):
    response = query(real_bm25_index, REAL_QUERIES[0], top_k=5)
    pack = build_evidence_pack(response.results, REAL_QUERIES[0])
    by_chunk_id = {r.chunk_id: r for r in response.results}

    for evidence in pack.evidence_items:
        source_result = by_chunk_id[evidence.chunk_id]
        assert evidence.document_id == DOCUMENT_ID
        assert evidence.source_family_id == "SF-05"
        assert evidence.jurisdiction == "INDIA"
        assert evidence.synthetic is False
        assert evidence.content_hash == real_provenance["content_hash"]
        assert 1 <= min(evidence.page_numbers) and max(evidence.page_numbers) <= 27
        assert len(evidence.block_ids) > 0
        assert evidence.evidence_text == source_result.chunk_text  # verbatim, never rewritten


# ---------------------------------------------------------------------------
# 4-5. Evidence ID determinism + EvidencePack determinism
# ---------------------------------------------------------------------------


def test_evidence_id_is_deterministic_across_repeated_builds(real_bm25_index):
    response = query(real_bm25_index, REAL_QUERIES[0], top_k=3)
    pack_a = build_evidence_pack(response.results, REAL_QUERIES[0])
    pack_b = build_evidence_pack(response.results, REAL_QUERIES[0])
    ids_a = [e.evidence_id for e in pack_a.evidence_items]
    ids_b = [e.evidence_id for e in pack_b.evidence_items]
    assert ids_a == ids_b
    assert len(ids_a) == len(set(ids_a))  # no duplicate evidence_id within one pack


def test_evidence_pack_is_deterministic_end_to_end(real_bm25_index):
    # identical query + identical index -> identical RetrievalResponse
    response_a = query(real_bm25_index, REAL_QUERIES[2], top_k=3)
    response_b = query(real_bm25_index, REAL_QUERIES[2], top_k=3)
    assert [r.chunk_id for r in response_a.results] == [r.chunk_id for r in response_b.results]
    assert [r.score for r in response_a.results] == [r.score for r in response_b.results]

    # identical RetrievalResponse -> identical EvidencePack (same pack_id)
    pack_a = build_evidence_pack(response_a.results, REAL_QUERIES[2])
    pack_b = build_evidence_pack(response_b.results, REAL_QUERIES[2])
    assert pack_a.pack_id == pack_b.pack_id
    assert [e.evidence_id for e in pack_a.evidence_items] == [e.evidence_id for e in pack_b.evidence_items]


def test_evidence_pack_serialization_is_deterministic(real_bm25_index):
    from evidence.serialize import evidence_pack_to_dict

    response = query(real_bm25_index, REAL_QUERIES[3], top_k=3)
    pack_a = build_evidence_pack(response.results, REAL_QUERIES[3])
    pack_b = build_evidence_pack(response.results, REAL_QUERIES[3])
    assert json.dumps(evidence_pack_to_dict(pack_a), sort_keys=True) == json.dumps(evidence_pack_to_dict(pack_b), sort_keys=True)


def test_pack_and_evidence_identity_verify_against_their_own_content(real_bm25_index):
    response = query(real_bm25_index, REAL_QUERIES[4], top_k=3)
    pack = build_evidence_pack(response.results, REAL_QUERIES[4])
    verify_pack_identity(pack)  # must not raise
    for evidence in pack.evidence_items:
        verify_evidence_identity(evidence)  # must not raise


# ---------------------------------------------------------------------------
# 6. Citation validator compatibility - valid and fabricated IDs
# ---------------------------------------------------------------------------


def test_valid_citation_referencing_a_real_evidence_id_is_valid(real_bm25_index):
    response = query(real_bm25_index, REAL_QUERIES[0], top_k=3)
    pack = build_evidence_pack(response.results, REAL_QUERIES[0])
    real_evidence_id = pack.evidence_items[0].evidence_id

    result = validate_citation(CitationReference(evidence_id=real_evidence_id), pack)
    assert result.status == "VALID"


def test_fabricated_evidence_id_is_rejected_as_unresolved(real_bm25_index):
    response = query(real_bm25_index, REAL_QUERIES[0], top_k=3)
    pack = build_evidence_pack(response.results, REAL_QUERIES[0])

    result = validate_citation(CitationReference(evidence_id="FABRICATED-EVIDENCE-ID-DOES-NOT-EXIST"), pack)
    assert result.status == "UNRESOLVED"


def test_slightly_altered_real_evidence_id_is_still_unresolved_not_silently_accepted(real_bm25_index):
    # "unknown chunk ID is rejected": a near-miss on a real evidence_id
    # (one character flipped) must not fuzzy-match - exact-match only.
    response = query(real_bm25_index, REAL_QUERIES[0], top_k=3)
    pack = build_evidence_pack(response.results, REAL_QUERIES[0])
    real_evidence_id = pack.evidence_items[0].evidence_id
    almost_real_id = real_evidence_id[:-1] + ("0" if real_evidence_id[-1] != "0" else "1")

    result = validate_citation(CitationReference(evidence_id=almost_real_id), pack)
    assert result.status == "UNRESOLVED"


def test_malformed_citation_reference_is_invalid(real_bm25_index):
    response = query(real_bm25_index, REAL_QUERIES[0], top_k=3)
    pack = build_evidence_pack(response.results, REAL_QUERIES[0])

    result = validate_citation(CitationReference(evidence_id=None), pack)
    assert result.status == "INVALID"


# ---------------------------------------------------------------------------
# 7. Negative tests: no fabrication, mismatches rejected, synthetic preserved
# ---------------------------------------------------------------------------


def test_empty_retrieval_results_produce_an_empty_pack_never_fabricated_evidence(real_bm25_index):
    empty_response = query(real_bm25_index, "zzz_no_such_term_zzz_nonexistent_query_token", top_k=5)
    pack = build_evidence_pack(empty_response.results, "zzz_no_such_term_zzz_nonexistent_query_token")
    assert pack.evidence_items == []
    assert pack.query == "zzz_no_such_term_zzz_nonexistent_query_token"


def test_tampered_document_id_is_detected_by_identity_verification(real_bm25_index):
    response = query(real_bm25_index, REAL_QUERIES[0], top_k=1)
    pack = build_evidence_pack(response.results, REAL_QUERIES[0])
    tampered = dataclasses.replace(pack.evidence_items[0], document_id="SOME-OTHER-DOCUMENT")
    with pytest.raises(EvidenceIntegrityError):
        verify_evidence_identity(tampered)


def test_tampered_source_family_is_detected_by_identity_verification(real_bm25_index):
    response = query(real_bm25_index, REAL_QUERIES[0], top_k=1)
    pack = build_evidence_pack(response.results, REAL_QUERIES[0])
    tampered = dataclasses.replace(pack.evidence_items[0], source_family_id="SF-01")
    with pytest.raises(EvidenceIntegrityError):
        verify_evidence_identity(tampered)


def test_tampered_jurisdiction_is_detected_by_identity_verification(real_bm25_index):
    response = query(real_bm25_index, REAL_QUERIES[0], top_k=1)
    pack = build_evidence_pack(response.results, REAL_QUERIES[0])
    tampered = dataclasses.replace(pack.evidence_items[0], jurisdiction="INTERNATIONAL")
    with pytest.raises(EvidenceIntegrityError):
        verify_evidence_identity(tampered)


def test_tampered_content_hash_is_detected_by_identity_verification(real_bm25_index):
    response = query(real_bm25_index, REAL_QUERIES[0], top_k=1)
    pack = build_evidence_pack(response.results, REAL_QUERIES[0])
    tampered = dataclasses.replace(pack.evidence_items[0], content_hash="0" * 64)
    with pytest.raises(EvidenceIntegrityError):
        verify_evidence_identity(tampered)


def test_synthetic_true_variant_cannot_masquerade_as_the_real_evidence(real_bm25_index, real_provenance):
    # A synthetic=true candidate (all else identical) must be faithfully
    # propagated, never silently coerced to false - proving it can never
    # be mistaken for the real, admitted document's evidence.
    response = query(real_bm25_index, REAL_QUERIES[0], top_k=1)
    real_result = response.results[0]
    synthetic_result = dataclasses.replace(real_result, synthetic=True)

    real_pack = build_evidence_pack([real_result], REAL_QUERIES[0])
    synthetic_pack = build_evidence_pack([synthetic_result], REAL_QUERIES[0])

    assert real_pack.evidence_items[0].synthetic is False
    assert synthetic_pack.evidence_items[0].synthetic is True
    # Different synthetic flags feed into evidence_id computation only if
    # synthetic is itself a hash input - either way the two evidence
    # objects must not be treated as interchangeable/identical.
    assert real_pack.evidence_items[0].synthetic != synthetic_pack.evidence_items[0].synthetic
