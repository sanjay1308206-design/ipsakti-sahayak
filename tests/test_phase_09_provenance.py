"""
Phase 9 tests: provenance preservation on VALID results, and EvidencePack
validation before citation resolution (docs/PHASE_09_CITATION_VALIDATION.md
Sections J, M).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
import yaml
from _citation_fixtures import make_pack_from_texts, make_reference

from citation.validator import check_evidence_pack_validity, validate_citation, validate_citations
from evidence.models import Evidence, EvidencePack

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Provenance survives onto a VALID result's ResolvedEvidenceSummary
# ---------------------------------------------------------------------------


def test_valid_result_preserves_the_full_provenance_chain(authority_matrix):
    pack = make_pack_from_texts([("D-PROV-1", "Trademark provenance content.")], authority_matrix)
    evidence = pack.evidence_items[0]
    result = validate_citation(make_reference(evidence.evidence_id), pack)

    assert result.status == "VALID"
    summary = result.resolved_evidence
    assert summary.evidence_id == evidence.evidence_id
    assert summary.chunk_id == evidence.chunk_id
    assert summary.document_id == evidence.document_id
    assert summary.source_family_id == evidence.source_family_id
    assert summary.jurisdiction == evidence.jurisdiction


def test_result_never_asserts_page_numbers_or_block_ids_directly_but_they_remain_on_evidence(authority_matrix):
    # Phase 9 does not duplicate Evidence's full provenance onto the
    # result (ResolvedEvidenceSummary is a deliberate strict subset,
    # docs Section G) - but the underlying Evidence object (still
    # reachable through the EvidencePack that was validated) still
    # carries them, unmodified.
    pack = make_pack_from_texts([("D-PROV-2", "Patent provenance content.")], authority_matrix)
    evidence = pack.evidence_items[0]
    result = validate_citation(make_reference(evidence.evidence_id), pack)
    assert result.status == "VALID"
    assert not hasattr(result.resolved_evidence, "page_numbers")
    assert not hasattr(result.resolved_evidence, "block_ids")
    assert evidence.page_numbers and evidence.block_ids


# ---------------------------------------------------------------------------
# EvidencePack validation before citation resolution
# ---------------------------------------------------------------------------


def test_forged_pack_id_fails_pack_validation(authority_matrix):
    pack = make_pack_from_texts([("D-PACK-1", "Content.")], authority_matrix)
    forged = dataclasses.replace(pack, pack_id="0" * 64)
    error = check_evidence_pack_validity(forged)
    assert error is not None

    real_id = pack.evidence_items[0].evidence_id
    result = validate_citation(make_reference(real_id), forged)
    assert result.status == "INVALID"
    assert result.reason_code == "INVALID_PACK"


def test_missing_config_signature_fails_pack_validation(authority_matrix):
    pack = make_pack_from_texts([("D-PACK-2", "Content.")], authority_matrix)
    stripped_metadata = dict(pack.construction_metadata)
    del stripped_metadata["config_signature"]
    corrupted = dataclasses.replace(pack, construction_metadata=stripped_metadata)
    assert check_evidence_pack_validity(corrupted) is not None


def test_unsupported_pack_schema_version_fails_pack_validation(authority_matrix):
    pack = make_pack_from_texts([("D-PACK-3", "Content.")], authority_matrix)
    corrupted = dataclasses.replace(pack, schema_version="9.9.9")
    assert check_evidence_pack_validity(corrupted) is not None


def test_invalid_pack_invalidates_every_citation_in_the_batch(authority_matrix):
    pack = make_pack_from_texts(
        [("D-PACK-4", "Trademark content."), ("D-PACK-5", "Patent content.")], authority_matrix
    )
    forged = dataclasses.replace(pack, pack_id="0" * 64)
    real_ids = [e.evidence_id for e in pack.evidence_items]
    refs = [make_reference(rid) for rid in real_ids]
    results = validate_citations(refs, forged)
    assert all(r.status == "INVALID" and r.reason_code == "INVALID_PACK" for r in results)


def test_valid_pack_passes_pack_validation(authority_matrix):
    pack = make_pack_from_texts([("D-PACK-6", "Content.")], authority_matrix)
    assert check_evidence_pack_validity(pack) is None


# ---------------------------------------------------------------------------
# Defensive per-evidence provenance-shape check (EVIDENCE_PROVENANCE_FAILURE)
# ---------------------------------------------------------------------------


def _bypass_construction_evidence(template: Evidence, **overrides) -> Evidence:
    """
    Builds an Evidence-shaped object that skips __post_init__ entirely -
    simulating a hand-corrupted in-memory object that could not have come
    through normal construction. Used ONLY to prove the defensive
    provenance-shape re-check in validator.py actually fires; this is not
    a realistic construction path in the rest of the codebase.
    """
    obj = object.__new__(Evidence)
    for field in dataclasses.fields(template):
        object.__setattr__(obj, field.name, getattr(template, field.name))
    for name, value in overrides.items():
        object.__setattr__(obj, name, value)
    return obj


def test_evidence_with_corrupted_document_id_fails_provenance_check(authority_matrix):
    pack = make_pack_from_texts([("D-PROVFAIL-1", "Content.")], authority_matrix)
    original = pack.evidence_items[0]
    corrupted = _bypass_construction_evidence(original, document_id="   ")
    corrupted_pack = EvidencePack(
        pack_id=pack.pack_id,
        schema_version=pack.schema_version,
        query=pack.query,
        evidence_items=[corrupted],
        construction_metadata=pack.construction_metadata,
    )
    result = validate_citation(make_reference(original.evidence_id), corrupted_pack)
    assert result.status == "INVALID"
    assert result.reason_code == "EVIDENCE_PROVENANCE_FAILURE"


def test_evidence_with_empty_page_numbers_fails_provenance_check(authority_matrix):
    pack = make_pack_from_texts([("D-PROVFAIL-2", "Content.")], authority_matrix)
    original = pack.evidence_items[0]
    corrupted = _bypass_construction_evidence(original, page_numbers=[])
    corrupted_pack = EvidencePack(
        pack_id=pack.pack_id,
        schema_version=pack.schema_version,
        query=pack.query,
        evidence_items=[corrupted],
        construction_metadata=pack.construction_metadata,
    )
    result = validate_citation(make_reference(original.evidence_id), corrupted_pack)
    assert result.status == "INVALID"
    assert result.reason_code == "EVIDENCE_PROVENANCE_FAILURE"
