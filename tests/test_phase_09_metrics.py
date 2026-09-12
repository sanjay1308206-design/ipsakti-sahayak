"""
Phase 9 tests: citation coverage metrics
(docs/PHASE_09_CITATION_VALIDATION.md Section P). These measure CITATION
INTEGRITY only - never legal correctness, claim support, or answer
factual accuracy.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _citation_fixtures import fabricated_evidence_id, make_pack_from_texts, make_reference

from citation.metrics import CitationCoverageMetrics, compute_citation_coverage
from citation.validator import validate_citations

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def test_coverage_of_zero_references(authority_matrix):
    metrics = compute_citation_coverage([])
    assert metrics.total_references == 0
    assert metrics.citation_integrity_validation_rate == 0.0


def test_coverage_of_all_valid_references(authority_matrix):
    pack = make_pack_from_texts(
        [("D-MET-1", "Trademark content."), ("D-MET-2", "Patent content.")], authority_matrix
    )
    real_ids = [e.evidence_id for e in pack.evidence_items]
    results = validate_citations([make_reference(rid) for rid in real_ids], pack)
    metrics = compute_citation_coverage(results)
    assert metrics.total_references == 2
    assert metrics.valid_count == 2
    assert metrics.invalid_count == 0
    assert metrics.unresolved_count == 0
    assert metrics.unique_valid_evidence_id_count == 2
    assert metrics.citation_integrity_validation_rate == 1.0


def test_coverage_of_a_mixed_batch(authority_matrix):
    pack = make_pack_from_texts([("D-MET-3", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    refs = [
        make_reference(real_id),  # VALID
        make_reference(fabricated_evidence_id()),  # UNRESOLVED
        make_reference(None),  # INVALID
        make_reference(real_id),  # VALID, duplicate
    ]
    results = validate_citations(refs, pack)
    metrics = compute_citation_coverage(results)
    assert metrics.total_references == 4
    assert metrics.valid_count == 2
    assert metrics.invalid_count == 1
    assert metrics.unresolved_count == 1
    assert metrics.unique_valid_evidence_id_count == 1  # both VALID results cite the SAME real evidence
    assert metrics.duplicate_occurrence_count == 1
    assert metrics.citation_integrity_validation_rate == 0.5


def test_unique_valid_evidence_id_count_excludes_invalid_and_unresolved(authority_matrix):
    # An invalid/unresolved reference never counts as "citing real
    # evidence" - even if by coincidence the fabricated string happens to
    # equal a real evidence_id elsewhere, this test uses a definitely-fake one.
    pack = make_pack_from_texts([("D-MET-4", "Content.")], authority_matrix)
    refs = [make_reference(fabricated_evidence_id()), make_reference(None)]
    results = validate_citations(refs, pack)
    metrics = compute_citation_coverage(results)
    assert metrics.unique_valid_evidence_id_count == 0


def test_metrics_never_named_or_documented_as_legal_correctness():
    doc_path = REPO_ROOT / "docs" / "PHASE_09_CITATION_VALIDATION.md"
    text = doc_path.read_text(encoding="utf-8")
    assert "legal correctness" in text.lower()
    assert "citation-integrity" in text.lower() or "citation integrity" in text.lower()


def test_compute_citation_coverage_rejects_non_list():
    with pytest.raises(TypeError):
        compute_citation_coverage("not a list")


def test_compute_citation_coverage_rejects_a_list_of_wrong_type():
    with pytest.raises(TypeError):
        compute_citation_coverage(["not a result"])


def test_coverage_metrics_invariant_counts_sum_to_total():
    with pytest.raises(ValueError):
        CitationCoverageMetrics(
            schema_version="1.0.0",
            total_references=5,
            valid_count=1,
            invalid_count=1,
            unresolved_count=1,  # sums to 3, not 5
            unique_valid_evidence_id_count=1,
            duplicate_occurrence_count=0,
            citation_integrity_validation_rate=0.2,
        )


def test_coverage_metrics_invariant_rate_bounds():
    with pytest.raises(ValueError):
        CitationCoverageMetrics(
            schema_version="1.0.0",
            total_references=1,
            valid_count=1,
            invalid_count=0,
            unresolved_count=0,
            unique_valid_evidence_id_count=1,
            duplicate_occurrence_count=0,
            citation_integrity_validation_rate=1.5,
        )
