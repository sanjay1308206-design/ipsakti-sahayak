"""
Reciprocal Rank Fusion (docs/PHASE_07_HYBRID_FUSION_AND_RERANKING.md
Sections F, G, H, I, J, K).

fuse_rrf(): the only way to combine a Phase 5 BM25 RetrievalResponse and a
Phase 6 DenseRetrievalResponse into one RRF-ranked candidate set. Pure
function, no I/O, no model loading, no reranking here (see reranker.py/
hybrid.py).

RRF_score(d) = sum over retrieval lists L containing d of 1/(k + rank_L(d))

`rank_L(d)` is always the 1-based rank the contributing retrieval system's
own result contract already assigned - RRF never re-derives, renumbers, or
guesses a rank. `k` is `RrfConfig.k`, never a hidden magic constant.

RRF_score is a rank-fusion signal ONLY. It is NOT legal confidence,
regulatory authority, citation validity, or factual correctness.
"""

from __future__ import annotations

import math

from .models import DenseRetrievalResponse, RetrievalResponse, RrfConfig, RrfResult, RrfResponse

_PROVENANCE_FIELDS = (
    "document_id",
    "source_family_id",
    "jurisdiction",
    "content_hash",
    "synthetic",
    "page_numbers",
    "block_ids",
    "chunk_text",
)


def _validate_response_type(response, expected_type, name: str) -> None:
    if not isinstance(response, expected_type):
        raise TypeError(f"{name} must be a {expected_type.__name__}, got {type(response).__name__}")


def _validate_results_list(results: list, name: str) -> None:
    chunk_ids = [r.chunk_id for r in results]
    if len(chunk_ids) != len(set(chunk_ids)):
        # Duplicate chunk_id WITHIN one input list is treated as malformed
        # retrieval output and rejected outright, per the originating
        # instruction's explicit preference: "prefer rejecting malformed
        # retrieval output rather than silently repairing it." Phase 5's
        # Bm25Index and Phase 6's DenseIndex both already guarantee unique
        # chunk_ids at build time, so a duplicate here can only mean the
        # response object was hand-constructed or corrupted after the fact.
        seen = set()
        duplicates = sorted({cid for cid in chunk_ids if (cid in seen) or seen.add(cid)})
        raise ValueError(f"{name} contains duplicate chunk_id value(s): {duplicates}")
    for result in results:
        if not isinstance(result.rank, int) or isinstance(result.rank, bool) or result.rank < 1:
            raise ValueError(f"{name} contains an invalid rank for chunk_id {result.chunk_id!r}: {result.rank!r}")
        if not isinstance(result.score, (int, float)) or isinstance(result.score, bool) or not math.isfinite(result.score):
            raise ValueError(f"{name} contains a non-finite score for chunk_id {result.chunk_id!r}: {result.score!r}")


def _validate_matching_provenance(bm25_result, dense_result, chunk_id: str) -> None:
    for field_name in _PROVENANCE_FIELDS:
        bm25_value = getattr(bm25_result, field_name)
        dense_value = getattr(dense_result, field_name)
        if bm25_value != dense_value:
            raise ValueError(
                f"chunk_id {chunk_id!r} has mismatched {field_name!r} between the BM25 result "
                f"({bm25_value!r}) and the dense result ({dense_value!r}) - refusing to fuse "
                f"inconsistent provenance for the same identity"
            )


def fuse_rrf(
    bm25_response: RetrievalResponse,
    dense_response: DenseRetrievalResponse,
    candidate_k: int,
    config: RrfConfig = None,
) -> RrfResponse:
    """
    Fuse a BM25 RetrievalResponse and a DenseRetrievalResponse via
    Reciprocal Rank Fusion. `candidate_k` limits the returned candidate
    union to the top `candidate_k` by RRF score (a required, explicit,
    positive integer - mirroring Phase 5/6's own top_k discipline).

    Candidate union: every chunk_id appearing in either input list. If a
    chunk_id appears in both, both retrieval systems' ranks contribute to
    its RRF score and its provenance must match exactly between the two
    (Section J of the originating instruction); if only one, only that
    system contributes. Never generates a new identity - every candidate
    is a real Phase 4 chunk_id already present in one of the two inputs.
    """
    _validate_response_type(bm25_response, RetrievalResponse, "bm25_response")
    _validate_response_type(dense_response, DenseRetrievalResponse, "dense_response")
    if isinstance(candidate_k, bool) or not isinstance(candidate_k, int) or candidate_k <= 0:
        raise ValueError(f"candidate_k must be a positive integer, got {candidate_k!r}")
    if config is None:
        config = RrfConfig()
    if bm25_response.query != dense_response.query:
        raise ValueError(
            f"bm25_response.query {bm25_response.query!r} does not match "
            f"dense_response.query {dense_response.query!r} - refusing to fuse results from different queries"
        )

    _validate_results_list(bm25_response.results, "bm25_response.results")
    _validate_results_list(dense_response.results, "dense_response.results")

    bm25_by_id = {r.chunk_id: r for r in bm25_response.results}
    dense_by_id = {r.chunk_id: r for r in dense_response.results}

    # Union built from both inputs' own chunk_id ordering, not set/dict
    # iteration order, so the union's construction itself stays traceable
    # even though final ordering is decided by the RRF score sort below.
    ordered_candidate_ids = list(dict.fromkeys(
        [r.chunk_id for r in bm25_response.results] + [r.chunk_id for r in dense_response.results]
    ))

    scored_candidates = []
    for chunk_id in ordered_candidate_ids:
        bm25_result = bm25_by_id.get(chunk_id)
        dense_result = dense_by_id.get(chunk_id)

        if bm25_result is not None and dense_result is not None:
            _validate_matching_provenance(bm25_result, dense_result, chunk_id)

        rrf_score = 0.0
        if bm25_result is not None:
            rrf_score += 1.0 / (config.k + bm25_result.rank)
        if dense_result is not None:
            rrf_score += 1.0 / (config.k + dense_result.rank)

        provenance_source = bm25_result if bm25_result is not None else dense_result
        scored_candidates.append((rrf_score, chunk_id, bm25_result, dense_result, provenance_source))

    # Deterministic tie-break (docs Section K): descending RRF score, then
    # ascending chunk_id - never insertion order, random order, or any
    # dict/set-derived order.
    scored_candidates.sort(key=lambda item: (-item[0], item[1]))
    top_candidates = scored_candidates[:candidate_k]

    results = []
    for rank, (rrf_score, chunk_id, bm25_result, dense_result, provenance) in enumerate(top_candidates, start=1):
        results.append(
            RrfResult(
                rank=rank,
                chunk_id=chunk_id,
                rrf_score=rrf_score,
                bm25_rank=bm25_result.rank if bm25_result is not None else None,
                bm25_score=bm25_result.score if bm25_result is not None else None,
                dense_rank=dense_result.rank if dense_result is not None else None,
                dense_score=dense_result.score if dense_result is not None else None,
                document_id=provenance.document_id,
                source_family_id=provenance.source_family_id,
                jurisdiction=provenance.jurisdiction,
                content_hash=provenance.content_hash,
                synthetic=provenance.synthetic,
                page_numbers=provenance.page_numbers,
                block_ids=provenance.block_ids,
                chunk_text=provenance.chunk_text,
            )
        )

    return RrfResponse(
        query=bm25_response.query,
        candidate_k=candidate_k,
        rrf_k=config.k,
        results=results,
    )
