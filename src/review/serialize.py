"""
Phase 15 deterministic JSON serialization
(docs/PHASE_15_HUMAN_IN_THE_LOOP.md Section V), mirroring
src/safety/serialize.py's convention exactly. `ReviewRequest`/`ReviewAction`/
`PresentationAuthorization` are trusted shapes (validated workflow output,
not untrusted provider output) - full explicit field reconstruction with
every invariant re-enforced on deserialization. No pickle, no arbitrary/
executable deserialization anywhere.
"""

from __future__ import annotations

import json

from .models import (
    PresentationAuthorization,
    ReviewAction,
    ReviewCaseSnapshot,
    ReviewRequest,
    ReviewSchemaError,
)


def _require_dict(data, what: str) -> dict:
    if not isinstance(data, dict):
        raise ReviewSchemaError(f"malformed {what}: expected a JSON object, got {type(data).__name__}")
    return data


# ---------------------------------------------------------------------------
# ReviewCaseSnapshot (nested inside ReviewRequest)
# ---------------------------------------------------------------------------


def case_snapshot_to_dict(snapshot: ReviewCaseSnapshot) -> dict:
    return {
        "schema_version": snapshot.schema_version,
        "classification_state": snapshot.classification_state,
        "classification_input_id": snapshot.classification_input_id,
        "regulatory_track": snapshot.regulatory_track,
        "evidence_state": snapshot.evidence_state,
        "jurisdiction_state": snapshot.jurisdiction_state,
        "jurisdiction_decision_id": snapshot.jurisdiction_decision_id,
        "grounding_status": snapshot.grounding_status,
        "response_id": snapshot.response_id,
        "evidence_pack_id": snapshot.evidence_pack_id,
        "cited_evidence_ids": list(snapshot.cited_evidence_ids),
        "citation_total_references": snapshot.citation_total_references,
        "citation_valid_count": snapshot.citation_valid_count,
        "citation_invalid_count": snapshot.citation_invalid_count,
        "citation_unresolved_count": snapshot.citation_unresolved_count,
        "safety_status": snapshot.safety_status,
        "safety_decision_id": snapshot.safety_decision_id,
        "safety_engineering_signal_band": snapshot.safety_engineering_signal_band,
        "multilingual_delivery_status": snapshot.multilingual_delivery_status,
        "multilingual_result_id": snapshot.multilingual_result_id,
        "requested_language": snapshot.requested_language,
        "detected_script": snapshot.detected_script,
        "synthetic": snapshot.synthetic,
    }


def case_snapshot_from_dict(data: dict) -> ReviewCaseSnapshot:
    data = _require_dict(data, "review case snapshot data")
    try:
        cited_evidence_ids = data["cited_evidence_ids"]
        if not isinstance(cited_evidence_ids, list) or any(not isinstance(x, str) for x in cited_evidence_ids):
            raise TypeError("cited_evidence_ids must be a list of strings")
        snapshot = ReviewCaseSnapshot(
            schema_version=data["schema_version"],
            classification_state=data["classification_state"],
            classification_input_id=data["classification_input_id"],
            regulatory_track=data["regulatory_track"],
            evidence_state=data["evidence_state"],
            jurisdiction_state=data["jurisdiction_state"],
            jurisdiction_decision_id=data["jurisdiction_decision_id"],
            grounding_status=data["grounding_status"],
            response_id=data["response_id"],
            evidence_pack_id=data["evidence_pack_id"],
            cited_evidence_ids=cited_evidence_ids,
            citation_total_references=data["citation_total_references"],
            citation_valid_count=data["citation_valid_count"],
            citation_invalid_count=data["citation_invalid_count"],
            citation_unresolved_count=data["citation_unresolved_count"],
            safety_status=data["safety_status"],
            safety_decision_id=data["safety_decision_id"],
            safety_engineering_signal_band=data["safety_engineering_signal_band"],
            multilingual_delivery_status=data["multilingual_delivery_status"],
            multilingual_result_id=data["multilingual_result_id"],
            requested_language=data["requested_language"],
            detected_script=data["detected_script"],
            synthetic=data["synthetic"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ReviewSchemaError(f"malformed review case snapshot data: {exc}") from exc
    return snapshot


# ---------------------------------------------------------------------------
# ReviewRequest
# ---------------------------------------------------------------------------


def review_request_to_dict(request: ReviewRequest) -> dict:
    return {
        "schema_version": request.schema_version,
        "review_request_id": request.review_request_id,
        "input_id": request.input_id,
        "original_query": request.original_query,
        "canonical_query": request.canonical_query,
        "case_snapshot": case_snapshot_to_dict(request.case_snapshot),
        "trigger_reasons": list(request.trigger_reasons),
        "priority": request.priority,
        "review_reason": request.review_reason,
        "review_status": request.review_status,
        "config_signature": request.config_signature,
    }


def review_request_to_json(request: ReviewRequest) -> str:
    payload = {"content": review_request_to_dict(request)}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def review_request_from_dict(data: dict) -> ReviewRequest:
    data = _require_dict(data, "review request data")
    try:
        trigger_reasons = data["trigger_reasons"]
        if not isinstance(trigger_reasons, list) or any(not isinstance(x, str) for x in trigger_reasons):
            raise TypeError("trigger_reasons must be a list of strings")
        request = ReviewRequest(
            schema_version=data["schema_version"],
            review_request_id=data["review_request_id"],
            input_id=data["input_id"],
            original_query=data["original_query"],
            canonical_query=data["canonical_query"],
            case_snapshot=case_snapshot_from_dict(data["case_snapshot"]),
            trigger_reasons=trigger_reasons,
            priority=data["priority"],
            review_reason=data["review_reason"],
            review_status=data["review_status"],
            config_signature=data["config_signature"],
        )
    except (KeyError, TypeError, ValueError, ReviewSchemaError) as exc:
        raise ReviewSchemaError(f"malformed review request data: {exc}") from exc
    return request


# ---------------------------------------------------------------------------
# ReviewAction
# ---------------------------------------------------------------------------


def review_action_to_dict(action: ReviewAction) -> dict:
    return {
        "schema_version": action.schema_version,
        "review_action_id": action.review_action_id,
        "review_request_id": action.review_request_id,
        "sequence_number": action.sequence_number,
        "reviewer_id": action.reviewer_id,
        "action": action.action,
        "previous_status": action.previous_status,
        "new_status": action.new_status,
        "reviewer_comment": action.reviewer_comment,
        "selected_evidence_ids": list(action.selected_evidence_ids),
        "metadata": dict(action.metadata),
        "config_signature": action.config_signature,
    }


def review_action_to_json(action: ReviewAction) -> str:
    payload = {"content": review_action_to_dict(action)}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def review_action_from_dict(data: dict) -> ReviewAction:
    data = _require_dict(data, "review action data")
    try:
        selected_evidence_ids = data["selected_evidence_ids"]
        if not isinstance(selected_evidence_ids, list) or any(not isinstance(x, str) for x in selected_evidence_ids):
            raise TypeError("selected_evidence_ids must be a list of strings")
        metadata = data["metadata"]
        if not isinstance(metadata, dict):
            raise TypeError("metadata must be a dict")
        action = ReviewAction(
            schema_version=data["schema_version"],
            review_action_id=data["review_action_id"],
            review_request_id=data["review_request_id"],
            sequence_number=data["sequence_number"],
            reviewer_id=data["reviewer_id"],
            action=data["action"],
            previous_status=data["previous_status"],
            new_status=data["new_status"],
            reviewer_comment=data["reviewer_comment"],
            selected_evidence_ids=selected_evidence_ids,
            metadata=metadata,
            config_signature=data["config_signature"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ReviewSchemaError(f"malformed review action data: {exc}") from exc
    return action


# ---------------------------------------------------------------------------
# PresentationAuthorization
# ---------------------------------------------------------------------------


def presentation_authorization_to_dict(authorization: PresentationAuthorization) -> dict:
    return {
        "schema_version": authorization.schema_version,
        "authorized": authorization.authorized,
        "source": authorization.source,
        "safety_status": authorization.safety_status,
        "review_action_id": authorization.review_action_id,
        "explanation": authorization.explanation,
        "disclaimer": authorization.disclaimer,
    }


def presentation_authorization_to_json(authorization: PresentationAuthorization) -> str:
    payload = {"content": presentation_authorization_to_dict(authorization)}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def presentation_authorization_from_dict(data: dict) -> PresentationAuthorization:
    data = _require_dict(data, "presentation authorization data")
    try:
        authorization = PresentationAuthorization(
            schema_version=data["schema_version"],
            authorized=data["authorized"],
            source=data["source"],
            safety_status=data["safety_status"],
            review_action_id=data["review_action_id"],
            explanation=data["explanation"],
            disclaimer=data["disclaimer"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ReviewSchemaError(f"malformed presentation authorization data: {exc}") from exc
    return authorization
