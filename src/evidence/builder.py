"""
Deterministic candidate -> Evidence -> EvidencePack construction
(docs/PHASE_08_EVIDENCE_OBJECT_AND_CITATION_ARCHITECTURE.md Sections G, N,
O, P, Q).

build_evidence_from_candidate(): converts ONE ranked retrieval candidate
(a Phase 5 RetrievalResult, Phase 6 DenseRetrievalResult, Phase 7
RrfResult, or HybridRetrievalResult - or any future type sharing the same
provenance attribute names) into one Evidence object. Never introduces an
LLM. Never rewrites candidate text.

build_evidence_pack(): the only way to construct an EvidencePack. Pure,
deterministic candidate-list -> pack transformation - no network, no
model inference, no randomness.

resolve_citation_target(): looks up a CitationTarget's evidence_id inside
a real EvidencePack. This is as far as Phase 8 goes - validating a
GENERATED ANSWER's citation against this is Phase 9's job.
"""

from __future__ import annotations

import hashlib

from retrieval.models import DenseRetrievalResult, HybridRetrievalResult, RetrievalResult, RrfResult

from .identity import compute_evidence_id, compute_pack_id
from .models import (
    EVIDENCE_SCHEMA_VERSION,
    PACK_SCHEMA_VERSION,
    CitationTarget,
    Evidence,
    EvidenceNotFoundError,
    EvidencePack,
    EvidenceSelectionConfig,
    RetrievalMetadata,
    VersionInfo,
)

REQUIRED_CANDIDATE_ATTRS = (
    "chunk_id",
    "chunk_text",
    "document_id",
    "source_family_id",
    "jurisdiction",
    "content_hash",
    "synthetic",
    "page_numbers",
    "block_ids",
    "rank",
)


def _validate_candidate_shape(candidate) -> None:
    missing = [attr for attr in REQUIRED_CANDIDATE_ATTRS if not hasattr(candidate, attr)]
    if missing:
        raise ValueError(
            f"candidate {candidate!r} is missing required provenance attribute(s): {missing} - "
            f"build_evidence_from_candidate accepts ranked retrieval candidates "
            f"(RetrievalResult/DenseRetrievalResult/RrfResult/HybridRetrievalResult or a "
            f"compatible type), not a bare Phase 4 Chunk"
        )


def _extract_retrieval_metadata(candidate) -> RetrievalMetadata:
    """Type-aware for the four known Phase 5/6/7 result types; falls back to generic duck-typing otherwise."""
    if isinstance(candidate, HybridRetrievalResult):
        return RetrievalMetadata(
            rank=candidate.rank,
            bm25_rank=candidate.bm25_rank,
            bm25_score=candidate.bm25_score,
            dense_rank=candidate.dense_rank,
            dense_score=candidate.dense_score,
            rrf_score=candidate.rrf_score,
            reranker_score=candidate.reranker_score,
            reranker_model_identity=candidate.reranker_model_identity,
        )
    if isinstance(candidate, RrfResult):
        return RetrievalMetadata(
            rank=candidate.rank,
            bm25_rank=candidate.bm25_rank,
            bm25_score=candidate.bm25_score,
            dense_rank=candidate.dense_rank,
            dense_score=candidate.dense_score,
            rrf_score=candidate.rrf_score,
        )
    if isinstance(candidate, DenseRetrievalResult):
        return RetrievalMetadata(
            rank=candidate.rank,
            dense_rank=candidate.rank,
            dense_score=candidate.score,
            dense_model_identity=candidate.model_identity,
        )
    if isinstance(candidate, RetrievalResult):
        return RetrievalMetadata(rank=candidate.rank, bm25_rank=candidate.rank, bm25_score=candidate.score)

    # Unknown candidate type - generic fallback, per "design around stable
    # provenance, not retrieval-specific implementation details": capture
    # whatever standard-named fields happen to exist, fabricate nothing.
    return RetrievalMetadata(
        rank=candidate.rank,
        bm25_rank=getattr(candidate, "bm25_rank", None),
        bm25_score=getattr(candidate, "bm25_score", None),
        dense_rank=getattr(candidate, "dense_rank", None),
        dense_score=getattr(candidate, "dense_score", None),
        dense_model_identity=getattr(candidate, "model_identity", None),
        rrf_score=getattr(candidate, "rrf_score", None),
        reranker_score=getattr(candidate, "reranker_score", None),
        reranker_model_identity=getattr(candidate, "reranker_model_identity", None),
    )


def _primary_score(candidate):
    """The most-refined available score, in pipeline-sophistication order. Never a legal relevance measure."""
    for attr in ("reranker_score", "rrf_score", "score"):
        value = getattr(candidate, attr, None)
        if value is not None:
            return value
    return None


def build_evidence_from_candidate(candidate, schema_version: str = EVIDENCE_SCHEMA_VERSION) -> Evidence:
    _validate_candidate_shape(candidate)

    text = candidate.chunk_text
    if not isinstance(text, str) or not text.strip():
        raise ValueError("candidate.chunk_text must be a non-empty string")

    chunk_id = candidate.chunk_id
    document_id = candidate.document_id
    source_family_id = candidate.source_family_id
    jurisdiction = candidate.jurisdiction
    content_hash = candidate.content_hash
    synthetic = candidate.synthetic
    page_numbers = list(candidate.page_numbers)
    block_ids = list(candidate.block_ids)

    for name, value in (
        ("chunk_id", chunk_id),
        ("document_id", document_id),
        ("source_family_id", source_family_id),
        ("jurisdiction", jurisdiction),
        ("content_hash", content_hash),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"candidate.{name} must be a non-empty string")
    if not isinstance(synthetic, bool):
        raise ValueError("candidate.synthetic must be a bool")
    if not page_numbers:
        raise ValueError("candidate.page_numbers must not be empty")
    if not block_ids:
        raise ValueError("candidate.block_ids must not be empty")

    evidence_text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    evidence_id = compute_evidence_id(
        schema_version, chunk_id, content_hash, document_id, source_family_id, jurisdiction, block_ids, page_numbers
    )

    return Evidence(
        evidence_id=evidence_id,
        evidence_schema_version=schema_version,
        evidence_type="CHUNK",
        evidence_text=text,
        evidence_text_hash=evidence_text_hash,
        chunk_id=chunk_id,
        document_id=document_id,
        source_family_id=source_family_id,
        jurisdiction=jurisdiction,
        content_hash=content_hash,
        synthetic=synthetic,
        page_numbers=page_numbers,
        block_ids=block_ids,
        retrieval_metadata=_extract_retrieval_metadata(candidate),
        version_info=VersionInfo(),  # always "not available" - see VersionInfo docstring
        section_heading_text=getattr(candidate, "section_heading_text", None),
        section_heading_level=getattr(candidate, "section_heading_level", None),
    )


def build_evidence_pack(candidates: list, query: str, config: EvidenceSelectionConfig = None) -> EvidencePack:
    """
    Deterministically converts a list of ranked retrieval candidates into
    an EvidencePack: validate -> deduplicate by chunk_id (first occurrence,
    by input order, wins) -> apply max_rank/min_score filters -> sort by
    (rank, chunk_id) -> truncate to max_evidence_items -> build Evidence
    objects -> compute pack_id.
    """
    if not isinstance(candidates, list):
        raise TypeError(f"build_evidence_pack expects a list of candidates, got {type(candidates).__name__}")
    if not isinstance(query, str):
        raise TypeError(f"build_evidence_pack expects query to be str, got {type(query).__name__}")
    if config is None:
        config = EvidenceSelectionConfig()
    elif not isinstance(config, EvidenceSelectionConfig):
        raise TypeError(f"config must be an EvidenceSelectionConfig, got {type(config).__name__}")

    for candidate in candidates:
        _validate_candidate_shape(candidate)

    seen_chunk_ids = set()
    deduplicated = []
    dropped_duplicate_count = 0
    for candidate in candidates:
        if candidate.chunk_id in seen_chunk_ids:
            dropped_duplicate_count += 1
            continue
        seen_chunk_ids.add(candidate.chunk_id)
        deduplicated.append(candidate)

    if config.max_rank is not None:
        deduplicated = [c for c in deduplicated if c.rank <= config.max_rank]

    if config.min_score is not None:
        deduplicated = [
            c for c in deduplicated if _primary_score(c) is not None and _primary_score(c) >= config.min_score
        ]

    # Deterministic ordering (docs Section P): ascending rank, then
    # ascending chunk_id - never insertion order alone.
    deduplicated.sort(key=lambda c: (c.rank, c.chunk_id))

    selected = deduplicated[: config.max_evidence_items]
    evidence_items = [build_evidence_from_candidate(c) for c in selected]
    evidence_ids = [e.evidence_id for e in evidence_items]

    config_signature = config.signature
    pack_id = compute_pack_id(PACK_SCHEMA_VERSION, query, evidence_ids, config_signature)

    construction_metadata = {
        "candidate_count": len(candidates),
        "dropped_duplicate_chunk_id_count": dropped_duplicate_count,
        "after_filter_count": len(deduplicated),
        "selected_count": len(selected),
        "max_evidence_items": config.max_evidence_items,
        "max_rank": config.max_rank,
        "min_score": config.min_score,
        "config_signature": config_signature,
    }

    return EvidencePack(
        pack_id=pack_id,
        schema_version=PACK_SCHEMA_VERSION,
        query=query,
        evidence_items=evidence_items,
        construction_metadata=construction_metadata,
    )


def resolve_citation_target(citation_target: CitationTarget, pack: EvidencePack) -> Evidence:
    if not isinstance(citation_target, CitationTarget):
        raise TypeError(f"resolve_citation_target expects a CitationTarget, got {type(citation_target).__name__}")
    if not isinstance(pack, EvidencePack):
        raise TypeError(f"resolve_citation_target expects an EvidencePack, got {type(pack).__name__}")
    for evidence in pack.evidence_items:
        if evidence.evidence_id == citation_target.evidence_id:
            return evidence
    raise EvidenceNotFoundError(
        f"citation target references evidence_id {citation_target.evidence_id!r} not present in this "
        f"EvidencePack - possible fabricated evidence ID"
    )
