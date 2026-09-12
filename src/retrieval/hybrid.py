"""
Hybrid retrieval orchestration (docs/PHASE_07_HYBRID_FUSION_AND_RERANKING.md
Sections F, L, O, P, Q, R).

rerank_candidates(): reranks an already-fused RrfResponse's candidates with
a loaded Reranker, producing the final HybridRetrievalResponse. Usable
independently of run_hybrid_pipeline() so "RRF alone" vs "RRF + reranker"
can each be measured (docs Section F, architectural principle).

run_hybrid_pipeline(): composes the full target pipeline - BM25 retrieval
-> dense retrieval -> candidate union -> RRF -> reranking - from already
-built Phase 5/6 indexes and a loaded embedding model + reranker. A thin
convenience wrapper; every stage remains independently callable and
independently measurable.

The reranker receives ONLY (query, chunk_text) pairs as data. It never
receives, generates, or is asked to interpret legal conclusions, evidence,
or citations - those remain out of scope for Phase 7 (Phase 8/9/10 own
that architecture).
"""

from __future__ import annotations

import math

from .embeddings import EmbeddingModel
from .faiss_index import DenseIndex, dense_query
from .index import Bm25Index, query as bm25_query
from .models import HybridRetrievalResponse, HybridRetrievalResult, RrfConfig, RrfResponse
from .reranker import Reranker
from .rrf import fuse_rrf


def _validate_reranker_scores(scores, expected_count: int) -> list:
    if len(scores) != expected_count:
        raise ValueError(
            f"reranker.score() returned {len(scores)} score(s), expected {expected_count} "
            f"(one per candidate) - refusing to use a mismatched score list"
        )
    validated = []
    for score in scores:
        value = float(score)
        if not math.isfinite(value):
            raise ValueError(f"reranker.score() produced a non-finite score: {value!r}")
        validated.append(value)
    return validated


def rerank_candidates(rrf_response: RrfResponse, reranker: Reranker, top_k: int) -> HybridRetrievalResponse:
    """
    Rerank every candidate in `rrf_response` (already limited to its own
    `candidate_k` by fuse_rrf) using `reranker`, returning the final
    top `top_k` by reranker score. Never modifies candidate chunk text,
    provenance, or the upstream bm25/dense/rrf scores - it only adds a
    reranker_score and re-sorts.
    """
    if not isinstance(rrf_response, RrfResponse):
        raise TypeError(f"rerank_candidates expects an RrfResponse, got {type(rrf_response).__name__}")
    if not isinstance(reranker, Reranker):
        raise TypeError(f"rerank_candidates expects a Reranker, got {type(reranker).__name__}")
    if not reranker.is_loaded:
        raise RuntimeError("reranker must be loaded (call reranker.load()) before rerank_candidates")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
        raise ValueError(f"top_k must be a positive integer, got {top_k!r}")

    candidates = rrf_response.results
    if not candidates:
        return HybridRetrievalResponse(
            query=rrf_response.query,
            top_k=top_k,
            rrf_k=rrf_response.rrf_k,
            reranker_model_identity=reranker.model_identity,
            results=[],
        )

    candidate_texts = [c.chunk_text for c in candidates]
    raw_scores = reranker.score(rrf_response.query, candidate_texts)
    reranker_scores = _validate_reranker_scores(raw_scores, len(candidates))

    scored = list(zip(reranker_scores, candidates))
    # Deterministic tie-break (docs Section L/R): descending reranker
    # score, then ascending chunk_id - never model output order, dict/set
    # order, or any other unstable ordering.
    scored.sort(key=lambda item: (-item[0], item[1].chunk_id))

    top = scored[:top_k]
    results = []
    for rank, (reranker_score, candidate) in enumerate(top, start=1):
        results.append(
            HybridRetrievalResult(
                rank=rank,
                chunk_id=candidate.chunk_id,
                reranker_score=reranker_score,
                rrf_score=candidate.rrf_score,
                bm25_rank=candidate.bm25_rank,
                bm25_score=candidate.bm25_score,
                dense_rank=candidate.dense_rank,
                dense_score=candidate.dense_score,
                reranker_model_identity=reranker.model_identity,
                document_id=candidate.document_id,
                source_family_id=candidate.source_family_id,
                jurisdiction=candidate.jurisdiction,
                content_hash=candidate.content_hash,
                synthetic=candidate.synthetic,
                page_numbers=candidate.page_numbers,
                block_ids=candidate.block_ids,
                chunk_text=candidate.chunk_text,
            )
        )

    return HybridRetrievalResponse(
        query=rrf_response.query,
        top_k=top_k,
        rrf_k=rrf_response.rrf_k,
        reranker_model_identity=reranker.model_identity,
        results=results,
    )


def run_hybrid_pipeline(
    bm25_index: Bm25Index,
    dense_index: DenseIndex,
    embedding_model: EmbeddingModel,
    reranker: Reranker,
    query_text: str,
    bm25_top_k: int,
    dense_top_k: int,
    candidate_k: int,
    reranker_top_k: int,
    rrf_config: RrfConfig = None,
) -> HybridRetrievalResponse:
    """
    The full target pipeline: BM25 retrieval -> dense retrieval ->
    candidate union -> RRF -> reranking. Every depth parameter
    (`bm25_top_k`, `dense_top_k`, `candidate_k`, `reranker_top_k`) is
    explicit and required - none is a hidden default (docs Section O).
    """
    bm25_response = bm25_query(bm25_index, query_text, bm25_top_k)
    dense_response = dense_query(dense_index, embedding_model, query_text, dense_top_k)
    rrf_response = fuse_rrf(bm25_response, dense_response, candidate_k, config=rrf_config)
    return rerank_candidates(rrf_response, reranker, reranker_top_k)
