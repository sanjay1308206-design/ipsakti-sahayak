"""
Phase 8 tests: serialization round-trip safety - Evidence, EvidencePack,
CitationTarget (docs/PHASE_08_EVIDENCE_OBJECT_AND_CITATION_ARCHITECTURE.md
Section W).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from _evidence_fixtures import make_hybrid_response, make_single_chunk

from evidence.builder import build_evidence_from_candidate, build_evidence_pack
from evidence.models import CitationTarget, EvidenceIntegrityError
from evidence.serialize import (
    citation_target_from_dict,
    citation_target_to_dict,
    evidence_from_dict,
    evidence_pack_from_dict,
    evidence_pack_to_dict,
    evidence_pack_to_json,
    evidence_to_dict,
    evidence_to_json,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Evidence round-trip
# ---------------------------------------------------------------------------


def test_evidence_round_trips_through_dict(authority_matrix):
    chunk = make_single_chunk("Trademark registration serialization content.", "D-SER-1", authority_matrix)
    resp = make_hybrid_response([chunk], "trademark registration serialization", top_k=1)
    evidence = build_evidence_from_candidate(resp.results[0])

    reloaded = evidence_from_dict(evidence_to_dict(evidence))
    assert reloaded.evidence_id == evidence.evidence_id
    assert reloaded.evidence_text == evidence.evidence_text
    assert reloaded.chunk_id == evidence.chunk_id
    assert reloaded.retrieval_metadata == evidence.retrieval_metadata
    assert reloaded.version_info == evidence.version_info


def test_evidence_json_is_valid_json_and_round_trips(authority_matrix):
    chunk = make_single_chunk("Trademark registration JSON content.", "D-SER-2", authority_matrix)
    resp = make_hybrid_response([chunk], "trademark registration json", top_k=1)
    evidence = build_evidence_from_candidate(resp.results[0])

    json_str = evidence_to_json(evidence)
    parsed = json.loads(json_str)
    reloaded = evidence_from_dict(parsed["content"])
    assert reloaded.evidence_id == evidence.evidence_id


def test_evidence_from_dict_rejects_missing_field(authority_matrix):
    chunk = make_single_chunk("Content.", "D-SER-3", authority_matrix)
    resp = make_hybrid_response([chunk], "content", top_k=1)
    evidence = build_evidence_from_candidate(resp.results[0])
    data = evidence_to_dict(evidence)
    del data["chunk_id"]
    with pytest.raises(EvidenceIntegrityError):
        evidence_from_dict(data)


def test_evidence_from_dict_rejects_tampered_text_hash(authority_matrix):
    chunk = make_single_chunk("Content for tamper test.", "D-SER-4", authority_matrix)
    resp = make_hybrid_response([chunk], "content for tamper test", top_k=1)
    evidence = build_evidence_from_candidate(resp.results[0])
    data = evidence_to_dict(evidence)
    data["evidence_text"] = "This text was swapped after hashing."
    with pytest.raises(EvidenceIntegrityError):
        evidence_from_dict(data)


def test_evidence_from_dict_rejects_forged_evidence_id(authority_matrix):
    chunk = make_single_chunk("Content for forged id test.", "D-SER-5", authority_matrix)
    resp = make_hybrid_response([chunk], "content forged id test", top_k=1)
    evidence = build_evidence_from_candidate(resp.results[0])
    data = evidence_to_dict(evidence)
    data["evidence_id"] = "f" * 64
    with pytest.raises(EvidenceIntegrityError):
        evidence_from_dict(data)


def test_evidence_from_dict_rejects_malformed_json_structure():
    with pytest.raises(EvidenceIntegrityError):
        evidence_from_dict({"not": "a valid evidence dict"})
    with pytest.raises(EvidenceIntegrityError):
        evidence_from_dict({"evidence_id": "x" * 64})  # missing everything else


# ---------------------------------------------------------------------------
# EvidencePack round-trip
# ---------------------------------------------------------------------------


def test_evidence_pack_round_trips_through_dict(authority_matrix):
    chunks = [
        make_single_chunk("Trademark registration pack content.", "D-PACK-1", authority_matrix),
        make_single_chunk("Patent filing pack content.", "D-PACK-2", authority_matrix),
    ]
    resp = make_hybrid_response(chunks, "trademark patent", top_k=2)
    pack = build_evidence_pack(resp.results, "trademark patent")

    reloaded = evidence_pack_from_dict(evidence_pack_to_dict(pack))
    assert reloaded.pack_id == pack.pack_id
    assert len(reloaded.evidence_items) == len(pack.evidence_items)
    assert [e.evidence_id for e in reloaded.evidence_items] == [e.evidence_id for e in pack.evidence_items]


def test_evidence_pack_json_round_trips(authority_matrix):
    chunk = make_single_chunk("Trademark registration pack JSON content.", "D-PACK-JSON", authority_matrix)
    resp = make_hybrid_response([chunk], "trademark registration pack json", top_k=1)
    pack = build_evidence_pack(resp.results, "trademark registration pack json")

    json_str = evidence_pack_to_json(pack)
    parsed = json.loads(json_str)
    reloaded = evidence_pack_from_dict(parsed["content"])
    assert reloaded.pack_id == pack.pack_id


def test_evidence_pack_from_dict_rejects_tampered_pack_id(authority_matrix):
    chunk = make_single_chunk("Content for pack tamper test.", "D-PACK-TAMPER", authority_matrix)
    resp = make_hybrid_response([chunk], "content pack tamper test", top_k=1)
    pack = build_evidence_pack(resp.results, "content pack tamper test")
    data = evidence_pack_to_dict(pack)
    data["pack_id"] = "0" * 64
    with pytest.raises(EvidenceIntegrityError):
        evidence_pack_from_dict(data)


def test_evidence_pack_from_dict_rejects_tampered_query(authority_matrix):
    chunk = make_single_chunk("Content for pack query tamper test.", "D-PACK-QUERY-TAMPER", authority_matrix)
    resp = make_hybrid_response([chunk], "content pack query tamper test", top_k=1)
    pack = build_evidence_pack(resp.results, "content pack query tamper test")
    data = evidence_pack_to_dict(pack)
    data["query"] = "a different query entirely"
    with pytest.raises(EvidenceIntegrityError):
        evidence_pack_from_dict(data)


def test_evidence_pack_from_dict_rejects_missing_evidence_items_key():
    with pytest.raises(EvidenceIntegrityError):
        evidence_pack_from_dict({"pack_id": "x" * 64, "schema_version": "1.0.0", "query": "q", "construction_metadata": {}})


def test_evidence_pack_from_dict_propagates_item_level_tampering(authority_matrix):
    chunk = make_single_chunk("Content for item level tamper.", "D-ITEM-TAMPER", authority_matrix)
    resp = make_hybrid_response([chunk], "content item level tamper", top_k=1)
    pack = build_evidence_pack(resp.results, "content item level tamper")
    data = evidence_pack_to_dict(pack)
    data["evidence_items"][0]["evidence_text"] = "Swapped text inside the pack."
    with pytest.raises(EvidenceIntegrityError):
        evidence_pack_from_dict(data)


# ---------------------------------------------------------------------------
# CitationTarget round-trip
# ---------------------------------------------------------------------------


def test_citation_target_round_trips():
    target = CitationTarget(evidence_id="a" * 64)
    reloaded = citation_target_from_dict(citation_target_to_dict(target))
    assert reloaded.evidence_id == target.evidence_id
    assert reloaded.schema_version == target.schema_version


def test_citation_target_from_dict_rejects_missing_field():
    with pytest.raises(EvidenceIntegrityError):
        citation_target_from_dict({"schema_version": "1.0.0"})
