"""
Phase 5 tests: index-build determinism, query determinism, index signature
stability, and serialized index/result determinism
(docs/PHASE_05_BM25_BASELINE.md Section N).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _bm25_fixtures import make_chunks, make_single_chunk

from retrieval.index import build_index, query
from retrieval.models import Bm25Config
from retrieval.serialize import index_to_json, response_to_json

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def _sample_chunks(authority_matrix):
    return [
        make_single_chunk("Trademark registration process explained in detail.", "D-DET-1", authority_matrix),
        make_single_chunk("Patent filing requires a detailed specification document.", "D-DET-2", authority_matrix),
        make_single_chunk("Ayurveda formulation compliance with AYUSH rules.", "D-DET-3", authority_matrix),
    ]


def test_building_the_same_index_twice_produces_identical_statistics(authority_matrix):
    chunks = _sample_chunks(authority_matrix)
    idx1 = build_index(chunks)
    idx2 = build_index(chunks)
    assert idx1.chunk_ids == idx2.chunk_ids
    assert idx1.document_lengths == idx2.document_lengths
    assert idx1.term_document_frequency == idx2.term_document_frequency
    assert idx1.average_document_length == idx2.average_document_length
    assert idx1.signature == idx2.signature


def test_running_the_same_query_twice_produces_identical_response(authority_matrix):
    chunks = _sample_chunks(authority_matrix)
    idx = build_index(chunks)
    resp1 = query(idx, "trademark registration", top_k=3)
    resp2 = query(idx, "trademark registration", top_k=3)
    assert [r.chunk_id for r in resp1.results] == [r.chunk_id for r in resp2.results]
    assert [r.score for r in resp1.results] == [r.score for r in resp2.results]


def test_running_the_same_query_ten_times_produces_byte_identical_json(authority_matrix):
    chunks = _sample_chunks(authority_matrix)
    idx = build_index(chunks)
    outputs = {response_to_json(query(idx, "trademark patent formulation", top_k=3)) for _ in range(10)}
    assert len(outputs) == 1


def test_serialized_index_is_byte_identical_across_rebuilds(authority_matrix):
    chunks = _sample_chunks(authority_matrix)
    outputs = {index_to_json(build_index(chunks)) for _ in range(5)}
    assert len(outputs) == 1


def test_index_signature_changes_when_bm25_parameters_change(authority_matrix):
    chunks = _sample_chunks(authority_matrix)
    idx_default = build_index(chunks, config=Bm25Config())
    idx_custom = build_index(chunks, config=Bm25Config(k1=2.0, b=0.5))
    assert idx_default.signature != idx_custom.signature


def test_index_signature_changes_when_chunk_set_changes(authority_matrix):
    chunks = _sample_chunks(authority_matrix)
    idx_full = build_index(chunks)
    idx_partial = build_index(chunks[:2])
    assert idx_full.signature != idx_partial.signature


def test_index_signature_is_identical_for_identical_chunk_set_and_config(authority_matrix):
    chunks = _sample_chunks(authority_matrix)
    idx1 = build_index(chunks, config=Bm25Config(k1=1.2, b=0.6))
    idx2 = build_index(chunks, config=Bm25Config(k1=1.2, b=0.6))
    assert idx1.signature == idx2.signature


def test_multi_chunk_document_indexing_is_also_deterministic(authority_matrix):
    chunks = make_chunks(
        "1. Heading One\n\nBody one about trademarks.\n\n2. Heading Two\n\nBody two about patents.\n",
        "D-DET-MULTI",
        authority_matrix,
    )
    outputs = {index_to_json(build_index(chunks)) for _ in range(5)}
    assert len(outputs) == 1
