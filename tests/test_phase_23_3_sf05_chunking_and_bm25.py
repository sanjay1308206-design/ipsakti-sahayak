"""
Phase 23.3.3: real chunking + real BM25 retrieval over the first real,
admitted corpus document (SF-05, "Food Safety and Standards (Ayurveda
Aahara) Regulations, 2022" - Phase 23.3.2E).

The real ExtractedDocument is deterministically RE-DERIVED from the
persisted raw bytes + manifest on every test run (the same "no second
loader" convention already established for documents/chunks elsewhere in
this project - Phase 3/4 offer only a one-way serializer, never a
dict-to-dataclass loader) - never read back from the gitignored,
regenerable data/normalized|chunks|indexes/ JSON snapshots directly as a
dataclass. This exercises the REAL, unmodified Phase 3 pipeline, Phase 4
chunker, and Phase 5 BM25 builder/query - none of the three is
reimplemented or bypassed anywhere in this file.
"""

from __future__ import annotations

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

DOCUMENT_ID = "SF05-FSSAI-AYURVEDA-AAHARA-REGULATIONS-2022"
RAW_PDF_PATH = REPO_ROOT / "data" / "raw" / "SF-05" / f"{DOCUMENT_ID}.pdf"
MANIFEST_PATH = REPO_ROOT / "data" / "manifest" / "SF-05" / f"{DOCUMENT_ID}.json"


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
def real_document(real_provenance, authority_matrix):
    """Deterministically re-derived real ExtractedDocument - see module docstring."""
    data = RAW_PDF_PATH.read_bytes()
    result = ingest_bytes(data, real_provenance, ".pdf", authority_matrix)
    assert result.pipeline_state == "EXTRACTION_SUCCESS"
    return result.document


@pytest.fixture(scope="module")
def real_chunks(real_document):
    result = chunk_document(real_document)
    return result.chunks


@pytest.fixture(scope="module")
def real_bm25_index(real_chunks):
    return build_index(real_chunks)


# ---------------------------------------------------------------------------
# 1-2. Real document loads; chunking produces a non-zero deterministic set
# ---------------------------------------------------------------------------


def test_real_document_loads_successfully(real_document):
    assert real_document.document_id == DOCUMENT_ID
    assert real_document.extraction_status == "EXTRACTION_SUCCESS" or all(
        p.extraction_status == "SUCCESS" for p in real_document.pages
    )
    assert len(real_document.pages) == 27


def test_chunking_produces_a_nonzero_deterministic_chunk_set(real_chunks):
    assert len(real_chunks) > 0


# ---------------------------------------------------------------------------
# 3-4. Deterministic chunk IDs; correct document reference
# ---------------------------------------------------------------------------


def test_chunk_ids_are_deterministic_across_repeated_chunking_of_the_same_document(real_document):
    result_a = chunk_document(real_document)
    result_b = chunk_document(real_document)
    ids_a = [c.chunk_id for c in result_a.chunks]
    ids_b = [c.chunk_id for c in result_b.chunks]
    assert ids_a == ids_b
    assert len(ids_a) == len(set(ids_a))  # no duplicate chunk_ids within one document


def test_every_chunk_references_the_correct_document(real_chunks):
    for chunk in real_chunks:
        assert chunk.document_id == DOCUMENT_ID


# ---------------------------------------------------------------------------
# 5-7. source_family_id / jurisdiction / synthetic preserved on every chunk
# ---------------------------------------------------------------------------


def test_every_chunk_references_sf05(real_chunks):
    for chunk in real_chunks:
        assert chunk.source_family_id == "SF-05"


def test_every_chunk_is_india_jurisdiction(real_chunks):
    for chunk in real_chunks:
        assert chunk.jurisdiction == "INDIA"


def test_synthetic_false_is_preserved_on_every_chunk(real_chunks):
    for chunk in real_chunks:
        assert chunk.synthetic is False


# ---------------------------------------------------------------------------
# 8. Chunk provenance: page/document/source/hash linkage
# ---------------------------------------------------------------------------


def test_chunk_provenance_links_page_document_source_and_hash(real_chunks, real_provenance):
    for chunk in real_chunks:
        assert len(chunk.page_numbers) > 0
        assert all(1 <= p <= 27 for p in chunk.page_numbers)
        assert chunk.document_id == DOCUMENT_ID
        assert chunk.source_family_id == "SF-05"
        assert chunk.content_hash == real_provenance["content_hash"]
        assert len(chunk.block_ids) > 0
        assert chunk.text.strip() != ""


# ---------------------------------------------------------------------------
# 9. Re-running chunking (full fresh re-extraction) produces identical output
# ---------------------------------------------------------------------------


def test_full_fresh_reextraction_and_rechunking_is_byte_identical(real_provenance, authority_matrix, real_chunks):
    data = RAW_PDF_PATH.read_bytes()
    fresh_result = ingest_bytes(data, real_provenance, ".pdf", authority_matrix)
    fresh_chunks = chunk_document(fresh_result.document).chunks

    assert [c.chunk_id for c in fresh_chunks] == [c.chunk_id for c in real_chunks]
    assert [c.text for c in fresh_chunks] == [c.text for c in real_chunks]


# ---------------------------------------------------------------------------
# 10-11. BM25 index builds successfully; query returns deterministic results
# ---------------------------------------------------------------------------


def test_bm25_index_builds_successfully_from_real_chunks(real_bm25_index, real_chunks):
    assert real_bm25_index.chunk_count == len(real_chunks)
    assert set(real_bm25_index.chunk_ids) == {c.chunk_id for c in real_chunks}


def test_bm25_query_returns_deterministic_results(real_bm25_index):
    response_a = query(real_bm25_index, "आयुर्वेद आहार", top_k=3)
    response_b = query(real_bm25_index, "आयुर्वेद आहार", top_k=3)
    assert [r.chunk_id for r in response_a.results] == [r.chunk_id for r in response_b.results]
    assert [r.score for r in response_a.results] == [r.score for r in response_b.results]
    assert len(response_a.results) > 0


@pytest.mark.parametrize(
    "query_text",
    ["आयुर्वेद आहार", "लेबडलंग अपेक्षा", "अनुसूची क"],
)
def test_real_queries_retrieve_chunks_containing_a_query_token(real_bm25_index, real_chunks, query_text):
    # Retrieval validation only - no legal conclusion is drawn from the
    # concept matched.
    response = query(real_bm25_index, query_text, top_k=3)
    assert len(response.results) > 0
    by_id = {c.chunk_id: c for c in real_chunks}
    tokens = query_text.split()
    for result in response.results:
        chunk = by_id[result.chunk_id]
        assert any(tok in chunk.text for tok in tokens)


# ---------------------------------------------------------------------------
# 12. Retrieved candidates contain valid provenance (ready for Phase 23.3.4)
# ---------------------------------------------------------------------------


def test_retrieved_candidates_carry_full_evidence_ready_provenance(real_bm25_index, real_chunks, real_provenance):
    by_id = {c.chunk_id: c for c in real_chunks}
    response = query(real_bm25_index, "आयुर्वेद आहार", top_k=5)
    assert len(response.results) > 0
    for result in response.results:
        chunk = by_id[result.chunk_id]
        # Exactly the fields evidence.builder.build_evidence_pack's own
        # candidate shape requires (chunk_text, chunk_id, document_id,
        # source_family_id, jurisdiction, content_hash, synthetic,
        # page_numbers, block_ids) - proven present, never assumed.
        assert chunk.text.strip() != ""
        assert chunk.chunk_id == result.chunk_id
        assert chunk.document_id == DOCUMENT_ID
        assert chunk.source_family_id == "SF-05"
        assert chunk.jurisdiction == "INDIA"
        assert chunk.content_hash == real_provenance["content_hash"]
        assert chunk.synthetic is False
        assert len(chunk.page_numbers) > 0
        assert len(chunk.block_ids) > 0


# ---------------------------------------------------------------------------
# 13. Empty/invalid chunk input - actual, unmodified Phase 5 behavior
# ---------------------------------------------------------------------------


def test_empty_chunk_list_produces_a_valid_empty_index_not_an_error():
    # This documents ACTUAL existing Phase 5 behavior (verified, not
    # changed): build_index([]) does not raise - it returns a valid,
    # empty Bm25Index. This is the pre-existing, unmodified contract.
    empty_index = build_index([])
    assert empty_index.chunk_count == 0
    assert empty_index.chunk_ids == []


def test_non_chunk_items_are_rejected_with_type_error():
    with pytest.raises(TypeError):
        build_index(["not-a-chunk"])


# ---------------------------------------------------------------------------
# 14. Index can be reconstructed deterministically from the same real chunks
# ---------------------------------------------------------------------------


def test_index_signature_is_deterministic_across_rebuilds_from_the_same_chunks(real_chunks):
    index_a = build_index(real_chunks)
    index_b = build_index(real_chunks)
    assert index_a.signature == index_b.signature
    assert index_a.chunk_ids == index_b.chunk_ids
