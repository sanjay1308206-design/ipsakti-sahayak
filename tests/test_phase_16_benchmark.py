"""
Phase 16 tests: the shared benchmark-scoring infrastructure
(docs/PHASE_16_EVALUATION_AND_RED_TEAM.md Sections G, Y, Z) - report
construction, referenced-existing-coverage reporting, and generic
exact-match aggregation. Domain-specific pipelines (retrieval,
classification, jurisdiction, citation, grounding, safety, multilingual,
human-review, end-to-end) each have their own dedicated test file.
"""

from __future__ import annotations

import pytest
from _evaluation_fixtures import make_case

from evaluation.benchmark import build_component_report, build_referenced_coverage_report, score_exact_match_cases
from evaluation.models import EvaluationResult


def test_build_component_report_deterministic_id_and_counts():
    result = EvaluationResult(
        schema_version="1.0.0", metric_name="X", component="CLASSIFICATION", applicable=True, value=1.0,
        numerator=1, denominator=1, explanation="ok",
    )
    report = build_component_report("CLASSIFICATION", [result], ["C1"], [])
    assert report.case_count == 1
    assert report.passed_case_ids == ["C1"]
    assert report.report_id  # non-empty


def test_build_referenced_coverage_report_rejects_non_referenced_component():
    with pytest.raises(ValueError):
        build_referenced_coverage_report("CLASSIFICATION", "not applicable")


def test_build_referenced_coverage_report_is_never_applicable():
    report = build_referenced_coverage_report("EVIDENCE_CONSTRUCTION", "Phase 8's own 191-test suite")
    assert report.component == "EVIDENCE_CONSTRUCTION"
    assert len(report.results) == 1
    assert report.results[0].applicable is False
    assert "NOT RUN" in report.results[0].explanation
    assert "Phase 8's own 191-test suite" in report.results[0].explanation


def test_score_exact_match_cases_all_pass():
    cases = [
        (make_case("C1", "CLASSIFICATION", "SYNTHETIC_EXPECTATION", "x", "y"), True),
        (make_case("C2", "CLASSIFICATION", "SYNTHETIC_EXPECTATION", "x", "y"), True),
    ]
    report = score_exact_match_cases("CLASSIFICATION", "CLASSIFICATION_STATE_EXACT_ACCURACY", cases)
    assert report.results[0].value == 1.0
    assert report.failed_case_ids == []


def test_score_exact_match_cases_mixed_results():
    cases = [
        (make_case("C1", "CLASSIFICATION", "SYNTHETIC_EXPECTATION", "x", "y"), True),
        (make_case("C2", "CLASSIFICATION", "SYNTHETIC_EXPECTATION", "x", "y"), False),
    ]
    report = score_exact_match_cases("CLASSIFICATION", "CLASSIFICATION_STATE_EXACT_ACCURACY", cases)
    assert report.results[0].value == 0.5
    assert report.passed_case_ids == ["C1"]
    assert report.failed_case_ids == ["C2"]


def test_score_exact_match_cases_empty_is_not_applicable():
    report = score_exact_match_cases("CLASSIFICATION", "CLASSIFICATION_STATE_EXACT_ACCURACY", [])
    assert report.results[0].applicable is False
    assert report.case_count == 0


def test_score_exact_match_cases_rejects_non_benchmark_case_entries():
    with pytest.raises(TypeError):
        score_exact_match_cases("CLASSIFICATION", "X", [("not a case", True)])


def test_repeated_component_report_construction_is_identical():
    result = EvaluationResult(
        schema_version="1.0.0", metric_name="X", component="CLASSIFICATION", applicable=True, value=1.0,
        numerator=1, denominator=1, explanation="ok",
    )
    reports = [build_component_report("CLASSIFICATION", [result], ["C1"], []) for _ in range(5)]
    assert all(r == reports[0] for r in reports)
