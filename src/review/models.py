"""
Phase 15 human-in-the-loop data shapes
(docs/PHASE_15_HUMAN_IN_THE_LOOP.md Sections F, G, H, I, J, Q, R).

CRITICAL DISTINCTIONS preserved throughout this module, per explicit
instruction:

1. AUTHORITATIVE SYSTEM DATA vs REVIEWER DECISION - `ReviewCaseSnapshot`
   holds only a flat, read-only SUMMARY of upstream facts (state/status
   strings and identity references), never the live upstream objects
   themselves and never a mutable copy of them. `ReviewAction` records a
   reviewer's decision as an independent, separately-identified fact -
   it has no field that could overwrite `classification_state`,
   `jurisdiction_state`, `grounding_status`, `safety_status`, an
   evidence_id, or a citation identity anywhere upstream.
2. TRIGGER REASONS are drawn EXCLUSIVELY from vocabulary values that
   already exist in Phase 1/9/10/11/12/13/14's own contracts
   (`CLASSIFICATION_STATES`, `REGULATORY_TRACK_VALUES`,
   `EVIDENCE_STATE_VALUES`, `JURISDICTION_STATES`, citation
   `CITATION_STATUSES`, `GROUNDING_STATUSES`, `SAFETY_STATUSES`,
   `DELIVERY_STATUSES`) - no new regulatory-risk category is invented
   anywhere in this phase.
3. PRIORITY is a small, CATEGORICAL vocabulary (`NORMAL`/`HIGH`/
   `CRITICAL`), never a fabricated numeric probability - mirroring Phase
   13's own `engineering_signal_band` discipline exactly.
4. NO TIMESTAMPS - every identity/ordering field in this project is a
   deterministic hash or an explicit ordinal, never a random UUID or
   wall-clock timestamp (`docs/PHASE_15_HUMAN_IN_THE_LOOP.md` Section
   AA/W). `ReviewAction.sequence_number` provides deterministic ordering
   within one review request without a timestamp.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from classification.models import (
    CLASSIFICATION_STATES,
    EVIDENCE_STATE_VALUES,
    REGULATORY_TRACK_VALUES,
)
from generation.models import GROUNDING_STATUSES
from jurisdiction.models import JURISDICTION_STATES
from multilingual.models import DELIVERY_STATUSES, SCRIPT_TAGS
from safety.models import ENGINEERING_SIGNAL_BANDS, SAFETY_STATUSES

REVIEW_SCHEMA_VERSION = "1.0.0"

# Provider/reviewer-adjacent metadata must never carry credential-shaped
# keys - reused verbatim from Phase 10/14's own guard convention.
_FORBIDDEN_METADATA_KEY_SUBSTRINGS = (
    "api_key",
    "apikey",
    "credential",
    "secret",
    "password",
    "access_token",
    "auth_token",
    "bearer",
)

# A defensive, documented bound on free-text reviewer comments (docs
# Section S: "Do NOT create an unbounded free-text audit format").
# [OUR ENHANCEMENT] - not derived from any project contract; a
# deliberately generous limit that never truncates a realistic review
# comment while still ruling out unbounded storage.
MAX_REVIEWER_COMMENT_LENGTH = 10_000

# --- Trigger vocabulary (docs Section E) -----------------------------------
# Every reason below maps to an upstream vocabulary value that ALREADY
# exists in an earlier phase's own contract - never an invented
# regulatory-risk category. See config/human_review_contract.yaml for the
# machine-readable mirror of this table.
TRIGGER_SAFETY_ESCALATE = "SAFETY_ESCALATE"
TRIGGER_SAFETY_ABSTAIN = "SAFETY_ABSTAIN"
TRIGGER_CLASSIFICATION_AMBIGUOUS = "CLASSIFICATION_AMBIGUOUS"
TRIGGER_CLASSIFICATION_UNRESOLVED = "CLASSIFICATION_UNRESOLVED"
TRIGGER_CLASSIFICATION_NEEDS_EVIDENCE = "CLASSIFICATION_NEEDS_EVIDENCE"
TRIGGER_REGULATORY_TRACK_CONFLICTING = "REGULATORY_TRACK_CONFLICTING"
TRIGGER_JURISDICTION_AMBIGUOUS = "JURISDICTION_AMBIGUOUS"
TRIGGER_JURISDICTION_UNRESOLVED = "JURISDICTION_UNRESOLVED"
TRIGGER_CITATION_INTEGRITY_FAILURE = "CITATION_INTEGRITY_FAILURE"
TRIGGER_GROUNDING_FAILURE = "GROUNDING_FAILURE"
TRIGGER_MULTILINGUAL_DELIVERY_ISSUE = "MULTILINGUAL_DELIVERY_ISSUE"

TRIGGER_REASON_CODES = frozenset(
    {
        TRIGGER_SAFETY_ESCALATE,
        TRIGGER_SAFETY_ABSTAIN,
        TRIGGER_CLASSIFICATION_AMBIGUOUS,
        TRIGGER_CLASSIFICATION_UNRESOLVED,
        TRIGGER_CLASSIFICATION_NEEDS_EVIDENCE,
        TRIGGER_REGULATORY_TRACK_CONFLICTING,
        TRIGGER_JURISDICTION_AMBIGUOUS,
        TRIGGER_JURISDICTION_UNRESOLVED,
        TRIGGER_CITATION_INTEGRITY_FAILURE,
        TRIGGER_GROUNDING_FAILURE,
        TRIGGER_MULTILINGUAL_DELIVERY_ISSUE,
    }
)

# Categorical priority only (docs Section E/critical instruction: "NO
# NUMERIC CONFIDENCE INVENTION"). Ordered low-to-high for max()-style
# comparison via index lookup - never a numeric score.
PRIORITY_LEVELS = ("NORMAL", "HIGH", "CRITICAL")
PRIORITY_NOT_APPLICABLE = "NOT_APPLICABLE"
REVIEW_PRIORITIES = frozenset(PRIORITY_LEVELS) | {PRIORITY_NOT_APPLICABLE}

# Fixed, documented mapping - each trigger reason has exactly one
# priority. [ENGINEERING RECOMMENDATION]: CRITICAL is reserved for a
# jurisdiction/classification-ambiguity escalation (cross-jurisdiction
# risk), HIGH for anything that blocks a trustworthy grounded answer
# (abstention, conflicting regulatory track, citation/grounding failure,
# jurisdiction ambiguity), NORMAL for informational/lower-severity issues
# (unresolved-but-not-ambiguous states, a translation-only problem).
TRIGGER_PRIORITY = {
    TRIGGER_SAFETY_ESCALATE: "CRITICAL",
    TRIGGER_SAFETY_ABSTAIN: "HIGH",
    TRIGGER_CLASSIFICATION_AMBIGUOUS: "HIGH",
    TRIGGER_CLASSIFICATION_UNRESOLVED: "NORMAL",
    TRIGGER_CLASSIFICATION_NEEDS_EVIDENCE: "NORMAL",
    TRIGGER_REGULATORY_TRACK_CONFLICTING: "HIGH",
    TRIGGER_JURISDICTION_AMBIGUOUS: "HIGH",
    TRIGGER_JURISDICTION_UNRESOLVED: "NORMAL",
    TRIGGER_CITATION_INTEGRITY_FAILURE: "HIGH",
    TRIGGER_GROUNDING_FAILURE: "HIGH",
    TRIGGER_MULTILINGUAL_DELIVERY_ISSUE: "NORMAL",
}

# --- Review state machine (docs Section G) ---------------------------------
REVIEW_STATUSES = frozenset({"PENDING", "IN_REVIEW", "APPROVED", "REJECTED", "NEEDS_MORE_EVIDENCE", "ESCALATED"})
TERMINAL_REVIEW_STATUSES = frozenset({"APPROVED", "REJECTED", "NEEDS_MORE_EVIDENCE", "ESCALATED"})
INITIAL_REVIEW_STATUS = "PENDING"

# --- Reviewer actions / decisions (docs Section H) -------------------------
ACTION_START_REVIEW = "START_REVIEW"
ACTION_APPROVE = "APPROVE"
ACTION_REJECT = "REJECT"
ACTION_REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"
ACTION_ESCALATE = "ESCALATE"
ACTION_TYPES = frozenset({ACTION_START_REVIEW, ACTION_APPROVE, ACTION_REJECT, ACTION_REQUEST_MORE_EVIDENCE, ACTION_ESCALATE})

# The ENTIRE, closed transition table - deterministic, first-match-only.
# Any (status, action) pair not listed here is an invalid transition.
ACTION_TRANSITIONS = {
    ("PENDING", ACTION_START_REVIEW): "IN_REVIEW",
    ("PENDING", ACTION_APPROVE): "APPROVED",
    ("PENDING", ACTION_REJECT): "REJECTED",
    ("PENDING", ACTION_REQUEST_MORE_EVIDENCE): "NEEDS_MORE_EVIDENCE",
    ("PENDING", ACTION_ESCALATE): "ESCALATED",
    ("IN_REVIEW", ACTION_APPROVE): "APPROVED",
    ("IN_REVIEW", ACTION_REJECT): "REJECTED",
    ("IN_REVIEW", ACTION_REQUEST_MORE_EVIDENCE): "NEEDS_MORE_EVIDENCE",
    ("IN_REVIEW", ACTION_ESCALATE): "ESCALATED",
}

# --- Presentation authorization (docs Section O) ---------------------------
AUTHORIZATION_SOURCES = frozenset({"AUTOMATED_SAFE_TO_PRESENT", "HUMAN_REVIEW_APPROVED", "BLOCKED"})

# Fixed disclaimer text for a human-approved presentation - mirrors
# classification.models.FIXED_DISCLAIMER exactly in spirit (docs Section
# "APPROVAL SEMANTICS"). Human approval is a workflow fact, never a legal
# certification or government/regulatory authority claim.
FIXED_HUMAN_REVIEW_DISCLAIMER = (
    "This approval reflects only a designated reviewer's decision within this project's internal "
    "human-review workflow. It is not a legal determination, not a government or regulatory "
    "certification, and does not establish that the underlying regulatory answer is legally correct. "
    "Consult the cited authoritative source and, where applicable, a qualified professional before "
    "relying on it."
)


class ReviewSchemaError(ValueError):
    """Raised when serialized Phase 15 review data is malformed or structurally inconsistent."""


class InvalidReviewTransitionError(ValueError):
    """Raised when a reviewer action would perform a transition not present in ACTION_TRANSITIONS."""


class FakeEvidenceReferenceError(ValueError):
    """Raised when a reviewer selects an evidence_id that does not exist in the real, trusted EvidencePack."""


class ReviewerIdentityError(ValueError):
    """Raised when a reviewer_id is missing, empty, or not a string. No real authentication is implemented (docs Section I, [DEFERRED])."""


def _check_no_credential_shaped_keys(metadata: dict, *, owner: str) -> None:
    for key in metadata:
        if not isinstance(key, str):
            raise ValueError(f"{owner} metadata keys must be strings, got {key!r}")
        lowered = key.lower()
        for forbidden in _FORBIDDEN_METADATA_KEY_SUBSTRINGS:
            if forbidden in lowered:
                raise ValueError(f"{owner} metadata key {key!r} looks credential-shaped and is forbidden")


@dataclass(frozen=True)
class HumanReviewConfig:
    """
    Explicit, documented configuration. No knob currently changes trigger
    or transition behavior - the trigger/priority/transition tables are
    fixed engineering decisions (docs Section E), mirroring
    `JurisdictionFirewallConfig`'s own "no knob yet" convention. Kept for
    forward compatibility and a stable, inspectable `signature`.
    """

    schema_version: str = REVIEW_SCHEMA_VERSION

    def __post_init__(self):
        if not isinstance(self.schema_version, str) or not self.schema_version.strip():
            raise ValueError("schema_version must be a non-empty string")

    @property
    def signature(self) -> str:
        return f"human-review-config:v{self.schema_version}"


@dataclass(frozen=True)
class ReviewTriggerAssessment:
    """
    The deterministic output of `policy.evaluate_review_trigger` (docs
    Section E). Purely an intermediate/audit object - its content is
    folded into `ReviewRequest.trigger_reasons`/`priority`/`review_reason`
    when a request is actually built; it is not independently serialized.
    """

    requires_review: bool
    trigger_reasons: list
    priority: str
    basis: list
    explanation: str

    def __post_init__(self):
        if not isinstance(self.requires_review, bool):
            raise ValueError("requires_review must be a bool")
        if not isinstance(self.trigger_reasons, list) or any(x not in TRIGGER_REASON_CODES for x in self.trigger_reasons):
            raise ValueError(f"trigger_reasons must be a list drawn from {sorted(TRIGGER_REASON_CODES)}")
        if self.requires_review != bool(self.trigger_reasons):
            raise ValueError("requires_review must be true if and only if trigger_reasons is non-empty")
        if self.priority not in REVIEW_PRIORITIES:
            raise ValueError(f"priority must be one of {sorted(REVIEW_PRIORITIES)}, got {self.priority!r}")
        if self.requires_review and self.priority == PRIORITY_NOT_APPLICABLE:
            raise ValueError("priority must not be NOT_APPLICABLE when requires_review is true")
        if not self.requires_review and self.priority != PRIORITY_NOT_APPLICABLE:
            raise ValueError("priority must be NOT_APPLICABLE when requires_review is false")
        if not isinstance(self.basis, list) or any(not isinstance(x, str) for x in self.basis):
            raise ValueError("basis must be a list of strings")
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise ValueError("explanation must be a non-empty string")


@dataclass(frozen=True)
class ReviewCaseSnapshot:
    """
    A flat, read-only SUMMARY of upstream facts (docs Section Q) - never a
    live reference to, or a mutable copy of, the real upstream objects.
    Every non-None field is validated against the SAME closed vocabulary
    its source phase already defines - this module never invents a
    parallel vocabulary. This is "what system state was reviewed,"
    expressed only as already-established status/state strings plus the
    upstream objects' own deterministic identity fields (never their full
    content) - `evidence_pack_id`/`response_id`/`jurisdiction_decision_id`/
    `safety_decision_id`/`multilingual_result_id` let a reviewer or
    auditor locate the exact authoritative object elsewhere, without this
    snapshot ever duplicating its content.
    """

    schema_version: str
    classification_state: Optional[str]
    classification_input_id: Optional[str]
    regulatory_track: Optional[str]
    evidence_state: Optional[str]
    jurisdiction_state: Optional[str]
    jurisdiction_decision_id: Optional[str]
    grounding_status: Optional[str]
    response_id: Optional[str]
    evidence_pack_id: Optional[str]
    cited_evidence_ids: list
    citation_total_references: Optional[int]
    citation_valid_count: Optional[int]
    citation_invalid_count: Optional[int]
    citation_unresolved_count: Optional[int]
    safety_status: Optional[str]
    safety_decision_id: Optional[str]
    safety_engineering_signal_band: Optional[str]
    multilingual_delivery_status: Optional[str]
    multilingual_result_id: Optional[str]
    requested_language: Optional[str]
    detected_script: Optional[str]
    synthetic: Optional[bool]

    def __post_init__(self):
        if not isinstance(self.schema_version, str) or not self.schema_version.strip():
            raise ValueError("schema_version must be a non-empty string")

        def _check_enum(name, value, vocabulary):
            if value is not None and value not in vocabulary:
                raise ValueError(f"{name} must be a member of {sorted(vocabulary)} or None, got {value!r}")

        _check_enum("classification_state", self.classification_state, CLASSIFICATION_STATES)
        _check_enum("regulatory_track", self.regulatory_track, REGULATORY_TRACK_VALUES)
        _check_enum("evidence_state", self.evidence_state, EVIDENCE_STATE_VALUES)
        _check_enum("jurisdiction_state", self.jurisdiction_state, JURISDICTION_STATES)
        _check_enum("grounding_status", self.grounding_status, GROUNDING_STATUSES)
        _check_enum("safety_status", self.safety_status, SAFETY_STATUSES)
        _check_enum("safety_engineering_signal_band", self.safety_engineering_signal_band, ENGINEERING_SIGNAL_BANDS)
        _check_enum("multilingual_delivery_status", self.multilingual_delivery_status, DELIVERY_STATUSES)
        _check_enum("detected_script", self.detected_script, SCRIPT_TAGS)

        for name in (
            "classification_input_id", "jurisdiction_decision_id", "response_id", "evidence_pack_id",
            "safety_decision_id", "multilingual_result_id", "requested_language",
        ):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{name} must be a string or None")

        if not isinstance(self.cited_evidence_ids, list) or any(not isinstance(x, str) for x in self.cited_evidence_ids):
            raise ValueError("cited_evidence_ids must be a list of strings")
        if len(self.cited_evidence_ids) != len(set(self.cited_evidence_ids)):
            raise ValueError("cited_evidence_ids must not contain duplicates")

        for name in ("citation_total_references", "citation_valid_count", "citation_invalid_count", "citation_unresolved_count"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise ValueError(f"{name} must be a non-negative integer or None, got {value!r}")

        if self.synthetic is not None and not isinstance(self.synthetic, bool):
            raise ValueError("synthetic must be a bool or None")


@dataclass(frozen=True)
class ReviewRequest:
    """
    The Phase 15 escalation record (docs Section F). `review_request_id`
    is a deterministic SHA-256 hash (`policy.compute_review_request_id`) -
    never a random UUID, never derived from a timestamp. `review_status`
    is always its fixed initial value (`INITIAL_REVIEW_STATUS`) - the
    LIVE status is a derived function of the ordered `ReviewAction`
    history (`workflow.compute_current_status`), never stored/mutated on
    this frozen object. `original_query`/`canonical_query` are preserved
    verbatim, exactly like Phase 14's own `MultilingualInputContext`.
    """

    schema_version: str
    review_request_id: str
    input_id: str
    original_query: str
    canonical_query: Optional[str]
    case_snapshot: ReviewCaseSnapshot
    trigger_reasons: list
    priority: str
    review_reason: str
    review_status: str
    config_signature: str

    def __post_init__(self):
        for name in ("schema_version", "review_request_id", "input_id", "review_reason", "config_signature"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.original_query, str):
            raise ValueError("original_query must be a string")
        if self.canonical_query is not None and not isinstance(self.canonical_query, str):
            raise ValueError("canonical_query must be a string or None")
        if not isinstance(self.case_snapshot, ReviewCaseSnapshot):
            raise ValueError("case_snapshot must be a ReviewCaseSnapshot instance")
        if not isinstance(self.trigger_reasons, list) or any(x not in TRIGGER_REASON_CODES for x in self.trigger_reasons) or not self.trigger_reasons:
            raise ValueError(f"trigger_reasons must be a non-empty list drawn from {sorted(TRIGGER_REASON_CODES)}")
        if self.priority not in PRIORITY_LEVELS:
            raise ValueError(f"priority must be one of {PRIORITY_LEVELS}, got {self.priority!r}")
        if self.review_status != INITIAL_REVIEW_STATUS:
            raise ValueError(f"review_status must always be {INITIAL_REVIEW_STATUS!r} at construction, got {self.review_status!r}")


@dataclass(frozen=True)
class ReviewAction:
    """
    One immutable, append-only audit record (docs Section R). Every
    action is independently identified (`review_action_id`, a
    deterministic SHA-256 hash) and independently sequenced
    (`sequence_number`, an explicit ordinal - never a timestamp).
    `__post_init__` cross-validates `(previous_status, action) ->
    new_status` against the SAME closed `ACTION_TRANSITIONS` table
    `workflow.apply_action` uses - a hand-forged, internally-inconsistent
    ReviewAction is structurally impossible, mirroring Phase 9/12/13's own
    status/reason-code cross-validation discipline.

    `reviewer_comment` and `selected_evidence_ids` are the ONLY fields a
    reviewer's own input reaches - `reviewer_comment` is untrusted
    free text, never parsed, never able to influence `action`/
    `new_status`/`selected_evidence_ids` or anything upstream.
    `selected_evidence_ids` must be validated by `workflow.apply_action`
    against a real EvidencePack before construction - this dataclass only
    enforces the LIST SHAPE (strings, no duplicates), never evidence
    existence (that check requires a real pack, unavailable here, exactly
    like Phase 9's own `CitationReference`/`validator.py` split).
    """

    schema_version: str
    review_action_id: str
    review_request_id: str
    sequence_number: int
    reviewer_id: str
    action: str
    previous_status: str
    new_status: str
    reviewer_comment: Optional[str]
    selected_evidence_ids: list
    metadata: dict
    config_signature: str

    def __post_init__(self):
        for name in ("schema_version", "review_action_id", "review_request_id", "reviewer_id", "config_signature"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")

        if isinstance(self.sequence_number, bool) or not isinstance(self.sequence_number, int) or self.sequence_number < 0:
            raise ValueError(f"sequence_number must be a non-negative integer, got {self.sequence_number!r}")

        if self.action not in ACTION_TYPES:
            raise ValueError(f"action must be one of {sorted(ACTION_TYPES)}, got {self.action!r}")
        if self.previous_status not in REVIEW_STATUSES:
            raise ValueError(f"previous_status must be one of {sorted(REVIEW_STATUSES)}, got {self.previous_status!r}")
        if self.new_status not in REVIEW_STATUSES:
            raise ValueError(f"new_status must be one of {sorted(REVIEW_STATUSES)}, got {self.new_status!r}")

        expected_new_status = ACTION_TRANSITIONS.get((self.previous_status, self.action))
        if expected_new_status is None:
            raise InvalidReviewTransitionError(
                f"no transition exists for (previous_status={self.previous_status!r}, action={self.action!r})"
            )
        if expected_new_status != self.new_status:
            raise InvalidReviewTransitionError(
                f"action {self.action!r} from {self.previous_status!r} must produce new_status "
                f"{expected_new_status!r}, got {self.new_status!r}"
            )

        if self.reviewer_comment is not None:
            if not isinstance(self.reviewer_comment, str):
                raise ValueError("reviewer_comment must be a string or None")
            if len(self.reviewer_comment) > MAX_REVIEWER_COMMENT_LENGTH:
                raise ValueError(f"reviewer_comment must be at most {MAX_REVIEWER_COMMENT_LENGTH} characters")

        if not isinstance(self.selected_evidence_ids, list) or any(not isinstance(x, str) for x in self.selected_evidence_ids):
            raise ValueError("selected_evidence_ids must be a list of strings")
        if len(self.selected_evidence_ids) != len(set(self.selected_evidence_ids)):
            raise ValueError("selected_evidence_ids must not contain duplicates")

        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dict")
        _check_no_credential_shaped_keys(self.metadata, owner="ReviewAction")


@dataclass(frozen=True)
class PresentationAuthorization:
    """
    The "HUMAN REVIEW DECISION -> DELIVERY CONTROL" boundary object (docs
    Section O). A pure combination of a real Phase 13 `SafetyDecision` and,
    optionally, one real `ReviewAction` - it never mutates either. Reading
    `authorized=True` with `source="HUMAN_REVIEW_APPROVED"` is NOT a legal
    determination (`disclaimer` is always the fixed constant text in that
    case) - it only records that a designated reviewer approved
    presentation through this workflow.
    """

    schema_version: str
    authorized: bool
    source: str
    safety_status: Optional[str]
    review_action_id: Optional[str]
    explanation: str
    disclaimer: Optional[str]

    def __post_init__(self):
        if not isinstance(self.schema_version, str) or not self.schema_version.strip():
            raise ValueError("schema_version must be a non-empty string")
        if not isinstance(self.authorized, bool):
            raise ValueError("authorized must be a bool")
        if self.source not in AUTHORIZATION_SOURCES:
            raise ValueError(f"source must be one of {sorted(AUTHORIZATION_SOURCES)}, got {self.source!r}")
        if self.authorized != (self.source != "BLOCKED"):
            raise ValueError("authorized must be true if and only if source != BLOCKED")
        if self.safety_status is not None and not isinstance(self.safety_status, str):
            raise ValueError("safety_status must be a string or None")
        if (self.review_action_id is not None) != (self.source == "HUMAN_REVIEW_APPROVED"):
            raise ValueError("review_action_id must be set if and only if source == HUMAN_REVIEW_APPROVED")
        if self.review_action_id is not None and not isinstance(self.review_action_id, str):
            raise ValueError("review_action_id must be a string or None")
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise ValueError("explanation must be a non-empty string")
        if (self.disclaimer is not None) != (self.source == "HUMAN_REVIEW_APPROVED"):
            raise ValueError("disclaimer must be set if and only if source == HUMAN_REVIEW_APPROVED")
        if self.disclaimer is not None and self.disclaimer != FIXED_HUMAN_REVIEW_DISCLAIMER:
            raise ValueError("disclaimer must be exactly the fixed constant text - never altered, never omitted")
