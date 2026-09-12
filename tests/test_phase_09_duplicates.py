"""
Phase 9 tests: duplicate citation occurrence behavior
(docs/PHASE_09_CITATION_VALIDATION.md Section O). Repeated references to
the same evidence_id must never create two evidence identities, and must
never be treated as automatically invalid.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _citation_fixtures import fabricated_evidence_id, make_pack_from_texts, make_reference

from citation.validator import validate_citations

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def test_first_occurrence_is_never_marked_duplicate(authority_matrix):
    pack = make_pack_from_texts([("D-DUP-1", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    results = validate_citations([make_reference(real_id)], pack)
    assert results[0].is_duplicate_occurrence is False


def test_second_occurrence_of_the_same_id_is_marked_duplicate(authority_matrix):
    pack = make_pack_from_texts([("D-DUP-2", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    results = validate_citations([make_reference(real_id), make_reference(real_id)], pack)
    assert results[0].is_duplicate_occurrence is False
    assert results[1].is_duplicate_occurrence is True


def test_duplicate_occurrence_is_not_automatically_invalid(authority_matrix):
    pack = make_pack_from_texts([("D-DUP-3", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    results = validate_citations([make_reference(real_id), make_reference(real_id), make_reference(real_id)], pack)
    assert all(r.status == "VALID" for r in results)
    assert [r.is_duplicate_occurrence for r in results] == [False, True, True]


def test_duplicate_occurrence_still_resolves_to_the_same_single_evidence_identity(authority_matrix):
    pack = make_pack_from_texts([("D-DUP-4", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    results = validate_citations([make_reference(real_id), make_reference(real_id)], pack)
    evidence_ids = {r.resolved_evidence.evidence_id for r in results}
    assert evidence_ids == {real_id}  # never two distinct identities for the same citation


def test_duplicate_unresolved_fabricated_id_is_still_tracked_as_duplicate(authority_matrix):
    # A duplicate is about the REQUESTED evidence_id string, independent
    # of whether it actually resolves - citing the same fabricated ID
    # twice is still worth flagging for coverage purposes.
    pack = make_pack_from_texts([("D-DUP-5", "Content.")], authority_matrix)
    fake_id = fabricated_evidence_id()
    results = validate_citations([make_reference(fake_id), make_reference(fake_id)], pack)
    assert results[0].status == "UNRESOLVED"
    assert results[1].status == "UNRESOLVED"
    assert results[0].is_duplicate_occurrence is False
    assert results[1].is_duplicate_occurrence is True


def test_two_malformed_references_are_not_considered_duplicates_of_each_other(authority_matrix):
    # None/empty-string evidence_id has no identity - two malformed
    # references are not "duplicates" of one another.
    pack = make_pack_from_texts([("D-DUP-6", "Content.")], authority_matrix)
    results = validate_citations([make_reference(None), make_reference(None), make_reference("")], pack)
    assert all(r.is_duplicate_occurrence is False for r in results)


def test_distinct_evidence_ids_are_never_marked_duplicate(authority_matrix):
    pack = make_pack_from_texts(
        [("D-DUP-7", "Trademark content."), ("D-DUP-8", "Patent content.")], authority_matrix
    )
    real_ids = [e.evidence_id for e in pack.evidence_items]
    results = validate_citations([make_reference(rid) for rid in real_ids], pack)
    assert all(r.is_duplicate_occurrence is False for r in results)


def test_duplicate_tracking_preserves_deterministic_input_order(authority_matrix):
    pack = make_pack_from_texts(
        [("D-DUP-9", "Trademark content."), ("D-DUP-10", "Patent content.")], authority_matrix
    )
    id_a, id_b = (e.evidence_id for e in pack.evidence_items)
    refs = [make_reference(id_a), make_reference(id_b), make_reference(id_a), make_reference(id_b)]
    results = validate_citations(refs, pack)
    assert [r.occurrence_index for r in results] == [0, 1, 2, 3]
    assert [r.is_duplicate_occurrence for r in results] == [False, False, True, True]
