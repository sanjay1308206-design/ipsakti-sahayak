"""
Phase 9 tests: deterministic validation results
(docs/PHASE_09_CITATION_VALIDATION.md Section "CITATION ORDERING").
Repeated validation of identical input must produce identical output,
in preserved input order - never set/dict iteration order.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _citation_fixtures import fabricated_evidence_id, make_pack_from_texts, make_reference

from citation.metrics import compute_citation_coverage
from citation.validator import validate_citation, validate_citations

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def test_repeated_single_validation_is_identical(authority_matrix):
    pack = make_pack_from_texts([("D-DET-1", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    results = {validate_citation(make_reference(real_id), pack) for _ in range(5)}
    assert len(results) == 1


def test_repeated_batch_validation_is_identical_and_ordered(authority_matrix):
    pack = make_pack_from_texts(
        [("D-DET-2", "Trademark content."), ("D-DET-3", "Patent content."), ("D-DET-4", "Ayurveda content.")],
        authority_matrix,
    )
    real_ids = [e.evidence_id for e in pack.evidence_items]
    refs = [make_reference(rid) for rid in real_ids] + [make_reference(fabricated_evidence_id())]

    runs = [validate_citations(refs, pack) for _ in range(5)]
    first = runs[0]
    for run in runs[1:]:
        assert [(r.status, r.reason_code, r.occurrence_index) for r in run] == [
            (r.status, r.reason_code, r.occurrence_index) for r in first
        ]

    # Occurrence order must match INPUT order exactly.
    assert [r.occurrence_index for r in first] == list(range(len(refs)))


def test_coverage_metrics_are_deterministic_across_runs(authority_matrix):
    pack = make_pack_from_texts([("D-DET-5", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    refs = [make_reference(real_id), make_reference(fabricated_evidence_id()), make_reference(None)]

    metrics_runs = [compute_citation_coverage(validate_citations(refs, pack)) for _ in range(5)]
    assert len({m.citation_integrity_validation_rate for m in metrics_runs}) == 1
    assert len({(m.valid_count, m.invalid_count, m.unresolved_count) for m in metrics_runs}) == 1


def test_ordering_does_not_depend_on_dict_or_set_iteration(authority_matrix):
    # Build a pack with many evidence items and confirm results preserve
    # the input reference list's order exactly, regardless of internal
    # dict/set usage inside the validator.
    docs = [(f"D-DET-ORDER-{i}", f"Distinct content number {i}.") for i in range(8)]
    pack = make_pack_from_texts(docs, authority_matrix)
    ids_in_pack_order = [e.evidence_id for e in pack.evidence_items]
    # Deliberately request them in REVERSE order.
    reversed_ids = list(reversed(ids_in_pack_order))
    refs = [make_reference(rid) for rid in reversed_ids]
    results = validate_citations(refs, pack)
    assert [r.resolved_evidence.evidence_id for r in results] == reversed_ids
