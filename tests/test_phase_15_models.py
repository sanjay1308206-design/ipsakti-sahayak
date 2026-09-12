"""
Phase 15 tests: data-shape invariants for ReviewCaseSnapshot, ReviewRequest,
ReviewAction, and PresentationAuthorization
(docs/PHASE_15_HUMAN_IN_THE_LOOP.md Sections F, G, H, O).
"""

from __future__ import annotations

import pytest

from review.models import (
    FIXED_HUMAN_REVIEW_DISCLAIMER,
    HumanReviewConfig,
    InvalidReviewTransitionError,
    PresentationAuthorization,
    ReviewAction,
    ReviewCaseSnapshot,
    ReviewRequest,
    ReviewTriggerAssessment,
)


def _snapshot(**overrides) -> ReviewCaseSnapshot:
    defaults = dict(
        schema_version="1.0.0",
        classification_state=None,
        classification_input_id=None,
        regulatory_track=None,
        evidence_state=None,
        jurisdiction_state=None,
        jurisdiction_decision_id=None,
        grounding_status=None,
        response_id=None,
        evidence_pack_id=None,
        cited_evidence_ids=[],
        citation_total_references=None,
        citation_valid_count=None,
        citation_invalid_count=None,
        citation_unresolved_count=None,
        safety_status=None,
        safety_decision_id=None,
        safety_engineering_signal_band=None,
        multilingual_delivery_status=None,
        multilingual_result_id=None,
        requested_language=None,
        detected_script=None,
        synthetic=None,
    )
    defaults.update(overrides)
    return ReviewCaseSnapshot(**defaults)


def _request(**overrides) -> ReviewRequest:
    defaults = dict(
        schema_version="1.0.0",
        review_request_id="r" * 64,
        input_id="IN1",
        original_query="query text",
        canonical_query="query text",
        case_snapshot=_snapshot(safety_status="ESCALATE"),
        trigger_reasons=["SAFETY_ESCALATE"],
        priority="CRITICAL",
        review_reason="Human review required: safety escalated.",
        review_status="PENDING",
        config_signature="human-review-config:v1.0.0",
    )
    defaults.update(overrides)
    return ReviewRequest(**defaults)


def _action(**overrides) -> ReviewAction:
    defaults = dict(
        schema_version="1.0.0",
        review_action_id="a" * 64,
        review_request_id="r" * 64,
        sequence_number=0,
        reviewer_id="reviewer-1",
        action="START_REVIEW",
        previous_status="PENDING",
        new_status="IN_REVIEW",
        reviewer_comment=None,
        selected_evidence_ids=[],
        metadata={},
        config_signature="human-review-config:v1.0.0",
    )
    defaults.update(overrides)
    return ReviewAction(**defaults)


# ---------------------------------------------------------------------------
# ReviewCaseSnapshot
# ---------------------------------------------------------------------------


def test_case_snapshot_accepts_all_none_fields():
    snapshot = _snapshot()
    assert snapshot.classification_state is None
    assert snapshot.cited_evidence_ids == []


def test_case_snapshot_rejects_invalid_classification_state():
    with pytest.raises(ValueError):
        _snapshot(classification_state="NOT_A_REAL_STATE")


def test_case_snapshot_rejects_invalid_safety_status():
    with pytest.raises(ValueError):
        _snapshot(safety_status="MADE_UP_STATUS")


def test_case_snapshot_rejects_invalid_regulatory_track():
    with pytest.raises(ValueError):
        _snapshot(regulatory_track="INVENTED_TRACK")


def test_case_snapshot_rejects_duplicate_cited_evidence_ids():
    with pytest.raises(ValueError):
        _snapshot(cited_evidence_ids=["E1", "E1"])


def test_case_snapshot_rejects_negative_citation_counts():
    with pytest.raises(ValueError):
        _snapshot(citation_valid_count=-1)


# ---------------------------------------------------------------------------
# ReviewRequest
# ---------------------------------------------------------------------------


def test_review_request_valid_construction():
    request = _request()
    assert request.review_status == "PENDING"
    assert request.priority == "CRITICAL"


def test_review_request_rejects_non_pending_review_status():
    with pytest.raises(ValueError):
        _request(review_status="APPROVED")


def test_review_request_rejects_empty_trigger_reasons():
    with pytest.raises(ValueError):
        _request(trigger_reasons=[])


def test_review_request_rejects_unknown_trigger_reason():
    with pytest.raises(ValueError):
        _request(trigger_reasons=["NOT_A_REAL_TRIGGER"])


def test_review_request_rejects_invalid_priority():
    with pytest.raises(ValueError):
        _request(priority="URGENT")


def test_review_request_rejects_wrong_case_snapshot_type():
    with pytest.raises(ValueError):
        _request(case_snapshot="not a snapshot")


# ---------------------------------------------------------------------------
# ReviewAction
# ---------------------------------------------------------------------------


def test_review_action_valid_construction():
    action = _action()
    assert action.new_status == "IN_REVIEW"


def test_review_action_rejects_unknown_action_type():
    with pytest.raises(ValueError):
        _action(action="DELETE_EVERYTHING")


def test_review_action_rejects_inconsistent_transition():
    with pytest.raises(InvalidReviewTransitionError):
        _action(previous_status="PENDING", action="START_REVIEW", new_status="APPROVED")


def test_review_action_rejects_transition_not_in_table():
    with pytest.raises(InvalidReviewTransitionError):
        _action(previous_status="APPROVED", action="APPROVE", new_status="APPROVED")


def test_review_action_rejects_negative_sequence_number():
    with pytest.raises(ValueError):
        _action(sequence_number=-1)


def test_review_action_rejects_duplicate_selected_evidence_ids():
    with pytest.raises(ValueError):
        _action(
            previous_status="PENDING", action="APPROVE", new_status="APPROVED",
            selected_evidence_ids=["E1", "E1"],
        )


def test_review_action_rejects_credential_shaped_metadata():
    with pytest.raises(ValueError):
        _action(metadata={"api_key": "secret"})


def test_review_action_rejects_overlong_comment():
    with pytest.raises(ValueError):
        _action(reviewer_comment="x" * 10_001)


def test_review_action_accepts_comment_at_exact_limit():
    action = _action(reviewer_comment="x" * 10_000)
    assert len(action.reviewer_comment) == 10_000


# ---------------------------------------------------------------------------
# PresentationAuthorization
# ---------------------------------------------------------------------------


def test_presentation_authorization_automated_safe():
    auth = PresentationAuthorization(
        schema_version="1.0.0", authorized=True, source="AUTOMATED_SAFE_TO_PRESENT",
        safety_status="SAFE_TO_PRESENT", review_action_id=None, explanation="ok", disclaimer=None,
    )
    assert auth.authorized is True


def test_presentation_authorization_human_approved_requires_disclaimer_and_action_id():
    with pytest.raises(ValueError):
        PresentationAuthorization(
            schema_version="1.0.0", authorized=True, source="HUMAN_REVIEW_APPROVED",
            safety_status="ABSTAIN", review_action_id=None, explanation="ok", disclaimer=FIXED_HUMAN_REVIEW_DISCLAIMER,
        )


def test_presentation_authorization_rejects_altered_disclaimer():
    with pytest.raises(ValueError):
        PresentationAuthorization(
            schema_version="1.0.0", authorized=True, source="HUMAN_REVIEW_APPROVED",
            safety_status="ABSTAIN", review_action_id="a" * 64, explanation="ok", disclaimer="this is legally certified",
        )


def test_presentation_authorization_blocked_requires_authorized_false():
    with pytest.raises(ValueError):
        PresentationAuthorization(
            schema_version="1.0.0", authorized=True, source="BLOCKED",
            safety_status="ABSTAIN", review_action_id=None, explanation="ok", disclaimer=None,
        )


# ---------------------------------------------------------------------------
# ReviewTriggerAssessment / HumanReviewConfig
# ---------------------------------------------------------------------------


def test_trigger_assessment_requires_review_matches_reasons():
    with pytest.raises(ValueError):
        ReviewTriggerAssessment(requires_review=True, trigger_reasons=[], priority="HIGH", basis=[], explanation="x")


def test_trigger_assessment_no_trigger_priority_must_be_not_applicable():
    with pytest.raises(ValueError):
        ReviewTriggerAssessment(requires_review=False, trigger_reasons=[], priority="HIGH", basis=[], explanation="x")


def test_human_review_config_default_signature_is_stable():
    assert HumanReviewConfig().signature == HumanReviewConfig().signature
