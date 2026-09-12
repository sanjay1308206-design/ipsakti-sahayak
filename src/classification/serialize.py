"""
Phase 11 deterministic JSON serialization
(docs/PHASE_11_FORMULATION_CLASSIFICATION.md Section S), mirroring
src/citation/serialize.py's / src/generation/serialize.py's convention.

Both ClassificationInput and ClassificationResult are TRUSTED shapes here
(the input is a validated API request object, not untrusted LLM output
like Phase 9/10's CitationReference) - both get full explicit field
reconstruction with every invariant re-enforced on deserialization. No
pickle, no arbitrary/executable deserialization anywhere.
"""

from __future__ import annotations

import dataclasses
import json

from .models import (
    ClassificationInput,
    ClassificationProvenance,
    ClassificationResult,
    ClassificationSchemaError,
    DimensionResult,
    FormulationClassificationValues,
)


def _require_dict(data, what: str) -> dict:
    if not isinstance(data, dict):
        raise ClassificationSchemaError(f"malformed {what}: expected a JSON object, got {type(data).__name__}")
    return data


# ---------------------------------------------------------------------------
# ClassificationInput
# ---------------------------------------------------------------------------


def classification_input_to_dict(classification_input: ClassificationInput) -> dict:
    return dataclasses.asdict(classification_input)


def classification_input_to_json(classification_input: ClassificationInput) -> str:
    payload = {"content": classification_input_to_dict(classification_input)}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def classification_input_from_dict(data: dict) -> ClassificationInput:
    data = _require_dict(data, "classification input data")
    try:
        return ClassificationInput(
            input_id=data["input_id"],
            raw_query=data["raw_query"],
            formulation_description=data["formulation_description"],
            evidence_state=data["evidence_state"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ClassificationSchemaError(f"malformed classification input data: {exc}") from exc


# ---------------------------------------------------------------------------
# ClassificationResult
# ---------------------------------------------------------------------------


def classification_result_to_dict(result: ClassificationResult) -> dict:
    return dataclasses.asdict(result)


def classification_result_to_json(result: ClassificationResult) -> str:
    payload = {"content": classification_result_to_dict(result)}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _dimension_result_from_dict(data: dict) -> DimensionResult:
    data = _require_dict(data, "dimension result data")
    return DimensionResult(
        dimension=data["dimension"],
        value=data["value"],
        state=data["state"],
        matched_rule_ids=data["matched_rule_ids"],
        reason=data["reason"],
    )


def classification_result_from_dict(data: dict) -> ClassificationResult:
    """Reconstructs and re-validates one ClassificationResult. Raises ClassificationSchemaError on any malformation."""
    data = _require_dict(data, "classification result data")
    try:
        formulation_data = _require_dict(data["formulation_classification"], "formulation_classification data")
        formulation = FormulationClassificationValues(
            regulatory_track=formulation_data["regulatory_track"],
            ip_protection_category=formulation_data["ip_protection_category"],
            abs_tk_relation=formulation_data["abs_tk_relation"],
        )

        provenance_data = _require_dict(data["provenance"], "provenance data")
        provenance = ClassificationProvenance(
            taxonomy_version=provenance_data["taxonomy_version"],
            decision_tree_version=provenance_data["decision_tree_version"],
            contract_version=provenance_data["contract_version"],
        )

        dimension_details_data = _require_dict(data["dimension_details"], "dimension_details data")
        dimension_details = {key: _dimension_result_from_dict(value) for key, value in dimension_details_data.items()}

        result = ClassificationResult(
            schema_version=data["schema_version"],
            input_id=data["input_id"],
            user_intent=data["user_intent"],
            formulation_classification=formulation,
            regulatory_question_type=data["regulatory_question_type"],
            jurisdiction_input=data["jurisdiction_input"],
            evidence_state=data["evidence_state"],
            classification_state=data["classification_state"],
            reason_codes=data["reason_codes"],
            explanation=data["explanation"],
            requires_evidence=data["requires_evidence"],
            requires_escalation=data["requires_escalation"],
            basis=data["basis"],
            disclaimer=data["disclaimer"],
            provenance=provenance,
            dimension_details=dimension_details,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ClassificationSchemaError(f"malformed classification result data: {exc}") from exc
    return result
