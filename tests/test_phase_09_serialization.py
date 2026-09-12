"""
Phase 9 tests: serialization round-trip safety - CitationReference,
CitationValidationResult, CitationCoverageMetrics
(docs/PHASE_09_CITATION_VALIDATION.md Section T).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from _citation_fixtures import fabricated_evidence_id, make_pack_from_texts, make_reference

from citation.metrics import compute_citation_coverage
from citation.models import CitationReference, CitationSchemaError
from citation.serialize import (
    citation_coverage_metrics_from_dict,
    citation_coverage_metrics_to_dict,
    citation_coverage_metrics_to_json,
    citation_reference_from_dict,
    citation_reference_to_dict,
    citation_reference_to_json,
    citation_validation_result_from_dict,
    citation_validation_result_to_dict,
    citation_validation_result_to_json,
)
from citation.validator import validate_citation, validate_citations

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# CitationReference round-trip
# ---------------------------------------------------------------------------


def test_citation_reference_round_trips_through_dict():
    ref = CitationReference(evidence_id="a" * 64, citation_ref_id="ref-1", display_order=3)
    reloaded = citation_reference_from_dict(citation_reference_to_dict(ref))
    assert reloaded == ref


def test_citation_reference_json_is_valid_json_and_round_trips():
    ref = CitationReference(evidence_id="b" * 64)
    parsed = json.loads(citation_reference_to_json(ref))
    reloaded = citation_reference_from_dict(parsed["content"])
    assert reloaded == ref


def test_citation_reference_with_malformed_evidence_id_still_round_trips():
    # The ENVELOPE is well-formed even though evidence_id is malformed -
    # serialization passes the value through unchanged; classification is
    # validator.py's job, not the parser's.
    ref = CitationReference(evidence_id="   ")
    reloaded = citation_reference_from_dict(citation_reference_to_dict(ref))
    assert reloaded.evidence_id == "   "


def test_citation_reference_from_dict_rejects_non_dict():
    with pytest.raises(CitationSchemaError):
        citation_reference_from_dict("not a dict")
    with pytest.raises(CitationSchemaError):
        citation_reference_from_dict([1, 2, 3])


def test_citation_reference_from_dict_rejects_missing_schema_version_key():
    with pytest.raises(CitationSchemaError):
        citation_reference_from_dict({"evidence_id": "a" * 64})


# ---------------------------------------------------------------------------
# CitationValidationResult round-trip
# ---------------------------------------------------------------------------


def test_valid_result_round_trips_through_dict(authority_matrix):
    pack = make_pack_from_texts([("D-SER-1", "Trademark serialization content.")], authority_matrix)
    result = validate_citation(make_reference(pack.evidence_items[0].evidence_id), pack)
    reloaded = citation_validation_result_from_dict(citation_validation_result_to_dict(result))
    assert reloaded == result


def test_unresolved_result_round_trips_through_dict(authority_matrix):
    pack = make_pack_from_texts([("D-SER-2", "Content.")], authority_matrix)
    result = validate_citation(make_reference(fabricated_evidence_id()), pack)
    reloaded = citation_validation_result_from_dict(citation_validation_result_to_dict(result))
    assert reloaded == result


def test_invalid_result_round_trips_through_dict(authority_matrix):
    pack = make_pack_from_texts([("D-SER-3", "Content.")], authority_matrix)
    result = validate_citation(make_reference(None), pack)
    reloaded = citation_validation_result_from_dict(citation_validation_result_to_dict(result))
    assert reloaded == result


def test_result_json_is_valid_json_and_round_trips(authority_matrix):
    pack = make_pack_from_texts([("D-SER-4", "Content.")], authority_matrix)
    result = validate_citation(make_reference(pack.evidence_items[0].evidence_id), pack)
    parsed = json.loads(citation_validation_result_to_json(result))
    reloaded = citation_validation_result_from_dict(parsed["content"])
    assert reloaded == result


def test_result_json_is_deterministic_across_calls(authority_matrix):
    pack = make_pack_from_texts([("D-SER-5", "Content.")], authority_matrix)
    result = validate_citation(make_reference(pack.evidence_items[0].evidence_id), pack)
    assert citation_validation_result_to_json(result) == citation_validation_result_to_json(result)


def test_result_from_dict_rejects_non_dict():
    with pytest.raises(CitationSchemaError):
        citation_validation_result_from_dict("not a dict")


def test_result_from_dict_rejects_missing_field(authority_matrix):
    pack = make_pack_from_texts([("D-SER-6", "Content.")], authority_matrix)
    result = validate_citation(make_reference(pack.evidence_items[0].evidence_id), pack)
    data = citation_validation_result_to_dict(result)
    del data["status"]
    with pytest.raises(CitationSchemaError):
        citation_validation_result_from_dict(data)


def test_result_from_dict_rejects_malformed_resolved_evidence(authority_matrix):
    pack = make_pack_from_texts([("D-SER-7", "Content.")], authority_matrix)
    result = validate_citation(make_reference(pack.evidence_items[0].evidence_id), pack)
    data = citation_validation_result_to_dict(result)
    data["resolved_evidence"]["document_id"] = ""  # violates ResolvedEvidenceSummary invariant
    with pytest.raises(CitationSchemaError):
        citation_validation_result_from_dict(data)


# ---------------------------------------------------------------------------
# CitationCoverageMetrics round-trip
# ---------------------------------------------------------------------------


def test_metrics_round_trip_through_dict(authority_matrix):
    pack = make_pack_from_texts([("D-SER-8", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    results = validate_citations([make_reference(real_id), make_reference(fabricated_evidence_id())], pack)
    metrics = compute_citation_coverage(results)
    reloaded = citation_coverage_metrics_from_dict(citation_coverage_metrics_to_dict(metrics))
    assert reloaded == metrics


def test_metrics_json_round_trips(authority_matrix):
    pack = make_pack_from_texts([("D-SER-9", "Content.")], authority_matrix)
    results = validate_citations([make_reference(pack.evidence_items[0].evidence_id)], pack)
    metrics = compute_citation_coverage(results)
    parsed = json.loads(citation_coverage_metrics_to_json(metrics))
    reloaded = citation_coverage_metrics_from_dict(parsed["content"])
    assert reloaded == metrics


def test_metrics_from_dict_rejects_missing_field():
    with pytest.raises(CitationSchemaError):
        citation_coverage_metrics_from_dict({"schema_version": "1.0.0"})


def test_metrics_from_dict_rejects_inconsistent_counts():
    with pytest.raises(CitationSchemaError):
        citation_coverage_metrics_from_dict(
            {
                "schema_version": "1.0.0",
                "total_references": 5,
                "valid_count": 1,
                "invalid_count": 1,
                "unresolved_count": 1,
                "unique_valid_evidence_id_count": 1,
                "duplicate_occurrence_count": 0,
                "citation_integrity_validation_rate": 0.2,
            }
        )
