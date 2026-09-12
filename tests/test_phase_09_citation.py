"""
Phase 9 tests: CitationReference / CitationValidationResult / ResolvedEvidenceSummary
model invariants (docs/PHASE_09_CITATION_VALIDATION.md Sections F, G, H, I).
"""

from __future__ import annotations

import dataclasses

import pytest

from citation.models import (
    CITATION_REASON_CODES,
    CITATION_STATUSES,
    CitationReference,
    CitationValidationResult,
    ResolvedEvidenceSummary,
)


# ---------------------------------------------------------------------------
# CitationReference - deliberately permissive (untrusted-input shape)
# ---------------------------------------------------------------------------


def test_citation_reference_accepts_a_well_formed_evidence_id():
    ref = CitationReference(evidence_id="a" * 64)
    assert ref.evidence_id == "a" * 64
    assert ref.schema_version == "1.0.0"


def test_citation_reference_construction_never_raises_for_malformed_content():
    # Deliberately deviating from Phase 8's CitationTarget: constructing a
    # malformed reference must NOT raise - classifying it is validator.py's
    # job, never the container's.
    CitationReference(evidence_id=None)
    CitationReference(evidence_id="")
    CitationReference(evidence_id="   ")
    CitationReference(evidence_id=12345)
    CitationReference(evidence_id=["not", "a", "string"])
    CitationReference(schema_version="9.9.9")
    CitationReference(schema_version=None)


def test_citation_reference_has_no_field_beyond_the_documented_minimum():
    field_names = {f.name for f in dataclasses.fields(CitationReference)}
    assert field_names == {"evidence_id", "schema_version", "citation_ref_id", "display_order"}


def test_citation_reference_never_duplicates_the_full_evidence_object():
    field_names = {f.name for f in dataclasses.fields(CitationReference)}
    forbidden = {"evidence_text", "document_id", "source_family_id", "jurisdiction", "content_hash", "page_numbers", "block_ids"}
    assert field_names.isdisjoint(forbidden)


def test_citation_reference_never_contains_a_legal_conclusion_field():
    field_names = {f.name for f in dataclasses.fields(CitationReference)}
    forbidden = {"legal_conclusion", "answer", "claim", "recommendation", "interpretation", "generated_answer"}
    assert field_names.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# ResolvedEvidenceSummary
# ---------------------------------------------------------------------------


def test_resolved_evidence_summary_rejects_empty_required_fields():
    with pytest.raises(ValueError):
        ResolvedEvidenceSummary(
            evidence_id="", chunk_id="c1", document_id="d1", source_family_id="SF-01", jurisdiction="INDIA", synthetic=True
        )


def test_resolved_evidence_summary_rejects_non_bool_synthetic():
    with pytest.raises(ValueError):
        ResolvedEvidenceSummary(
            evidence_id="a" * 64, chunk_id="c1", document_id="d1", source_family_id="SF-01", jurisdiction="INDIA", synthetic="yes"
        )


def test_resolved_evidence_summary_never_carries_evidence_text():
    field_names = {f.name for f in dataclasses.fields(ResolvedEvidenceSummary)}
    assert "evidence_text" not in field_names


# ---------------------------------------------------------------------------
# CitationValidationResult - strictly validated (trusted-output shape)
# ---------------------------------------------------------------------------


def _summary(evidence_id="a" * 64) -> ResolvedEvidenceSummary:
    return ResolvedEvidenceSummary(
        evidence_id=evidence_id, chunk_id="c1", document_id="d1", source_family_id="SF-01", jurisdiction="INDIA", synthetic=False
    )


def test_valid_result_requires_no_reason_code_and_a_resolved_evidence_summary():
    result = CitationValidationResult(
        citation_reference=CitationReference(evidence_id="a" * 64),
        status="VALID",
        reason_code=None,
        requested_evidence_id="a" * 64,
        resolved_evidence=_summary(),
        occurrence_index=0,
        is_duplicate_occurrence=False,
        detail=None,
    )
    assert result.status == "VALID"


def test_valid_result_rejects_a_reason_code():
    with pytest.raises(ValueError):
        CitationValidationResult(
            citation_reference=CitationReference(evidence_id="a" * 64),
            status="VALID",
            reason_code="EVIDENCE_NOT_FOUND",
            requested_evidence_id="a" * 64,
            resolved_evidence=_summary(),
            occurrence_index=0,
            is_duplicate_occurrence=False,
            detail=None,
        )


def test_valid_result_rejects_missing_resolved_evidence():
    with pytest.raises(ValueError):
        CitationValidationResult(
            citation_reference=CitationReference(evidence_id="a" * 64),
            status="VALID",
            reason_code=None,
            requested_evidence_id="a" * 64,
            resolved_evidence=None,
            occurrence_index=0,
            is_duplicate_occurrence=False,
            detail=None,
        )


@pytest.mark.parametrize("status", ["INVALID", "UNRESOLVED"])
def test_non_valid_result_requires_a_real_reason_code(status):
    with pytest.raises(ValueError):
        CitationValidationResult(
            citation_reference=CitationReference(evidence_id="a" * 64),
            status=status,
            reason_code=None,
            requested_evidence_id="a" * 64,
            resolved_evidence=None,
            occurrence_index=0,
            is_duplicate_occurrence=False,
            detail=None,
        )


def test_non_valid_result_rejects_a_resolved_evidence_summary():
    with pytest.raises(ValueError):
        CitationValidationResult(
            citation_reference=CitationReference(evidence_id="a" * 64),
            status="INVALID",
            reason_code="EVIDENCE_NOT_FOUND",
            requested_evidence_id="a" * 64,
            resolved_evidence=_summary(),
            occurrence_index=0,
            is_duplicate_occurrence=False,
            detail=None,
        )


def test_result_rejects_an_unknown_status():
    with pytest.raises(ValueError):
        CitationValidationResult(
            citation_reference=CitationReference(evidence_id="a" * 64),
            status="MAYBE",
            reason_code=None,
            requested_evidence_id="a" * 64,
            resolved_evidence=_summary(),
            occurrence_index=0,
            is_duplicate_occurrence=False,
            detail=None,
        )


def test_result_rejects_negative_occurrence_index():
    with pytest.raises(ValueError):
        CitationValidationResult(
            citation_reference=CitationReference(evidence_id="a" * 64),
            status="INVALID",
            reason_code="EVIDENCE_NOT_FOUND",
            requested_evidence_id="a" * 64,
            resolved_evidence=None,
            occurrence_index=-1,
            is_duplicate_occurrence=False,
            detail=None,
        )


def test_result_never_contains_a_generated_answer_field():
    field_names = {f.name for f in dataclasses.fields(CitationValidationResult)}
    forbidden = {"generated_answer", "llm_response", "generated_claim", "answer_text", "legal_conclusion"}
    assert field_names.isdisjoint(forbidden)


def test_status_and_reason_code_vocabularies_are_closed_and_documented():
    assert CITATION_STATUSES == {"VALID", "INVALID", "UNRESOLVED"}
    assert CITATION_REASON_CODES == {
        "EVIDENCE_ID_MISSING",
        "MALFORMED_REFERENCE",
        "SCHEMA_MISMATCH",
        "EVIDENCE_NOT_FOUND",
        "INVALID_PACK",
        "EVIDENCE_INTEGRITY_FAILURE",
        "EVIDENCE_PROVENANCE_FAILURE",
    }
