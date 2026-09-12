"""
Phase 16 tests: citation-integrity evaluation, reusing Phase 9's own
`citation.metrics.compute_citation_coverage` unchanged
(docs/PHASE_16_EVALUATION_AND_RED_TEAM.md Section N).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _citation_fixtures import fabricated_evidence_id, make_pack_from_texts, make_reference

from citation.metrics import compute_citation_coverage
from citation.validator import validate_citations
from evaluation.benchmark import score_citation_benchmark

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def benchmark_pack(authority_matrix):
    fixtures = [
        ("SYNTHETIC-BENCH-16-CIT-1", "Trademark registration requires filing an application with the trademark registry."),
        ("SYNTHETIC-BENCH-16-CIT-2", "Patent applications require a complete technical specification of the invention."),
    ]
    return make_pack_from_texts(fixtures, authority_matrix, query="trademark patent")


def test_citation_benchmark_all_valid(benchmark_pack):
    real_ids = [e.evidence_id for e in benchmark_pack.evidence_items]
    results = validate_citations([make_reference(rid) for rid in real_ids], benchmark_pack)
    coverage = compute_citation_coverage(results)
    report = score_citation_benchmark(["CIT1"], coverage)
    rate = next(r for r in report.results if r.metric_name == "CITATION_INTEGRITY_VALIDATION_RATE")
    assert rate.applicable is True
    assert rate.value == 1.0


def test_citation_benchmark_mixed_valid_invalid_unresolved(benchmark_pack):
    real_id = benchmark_pack.evidence_items[0].evidence_id
    references = [make_reference(real_id), make_reference(None), make_reference(fabricated_evidence_id())]
    results = validate_citations(references, benchmark_pack)
    coverage = compute_citation_coverage(results)
    assert coverage.valid_count == 1
    assert coverage.invalid_count == 1
    assert coverage.unresolved_count == 1
    report = score_citation_benchmark(["CIT2"], coverage)
    rate = next(r for r in report.results if r.metric_name == "CITATION_INTEGRITY_VALIDATION_RATE")
    assert abs(rate.value - (1 / 3)) < 1e-9


def test_citation_benchmark_zero_references_is_not_applicable():
    coverage = compute_citation_coverage([])
    report = score_citation_benchmark([], coverage)
    rate = next(r for r in report.results if r.metric_name == "CITATION_INTEGRITY_VALIDATION_RATE")
    assert rate.applicable is False


def test_citation_benchmark_never_claims_legal_correctness(benchmark_pack):
    real_ids = [e.evidence_id for e in benchmark_pack.evidence_items]
    results = validate_citations([make_reference(rid) for rid in real_ids], benchmark_pack)
    coverage = compute_citation_coverage(results)
    report = score_citation_benchmark(["CIT3"], coverage)
    for result in report.results:
        assert "legally correct" not in result.explanation.lower()
        assert "legal correctness" not in result.explanation.lower()


def test_citation_benchmark_discloses_claim_support_is_deferred(benchmark_pack):
    real_ids = [e.evidence_id for e in benchmark_pack.evidence_items]
    results = validate_citations([make_reference(rid) for rid in real_ids], benchmark_pack)
    coverage = compute_citation_coverage(results)
    report = score_citation_benchmark(["CIT4"], coverage)
    entailment_result = next(r for r in report.results if r.metric_name == "CLAIM_SUPPORT_ENTAILMENT")
    assert entailment_result.applicable is False
    assert "DEFERRED" in entailment_result.explanation or "entailment" in entailment_result.explanation.lower()


def test_score_citation_benchmark_rejects_wrong_type():
    with pytest.raises(TypeError):
        score_citation_benchmark([], "not a coverage object")
