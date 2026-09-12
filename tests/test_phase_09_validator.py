"""
Phase 9 tests: core validator behavior - valid citation, nonexistent
evidence_id, malformed reference, schema mismatch, exact-match-only
resolution, zero/one/many citations
(docs/PHASE_09_CITATION_VALIDATION.md Sections J, K, L, M).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _citation_fixtures import fabricated_evidence_id, make_pack_from_texts, make_reference

from citation.models import CitationReference, CitationValidationResult
from citation.validator import check_evidence_pack_validity, validate_citation, validate_citations

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Valid citation
# ---------------------------------------------------------------------------


def test_valid_citation_resolves_to_valid(authority_matrix):
    pack = make_pack_from_texts([("D-VAL-1", "Trademark registration content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    result = validate_citation(make_reference(real_id), pack)
    assert result.status == "VALID"
    assert result.reason_code is None
    assert result.resolved_evidence.evidence_id == real_id


def test_valid_citation_result_is_a_citation_validation_result(authority_matrix):
    pack = make_pack_from_texts([("D-VAL-TYPE", "Patent filing content.")], authority_matrix)
    result = validate_citation(make_reference(pack.evidence_items[0].evidence_id), pack)
    assert isinstance(result, CitationValidationResult)


# ---------------------------------------------------------------------------
# Nonexistent evidence_id -> UNRESOLVED
# ---------------------------------------------------------------------------


def test_nonexistent_evidence_id_is_unresolved(authority_matrix):
    pack = make_pack_from_texts([("D-UNRES-1", "Ayurveda formulation content.")], authority_matrix)
    result = validate_citation(make_reference(fabricated_evidence_id()), pack)
    assert result.status == "UNRESOLVED"
    assert result.reason_code == "EVIDENCE_NOT_FOUND"
    assert result.resolved_evidence is None


def test_unresolved_citation_never_falls_back_to_a_nearby_evidence_item(authority_matrix):
    pack = make_pack_from_texts(
        [("D-NEARBY-1", "Trademark registration process."), ("D-NEARBY-2", "Trademark filing procedure.")],
        authority_matrix,
    )
    result = validate_citation(make_reference(fabricated_evidence_id()), pack)
    assert result.status == "UNRESOLVED"
    real_ids = {e.evidence_id for e in pack.evidence_items}
    assert result.requested_evidence_id not in real_ids


# ---------------------------------------------------------------------------
# Malformed references
# ---------------------------------------------------------------------------


def test_missing_evidence_id_is_invalid(authority_matrix):
    pack = make_pack_from_texts([("D-MISS-1", "Content.")], authority_matrix)
    result = validate_citation(make_reference(None), pack)
    assert result.status == "INVALID"
    assert result.reason_code == "EVIDENCE_ID_MISSING"


@pytest.mark.parametrize("bad_id", ["", "   ", 12345, ["not", "a", "string"], {"nested": "dict"}, 3.14])
def test_malformed_evidence_id_is_invalid(authority_matrix, bad_id):
    pack = make_pack_from_texts([("D-MALFORMED-1", "Content.")], authority_matrix)
    result = validate_citation(make_reference(bad_id), pack)
    assert result.status == "INVALID"
    assert result.reason_code == "MALFORMED_REFERENCE"


def test_unsupported_schema_version_is_invalid(authority_matrix):
    pack = make_pack_from_texts([("D-SCHEMA-1", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    ref = CitationReference(evidence_id=real_id, schema_version="9.9.9")
    result = validate_citation(ref, pack)
    assert result.status == "INVALID"
    assert result.reason_code == "SCHEMA_MISMATCH"


def test_non_string_schema_version_is_invalid(authority_matrix):
    pack = make_pack_from_texts([("D-SCHEMA-2", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    ref = CitationReference(evidence_id=real_id, schema_version=None)
    result = validate_citation(ref, pack)
    assert result.status == "INVALID"
    assert result.reason_code == "SCHEMA_MISMATCH"


# ---------------------------------------------------------------------------
# Exact matching - no fuzzy, no partial, no case-folding
# ---------------------------------------------------------------------------


def test_exact_matching_rejects_a_truncated_id(authority_matrix):
    pack = make_pack_from_texts([("D-EXACT-1", "Content for exact-match test.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    truncated = real_id[:-1]
    result = validate_citation(make_reference(truncated), pack)
    assert result.status == "UNRESOLVED"


def test_exact_matching_rejects_a_one_character_appended_id(authority_matrix):
    pack = make_pack_from_texts([("D-EXACT-2", "Content for appended-character test.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    appended = real_id + "0"
    result = validate_citation(make_reference(appended), pack)
    assert result.status == "UNRESOLVED"


def test_exact_matching_rejects_a_case_folded_id(authority_matrix):
    pack = make_pack_from_texts([("D-EXACT-3", "Content for case-fold test.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    # SHA-256 hex digests are lowercase - an uppercased version is a
    # different string and must NOT resolve (no case-insensitive matching
    # unless the identity contract explicitly defines it that way, which
    # Phase 8 does not).
    upper = real_id.upper()
    if upper == real_id:
        pytest.skip("evidence_id has no alphabetic characters to case-fold")
    result = validate_citation(make_reference(upper), pack)
    assert result.status == "UNRESOLVED"


def test_exact_matching_rejects_whitespace_wrapped_id(authority_matrix):
    pack = make_pack_from_texts([("D-EXACT-4", "Content for whitespace-wrap test.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    wrapped = f" {real_id} "
    result = validate_citation(make_reference(wrapped), pack)
    assert result.status == "UNRESOLVED"


# ---------------------------------------------------------------------------
# Zero / one / many citations
# ---------------------------------------------------------------------------


def test_zero_citations_returns_empty_list(authority_matrix):
    pack = make_pack_from_texts([("D-ZERO-1", "Content.")], authority_matrix)
    results = validate_citations([], pack)
    assert results == []


def test_one_citation_returns_one_result(authority_matrix):
    pack = make_pack_from_texts([("D-ONE-1", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    results = validate_citations([make_reference(real_id)], pack)
    assert len(results) == 1
    assert results[0].status == "VALID"


def test_many_citations_returns_one_result_per_reference(authority_matrix):
    pack = make_pack_from_texts(
        [("D-MANY-1", "Trademark content."), ("D-MANY-2", "Patent content."), ("D-MANY-3", "Ayurveda content.")],
        authority_matrix,
    )
    real_ids = [e.evidence_id for e in pack.evidence_items]
    refs = [make_reference(rid) for rid in real_ids] + [make_reference(fabricated_evidence_id()), make_reference(None)]
    results = validate_citations(refs, pack)
    assert len(results) == len(refs)
    assert [r.status for r in results[: len(real_ids)]] == ["VALID"] * len(real_ids)
    assert results[len(real_ids)].status == "UNRESOLVED"
    assert results[len(real_ids) + 1].status == "INVALID"


# ---------------------------------------------------------------------------
# Type discipline
# ---------------------------------------------------------------------------


def test_validate_citation_rejects_non_citation_reference(authority_matrix):
    pack = make_pack_from_texts([("D-TYPE-1", "Content.")], authority_matrix)
    with pytest.raises(TypeError):
        validate_citation("not a citation reference", pack)


def test_validate_citations_rejects_non_list():
    with pytest.raises(TypeError):
        validate_citations("not a list", None)


def test_validate_citations_rejects_a_list_containing_a_non_reference(authority_matrix):
    pack = make_pack_from_texts([("D-TYPE-2", "Content.")], authority_matrix)
    with pytest.raises(TypeError):
        validate_citations([make_reference("a" * 64), "not a reference"], pack)


def test_check_evidence_pack_validity_rejects_wrong_type():
    with pytest.raises(TypeError):
        check_evidence_pack_validity("not a pack")


def test_check_evidence_pack_validity_accepts_a_freshly_built_pack(authority_matrix):
    pack = make_pack_from_texts([("D-VALID-PACK-1", "Content.")], authority_matrix)
    assert check_evidence_pack_validity(pack) is None
