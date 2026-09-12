"""
Phase 15 review-trigger policy and review-request construction
(docs/PHASE_15_HUMAN_IN_THE_LOOP.md Sections E, F, O).

`evaluate_review_trigger` is the ONLY place in this package that decides
WHETHER a case requires human review - it reads already-established
upstream facts (Phase 9/10/11/12/13/14's own closed vocabularies) and
never computes a new heuristic, score, or probability. `build_review_request`
wraps that decision into a structured, serializable `ReviewRequest`, or
returns `None` when no trigger fired - it never fabricates a request for
a safe, normal case. `authorize_presentation` is the "HUMAN REVIEW
DECISION -> DELIVERY CONTROL" boundary (docs Section O) - a pure
read-and-combine function that never mutates the `SafetyDecision` or
`ReviewAction` it reads.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from citation.models import CitationValidationResult
from classification.models import ClassificationResult
from generation.models import GroundedResponse
from jurisdiction.models import JurisdictionDecision
from multilingual.models import MultilingualDeliveryResult
from safety.models import SafetyDecision

from .models import (
    FIXED_HUMAN_REVIEW_DISCLAIMER,
    INITIAL_REVIEW_STATUS,
    PRIORITY_LEVELS,
    PRIORITY_NOT_APPLICABLE,
    REVIEW_SCHEMA_VERSION,
    TRIGGER_CITATION_INTEGRITY_FAILURE,
    TRIGGER_CLASSIFICATION_AMBIGUOUS,
    TRIGGER_CLASSIFICATION_NEEDS_EVIDENCE,
    TRIGGER_CLASSIFICATION_UNRESOLVED,
    TRIGGER_GROUNDING_FAILURE,
    TRIGGER_JURISDICTION_AMBIGUOUS,
    TRIGGER_JURISDICTION_UNRESOLVED,
    TRIGGER_MULTILINGUAL_DELIVERY_ISSUE,
    TRIGGER_PRIORITY,
    TRIGGER_REGULATORY_TRACK_CONFLICTING,
    TRIGGER_SAFETY_ABSTAIN,
    TRIGGER_SAFETY_ESCALATE,
    HumanReviewConfig,
    PresentationAuthorization,
    ReviewAction,
    ReviewCaseSnapshot,
    ReviewRequest,
    ReviewTriggerAssessment,
)


def compute_review_request_id(
    schema_version: str,
    input_id: str,
    original_query: str,
    trigger_reasons: list,
    priority: str,
    config_signature: str,
) -> str:
    """Deterministic, backend-owned review-request identity - never a random UUID, never a timestamp."""
    canonical = "|".join(
        [
            "human-review-request-v1",
            schema_version,
            input_id,
            original_query,
            ",".join(sorted(trigger_reasons)),
            priority,
            config_signature,
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def evaluate_review_trigger(
    *,
    classification_result: Optional[ClassificationResult] = None,
    jurisdiction_decision: Optional[JurisdictionDecision] = None,
    citation_results: Optional[list] = None,
    grounded_response: Optional[GroundedResponse] = None,
    safety_decision: Optional[SafetyDecision] = None,
    multilingual_result: Optional[MultilingualDeliveryResult] = None,
) -> ReviewTriggerAssessment:
    """
    The sole trigger-determination entry point. Every check below reads
    ONE already-closed upstream vocabulary value - no new detection logic,
    keyword heuristic, or numeric threshold is introduced anywhere here.
    """
    if classification_result is not None and not isinstance(classification_result, ClassificationResult):
        raise TypeError(f"classification_result must be a ClassificationResult or None, got {type(classification_result).__name__}")
    if jurisdiction_decision is not None and not isinstance(jurisdiction_decision, JurisdictionDecision):
        raise TypeError(f"jurisdiction_decision must be a JurisdictionDecision or None, got {type(jurisdiction_decision).__name__}")
    if citation_results is not None:
        if not isinstance(citation_results, list) or any(not isinstance(r, CitationValidationResult) for r in citation_results):
            raise TypeError("citation_results must be a list of CitationValidationResult or None")
    if grounded_response is not None and not isinstance(grounded_response, GroundedResponse):
        raise TypeError(f"grounded_response must be a GroundedResponse or None, got {type(grounded_response).__name__}")
    if safety_decision is not None and not isinstance(safety_decision, SafetyDecision):
        raise TypeError(f"safety_decision must be a SafetyDecision or None, got {type(safety_decision).__name__}")
    if multilingual_result is not None and not isinstance(multilingual_result, MultilingualDeliveryResult):
        raise TypeError(f"multilingual_result must be a MultilingualDeliveryResult or None, got {type(multilingual_result).__name__}")

    reasons: list = []
    basis: list = []

    if safety_decision is not None:
        if safety_decision.safety_status == "ESCALATE":
            reasons.append(TRIGGER_SAFETY_ESCALATE)
            basis.append(f"safety_decision.safety_status={safety_decision.safety_status!r} (reason_code={safety_decision.reason_code!r})")
        elif safety_decision.safety_status == "ABSTAIN":
            reasons.append(TRIGGER_SAFETY_ABSTAIN)
            basis.append(f"safety_decision.safety_status={safety_decision.safety_status!r} (reason_code={safety_decision.reason_code!r})")

    if classification_result is not None:
        state = classification_result.classification_state
        if state == "AMBIGUOUS" or classification_result.requires_escalation:
            reasons.append(TRIGGER_CLASSIFICATION_AMBIGUOUS)
            basis.append(f"classification_result.classification_state={state!r}, requires_escalation={classification_result.requires_escalation!r}")
        elif state == "UNKNOWN":
            reasons.append(TRIGGER_CLASSIFICATION_UNRESOLVED)
            basis.append(f"classification_result.classification_state={state!r}")
        elif state == "NEEDS_EVIDENCE":
            reasons.append(TRIGGER_CLASSIFICATION_NEEDS_EVIDENCE)
            basis.append(f"classification_result.classification_state={state!r}")

        regulatory_track = classification_result.formulation_classification.regulatory_track
        if regulatory_track == "CONFLICTING":
            reasons.append(TRIGGER_REGULATORY_TRACK_CONFLICTING)
            basis.append(f"classification_result.formulation_classification.regulatory_track={regulatory_track!r}")

    if jurisdiction_decision is not None:
        state = jurisdiction_decision.state
        if state == "AMBIGUOUS" or jurisdiction_decision.requires_escalation:
            reasons.append(TRIGGER_JURISDICTION_AMBIGUOUS)
            basis.append(f"jurisdiction_decision.state={state!r}, requires_escalation={jurisdiction_decision.requires_escalation!r}")
        elif state == "UNKNOWN":
            reasons.append(TRIGGER_JURISDICTION_UNRESOLVED)
            basis.append(f"jurisdiction_decision.state={state!r}")

    if citation_results:
        failing = [r for r in citation_results if r.status != "VALID"]
        if failing:
            reasons.append(TRIGGER_CITATION_INTEGRITY_FAILURE)
            basis.append(f"{len(failing)} of {len(citation_results)} citation_results are not VALID")

    if grounded_response is not None and grounded_response.grounding_status != "GROUNDED":
        reasons.append(TRIGGER_GROUNDING_FAILURE)
        basis.append(f"grounded_response.grounding_status={grounded_response.grounding_status!r}")

    if multilingual_result is not None and multilingual_result.delivery_status in ("TRANSLATION_FAILED", "UNSUPPORTED_LANGUAGE"):
        reasons.append(TRIGGER_MULTILINGUAL_DELIVERY_ISSUE)
        basis.append(f"multilingual_result.delivery_status={multilingual_result.delivery_status!r}")

    requires_review = bool(reasons)
    if requires_review:
        priority = max((TRIGGER_PRIORITY[r] for r in reasons), key=PRIORITY_LEVELS.index)
        explanation = "Human review required: " + "; ".join(basis)
    else:
        priority = PRIORITY_NOT_APPLICABLE
        explanation = "No human review required: every inspected upstream signal was within normal, non-ambiguous bounds."

    return ReviewTriggerAssessment(
        requires_review=requires_review, trigger_reasons=reasons, priority=priority, basis=basis, explanation=explanation,
    )


def _build_case_snapshot(
    *,
    classification_result,
    jurisdiction_decision,
    citation_results,
    grounded_response,
    safety_decision,
    multilingual_result,
) -> ReviewCaseSnapshot:
    citation_counts = (None, None, None, None)
    if citation_results:
        total = len(citation_results)
        valid = sum(1 for r in citation_results if r.status == "VALID")
        invalid = sum(1 for r in citation_results if r.status == "INVALID")
        unresolved = sum(1 for r in citation_results if r.status == "UNRESOLVED")
        citation_counts = (total, valid, invalid, unresolved)
    elif grounded_response is not None:
        summary = grounded_response.citation_validation_summary
        citation_counts = (summary.total_references, summary.valid_count, summary.invalid_count, summary.unresolved_count)

    synthetic = None
    if grounded_response is not None:
        synthetic = grounded_response.synthetic
    elif safety_decision is not None:
        synthetic = safety_decision.synthetic

    return ReviewCaseSnapshot(
        schema_version=REVIEW_SCHEMA_VERSION,
        classification_state=classification_result.classification_state if classification_result is not None else None,
        classification_input_id=classification_result.input_id if classification_result is not None else None,
        regulatory_track=classification_result.formulation_classification.regulatory_track if classification_result is not None else None,
        evidence_state=classification_result.evidence_state if classification_result is not None else None,
        jurisdiction_state=jurisdiction_decision.state if jurisdiction_decision is not None else None,
        jurisdiction_decision_id=jurisdiction_decision.decision_id if jurisdiction_decision is not None else None,
        grounding_status=grounded_response.grounding_status if grounded_response is not None else None,
        response_id=grounded_response.response_id if grounded_response is not None else None,
        evidence_pack_id=grounded_response.evidence_pack_id if grounded_response is not None else None,
        cited_evidence_ids=list(grounded_response.cited_evidence_ids) if grounded_response is not None else [],
        citation_total_references=citation_counts[0],
        citation_valid_count=citation_counts[1],
        citation_invalid_count=citation_counts[2],
        citation_unresolved_count=citation_counts[3],
        safety_status=safety_decision.safety_status if safety_decision is not None else None,
        safety_decision_id=safety_decision.decision_id if safety_decision is not None else None,
        safety_engineering_signal_band=safety_decision.engineering_signal_band if safety_decision is not None else None,
        multilingual_delivery_status=multilingual_result.delivery_status if multilingual_result is not None else None,
        multilingual_result_id=multilingual_result.result_id if multilingual_result is not None else None,
        requested_language=multilingual_result.requested_language if multilingual_result is not None else None,
        detected_script=multilingual_result.detected_script if multilingual_result is not None else None,
        synthetic=synthetic,
    )


def build_review_request(
    input_id: str,
    original_query: str,
    canonical_query: Optional[str] = None,
    *,
    classification_result: Optional[ClassificationResult] = None,
    jurisdiction_decision: Optional[JurisdictionDecision] = None,
    citation_results: Optional[list] = None,
    grounded_response: Optional[GroundedResponse] = None,
    safety_decision: Optional[SafetyDecision] = None,
    multilingual_result: Optional[MultilingualDeliveryResult] = None,
    config: Optional[HumanReviewConfig] = None,
) -> Optional[ReviewRequest]:
    """
    Builds a `ReviewRequest` only when `evaluate_review_trigger` actually
    fires - returns `None` for a safe, normal flow (never fabricates an
    escalation for a case that does not need one).
    """
    if not isinstance(input_id, str) or not input_id.strip():
        raise ValueError("input_id must be a non-empty string")
    if not isinstance(original_query, str):
        raise TypeError(f"original_query must be a string, got {type(original_query).__name__}")
    if canonical_query is not None and not isinstance(canonical_query, str):
        raise TypeError(f"canonical_query must be a string or None, got {type(canonical_query).__name__}")
    if config is None:
        config = HumanReviewConfig()
    elif not isinstance(config, HumanReviewConfig):
        raise TypeError(f"config must be a HumanReviewConfig or None, got {type(config).__name__}")

    assessment = evaluate_review_trigger(
        classification_result=classification_result,
        jurisdiction_decision=jurisdiction_decision,
        citation_results=citation_results,
        grounded_response=grounded_response,
        safety_decision=safety_decision,
        multilingual_result=multilingual_result,
    )
    if not assessment.requires_review:
        return None

    snapshot = _build_case_snapshot(
        classification_result=classification_result,
        jurisdiction_decision=jurisdiction_decision,
        citation_results=citation_results,
        grounded_response=grounded_response,
        safety_decision=safety_decision,
        multilingual_result=multilingual_result,
    )

    review_request_id = compute_review_request_id(
        config.schema_version, input_id, original_query, assessment.trigger_reasons, assessment.priority, config.signature,
    )

    return ReviewRequest(
        schema_version=config.schema_version,
        review_request_id=review_request_id,
        input_id=input_id,
        original_query=original_query,
        canonical_query=canonical_query,
        case_snapshot=snapshot,
        trigger_reasons=assessment.trigger_reasons,
        priority=assessment.priority,
        review_reason=assessment.explanation,
        review_status=INITIAL_REVIEW_STATUS,
        config_signature=config.signature,
    )


def authorize_presentation(
    safety_decision: SafetyDecision,
    review_action: Optional[ReviewAction] = None,
    config: Optional[HumanReviewConfig] = None,
) -> PresentationAuthorization:
    """
    The "HUMAN REVIEW DECISION -> DELIVERY CONTROL" boundary (docs Section
    O). Reads `safety_decision`/`review_action` only - never mutates
    either, never writes a new `safety_status` anywhere. An `ABSTAIN`/
    `ESCALATE` `SafetyDecision` is authorized for presentation ONLY when a
    real `ReviewAction` with `action == "APPROVE"`/`new_status ==
    "APPROVED"` is supplied - and even then, `source` is always
    `HUMAN_REVIEW_APPROVED` (never rewritten to look like an automated
    `SAFE_TO_PRESENT`), and `disclaimer` always carries the fixed,
    non-legal-certification text.
    """
    if not isinstance(safety_decision, SafetyDecision):
        raise TypeError(f"safety_decision must be a SafetyDecision, got {type(safety_decision).__name__}")
    if review_action is not None and not isinstance(review_action, ReviewAction):
        raise TypeError(f"review_action must be a ReviewAction or None, got {type(review_action).__name__}")
    if config is None:
        config = HumanReviewConfig()
    elif not isinstance(config, HumanReviewConfig):
        raise TypeError(f"config must be a HumanReviewConfig or None, got {type(config).__name__}")

    if safety_decision.safety_status == "SAFE_TO_PRESENT":
        return PresentationAuthorization(
            schema_version=config.schema_version, authorized=True, source="AUTOMATED_SAFE_TO_PRESENT",
            safety_status=safety_decision.safety_status, review_action_id=None,
            explanation="Phase 13 marked this response SAFE_TO_PRESENT automatically - no human review was required for delivery.",
            disclaimer=None,
        )

    if review_action is not None and review_action.action == "APPROVE" and review_action.new_status == "APPROVED":
        return PresentationAuthorization(
            schema_version=config.schema_version, authorized=True, source="HUMAN_REVIEW_APPROVED",
            safety_status=safety_decision.safety_status, review_action_id=review_action.review_action_id,
            explanation=(
                f"Phase 13 marked this response {safety_decision.safety_status!r}, but a designated reviewer "
                f"explicitly approved presentation via review_action_id={review_action.review_action_id!r}."
            ),
            disclaimer=FIXED_HUMAN_REVIEW_DISCLAIMER,
        )

    return PresentationAuthorization(
        schema_version=config.schema_version, authorized=False, source="BLOCKED",
        safety_status=safety_decision.safety_status, review_action_id=None,
        explanation=(
            f"Phase 13 marked this response {safety_decision.safety_status!r} and no recorded human-review "
            f"approval authorizes presenting it."
        ),
        disclaimer=None,
    )
