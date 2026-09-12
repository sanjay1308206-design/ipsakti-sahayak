"""
Phase 16 tests: deterministic behavior (docs/PHASE_16_EVALUATION_AND_RED_TEAM.md
Section AA). Identical benchmark cases, synthetic corpus, configuration,
and fake providers must produce identical Phase 16 results.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _citation_fixtures import make_pack_from_texts
from _evaluation_fixtures import make_case

from evaluation.benchmark import score_citation_benchmark, score_exact_match_cases
from evaluation.redteam import build_redteam_result, build_redteam_summary, get_case
from evaluation.runner import aggregate_evaluation_report
from evaluation.serialize import component_report_to_json, evaluation_report_to_json, redteam_summary_to_json
from citation.metrics import compute_citation_coverage
from citation.validator import validate_citations
from _citation_fixtures import make_reference

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def test_repeated_exact_match_scoring_is_identical():
    case = make_case("DET1", "CLASSIFICATION", "SYNTHETIC_EXPECTATION", "x", "y")
    reports = [score_exact_match_cases("CLASSIFICATION", "M", [(case, True)]) for _ in range(10)]
    assert all(r == reports[0] for r in reports)


def test_repeated_report_id_is_identical():
    case = make_case("DET2", "CLASSIFICATION", "SYNTHETIC_EXPECTATION", "x", "y")
    ids = {score_exact_match_cases("CLASSIFICATION", "M", [(case, True)]).report_id for _ in range(10)}
    assert len(ids) == 1


def test_repeated_component_report_json_is_byte_identical():
    case = make_case("DET3", "CLASSIFICATION", "SYNTHETIC_EXPECTATION", "x", "y")
    jsons = {component_report_to_json(score_exact_match_cases("CLASSIFICATION", "M", [(case, True)])) for _ in range(10)}
    assert len(jsons) == 1


def test_citation_benchmark_is_deterministic(authority_matrix):
    pack = make_pack_from_texts([("DET4-D1", "Content.")], authority_matrix, query="det4")
    real_id = pack.evidence_items[0].evidence_id
    reports = []
    for _ in range(5):
        results = validate_citations([make_reference(real_id)], pack)
        coverage = compute_citation_coverage(results)
        reports.append(score_citation_benchmark(["DET4"], coverage))
    assert all(r == reports[0] for r in reports)


def test_redteam_result_is_deterministic():
    results = [build_redteam_result(get_case("RT-01"), False, "checked") for _ in range(10)]
    assert all(r == results[0] for r in results)


def test_redteam_summary_json_is_byte_identical():
    def build():
        results = [build_redteam_result(get_case("RT-01"), False, "x"), build_redteam_result(get_case("RT-02"), False, "y")]
        return redteam_summary_to_json(build_redteam_summary(results))

    jsons = {build() for _ in range(10)}
    assert len(jsons) == 1


def test_full_evaluation_report_is_deterministic():
    case = make_case("DET5", "CLASSIFICATION", "SYNTHETIC_EXPECTATION", "x", "y")

    def build():
        report = score_exact_match_cases("CLASSIFICATION", "M", [(case, True)])
        return evaluation_report_to_json(aggregate_evaluation_report([report]))

    jsons = {build() for _ in range(10)}
    assert len(jsons) == 1


def test_report_id_differs_for_different_case_ids():
    case_a = make_case("DET6A", "CLASSIFICATION", "SYNTHETIC_EXPECTATION", "x", "y")
    case_b = make_case("DET6B", "CLASSIFICATION", "SYNTHETIC_EXPECTATION", "x", "y")
    report_a = score_exact_match_cases("CLASSIFICATION", "M", [(case_a, True)])
    report_b = score_exact_match_cases("CLASSIFICATION", "M", [(case_b, True)])
    assert report_a.report_id != report_b.report_id
