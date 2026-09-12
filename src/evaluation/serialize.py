"""
Phase 16 deterministic JSON serialization
(docs/PHASE_16_EVALUATION_AND_RED_TEAM.md Section Z), mirroring
src/safety/serialize.py's convention exactly. All Phase 16 result shapes
are trusted (already-validated) outputs - full explicit field
reconstruction with every invariant re-enforced on deserialization. No
pickle, no arbitrary/executable deserialization anywhere.
"""

from __future__ import annotations

import json

from .models import (
    BenchmarkCase,
    ComponentBenchmarkReport,
    EvaluationReport,
    EvaluationResult,
    EvaluationSchemaError,
    FailureTriageEntry,
    RedTeamCase,
    RedTeamResult,
    RedTeamSummary,
)


def _require_dict(data, what: str) -> dict:
    if not isinstance(data, dict):
        raise EvaluationSchemaError(f"malformed {what}: expected a JSON object, got {type(data).__name__}")
    return data


def _to_json(payload: dict) -> str:
    return json.dumps({"content": payload}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


# ---------------------------------------------------------------------------
# BenchmarkCase
# ---------------------------------------------------------------------------


def benchmark_case_to_dict(case: BenchmarkCase) -> dict:
    return {
        "schema_version": case.schema_version,
        "case_id": case.case_id,
        "category": case.category,
        "ground_truth_origin": case.ground_truth_origin,
        "input_summary": case.input_summary,
        "expected_behavior": case.expected_behavior,
        "expected_evidence_ids": list(case.expected_evidence_ids) if case.expected_evidence_ids is not None else None,
        "expected_jurisdiction": case.expected_jurisdiction,
        "expected_classification_state": case.expected_classification_state,
        "expected_safety_status": case.expected_safety_status,
        "expected_review_status": case.expected_review_status,
        "expected_language": case.expected_language,
        "adversarial": case.adversarial,
        "synthetic": case.synthetic,
        "notes": case.notes,
    }


def benchmark_case_to_json(case: BenchmarkCase) -> str:
    return _to_json(benchmark_case_to_dict(case))


def benchmark_case_from_dict(data: dict) -> BenchmarkCase:
    data = _require_dict(data, "benchmark case data")
    try:
        return BenchmarkCase(
            schema_version=data["schema_version"], case_id=data["case_id"], category=data["category"],
            ground_truth_origin=data["ground_truth_origin"], input_summary=data["input_summary"],
            expected_behavior=data["expected_behavior"], expected_evidence_ids=data["expected_evidence_ids"],
            expected_jurisdiction=data["expected_jurisdiction"], expected_classification_state=data["expected_classification_state"],
            expected_safety_status=data["expected_safety_status"], expected_review_status=data["expected_review_status"],
            expected_language=data["expected_language"], adversarial=data["adversarial"], synthetic=data["synthetic"],
            notes=data["notes"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise EvaluationSchemaError(f"malformed benchmark case data: {exc}") from exc


# ---------------------------------------------------------------------------
# EvaluationResult
# ---------------------------------------------------------------------------


def evaluation_result_to_dict(result: EvaluationResult) -> dict:
    return {
        "schema_version": result.schema_version, "metric_name": result.metric_name, "component": result.component,
        "applicable": result.applicable, "value": result.value, "numerator": result.numerator,
        "denominator": result.denominator, "explanation": result.explanation, "ground_truth_origin": result.ground_truth_origin,
    }


def evaluation_result_from_dict(data: dict) -> EvaluationResult:
    data = _require_dict(data, "evaluation result data")
    try:
        return EvaluationResult(
            schema_version=data["schema_version"], metric_name=data["metric_name"], component=data["component"],
            applicable=data["applicable"], value=data["value"], numerator=data["numerator"], denominator=data["denominator"],
            explanation=data["explanation"], ground_truth_origin=data["ground_truth_origin"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise EvaluationSchemaError(f"malformed evaluation result data: {exc}") from exc


# ---------------------------------------------------------------------------
# ComponentBenchmarkReport
# ---------------------------------------------------------------------------


def component_report_to_dict(report: ComponentBenchmarkReport) -> dict:
    return {
        "schema_version": report.schema_version, "report_id": report.report_id, "component": report.component,
        "case_count": report.case_count, "results": [evaluation_result_to_dict(r) for r in report.results],
        "passed_case_ids": list(report.passed_case_ids), "failed_case_ids": list(report.failed_case_ids),
        "notes": report.notes, "config_signature": report.config_signature,
    }


def component_report_to_json(report: ComponentBenchmarkReport) -> str:
    return _to_json(component_report_to_dict(report))


def component_report_from_dict(data: dict) -> ComponentBenchmarkReport:
    data = _require_dict(data, "component benchmark report data")
    try:
        results = data["results"]
        if not isinstance(results, list):
            raise TypeError("results must be a list")
        return ComponentBenchmarkReport(
            schema_version=data["schema_version"], report_id=data["report_id"], component=data["component"],
            case_count=data["case_count"], results=[evaluation_result_from_dict(r) for r in results],
            passed_case_ids=data["passed_case_ids"], failed_case_ids=data["failed_case_ids"],
            notes=data["notes"], config_signature=data["config_signature"],
        )
    except (KeyError, TypeError, ValueError, EvaluationSchemaError) as exc:
        raise EvaluationSchemaError(f"malformed component benchmark report data: {exc}") from exc


# ---------------------------------------------------------------------------
# FailureTriageEntry
# ---------------------------------------------------------------------------


def failure_triage_entry_to_dict(entry: FailureTriageEntry) -> dict:
    return {
        "schema_version": entry.schema_version, "case_id": entry.case_id, "component": entry.component,
        "failure_category": entry.failure_category, "expected_behavior": entry.expected_behavior,
        "actual_behavior": entry.actual_behavior, "reproducible": entry.reproducible, "severity": entry.severity,
        "severity_rationale": entry.severity_rationale, "suggested_owner_phase": entry.suggested_owner_phase, "notes": entry.notes,
    }


def failure_triage_entry_from_dict(data: dict) -> FailureTriageEntry:
    data = _require_dict(data, "failure triage entry data")
    try:
        return FailureTriageEntry(
            schema_version=data["schema_version"], case_id=data["case_id"], component=data["component"],
            failure_category=data["failure_category"], expected_behavior=data["expected_behavior"],
            actual_behavior=data["actual_behavior"], reproducible=data["reproducible"], severity=data["severity"],
            severity_rationale=data["severity_rationale"], suggested_owner_phase=data["suggested_owner_phase"], notes=data["notes"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise EvaluationSchemaError(f"malformed failure triage entry data: {exc}") from exc


# ---------------------------------------------------------------------------
# RedTeamCase / RedTeamResult / RedTeamSummary
# ---------------------------------------------------------------------------


def redteam_case_to_dict(case: RedTeamCase) -> dict:
    return {
        "schema_version": case.schema_version, "case_id": case.case_id, "attack_category": case.attack_category,
        "attack_input_summary": case.attack_input_summary, "target_component": case.target_component,
        "expected_security_property": case.expected_security_property, "expected_result": case.expected_result,
        "synthetic": case.synthetic, "severity": case.severity, "severity_rationale": case.severity_rationale, "notes": case.notes,
    }


def redteam_case_from_dict(data: dict) -> RedTeamCase:
    data = _require_dict(data, "red-team case data")
    try:
        return RedTeamCase(
            schema_version=data["schema_version"], case_id=data["case_id"], attack_category=data["attack_category"],
            attack_input_summary=data["attack_input_summary"], target_component=data["target_component"],
            expected_security_property=data["expected_security_property"], expected_result=data["expected_result"],
            synthetic=data["synthetic"], severity=data["severity"], severity_rationale=data["severity_rationale"], notes=data["notes"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise EvaluationSchemaError(f"malformed red-team case data: {exc}") from exc


def redteam_result_to_dict(result: RedTeamResult) -> dict:
    return {
        "schema_version": result.schema_version, "case_id": result.case_id, "attack_category": result.attack_category,
        "target_component": result.target_component, "success_definition": result.success_definition,
        "attack_success": result.attack_success, "detail": result.detail, "config_signature": result.config_signature,
    }


def redteam_result_to_json(result: RedTeamResult) -> str:
    return _to_json(redteam_result_to_dict(result))


def redteam_result_from_dict(data: dict) -> RedTeamResult:
    data = _require_dict(data, "red-team result data")
    try:
        return RedTeamResult(
            schema_version=data["schema_version"], case_id=data["case_id"], attack_category=data["attack_category"],
            target_component=data["target_component"], success_definition=data["success_definition"],
            attack_success=data["attack_success"], detail=data["detail"], config_signature=data["config_signature"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise EvaluationSchemaError(f"malformed red-team result data: {exc}") from exc


def redteam_summary_to_dict(summary: RedTeamSummary) -> dict:
    return {
        "schema_version": summary.schema_version, "attack_cases": summary.attack_cases,
        "successful_attacks": summary.successful_attacks, "blocked_attacks": summary.blocked_attacks,
        "detection_rate": summary.detection_rate, "attack_success_rate": summary.attack_success_rate,
        "results": [redteam_result_to_dict(r) for r in summary.results],
    }


def redteam_summary_to_json(summary: RedTeamSummary) -> str:
    return _to_json(redteam_summary_to_dict(summary))


def redteam_summary_from_dict(data: dict) -> RedTeamSummary:
    data = _require_dict(data, "red-team summary data")
    try:
        results = data["results"]
        if not isinstance(results, list):
            raise TypeError("results must be a list")
        return RedTeamSummary(
            schema_version=data["schema_version"], attack_cases=data["attack_cases"],
            successful_attacks=data["successful_attacks"], blocked_attacks=data["blocked_attacks"],
            detection_rate=data["detection_rate"], attack_success_rate=data["attack_success_rate"],
            results=[redteam_result_from_dict(r) for r in results],
        )
    except (KeyError, TypeError, ValueError, EvaluationSchemaError) as exc:
        raise EvaluationSchemaError(f"malformed red-team summary data: {exc}") from exc


# ---------------------------------------------------------------------------
# EvaluationReport
# ---------------------------------------------------------------------------


def evaluation_report_to_dict(report: EvaluationReport) -> dict:
    return {
        "schema_version": report.schema_version, "benchmark_schema_version": report.benchmark_schema_version,
        "report_id": report.report_id, "component_reports": [component_report_to_dict(r) for r in report.component_reports],
        "redteam_summary": redteam_summary_to_dict(report.redteam_summary) if report.redteam_summary is not None else None,
        "failure_triage": [failure_triage_entry_to_dict(e) for e in report.failure_triage],
        "config_signature": report.config_signature,
    }


def evaluation_report_to_json(report: EvaluationReport) -> str:
    return _to_json(evaluation_report_to_dict(report))


def evaluation_report_from_dict(data: dict) -> EvaluationReport:
    data = _require_dict(data, "evaluation report data")
    try:
        component_reports = data["component_reports"]
        failure_triage = data["failure_triage"]
        if not isinstance(component_reports, list) or not isinstance(failure_triage, list):
            raise TypeError("component_reports and failure_triage must be lists")
        redteam_data = data["redteam_summary"]
        return EvaluationReport(
            schema_version=data["schema_version"], benchmark_schema_version=data["benchmark_schema_version"],
            report_id=data["report_id"], component_reports=[component_report_from_dict(r) for r in component_reports],
            redteam_summary=redteam_summary_from_dict(redteam_data) if redteam_data is not None else None,
            failure_triage=[failure_triage_entry_from_dict(e) for e in failure_triage],
            config_signature=data["config_signature"],
        )
    except (KeyError, TypeError, ValueError, EvaluationSchemaError) as exc:
        raise EvaluationSchemaError(f"malformed evaluation report data: {exc}") from exc
