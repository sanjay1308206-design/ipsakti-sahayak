"""
Phase 21 operational metrics aggregation
(docs/PHASE_21_OBSERVABILITY_BACKUP_CORPUS_REFRESH.md Sections 6-11,
config/phase_21_observability.yaml).

`[ENGINEERING RECOMMENDATION]` This module is an AGGREGATION/REPORTING
layer only, mirroring `evaluation.benchmark`'s own "accepts already-real
objects, never builds its own" convention. It never re-implements:

- citation validity (`citation.metrics.CitationCoverageMetrics` /
  `compute_citation_coverage`, Phase 9, reused verbatim as input),
- safety/abstention decisions (`safety.models.SafetyDecision`, Phase 13,
  reused verbatim as input - `.abstained`/`.safety_status`/`.reason_code`
  are read directly, never recomputed),
- retrieval scoring (`retrieval.evaluation.precision_at_k`/`recall_at_k`/
  `reciprocal_rank`, Phase 5/6, called verbatim, never duplicated), or
- the zero-denominator/zero-observation POLICY itself
  (`evaluation.metrics.safe_rate`, Phase 16, reused directly wherever its
  int-numerator/int-denominator shape fits).

No database, cache, external metrics-export protocol, or persistence of
any kind exists in this module - every function here is pure (same
inputs -> same output, no I/O, no global mutable state) and every output
is a plain, JSON-serializable `dataclasses` instance
(`src/observability/models.py`).
"""

from __future__ import annotations

import hashlib
from typing import Optional

from citation.metrics import CitationCoverageMetrics
from evaluation.metrics import safe_rate
from retrieval.evaluation import precision_at_k, recall_at_k, reciprocal_rank
from safety.models import SAFETY_REASON_CODES, SafetyDecision

from .models import (
    OBSERVABILITY_SCHEMA_VERSION,
    AbstentionSummary,
    CitationRejectionSummary,
    LatencyStats,
    OperationalMetricsReport,
    RetrievalDiagnosticsSummary,
)


def _safe_mean(values: list) -> Optional[float]:
    """
    `sum(values) / len(values)`, or `None` if `values` is empty - the
    same zero-observation POLICY as `evaluation.metrics.safe_rate`,
    applied here because `safe_rate` itself expects two non-negative
    integers (a count/count rate), not a list of already-computed
    floats (a mean) - this is a narrow, disclosed application of the
    same policy to a shape `safe_rate` does not cover, never a second,
    competing rate algorithm.
    """
    if not isinstance(values, list) or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in values):
        raise TypeError("values must be a list of numbers")
    if not values:
        return None
    return sum(values) / len(values)


def compute_latency_stats(durations_seconds: list) -> LatencyStats:
    """Deterministic latency summary over already-measured request durations (seconds)."""
    if not isinstance(durations_seconds, list):
        raise TypeError(f"durations_seconds must be a list, got {type(durations_seconds).__name__}")
    for value in durations_seconds:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise ValueError(f"every duration must be a non-negative number, got {value!r}")

    count = len(durations_seconds)
    if count == 0:
        return LatencyStats(
            schema_version=OBSERVABILITY_SCHEMA_VERSION,
            sample_count=0,
            total_seconds=0.0,
            mean_seconds=None,
            min_seconds=None,
            max_seconds=None,
        )
    total = float(sum(durations_seconds))
    return LatencyStats(
        schema_version=OBSERVABILITY_SCHEMA_VERSION,
        sample_count=count,
        total_seconds=total,
        mean_seconds=total / count,
        min_seconds=float(min(durations_seconds)),
        max_seconds=float(max(durations_seconds)),
    )


def compute_retrieval_diagnostics(query_results: list) -> RetrievalDiagnosticsSummary:
    """
    `query_results`: a list of `(retrieved_chunk_ids, relevant_chunk_ids, k)`
    triples - the same shape `retrieval.evaluation`'s own functions
    already accept. Each query's precision/recall/reciprocal-rank is
    computed by calling those functions verbatim; only the cross-query
    MEAN, and the None-for-zero-queries policy (docs Section 9,
    `RetrievalDiagnosticsSummary` docstring), are added here.
    """
    if not isinstance(query_results, list):
        raise TypeError(f"query_results must be a list, got {type(query_results).__name__}")
    for item in query_results:
        if not isinstance(item, tuple) or len(item) != 3:
            raise ValueError("each query_results item must be a (retrieved_chunk_ids, relevant_chunk_ids, k) tuple")
        retrieved, relevant, k = item
        if not isinstance(retrieved, list) or any(not isinstance(x, str) for x in retrieved):
            raise ValueError("retrieved_chunk_ids must be a list of strings")
        if not isinstance(relevant, set) or any(not isinstance(x, str) for x in relevant):
            raise ValueError("relevant_chunk_ids must be a set of strings")
        if isinstance(k, bool) or not isinstance(k, int):
            raise ValueError("k must be an integer")

    if not query_results:
        return RetrievalDiagnosticsSummary(
            schema_version=OBSERVABILITY_SCHEMA_VERSION,
            query_count=0,
            mean_precision_at_k=None,
            mean_recall_at_k=None,
            mean_reciprocal_rank=None,
        )

    precisions = [precision_at_k(retrieved, relevant, k) for retrieved, relevant, k in query_results]
    recalls = [recall_at_k(retrieved, relevant, k) for retrieved, relevant, k in query_results]
    reciprocal_ranks = [reciprocal_rank(retrieved, relevant) for retrieved, relevant, _ in query_results]

    return RetrievalDiagnosticsSummary(
        schema_version=OBSERVABILITY_SCHEMA_VERSION,
        query_count=len(query_results),
        mean_precision_at_k=_safe_mean(precisions),
        mean_recall_at_k=_safe_mean(recalls),
        mean_reciprocal_rank=_safe_mean(reciprocal_ranks),
    )


def compute_citation_rejection_summary(citation_metrics: list) -> CitationRejectionSummary:
    """Aggregates already-computed `citation.metrics.CitationCoverageMetrics` across requests - never recomputes citation validity."""
    if not isinstance(citation_metrics, list):
        raise TypeError(f"citation_metrics must be a list, got {type(citation_metrics).__name__}")
    for item in citation_metrics:
        if not isinstance(item, CitationCoverageMetrics):
            raise TypeError(f"citation_metrics items must be CitationCoverageMetrics, got {type(item).__name__}")

    total_references = sum(m.total_references for m in citation_metrics)
    rejected = sum(m.invalid_count + m.unresolved_count for m in citation_metrics)
    rate = safe_rate(rejected, total_references)

    return CitationRejectionSummary(
        schema_version=OBSERVABILITY_SCHEMA_VERSION,
        request_count=len(citation_metrics),
        total_references=total_references,
        rejected_count=rejected,
        citation_rejection_rate=rate,
    )


def compute_abstention_summary(safety_decisions: list) -> AbstentionSummary:
    """Aggregates already-computed `safety.models.SafetyDecision` across requests - never a second safety classification."""
    if not isinstance(safety_decisions, list):
        raise TypeError(f"safety_decisions must be a list, got {type(safety_decisions).__name__}")
    for item in safety_decisions:
        if not isinstance(item, SafetyDecision):
            raise TypeError(f"safety_decisions items must be SafetyDecision, got {type(item).__name__}")

    total = len(safety_decisions)
    abstained = sum(1 for d in safety_decisions if d.safety_status == "ABSTAIN")
    escalated = sum(1 for d in safety_decisions if d.safety_status == "ESCALATE")
    safe = sum(1 for d in safety_decisions if d.safety_status == "SAFE_TO_PRESENT")
    rate = safe_rate(abstained, total)

    reason_code_counts: dict = {}
    for decision in safety_decisions:
        reason_code_counts[decision.reason_code] = reason_code_counts.get(decision.reason_code, 0) + 1
    assert set(reason_code_counts).issubset(SAFETY_REASON_CODES)

    return AbstentionSummary(
        schema_version=OBSERVABILITY_SCHEMA_VERSION,
        request_count=total,
        abstained_count=abstained,
        escalated_count=escalated,
        safe_to_present_count=safe,
        abstention_rate=rate,
        reason_code_counts=reason_code_counts,
    )


def compute_report_id(
    schema_version: str,
    request_count: int,
    latency: LatencyStats,
    retrieval_diagnostics: RetrievalDiagnosticsSummary,
    citation_rejection: CitationRejectionSummary,
    abstention: AbstentionSummary,
) -> str:
    """
    Deterministic, backend-owned report identity - never a random UUID,
    never a timestamp, matching every other phase's own identity
    convention (Phase 8 `evidence_id`, Phase 10 `response_id`, Phase 13
    `decision_id`, Phase 16 `compute_report_id`, Phase 17
    `compute_request_id`).
    """
    canonical = "|".join(
        [
            "observability-report-v1",
            schema_version,
            str(request_count),
            f"lat:{latency.sample_count}:{latency.total_seconds}",
            f"ret:{retrieval_diagnostics.query_count}",
            f"cit:{citation_rejection.total_references}:{citation_rejection.rejected_count}",
            f"abs:{abstention.abstained_count}:{abstention.escalated_count}:{abstention.safe_to_present_count}",
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_operational_metrics_report(
    *,
    request_count: int,
    durations_seconds: Optional[list] = None,
    query_results: Optional[list] = None,
    citation_metrics: Optional[list] = None,
    safety_decisions: Optional[list] = None,
) -> OperationalMetricsReport:
    """
    The single Phase 21 Step-3 entry point: composes the four sub-summaries
    above into one deterministic `OperationalMetricsReport`.

    `request_count` is the caller-declared number of requests this report
    covers - it is independent of the individual list lengths above, since
    not every request necessarily produces every kind of observation
    (e.g. a request that abstains before retrieval runs contributes to
    `safety_decisions` but never to `query_results`); this function does
    not assume the four lists are the same length.
    """
    if isinstance(request_count, bool) or not isinstance(request_count, int) or request_count < 0:
        raise ValueError(f"request_count must be a non-negative integer, got {request_count!r}")

    latency = compute_latency_stats(durations_seconds if durations_seconds is not None else [])
    retrieval_diagnostics = compute_retrieval_diagnostics(query_results if query_results is not None else [])
    citation_rejection = compute_citation_rejection_summary(citation_metrics if citation_metrics is not None else [])
    abstention = compute_abstention_summary(safety_decisions if safety_decisions is not None else [])

    report_id = compute_report_id(
        OBSERVABILITY_SCHEMA_VERSION, request_count, latency, retrieval_diagnostics, citation_rejection, abstention
    )

    return OperationalMetricsReport(
        schema_version=OBSERVABILITY_SCHEMA_VERSION,
        report_id=report_id,
        request_count=request_count,
        latency=latency,
        retrieval_diagnostics=retrieval_diagnostics,
        citation_rejection=citation_rejection,
        abstention=abstention,
    )
