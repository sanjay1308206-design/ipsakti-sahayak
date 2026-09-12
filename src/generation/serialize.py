"""
Phase 10 deterministic JSON serialization
(docs/PHASE_10_GROUNDED_GENERATION.md Section R), mirroring
src/citation/serialize.py's convention exactly.

`GroundedResponse` and `GenerationOutput` are both TRUSTED shapes (the
former is this system's own deterministic output; the latter, once
constructed, has already passed its own `__post_init__` invariants) - so
both get full explicit field reconstruction with every invariant
re-enforced, identical to Phase 8/9's own trusted-output serialization.
No pickle, no arbitrary/executable deserialization anywhere.
"""

from __future__ import annotations

import dataclasses
import json

from citation.serialize import citation_coverage_metrics_from_dict

from .models import GenerationOutput, GenerationSchemaError, GroundedResponse


def _require_dict(data, what: str) -> dict:
    if not isinstance(data, dict):
        raise GenerationSchemaError(f"malformed {what}: expected a JSON object, got {type(data).__name__}")
    return data


def generation_output_to_dict(output: GenerationOutput) -> dict:
    return dataclasses.asdict(output)


def generation_output_to_json(output: GenerationOutput) -> str:
    payload = {"content": generation_output_to_dict(output)}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def generation_output_from_dict(data: dict) -> GenerationOutput:
    data = _require_dict(data, "generation output data")
    try:
        output = GenerationOutput(
            raw_text=data["raw_text"],
            provider_name=data["provider_name"],
            model_identifier=data["model_identifier"],
            success=data["success"],
            failure_reason=data["failure_reason"],
            metadata=data["metadata"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise GenerationSchemaError(f"malformed generation output data: {exc}") from exc
    return output


def grounded_response_to_dict(response: GroundedResponse) -> dict:
    return dataclasses.asdict(response)


def grounded_response_to_json(response: GroundedResponse) -> str:
    payload = {"content": grounded_response_to_dict(response)}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def grounded_response_from_dict(data: dict) -> GroundedResponse:
    """Reconstructs and re-validates one GroundedResponse. Raises GenerationSchemaError on any malformation."""
    data = _require_dict(data, "grounded response data")
    try:
        summary_data = _require_dict(data["citation_validation_summary"], "citation_validation_summary data")
        try:
            summary = citation_coverage_metrics_from_dict(summary_data)
        except Exception as exc:  # the nested CitationSchemaError is itself a ValueError subclass
            raise GenerationSchemaError(f"malformed citation_validation_summary: {exc}") from exc

        response = GroundedResponse(
            schema_version=data["schema_version"],
            response_id=data["response_id"],
            query=data["query"],
            canonical_query=data["canonical_query"],
            answer_text=data["answer_text"],
            cited_evidence_ids=data["cited_evidence_ids"],
            citation_validation_summary=summary,
            grounding_status=data["grounding_status"],
            abstained=data["abstained"],
            abstention_reason=data["abstention_reason"],
            failure_reason=data["failure_reason"],
            provider_name=data["provider_name"],
            model_identifier=data["model_identifier"],
            generation_metadata=data["generation_metadata"],
            synthetic=data["synthetic"],
            evidence_pack_id=data["evidence_pack_id"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise GenerationSchemaError(f"malformed grounded response data: {exc}") from exc
    return response
