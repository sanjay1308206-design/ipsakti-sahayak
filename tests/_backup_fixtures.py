"""
Phase 21 test-support module: builds real Phase 3 AdmittedDocument pairs
(provenance dict + ExtractedDocument), Phase 4 ChunkingResult objects, and
a Phase 5 Bm25Index, for use by tests/test_phase_21_backup.py.

SYNTHETIC TEST FIXTURE GENERATOR ONLY - reuses _provenance_fixtures.make_provenance
(always synthetic=True) and the real Phase 3/4/5 pipeline. Not a test
module itself (no test_ prefix) - pytest will not collect it.
"""

from __future__ import annotations

from _provenance_fixtures import make_provenance

from chunking.chunker import chunk_document
from chunking.models import ChunkingConfig
from ingestion.hashing import compute_content_hash
from ingestion.pipeline import ingest_bytes
from observability.backup_models import AdmittedDocument
from retrieval.index import build_index

_LARGE_MAX_CHUNK_SIZE = 100_000


def make_admitted_document(text: str, document_id: str, authority_matrix: dict, **provenance_overrides) -> AdmittedDocument:
    """Ingests `text` as a synthetic TEXT document through the real Phase 3 pipeline, returning an AdmittedDocument pairing its provenance with the resulting ExtractedDocument."""
    data = text.encode("utf-8")
    provenance = make_provenance(
        compute_content_hash(data),
        document_id=document_id,
        provenance_status="COMPLETE",
        validation_status="VALIDATED",
        **provenance_overrides,
    )
    result = ingest_bytes(data, provenance, ".txt", authority_matrix=authority_matrix)
    assert result.document is not None, (
        f"ingestion did not produce a document: pipeline_state={result.pipeline_state} reason_codes={result.reason_codes}"
    )
    return AdmittedDocument(provenance=provenance, extracted_document=result.document)


def make_chunking_result(admitted: AdmittedDocument):
    """Runs the real Phase 4 chunker over an AdmittedDocument's ExtractedDocument."""
    return chunk_document(admitted.extracted_document, ChunkingConfig(max_chunk_size_chars=_LARGE_MAX_CHUNK_SIZE))


def make_bm25_index(chunking_results: list):
    """Builds a real Phase 5 Bm25Index across every chunk in `chunking_results`."""
    chunks = [chunk for cr in chunking_results for chunk in cr.chunks]
    return build_index(chunks)
