"""
Phase 3 — Document Ingestion & Legal Structure Extraction.

Converts a document that has already passed the Phase 2 corpus-admission
policy into a deterministic, provenance-preserving normalized structural
representation (see docs/PHASE_03_DOCUMENT_INGESTION.md).

Explicitly out of scope here: chunking (Phase 4), retrieval (Phases 5-7),
citation validation (Phase 9), generation (Phase 10).
"""

from .pipeline import ingest_document, ingest_bytes

__all__ = ["ingest_document", "ingest_bytes"]
