"""
Phase 9 tests: per-citation Evidence integrity verification
(docs/PHASE_09_CITATION_VALIDATION.md Section N). Reuses Phase 8's own
tamper-detection functions - these tests prove Phase 9 actually calls
them, not that Phase 8's own hashing works (already tested by Phase 8).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
import yaml
from _citation_fixtures import make_pack_from_texts, make_reference

from evidence.identity import compute_pack_id
from evidence.models import EvidencePack

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def _rebuild_pack_with_replaced_evidence(pack: EvidencePack, index: int, **replacements) -> EvidencePack:
    """
    Replaces one field on one evidence item, WITHOUT touching pack-level
    identity - recomputes pack_id consistently from the (possibly
    changed) evidence_id list, so a test targeting evidence-LEVEL
    tampering (EVIDENCE_INTEGRITY_FAILURE/EVIDENCE_PROVENANCE_FAILURE)
    is not instead caught by the pack-level INVALID_PACK gate, which
    would otherwise fire first whenever `replacements` includes a new
    `evidence_id` (pack_id is itself derived from the evidence_id list).
    """
    items = list(pack.evidence_items)
    items[index] = dataclasses.replace(items[index], **replacements)
    config_signature = pack.construction_metadata["config_signature"]
    new_pack_id = compute_pack_id(pack.schema_version, pack.query, [e.evidence_id for e in items], config_signature)
    return EvidencePack(
        pack_id=new_pack_id,
        schema_version=pack.schema_version,
        query=pack.query,
        evidence_items=items,
        construction_metadata=pack.construction_metadata,
    )


def test_tampered_evidence_text_is_detected_as_integrity_failure(authority_matrix):
    from citation.validator import validate_citation

    pack = make_pack_from_texts([("D-INT-1", "Original trademark content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    tampered_pack = _rebuild_pack_with_replaced_evidence(pack, 0, evidence_text="Swapped content after hashing.")

    result = validate_citation(make_reference(real_id), tampered_pack)
    assert result.status == "INVALID"
    assert result.reason_code == "EVIDENCE_INTEGRITY_FAILURE"
    assert result.resolved_evidence is None


def test_tampered_evidence_text_hash_is_detected(authority_matrix):
    from citation.validator import validate_citation

    pack = make_pack_from_texts([("D-INT-2", "Original patent content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    tampered_pack = _rebuild_pack_with_replaced_evidence(pack, 0, evidence_text_hash="0" * 64)

    result = validate_citation(make_reference(real_id), tampered_pack)
    assert result.status == "INVALID"
    assert result.reason_code == "EVIDENCE_INTEGRITY_FAILURE"


def test_forged_evidence_id_is_detected_as_integrity_failure(authority_matrix):
    from citation.validator import validate_citation

    pack = make_pack_from_texts([("D-INT-3", "Original ayurveda content.")], authority_matrix)
    forged_id = "1" * 64
    tampered_pack = _rebuild_pack_with_replaced_evidence(pack, 0, evidence_id=forged_id)

    result = validate_citation(make_reference(forged_id), tampered_pack)
    assert result.status == "INVALID"
    assert result.reason_code == "EVIDENCE_INTEGRITY_FAILURE"


def test_one_tampered_item_does_not_invalidate_citations_to_other_items(authority_matrix):
    from citation.validator import validate_citation

    pack = make_pack_from_texts(
        [("D-INT-4", "Trademark registration content."), ("D-INT-5", "Patent filing content.")],
        authority_matrix,
    )
    good_id = pack.evidence_items[1].evidence_id
    tampered_pack = _rebuild_pack_with_replaced_evidence(pack, 0, evidence_text="Corrupted content.")

    other_result = validate_citation(make_reference(good_id), tampered_pack)
    assert other_result.status == "VALID"


def test_untampered_evidence_passes_integrity_verification(authority_matrix):
    from citation.validator import validate_citation

    pack = make_pack_from_texts([("D-INT-6", "Genuinely unmodified content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    result = validate_citation(make_reference(real_id), pack)
    assert result.status == "VALID"
