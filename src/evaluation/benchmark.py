"""
Phase 16 component/end-to-end benchmark scoring
(docs/PHASE_16_EVALUATION_AND_RED_TEAM.md Sections H-S).

Every function here accepts ALREADY-COMPUTED real Phase 3-15 objects -
this module never builds an EvidencePack, never calls a real embedding
model, never runs classify()/resolve_jurisdiction()/evaluate_safety()
itself. Building those real objects over a small synthetic corpus is the
caller's job (tests/test_phase_16_*.py, reusing the project's existing
tests/_*_fixtures.py exactly like every earlier phase's own
test_phase_XX_evaluation.py already did) - this module is the
metrics/comparison/reporting layer only, per the explicit instruction to
reuse existing Phase 5-15 evaluation utilities rather than duplicate
pipeline construction.

CRITICAL: nothing here changes retrieval/classification/jurisdiction/
citation/grounding/safety/multilingual/review behavior. It only measures
and reports what already happened.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from citation.metrics import CitationCoverageMetrics

from .metrics import build_not_run_result, build_rate_result
from .models import (
    BenchmarkCase,
    ComponentBenchmarkReport,
    EvaluationConfig,
    EvaluationResult,
    REFERENCED_EXISTING_COVERAGE_COMPONENTS,
)


def compute_report_id(schema_version: str, component: str, case_ids: list, config_signature: str) -> str:
    """Deterministic, backend-owned report identity - never a random UUID, never a timestamp."""
    canonical = "|".join(["evaluation-report-v1", schema_version, component, ",".join(sorted(case_ids)), config_signature])
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_component_report(
    component: str,
    results: list,
    passed_case_ids: list,
    failed_case_ids: list,
    *,
    notes: Optional[str] = None,
    config: Optional[EvaluationConfig] = None,
) -> ComponentBenchmarkReport:
    if config is None:
        config = EvaluationConfig()
    case_ids = sorted(set(passed_case_ids) | set(failed_case_ids))
    return ComponentBenchmarkReport(
        schema_version=config.schema_version,
        report_id=compute_report_id(config.schema_version, component, case_ids, config.signature),
        component=component,
        case_count=len(passed_case_ids) + len(failed_case_ids),
        results=results,
        passed_case_ids=list(passed_case_ids),
        failed_case_ids=list(failed_case_ids),
        notes=notes,
        config_signature=config.signature,
    )


def build_referenced_coverage_report(
    component: str, referenced_description: str, config: Optional[EvaluationConfig] = None
) -> ComponentBenchmarkReport:
    """
    For components already covered exhaustively by an earlier phase's own
    test suite (docs Section B: CORPUS_PROVENANCE, DOCUMENT_STRUCTURE,
    EVIDENCE_CONSTRUCTION) - Phase 16 does not duplicate that coverage, it
    only records the reference. `applicable=False` throughout: this is
    not a Phase-16-computed metric.
    """
    if component not in REFERENCED_EXISTING_COVERAGE_COMPONENTS:
        raise ValueError(f"component {component!r} is not a referenced-existing-coverage component")
    if config is None:
        config = EvaluationConfig()
    result = EvaluationResult(
        schema_version=config.schema_version,
        metric_name="COVERAGE_STATUS",
        component=component,
        applicable=False,
        value=None,
        numerator=None,
        denominator=None,
        explanation=f"NOT RUN by Phase 16 (duplication avoided): {referenced_description}",
    )
    return build_component_report(component, [result], [], [], notes=referenced_description, config=config)


# ---------------------------------------------------------------------------
# Retrieval (BM25 / dense / hybrid+RRF / reranked) - wraps retrieval.evaluation
# ---------------------------------------------------------------------------


def score_retrieval_condition(
    component: str,
    per_query_results: list,
    k: int,
    *,
    real_model_validated: bool = False,
    not_validated_reason: Optional[str] = None,
    config: Optional[EvaluationConfig] = None,
) -> ComponentBenchmarkReport:
    """
    `per_query_results`: list of `(query_id, retrieved_chunk_ids, relevant_chunk_ids)`
    already produced by the caller via a REAL Phase 5/6/7 index/query call
    (BM25, dense with a real or fake embedding model, RRF fusion, or
    reranked). Wraps them with `retrieval.evaluation`'s own
    Precision@K/Recall@K/MRR (never reimplemented here). When
    `real_model_validated=False`, an additional NOT_RUN result records
    that real-model retrieval quality (e.g. BGE-M3, bge-reranker-v2-m3)
    was not validated this run (docs Section J).
    """
    from retrieval.evaluation import mean_reciprocal_rank, precision_at_k, recall_at_k

    if config is None:
        config = EvaluationConfig()
    query_ids = [qid for qid, _, _ in per_query_results]
    n = len(per_query_results)

    if n == 0:
        precision_result = build_not_run_result(
            metric_name=f"PRECISION_AT_{k}", component=component, reason="no queries were run in this benchmark", schema_version=config.schema_version,
        )
        recall_result = build_not_run_result(
            metric_name=f"RECALL_AT_{k}", component=component, reason="no queries were run in this benchmark", schema_version=config.schema_version,
        )
        mrr_result = build_not_run_result(
            metric_name="MEAN_RECIPROCAL_RANK", component=component, reason="no queries were run in this benchmark", schema_version=config.schema_version,
        )
    else:
        precisions = [precision_at_k(retrieved, relevant, k) for _, retrieved, relevant in per_query_results]
        recalls = [recall_at_k(retrieved, relevant, k) for _, retrieved, relevant in per_query_results]
        mrr = mean_reciprocal_rank([(retrieved, relevant) for _, retrieved, relevant in per_query_results])
        precision_result = EvaluationResult(
            schema_version=config.schema_version, metric_name=f"PRECISION_AT_{k}", component=component,
            applicable=True, value=sum(precisions) / n, numerator=None, denominator=n,
            explanation=f"Mean Precision@{k} over {n} synthetic queries.", ground_truth_origin="STRUCTURAL_EXPECTATION",
        )
        recall_result = EvaluationResult(
            schema_version=config.schema_version, metric_name=f"RECALL_AT_{k}", component=component,
            applicable=True, value=sum(recalls) / n, numerator=None, denominator=n,
            explanation=f"Mean Recall@{k} over {n} synthetic queries.", ground_truth_origin="STRUCTURAL_EXPECTATION",
        )
        mrr_result = EvaluationResult(
            schema_version=config.schema_version, metric_name="MEAN_RECIPROCAL_RANK", component=component,
            applicable=True, value=mrr, numerator=None, denominator=n,
            explanation=f"Mean Reciprocal Rank over {n} synthetic queries.", ground_truth_origin="STRUCTURAL_EXPECTATION",
        )

    results = [precision_result, recall_result, mrr_result]
    if not real_model_validated:
        results.append(
            build_not_run_result(
                metric_name="REAL_MODEL_RETRIEVAL_QUALITY", component=component,
                reason=not_validated_reason or "a real (non-fake) embedding/reranker model was not used in this benchmark run",
                schema_version=config.schema_version,
            )
        )

    passed = query_ids if n > 0 else []
    return build_component_report(
        component, results, passed, [],
        notes="Synthetic, fake-model benchmark - measures engineering correctness only, not real regulatory retrieval quality.",
        config=config,
    )


# ---------------------------------------------------------------------------
# Citation - wraps citation.metrics.compute_citation_coverage directly
# ---------------------------------------------------------------------------


def score_citation_benchmark(
    case_ids: list, coverage: CitationCoverageMetrics, *, config: Optional[EvaluationConfig] = None
) -> ComponentBenchmarkReport:
    """`coverage` must already be `citation.metrics.compute_citation_coverage(results)`'s real return value - never recomputed here."""
    if config is None:
        config = EvaluationConfig()
    if not isinstance(coverage, CitationCoverageMetrics):
        raise TypeError(f"coverage must be a CitationCoverageMetrics, got {type(coverage).__name__}")

    total = coverage.total_references
    rate_result = build_rate_result(
        metric_name="CITATION_INTEGRITY_VALIDATION_RATE", component="CITATION_INTEGRITY",
        numerator=coverage.valid_count, denominator=total,
        explanation_if_applicable=f"{coverage.valid_count} of {total} citation references were VALID (Phase 9's own coverage metric, reused unchanged).",
        explanation_if_not_applicable="No citation references were validated in this benchmark run.",
        ground_truth_origin="STRUCTURAL_EXPECTATION", schema_version=config.schema_version,
    )
    unique_result = EvaluationResult(
        schema_version=config.schema_version, metric_name="UNIQUE_VALID_EVIDENCE_ID_COUNT", component="CITATION_INTEGRITY",
        applicable=True, value=float(coverage.unique_valid_evidence_id_count), numerator=coverage.unique_valid_evidence_id_count,
        denominator=None, explanation="Distinct evidence_id values among VALID citation results (Phase 9's own count).",
    )
    disclaimer = build_not_run_result(
        metric_name="CLAIM_SUPPORT_ENTAILMENT", component="CITATION_INTEGRITY",
        reason="semantic claim/evidence entailment is Phase 9's own explicitly [DEFERRED] scope boundary - citation integrity is never claim support",
        schema_version=config.schema_version,
    )
    passed = case_ids if total > 0 and coverage.valid_count == total else []
    failed = [] if total == 0 else [cid for cid in case_ids if cid not in passed]
    return build_component_report(
        "CITATION_INTEGRITY", [rate_result, unique_result, disclaimer], passed, failed,
        notes="Reuses citation.metrics.compute_citation_coverage unchanged - never re-derives citation validity.",
        config=config,
    )


# ---------------------------------------------------------------------------
# Generic exact-match component scoring (classification / jurisdiction state /
# safety / multilingual / human-review / grounding / end-to-end)
# ---------------------------------------------------------------------------


def score_exact_match_cases(
    component: str,
    metric_name: str,
    entries: list,
    *,
    ground_truth_origin: str = "SYNTHETIC_EXPECTATION",
    config: Optional[EvaluationConfig] = None,
) -> ComponentBenchmarkReport:
    """
    `entries`: list of `(BenchmarkCase, matched: bool)` where `matched`
    was already computed by the caller comparing one real upstream
    object's field(s) against the case's own `expected_*` field(s). This
    function only aggregates - it never re-derives what "matched" means
    for a given component (each component's own comparison semantics are
    documented at the call site in tests/test_phase_16_*.py).
    """
    if config is None:
        config = EvaluationConfig()
    if not entries:
        result = build_not_run_result(metric_name=metric_name, component=component, reason="no benchmark cases were supplied", schema_version=config.schema_version)
        return build_component_report(component, [result], [], [], config=config)

    passed, failed = [], []
    for case, matched in entries:
        if not isinstance(case, BenchmarkCase):
            raise TypeError(f"entries must contain BenchmarkCase instances, got {type(case).__name__}")
        (passed if matched else failed).append(case.case_id)

    result = build_rate_result(
        metric_name=metric_name, component=component, numerator=len(passed), denominator=len(entries),
        explanation_if_applicable=f"{len(passed)} of {len(entries)} synthetic cases matched their declared expectation.",
        explanation_if_not_applicable="No cases were supplied.", ground_truth_origin=ground_truth_origin,
        schema_version=config.schema_version,
    )
    return build_component_report(component, [result], passed, failed, config=config)


# ---------------------------------------------------------------------------
# Jurisdiction leakage - the HIGH-PRIORITY safety benchmark
# ---------------------------------------------------------------------------


def score_jurisdiction_leakage(
    case_ids: list,
    prohibited_ids_seen: int,
    prohibited_ids_leaked: int,
    *,
    config: Optional[EvaluationConfig] = None,
) -> EvaluationResult:
    """
    `JURISDICTION_LEAKAGE_RATE = prohibited_ids_leaked / prohibited_ids_seen`
    (docs Section M) - an engineering metric only, `NOT_APPLICABLE` when no
    prohibited evidence was ever presented to a jurisdiction filter in
    this run (there is nothing to leak). A single leaked item must be
    surfaced: `prohibited_ids_leaked > 0` always yields a non-zero,
    visible rate, never rounded away.
    """
    if config is None:
        config = EvaluationConfig()
    return build_rate_result(
        metric_name="JURISDICTION_LEAKAGE_RATE", component="JURISDICTION",
        numerator=prohibited_ids_leaked, denominator=prohibited_ids_seen,
        explanation_if_applicable=(
            f"{prohibited_ids_leaked} of {prohibited_ids_seen} prohibited evidence item(s) leaked into "
            f"allowed_evidence across {len(case_ids)} jurisdiction-filtering case(s)."
        ),
        explanation_if_not_applicable="No prohibited evidence was presented to jurisdiction filtering in this run.",
        ground_truth_origin="SECURITY_EXPECTATION", schema_version=config.schema_version,
    )
