"""
Phase 12 orchestration (docs/PHASE_12_JURISDICTION_FIREWALL.md Sections
G, H, J, M). The only place in this package that ties an input signal
(Phase 11's ClassificationResult and/or an explicit override) together
with normalization and corpus-policy mapping into one deterministic,
explainable JurisdictionDecision.

Reuses Phase 11's ClassificationResult directly (read-only access to
`jurisdiction_input`) rather than reconstructing classification - no
free-text jurisdiction inference happens anywhere in this module (that
is Phase 11's job, already done by the time a ClassificationResult
exists).
"""

from __future__ import annotations

import hashlib
from typing import Optional

from classification.models import ClassificationResult

from .models import (
    REASON_EXPLICIT_JURISDICTION_ACCEPTED,
    REASON_JURISDICTION_AMBIGUOUS,
    REASON_JURISDICTION_METADATA_INVALID,
    REASON_JURISDICTION_NOT_SUPPORTED,
    REASON_JURISDICTION_UNKNOWN,
    JurisdictionDecision,
    JurisdictionFirewallConfig,
)
from .policy import blocked_evidence_jurisdictions, normalize_requested_jurisdiction, permitted_evidence_jurisdictions


def compute_decision_id(
    schema_version: str,
    input_id: str,
    requested_jurisdiction: Optional[str],
    normalized_jurisdiction: Optional[str],
    state: str,
    reason_code: str,
    allowed_jurisdictions: frozenset,
    config_signature: str,
) -> str:
    """Deterministic, backend-owned decision identity - never a random UUID, never a timestamp."""
    canonical = "|".join(
        [
            "jurisdiction-decision-v1",
            schema_version,
            input_id,
            requested_jurisdiction or "",
            normalized_jurisdiction or "",
            state,
            reason_code,
            ",".join(sorted(allowed_jurisdictions)),
            config_signature,
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_decision(
    *,
    schema_version: str,
    input_id: str,
    requested_jurisdiction: Optional[str],
    normalized_jurisdiction: Optional[str],
    state: str,
    reason_code: str,
    explanation: str,
    basis: list,
    config_signature: str,
) -> JurisdictionDecision:
    allowed = permitted_evidence_jurisdictions(normalized_jurisdiction) if state == "KNOWN" else frozenset()
    blocked = blocked_evidence_jurisdictions(allowed)
    decision_id = compute_decision_id(
        schema_version, input_id, requested_jurisdiction, normalized_jurisdiction, state, reason_code, allowed, config_signature
    )
    return JurisdictionDecision(
        schema_version=schema_version,
        decision_id=decision_id,
        input_id=input_id,
        requested_jurisdiction=requested_jurisdiction,
        normalized_jurisdiction=normalized_jurisdiction,
        state=state,
        reason_code=reason_code,
        explanation=explanation,
        allowed_jurisdictions=allowed,
        blocked_jurisdictions=blocked,
        allowed_corpora=allowed,
        blocked_corpora=blocked,
        requires_evidence=(state == "NEEDS_EVIDENCE"),
        requires_escalation=(state == "AMBIGUOUS"),
        basis=basis,
        config_signature=config_signature,
    )


def resolve_jurisdiction(
    input_id: str,
    classification_result: Optional[ClassificationResult] = None,
    explicit_jurisdiction: Optional[str] = None,
    config: Optional[JurisdictionFirewallConfig] = None,
) -> JurisdictionDecision:
    """
    The sole Phase 12 entry point. Determines a `JurisdictionDecision` from
    up to two independent signals:

    - `classification_result.jurisdiction_input` (Phase 11's own already-
      normalized value, reused directly - never re-derived from free text
      here).
    - `explicit_jurisdiction` (an optional direct override, normalized by
      this module's own deterministic, non-inferential normalization).

    If both are supplied and, after normalization, disagree -> AMBIGUOUS
    (a conflicting-signal case, never silently resolved by picking one).
    If only one is supplied, it is used. If neither is supplied (or
    neither normalizes to a recognized value), the result fails closed
    to UNKNOWN/NOT_SUPPORTED/METADATA_INVALID as appropriate - never
    guessed to INDIA merely because this is an India-focused project.
    """
    if not isinstance(input_id, str) or not input_id.strip():
        raise ValueError("input_id must be a non-empty string")
    if classification_result is not None and not isinstance(classification_result, ClassificationResult):
        raise TypeError(
            f"resolve_jurisdiction expects classification_result to be a ClassificationResult or None, "
            f"got {type(classification_result).__name__}"
        )
    if explicit_jurisdiction is not None and not isinstance(explicit_jurisdiction, str):
        # A wrong TYPE (not even a string) is metadata-invalid input, not a
        # programmer error - handled as a fail-closed decision, never raised,
        # since this is exactly the kind of untrusted input the firewall
        # must treat defensively (docs Section T).
        return _build_decision(
            schema_version=(config or JurisdictionFirewallConfig()).schema_version,
            input_id=input_id,
            requested_jurisdiction=None,
            normalized_jurisdiction=None,
            state="UNKNOWN",
            reason_code=REASON_JURISDICTION_METADATA_INVALID,
            explanation=f"explicit_jurisdiction was not a string (got {type(explicit_jurisdiction).__name__}); treated as invalid metadata, never guessed.",
            basis=["JURISDICTION-METADATA-TYPE-CHECK"],
            config_signature=(config or JurisdictionFirewallConfig()).signature,
        )
    if config is None:
        config = JurisdictionFirewallConfig()
    elif not isinstance(config, JurisdictionFirewallConfig):
        raise TypeError(f"resolve_jurisdiction expects config to be a JurisdictionFirewallConfig or None, got {type(config).__name__}")

    schema_version = config.schema_version
    config_signature = config.signature

    classification_value = classification_result.jurisdiction_input if classification_result is not None else None
    explicit_normalized = normalize_requested_jurisdiction(explicit_jurisdiction)
    classification_normalized = normalize_requested_jurisdiction(classification_value)

    # "UNSPECIFIED" is a genuine member of REQUEST_JURISDICTION_VALUES
    # (it round-trips through normalize_requested_jurisdiction successfully)
    # but it means "no real signal" - it must never be treated as a
    # RESOLVED value that reaches state=KNOWN. `_is_resolved` is the
    # single place this distinction is enforced.
    def _is_resolved(value):
        return value is not None and value != "UNSPECIFIED"

    basis = []
    if classification_result is not None:
        basis.append(f"classification_result.input_id={classification_result.input_id}")
        basis.append(f"classification_result.jurisdiction_input={classification_value}")
    if explicit_jurisdiction is not None:
        basis.append(f"explicit_jurisdiction={explicit_jurisdiction!r}")

    requested_raw_for_record = explicit_jurisdiction if explicit_jurisdiction is not None else classification_value

    # Both signals supplied and both resolve to a real value.
    if explicit_jurisdiction is not None and classification_result is not None:
        if _is_resolved(explicit_normalized) and _is_resolved(classification_normalized):
            if explicit_normalized != classification_normalized:
                explanation = (
                    f"Conflicting jurisdiction signals: explicit_jurisdiction normalized to {explicit_normalized!r} "
                    f"but classification_result.jurisdiction_input normalized to {classification_normalized!r}; "
                    f"no deterministic tiebreak is applied."
                )
                return _build_decision(
                    schema_version=schema_version, input_id=input_id, requested_jurisdiction=requested_raw_for_record,
                    normalized_jurisdiction=None, state="AMBIGUOUS", reason_code=REASON_JURISDICTION_AMBIGUOUS,
                    explanation=explanation, basis=basis, config_signature=config_signature,
                )
            # Agree - fall through using the shared normalized value.
            normalized = explicit_normalized
        else:
            # At least one failed to resolve - the other (if resolved)
            # is used; if NEITHER resolved, this is handled below.
            normalized = explicit_normalized if _is_resolved(explicit_normalized) else classification_normalized
    elif explicit_jurisdiction is not None:
        normalized = explicit_normalized
    elif classification_result is not None:
        normalized = classification_normalized
    else:
        normalized = None

    if _is_resolved(normalized):
        explanation = f"Jurisdiction input normalized to {normalized!r}; corpus access permitted accordingly."
        return _build_decision(
            schema_version=schema_version, input_id=input_id, requested_jurisdiction=requested_raw_for_record,
            normalized_jurisdiction=normalized, state="KNOWN", reason_code=REASON_EXPLICIT_JURISDICTION_ACCEPTED,
            explanation=explanation, basis=basis, config_signature=config_signature,
        )

    # Nothing resolved. Distinguish "nothing was supplied at all" /
    # "UNSPECIFIED was supplied" (JURISDICTION_UNKNOWN) from "something WAS
    # supplied but it is not a value this vocabulary supports"
    # (JURISDICTION_NOT_SUPPORTED) - never conflated, per explicit
    # instruction that every reason code be independently meaningful.
    supplied_something_unsupported = (
        (explicit_jurisdiction is not None and explicit_jurisdiction.strip() and explicit_jurisdiction.strip().upper() != "UNSPECIFIED")
        or (classification_value is not None and classification_value.strip() and classification_value.strip().upper() != "UNSPECIFIED")
    )
    if supplied_something_unsupported:
        explanation = (
            f"A jurisdiction value was supplied (requested_jurisdiction={requested_raw_for_record!r}) but it is not "
            f"a member of this system's supported vocabulary {sorted({'INDIA', 'INTERNATIONAL', 'BOTH', 'UNSPECIFIED'})}; "
            f"country-level routing beyond this vocabulary is not supported (deferred) - no corpus is permitted."
        )
        return _build_decision(
            schema_version=schema_version, input_id=input_id, requested_jurisdiction=requested_raw_for_record,
            normalized_jurisdiction=None, state="UNKNOWN", reason_code=REASON_JURISDICTION_NOT_SUPPORTED,
            explanation=explanation, basis=basis, config_signature=config_signature,
        )

    explanation = "No usable jurisdiction signal was supplied (missing or UNSPECIFIED); no corpus is permitted until jurisdiction is provided."
    return _build_decision(
        schema_version=schema_version, input_id=input_id, requested_jurisdiction=requested_raw_for_record,
        normalized_jurisdiction=None, state="UNKNOWN", reason_code=REASON_JURISDICTION_UNKNOWN,
        explanation=explanation, basis=basis or ["NO_SIGNAL_SUPPLIED"], config_signature=config_signature,
    )
