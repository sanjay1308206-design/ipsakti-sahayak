"""
Phase 15 defensive validation helpers (docs/PHASE_15_HUMAN_IN_THE_LOOP.md
Sections I, J, K). Mirrors Phase 9's `CitationReference`/`validator.py`
split: reviewer-supplied input is deliberately permissive to CONSTRUCT
(untrusted), but every check that decides whether it may actually be
USED is deterministic, explicit, and fails closed here - never inside a
frozen dataclass's own `__post_init__` (which has no access to a real
EvidencePack to check against).
"""

from __future__ import annotations

from evidence.models import EvidencePack

from .models import ACTION_TYPES, FakeEvidenceReferenceError, ReviewerIdentityError


def validate_reviewer_id(reviewer_id) -> None:
    """
    No real authentication/authorization is implemented in this phase
    (docs Section I, `[DEFERRED]`) - this only enforces that SOME
    non-empty string identity is recorded, distinguishing
    reviewer-generated data from system-generated data. Synthetic
    reviewer IDs are explicitly acceptable for tests.
    """
    if not isinstance(reviewer_id, str) or not reviewer_id.strip():
        raise ReviewerIdentityError(f"reviewer_id must be a non-empty string, got {reviewer_id!r}")


def validate_action_type(action) -> None:
    if action not in ACTION_TYPES:
        raise ValueError(f"action must be one of {sorted(ACTION_TYPES)}, got {action!r}")


def validate_selected_evidence_ids(selected_evidence_ids, evidence_pack) -> None:
    """
    A reviewer may only ever point at evidence that ALREADY exists in a
    real, trusted `EvidencePack` (docs Section K - "the reviewer cannot
    manufacture a citation"). No fuzzy/partial matching, no case-folding -
    exact membership only, mirroring Phase 9's own exact-match discipline.
    Fails closed: selecting anything without a real pack to check against
    is rejected outright, never silently accepted as "trusted anyway."
    """
    if not isinstance(selected_evidence_ids, list) or any(not isinstance(x, str) for x in selected_evidence_ids):
        raise ValueError("selected_evidence_ids must be a list of strings")
    if not selected_evidence_ids:
        return
    if evidence_pack is None:
        raise FakeEvidenceReferenceError(
            "selected_evidence_ids were supplied but no EvidencePack was provided to validate them against"
        )
    if not isinstance(evidence_pack, EvidencePack):
        raise TypeError(f"evidence_pack must be an EvidencePack or None, got {type(evidence_pack).__name__}")

    real_ids = {item.evidence_id for item in evidence_pack.evidence_items}
    fake = [eid for eid in selected_evidence_ids if eid not in real_ids]
    if fake:
        raise FakeEvidenceReferenceError(
            f"selected_evidence_ids contains id(s) not present in the given EvidencePack: {fake}"
        )
