"""
Phase 7 tests: RRF and reranking determinism - repeated fusion, repeated
reranking, byte-identical serialized JSON
(docs/PHASE_07_HYBRID_FUSION_AND_RERANKING.md Section K/L/T).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _hybrid_fixtures import make_fake_model, make_fake_reranker, make_single_chunk

from retrieval.faiss_index import build_dense_index, dense_query
from retrieval.hybrid import rerank_candidates, run_hybrid_pipeline
from retrieval.index import build_index, query as bm25_query
from retrieval.models import RrfConfig
from retrieval.rrf import fuse_rrf
from retrieval.serialize import hybrid_response_to_json, rrf_response_to_json

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def _sample_responses(authority_matrix):
    chunks = [
        make_single_chunk("Trademark registration process explained in detail.", "D-DET-1", authority_matrix),
        make_single_chunk("Patent filing requires a detailed specification document.", "D-DET-2", authority_matrix),
        make_single_chunk("Ayurveda formulation compliance with AYUSH rules.", "D-DET-3", authority_matrix),
    ]
    bm25_index = build_index(chunks)
    model = make_fake_model()
    dense_index = build_dense_index(chunks, model)
    bm25_resp = bm25_query(bm25_index, "trademark patent formulation", top_k=3)
    dense_resp = dense_query(dense_index, model, "trademark patent formulation", top_k=3)
    return bm25_resp, dense_resp


def test_fuse_rrf_repeated_calls_produce_identical_results(authority_matrix):
    bm25_resp, dense_resp = _sample_responses(authority_matrix)
    result1 = fuse_rrf(bm25_resp, dense_resp, candidate_k=3)
    result2 = fuse_rrf(bm25_resp, dense_resp, candidate_k=3)
    assert rrf_response_to_json(result1) == rrf_response_to_json(result2)


def test_fuse_rrf_ten_times_produces_byte_identical_json(authority_matrix):
    bm25_resp, dense_resp = _sample_responses(authority_matrix)
    outputs = {rrf_response_to_json(fuse_rrf(bm25_resp, dense_resp, candidate_k=3)) for _ in range(10)}
    assert len(outputs) == 1


def test_rerank_candidates_repeated_calls_produce_identical_results(authority_matrix):
    bm25_resp, dense_resp = _sample_responses(authority_matrix)
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=3)
    reranker = make_fake_reranker()
    result1 = rerank_candidates(rrf_resp, reranker, top_k=3)
    result2 = rerank_candidates(rrf_resp, reranker, top_k=3)
    assert hybrid_response_to_json(result1) == hybrid_response_to_json(result2)


def test_rerank_candidates_ten_times_produces_byte_identical_json(authority_matrix):
    bm25_resp, dense_resp = _sample_responses(authority_matrix)
    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=3)
    reranker = make_fake_reranker()
    outputs = {hybrid_response_to_json(rerank_candidates(rrf_resp, reranker, top_k=3)) for _ in range(10)}
    assert len(outputs) == 1


def test_full_pipeline_repeated_runs_produce_identical_json(authority_matrix):
    chunks = [
        make_single_chunk("Trademark registration process.", "D-PIPE-1", authority_matrix),
        make_single_chunk("Patent filing specification.", "D-PIPE-2", authority_matrix),
    ]
    bm25_index = build_index(chunks)
    model = make_fake_model()
    dense_index = build_dense_index(chunks, model)
    reranker = make_fake_reranker()

    outputs = set()
    for _ in range(5):
        resp = run_hybrid_pipeline(
            bm25_index, dense_index, model, reranker, "trademark patent",
            bm25_top_k=2, dense_top_k=2, candidate_k=2, reranker_top_k=2,
        )
        outputs.add(hybrid_response_to_json(resp))
    assert len(outputs) == 1


def test_rrf_signature_free_but_config_changes_alter_output(authority_matrix):
    # RrfResponse has no separate "signature" field (Phase 7 introduces no
    # new persistence - docs Section T) - but rrf_k itself is recorded and
    # changing it deterministically changes the scores/output.
    bm25_resp, dense_resp = _sample_responses(authority_matrix)
    result_default = fuse_rrf(bm25_resp, dense_resp, candidate_k=3, config=RrfConfig(k=60.0))
    result_custom = fuse_rrf(bm25_resp, dense_resp, candidate_k=3, config=RrfConfig(k=10.0))
    assert rrf_response_to_json(result_default) != rrf_response_to_json(result_custom)
    assert result_default.rrf_k == 60.0
    assert result_custom.rrf_k == 10.0
