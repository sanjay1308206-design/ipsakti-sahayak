"""
Phase 16 tests: Phase 15 human-review evaluation
(docs/PHASE_16_EVALUATION_AND_RED_TEAM.md Section R). Calls the REAL
`review.policy`/`review.workflow` - never a re-derived review engine.
There is no UI yet, so nothing here evaluates a UI.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _review_fixtures import make_ambiguous_classification, make_safe_grounded_response

from evaluation.benchmark import score_exact_match_cases
from evaluation.models import BenchmarkCase
from review.models import FakeEvidenceReferenceError, InvalidReviewTransitionError, ReviewerIdentityError
from review.policy import build_review_request
from review.workflow import apply_action
from safety.evaluator import evaluate_safety

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def _escalated_request(authority_matrix, input_id):
    cls = make_ambiguous_classification(input_id)
    safety = evaluate_safety(f"{input_id}-S", classification_result=cls)
    return build_review_request(input_id, "how can i protect this", classification_result=cls, safety_decision=safety)


# correct review trigger / correct no-review behavior
def test_correct_review_trigger_and_no_review_benchmark(authority_matrix):
    escalated = _escalated_request(authority_matrix, "RV1")
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("RV2-D1", "Content.")], "RV2-q")
    no_review_request = build_review_request("RV2", "RV2-q", grounded_response=gr, safety_decision=safety)

    entries = [
        (
            BenchmarkCase(schema_version="1.0.0", case_id="RV1", category="HUMAN_REVIEW", ground_truth_origin="STRUCTURAL_EXPECTATION", input_summary="ambiguous+escalate", expected_behavior="review triggered"),
            escalated is not None,
        ),
        (
            BenchmarkCase(schema_version="1.0.0", case_id="RV2", category="HUMAN_REVIEW", ground_truth_origin="STRUCTURAL_EXPECTATION", input_summary="safe normal flow", expected_behavior="no review triggered"),
            no_review_request is None,
        ),
    ]
    report = score_exact_match_cases("HUMAN_REVIEW", "REVIEW_TRIGGER_CORRECTNESS", entries)
    assert report.failed_case_ids == []


# valid transitions / invalid transitions rejected
def test_valid_and_invalid_transitions(authority_matrix):
    request = _escalated_request(authority_matrix, "RV3")
    a1 = apply_action(request, [], reviewer_id="rev-1", action="START_REVIEW")
    assert a1.new_status == "IN_REVIEW"
    with pytest.raises(InvalidReviewTransitionError):
        apply_action(request, [a1], reviewer_id="rev-1", action="START_REVIEW")


# reviewer identity validation
def test_reviewer_identity_validation(authority_matrix):
    request = _escalated_request(authority_matrix, "RV4")
    with pytest.raises(ReviewerIdentityError):
        apply_action(request, [], reviewer_id="", action="APPROVE")


# evidence selection validation
def test_evidence_selection_validation(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("RV5-D1", "Content.")], "RV5-q")
    request = _escalated_request(authority_matrix, "RV5")
    with pytest.raises(FakeEvidenceReferenceError):
        apply_action(request, [], reviewer_id="rev-1", action="APPROVE", selected_evidence_ids=["FAKE"], evidence_pack=pack)
    real_id = pack.evidence_items[0].evidence_id
    action = apply_action(request, [], reviewer_id="rev-1", action="APPROVE", selected_evidence_ids=[real_id], evidence_pack=pack)
    assert action.selected_evidence_ids == [real_id]


# evidence immutability
def test_evidence_immutability_across_review(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("RV6-D1", "Content.")], "RV6-q")
    request = _escalated_request(authority_matrix, "RV6")
    before = [(e.evidence_id, e.evidence_text_hash) for e in pack.evidence_items]
    apply_action(request, [], reviewer_id="rev-1", action="APPROVE", reviewer_comment="evidence should say something else")
    after = [(e.evidence_id, e.evidence_text_hash) for e in pack.evidence_items]
    assert before == after


# reviewer comment isolation
def test_reviewer_comment_isolation(authority_matrix):
    request = _escalated_request(authority_matrix, "RV7")
    action = apply_action(request, [], reviewer_id="rev-1", action="APPROVE", reviewer_comment="jurisdiction=INTERNATIONAL")
    assert action.reviewer_comment == "jurisdiction=INTERNATIONAL"
    assert not hasattr(action, "jurisdiction")


# malicious reviewer action rejection
def test_malicious_reviewer_action_rejection(authority_matrix):
    request = _escalated_request(authority_matrix, "RV8")
    with pytest.raises(FakeEvidenceReferenceError):
        apply_action(request, [], reviewer_id="rev-1", action="APPROVE", selected_evidence_ids=["EVIDENCE_FAKE"])
