"""
Phase 14 deterministic JSON serialization
(docs/PHASE_14_MULTILINGUAL_DELIVERY.md Section AC), mirroring
src/safety/serialize.py's convention exactly. Both `MultilingualInputContext`
and `MultilingualDeliveryResult` are trusted shapes (validated request/
response objects, not untrusted provider output) - full explicit field
reconstruction with every invariant re-enforced on deserialization. No
pickle, no arbitrary/executable deserialization anywhere.
"""

from __future__ import annotations

import json

from .models import MultilingualDeliveryResult, MultilingualInputContext, MultilingualSchemaError


def _require_dict(data, what: str) -> dict:
    if not isinstance(data, dict):
        raise MultilingualSchemaError(f"malformed {what}: expected a JSON object, got {type(data).__name__}")
    return data


# ---------------------------------------------------------------------------
# MultilingualInputContext
# ---------------------------------------------------------------------------


def input_context_to_dict(context: MultilingualInputContext) -> dict:
    return {
        "schema_version": context.schema_version,
        "input_id": context.input_id,
        "original_query": context.original_query,
        "canonical_query": context.canonical_query,
        "detected_script": context.detected_script,
        "requested_language": context.requested_language,
    }


def input_context_to_json(context: MultilingualInputContext) -> str:
    payload = {"content": input_context_to_dict(context)}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def input_context_from_dict(data: dict) -> MultilingualInputContext:
    data = _require_dict(data, "multilingual input context data")
    try:
        context = MultilingualInputContext(
            schema_version=data["schema_version"],
            input_id=data["input_id"],
            original_query=data["original_query"],
            canonical_query=data["canonical_query"],
            detected_script=data["detected_script"],
            requested_language=data["requested_language"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MultilingualSchemaError(f"malformed multilingual input context data: {exc}") from exc
    return context


# ---------------------------------------------------------------------------
# MultilingualDeliveryResult
# ---------------------------------------------------------------------------


def delivery_result_to_dict(result: MultilingualDeliveryResult) -> dict:
    return {
        "schema_version": result.schema_version,
        "result_id": result.result_id,
        "input_id": result.input_id,
        "original_query": result.original_query,
        "canonical_query": result.canonical_query,
        "requested_language": result.requested_language,
        "detected_script": result.detected_script,
        "delivery_status": result.delivery_status,
        "reason_code": result.reason_code,
        "explanation": result.explanation,
        "answer_text": result.answer_text,
        "answer_language": result.answer_language,
        "translation_applied": result.translation_applied,
        "provider_name": result.provider_name,
        "cited_evidence_ids": list(result.cited_evidence_ids),
        "grounding_status": result.grounding_status,
        "safety_status": result.safety_status,
        "evidence_preservation_status": result.evidence_preservation_status,
        "synthetic": result.synthetic,
        "delivery_metadata": dict(result.delivery_metadata),
        "config_signature": result.config_signature,
    }


def delivery_result_to_json(result: MultilingualDeliveryResult) -> str:
    payload = {"content": delivery_result_to_dict(result)}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def delivery_result_from_dict(data: dict) -> MultilingualDeliveryResult:
    """Reconstructs and re-validates one MultilingualDeliveryResult. Raises MultilingualSchemaError on any malformation."""
    data = _require_dict(data, "multilingual delivery result data")
    try:
        cited_evidence_ids = data["cited_evidence_ids"]
        if not isinstance(cited_evidence_ids, list) or any(not isinstance(x, str) for x in cited_evidence_ids):
            raise TypeError("cited_evidence_ids must be a list of strings")
        delivery_metadata = data["delivery_metadata"]
        if not isinstance(delivery_metadata, dict):
            raise TypeError("delivery_metadata must be a dict")

        result = MultilingualDeliveryResult(
            schema_version=data["schema_version"],
            result_id=data["result_id"],
            input_id=data["input_id"],
            original_query=data["original_query"],
            canonical_query=data["canonical_query"],
            requested_language=data["requested_language"],
            detected_script=data["detected_script"],
            delivery_status=data["delivery_status"],
            reason_code=data["reason_code"],
            explanation=data["explanation"],
            answer_text=data["answer_text"],
            answer_language=data["answer_language"],
            translation_applied=data["translation_applied"],
            provider_name=data["provider_name"],
            cited_evidence_ids=cited_evidence_ids,
            grounding_status=data["grounding_status"],
            safety_status=data["safety_status"],
            evidence_preservation_status=data["evidence_preservation_status"],
            synthetic=data["synthetic"],
            delivery_metadata=delivery_metadata,
            config_signature=data["config_signature"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MultilingualSchemaError(f"malformed multilingual delivery result data: {exc}") from exc
    return result
