"""
Phase 4 test-support module: builds a real Phase 3 ExtractedDocument from
synthetic bytes, for use by tests/test_phase_04_*.py.

SYNTHETIC TEST FIXTURE GENERATOR ONLY - reuses _provenance_fixtures.make_provenance,
which always sets synthetic=True. Not a test module itself (no test_ prefix)
- pytest will not collect it.
"""

from __future__ import annotations

from _provenance_fixtures import make_provenance

from ingestion.hashing import compute_content_hash
from ingestion.pipeline import ingest_bytes


def make_document(data: bytes, file_extension: str, authority_matrix: dict, **provenance_overrides):
    """
    Ingest synthetic bytes through the real Phase 3 pipeline and return the
    resulting ExtractedDocument.

    Raises AssertionError if ingestion did not produce a document - tests
    that want to exercise a non-success ingestion path should call
    ingestion.pipeline.ingest_bytes directly instead of this helper.
    """
    provenance = make_provenance(compute_content_hash(data), **provenance_overrides)
    result = ingest_bytes(data, provenance, file_extension, authority_matrix=authority_matrix)
    assert result.document is not None, (
        f"ingestion did not produce a document: pipeline_state={result.pipeline_state} "
        f"reason_codes={result.reason_codes}"
    )
    return result.document
