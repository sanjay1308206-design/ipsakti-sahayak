"""
Phase 15 tests: dedicated defensive-validation helpers
(docs/PHASE_15_HUMAN_IN_THE_LOOP.md Sections I, K).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _review_fixtures import make_safe_grounded_response

from review.models import FakeEvidenceReferenceError, ReviewerIdentityError
from review.validation import validate_action_type, validate_reviewer_id, validate_selected_evidence_ids

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def test_validate_reviewer_id_accepts_non_empty_string():
    validate_reviewer_id("reviewer-42")


@pytest.mark.parametrize("bad_id", [None, "", "   ", 12345, [], {}])
def test_validate_reviewer_id_rejects_bad_values(bad_id):
    with pytest.raises(ReviewerIdentityError):
        validate_reviewer_id(bad_id)


def test_validate_action_type_accepts_known_action():
    validate_action_type("APPROVE")


def test_validate_action_type_rejects_unknown_action():
    with pytest.raises(ValueError):
        validate_action_type("HACK_THE_SYSTEM")


def test_validate_selected_evidence_ids_accepts_empty_list():
    validate_selected_evidence_ids([], None)


def test_validate_selected_evidence_ids_rejects_non_list():
    with pytest.raises(ValueError):
        validate_selected_evidence_ids("not a list", None)


def test_validate_selected_evidence_ids_rejects_non_string_items():
    with pytest.raises(ValueError):
        validate_selected_evidence_ids([123], None)


def test_validate_selected_evidence_ids_rejects_missing_pack_when_ids_given():
    with pytest.raises(FakeEvidenceReferenceError):
        validate_selected_evidence_ids(["SOME-ID"], None)


def test_validate_selected_evidence_ids_rejects_wrong_pack_type():
    with pytest.raises(TypeError):
        validate_selected_evidence_ids(["SOME-ID"], "not a pack")


def test_validate_selected_evidence_ids_accepts_real_ids(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("V1-D1", "Content.")], "v1-q")
    real_id = pack.evidence_items[0].evidence_id
    validate_selected_evidence_ids([real_id], pack)


def test_validate_selected_evidence_ids_rejects_fabricated_id(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("V2-D1", "Content.")], "v2-q")
    with pytest.raises(FakeEvidenceReferenceError):
        validate_selected_evidence_ids(["EVIDENCE_FAKE"], pack)


def test_validate_selected_evidence_ids_rejects_partial_match_with_one_fake(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("V3-D1", "Content.")], "v3-q")
    real_id = pack.evidence_items[0].evidence_id
    with pytest.raises(FakeEvidenceReferenceError):
        validate_selected_evidence_ids([real_id, "EVIDENCE_FAKE"], pack)
