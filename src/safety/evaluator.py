"""
Phase 13 orchestration (docs/PHASE_13_CONFIDENCE_SAFETY_ABSTENTION.md
Sections E, H, I, N, O, P, Q). The only place in this package that ties
Phase 11's ClassificationResult, Phase 12's JurisdictionDecision, and
Phase 10's GroundedResponse together into one deterministic, explainable
SafetyDecision.

Nine ordered, deterministic, first-match-wins gates (G1..G9), mirroring
the exact "ordered rule list" convention already established by Phase
1/9/11/12's own decision trees. Hard gates ALWAYS run to completion
before the optional engineering signal is even computed (docs
"HARD-GATE ORDER") - there is no code path that computes a reassuring
signal and then discovers a hard failure afterward.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from classification.models import ClassificationResult
from generation.models import GroundedResponse
from jurisdiction.models import JurisdictionDecision

from .models import (
    REASON_CLASSIFICATION_AMBIGUOUS,
    REASON_CLASSIFICATION_UNRESOLVED,
    REASON_GENERATION_ABSTAINED,
    REASON_GENERATION_FAILED,
    REASON_JURISDICTION_AMBIGUOUS,
    REASON_JURISDICTION_UNRESOLVED,
    REASON_MISSING_GROUNDED_RESPONSE,
    REASON_NO_VALID_CITATIONS,
    REASON_SAFE_GROUNDED_RESPONSE,
    SafetyDecision,
    SafetyPolicyConfig,
)
from .policy import compute_engineering_signal_band


def compute_decision_id(
    schema_version: str,
    input_id: str,
    safety_status: str,
    reason_code: str,
    engineering_signal_band: str,
    input_status_summary: dict,
    config_signature: str,
) -> str:
    """Deterministic, backend-owned decision identity - never a random UUID, never a timestamp."""
    summary_part = ",".join(f"{k}={input_status_summary[k]}" for k in sorted(input_status_summary))
    canonical = "|".join(
        [
            "safety-decision-v1",
            schema_version,
            input_id,
            safety_status,
            reason_code,
            engineering_signal_band,
            summary_part,
            config_signature,
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_status_summary(
    classification_result: Optional[ClassificationResult],
    jurisdiction_decision: Optional[JurisdictionDecision],
    grounded_response: Optional[GroundedResponse],
) -> dict:
    """
    Purely informational (docs Section G) - a flat record of what was
    observed, never itself consulted to make the decision (the gates in
    `evaluate_safety` read the real objects directly). `None` is used
    honestly wherever a fact is genuinely unavailable, never defaulted to
    a value implying certainty.
    """
    summary = {
        "classification_state": classification_result.classification_state if classification_result is not None else None,
        "jurisdiction_state": jurisdiction_decision.state if jurisdiction_decision is not None else None,
        "grounding_status": grounded_response.grounding_status if grounded_response is not None else None,
        "cited_evidence_count": len(grounded_response.cited_evidence_ids) if grounded_response is not None else None,
        "unique_valid_evidence_id_count": (
            grounded_response.citation_validation_summary.unique_valid_evidence_id_count
            if grounded_response is not None
            else None
        ),
        "citation_integrity_validation_rate": (
            grounded_response.citation_validation_summary.citation_integrity_validation_rate
            if grounded_response is not None
            else None
        ),
    }
    return summary


def _build_decision(
    *,
    schema_version: str,
    input_id: str,
    safety_status: str,
    reason_code: str,
    explanation: str,
    engineering_signal_band: str,
    hard_gate_results: list,
    input_status_summary: dict,
    synthetic: Optional[bool],
    config_signature: str,
) -> SafetyDecision:
    decision_id = compute_decision_id(
        schema_version, input_id, safety_status, reason_code, engineering_signal_band, input_status_summary, config_signature
    )
    return SafetyDecision(
        schema_version=schema_version,
        decision_id=decision_id,
        input_id=input_id,
        safety_status=safety_status,
        reason_code=reason_code,
        explanation=explanation,
        engineering_signal_band=engineering_signal_band,
        hard_gate_results=hard_gate_results,
        input_status_summary=input_status_summary,
        abstained=(safety_status == "ABSTAIN"),
        escalation_required=(safety_status == "ESCALATE"),
        synthetic=synthetic,
        config_signature=config_signature,
    )


def evaluate_safety(
    input_id: str,
    classification_result: Optional[ClassificationResult] = None,
    jurisdiction_decision: Optional[JurisdictionDecision] = None,
    grounded_response: Optional[GroundedResponse] = None,
    config: Optional[SafetyPolicyConfig] = None,
) -> SafetyDecision:
    """The sole Phase 13 entry point. See module docstring for the nine-gate decision flow."""
    if not isinstance(input_id, str) or not input_id.strip():
        raise ValueError("input_id must be a non-empty string")
    if classification_result is not None and not isinstance(classification_result, ClassificationResult):
        raise TypeError(
            f"evaluate_safety expects classification_result to be a ClassificationResult or None, "
            f"got {type(classification_result).__name__}"
        )
    if jurisdiction_decision is not None and not isinstance(jurisdiction_decision, JurisdictionDecision):
        raise TypeError(
            f"evaluate_safety expects jurisdiction_decision to be a JurisdictionDecision or None, "
            f"got {type(jurisdiction_decision).__name__}"
        )
    if grounded_response is not None and not isinstance(grounded_response, GroundedResponse):
        raise TypeError(
            f"evaluate_safety expects grounded_response to be a GroundedResponse or None, got {type(grounded_response).__name__}"
        )
    if config is None:
        config = SafetyPolicyConfig()
    elif not isinstance(config, SafetyPolicyConfig):
        raise TypeError(f"evaluate_safety expects config to be a SafetyPolicyConfig or None, got {type(config).__name__}")

    schema_version = config.schema_version
    config_signature = config.signature
    status_summary = _build_status_summary(classification_result, jurisdiction_decision, grounded_response)
    synthetic = grounded_response.synthetic if grounded_response is not None else None

    def result(status, reason, explanation, gate_log):
        return _build_decision(
            schema_version=schema_version, input_id=input_id, safety_status=status, reason_code=reason,
            explanation=explanation, engineering_signal_band="NOT_APPLICABLE", hard_gate_results=gate_log,
            input_status_summary=status_summary, synthetic=synthetic, config_signature=config_signature,
        )

    gate_log = []

    # G1 - CLASSIFICATION_AMBIGUOUS (Phase 11's own requires_escalation flag, reused verbatim)
    if classification_result is not None and classification_result.requires_escalation:
        gate_log.append("G1:FIRED")
        return result(
            "ESCALATE", REASON_CLASSIFICATION_AMBIGUOUS,
            "Escalation required: Phase 11 classification is AMBIGUOUS (conflicting signals, no deterministic tiebreak).",
            gate_log,
        )
    gate_log.append("G1:PASS")

    # G2 - CLASSIFICATION_UNRESOLVED (missing entirely, or Phase 11's own UNKNOWN state)
    if classification_result is None or classification_result.classification_state == "UNKNOWN":
        gate_log.append("G2:FIRED")
        return result(
            "ABSTAIN", REASON_CLASSIFICATION_UNRESOLVED,
            "Abstaining: no classification result was supplied, or Phase 11 classification is UNKNOWN.",
            gate_log,
        )
    gate_log.append("G2:PASS")

    # G3 - JURISDICTION_AMBIGUOUS (Phase 12's own requires_escalation flag, reused verbatim)
    if jurisdiction_decision is not None and jurisdiction_decision.requires_escalation:
        gate_log.append("G3:FIRED")
        return result(
            "ESCALATE", REASON_JURISDICTION_AMBIGUOUS,
            "Escalation required: Phase 12 jurisdiction resolution is AMBIGUOUS (conflicting signals, no deterministic tiebreak).",
            gate_log,
        )
    gate_log.append("G3:PASS")

    # G4 - JURISDICTION_UNRESOLVED (missing entirely, or Phase 12's own UNKNOWN state)
    if jurisdiction_decision is None or jurisdiction_decision.state == "UNKNOWN":
        gate_log.append("G4:FIRED")
        return result(
            "ABSTAIN", REASON_JURISDICTION_UNRESOLVED,
            "Abstaining: no jurisdiction decision was supplied, or Phase 12 jurisdiction is UNKNOWN - never presenting "
            "under an unresolved jurisdiction, never guessed.",
            gate_log,
        )
    gate_log.append("G4:PASS")

    # G5 - MISSING_GROUNDED_RESPONSE
    if grounded_response is None:
        gate_log.append("G5:FIRED")
        return result("ABSTAIN", REASON_MISSING_GROUNDED_RESPONSE, "Abstaining: no grounded response was supplied.", gate_log)
    gate_log.append("G5:PASS")

    # G6 - GENERATION_FAILED (Phase 10's own status, reused verbatim - never becomes SAFE_TO_PRESENT)
    if grounded_response.grounding_status == "GENERATION_FAILED":
        gate_log.append("G6:FIRED")
        return result(
            "ABSTAIN", REASON_GENERATION_FAILED,
            f"Abstaining: Phase 10 generation failed ({grounded_response.failure_reason}).",
            gate_log,
        )
    gate_log.append("G6:PASS")

    # G7 - GENERATION_ABSTAINED (Phase 10's own status, reused verbatim - never becomes SAFE_TO_PRESENT)
    if grounded_response.grounding_status == "ABSTAINED":
        gate_log.append("G7:FIRED")
        return result(
            "ABSTAIN", REASON_GENERATION_ABSTAINED,
            f"Abstaining: Phase 10 already abstained ({grounded_response.abstention_reason}).",
            gate_log,
        )
    gate_log.append("G7:PASS")

    # G8 - NO_VALID_CITATIONS (Phase 13's OWN presentation-safety policy - may be
    # stricter than Phase 10's own generation-time require_citations config)
    if config.require_at_least_one_valid_citation and not grounded_response.cited_evidence_ids:
        gate_log.append("G8:FIRED")
        return result(
            "ABSTAIN", REASON_NO_VALID_CITATIONS,
            "Abstaining: the grounded response carries zero validated citations, and this policy requires at least one.",
            gate_log,
        )
    gate_log.append("G8:PASS")

    # G9 - DEFAULT SAFE. Only now, after every hard gate has passed, is the
    # optional engineering signal computed - it can never override a gate
    # that already fired above.
    gate_log.append("G9:FIRED")
    band = compute_engineering_signal_band(grounded_response.citation_validation_summary, config)
    return _build_decision(
        schema_version=schema_version, input_id=input_id, safety_status="SAFE_TO_PRESENT",
        reason_code=REASON_SAFE_GROUNDED_RESPONSE,
        explanation=(
            f"Safe to present: classification and jurisdiction are resolved, generation is grounded, and "
            f"{grounded_response.citation_validation_summary.unique_valid_evidence_id_count} distinct citation(s) "
            f"validated (engineering_signal_band={band}, never a legal-correctness probability)."
        ),
        engineering_signal_band=band, hard_gate_results=gate_log, input_status_summary=status_summary,
        synthetic=synthetic, config_signature=config_signature,
    )
