"""
Phase 21 Step 3 tests: operational metrics aggregation
(docs/PHASE_21_OBSERVABILITY_BACKUP_CORPUS_REFRESH.md Sections 6-11, 27).

Reuses real Phase 8-13 objects (via tests/_safety_fixtures.py, exactly
like tests/test_phase_13_*.py already does) rather than hand-built
stand-ins, so these tests also prove the metrics layer reads real,
already-validated Phase 9/13 output correctly - never a second,
competing citation/safety computation.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest
import yaml
from _safety_fixtures import make_grounded_response, make_known_classification, make_known_jurisdiction

from citation.metrics import CitationCoverageMetrics
from observability.metrics import (
    build_operational_metrics_report,
    compute_abstention_summary,
    compute_citation_rejection_summary,
    compute_latency_stats,
    compute_retrieval_diagnostics,
)
from observability.models import AbstentionSummary, CitationRejectionSummary, LatencyStats, RetrievalDiagnosticsSummary
from safety.evaluator import evaluate_safety

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def _safe_to_present_decision(authority_matrix, input_id: str):
    """A real, deterministically-built SAFE_TO_PRESENT SafetyDecision, exactly like test_phase_13_gates.py's own G9 fixture."""
    classification = make_known_classification(f"{input_id}-CLS")
    jurisdiction = make_known_jurisdiction(f"{input_id}-JUR")
    pack, gr = make_grounded_response(
        authority_matrix, [(f"{input_id}-D1", "Trademark content."), (f"{input_id}-D2", "Patent content.")], f"{input_id}-q",
        cite_real=True,
    )
    decision = evaluate_safety(input_id, classification, jurisdiction, gr)
    return decision, gr


def _abstain_decision(input_id: str):
    """A real ABSTAIN SafetyDecision - no grounded response supplied at all (Phase 13 gate G5)."""
    classification = make_known_classification(f"{input_id}-CLS")
    jurisdiction = make_known_jurisdiction(f"{input_id}-JUR")
    return evaluate_safety(input_id, classification, jurisdiction, None)


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------


def test_happy_path_builds_a_full_deterministic_report(authority_matrix):
    decision, gr = _safe_to_present_decision(authority_matrix, "HAPPY")
    report = build_operational_metrics_report(
        request_count=1,
        durations_seconds=[0.25],
        query_results=[(["c1", "c2"], {"c1"}, 2)],
        citation_metrics=[gr.citation_validation_summary],
        safety_decisions=[decision],
    )
    assert report.request_count == 1
    assert report.latency.sample_count == 1
    assert report.latency.mean_seconds == 0.25
    assert report.retrieval_diagnostics.query_count == 1
    assert report.retrieval_diagnostics.mean_precision_at_k == 0.5
    assert report.citation_rejection.request_count == 1
    assert report.abstention.request_count == 1
    assert report.abstention.safe_to_present_count == 1
    assert report.abstention.abstained_count == 0
    assert isinstance(report.report_id, str) and len(report.report_id) == 64


# ---------------------------------------------------------------------------
# 2. Zero observations
# ---------------------------------------------------------------------------


def test_zero_observations_report_has_no_fabricated_rates():
    report = build_operational_metrics_report(request_count=0)
    assert report.latency.sample_count == 0
    assert report.latency.mean_seconds is None
    assert report.latency.total_seconds == 0.0
    assert report.retrieval_diagnostics.query_count == 0
    assert report.retrieval_diagnostics.mean_precision_at_k is None
    assert report.citation_rejection.total_references == 0
    assert report.citation_rejection.citation_rejection_rate is None
    assert report.abstention.request_count == 0
    assert report.abstention.abstention_rate is None
    assert report.abstention.reason_code_counts == {}


# ---------------------------------------------------------------------------
# 3. Malformed input
# ---------------------------------------------------------------------------


def test_compute_latency_stats_rejects_non_list():
    with pytest.raises(TypeError):
        compute_latency_stats("not-a-list")


def test_compute_latency_stats_rejects_negative_duration():
    with pytest.raises(ValueError):
        compute_latency_stats([1.0, -0.5])


def test_compute_retrieval_diagnostics_rejects_malformed_tuple_shape():
    with pytest.raises(ValueError):
        compute_retrieval_diagnostics([(["c1"], {"c1"})])  # missing k


def test_compute_citation_rejection_summary_rejects_wrong_item_type():
    with pytest.raises(TypeError):
        compute_citation_rejection_summary([{"total_references": 1}])


def test_compute_abstention_summary_rejects_wrong_item_type():
    with pytest.raises(TypeError):
        compute_abstention_summary(["not-a-safety-decision"])


def test_build_operational_metrics_report_rejects_negative_request_count():
    with pytest.raises(ValueError):
        build_operational_metrics_report(request_count=-1)


# ---------------------------------------------------------------------------
# 4. Invalid citation counts
# ---------------------------------------------------------------------------


def test_citation_rejection_summary_rejects_rejected_count_exceeding_total():
    with pytest.raises(ValueError):
        CitationRejectionSummary(
            schema_version="1.0.0", request_count=1, total_references=2, rejected_count=3, citation_rejection_rate=1.0
        )


def test_citation_rejection_summary_rejects_a_rate_when_total_is_zero():
    with pytest.raises(ValueError):
        CitationRejectionSummary(
            schema_version="1.0.0", request_count=0, total_references=0, rejected_count=0, citation_rejection_rate=0.0
        )


# ---------------------------------------------------------------------------
# 5. Invalid abstention counts
# ---------------------------------------------------------------------------


def test_abstention_summary_rejects_counts_not_summing_to_request_count():
    with pytest.raises(ValueError):
        AbstentionSummary(
            schema_version="1.0.0",
            request_count=5,
            abstained_count=1,
            escalated_count=1,
            safe_to_present_count=1,
            abstention_rate=0.2,
            reason_code_counts={},
        )


def test_abstention_summary_rejects_reason_code_counts_exceeding_request_count():
    with pytest.raises(ValueError):
        AbstentionSummary(
            schema_version="1.0.0",
            request_count=1,
            abstained_count=1,
            escalated_count=0,
            safe_to_present_count=0,
            abstention_rate=1.0,
            reason_code_counts={"MISSING_GROUNDED_RESPONSE": 5},
        )


# ---------------------------------------------------------------------------
# 6. Retrieval diagnostics with no results
# ---------------------------------------------------------------------------


def test_retrieval_diagnostics_with_no_query_results():
    summary = compute_retrieval_diagnostics([])
    assert summary.query_count == 0
    assert summary.mean_precision_at_k is None
    assert summary.mean_recall_at_k is None
    assert summary.mean_reciprocal_rank is None


def test_retrieval_diagnostics_reuses_real_precision_recall_mrr_functions():
    summary = compute_retrieval_diagnostics([(["a", "b", "c"], {"a", "c"}, 3), (["x"], set(), 1)])
    assert summary.query_count == 2
    # query 1: precision=2/3, recall=2/2=1.0, rr=1.0 (rank 1 hit); query 2: precision=0.0, recall=0.0, rr=0.0
    assert summary.mean_precision_at_k == pytest.approx((2 / 3 + 0.0) / 2)
    assert summary.mean_recall_at_k == pytest.approx((1.0 + 0.0) / 2)
    assert summary.mean_reciprocal_rank == pytest.approx((1.0 + 0.0) / 2)


# ---------------------------------------------------------------------------
# 7. Deterministic repeated aggregation
# ---------------------------------------------------------------------------


def test_repeated_aggregation_is_byte_identical(authority_matrix):
    decision, gr = _safe_to_present_decision(authority_matrix, "DET")
    kwargs = dict(
        request_count=1,
        durations_seconds=[0.1, 0.2],
        query_results=[(["c1"], {"c1"}, 1)],
        citation_metrics=[gr.citation_validation_summary],
        safety_decisions=[decision],
    )
    report_a = build_operational_metrics_report(**kwargs)
    report_b = build_operational_metrics_report(**kwargs)
    assert report_a.report_id == report_b.report_id
    assert report_a == report_b


def test_different_inputs_produce_different_report_ids():
    report_empty = build_operational_metrics_report(request_count=0)
    report_with_latency = build_operational_metrics_report(request_count=1, durations_seconds=[1.0])
    assert report_empty.report_id != report_with_latency.report_id


# ---------------------------------------------------------------------------
# 8. Serialization/schema behavior
# ---------------------------------------------------------------------------


def test_report_round_trips_through_json(authority_matrix):
    decision, gr = _safe_to_present_decision(authority_matrix, "SER")
    report = build_operational_metrics_report(
        request_count=1,
        durations_seconds=[0.5],
        query_results=[(["c1"], {"c1"}, 1)],
        citation_metrics=[gr.citation_validation_summary],
        safety_decisions=[decision],
    )
    as_dict = dataclasses.asdict(report)
    text = json.dumps(as_dict, sort_keys=True)
    reloaded = json.loads(text)
    assert reloaded["report_id"] == report.report_id
    assert reloaded["abstention"]["safe_to_present_count"] == 1
    assert reloaded["latency"]["mean_seconds"] == 0.5


# ---------------------------------------------------------------------------
# 9. Division-by-zero protection
# ---------------------------------------------------------------------------


def test_citation_rejection_rate_never_divides_by_zero():
    summary = compute_citation_rejection_summary([])
    assert summary.total_references == 0
    assert summary.citation_rejection_rate is None


def test_abstention_rate_never_divides_by_zero():
    summary = compute_abstention_summary([])
    assert summary.request_count == 0
    assert summary.abstention_rate is None


def test_latency_mean_never_divides_by_zero():
    stats = compute_latency_stats([])
    assert stats.sample_count == 0
    assert stats.mean_seconds is None


# ---------------------------------------------------------------------------
# 10. Regression compatibility with existing Phase 0-20 semantics
# ---------------------------------------------------------------------------


def test_citation_rejection_summary_matches_the_real_phase_9_coverage_object(authority_matrix):
    _, gr = _safe_to_present_decision(authority_matrix, "REG1")
    coverage: CitationCoverageMetrics = gr.citation_validation_summary
    summary = compute_citation_rejection_summary([coverage])
    assert summary.total_references == coverage.total_references
    assert summary.rejected_count == coverage.invalid_count + coverage.unresolved_count
    # Phase 9's own integrity rate + Phase 21's rejection rate must be structural complements.
    if coverage.total_references > 0:
        assert summary.citation_rejection_rate == pytest.approx(1.0 - coverage.citation_integrity_validation_rate)


def test_abstention_summary_matches_a_real_phase_13_abstain_decision():
    decision = _abstain_decision("REG2")
    assert decision.safety_status == "ABSTAIN"
    summary = compute_abstention_summary([decision])
    assert summary.abstained_count == 1
    assert summary.abstention_rate == 1.0
    assert summary.reason_code_counts == {decision.reason_code: 1}


def test_abstention_summary_matches_a_real_phase_13_safe_to_present_decision(authority_matrix):
    decision, _ = _safe_to_present_decision(authority_matrix, "REG3")
    assert decision.safety_status == "SAFE_TO_PRESENT"
    summary = compute_abstention_summary([decision])
    assert summary.safe_to_present_count == 1
    assert summary.abstained_count == 0
    assert summary.abstention_rate == 0.0
