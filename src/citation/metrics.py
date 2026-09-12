"""
Phase 9 citation coverage metrics
(docs/PHASE_09_CITATION_VALIDATION.md Section P).

CRITICAL SCOPE BOUNDARY: these metrics measure CITATION INTEGRITY only -
"how many citation references resolve to valid Evidence?" They are never
"legal correctness", "answer factual accuracy", or "how many claims are
legally supported" (docs Section Q). No field here is, or could be
mistaken for, a legal conclusion.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import CitationValidationResult

CITATION_METRICS_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class CitationCoverageMetrics:
    """
    - total_references: every CitationReference validated, including
      malformed/duplicate ones.
    - unique_valid_evidence_id_count: distinct evidence_id values among
      VALID results ONLY - an INVALID/UNRESOLVED reference does not cite
      any real evidence, so it never contributes to this count (docs
      Section P - "citation occurrence" vs "unique cited evidence").
    - citation_integrity_validation_rate: valid_count / total_references
      (0.0 when total_references is 0) - a citation-integrity measure,
      never a claim-support or legal-correctness measure.
    """

    schema_version: str
    total_references: int
    valid_count: int
    invalid_count: int
    unresolved_count: int
    unique_valid_evidence_id_count: int
    duplicate_occurrence_count: int
    citation_integrity_validation_rate: float

    def __post_init__(self):
        for name in (
            "total_references",
            "valid_count",
            "invalid_count",
            "unresolved_count",
            "unique_valid_evidence_id_count",
            "duplicate_occurrence_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer, got {value!r}")
        if self.valid_count + self.invalid_count + self.unresolved_count != self.total_references:
            raise ValueError(
                "valid_count + invalid_count + unresolved_count must equal total_references "
                f"({self.valid_count} + {self.invalid_count} + {self.unresolved_count} != {self.total_references})"
            )
        if self.unique_valid_evidence_id_count > self.valid_count:
            raise ValueError("unique_valid_evidence_id_count cannot exceed valid_count")
        if self.duplicate_occurrence_count > self.total_references:
            raise ValueError("duplicate_occurrence_count cannot exceed total_references")
        if isinstance(self.citation_integrity_validation_rate, bool) or not isinstance(
            self.citation_integrity_validation_rate, (int, float)
        ):
            raise ValueError("citation_integrity_validation_rate must be a number")
        if not (0.0 <= float(self.citation_integrity_validation_rate) <= 1.0):
            raise ValueError("citation_integrity_validation_rate must be within [0.0, 1.0]")
        if not isinstance(self.schema_version, str) or not self.schema_version.strip():
            raise ValueError("schema_version must be a non-empty string")


def compute_citation_coverage(results: list) -> CitationCoverageMetrics:
    """Deterministic citation-integrity coverage over a list of CitationValidationResult. Never legal correctness."""
    if not isinstance(results, list):
        raise TypeError(f"compute_citation_coverage expects a list, got {type(results).__name__}")
    for item in results:
        if not isinstance(item, CitationValidationResult):
            raise TypeError(
                f"compute_citation_coverage expects a list of CitationValidationResult, got {type(item).__name__}"
            )

    total = len(results)
    valid = sum(1 for r in results if r.status == "VALID")
    invalid = sum(1 for r in results if r.status == "INVALID")
    unresolved = sum(1 for r in results if r.status == "UNRESOLVED")
    unique_valid_ids = {r.resolved_evidence.evidence_id for r in results if r.status == "VALID"}
    duplicates = sum(1 for r in results if r.is_duplicate_occurrence)
    rate = (valid / total) if total > 0 else 0.0

    return CitationCoverageMetrics(
        schema_version=CITATION_METRICS_SCHEMA_VERSION,
        total_references=total,
        valid_count=valid,
        invalid_count=invalid,
        unresolved_count=unresolved,
        unique_valid_evidence_id_count=len(unique_valid_ids),
        duplicate_occurrence_count=duplicates,
        citation_integrity_validation_rate=rate,
    )
