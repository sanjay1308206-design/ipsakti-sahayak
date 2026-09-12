"""
Phase 5 test-support module: builds real Phase 4 chunking.models.Chunk
objects from synthetic text, for use by tests/test_phase_05_*.py.

SYNTHETIC TEST FIXTURE GENERATOR ONLY - reuses tests/_chunk_fixtures.py's
make_document (which itself reuses tests/_provenance_fixtures.make_provenance,
always synthetic=True). Not a test module itself (no test_ prefix) - pytest
will not collect it.
"""

from __future__ import annotations

from _chunk_fixtures import make_document

from chunking.chunker import chunk_document
from chunking.models import ChunkingConfig

# Large enough that a short synthetic document (no heading, or one short
# heading + one paragraph) becomes exactly one chunk - keeps BM25 fixture
# term composition fully predictable.
_LARGE_MAX_CHUNK_SIZE = 100_000


def make_chunks(text: str, document_id: str, authority_matrix: dict, **provenance_overrides) -> list:
    """Ingests `text` as a synthetic TEXT document through the real Phase 3
    pipeline and the real Phase 4 chunker, returning the resulting list of
    chunking.models.Chunk objects (usually exactly one, for a short
    single-paragraph fixture with no heading)."""
    data = text.encode("utf-8")
    doc = make_document(data, ".txt", authority_matrix, document_id=document_id, **provenance_overrides)
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=_LARGE_MAX_CHUNK_SIZE))
    assert result.chunks, f"expected at least one chunk for document {document_id!r}, got none"
    return list(result.chunks)


def make_single_chunk(text: str, document_id: str, authority_matrix: dict, **provenance_overrides):
    """Convenience wrapper for the common case: exactly one chunk expected."""
    chunks = make_chunks(text, document_id, authority_matrix, **provenance_overrides)
    assert len(chunks) == 1, f"expected exactly one chunk for document {document_id!r}, got {len(chunks)}"
    return chunks[0]
