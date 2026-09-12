"""
Phase 12 evidence filtering (docs/PHASE_12_JURISDICTION_FIREWALL.md
Sections N, O, P). The machine-checkable invariant this phase exists to
provide: for every evidence-shaped object, `evidence.jurisdiction` MUST be
compatible with the firewall's permitted jurisdiction, or it is
structurally excluded before it can reach downstream generation - never
merely flagged with a warning.

Operates on a plain `list` of Evidence-shaped objects (e.g.
`EvidencePack.evidence_items`) - never a second, independent evidence
representation, and never a rewrite of Phase 5-7 retrieval or Phase 8
evidence construction. See docs Section P for the exact integration point
this provides for a future retrieval-layer adapter.
"""

from __future__ import annotations

from typing import Optional

from .models import (
    EVIDENCE_JURISDICTION_VALUES,
    REASON_CORPUS_NOT_PERMITTED,
    REASON_CROSS_JURISDICTION_EVIDENCE_BLOCKED,
    REASON_JURISDICTION_METADATA_INVALID,
    EvidenceFilterResult,
    JurisdictionDecision,
)

REQUIRED_EVIDENCE_ATTRS = ("evidence_id", "jurisdiction")


def _validate_evidence_shape(evidence) -> None:
    missing = [attr for attr in REQUIRED_EVIDENCE_ATTRS if not hasattr(evidence, attr)]
    if missing:
        raise TypeError(
            f"evidence object {evidence!r} is missing required attribute(s) {missing} - "
            f"filter_evidence expects Evidence-shaped objects (e.g. evidence.models.Evidence)"
        )


def check_evidence_compatible(decision: JurisdictionDecision, evidence) -> "tuple[bool, Optional[str]]":
    """
    Single-item compatibility check. Returns `(True, None)` if `evidence`
    may be treated as allowed under `decision`; otherwise `(False, reason_code)`.
    Never mutates or relabels `evidence` - a rejected item is excluded,
    never silently repaired.
    """
    if not isinstance(decision, JurisdictionDecision):
        raise TypeError(f"check_evidence_compatible expects a JurisdictionDecision, got {type(decision).__name__}")
    _validate_evidence_shape(evidence)

    evidence_jurisdiction = evidence.jurisdiction
    if not isinstance(evidence_jurisdiction, str) or not evidence_jurisdiction.strip():
        return False, REASON_JURISDICTION_METADATA_INVALID
    if evidence_jurisdiction not in EVIDENCE_JURISDICTION_VALUES:
        return False, REASON_JURISDICTION_METADATA_INVALID

    if decision.state != "KNOWN":
        return False, REASON_CORPUS_NOT_PERMITTED

    if evidence_jurisdiction not in decision.allowed_jurisdictions:
        return False, REASON_CROSS_JURISDICTION_EVIDENCE_BLOCKED

    return True, None


def filter_evidence(decision: JurisdictionDecision, evidence_items: list) -> EvidenceFilterResult:
    """
    Deterministically partitions `evidence_items` (input order preserved
    for `allowed_evidence`) into allowed vs. blocked, applying
    `check_evidence_compatible` to every item. Guarantees NO evidence with
    an incompatible, missing, or malformed jurisdiction can ever appear in
    `allowed_evidence` - fail closed, never a warning-only pass-through.
    """
    if not isinstance(decision, JurisdictionDecision):
        raise TypeError(f"filter_evidence expects a JurisdictionDecision, got {type(decision).__name__}")
    if not isinstance(evidence_items, list):
        raise TypeError(f"filter_evidence expects a list of evidence, got {type(evidence_items).__name__}")

    allowed = []
    blocked_ids = []
    block_reasons = {}
    for evidence in evidence_items:
        _validate_evidence_shape(evidence)
        is_allowed, reason = check_evidence_compatible(decision, evidence)
        if is_allowed:
            allowed.append(evidence)
        else:
            blocked_ids.append(evidence.evidence_id)
            block_reasons[evidence.evidence_id] = reason

    return EvidenceFilterResult(
        schema_version=decision.schema_version,
        decision_id=decision.decision_id,
        total_count=len(evidence_items),
        allowed_evidence=allowed,
        blocked_evidence_ids=blocked_ids,
        block_reasons=block_reasons,
    )
