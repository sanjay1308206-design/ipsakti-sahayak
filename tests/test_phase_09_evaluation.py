"""
Phase 9 tests: the synthetic citation-validation benchmark
(docs/PHASE_09_CITATION_VALIDATION.md Section AA).

This benchmark measures IMPLEMENTATION properties of citation validation
- valid/invalid/unresolved detection, tamper detection, duplicate
handling, deterministic results, multilingual resolution, and
serialization round-trip correctness. It is explicitly NOT a legal-answer
benchmark and does not measure or claim regulatory correctness - no real
regulatory corpus or generation model is involved
(docs/DEVELOPMENT_RULES.md Rule 7).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
import yaml
from _citation_fixtures import fabricated_evidence_id, make_pack_from_texts, make_reference

from citation.metrics import compute_citation_coverage
from citation.serialize import citation_validation_result_from_dict, citation_validation_result_to_dict
from citation.validator import validate_citations

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def benchmark_pack(authority_matrix):
    fixtures = [
        ("SYNTHETIC-BENCH-09-TM-1", "Trademark registration requires filing an application with the trademark registry."),
        ("SYNTHETIC-BENCH-09-TM-2", "The trademark registry processes each registration application for distinctiveness review."),
        ("SYNTHETIC-BENCH-09-PT-1", "Patent applications require a complete technical specification of the invention."),
        ("SYNTHETIC-BENCH-09-AY-1", "Ayurveda formulation registration follows AYUSH ministry compliance rules."),
        ("SYNTHETIC-BENCH-09-HI-1", "आयुर्वेद औषधि पंजीकरण के लिए आवेदन आवश्यक है।"),
    ]
    return make_pack_from_texts(fixtures, authority_matrix, query="trademark patent ayurveda registration", max_evidence_items=5)


def test_benchmark_property_valid_citation_detection(benchmark_pack):
    real_ids = [e.evidence_id for e in benchmark_pack.evidence_items]
    results = validate_citations([make_reference(rid) for rid in real_ids], benchmark_pack)
    assert all(r.status == "VALID" for r in results)


def test_benchmark_property_invalid_citation_detection(benchmark_pack):
    results = validate_citations([make_reference(None), make_reference(""), make_reference(12345)], benchmark_pack)
    assert all(r.status == "INVALID" for r in results)


def test_benchmark_property_unresolved_citation_detection(benchmark_pack):
    results = validate_citations([make_reference(fabricated_evidence_id())], benchmark_pack)
    assert results[0].status == "UNRESOLVED"


def test_benchmark_property_tamper_detection(benchmark_pack):
    from evidence.identity import compute_pack_id

    tampered_item = dataclasses.replace(benchmark_pack.evidence_items[0], evidence_text="tampered benchmark text")
    items = [tampered_item] + list(benchmark_pack.evidence_items[1:])
    config_signature = benchmark_pack.construction_metadata["config_signature"]
    new_pack_id = compute_pack_id(
        benchmark_pack.schema_version, benchmark_pack.query, [e.evidence_id for e in items], config_signature
    )
    from evidence.models import EvidencePack

    tampered_pack = EvidencePack(
        pack_id=new_pack_id,
        schema_version=benchmark_pack.schema_version,
        query=benchmark_pack.query,
        evidence_items=items,
        construction_metadata=benchmark_pack.construction_metadata,
    )
    result = validate_citations([make_reference(tampered_item.evidence_id)], tampered_pack)[0]
    assert result.status == "INVALID"
    assert result.reason_code == "EVIDENCE_INTEGRITY_FAILURE"


def test_benchmark_property_duplicate_handling(benchmark_pack):
    real_id = benchmark_pack.evidence_items[0].evidence_id
    results = validate_citations([make_reference(real_id)] * 3, benchmark_pack)
    assert [r.is_duplicate_occurrence for r in results] == [False, True, True]
    metrics = compute_citation_coverage(results)
    assert metrics.unique_valid_evidence_id_count == 1
    assert metrics.valid_count == 3


def test_benchmark_property_deterministic_results(benchmark_pack):
    real_ids = [e.evidence_id for e in benchmark_pack.evidence_items]
    refs = [make_reference(rid) for rid in real_ids] + [make_reference(fabricated_evidence_id())]
    runs = [
        [(r.status, r.reason_code) for r in validate_citations(refs, benchmark_pack)] for _ in range(5)
    ]
    assert len({tuple(run) for run in runs}) == 1


def test_benchmark_property_multilingual_resolution(benchmark_pack):
    hindi_evidence = next(e for e in benchmark_pack.evidence_items if e.document_id == "SYNTHETIC-BENCH-09-HI-1")
    result = validate_citations([make_reference(hindi_evidence.evidence_id)], benchmark_pack)[0]
    assert result.status == "VALID"


def test_benchmark_property_serialization_round_trip_correctness(benchmark_pack):
    real_ids = [e.evidence_id for e in benchmark_pack.evidence_items]
    results = validate_citations([make_reference(rid) for rid in real_ids], benchmark_pack)
    for result in results:
        reloaded = citation_validation_result_from_dict(citation_validation_result_to_dict(result))
        assert reloaded == result


def test_benchmark_all_synthetic_evidence_is_marked_synthetic(benchmark_pack):
    real_ids = [e.evidence_id for e in benchmark_pack.evidence_items]
    results = validate_citations([make_reference(rid) for rid in real_ids], benchmark_pack)
    assert all(r.resolved_evidence.synthetic is True for r in results)


def test_benchmark_does_not_claim_regulatory_correctness():
    # This test's only purpose is to assert the benchmark's own scope
    # discipline is documented, not to measure anything numeric.
    doc_path = REPO_ROOT / "docs" / "PHASE_09_CITATION_VALIDATION.md"
    text = doc_path.read_text(encoding="utf-8")
    assert "does not measure regulatory correctness" in text or "does not measure" in text
