"""
Phase 9 deterministic JSON serialization
(docs/PHASE_09_CITATION_VALIDATION.md Section T), mirroring
src/evidence/serialize.py's convention.

No arbitrary/executable Python object deserialization anywhere - every
payload here is plain JSON data (str/int/float/bool/list/dict/None);
`pickle` is never used.

Two different strictness postures, matching models.py's two trust
postures:

- `citation_reference_*`: the ENVELOPE (is this actually a dict with the
  expected keys present?) is validated strictly and rejected on any
  shape violation. The VALUES inside a present key are passed through
  unchanged, exactly as permissively as `CitationReference` itself is
  constructed - a malformed evidence_id inside a well-formed envelope is
  not this layer's job to reject; classifying it is validator.py's job.
- `citation_validation_result_*` / `citation_coverage_metrics_*`: the
  TRUSTED OUTPUT shapes are reconstructed with full explicit field
  validation (identical to Phase 8's `evidence_from_dict`) - any
  missing/malformed field or inconsistent status/reason_code pairing
  raises CitationSchemaError, never a silently-repaired partial object.
"""

from __future__ import annotations

import dataclasses
import json

from .metrics import CitationCoverageMetrics
from .models import (
    CitationReference,
    CitationSchemaError,
    CitationValidationResult,
    ResolvedEvidenceSummary,
)


def _require_dict(data, what: str) -> dict:
    if not isinstance(data, dict):
        raise CitationSchemaError(f"malformed {what}: expected a JSON object, got {type(data).__name__}")
    return data


# ---------------------------------------------------------------------------
# CitationReference - untrusted-input envelope, permissive values
# ---------------------------------------------------------------------------


def citation_reference_to_dict(reference: CitationReference) -> dict:
    return dataclasses.asdict(reference)


def citation_reference_to_json(reference: CitationReference) -> str:
    payload = {"content": citation_reference_to_dict(reference)}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def citation_reference_from_dict(data: dict) -> CitationReference:
    """
    Rejects a malformed ENVELOPE (not a dict at all, or missing the
    required `schema_version` key). Does NOT reject a malformed VALUE
    (e.g. `evidence_id` present but not a string) - that classification
    is validator.py's job, never this parser's.
    """
    data = _require_dict(data, "citation reference data")
    try:
        schema_version = data["schema_version"]
    except KeyError as exc:
        raise CitationSchemaError(f"malformed citation reference data: missing required key {exc}") from exc
    return CitationReference(
        evidence_id=data.get("evidence_id"),
        schema_version=schema_version,
        citation_ref_id=data.get("citation_ref_id"),
        display_order=data.get("display_order"),
    )


# ---------------------------------------------------------------------------
# CitationValidationResult - trusted validator output, strict reconstruction
# ---------------------------------------------------------------------------


def citation_validation_result_to_dict(result: CitationValidationResult) -> dict:
    return dataclasses.asdict(result)


def citation_validation_result_to_json(result: CitationValidationResult) -> str:
    payload = {"content": citation_validation_result_to_dict(result)}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def citation_validation_result_from_dict(data: dict) -> CitationValidationResult:
    """Reconstructs and re-validates one CitationValidationResult. Raises CitationSchemaError on any malformation."""
    data = _require_dict(data, "citation validation result data")
    try:
        reference_data = data["citation_reference"]
        resolved_evidence_data = data["resolved_evidence"]
        resolved_evidence = None
        if resolved_evidence_data is not None:
            resolved_evidence_data = _require_dict(resolved_evidence_data, "resolved_evidence data")
            resolved_evidence = ResolvedEvidenceSummary(
                evidence_id=resolved_evidence_data["evidence_id"],
                chunk_id=resolved_evidence_data["chunk_id"],
                document_id=resolved_evidence_data["document_id"],
                source_family_id=resolved_evidence_data["source_family_id"],
                jurisdiction=resolved_evidence_data["jurisdiction"],
                synthetic=resolved_evidence_data["synthetic"],
            )
        result = CitationValidationResult(
            citation_reference=citation_reference_from_dict(reference_data),
            status=data["status"],
            reason_code=data["reason_code"],
            requested_evidence_id=data["requested_evidence_id"],
            resolved_evidence=resolved_evidence,
            occurrence_index=data["occurrence_index"],
            is_duplicate_occurrence=data["is_duplicate_occurrence"],
            detail=data["detail"],
            validator_schema_version=data["validator_schema_version"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CitationSchemaError(f"malformed citation validation result data: {exc}") from exc
    return result


# ---------------------------------------------------------------------------
# CitationCoverageMetrics - trusted derived output, strict reconstruction
# ---------------------------------------------------------------------------


def citation_coverage_metrics_to_dict(metrics: CitationCoverageMetrics) -> dict:
    return dataclasses.asdict(metrics)


def citation_coverage_metrics_to_json(metrics: CitationCoverageMetrics) -> str:
    payload = {"content": citation_coverage_metrics_to_dict(metrics)}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def citation_coverage_metrics_from_dict(data: dict) -> CitationCoverageMetrics:
    data = _require_dict(data, "citation coverage metrics data")
    try:
        metrics = CitationCoverageMetrics(
            schema_version=data["schema_version"],
            total_references=data["total_references"],
            valid_count=data["valid_count"],
            invalid_count=data["invalid_count"],
            unresolved_count=data["unresolved_count"],
            unique_valid_evidence_id_count=data["unique_valid_evidence_id_count"],
            duplicate_occurrence_count=data["duplicate_occurrence_count"],
            citation_integrity_validation_rate=data["citation_integrity_validation_rate"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CitationSchemaError(f"malformed citation coverage metrics data: {exc}") from exc
    return metrics
