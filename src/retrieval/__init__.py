"""
Phase 5 — BM25 Retrieval Baseline (lexical) + Phase 6 — Multilingual Dense
Retrieval (embedding/FAISS) + Phase 7 — Hybrid Fusion (RRF) + Cross-Encoder
Reranking.

All three are deterministic, independently measurable retrieval stages
over Phase 4 chunking.models.Chunk objects (see docs/PHASE_05_BM25_BASELINE.md,
docs/PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md,
docs/PHASE_07_HYBRID_FUSION_AND_RERANKING.md). None is the final retrieval
architecture.

Explicitly out of scope here: Evidence Pack architecture, citation
validation, claim/evidence binding, grounded generation (Phase 8-10), the
jurisdiction firewall (Phase 12), the confidence engine (Phase 13) -
with one narrow, disclosed exception: `production_corpus.py` (LD-2,
Production Corpus & Retrieval) depends on `evidence.builder` (to expose
a ready-to-wire `Callable[[str], EvidencePack]`) and on
`ingestion.pipeline`/`chunking.chunker` (to deterministically rebuild the
one real, admitted SF-05 document at runtime, never a second loader over
a persisted JSON snapshot). It is not imported by this package's own
`__init__.py` and is not required for any of the retrieval primitives
below.
"""

from .embeddings import (
    EmbeddingConfig,
    EmbeddingModel,
    EmbeddingModelLoadError,
    EmbeddingModelNotLoadedError,
    FakeEmbeddingModel,
    SentenceTransformerEmbeddingModel,
)
from .faiss_index import build_dense_index, dense_query
from .hybrid import rerank_candidates, run_hybrid_pipeline
from .index import build_index, query
from .models import (
    Bm25Config,
    Bm25Index,
    DenseIndex,
    DenseIndexCompatibilityError,
    DenseIndexConfig,
    DenseRetrievalResponse,
    DenseRetrievalResult,
    HybridRetrievalResponse,
    HybridRetrievalResult,
    RetrievalResponse,
    RetrievalResult,
    RrfConfig,
    RrfResponse,
    RrfResult,
)
from .reranker import (
    CrossEncoderReranker,
    FakeReranker,
    Reranker,
    RerankerConfig,
    RerankerLoadError,
    RerankerNotLoadedError,
)
from .rrf import fuse_rrf

__all__ = [
    "build_index",
    "query",
    "Bm25Config",
    "Bm25Index",
    "RetrievalResponse",
    "RetrievalResult",
    "build_dense_index",
    "dense_query",
    "EmbeddingConfig",
    "EmbeddingModel",
    "EmbeddingModelLoadError",
    "EmbeddingModelNotLoadedError",
    "FakeEmbeddingModel",
    "SentenceTransformerEmbeddingModel",
    "DenseIndex",
    "DenseIndexConfig",
    "DenseIndexCompatibilityError",
    "DenseRetrievalResponse",
    "DenseRetrievalResult",
    "fuse_rrf",
    "rerank_candidates",
    "run_hybrid_pipeline",
    "RrfConfig",
    "RrfResponse",
    "RrfResult",
    "HybridRetrievalResponse",
    "HybridRetrievalResult",
    "Reranker",
    "RerankerConfig",
    "RerankerLoadError",
    "RerankerNotLoadedError",
    "CrossEncoderReranker",
    "FakeReranker",
]
