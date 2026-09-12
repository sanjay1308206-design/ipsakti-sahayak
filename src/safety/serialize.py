"""
Phase 13 deterministic JSON serialization
(docs/PHASE_13_CONFIDENCE_SAFETY_ABSTENTION.md Section Z), mirroring
src/jurisdiction/serialize.py's convention exactly. `SafetyDecision` is a
trusted shape (this system's own deterministic output) - full explicit
field reconstruction with every invariant re-enforced on deserialization.
No pickle, no arbitrary/executable deserialization anywhere.
"""

from __future__ import annotations

import json

from .models import SafetyDecision, SafetySchemaError


def _require_dict(data, what: str) -> dict:
    if not isinstance(data, dict):
        raise SafetySchemaError(f"malformed {what}: expected a JSON object, got {type(data).__name__}")
    return data


def safety_decision_to_dict(decision: SafetyDecision) -> dict:
    return {
        "schema_version": decision.schema_version,
        "decision_id": decision.decision_id,
        "input_id": decision.input_id,
        "safety_status": decision.safety_status,
        "reason_code": decision.reason_code,
        "explanation": decision.explanation,
        "engineering_signal_band": decision.engineering_signal_band,
        "hard_gate_results": list(decision.hard_gate_results),
        "input_status_summary": dict(decision.input_status_summary),
        "abstained": decision.abstained,
        "escalation_required": decision.escalation_required,
        "synthetic": decision.synthetic,
        "config_signature": decision.config_signature,
    }


def safety_decision_to_json(decision: SafetyDecision) -> str:
    payload = {"content": safety_decision_to_dict(decision)}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def safety_decision_from_dict(data: dict) -> SafetyDecision:
    """Reconstructs and re-validates one SafetyDecision. Raises SafetySchemaError on any malformation."""
    data = _require_dict(data, "safety decision data")
    try:
        hard_gate_results = data["hard_gate_results"]
        if not isinstance(hard_gate_results, list) or any(not isinstance(x, str) for x in hard_gate_results):
            raise TypeError("hard_gate_results must be a list of strings")
        input_status_summary = data["input_status_summary"]
        if not isinstance(input_status_summary, dict):
            raise TypeError("input_status_summary must be a dict")

        decision = SafetyDecision(
            schema_version=data["schema_version"],
            decision_id=data["decision_id"],
            input_id=data["input_id"],
            safety_status=data["safety_status"],
            reason_code=data["reason_code"],
            explanation=data["explanation"],
            engineering_signal_band=data["engineering_signal_band"],
            hard_gate_results=hard_gate_results,
            input_status_summary=input_status_summary,
            abstained=data["abstained"],
            escalation_required=data["escalation_required"],
            synthetic=data["synthetic"],
            config_signature=data["config_signature"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SafetySchemaError(f"malformed safety decision data: {exc}") from exc
    return decision
