"""
Phase 8 tests: core Evidence/EvidencePack construction - candidate ->
Evidence, EvidencePack from candidate lists, selection config behavior
(docs/PHASE_08_EVIDENCE_OBJECT_AND_CITATION_ARCHITECTURE.md Sections G, M, N).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _evidence_fixtures import make_hybrid_response, make_single_chunk

from evidence.builder import build_evidence_from_candidate, build_evidence_pack
from evidence.models import EVIDENCE_TYPES, CitationTarget, Evidence, EvidencePack, EvidenceSelectionConfig

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# build_evidence_from_candidate
# ---------------------------------------------------------------------------


def test_build_evidence_from_single_candidate(authority_matrix):
    chunk = make_single_chunk("Trademark registration application process.", "D1", authority_matrix)
    resp = make_hybrid_response([chunk], "trademark registration", top_k=1)
    candidate = resp.results[0]

    evidence = build_evidence_from_candidate(candidate)
    assert isinstance(evidence, Evidence)
    assert evidence.evidence_type in EVIDENCE_TYPES
    assert evidence.evidence_text == candidate.chunk_text
    assert evidence.chunk_id == candidate.chunk_id
    assert evidence.document_id == candidate.document_id


def test_evidence_never_contains_legal_conclusion_fields(authority_matrix):
    chunk = make_single_chunk("Patent application content.", "D1", authority_matrix)
    resp = make_hybrid_response([chunk], "patent application", top_k=1)
    evidence = build_evidence_from_candidate(resp.results[0])
    field_names = {f.name for f in __import__("dataclasses").fields(Evidence)}
    forbidden = {"legal_conclusion", "answer", "claim", "recommendation", "interpretation"}
    assert field_names.isdisjoint(forbidden)


def test_build_evidence_rejects_candidate_missing_required_attributes():
    class BadCandidate:
        chunk_id = "X"
        # missing everything else

    with pytest.raises(ValueError):
        build_evidence_from_candidate(BadCandidate())


def test_build_evidence_rejects_bare_chunk_object(authority_matrix):
    chunk = make_single_chunk("Some content.", "D1", authority_matrix)
    # a bare Phase 4 Chunk has no `.rank` or `.chunk_text` (it has `.text`) -
    # build_evidence_from_candidate must reject it with a clear error,
    # never silently guess.
    with pytest.raises(ValueError):
        build_evidence_from_candidate(chunk)


# ---------------------------------------------------------------------------
# build_evidence_pack
# ---------------------------------------------------------------------------


def test_build_evidence_pack_from_multiple_candidates(authority_matrix):
    chunks = [
        make_single_chunk("Trademark registration process.", "D1", authority_matrix),
        make_single_chunk("Patent filing specification.", "D2", authority_matrix),
        make_single_chunk("Ayurveda formulation rules.", "D3", authority_matrix),
    ]
    resp = make_hybrid_response(chunks, "trademark patent formulation", top_k=3)
    pack = build_evidence_pack(resp.results, "trademark patent formulation")

    assert isinstance(pack, EvidencePack)
    assert len(pack.evidence_items) == 3
    assert pack.query == "trademark patent formulation"


def test_evidence_pack_respects_max_evidence_items(authority_matrix):
    chunks = [make_single_chunk(f"Trademark document {i}.", f"D-{i}", authority_matrix) for i in range(5)]
    resp = make_hybrid_response(chunks, "trademark", top_k=5)
    pack = build_evidence_pack(resp.results, "trademark", EvidenceSelectionConfig(max_evidence_items=2))
    assert len(pack.evidence_items) == 2


def test_evidence_pack_respects_max_rank(authority_matrix):
    chunks = [make_single_chunk(f"Trademark document {i}.", f"D-MR-{i}", authority_matrix) for i in range(5)]
    resp = make_hybrid_response(chunks, "trademark", top_k=5)
    pack = build_evidence_pack(resp.results, "trademark", EvidenceSelectionConfig(max_evidence_items=10, max_rank=2))
    assert len(pack.evidence_items) <= 2
    for evidence in pack.evidence_items:
        assert evidence.retrieval_metadata.rank <= 2


def test_evidence_pack_empty_candidate_list_produces_empty_pack():
    pack = build_evidence_pack([], "no results query")
    assert pack.evidence_items == []


def test_evidence_selection_config_rejects_non_positive_max_items():
    with pytest.raises(ValueError):
        EvidenceSelectionConfig(max_evidence_items=0)
    with pytest.raises(ValueError):
        EvidenceSelectionConfig(max_evidence_items=-1)


def test_evidence_selection_config_rejects_invalid_max_rank():
    with pytest.raises(ValueError):
        EvidenceSelectionConfig(max_rank=0)
    with pytest.raises(ValueError):
        EvidenceSelectionConfig(max_rank=-5)


def test_evidence_selection_config_rejects_non_finite_min_score():
    with pytest.raises(ValueError):
        EvidenceSelectionConfig(min_score=float("nan"))
    with pytest.raises(ValueError):
        EvidenceSelectionConfig(min_score=float("inf"))


def test_build_evidence_pack_rejects_non_list_candidates():
    with pytest.raises(TypeError):
        build_evidence_pack("not a list", "query")


def test_build_evidence_pack_rejects_non_string_query(authority_matrix):
    chunk = make_single_chunk("Some content.", "D1", authority_matrix)
    resp = make_hybrid_response([chunk], "content", top_k=1)
    with pytest.raises(TypeError):
        build_evidence_pack(resp.results, 12345)


def test_build_evidence_pack_rejects_wrong_config_type(authority_matrix):
    chunk = make_single_chunk("Some content.", "D1", authority_matrix)
    resp = make_hybrid_response([chunk], "content", top_k=1)
    with pytest.raises(TypeError):
        build_evidence_pack(resp.results, "content", config="not a config")


# ---------------------------------------------------------------------------
# CitationTarget
# ---------------------------------------------------------------------------


def test_citation_target_rejects_empty_evidence_id():
    with pytest.raises(ValueError):
        CitationTarget(evidence_id="")
    with pytest.raises(ValueError):
        CitationTarget(evidence_id="   ")
