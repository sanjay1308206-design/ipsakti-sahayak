"""
Phase 15 tests: deterministic JSON serialization round-trip safety for
ReviewRequest, ReviewAction, and PresentationAuthorization
(docs/PHASE_15_HUMAN_IN_THE_LOOP.md Section V), and rejection of malformed
serialized data.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from _review_fixtures import make_ambiguous_classification, make_safe_grounded_response

from review.models import ReviewSchemaError
from review.policy import authorize_presentation, build_review_request
from review.serialize import (
    presentation_authorization_from_dict,
    presentation_authorization_to_dict,
    presentation_authorization_to_json,
    review_action_from_dict,
    review_action_to_dict,
    review_action_to_json,
    review_request_from_dict,
    review_request_to_dict,
    review_request_to_json,
)
from review.workflow import apply_action
from safety.evaluator import evaluate_safety

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def _escalated_request(authority_matrix, input_id, query="how can i protect this"):
    cls = make_ambiguous_classification(input_id)
    escalate_safety = evaluate_safety(f"{input_id}-S", classification_result=cls)
    request = build_review_request(input_id, query, canonical_query=query, classification_result=cls, safety_decision=escalate_safety)
    return request, escalate_safety


# ---------------------------------------------------------------------------
# ReviewRequest round-trip (27)
# ---------------------------------------------------------------------------


def test_review_request_round_trips_through_dict(authority_matrix):
    request, _ = _escalated_request(authority_matrix, "SER1")
    reloaded = review_request_from_dict(review_request_to_dict(request))
    assert reloaded == request


def test_review_request_round_trips_through_json(authority_matrix):
    request, _ = _escalated_request(authority_matrix, "SER2")
    parsed = json.loads(review_request_to_json(request))
    reloaded = review_request_from_dict(parsed["content"])
    assert reloaded == request


def test_review_request_json_preserves_unicode_without_escaping(authority_matrix):
    request, _ = _escalated_request(authority_matrix, "SER3", query="आयुर्वेद औषधि पंजीकरण protect this in India")
    raw_json = review_request_to_json(request)
    assert "आयुर्वेद" in raw_json


# ---------------------------------------------------------------------------
# ReviewAction round-trip
# ---------------------------------------------------------------------------


def test_review_action_round_trips_through_dict(authority_matrix):
    request, _ = _escalated_request(authority_matrix, "SER4")
    action = apply_action(request, [], reviewer_id="rev-1", action="START_REVIEW")
    reloaded = review_action_from_dict(review_action_to_dict(action))
    assert reloaded == action


def test_review_action_with_comment_and_evidence_round_trips_through_json(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("SER5-D1", "Content.")], "ser5-q")
    request, _ = _escalated_request(authority_matrix, "SER5", query="ser5-q")
    real_id = pack.evidence_items[0].evidence_id
    action = apply_action(
        request, [], reviewer_id="rev-1", action="APPROVE",
        reviewer_comment="Looks fine, अनुमोदित", selected_evidence_ids=[real_id], evidence_pack=pack,
    )
    parsed = json.loads(review_action_to_json(action))
    reloaded = review_action_from_dict(parsed["content"])
    assert reloaded == action
    assert "अनुमोदित" in review_action_to_json(action)


# ---------------------------------------------------------------------------
# PresentationAuthorization round-trip
# ---------------------------------------------------------------------------


def test_presentation_authorization_round_trips_through_dict(authority_matrix):
    request, escalate_safety = _escalated_request(authority_matrix, "SER6")
    action = apply_action(request, [], reviewer_id="rev-1", action="APPROVE")
    auth = authorize_presentation(escalate_safety, action)
    reloaded = presentation_authorization_from_dict(presentation_authorization_to_dict(auth))
    assert reloaded == auth


def test_presentation_authorization_automated_round_trips_through_json(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("SER7-D1", "Content.")], "ser7-q")
    auth = authorize_presentation(safety)
    parsed = json.loads(presentation_authorization_to_json(auth))
    reloaded = presentation_authorization_from_dict(parsed["content"])
    assert reloaded == auth


# ---------------------------------------------------------------------------
# Malformed serialization rejection (28)
# ---------------------------------------------------------------------------


def test_review_request_from_dict_rejects_non_dict():
    with pytest.raises(ReviewSchemaError):
        review_request_from_dict("not a dict")
    with pytest.raises(ReviewSchemaError):
        review_request_from_dict(None)


def test_review_request_from_dict_rejects_missing_field(authority_matrix):
    request, _ = _escalated_request(authority_matrix, "SER8")
    data = review_request_to_dict(request)
    del data["review_status"]
    with pytest.raises(ReviewSchemaError):
        review_request_from_dict(data)


def test_review_request_from_dict_rejects_malformed_case_snapshot(authority_matrix):
    request, _ = _escalated_request(authority_matrix, "SER9")
    data = review_request_to_dict(request)
    data["case_snapshot"] = "not a dict"
    with pytest.raises(ReviewSchemaError):
        review_request_from_dict(data)


def test_review_request_from_dict_rejects_invalid_trigger_reason(authority_matrix):
    request, _ = _escalated_request(authority_matrix, "SER10")
    data = review_request_to_dict(request)
    data["trigger_reasons"] = ["NOT_A_REAL_TRIGGER"]
    with pytest.raises(ReviewSchemaError):
        review_request_from_dict(data)


def test_review_request_from_dict_rejects_non_pending_review_status(authority_matrix):
    request, _ = _escalated_request(authority_matrix, "SER11")
    data = review_request_to_dict(request)
    data["review_status"] = "APPROVED"
    with pytest.raises(ReviewSchemaError):
        review_request_from_dict(data)


def test_review_action_from_dict_rejects_non_dict():
    with pytest.raises(ReviewSchemaError):
        review_action_from_dict([1, 2, 3])


def test_review_action_from_dict_rejects_wrong_type_field(authority_matrix):
    request, _ = _escalated_request(authority_matrix, "SER12")
    action = apply_action(request, [], reviewer_id="rev-1", action="START_REVIEW")
    data = review_action_to_dict(action)
    data["selected_evidence_ids"] = "not a list"
    with pytest.raises(ReviewSchemaError):
        review_action_from_dict(data)


def test_review_action_from_dict_rejects_inconsistent_transition(authority_matrix):
    request, _ = _escalated_request(authority_matrix, "SER13")
    action = apply_action(request, [], reviewer_id="rev-1", action="START_REVIEW")
    data = review_action_to_dict(action)
    data["new_status"] = "APPROVED"  # forged - START_REVIEW from PENDING must be IN_REVIEW
    with pytest.raises(ReviewSchemaError):
        review_action_from_dict(data)


def test_review_action_from_dict_rejects_credential_shaped_metadata(authority_matrix):
    request, _ = _escalated_request(authority_matrix, "SER14")
    action = apply_action(request, [], reviewer_id="rev-1", action="START_REVIEW")
    data = review_action_to_dict(action)
    data["metadata"] = {"api_key": "leaked"}
    with pytest.raises(ReviewSchemaError):
        review_action_from_dict(data)


def test_presentation_authorization_from_dict_rejects_missing_field(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("SER15-D1", "Content.")], "ser15-q")
    auth = authorize_presentation(safety)
    data = presentation_authorization_to_dict(auth)
    del data["source"]
    with pytest.raises(ReviewSchemaError):
        presentation_authorization_from_dict(data)


def test_presentation_authorization_from_dict_rejects_altered_disclaimer(authority_matrix):
    request, escalate_safety = _escalated_request(authority_matrix, "SER16")
    action = apply_action(request, [], reviewer_id="rev-1", action="APPROVE")
    auth = authorize_presentation(escalate_safety, action)
    data = presentation_authorization_to_dict(auth)
    data["disclaimer"] = "this is a real legal certification"
    with pytest.raises(ReviewSchemaError):
        presentation_authorization_from_dict(data)
