"""
Phase 16 tests: data-shape invariants for BenchmarkCase, EvaluationResult,
ComponentBenchmarkReport, FailureTriageEntry, RedTeamCase, RedTeamResult,
RedTeamSummary, and EvaluationReport
(docs/PHASE_16_EVALUATION_AND_RED_TEAM.md Sections G, Y, Z).
"""

from __future__ import annotations

import pytest
from _evaluation_fixtures import make_case

from evaluation.models import (
    ComponentBenchmarkReport,
    EvaluationConfig,
    EvaluationReport,
    EvaluationResult,
    FailureTriageEntry,
    RedTeamCase,
    RedTeamResult,
    RedTeamSummary,
)


# ---------------------------------------------------------------------------
# BenchmarkCase
# ---------------------------------------------------------------------------


def test_benchmark_case_minimal_construction():
    case = make_case("C1", "CLASSIFICATION", "SYNTHETIC_EXPECTATION", "empty query", "classification_state == UNKNOWN")
    assert case.expected_evidence_ids is None
    assert case.synthetic is True
    assert case.adversarial is False


def test_benchmark_case_rejects_unknown_category():
    with pytest.raises(ValueError):
        make_case("C2", "NOT_A_COMPONENT", "SYNTHETIC_EXPECTATION", "x", "y")


def test_benchmark_case_rejects_unknown_ground_truth_origin():
    with pytest.raises(ValueError):
        make_case("C3", "CLASSIFICATION", "MODEL_GUESSED", "x", "y")


def test_benchmark_case_rejects_empty_case_id():
    with pytest.raises(ValueError):
        make_case("", "CLASSIFICATION", "SYNTHETIC_EXPECTATION", "x", "y")


def test_benchmark_case_rejects_duplicate_expected_evidence_ids():
    with pytest.raises(ValueError):
        make_case("C4", "CITATION_INTEGRITY", "SYNTHETIC_EXPECTATION", "x", "y", expected_evidence_ids=["E1", "E1"])


def test_benchmark_case_supports_category_specific_fields_only():
    case = make_case(
        "C5", "JURISDICTION", "SECURITY_EXPECTATION", "india-only request", "no international leakage",
        expected_jurisdiction="INDIA", adversarial=True,
    )
    assert case.expected_classification_state is None
    assert case.expected_jurisdiction == "INDIA"
    assert case.adversarial is True


# ---------------------------------------------------------------------------
# EvaluationResult - zero-denominator policy
# ---------------------------------------------------------------------------


def test_evaluation_result_applicable_requires_value():
    with pytest.raises(ValueError):
        EvaluationResult(
            schema_version="1.0.0", metric_name="X", component="CLASSIFICATION", applicable=True, value=None,
            numerator=1, denominator=1, explanation="x",
        )


def test_evaluation_result_not_applicable_requires_none_value():
    with pytest.raises(ValueError):
        EvaluationResult(
            schema_version="1.0.0", metric_name="X", component="CLASSIFICATION", applicable=False, value=0.0,
            numerator=None, denominator=None, explanation="x",
        )


def test_evaluation_result_zero_denominator_cannot_be_applicable():
    with pytest.raises(ValueError):
        EvaluationResult(
            schema_version="1.0.0", metric_name="X", component="CLASSIFICATION", applicable=True, value=0.5,
            numerator=0, denominator=0, explanation="x",
        )


def test_evaluation_result_rejects_nan_value():
    with pytest.raises(ValueError):
        EvaluationResult(
            schema_version="1.0.0", metric_name="X", component="CLASSIFICATION", applicable=True, value=float("nan"),
            numerator=1, denominator=1, explanation="x",
        )


def test_evaluation_result_rejects_infinite_value():
    with pytest.raises(ValueError):
        EvaluationResult(
            schema_version="1.0.0", metric_name="X", component="CLASSIFICATION", applicable=True, value=float("inf"),
            numerator=1, denominator=1, explanation="x",
        )


def test_evaluation_result_rejects_numerator_exceeding_denominator():
    with pytest.raises(ValueError):
        EvaluationResult(
            schema_version="1.0.0", metric_name="X", component="CLASSIFICATION", applicable=True, value=1.0,
            numerator=5, denominator=2, explanation="x",
        )


def test_evaluation_result_valid_not_applicable():
    result = EvaluationResult(
        schema_version="1.0.0", metric_name="X", component="CLASSIFICATION", applicable=False, value=None,
        numerator=None, denominator=None, explanation="NOT RUN: no cases",
    )
    assert result.value is None


# ---------------------------------------------------------------------------
# ComponentBenchmarkReport
# ---------------------------------------------------------------------------


def _result(applicable=True, value=1.0, numerator=1, denominator=1) -> EvaluationResult:
    return EvaluationResult(
        schema_version="1.0.0", metric_name="X", component="CLASSIFICATION", applicable=applicable, value=value if applicable else None,
        numerator=numerator, denominator=denominator, explanation="x",
    )


def test_component_report_rejects_overlap_between_passed_and_failed():
    with pytest.raises(ValueError):
        ComponentBenchmarkReport(
            schema_version="1.0.0", report_id="r" * 64, component="CLASSIFICATION", case_count=1,
            results=[_result()], passed_case_ids=["C1"], failed_case_ids=["C1"], notes=None, config_signature="cfg",
        )


def test_component_report_rejects_wrong_component():
    with pytest.raises(ValueError):
        ComponentBenchmarkReport(
            schema_version="1.0.0", report_id="r" * 64, component="NOT_A_COMPONENT", case_count=0,
            results=[], passed_case_ids=[], failed_case_ids=[], notes=None, config_signature="cfg",
        )


def test_component_report_valid_construction():
    report = ComponentBenchmarkReport(
        schema_version="1.0.0", report_id="r" * 64, component="CLASSIFICATION", case_count=2,
        results=[_result()], passed_case_ids=["C1"], failed_case_ids=["C2"], notes=None, config_signature="cfg",
    )
    assert report.case_count == 2


# ---------------------------------------------------------------------------
# FailureTriageEntry
# ---------------------------------------------------------------------------


def test_failure_triage_entry_requires_rationale_with_severity():
    with pytest.raises(ValueError):
        FailureTriageEntry(
            schema_version="1.0.0", case_id="C1", component="CLASSIFICATION", failure_category="INCORRECT_CLASSIFICATION",
            expected_behavior="KNOWN", actual_behavior="UNKNOWN", reproducible=True, severity="HIGH",
            severity_rationale=None, suggested_owner_phase="Phase 11", notes=None,
        )


def test_failure_triage_entry_rejects_rationale_without_severity():
    with pytest.raises(ValueError):
        FailureTriageEntry(
            schema_version="1.0.0", case_id="C1", component="CLASSIFICATION", failure_category="INCORRECT_CLASSIFICATION",
            expected_behavior="KNOWN", actual_behavior="UNKNOWN", reproducible=True, severity=None,
            severity_rationale="matters a lot", suggested_owner_phase="Phase 11", notes=None,
        )


def test_failure_triage_entry_valid_construction():
    entry = FailureTriageEntry(
        schema_version="1.0.0", case_id="C1", component="CLASSIFICATION", failure_category="INCORRECT_CLASSIFICATION",
        expected_behavior="KNOWN", actual_behavior="UNKNOWN", reproducible=True, severity="MEDIUM",
        severity_rationale="Affects only an edge-case query pattern.", suggested_owner_phase="Phase 11", notes=None,
    )
    assert entry.severity == "MEDIUM"


# ---------------------------------------------------------------------------
# RedTeamCase / RedTeamResult / RedTeamSummary
# ---------------------------------------------------------------------------


def _redteam_case(**overrides) -> RedTeamCase:
    defaults = dict(
        schema_version="1.0.0", case_id="RT-01", attack_category="PROMPT_INJECTION", attack_input_summary="x",
        target_component="HUMAN_REVIEW", expected_security_property="y", expected_result="INERT",
    )
    defaults.update(overrides)
    return RedTeamCase(**defaults)


def test_redteam_case_rejects_mismatched_expected_result():
    with pytest.raises(ValueError):
        _redteam_case(expected_result="NOT_A_REAL_OUTCOME")


def test_redteam_result_rejects_wrong_success_definition_for_category():
    with pytest.raises(ValueError):
        RedTeamResult(
            schema_version="1.0.0", case_id="RT-01", attack_category="PROMPT_INJECTION", target_component="HUMAN_REVIEW",
            success_definition="SAFETY_OVERRIDE", attack_success=False, detail="x", config_signature="cfg",
        )


def test_redteam_result_valid_construction():
    result = RedTeamResult(
        schema_version="1.0.0", case_id="RT-01", attack_category="PROMPT_INJECTION", target_component="HUMAN_REVIEW",
        success_definition="GENERIC_TRUSTED_STATE_UNCHANGED", attack_success=False, detail="inert", config_signature="cfg",
    )
    assert result.attack_success is False


def test_redteam_summary_zero_cases_has_no_rates():
    summary = RedTeamSummary(
        schema_version="1.0.0", attack_cases=0, successful_attacks=0, blocked_attacks=0,
        detection_rate=None, attack_success_rate=None, results=[],
    )
    assert summary.detection_rate is None


def test_redteam_summary_rejects_rate_when_zero_cases():
    with pytest.raises(ValueError):
        RedTeamSummary(
            schema_version="1.0.0", attack_cases=0, successful_attacks=0, blocked_attacks=0,
            detection_rate=1.0, attack_success_rate=0.0, results=[],
        )


def test_redteam_summary_rejects_count_mismatch():
    with pytest.raises(ValueError):
        RedTeamSummary(
            schema_version="1.0.0", attack_cases=2, successful_attacks=0, blocked_attacks=1,
            detection_rate=0.5, attack_success_rate=0.5, results=[],
        )


# ---------------------------------------------------------------------------
# EvaluationReport / EvaluationConfig
# ---------------------------------------------------------------------------


def test_evaluation_report_rejects_duplicate_component_reports():
    report = ComponentBenchmarkReport(
        schema_version="1.0.0", report_id="r" * 64, component="CLASSIFICATION", case_count=0,
        results=[], passed_case_ids=[], failed_case_ids=[], notes=None, config_signature="cfg",
    )
    with pytest.raises(ValueError):
        EvaluationReport(
            schema_version="1.0.0", benchmark_schema_version="1.0.0", report_id="e" * 64,
            component_reports=[report, report], redteam_summary=None, failure_triage=[], config_signature="cfg",
        )


def test_evaluation_config_signature_is_stable():
    assert EvaluationConfig().signature == EvaluationConfig().signature
