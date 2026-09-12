"""
Phase 4 — Legal-Aware Chunking.

Transforms a Phase 3 ingestion.models.ExtractedDocument into deterministic,
provenance-preserving, retrieval-ready chunks (see
docs/PHASE_04_LEGAL_AWARE_CHUNKING.md).

Explicitly out of scope here: BM25/dense/hybrid retrieval (Phases 5-7),
embeddings, FAISS, reranking, citation validation (Phase 9), generation
(Phase 10), jurisdiction firewall (Phase 12), confidence engine (Phase 13).
"""

from .chunker import chunk_document
from .models import Chunk, ChunkingConfig, ChunkingResult

__all__ = ["chunk_document", "Chunk", "ChunkingConfig", "ChunkingResult"]
