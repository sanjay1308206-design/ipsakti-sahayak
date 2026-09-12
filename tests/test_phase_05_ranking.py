"""
Phase 5 tests: ranking order and deterministic tie-breaking
(docs/PHASE_05_BM25_BASELINE.md Section J).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _bm25_fixtures import make_single_chunk

from retrieval.index import build_index, query
from retrieval.models import Bm25Config

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def test_results_are_sorted_by_descending_score(authority_matrix):
    strong = make_single_chunk("trademark trademark trademark application", "D-STRONG", authority_matrix)
    weak = make_single_chunk("trademark mentioned once in passing", "D-WEAK", authority_matrix)
    idx = build_index([strong, weak])
    resp = query(idx, "trademark", top_k=2)
    scores = [r.score for r in resp.results]
    assert scores == sorted(scores, reverse=True)


def test_identical_score_ties_are_broken_by_ascending_chunk_id(authority_matrix):
    # Two chunks built from byte-identical text produce identical BM25
    # scores for the same query - the tie-break must still be deterministic.
    a = make_single_chunk("Identical wording for a deterministic tie test.", "D-TIE-A", authority_matrix)
    b = make_single_chunk("Identical wording for a deterministic tie test.", "D-TIE-B", authority_matrix)
    idx = build_index([a, b])
    resp = query(idx, "identical wording", top_k=2)
    assert len(resp.results) == 2
    assert resp.results[0].score == resp.results[1].score
    assert [r.chunk_id for r in resp.results] == sorted(r.chunk_id for r in resp.results)


def test_tie_break_order_is_stable_regardless_of_input_list_order(authority_matrix):
    a = make_single_chunk("Stable tie break order test text sample.", "D-STABLE-A", authority_matrix)
    b = make_single_chunk("Stable tie break order test text sample.", "D-STABLE-B", authority_matrix)
    idx_forward = build_index([a, b])
    idx_reversed = build_index([b, a])
    resp_forward = query(idx_forward, "stable tie break", top_k=2)
    resp_reversed = query(idx_reversed, "stable tie break", top_k=2)
    assert [r.chunk_id for r in resp_forward.results] == [r.chunk_id for r in resp_reversed.results]


def test_rank_field_is_one_based_and_contiguous(authority_matrix):
    chunks = [
        make_single_chunk(f"Ranking test document number {i} about licensing.", f"D-RANK-{i}", authority_matrix)
        for i in range(5)
    ]
    idx = build_index(chunks)
    resp = query(idx, "ranking licensing", top_k=5)
    assert [r.rank for r in resp.results] == list(range(1, len(resp.results) + 1))


def test_different_k1_b_parameters_can_change_relative_ranking(authority_matrix):
    # Not asserting a specific direction - only that the parameters are
    # genuinely used (not ignored/hard-coded), by observing scores differ.
    chunk = make_single_chunk("Parameter sensitivity test text repeated repeated repeated.", "D-PARAM", authority_matrix)
    idx_default = build_index([chunk], config=Bm25Config())
    idx_custom = build_index([chunk], config=Bm25Config(k1=0.1, b=0.0))
    resp_default = query(idx_default, "repeated", top_k=1)
    resp_custom = query(idx_custom, "repeated", top_k=1)
    assert resp_default.results[0].score != resp_custom.results[0].score
