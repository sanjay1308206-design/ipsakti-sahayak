"""
Phase 15 tests: review-trigger determination and review-request
construction (docs/PHASE_15_HUMAN_IN_THE_LOOP.md Section E/F), and the
"HUMAN REVIEW DECISION -> DELIVERY CONTROL" presentation-authorization
boundary (docs Section O).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _review_fixtures import (
    make_ambiguous_classification,
    make_ambiguous_jurisdiction,
    make_conflicting_track_classification,
    make_context,
    make_failed_citation_results,
    make_needs_evidence_classification,
    make_safe_grounded_response,
    make_unresolved_classification,
    make_unresolved_jurisdiction,
    make_unsupported_language_delivery_result,
    make_valid_citation_results,
)

from review.policy import authorize_presentation, build_review_request, evaluate_review_trigger
from safety.evaluator import evaluate_safety

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. Review request creation / 6. No review for safe normal flow
# ---------------------------------------------------------------------------


def test_no_review_for_safe_normal_flow(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("P1-D1", "Content.")], "safe query")
    assessment = evaluate_review_trigger(grounded_response=gr, safety_decision=safety)
    assert assessment.requires_review is False
    assert assessment.priority == "NOT_APPLICABLE"

    request = build_review_request("P1", "safe query", grounded_response=gr, safety_decision=safety)
    assert request is None


def test_review_request_created_with_full_case_snapshot(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("P2-D1", "Content.")], "escalate query")
    cls = make_ambiguous_classification("P2")
    escalate_safety = evaluate_safety("P2-S", classification_result=cls)
    request = build_review_request(
        "P2", "how can i protect this", canonical_query="how can i protect this",
        classification_result=cls, safety_decision=escalate_safety,
    )
    assert request is not None
    assert request.input_id == "P2"
    assert request.case_snapshot.classification_state == "AMBIGUOUS"
    assert request.case_snapshot.safety_status == "ESCALATE"
    assert request.review_status == "PENDING"


# ---------------------------------------------------------------------------
# 2. Review trigger for ESCALATE
# ---------------------------------------------------------------------------


def test_trigger_fires_for_safety_escalate():
    cls = make_ambiguous_classification("T2")
    escalate_safety = evaluate_safety("T2-S", classification_result=cls)
    assert escalate_safety.safety_status == "ESCALATE"
    assessment = evaluate_review_trigger(safety_decision=escalate_safety)
    assert assessment.requires_review is True
    assert "SAFETY_ESCALATE" in assessment.trigger_reasons
    assert assessment.priority == "CRITICAL"


def test_trigger_fires_for_safety_abstain():
    abstain_safety = evaluate_safety("T2B-S")
    assert abstain_safety.safety_status == "ABSTAIN"
    assessment = evaluate_review_trigger(safety_decision=abstain_safety)
    assert "SAFETY_ABSTAIN" in assessment.trigger_reasons
    assert assessment.priority == "HIGH"


# ---------------------------------------------------------------------------
# 3. Review trigger for ambiguous classification
# ---------------------------------------------------------------------------


def test_trigger_fires_for_ambiguous_classification():
    cls = make_ambiguous_classification("T3")
    assessment = evaluate_review_trigger(classification_result=cls)
    assert "CLASSIFICATION_AMBIGUOUS" in assessment.trigger_reasons


def test_trigger_fires_for_unresolved_classification():
    cls = make_unresolved_classification("T3B")
    assessment = evaluate_review_trigger(classification_result=cls)
    assert "CLASSIFICATION_UNRESOLVED" in assessment.trigger_reasons
    assert assessment.priority == "NORMAL"


def test_trigger_fires_for_needs_evidence_classification():
    cls = make_needs_evidence_classification("T3C")
    assessment = evaluate_review_trigger(classification_result=cls)
    assert "CLASSIFICATION_NEEDS_EVIDENCE" in assessment.trigger_reasons


def test_trigger_fires_for_conflicting_regulatory_track():
    cls = make_conflicting_track_classification("T3D")
    assessment = evaluate_review_trigger(classification_result=cls)
    assert "REGULATORY_TRACK_CONFLICTING" in assessment.trigger_reasons


# ---------------------------------------------------------------------------
# 4. Review trigger for jurisdiction uncertainty
# ---------------------------------------------------------------------------


def test_trigger_fires_for_ambiguous_jurisdiction():
    jur = make_ambiguous_jurisdiction("T4")
    assessment = evaluate_review_trigger(jurisdiction_decision=jur)
    assert "JURISDICTION_AMBIGUOUS" in assessment.trigger_reasons
    assert assessment.priority == "HIGH"


def test_trigger_fires_for_unresolved_jurisdiction():
    jur = make_unresolved_jurisdiction("T4B")
    assessment = evaluate_review_trigger(jurisdiction_decision=jur)
    assert "JURISDICTION_UNRESOLVED" in assessment.trigger_reasons
    assert assessment.priority == "NORMAL"


# ---------------------------------------------------------------------------
# 5. Review trigger for grounding/citation issues
# ---------------------------------------------------------------------------


def test_trigger_fires_for_citation_integrity_failure(authority_matrix):
    pack, results = make_failed_citation_results(authority_matrix, [("T5-D1", "Content.")], "t5-q")
    assessment = evaluate_review_trigger(citation_results=results)
    assert "CITATION_INTEGRITY_FAILURE" in assessment.trigger_reasons


def test_no_trigger_for_all_valid_citations(authority_matrix):
    pack, results = make_valid_citation_results(authority_matrix, [("T5B-D1", "Content.")], "t5b-q")
    assessment = evaluate_review_trigger(citation_results=results)
    assert "CITATION_INTEGRITY_FAILURE" not in assessment.trigger_reasons


def test_trigger_fires_for_grounding_failure():
    from _review_fixtures import make_abstained_grounded_response

    _, gr = make_abstained_grounded_response("t5c-q")
    assessment = evaluate_review_trigger(grounded_response=gr)
    assert "GROUNDING_FAILURE" in assessment.trigger_reasons


def test_trigger_fires_for_multilingual_delivery_issue(authority_matrix):
    pack, gr, safety, ml = make_unsupported_language_delivery_result(authority_matrix, [("T5D-D1", "Content.")], "t5d-q")
    assessment = evaluate_review_trigger(multilingual_result=ml)
    assert "MULTILINGUAL_DELIVERY_ISSUE" in assessment.trigger_reasons


# ---------------------------------------------------------------------------
# Type discipline
# ---------------------------------------------------------------------------


def test_evaluate_review_trigger_rejects_wrong_types():
    with pytest.raises(TypeError):
        evaluate_review_trigger(classification_result="not a classification result")
    with pytest.raises(TypeError):
        evaluate_review_trigger(jurisdiction_decision="not a jurisdiction decision")
    with pytest.raises(TypeError):
        evaluate_review_trigger(citation_results=["not a citation result"])
    with pytest.raises(TypeError):
        evaluate_review_trigger(grounded_response="not a grounded response")
    with pytest.raises(TypeError):
        evaluate_review_trigger(safety_decision="not a safety decision")
    with pytest.raises(TypeError):
        evaluate_review_trigger(multilingual_result="not a multilingual result")


def test_build_review_request_rejects_empty_input_id():
    with pytest.raises(ValueError):
        build_review_request("", "query")


def test_build_review_request_rejects_non_string_query():
    with pytest.raises(TypeError):
        build_review_request("X", 12345)


# ---------------------------------------------------------------------------
# authorize_presentation (delivery-control boundary)
# ---------------------------------------------------------------------------


def test_authorize_presentation_automated_safe(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("AUTH1-D1", "Content.")], "auth1-q")
    auth = authorize_presentation(safety)
    assert auth.authorized is True
    assert auth.source == "AUTOMATED_SAFE_TO_PRESENT"
    assert auth.disclaimer is None


def test_authorize_presentation_blocked_without_review_action():
    abstain_safety = evaluate_safety("AUTH2-S")
    auth = authorize_presentation(abstain_safety)
    assert auth.authorized is False
    assert auth.source == "BLOCKED"


def test_authorize_presentation_rejects_wrong_safety_decision_type():
    with pytest.raises(TypeError):
        authorize_presentation("not a safety decision")


def test_authorize_presentation_rejects_wrong_review_action_type():
    abstain_safety = evaluate_safety("AUTH3-S")
    with pytest.raises(TypeError):
        authorize_presentation(abstain_safety, review_action="not a review action")
