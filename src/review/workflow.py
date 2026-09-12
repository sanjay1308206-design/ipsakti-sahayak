"""
Phase 15 review-workflow orchestration (docs/PHASE_15_HUMAN_IN_THE_LOOP.md
Sections G, H, R). `ReviewRequest` objects are frozen and never mutated -
"current status" is always a DERIVED function of the ordered `ReviewAction`
history (event-sourced, append-only), never a field flipped in place on
the request itself. `apply_action` is the ONLY place a new `ReviewAction`
is constructed; it never touches any upstream Phase 8-14 object.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from evidence.models import EvidencePack

from . import validation
from .models import (
    ACTION_TRANSITIONS,
    TERMINAL_REVIEW_STATUSES,
    HumanReviewConfig,
    InvalidReviewTransitionError,
    ReviewAction,
    ReviewRequest,
)


def compute_review_action_id(
    schema_version: str,
    review_request_id: str,
    sequence_number: int,
    reviewer_id: str,
    action: str,
    previous_status: str,
    new_status: str,
    reviewer_comment: Optional[str],
    selected_evidence_ids: list,
    config_signature: str,
) -> str:
    """Deterministic, backend-owned review-action identity - never a random UUID, never a timestamp."""
    canonical = "|".join(
        [
            "human-review-action-v1",
            schema_version,
            review_request_id,
            str(sequence_number),
            reviewer_id,
            action,
            previous_status,
            new_status,
            reviewer_comment or "",
            ",".join(selected_evidence_ids),
            config_signature,
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_current_status(review_request: ReviewRequest, actions: list) -> str:
    """
    Folds an ordered `ReviewAction` history into the request's current
    status - `review_request.review_status` (always `PENDING`) if no
    actions have been recorded yet, otherwise the `new_status` of the
    action with the highest `sequence_number`. Validates the entire chain:
    every action must reference `review_request.review_request_id`,
    `sequence_number`s must be exactly `0, 1, 2, ...` with no gaps or
    repeats, and each action's own `previous_status` must equal the
    status computed from the actions before it - a forged, reordered, or
    spliced-together history is rejected explicitly, never silently
    accepted.
    """
    if not isinstance(review_request, ReviewRequest):
        raise TypeError(f"review_request must be a ReviewRequest, got {type(review_request).__name__}")
    if not isinstance(actions, list) or any(not isinstance(a, ReviewAction) for a in actions):
        raise TypeError("actions must be a list of ReviewAction")

    if not actions:
        return review_request.review_status

    ordered = sorted(actions, key=lambda a: a.sequence_number)
    expected_status = review_request.review_status
    for index, action in enumerate(ordered):
        if action.review_request_id != review_request.review_request_id:
            raise ValueError(
                f"action {action.review_action_id!r} references review_request_id {action.review_request_id!r}, "
                f"expected {review_request.review_request_id!r}"
            )
        if action.sequence_number != index:
            raise ValueError(f"actions must have sequence_number 0..N-1 with no gaps or duplicates, got {[a.sequence_number for a in ordered]}")
        if action.previous_status != expected_status:
            raise ValueError(
                f"action at sequence_number {index} has previous_status {action.previous_status!r}, "
                f"but the status computed from the prior history is {expected_status!r}"
            )
        expected_status = action.new_status

    return expected_status


def apply_action(
    review_request: ReviewRequest,
    actions_so_far: list,
    *,
    reviewer_id: str,
    action: str,
    reviewer_comment: Optional[str] = None,
    selected_evidence_ids: Optional[list] = None,
    evidence_pack: Optional[EvidencePack] = None,
    config: Optional[HumanReviewConfig] = None,
) -> ReviewAction:
    """
    The sole place a new `ReviewAction` is created. Validates, in order:
    reviewer identity (docs Section I); the current status (folded from
    `actions_so_far`, never a status the caller merely asserts); that the
    requested `action` is a valid transition from that status (docs
    Section G - invalid transitions fail explicitly, `InvalidReviewTransitionError`);
    and that any `selected_evidence_ids` already exist in `evidence_pack`
    (docs Section K - never a fabricated evidence reference). Returns a
    new, independent `ReviewAction` - it never mutates `review_request` or
    anything in `actions_so_far`, and it never touches
    `evidence_pack`/any Phase 8-14 object beyond reading `evidence_pack`'s
    own evidence IDs for the one validation check above.
    """
    if not isinstance(review_request, ReviewRequest):
        raise TypeError(f"review_request must be a ReviewRequest, got {type(review_request).__name__}")
    if not isinstance(actions_so_far, list) or any(not isinstance(a, ReviewAction) for a in actions_so_far):
        raise TypeError("actions_so_far must be a list of ReviewAction")
    if reviewer_comment is not None and not isinstance(reviewer_comment, str):
        raise TypeError(f"reviewer_comment must be a string or None, got {type(reviewer_comment).__name__}")
    if config is None:
        config = HumanReviewConfig()
    elif not isinstance(config, HumanReviewConfig):
        raise TypeError(f"config must be a HumanReviewConfig or None, got {type(config).__name__}")

    validation.validate_reviewer_id(reviewer_id)
    validation.validate_action_type(action)

    current_status = compute_current_status(review_request, actions_so_far)
    if current_status in TERMINAL_REVIEW_STATUSES:
        raise InvalidReviewTransitionError(
            f"review_request {review_request.review_request_id!r} is already in terminal status "
            f"{current_status!r} - no further actions are permitted"
        )
    new_status = ACTION_TRANSITIONS.get((current_status, action))
    if new_status is None:
        raise InvalidReviewTransitionError(f"no transition exists for (status={current_status!r}, action={action!r})")

    selected_evidence_ids = list(selected_evidence_ids) if selected_evidence_ids is not None else []
    validation.validate_selected_evidence_ids(selected_evidence_ids, evidence_pack)

    sequence_number = len(actions_so_far)
    review_action_id = compute_review_action_id(
        config.schema_version, review_request.review_request_id, sequence_number, reviewer_id, action,
        current_status, new_status, reviewer_comment, selected_evidence_ids, config.signature,
    )

    return ReviewAction(
        schema_version=config.schema_version,
        review_action_id=review_action_id,
        review_request_id=review_request.review_request_id,
        sequence_number=sequence_number,
        reviewer_id=reviewer_id,
        action=action,
        previous_status=current_status,
        new_status=new_status,
        reviewer_comment=reviewer_comment,
        selected_evidence_ids=selected_evidence_ids,
        metadata={},
        config_signature=config.signature,
    )
