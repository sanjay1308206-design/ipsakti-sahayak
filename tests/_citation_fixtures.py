"""
Phase 9 test-support module: builds real Phase 8 EvidencePack objects
(reusing tests/_evidence_fixtures.py, which itself reuses
tests/_bm25_fixtures.py/_dense_fixtures.py/_hybrid_fixtures.py) plus
synthetic citation.models.CitationReference objects, for use by
tests/test_phase_09_*.py.

SYNTHETIC TEST FIXTURE GENERATOR ONLY. Not a test module itself (no test_
prefix) - pytest will not collect it.
"""

from __future__ import annotations

from _evidence_fixtures import make_hybrid_response, make_single_chunk

from citation.models import CitationReference
from evidence.builder import build_evidence_pack
from evidence.models import EvidencePack, EvidenceSelectionConfig

__all__ = [
    "make_hybrid_response",
    "make_single_chunk",
    "make_pack_from_texts",
    "make_reference",
    "fabricated_evidence_id",
]


def make_pack_from_texts(texts_and_doc_ids, authority_matrix, query: str = "citation validation query", **config_kwargs) -> EvidencePack:
    """
    Builds one real EvidencePack from a list of (document_id, text) pairs,
    via the real Phase 3/4 pipeline and Phase 5/6/7 hybrid retrieval -
    exactly like tests/test_phase_08_*.py does, never a hand-built pack.
    """
    chunks = [make_single_chunk(text, doc_id, authority_matrix) for doc_id, text in texts_and_doc_ids]
    resp = make_hybrid_response(chunks, query, top_k=len(chunks))
    config = EvidenceSelectionConfig(**config_kwargs) if config_kwargs else None
    return build_evidence_pack(resp.results, query, config)


def make_reference(evidence_id, **kwargs) -> CitationReference:
    """Convenience constructor - kwargs forward to CitationReference (schema_version, citation_ref_id, display_order)."""
    return CitationReference(evidence_id=evidence_id, **kwargs)


def fabricated_evidence_id() -> str:
    """A well-formed-looking but definitely-nonexistent SHA-256-shaped evidence_id - never a real one."""
    return "f" * 64
