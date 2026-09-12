"""
Phase 15 tests: the review state machine and apply_action orchestration
(docs/PHASE_15_HUMAN_IN_THE_LOOP.md Sections G, H, K).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _review_fixtures import make_safe_grounded_response

from review.models import FakeEvidenceReferenceError, InvalidReviewTransitionError, ReviewerIdentityError
from review.policy import build_review_request
from review.workflow import apply_action, compute_current_status
from safety.evaluator import evaluate_safety

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def _escalated_request(authority_matrix, input_id="W1"):
    from _review_fixtures import make_ambiguous_classification

    cls = make_ambiguous_classification(input_id)
    safety = evaluate_safety(f"{input_id}-S", classification_result=cls)
    request = build_review_request(input_id, "how can i protect this", classification_result=cls, safety_decision=safety)
    assert request is not None
    return request


# ---------------------------------------------------------------------------
# 7. Valid state transitions
# ---------------------------------------------------------------------------


def test_pending_to_in_review_via_start_review(authority_matrix):
    request = _escalated_request(authority_matrix, "W1")
    action = apply_action(request, [], reviewer_id="rev-1", action="START_REVIEW")
    assert action.previous_status == "PENDING"
    assert action.new_status == "IN_REVIEW"
    assert compute_current_status(request, [action]) == "IN_REVIEW"


def test_pending_to_approved_directly(authority_matrix):
    request = _escalated_request(authority_matrix, "W2")
    action = apply_action(request, [], reviewer_id="rev-1", action="APPROVE")
    assert action.new_status == "APPROVED"


def test_in_review_to_rejected(authority_matrix):
    request = _escalated_request(authority_matrix, "W3")
    a1 = apply_action(request, [], reviewer_id="rev-1", action="START_REVIEW")
    a2 = apply_action(request, [a1], reviewer_id="rev-1", action="REJECT")
    assert a2.previous_status == "IN_REVIEW"
    assert a2.new_status == "REJECTED"
    assert compute_current_status(request, [a1, a2]) == "REJECTED"


def test_pending_to_needs_more_evidence(authority_matrix):
    request = _escalated_request(authority_matrix, "W4")
    action = apply_action(request, [], reviewer_id="rev-1", action="REQUEST_MORE_EVIDENCE")
    assert action.new_status == "NEEDS_MORE_EVIDENCE"


def test_pending_to_escalated(authority_matrix):
    request = _escalated_request(authority_matrix, "W5")
    action = apply_action(request, [], reviewer_id="rev-1", action="ESCALATE")
    assert action.new_status == "ESCALATED"


# ---------------------------------------------------------------------------
# 8. Invalid state transitions
# ---------------------------------------------------------------------------


def test_cannot_act_on_terminal_approved_status(authority_matrix):
    request = _escalated_request(authority_matrix, "W6")
    a1 = apply_action(request, [], reviewer_id="rev-1", action="APPROVE")
    with pytest.raises(InvalidReviewTransitionError):
        apply_action(request, [a1], reviewer_id="rev-1", action="REJECT")


def test_cannot_act_on_terminal_needs_more_evidence_status(authority_matrix):
    request = _escalated_request(authority_matrix, "W7")
    a1 = apply_action(request, [], reviewer_id="rev-1", action="REQUEST_MORE_EVIDENCE")
    with pytest.raises(InvalidReviewTransitionError):
        apply_action(request, [a1], reviewer_id="rev-1", action="APPROVE")


def test_cannot_start_review_twice(authority_matrix):
    request = _escalated_request(authority_matrix, "W8")
    a1 = apply_action(request, [], reviewer_id="rev-1", action="START_REVIEW")
    with pytest.raises(InvalidReviewTransitionError):
        apply_action(request, [a1], reviewer_id="rev-1", action="START_REVIEW")


def test_compute_current_status_rejects_history_referencing_a_different_request(authority_matrix):
    request_a = _escalated_request(authority_matrix, "W9A")
    request_b = _escalated_request(authority_matrix, "W9B")
    action_from_b = apply_action(request_b, [], reviewer_id="rev-1", action="START_REVIEW")
    with pytest.raises(ValueError):
        compute_current_status(request_a, [action_from_b])


def test_compute_current_status_rejects_gap_in_sequence_numbers(authority_matrix):
    request = _escalated_request(authority_matrix, "W10")
    a1 = apply_action(request, [], reviewer_id="rev-1", action="START_REVIEW")
    # Hand-craft a second action with a skipped sequence_number.
    from review.models import ReviewAction
    from review.workflow import compute_review_action_id

    forged = ReviewAction(
        schema_version=a1.schema_version, review_action_id=compute_review_action_id(
            a1.schema_version, request.review_request_id, 5, "rev-1", "APPROVE", "IN_REVIEW", "APPROVED", None, [], a1.config_signature,
        ),
        review_request_id=request.review_request_id, sequence_number=5, reviewer_id="rev-1", action="APPROVE",
        previous_status="IN_REVIEW", new_status="APPROVED", reviewer_comment=None, selected_evidence_ids=[],
        metadata={}, config_signature=a1.config_signature,
    )
    with pytest.raises(ValueError):
        compute_current_status(request, [a1, forged])


# ---------------------------------------------------------------------------
# 9/10. Valid and invalid reviewer decisions
# ---------------------------------------------------------------------------


def test_apply_action_rejects_unknown_action(authority_matrix):
    request = _escalated_request(authority_matrix, "W11")
    with pytest.raises(ValueError):
        apply_action(request, [], reviewer_id="rev-1", action="DELETE_EVERYTHING")


def test_apply_action_rejects_wrong_request_type():
    with pytest.raises(TypeError):
        apply_action("not a request", [], reviewer_id="rev-1", action="APPROVE")


def test_apply_action_rejects_wrong_actions_so_far_type(authority_matrix):
    request = _escalated_request(authority_matrix, "W12")
    with pytest.raises(TypeError):
        apply_action(request, "not a list", reviewer_id="rev-1", action="APPROVE")


# ---------------------------------------------------------------------------
# 11. Reviewer identity validation
# ---------------------------------------------------------------------------


def test_apply_action_rejects_empty_reviewer_id(authority_matrix):
    request = _escalated_request(authority_matrix, "W13")
    with pytest.raises(ReviewerIdentityError):
        apply_action(request, [], reviewer_id="", action="APPROVE")


def test_apply_action_rejects_none_reviewer_id(authority_matrix):
    request = _escalated_request(authority_matrix, "W14")
    with pytest.raises(ReviewerIdentityError):
        apply_action(request, [], reviewer_id=None, action="APPROVE")


def test_apply_action_rejects_non_string_reviewer_id(authority_matrix):
    request = _escalated_request(authority_matrix, "W15")
    with pytest.raises(ReviewerIdentityError):
        apply_action(request, [], reviewer_id=12345, action="APPROVE")


def test_apply_action_accepts_synthetic_reviewer_id(authority_matrix):
    request = _escalated_request(authority_matrix, "W16")
    action = apply_action(request, [], reviewer_id="synthetic-test-reviewer-001", action="APPROVE")
    assert action.reviewer_id == "synthetic-test-reviewer-001"


# ---------------------------------------------------------------------------
# 23. Fake evidence ID resistance (selected_evidence_ids)
# ---------------------------------------------------------------------------


def test_apply_action_rejects_fake_selected_evidence_id(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("W17-D1", "Content.")], "w17-q")
    from _review_fixtures import make_ambiguous_classification

    cls = make_ambiguous_classification("W17")
    escalate_safety = evaluate_safety("W17-S", classification_result=cls)
    request = build_review_request("W17", "query", classification_result=cls, safety_decision=escalate_safety)
    with pytest.raises(FakeEvidenceReferenceError):
        apply_action(
            request, [], reviewer_id="rev-1", action="APPROVE",
            selected_evidence_ids=["EVIDENCE_FAKE"], evidence_pack=pack,
        )


def test_apply_action_accepts_real_selected_evidence_id(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("W18-D1", "Content.")], "w18-q")
    from _review_fixtures import make_ambiguous_classification

    cls = make_ambiguous_classification("W18")
    escalate_safety = evaluate_safety("W18-S", classification_result=cls)
    request = build_review_request("W18", "query", classification_result=cls, safety_decision=escalate_safety)
    real_id = pack.evidence_items[0].evidence_id
    action = apply_action(
        request, [], reviewer_id="rev-1", action="APPROVE",
        selected_evidence_ids=[real_id], evidence_pack=pack,
    )
    assert action.selected_evidence_ids == [real_id]


def test_apply_action_rejects_selected_evidence_ids_without_a_pack(authority_matrix):
    request = _escalated_request(authority_matrix, "W19")
    with pytest.raises(FakeEvidenceReferenceError):
        apply_action(request, [], reviewer_id="rev-1", action="APPROVE", selected_evidence_ids=["ANY-ID"])
