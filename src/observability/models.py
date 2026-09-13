"""
Phase 21 operational metrics data shapes
(docs/PHASE_21_OBSERVABILITY_BACKUP_CORPUS_REFRESH.md Section 6).

ZERO-OBSERVATION POLICY (`[ENGINEERING RECOMMENDATION]`, mirroring Phase
16's own "ZERO-DENOMINATOR POLICY", `evaluation.models.EvaluationResult`):
every rate/mean field below is `None` - never a fabricated `0.0`, `nan`,
or infinity - whenever there is nothing to average or divide. A real,
computed `0.0` (e.g. "citation rejection rate really is zero because
every one of 10 references was valid") is always structurally
distinguishable from "there were zero observations this window."

No field here is, or could be mistaken for, a legal, safety, or
citation-correctness conclusion - every value is a structural fact
about counts already produced by Phase 9/13/16, never recomputed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

OBSERVABILITY_SCHEMA_VERSION = "1.0.0"


def _check_non_negative_int(name: str, value) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer, got {value!r}")


def _check_optional_unit_rate(name: str, value) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number or None, got {value!r}")
    if not (0.0 <= float(value) <= 1.0):
        raise ValueError(f"{name} must be within [0.0, 1.0] or None, got {value!r}")


def _check_optional_finite_number(name: str, value) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number or None, got {value!r}")
    import math

    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite - NaN/infinity are never used to represent an undefined value")


def _check_non_empty_string(name: str, value) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


@dataclass(frozen=True)
class LatencyStats:
    """
    Deterministic latency summary over a set of already-measured request
    durations (seconds). `sample_count == 0` is the ONLY case where
    `mean_seconds`/`min_seconds`/`max_seconds` are `None` -
    `total_seconds` is always a real number (0.0 for an empty sample is a
    genuine, defined sum, not an undefined rate).
    """

    schema_version: str
    sample_count: int
    total_seconds: float
    mean_seconds: Optional[float]
    min_seconds: Optional[float]
    max_seconds: Optional[float]

    def __post_init__(self):
        _check_non_empty_string("schema_version", self.schema_version)
        _check_non_negative_int("sample_count", self.sample_count)
        if isinstance(self.total_seconds, bool) or not isinstance(self.total_seconds, (int, float)):
            raise ValueError("total_seconds must be a number")
        if self.total_seconds < 0:
            raise ValueError("total_seconds must be non-negative")
        for name in ("mean_seconds", "min_seconds", "max_seconds"):
            _check_optional_finite_number(name, getattr(self, name))
        if self.sample_count == 0:
            if self.mean_seconds is not None or self.min_seconds is not None or self.max_seconds is not None:
                raise ValueError("mean_seconds/min_seconds/max_seconds must be None when sample_count == 0")
            if self.total_seconds != 0.0:
                raise ValueError("total_seconds must be 0.0 when sample_count == 0")
        else:
            if self.mean_seconds is None or self.min_seconds is None or self.max_seconds is None:
                raise ValueError("mean_seconds/min_seconds/max_seconds must be set when sample_count > 0")
            if self.min_seconds > self.max_seconds:
                raise ValueError("min_seconds must not exceed max_seconds")


@dataclass(frozen=True)
class RetrievalDiagnosticsSummary:
    """
    Aggregates `retrieval.evaluation.precision_at_k`/`recall_at_k`/
    `reciprocal_rank` (Phase 5/6, reused verbatim, never reimplemented)
    across a set of query results. `[OUR ENHANCEMENT]`: this Phase 21
    reporting layer distinguishes "zero queries observed"
    (`query_count == 0`, every mean field `None`) from "a real mean of
    0.0 over N>0 queries" - `retrieval.evaluation.mean_reciprocal_rank`
    itself returns `0.0` for an empty query list (its own, unmodified,
    documented convention); this dataclass never calls it on an empty
    list, applying `None`-for-no-observations only at this report layer.
    """

    schema_version: str
    query_count: int
    mean_precision_at_k: Optional[float]
    mean_recall_at_k: Optional[float]
    mean_reciprocal_rank: Optional[float]

    def __post_init__(self):
        _check_non_empty_string("schema_version", self.schema_version)
        _check_non_negative_int("query_count", self.query_count)
        for name in ("mean_precision_at_k", "mean_recall_at_k", "mean_reciprocal_rank"):
            value = getattr(self, name)
            _check_optional_unit_rate(name, value)
        if self.query_count == 0:
            if self.mean_precision_at_k is not None or self.mean_recall_at_k is not None or self.mean_reciprocal_rank is not None:
                raise ValueError("mean_precision_at_k/mean_recall_at_k/mean_reciprocal_rank must be None when query_count == 0")
        else:
            if self.mean_precision_at_k is None or self.mean_recall_at_k is None or self.mean_reciprocal_rank is None:
                raise ValueError("mean_precision_at_k/mean_recall_at_k/mean_reciprocal_rank must be set when query_count > 0")


@dataclass(frozen=True)
class CitationRejectionSummary:
    """
    Aggregates `citation.metrics.CitationCoverageMetrics` (Phase 9,
    reused verbatim, never recomputed from raw citation references)
    across a set of already-validated requests. `citation_rejection_rate`
    is the fraction of citation references that were INVALID or
    UNRESOLVED - the structural inverse of Phase 9's own
    `citation_integrity_validation_rate`, never a claim about legal
    correctness (docs/PHASE_09_CITATION_VALIDATION.md Section Q,
    unchanged).
    """

    schema_version: str
    request_count: int
    total_references: int
    rejected_count: int
    citation_rejection_rate: Optional[float]

    def __post_init__(self):
        _check_non_empty_string("schema_version", self.schema_version)
        _check_non_negative_int("request_count", self.request_count)
        _check_non_negative_int("total_references", self.total_references)
        _check_non_negative_int("rejected_count", self.rejected_count)
        if self.rejected_count > self.total_references:
            raise ValueError("rejected_count must not exceed total_references")
        _check_optional_unit_rate("citation_rejection_rate", self.citation_rejection_rate)
        if self.total_references == 0:
            if self.citation_rejection_rate is not None:
                raise ValueError("citation_rejection_rate must be None when total_references == 0")
        else:
            if self.citation_rejection_rate is None:
                raise ValueError("citation_rejection_rate must be set when total_references > 0")


@dataclass(frozen=True)
class AbstentionSummary:
    """
    Aggregates `safety.models.SafetyDecision` (Phase 13, reused verbatim
    - `.abstained`/`.safety_status`/`.reason_code` are read directly,
    never a second safety classification). `reason_code_counts` only ever
    contains keys from `safety.models.SAFETY_REASON_CODES` - the same
    closed vocabulary Phase 13 already enforces.
    """

    schema_version: str
    request_count: int
    abstained_count: int
    escalated_count: int
    safe_to_present_count: int
    abstention_rate: Optional[float]
    reason_code_counts: dict

    def __post_init__(self):
        _check_non_empty_string("schema_version", self.schema_version)
        for name in ("request_count", "abstained_count", "escalated_count", "safe_to_present_count"):
            _check_non_negative_int(name, getattr(self, name))
        if self.abstained_count + self.escalated_count + self.safe_to_present_count != self.request_count:
            raise ValueError(
                "abstained_count + escalated_count + safe_to_present_count must equal request_count "
                f"({self.abstained_count} + {self.escalated_count} + {self.safe_to_present_count} != {self.request_count})"
            )
        _check_optional_unit_rate("abstention_rate", self.abstention_rate)
        if self.request_count == 0:
            if self.abstention_rate is not None:
                raise ValueError("abstention_rate must be None when request_count == 0")
        else:
            if self.abstention_rate is None:
                raise ValueError("abstention_rate must be set when request_count > 0")
        if not isinstance(self.reason_code_counts, dict):
            raise ValueError("reason_code_counts must be a dict")
        for key, value in self.reason_code_counts.items():
            if not isinstance(key, str):
                raise ValueError("reason_code_counts keys must be strings")
            _check_non_negative_int(f"reason_code_counts[{key!r}]", value)
        if sum(self.reason_code_counts.values()) > self.request_count:
            raise ValueError("sum(reason_code_counts.values()) must not exceed request_count")


@dataclass(frozen=True)
class OperationalMetricsReport:
    """The Phase 21 top-level deliverable for this step - one deterministic, serializable operational snapshot."""

    schema_version: str
    report_id: str
    request_count: int
    latency: LatencyStats
    retrieval_diagnostics: RetrievalDiagnosticsSummary
    citation_rejection: CitationRejectionSummary
    abstention: AbstentionSummary

    def __post_init__(self):
        _check_non_empty_string("schema_version", self.schema_version)
        _check_non_empty_string("report_id", self.report_id)
        _check_non_negative_int("request_count", self.request_count)
        if not isinstance(self.latency, LatencyStats):
            raise ValueError("latency must be a LatencyStats")
        if not isinstance(self.retrieval_diagnostics, RetrievalDiagnosticsSummary):
            raise ValueError("retrieval_diagnostics must be a RetrievalDiagnosticsSummary")
        if not isinstance(self.citation_rejection, CitationRejectionSummary):
            raise ValueError("citation_rejection must be a CitationRejectionSummary")
        if not isinstance(self.abstention, AbstentionSummary):
            raise ValueError("abstention must be an AbstentionSummary")
