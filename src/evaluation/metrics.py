"""
Phase 16 metric-computation helpers (docs/PHASE_16_EVALUATION_AND_RED_TEAM.md
Sections H, Z). This module does NOT reimplement Precision@K/Recall@K/MRR
(reused verbatim from `retrieval.evaluation`, already produced by Phase
5/6) or citation-coverage metrics (reused verbatim from
`citation.metrics.compute_citation_coverage`, Phase 9) - it only adds the
one thing neither of those modules provides: an explicit, structural
ZERO-DENOMINATOR POLICY (`safe_rate`) and a small helper to turn a raw
rate into a validated `EvaluationResult`.
"""

from __future__ import annotations

from typing import Optional

from .models import EvaluationResult, EvaluationSchemaError


def safe_rate(numerator: int, denominator: int) -> Optional[float]:
    """
    `numerator / denominator`, or `None` if `denominator == 0` - NEVER
    `0.0`, `nan`, or infinity for an undefined rate (docs "ZERO-DENOMINATOR
    POLICY"). This is the ONLY division performed anywhere in this
    package's own metric-scoring code.
    """
    if isinstance(numerator, bool) or not isinstance(numerator, int) or numerator < 0:
        raise ValueError(f"numerator must be a non-negative integer, got {numerator!r}")
    if isinstance(denominator, bool) or not isinstance(denominator, int) or denominator < 0:
        raise ValueError(f"denominator must be a non-negative integer, got {denominator!r}")
    if numerator > denominator and denominator != 0:
        raise ValueError("numerator must not exceed denominator")
    if denominator == 0:
        return None
    return numerator / denominator


def build_rate_result(
    *,
    metric_name: str,
    component: str,
    numerator: int,
    denominator: int,
    explanation_if_applicable: str,
    explanation_if_not_applicable: str,
    ground_truth_origin: Optional[str] = None,
    schema_version: str,
) -> EvaluationResult:
    """
    Builds one `EvaluationResult` for a numerator/denominator rate,
    applying `safe_rate`'s zero-denominator policy structurally - a
    caller can never accidentally produce a fabricated `0.0` for an
    empty dataset by forgetting to check the denominator first.
    """
    value = safe_rate(numerator, denominator)
    applicable = value is not None
    return EvaluationResult(
        schema_version=schema_version,
        metric_name=metric_name,
        component=component,
        applicable=applicable,
        value=value,
        numerator=numerator,
        denominator=denominator,
        explanation=explanation_if_applicable if applicable else explanation_if_not_applicable,
        ground_truth_origin=ground_truth_origin,
    )


def build_not_run_result(
    *, metric_name: str, component: str, reason: str, schema_version: str, ground_truth_origin: Optional[str] = None
) -> EvaluationResult:
    """
    A metric that was deliberately not executed this run (e.g. a real
    BGE-M3/Bhashini benchmark, docs Sections J/Q) - `applicable=False`,
    `value=None`, and `explanation` states plainly it was NOT RUN, never
    silently omitted or confused with "measured and the answer was zero."
    """
    if not isinstance(reason, str) or not reason.strip():
        raise EvaluationSchemaError("reason must be a non-empty string")
    return EvaluationResult(
        schema_version=schema_version,
        metric_name=metric_name,
        component=component,
        applicable=False,
        value=None,
        numerator=None,
        denominator=None,
        explanation=f"NOT RUN: {reason}",
        ground_truth_origin=ground_truth_origin,
    )
