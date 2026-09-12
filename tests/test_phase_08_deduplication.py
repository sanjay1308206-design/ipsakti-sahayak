"""
Phase 8 tests: evidence deduplication - the same underlying chunk_id,
retrieved through multiple retrieval signals, must map to exactly one
Evidence identity within one pack construction
(docs/PHASE_08_EVIDENCE_OBJECT_AND_CITATION_ARCHITECTURE.md Section O).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _evidence_fixtures import (
    make_bm25_response,
    make_dense_response,
    make_hybrid_response,
    make_rrf_response,
    make_single_chunk,
)

from evidence.builder import build_evidence_pack
from evidence.models import EvidenceSelectionConfig

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def test_normal_hybrid_response_has_no_duplicates_to_drop(authority_matrix):
    # Phase 7's own RRF fusion already guarantees one candidate per
    # chunk_id - the dedup logic in build_evidence_pack should be a no-op
    # for the normal pipeline.
    chunks = [
        make_single_chunk("Trademark registration content.", "D1", authority_matrix),
        make_single_chunk("Patent filing content.", "D2", authority_matrix),
        make_single_chunk("Ayurveda formulation content.", "D3", authority_matrix),
    ]
    resp = make_hybrid_response(chunks, "trademark patent formulation", top_k=3)
    pack = build_evidence_pack(resp.results, "trademark patent formulation")
    assert pack.construction_metadata["dropped_duplicate_chunk_id_count"] == 0
    assert len(pack.evidence_items) == len(resp.results)


def test_mixed_bm25_and_dense_candidates_for_same_chunk_deduplicate(authority_matrix):
    chunks = [
        make_single_chunk("Trademark registration procedure content.", "D1", authority_matrix),
        make_single_chunk("Patent filing specification content.", "D2", authority_matrix),
    ]
    bm25_resp = make_bm25_response(chunks, "trademark registration patent filing", top_k=5)
    dense_resp = make_dense_response(chunks, "trademark registration patent filing", top_k=5)

    # Both lists likely contain BOTH chunks (dense always returns
    # everything; bm25 returns whatever has nonzero term overlap) -
    # combine them directly (bypassing RRF) to force real duplication.
    mixed_candidates = list(bm25_resp.results) + list(dense_resp.results)
    real_chunk_ids = {c.chunk_id for c in chunks}
    assert len(mixed_candidates) > len(real_chunk_ids)  # sanity: genuine duplication present

    pack = build_evidence_pack(mixed_candidates, "trademark registration patent filing", EvidenceSelectionConfig(max_evidence_items=10))
    resulting_chunk_ids = {e.chunk_id for e in pack.evidence_items}
    assert resulting_chunk_ids == real_chunk_ids
    assert len(pack.evidence_items) == len(real_chunk_ids)
    assert pack.construction_metadata["dropped_duplicate_chunk_id_count"] == len(mixed_candidates) - len(real_chunk_ids)


def test_first_occurrence_wins_for_duplicate_chunk_id(authority_matrix):
    chunk = make_single_chunk("Trademark registration content.", "D1", authority_matrix)
    bm25_resp = make_bm25_response([chunk], "trademark registration", top_k=1)
    dense_resp = make_dense_response([chunk], "trademark registration", top_k=1)

    # bm25 candidate first, dense candidate second (same chunk_id) - bm25's
    # retrieval metadata should win (first occurrence wins).
    mixed = [bm25_resp.results[0], dense_resp.results[0]]
    pack = build_evidence_pack(mixed, "trademark registration")
    assert len(pack.evidence_items) == 1
    evidence = pack.evidence_items[0]
    assert evidence.retrieval_metadata.bm25_rank is not None
    assert evidence.retrieval_metadata.dense_rank is None  # dense occurrence was dropped, not merged


def test_deduplication_never_merges_different_chunks_with_similar_text(authority_matrix):
    a = make_single_chunk("Trademark registration content is here.", "D-SIM-A", authority_matrix)
    b = make_single_chunk("Trademark registration content is here.", "D-SIM-B", authority_matrix)
    resp = make_hybrid_response([a, b], "trademark registration content", top_k=2)
    pack = build_evidence_pack(resp.results, "trademark registration content")
    # two genuinely distinct chunk_ids, even with identical text - never merged
    assert len(pack.evidence_items) == 2
    chunk_ids = {e.chunk_id for e in pack.evidence_items}
    assert chunk_ids == {a.chunk_id, b.chunk_id}


def test_rrf_stage_candidates_deduplicate_correctly(authority_matrix):
    chunks = [
        make_single_chunk("Trademark registration and patent filing both mentioned.", "D-BOTH", authority_matrix),
        make_single_chunk("Only trademark registration mentioned here.", "D-BM25-ONLY", authority_matrix),
    ]
    rrf_resp = make_rrf_response(chunks, "trademark registration patent filing", top_k=5, candidate_k=5)
    pack = build_evidence_pack(rrf_resp.results, "trademark registration patent filing")
    chunk_ids = [e.chunk_id for e in pack.evidence_items]
    assert len(chunk_ids) == len(set(chunk_ids))


def test_deduplication_count_is_reported_in_construction_metadata(authority_matrix):
    chunk = make_single_chunk("Trademark content for dedup metadata test.", "D-META", authority_matrix)
    bm25_resp = make_bm25_response([chunk], "trademark content dedup metadata", top_k=1)
    dense_resp = make_dense_response([chunk], "trademark content dedup metadata", top_k=1)
    mixed = [bm25_resp.results[0], dense_resp.results[0], bm25_resp.results[0]]  # triple up
    pack = build_evidence_pack(mixed, "trademark content dedup metadata")
    assert len(pack.evidence_items) == 1
    assert pack.construction_metadata["dropped_duplicate_chunk_id_count"] == 2
    assert pack.construction_metadata["candidate_count"] == 3
