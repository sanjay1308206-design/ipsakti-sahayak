"""
Phase 8 evidence/citation data shapes
(docs/PHASE_08_EVIDENCE_OBJECT_AND_CITATION_ARCHITECTURE.md).

Pure data holders only - no I/O, no identity computation, no candidate
selection logic here (that lives in identity.py/builder.py), matching the
src/retrieval/models.py convention.

These types are deliberately independent of any specific Phase 5/6/7
retrieval result type - Evidence is built FROM a retrieval candidate
(builder.py), but never IS one. The evidence layer is the trust boundary:
retrieval says "this chunk may be relevant"; Evidence says "this exact
chunk, with this exact provenance and source location, is available to
downstream systems" (docs Section preamble).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Union

EVIDENCE_SCHEMA_VERSION = "1.0.0"
PACK_SCHEMA_VERSION = "1.0.0"

# The only evidence type this phase produces - every Evidence object is
# derived from exactly one Phase 4 chunk. A closed, versioned vocabulary,
# extensible later (e.g. a future non-chunk evidence type) only by adding
# a new named value here, never by silently accepting an arbitrary string.
EVIDENCE_TYPES = frozenset({"CHUNK"})


class EvidenceIntegrityError(ValueError):
    """Raised when Evidence/EvidencePack identity, text, or structural integrity cannot be verified."""


class EvidenceNotFoundError(LookupError):
    """Raised when a CitationTarget references an evidence_id not present in the given EvidencePack."""


@dataclass(frozen=True)
class VersionInfo:
    """
    Document version / effective-date / supersession metadata
    (docs Section T). `[DEFERRED]`/`[ASSUMPTION]`: Phase 2's
    `config/corpus_provenance_schema.yaml` defines `version`,
    `effective_date`, `publication_date`, and `supersession_status` fields,
    but NONE of them are currently carried forward by Phase 3's
    `ExtractedDocument`, Phase 4's `Chunk`, or any Phase 5/6/7 retrieval
    result - so every field here is `None`/`False` (explicitly "not
    available"), never fabricated, for every Evidence object this phase
    can currently produce. This type exists so the gap is structurally
    visible and so a future phase can populate it without an Evidence
    schema change, once Phase 3/4 actually propagate these fields.
    """

    version: Optional[str] = None
    version_known: bool = False
    effective_date: Optional[str] = None
    effective_date_known: bool = False
    publication_date: Optional[str] = None
    supersession_status: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.version_known, bool):
            raise ValueError("version_known must be a bool")
        if not isinstance(self.effective_date_known, bool):
            raise ValueError("effective_date_known must be a bool")


@dataclass(frozen=True)
class RetrievalMetadata:
    """
    Retrieval-signal metadata, kept explicitly separate from evidence
    identity/provenance (docs Section Q). `rank` is the candidate's rank
    within whichever retrieval stage produced it (BM25-only, dense-only,
    RRF, or final reranked - see `builder._extract_retrieval_metadata`).
    Every score/rank field not present on the originating candidate is
    `None` - never fabricated as 0 or any other sentinel.

    None of these fields is legal confidence, regulatory authority, or
    citation validity - they are lexical/semantic/fusion/reranking
    relevance signals only, identical to the discipline already documented
    in docs/PHASE_05_BM25_BASELINE.md, docs/PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md,
    and docs/PHASE_07_HYBRID_FUSION_AND_RERANKING.md.
    """

    rank: int
    bm25_rank: Optional[int] = None
    bm25_score: Optional[float] = None
    dense_rank: Optional[int] = None
    dense_score: Optional[float] = None
    dense_model_identity: Optional[str] = None
    rrf_score: Optional[float] = None
    reranker_score: Optional[float] = None
    reranker_model_identity: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.rank, int) or isinstance(self.rank, bool) or self.rank < 1:
            raise ValueError(f"rank must be a positive integer, got {self.rank!r}")
        for name in ("bm25_rank", "dense_rank"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 1):
                raise ValueError(f"{name} must be a positive integer or None, got {value!r}")
        for name in ("bm25_score", "dense_score", "rrf_score", "reranker_score"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
            ):
                raise ValueError(f"{name} must be a finite number or None, got {value!r}")


@dataclass(frozen=True)
class SourceLocation:
    """
    Explicit source-location representation (docs Section K) - returned by
    `Evidence.source_location`, a computed view over Evidence's own flat
    provenance fields (never a second, independently-stored copy of the
    same data - Development Rules: no redundant duplication).

    `section_heading_text`/`section_heading_level` are `None` whenever the
    originating candidate did not carry them - which, as of Phase 5/6/7's
    current result contracts, is always (none of RetrievalResult/
    DenseRetrievalResult/RrfResult/HybridRetrievalResult propagate Phase 4's
    heading metadata forward). Never fabricated; a documented, honest gap.
    """

    document_id: str
    source_family_id: str
    jurisdiction: str
    content_hash: str
    page_numbers: list
    block_ids: list
    section_heading_text: Optional[str] = None
    section_heading_level: Optional[Union[int, str]] = None


@dataclass(frozen=True)
class Evidence:
    """
    The canonical evidence object (docs Section G). `evidence_text` is
    verbatim candidate/chunk text - never paraphrased, summarized, or
    rewritten. `evidence_id` is a deterministic, backend-owned identity
    (identity.compute_evidence_id) - never a FAISS/BM25 position, a random
    UUID, or anything derived from LLM output. `chunk_id` remains the
    underlying Phase 4 retrieval identity; `evidence_id` is a distinct,
    evidence-layer-scoped identity derived from it (docs Section H) -
    Evidence never uses evidence_id in place of chunk_id internally.
    """

    evidence_id: str
    evidence_schema_version: str
    evidence_type: str
    evidence_text: str
    evidence_text_hash: str
    chunk_id: str
    document_id: str
    source_family_id: str
    jurisdiction: str
    content_hash: str
    synthetic: bool
    page_numbers: list
    block_ids: list
    retrieval_metadata: RetrievalMetadata
    version_info: VersionInfo
    section_heading_text: Optional[str] = None
    section_heading_level: Optional[Union[int, str]] = None

    def __post_init__(self):
        if self.evidence_type not in EVIDENCE_TYPES:
            raise ValueError(f"evidence_type must be one of {sorted(EVIDENCE_TYPES)}, got {self.evidence_type!r}")
        if not isinstance(self.evidence_schema_version, str) or not self.evidence_schema_version.strip():
            raise ValueError("evidence_schema_version must be a non-empty string")
        if not isinstance(self.evidence_id, str) or not self.evidence_id.strip():
            raise ValueError("evidence_id must be a non-empty string")
        if not isinstance(self.evidence_text, str) or not self.evidence_text.strip():
            raise ValueError("evidence_text must be a non-empty string")
        if not isinstance(self.evidence_text_hash, str) or len(self.evidence_text_hash) != 64:
            raise ValueError("evidence_text_hash must be a 64-character SHA-256 hex digest")
        for name in ("chunk_id", "document_id", "source_family_id", "jurisdiction"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.content_hash, str) or len(self.content_hash) != 64:
            raise ValueError("content_hash must be a 64-character SHA-256 hex digest")
        if not isinstance(self.synthetic, bool):
            raise ValueError("synthetic must be a bool")
        if not self.page_numbers:
            raise ValueError("page_numbers must not be empty - evidence must never be an orphaned fragment")
        if not self.block_ids:
            raise ValueError("block_ids must not be empty - evidence must never be an orphaned fragment")
        if not isinstance(self.retrieval_metadata, RetrievalMetadata):
            raise ValueError("retrieval_metadata must be a RetrievalMetadata instance")
        if not isinstance(self.version_info, VersionInfo):
            raise ValueError("version_info must be a VersionInfo instance")

    @property
    def source_location(self) -> SourceLocation:
        return SourceLocation(
            document_id=self.document_id,
            source_family_id=self.source_family_id,
            jurisdiction=self.jurisdiction,
            content_hash=self.content_hash,
            page_numbers=self.page_numbers,
            block_ids=self.block_ids,
            section_heading_text=self.section_heading_text,
            section_heading_level=self.section_heading_level,
        )


@dataclass(frozen=True)
class CitationTarget:
    """
    Points to exactly one Evidence ID (docs Section L). Contains no
    invented source data of its own - resolving it (builder.resolve_citation_target)
    always looks the ID up in a real EvidencePack. Phase 8 stops here:
    validating a GENERATED ANSWER's citation against this target is
    Phase 9's job, not implemented anywhere in this repository.
    """

    evidence_id: str
    schema_version: str = "1.0.0"

    def __post_init__(self):
        if not isinstance(self.evidence_id, str) or not self.evidence_id.strip():
            raise ValueError("evidence_id must be a non-empty string")
        if not isinstance(self.schema_version, str) or not self.schema_version.strip():
            raise ValueError("schema_version must be a non-empty string")


@dataclass(frozen=True)
class EvidenceSelectionConfig:
    """
    Explicit, documented evidence-selection parameters (docs Section N).
    `min_score`, when set, filters on the "most refined available" score
    per candidate (reranker_score > rrf_score > raw score -
    builder._primary_score) - a pure retrieval-signal filter, never a
    legal relevance threshold.
    """

    max_evidence_items: int = 10
    max_rank: Optional[int] = None
    min_score: Optional[float] = None
    schema_version: str = "1.0.0"

    def __post_init__(self):
        if (
            isinstance(self.max_evidence_items, bool)
            or not isinstance(self.max_evidence_items, int)
            or self.max_evidence_items <= 0
        ):
            raise ValueError(f"max_evidence_items must be a positive integer, got {self.max_evidence_items!r}")
        if self.max_rank is not None and (
            isinstance(self.max_rank, bool) or not isinstance(self.max_rank, int) or self.max_rank < 1
        ):
            raise ValueError(f"max_rank must be a positive integer or None, got {self.max_rank!r}")
        if self.min_score is not None and (
            isinstance(self.min_score, bool)
            or not isinstance(self.min_score, (int, float))
            or not math.isfinite(self.min_score)
        ):
            raise ValueError(f"min_score must be a finite number or None, got {self.min_score!r}")
        if not isinstance(self.schema_version, str) or not self.schema_version.strip():
            raise ValueError("schema_version must be a non-empty string")

    @property
    def signature(self) -> str:
        return (
            f"evidence-selection-config:v{self.schema_version}:"
            f"max_items={self.max_evidence_items}:max_rank={self.max_rank}:min_score={self.min_score}"
        )


@dataclass(frozen=True)
class EvidencePack:
    """
    The final Phase 8 deliverable (docs Section M). Contains actual
    Evidence objects only - never a generated answer, a generated claim,
    LLM reasoning, or a hallucinated citation. `pack_id` IS the
    deterministic identity/signature described in docs Section X, computed
    from `schema_version` + `query` + ordered evidence IDs + the
    construction config's own signature - satisfying both the "pack_id"
    and "deterministic signature" requirements with a single field rather
    than two redundant ones.
    """

    pack_id: str
    schema_version: str
    query: str
    evidence_items: list
    construction_metadata: dict

    def __post_init__(self):
        if not isinstance(self.pack_id, str) or not self.pack_id.strip():
            raise ValueError("pack_id must be a non-empty string")
        if not isinstance(self.schema_version, str) or not self.schema_version.strip():
            raise ValueError("schema_version must be a non-empty string")
        if not isinstance(self.query, str):
            raise ValueError("query must be a string")
        evidence_ids = [e.evidence_id for e in self.evidence_items]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("EvidencePack must not contain duplicate evidence_id values")
        chunk_ids = [e.chunk_id for e in self.evidence_items]
        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError("EvidencePack must not contain duplicate underlying chunk_id values")

    @property
    def jurisdictions(self) -> frozenset:
        """Derived, non-stored summary of distinct jurisdictions represented (docs Section S)."""
        return frozenset(e.jurisdiction for e in self.evidence_items)

    @property
    def source_family_ids(self) -> frozenset:
        return frozenset(e.source_family_id for e in self.evidence_items)
