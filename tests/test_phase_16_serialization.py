"""
Phase 16 tests: deterministic JSON serialization round-trip safety for
every Phase 16 result shape (docs/PHASE_16_EVALUATION_AND_RED_TEAM.md
Section Z), and rejection of malformed serialized data.
"""

from __future__ import annotations

import json

import pytest
from _evaluation_fixtures import make_case

from evaluation.benchmark import build_component_report
from evaluation.models import (
    EvaluationReport,
    EvaluationResult,
    EvaluationSchemaError,
    FailureTriageEntry,
    RedTeamCase,
    RedTeamResult,
    RedTeamSummary,
)
from evaluation.redteam import build_redteam_result, build_redteam_summary, get_case
from evaluation.runner import aggregate_evaluation_report
from evaluation.serialize import (
    benchmark_case_from_dict,
    benchmark_case_to_dict,
    benchmark_case_to_json,
    component_report_from_dict,
    component_report_to_dict,
    component_report_to_json,
    evaluation_report_from_dict,
    evaluation_report_to_dict,
    evaluation_report_to_json,
    evaluation_result_from_dict,
    evaluation_result_to_dict,
    failure_triage_entry_from_dict,
    failure_triage_entry_to_dict,
    redteam_case_from_dict,
    redteam_case_to_dict,
    redteam_result_from_dict,
    redteam_result_to_dict,
    redteam_result_to_json,
    redteam_summary_from_dict,
    redteam_summary_to_dict,
    redteam_summary_to_json,
)


# ---------------------------------------------------------------------------
# BenchmarkCase
# ---------------------------------------------------------------------------


def test_benchmark_case_round_trips():
    case = make_case("SER1", "CLASSIFICATION", "SYNTHETIC_EXPECTATION", "आयुर्वेद query 🎉", "state == KNOWN", notes="unicode test")
    reloaded = benchmark_case_from_dict(benchmark_case_to_dict(case))
    assert reloaded == case


def test_benchmark_case_json_preserves_unicode():
    case = make_case("SER2", "CLASSIFICATION", "SYNTHETIC_EXPECTATION", "मराठी", "state == KNOWN")
    assert "मराठी" in benchmark_case_to_json(case)


def test_benchmark_case_from_dict_rejects_non_dict():
    with pytest.raises(EvaluationSchemaError):
        benchmark_case_from_dict("not a dict")


def test_benchmark_case_from_dict_rejects_missing_field():
    case = make_case("SER3", "CLASSIFICATION", "SYNTHETIC_EXPECTATION", "x", "y")
    data = benchmark_case_to_dict(case)
    del data["category"]
    with pytest.raises(EvaluationSchemaError):
        benchmark_case_from_dict(data)


# ---------------------------------------------------------------------------
# EvaluationResult / ComponentBenchmarkReport
# ---------------------------------------------------------------------------


def test_evaluation_result_round_trips():
    result = EvaluationResult(
        schema_version="1.0.0", metric_name="X", component="CLASSIFICATION", applicable=True, value=0.5,
        numerator=1, denominator=2, explanation="ok", ground_truth_origin="SYNTHETIC_EXPECTATION",
    )
    assert evaluation_result_from_dict(evaluation_result_to_dict(result)) == result


def test_evaluation_result_not_applicable_round_trips():
    result = EvaluationResult(
        schema_version="1.0.0", metric_name="X", component="CLASSIFICATION", applicable=False, value=None,
        numerator=None, denominator=None, explanation="NOT RUN",
    )
    assert evaluation_result_from_dict(evaluation_result_to_dict(result)) == result


def test_component_report_round_trips_through_json():
    result = EvaluationResult(
        schema_version="1.0.0", metric_name="X", component="CLASSIFICATION", applicable=True, value=1.0,
        numerator=1, denominator=1, explanation="ok",
    )
    report = build_component_report("CLASSIFICATION", [result], ["C1"], [])
    parsed = json.loads(component_report_to_json(report))
    reloaded = component_report_from_dict(parsed["content"])
    assert reloaded == report


def test_component_report_from_dict_rejects_malformed_nested_result():
    result = EvaluationResult(
        schema_version="1.0.0", metric_name="X", component="CLASSIFICATION", applicable=True, value=1.0,
        numerator=1, denominator=1, explanation="ok",
    )
    report = build_component_report("CLASSIFICATION", [result], ["C1"], [])
    data = component_report_to_dict(report)
    data["results"][0]["applicable"] = "not a bool"
    with pytest.raises(EvaluationSchemaError):
        component_report_from_dict(data)


# ---------------------------------------------------------------------------
# FailureTriageEntry
# ---------------------------------------------------------------------------


def test_failure_triage_entry_round_trips():
    entry = FailureTriageEntry(
        schema_version="1.0.0", case_id="C1", component="CLASSIFICATION", failure_category="INCORRECT_CLASSIFICATION",
        expected_behavior="KNOWN", actual_behavior="UNKNOWN", reproducible=True, severity="LOW",
        severity_rationale="Edge-case only.", suggested_owner_phase="Phase 11", notes=None,
    )
    assert failure_triage_entry_from_dict(failure_triage_entry_to_dict(entry)) == entry


def test_failure_triage_entry_from_dict_rejects_missing_field():
    entry = FailureTriageEntry(
        schema_version="1.0.0", case_id="C1", component="CLASSIFICATION", failure_category="OTHER",
        expected_behavior="x", actual_behavior="y", reproducible=True, severity=None, severity_rationale=None,
        suggested_owner_phase=None, notes=None,
    )
    data = failure_triage_entry_to_dict(entry)
    del data["reproducible"]
    with pytest.raises(EvaluationSchemaError):
        failure_triage_entry_from_dict(data)


# ---------------------------------------------------------------------------
# RedTeamCase / RedTeamResult / RedTeamSummary
# ---------------------------------------------------------------------------


def test_redteam_case_round_trips():
    case = get_case("RT-13")
    assert redteam_case_from_dict(redteam_case_to_dict(case)) == case


def test_redteam_result_round_trips_through_json():
    result = build_redteam_result(get_case("RT-01"), False, "safety_status remained ESCALATE")
    parsed = json.loads(redteam_result_to_json(result))
    assert redteam_result_from_dict(parsed["content"]) == result


def test_redteam_summary_round_trips_through_json():
    results = [build_redteam_result(get_case("RT-01"), False, "x"), build_redteam_result(get_case("RT-02"), False, "y")]
    summary = build_redteam_summary(results)
    parsed = json.loads(redteam_summary_to_json(summary))
    assert redteam_summary_from_dict(parsed["content"]) == summary


def test_redteam_summary_empty_round_trips():
    summary = build_redteam_summary([])
    assert redteam_summary_from_dict(redteam_summary_to_dict(summary)) == summary


def test_redteam_result_from_dict_rejects_missing_field():
    result = build_redteam_result(get_case("RT-01"), False, "x")
    data = redteam_result_to_dict(result)
    del data["attack_success"]
    with pytest.raises(EvaluationSchemaError):
        redteam_result_from_dict(data)


# ---------------------------------------------------------------------------
# EvaluationReport
# ---------------------------------------------------------------------------


def test_evaluation_report_round_trips_with_redteam_and_failure_triage():
    result = EvaluationResult(
        schema_version="1.0.0", metric_name="X", component="CLASSIFICATION", applicable=True, value=0.0,
        numerator=0, denominator=1, explanation="ok",
    )
    report = build_component_report("CLASSIFICATION", [result], [], ["C1"])
    redteam_results = [build_redteam_result(get_case("RT-01"), False, "x")]
    summary = build_redteam_summary(redteam_results)
    triage = [
        FailureTriageEntry(
            schema_version="1.0.0", case_id="C1", component="CLASSIFICATION", failure_category="INCORRECT_CLASSIFICATION",
            expected_behavior="a", actual_behavior="b", reproducible=True, severity="LOW",
            severity_rationale="minor", suggested_owner_phase="Phase 11", notes=None,
        )
    ]
    top = aggregate_evaluation_report([report], redteam_summary=summary, failure_triage=triage)
    parsed = json.loads(evaluation_report_to_json(top))
    reloaded = evaluation_report_from_dict(parsed["content"])
    assert reloaded == top


def test_evaluation_report_round_trips_without_redteam():
    result = EvaluationResult(
        schema_version="1.0.0", metric_name="X", component="CLASSIFICATION", applicable=True, value=1.0,
        numerator=1, denominator=1, explanation="ok",
    )
    report = build_component_report("CLASSIFICATION", [result], ["C1"], [])
    top = aggregate_evaluation_report([report])
    assert evaluation_report_from_dict(evaluation_report_to_dict(top)) == top


def test_evaluation_report_from_dict_rejects_non_dict():
    with pytest.raises(EvaluationSchemaError):
        evaluation_report_from_dict(None)


def test_evaluation_report_empty_component_reports_round_trips():
    top = aggregate_evaluation_report([])
    assert evaluation_report_from_dict(evaluation_report_to_dict(top)) == top
