"""
Phase 16 top-level aggregation (docs/PHASE_16_EVALUATION_AND_RED_TEAM.md
Section Y). `aggregate_evaluation_report` combines already-produced
`ComponentBenchmarkReport`/`RedTeamSummary` objects (each produced by
`benchmark.py`/`redteam.py`, called from tests/test_phase_16_*.py against
real Phase 3-15 objects) into one deterministic `EvaluationReport`. This
module never runs a benchmark itself - it only aggregates and triages
already-computed results.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from .models import (
    ComponentBenchmarkReport,
    EvaluationConfig,
    EvaluationReport,
    FailureTriageEntry,
    RedTeamSummary,
)


def compute_evaluation_report_id(schema_version: str, benchmark_schema_version: str, component_names: list, config_signature: str) -> str:
    """Deterministic, backend-owned report identity - never a random UUID, never a timestamp."""
    canonical = "|".join(
        ["evaluation-report-top-v1", schema_version, benchmark_schema_version, ",".join(sorted(component_names)), config_signature]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def aggregate_evaluation_report(
    component_reports: list,
    *,
    redteam_summary: Optional[RedTeamSummary] = None,
    failure_triage: Optional[list] = None,
    config: Optional[EvaluationConfig] = None,
) -> EvaluationReport:
    if not isinstance(component_reports, list) or any(not isinstance(r, ComponentBenchmarkReport) for r in component_reports):
        raise TypeError("component_reports must be a list of ComponentBenchmarkReport")
    if redteam_summary is not None and not isinstance(redteam_summary, RedTeamSummary):
        raise TypeError(f"redteam_summary must be a RedTeamSummary or None, got {type(redteam_summary).__name__}")
    if failure_triage is not None and (not isinstance(failure_triage, list) or any(not isinstance(x, FailureTriageEntry) for x in failure_triage)):
        raise TypeError("failure_triage must be a list of FailureTriageEntry or None")
    if config is None:
        config = EvaluationConfig()

    component_names = [r.component for r in component_reports]
    report_id = compute_evaluation_report_id(config.schema_version, config.benchmark_schema_version, component_names, config.signature)

    return EvaluationReport(
        schema_version=config.schema_version,
        benchmark_schema_version=config.benchmark_schema_version,
        report_id=report_id,
        component_reports=list(component_reports),
        redteam_summary=redteam_summary,
        failure_triage=list(failure_triage) if failure_triage is not None else [],
        config_signature=config.signature,
    )


def collect_failed_case_ids(component_reports: list) -> dict:
    """Returns {component: [failed_case_id, ...]} for every component with at least one failure - a convenience for building FailureTriageEntry objects, never itself a triage decision."""
    if not isinstance(component_reports, list) or any(not isinstance(r, ComponentBenchmarkReport) for r in component_reports):
        raise TypeError("component_reports must be a list of ComponentBenchmarkReport")
    return {r.component: list(r.failed_case_ids) for r in component_reports if r.failed_case_ids}
