"""
Phase 8 tests: deterministic evidence/pack construction - repeated
construction, ordering, byte-identical serialized JSON
(docs/PHASE_08_EVIDENCE_OBJECT_AND_CITATION_ARCHITECTURE.md Section P).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _evidence_fixtures import make_hybrid_response, make_single_chunk

from evidence.builder import build_evidence_from_candidate, build_evidence_pack
from evidence.models import EvidenceSelectionConfig
from evidence.serialize import evidence_pack_to_json, evidence_to_json

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def _sample_candidates(authority_matrix):
    chunks = [
        make_single_chunk("Trademark registration process explained in detail.", "D-DET-1", authority_matrix),
        make_single_chunk("Patent filing requires a detailed specification document.", "D-DET-2", authority_matrix),
        make_single_chunk("Ayurveda formulation compliance with AYUSH rules.", "D-DET-3", authority_matrix),
    ]
    resp = make_hybrid_response(chunks, "trademark patent formulation", top_k=3)
    return resp.results


def test_build_evidence_from_candidate_repeated_calls_produce_identical_json(authority_matrix):
    candidates = _sample_candidates(authority_matrix)
    outputs = {evidence_to_json(build_evidence_from_candidate(candidates[0])) for _ in range(10)}
    assert len(outputs) == 1


def test_build_evidence_pack_repeated_calls_produce_identical_json(authority_matrix):
    candidates = _sample_candidates(authority_matrix)
    outputs = {evidence_pack_to_json(build_evidence_pack(candidates, "trademark patent formulation")) for _ in range(10)}
    assert len(outputs) == 1


def test_evidence_ordering_is_ascending_rank_then_ascending_chunk_id(authority_matrix):
    chunks = [make_single_chunk(f"Trademark document {i}.", f"D-ORDER-{i}", authority_matrix) for i in range(5)]
    resp = make_hybrid_response(chunks, "trademark", top_k=5)
    pack = build_evidence_pack(resp.results, "trademark")
    ranks = [e.retrieval_metadata.rank for e in pack.evidence_items]
    assert ranks == sorted(ranks)


def test_evidence_pack_ordering_is_independent_of_input_candidate_order(authority_matrix):
    chunks = [make_single_chunk(f"Trademark document {i}.", f"D-STABLE-{i}", authority_matrix) for i in range(4)]
    resp = make_hybrid_response(chunks, "trademark", top_k=4)
    forward = build_evidence_pack(list(resp.results), "trademark")
    shuffled = build_evidence_pack(list(reversed(resp.results)), "trademark")
    assert [e.chunk_id for e in forward.evidence_items] == [e.chunk_id for e in shuffled.evidence_items]


def test_full_construction_pipeline_repeated_runs_produce_identical_json(authority_matrix):
    chunks = [
        make_single_chunk("Trademark registration content.", "D-PIPE-1", authority_matrix),
        make_single_chunk("Patent filing content.", "D-PIPE-2", authority_matrix),
    ]
    outputs = set()
    for _ in range(5):
        resp = make_hybrid_response(chunks, "trademark patent", top_k=2)
        pack = build_evidence_pack(resp.results, "trademark patent")
        outputs.add(evidence_pack_to_json(pack))
    assert len(outputs) == 1


def test_different_selection_config_produces_different_but_deterministic_pack(authority_matrix):
    chunks = [make_single_chunk(f"Trademark document {i}.", f"D-CFG-DET-{i}", authority_matrix) for i in range(4)]
    resp = make_hybrid_response(chunks, "trademark", top_k=4)

    config_a = EvidenceSelectionConfig(max_evidence_items=2)
    pack_a1 = build_evidence_pack(resp.results, "trademark", config_a)
    pack_a2 = build_evidence_pack(resp.results, "trademark", config_a)
    assert evidence_pack_to_json(pack_a1) == evidence_pack_to_json(pack_a2)

    config_b = EvidenceSelectionConfig(max_evidence_items=4)
    pack_b = build_evidence_pack(resp.results, "trademark", config_b)
    assert evidence_pack_to_json(pack_a1) != evidence_pack_to_json(pack_b)
