"""
Phase 15 tests: deterministic behavior (docs/PHASE_15_HUMAN_IN_THE_LOOP.md
Section W). Identical inputs must produce identical ReviewRequest/
ReviewAction objects, identical identity hashes, and byte-identical JSON -
no randomness, no wall-clock timestamps, no dependence on call order.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _review_fixtures import make_ambiguous_classification, make_safe_grounded_response

from review.policy import build_review_request, evaluate_review_trigger
from review.serialize import review_action_to_json, review_request_to_json
from review.workflow import apply_action
from safety.evaluator import evaluate_safety

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def test_repeated_trigger_evaluation_is_identical():
    cls = make_ambiguous_classification("DET1")
    escalate_safety = evaluate_safety("DET1-S", classification_result=cls)
    results = [evaluate_review_trigger(classification_result=cls, safety_decision=escalate_safety) for _ in range(10)]
    assert all(r == results[0] for r in results)


def test_repeated_review_request_construction_is_identical():
    cls = make_ambiguous_classification("DET2")
    escalate_safety = evaluate_safety("DET2-S", classification_result=cls)
    requests = [
        build_review_request("DET2", "how can i protect this", classification_result=cls, safety_decision=escalate_safety)
        for _ in range(10)
    ]
    assert all(r == requests[0] for r in requests)


def test_review_request_id_is_identical_across_repeated_calls():
    cls = make_ambiguous_classification("DET3")
    escalate_safety = evaluate_safety("DET3-S", classification_result=cls)
    ids = {
        build_review_request("DET3", "how can i protect this", classification_result=cls, safety_decision=escalate_safety).review_request_id
        for _ in range(10)
    }
    assert len(ids) == 1


def test_review_request_json_is_byte_identical_across_repeated_calls():
    cls = make_ambiguous_classification("DET4")
    escalate_safety = evaluate_safety("DET4-S", classification_result=cls)
    jsons = {
        review_request_to_json(
            build_review_request("DET4", "how can i protect this", classification_result=cls, safety_decision=escalate_safety)
        )
        for _ in range(10)
    }
    assert len(jsons) == 1


def test_review_request_id_differs_for_different_input_ids():
    cls_a = make_ambiguous_classification("DET5A")
    cls_b = make_ambiguous_classification("DET5B")
    safety_a = evaluate_safety("DET5A-S", classification_result=cls_a)
    safety_b = evaluate_safety("DET5B-S", classification_result=cls_b)
    r1 = build_review_request("DET5A", "how can i protect this", classification_result=cls_a, safety_decision=safety_a)
    r2 = build_review_request("DET5B", "how can i protect this", classification_result=cls_b, safety_decision=safety_b)
    assert r1.review_request_id != r2.review_request_id


def test_review_action_id_is_deterministic_given_identical_arguments():
    cls = make_ambiguous_classification("DET6")
    escalate_safety = evaluate_safety("DET6-S", classification_result=cls)
    request = build_review_request("DET6", "how can i protect this", classification_result=cls, safety_decision=escalate_safety)
    actions = [apply_action(request, [], reviewer_id="rev-1", action="START_REVIEW") for _ in range(10)]
    ids = {a.review_action_id for a in actions}
    assert len(ids) == 1
    assert all(a == actions[0] for a in actions)


def test_review_action_json_is_byte_identical_across_repeated_calls():
    cls = make_ambiguous_classification("DET7")
    escalate_safety = evaluate_safety("DET7-S", classification_result=cls)
    request = build_review_request("DET7", "how can i protect this", classification_result=cls, safety_decision=escalate_safety)
    jsons = {review_action_to_json(apply_action(request, [], reviewer_id="rev-1", action="APPROVE")) for _ in range(10)}
    assert len(jsons) == 1


def test_review_action_id_differs_for_different_reviewer_ids():
    cls = make_ambiguous_classification("DET8")
    escalate_safety = evaluate_safety("DET8-S", classification_result=cls)
    request = build_review_request("DET8", "how can i protect this", classification_result=cls, safety_decision=escalate_safety)
    a1 = apply_action(request, [], reviewer_id="rev-1", action="APPROVE")
    a2 = apply_action(request, [], reviewer_id="rev-2", action="APPROVE")
    assert a1.review_action_id != a2.review_action_id


def test_review_action_id_differs_by_sequence_number(authority_matrix):
    cls = make_ambiguous_classification("DET9")
    escalate_safety = evaluate_safety("DET9-S", classification_result=cls)
    request = build_review_request("DET9", "how can i protect this", classification_result=cls, safety_decision=escalate_safety)
    a1 = apply_action(request, [], reviewer_id="rev-1", action="START_REVIEW")
    a2 = apply_action(request, [a1], reviewer_id="rev-1", action="APPROVE")
    assert a1.sequence_number == 0
    assert a2.sequence_number == 1
    assert a1.review_action_id != a2.review_action_id
