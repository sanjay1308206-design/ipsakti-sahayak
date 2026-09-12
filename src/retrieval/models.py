"""
Phase 5 (BM25), Phase 6 (dense/FAISS), and Phase 7 (RRF fusion +
cross-encoder reranking) output/config data shapes, mirroring
config/bm25_contract.yaml, config/retrieval_result_schema.yaml,
config/dense_retrieval_contract.yaml, config/dense_index_schema.yaml,
config/hybrid_retrieval_contract.yaml, and config/hybrid_result_schema.yaml.

Pure data holders only - no I/O, no scoring logic here (that lives in
bm25.py/index.py for Phase 5, faiss_index.py for Phase 6, rrf.py/hybrid.py
for Phase 7), matching the src/chunking/models.py convention.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .tokenizer import TOKENIZER_POLICY_VERSION


@dataclass(frozen=True)
class Bm25Config:
    """
    BM25 scoring parameters (docs/PHASE_05_BM25_BASELINE.md Section G).

    k1=1.5, b=0.75 are the standard textbook defaults from the original
    Okapi BM25 formulation (Robertson & Zaragoza) - not tuned for this
    corpus. Parameter tuning belongs to evaluation (Phase 16), never to
    this baseline. [ENGINEERING RECOMMENDATION].
    """

    k1: float = 1.5
    b: float = 0.75
    tokenizer_version: str = TOKENIZER_POLICY_VERSION
    contract_version: str = "1.0.0"

    def __post_init__(self):
        if isinstance(self.k1, bool) or not isinstance(self.k1, (int, float)) or self.k1 < 0:
            raise ValueError(f"k1 must be a non-negative number, got {self.k1!r}")
        if isinstance(self.b, bool) or not isinstance(self.b, (int, float)) or not (0.0 <= self.b <= 1.0):
            raise ValueError(f"b must be a number in [0.0, 1.0], got {self.b!r}")
        if self.tokenizer_version != TOKENIZER_POLICY_VERSION:
            raise ValueError(
                f"unsupported tokenizer_version {self.tokenizer_version!r}; "
                f"only {TOKENIZER_POLICY_VERSION!r} is implemented"
            )

    @property
    def signature(self) -> str:
        """Deterministic, canonical string identity for this config - part of the index signature."""
        return f"bm25-config:v{self.contract_version}:k1={self.k1}:b={self.b}:tokenizer={self.tokenizer_version}"


@dataclass(frozen=True)
class Bm25Index:
    """
    A built BM25 index over a fixed set of Phase 4 chunks. Every field is
    plain data (str/int/float/list/dict) - directly JSON-serializable with
    no custom encoder needed (src/retrieval/serialize.py).

    `chunk_ids[i]`, `document_lengths[i]`, and `term_frequencies[i]` all
    refer to the same internal document position `i` - the *only* internal
    identifier this index invents; it is never exposed outside this index
    and never substitutes for `chunk_id` in any output (docs/PHASE_05_BM25_BASELINE.md
    Section H).
    """

    config: Bm25Config
    chunk_count: int
    average_document_length: float
    chunk_ids: list  # list[str], internal position -> Phase 4 chunk_id
    document_lengths: list  # list[int], parallel to chunk_ids
    term_document_frequency: dict  # term -> number of chunks containing it
    term_frequencies: list  # list[dict[str, int]], parallel to chunk_ids
    chunk_provenance: list  # list[dict], parallel to chunk_ids - see index.py
    signature: str

    def __post_init__(self):
        assert len(self.chunk_ids) == self.chunk_count
        assert len(self.document_lengths) == self.chunk_count
        assert len(self.term_frequencies) == self.chunk_count
        assert len(self.chunk_provenance) == self.chunk_count
        assert len(self.chunk_ids) == len(set(self.chunk_ids)), "chunk_ids must be unique within an index"


@dataclass(frozen=True)
class RetrievalResult:
    """
    One ranked retrieval result. `score` is a BM25 lexical relevance score
    ONLY - it is never evidence of legal authority, and must never be
    presented as a citation or a legal ranking (docs/PHASE_05_BM25_BASELINE.md
    Section B/M).
    """

    rank: int
    chunk_id: str
    score: float
    document_id: str
    source_family_id: str
    jurisdiction: str
    content_hash: str
    synthetic: bool
    page_numbers: list
    block_ids: list
    chunk_text: str

    def __post_init__(self):
        assert self.rank >= 1
        assert self.block_ids, "a retrieval result must reference at least one contributing block"
        assert self.page_numbers, "a retrieval result must reference at least one contributing page"


@dataclass(frozen=True)
class RetrievalResponse:
    """Top-level result of index.query()."""

    query: str
    normalized_query_tokens: list  # list[str]
    top_k: int
    index_signature: str
    results: list = field(default_factory=list)  # list[RetrievalResult]


# ---------------------------------------------------------------------------
# Phase 6 - Multilingual Dense Retrieval (docs/PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md)
# ---------------------------------------------------------------------------

DENSE_INDEX_TYPES = frozenset({"FLAT_IP"})  # only one supported for this baseline - see docs Section K


class DenseIndexCompatibilityError(ValueError):
    """Raised when a persisted dense index/metadata pair is missing, corrupted, or internally inconsistent."""


@dataclass(frozen=True)
class DenseIndexConfig:
    """
    FAISS index configuration (docs Section K). `FLAT_IP` (exact brute-force
    inner-product search over L2-normalized vectors = exact cosine
    similarity) is the only supported index type for this baseline -
    IVF/HNSW/PQ/GPU FAISS are explicitly deferred (docs Section V) until a
    concrete accuracy/latency requirement demonstrates FLAT_IP is
    insufficient. `[ENGINEERING RECOMMENDATION]`.
    """

    index_type: str = "FLAT_IP"
    contract_version: str = "1.0.0"

    def __post_init__(self):
        if self.index_type not in DENSE_INDEX_TYPES:
            raise ValueError(
                f"unsupported index_type {self.index_type!r}; only {sorted(DENSE_INDEX_TYPES)} is implemented"
            )
        if not isinstance(self.contract_version, str) or not self.contract_version.strip():
            raise ValueError("contract_version must be a non-empty string")

    @property
    def signature(self) -> str:
        return f"dense-index-config:v{self.contract_version}:type={self.index_type}"


@dataclass(eq=False)
class DenseIndex:
    """
    A built dense (FAISS) index over a fixed set of Phase 4 chunks.

    Unlike Bm25Index, this is NOT fully plain-JSON data: `faiss_index` is
    an opaque native FAISS object. `eq=False` disables dataclass-generated
    equality (comparing FAISS index objects is not meaningful). Every
    OTHER field is plain data and is what gets persisted as the JSON
    metadata sidecar (src/retrieval/serialize.py) alongside the FAISS
    index's own native binary serialization (docs Section T).

    `chunk_ids[i]`/`chunk_provenance[i]` refer to the same internal FAISS
    vector position `i` - the *only* internal identifier this index
    invents; it is never exposed outside this index and never substitutes
    for `chunk_id` in any output (docs Section L).
    """

    embedding_config: object  # retrieval.embeddings.EmbeddingConfig (avoids a circular import at type-check time)
    dense_index_config: DenseIndexConfig
    model_identity: str
    dimension: int
    chunk_count: int
    chunk_ids: list  # list[str], internal FAISS position -> Phase 4 chunk_id
    chunk_provenance: list  # list[dict], parallel to chunk_ids - see faiss_index.py
    signature: str
    faiss_index: object  # faiss.Index - opaque, not JSON-serializable directly

    def __post_init__(self):
        assert len(self.chunk_ids) == self.chunk_count
        assert len(self.chunk_provenance) == self.chunk_count
        assert len(self.chunk_ids) == len(set(self.chunk_ids)), "chunk_ids must be unique within a dense index"


@dataclass(frozen=True)
class DenseRetrievalResult:
    """
    One ranked dense-retrieval result. `score` is a cosine-similarity
    signal ONLY (inner product of L2-normalized vectors) - it is never
    evidence of legal authority, citation validity, regulatory
    correctness, or confidence in a legal conclusion
    (docs/PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md Section N).
    """

    rank: int
    chunk_id: str
    score: float
    model_identity: str
    document_id: str
    source_family_id: str
    jurisdiction: str
    content_hash: str
    synthetic: bool
    page_numbers: list
    block_ids: list
    chunk_text: str

    def __post_init__(self):
        assert self.rank >= 1
        assert self.block_ids, "a dense retrieval result must reference at least one contributing block"
        assert self.page_numbers, "a dense retrieval result must reference at least one contributing page"


@dataclass(frozen=True)
class DenseRetrievalResponse:
    """
    Top-level result of faiss_index.dense_query(). Unlike Phase 5's BM25
    response, there is no meaningful token-level "normalized query"
    representation to report - the query is embedded holistically as one
    vector, not tokenized into scored terms (docs Section N).
    """

    query: str
    top_k: int
    index_signature: str
    model_identity: str
    results: list = field(default_factory=list)  # list[DenseRetrievalResult]


# ---------------------------------------------------------------------------
# Phase 7 - Hybrid Fusion + Reranking
# (docs/PHASE_07_HYBRID_FUSION_AND_RERANKING.md)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RrfConfig:
    """
    Reciprocal Rank Fusion parameters (docs Section H/I).

    RRF_score(d) = sum over retrieval lists L containing d of 1/(k + rank_L(d))

    `k=60.0` is the standard constant from the original RRF paper (Cormack,
    Clarke & Buettcher, 2009) `[EXTERNAL RESEARCH]` - not tuned for this
    corpus, exactly the same un-tuned-default discipline already applied to
    Phase 5's `k1`/`b`. `rank_L(d)` is always the 1-based rank already
    assigned by the contributing retrieval system's own result contract
    (`RetrievalResult.rank` / `DenseRetrievalResult.rank`) - RRF never
    re-derives or renumbers ranks itself.
    """

    k: float = 60.0
    contract_version: str = "1.0.0"

    def __post_init__(self):
        if isinstance(self.k, bool) or not isinstance(self.k, (int, float)) or self.k <= 0:
            raise ValueError(f"k must be a positive number, got {self.k!r}")
        if not isinstance(self.contract_version, str) or not self.contract_version.strip():
            raise ValueError("contract_version must be a non-empty string")

    @property
    def signature(self) -> str:
        return f"rrf-config:v{self.contract_version}:k={self.k}"


@dataclass(frozen=True)
class RrfResult:
    """
    One RRF-fused candidate, before reranking - directly usable to measure
    "RRF hybrid" on its own (docs Section F, comparison point 3).

    `rrf_score` is a rank-fusion signal ONLY - never legal confidence,
    regulatory authority, citation validity, or factual correctness
    (docs Section Q). `bm25_rank`/`bm25_score` and `dense_rank`/`dense_score`
    are `None` when the candidate was not present in that retrieval
    system's result list - never fabricated as 0 or any other sentinel
    that could be confused with a real rank/score.
    """

    rank: int
    chunk_id: str
    rrf_score: float
    bm25_rank: Optional[int]
    bm25_score: Optional[float]
    dense_rank: Optional[int]
    dense_score: Optional[float]
    document_id: str
    source_family_id: str
    jurisdiction: str
    content_hash: str
    synthetic: bool
    page_numbers: list
    block_ids: list
    chunk_text: str

    def __post_init__(self):
        assert self.rank >= 1
        assert self.bm25_rank is not None or self.dense_rank is not None, (
            "an RRF candidate must have contributed from at least one retrieval system"
        )
        assert self.block_ids, "an RRF result must reference at least one contributing block"
        assert self.page_numbers, "an RRF result must reference at least one contributing page"


@dataclass(frozen=True)
class RrfResponse:
    """Top-level result of rrf.fuse_rrf() - the candidate union already RRF-ranked, truncated to candidate_k."""

    query: str
    candidate_k: int
    rrf_k: float
    results: list = field(default_factory=list)  # list[RrfResult]


@dataclass(frozen=True)
class HybridRetrievalResult:
    """
    One final result after cross-encoder reranking of an RRF candidate set
    (docs Section P/Q). Preserves every upstream signal distinctly -
    `bm25_score`, `dense_score`, `rrf_score`, and `reranker_score` are never
    collapsed into one ambiguous field, and none of them is legal
    authority, citation validity, regulatory correctness, or confidence in
    a legal conclusion.
    """

    rank: int
    chunk_id: str
    reranker_score: float
    rrf_score: float
    bm25_rank: Optional[int]
    bm25_score: Optional[float]
    dense_rank: Optional[int]
    dense_score: Optional[float]
    reranker_model_identity: str
    document_id: str
    source_family_id: str
    jurisdiction: str
    content_hash: str
    synthetic: bool
    page_numbers: list
    block_ids: list
    chunk_text: str

    def __post_init__(self):
        assert self.rank >= 1
        assert self.bm25_rank is not None or self.dense_rank is not None, (
            "a hybrid result must have contributed from at least one retrieval system"
        )
        assert self.block_ids, "a hybrid result must reference at least one contributing block"
        assert self.page_numbers, "a hybrid result must reference at least one contributing page"


@dataclass(frozen=True)
class HybridRetrievalResponse:
    """Top-level result of hybrid.rerank_candidates() / hybrid.run_hybrid_pipeline() - the final Phase 7 output."""

    query: str
    top_k: int
    rrf_k: float
    reranker_model_identity: str
    results: list = field(default_factory=list)  # list[HybridRetrievalResult]
