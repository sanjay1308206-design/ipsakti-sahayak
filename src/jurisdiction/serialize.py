"""
Phase 12 deterministic JSON serialization
(docs/PHASE_12_JURISDICTION_FIREWALL.md Section Y), mirroring
src/classification/serialize.py's convention exactly. `JurisdictionDecision`
is a trusted shape (this system's own deterministic output) - full
explicit field reconstruction with every invariant re-enforced on
deserialization. No pickle, no arbitrary/executable deserialization
anywhere. `frozenset` fields are serialized as sorted lists for
deterministic, stable JSON output.
"""

from __future__ import annotations

import json

from .models import JurisdictionDecision, JurisdictionSchemaError


def _require_dict(data, what: str) -> dict:
    if not isinstance(data, dict):
        raise JurisdictionSchemaError(f"malformed {what}: expected a JSON object, got {type(data).__name__}")
    return data


def jurisdiction_decision_to_dict(decision: JurisdictionDecision) -> dict:
    return {
        "schema_version": decision.schema_version,
        "decision_id": decision.decision_id,
        "input_id": decision.input_id,
        "requested_jurisdiction": decision.requested_jurisdiction,
        "normalized_jurisdiction": decision.normalized_jurisdiction,
        "state": decision.state,
        "reason_code": decision.reason_code,
        "explanation": decision.explanation,
        "allowed_jurisdictions": sorted(decision.allowed_jurisdictions),
        "blocked_jurisdictions": sorted(decision.blocked_jurisdictions),
        "allowed_corpora": sorted(decision.allowed_corpora),
        "blocked_corpora": sorted(decision.blocked_corpora),
        "requires_evidence": decision.requires_evidence,
        "requires_escalation": decision.requires_escalation,
        "basis": list(decision.basis),
        "config_signature": decision.config_signature,
    }


def jurisdiction_decision_to_json(decision: JurisdictionDecision) -> str:
    payload = {"content": jurisdiction_decision_to_dict(decision)}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _require_frozenset_source(data: dict, key: str) -> frozenset:
    value = data[key]
    # A bare string would silently become a frozenset of its individual
    # characters (e.g. frozenset("INDIA") -> {'I','N','D','A'}) instead of
    # raising - explicitly rejected rather than risking that silent
    # misinterpretation.
    if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
        raise TypeError(f"{key} must be a list of strings, got {type(value).__name__}")
    return frozenset(value)


def jurisdiction_decision_from_dict(data: dict) -> JurisdictionDecision:
    """Reconstructs and re-validates one JurisdictionDecision. Raises JurisdictionSchemaError on any malformation."""
    data = _require_dict(data, "jurisdiction decision data")
    try:
        decision = JurisdictionDecision(
            schema_version=data["schema_version"],
            decision_id=data["decision_id"],
            input_id=data["input_id"],
            requested_jurisdiction=data["requested_jurisdiction"],
            normalized_jurisdiction=data["normalized_jurisdiction"],
            state=data["state"],
            reason_code=data["reason_code"],
            explanation=data["explanation"],
            allowed_jurisdictions=_require_frozenset_source(data, "allowed_jurisdictions"),
            blocked_jurisdictions=_require_frozenset_source(data, "blocked_jurisdictions"),
            allowed_corpora=_require_frozenset_source(data, "allowed_corpora"),
            blocked_corpora=_require_frozenset_source(data, "blocked_corpora"),
            requires_evidence=data["requires_evidence"],
            requires_escalation=data["requires_escalation"],
            basis=data["basis"],
            config_signature=data["config_signature"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise JurisdictionSchemaError(f"malformed jurisdiction decision data: {exc}") from exc
    return decision


