"""
Phase 11 orchestration (docs/PHASE_11_FORMULATION_CLASSIFICATION.md
Sections G, H, J). The only place in this package that ties text
extraction (rules.py) and the Phase 1 decision tree (rules.evaluate_tree)
together into one deterministic, explainable ClassificationResult.

No LLM, no network, no external retrieval, no randomness anywhere in this
module - given identical (ClassificationInput, ClassificationConfig),
classify() always returns an identical ClassificationResult.
"""

from __future__ import annotations

from typing import Optional

from .models import (
    CLASSIFICATION_CONTRACT_VERSION,
    DECISION_TREE_VERSION,
    EVIDENCE_STATE_VALUES,
    FIXED_DISCLAIMER,
    TAXONOMY_VERSION,
    ClassificationConfig,
    ClassificationInput,
    ClassificationProvenance,
    ClassificationResult,
    FormulationClassificationValues,
)
from .rules import (
    evaluate_tree,
    extract_abs_tk_relation,
    extract_ip_protection_category,
    extract_jurisdiction,
    extract_regulatory_question_type,
    extract_regulatory_track,
    extract_user_intent,
)

_DEFAULT_EVIDENCE_STATE = "NOT_YET_EVALUATED"


def _combined_text(classification_input: ClassificationInput) -> str:
    parts = [classification_input.raw_query or "", classification_input.formulation_description or ""]
    return " ".join(p for p in parts if p)


def _resolve_evidence_state(raw: Optional[str]) -> "tuple[str, Optional[str]]":
    """
    Opaque passthrough only (docs Section N) - Phase 11 never computes
    evidence_state itself. `None` or any value outside the closed
    vocabulary safely defaults to NOT_YET_EVALUATED, the only truthful
    value obtainable when no upstream evidence pipeline result was
    supplied - never guessed as SUFFICIENT_EVIDENCE.
    """
    if raw is None:
        return _DEFAULT_EVIDENCE_STATE, None
    if raw in EVIDENCE_STATE_VALUES:
        return raw, None
    return (
        _DEFAULT_EVIDENCE_STATE,
        f"evidence_state input {raw!r} was not a recognized value; treated as {_DEFAULT_EVIDENCE_STATE}",
    )


def _build_explanation(tree_result, dimension_details: dict, evidence_state_note: Optional[str]) -> str:
    parts = [f"classification_state={tree_result.classification_state} (rule {tree_result.rule_id})."]
    if tree_result.reason_codes:
        parts.append("Reason: " + "; ".join(tree_result.reason_codes) + ".")
    for name in (
        "user_intent",
        "regulatory_track",
        "ip_protection_category",
        "abs_tk_relation",
        "regulatory_question_type",
        "jurisdiction_input",
    ):
        dimension = dimension_details[name]
        parts.append(f"{name}={dimension.value} ({dimension.state}): {dimension.reason}.")
    if evidence_state_note:
        parts.append(evidence_state_note + ".")
    return " ".join(parts)


def classify(classification_input: ClassificationInput, config: Optional[ClassificationConfig] = None) -> ClassificationResult:
    """The sole Phase 11 entry point. See module docstring for the decision flow."""
    if not isinstance(classification_input, ClassificationInput):
        raise TypeError(f"classify expects a ClassificationInput, got {type(classification_input).__name__}")
    if config is None:
        config = ClassificationConfig()
    elif not isinstance(config, ClassificationConfig):
        raise TypeError(f"classify expects a ClassificationConfig or None, got {type(config).__name__}")

    combined_lower = _combined_text(classification_input).lower()

    user_intent_result = extract_user_intent(combined_lower, classification_input.raw_query)
    jurisdiction_result = extract_jurisdiction(combined_lower)
    regulatory_track_result = extract_regulatory_track(combined_lower)
    ip_protection_result = extract_ip_protection_category(combined_lower)
    abs_tk_result = extract_abs_tk_relation(combined_lower)
    regulatory_question_type_result = extract_regulatory_question_type(combined_lower)

    evidence_state_value, evidence_state_note = _resolve_evidence_state(classification_input.evidence_state)

    tree_result = evaluate_tree(
        user_intent=user_intent_result.value,
        formulation_regulatory_track=regulatory_track_result.value,
        jurisdiction=jurisdiction_result.value,
        regulatory_question_type=regulatory_question_type_result.value,
        evidence_state=evidence_state_value,
    )

    dimension_details = {
        "user_intent": user_intent_result,
        "regulatory_track": regulatory_track_result,
        "ip_protection_category": ip_protection_result,
        "abs_tk_relation": abs_tk_result,
        "regulatory_question_type": regulatory_question_type_result,
        "jurisdiction_input": jurisdiction_result,
    }

    basis = sorted({rule_id for result in dimension_details.values() for rule_id in result.matched_rule_ids} | {tree_result.rule_id})

    explanation = _build_explanation(tree_result, dimension_details, evidence_state_note)

    return ClassificationResult(
        schema_version=config.schema_version,
        input_id=classification_input.input_id,
        user_intent=user_intent_result.value,
        formulation_classification=FormulationClassificationValues(
            regulatory_track=regulatory_track_result.value,
            ip_protection_category=ip_protection_result.value,
            abs_tk_relation=abs_tk_result.value,
        ),
        regulatory_question_type=regulatory_question_type_result.value,
        jurisdiction_input=jurisdiction_result.value,
        evidence_state=evidence_state_value,
        classification_state=tree_result.classification_state,
        reason_codes=tree_result.reason_codes,
        explanation=explanation,
        requires_evidence=tree_result.requires_evidence,
        requires_escalation=tree_result.requires_escalation,
        basis=basis,
        disclaimer=FIXED_DISCLAIMER,
        provenance=ClassificationProvenance(
            taxonomy_version=TAXONOMY_VERSION,
            decision_tree_version=DECISION_TREE_VERSION,
            contract_version=CLASSIFICATION_CONTRACT_VERSION,
        ),
        dimension_details=dimension_details,
    )
