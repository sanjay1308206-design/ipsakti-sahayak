"""
Phase 17 application-layer data shapes
(docs/PHASE_17_BACKEND_PRODUCTIZATION.md Sections F, K, L, X).

Plain dataclasses only - no FastAPI, no Pydantic, no HTTP anywhere in this
module (docs Section AD, "TESTABILITY"). `src/api/schemas.py` converts
these to/from the HTTP wire format; this module never imports anything
from `src/api/`.

CRITICAL IDENTITY SEPARATION (docs Section X): `ApplicationQueryRequest.request_id`
is an APPLICATION-layer identity, computed by `application.service.compute_request_id`.
It is never an Evidence ID, a Document ID, a Review Request ID, or a
GroundedResponse ID - those remain each owning phase's own, separately
computed, deterministic identity. This module never derives one identity
domain from another.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from classification.models import CLASSIFICATION_STATES, REGULATORY_TRACK_VALUES, USER_INTENT_VALUES
from generation.models import GROUNDING_STATUSES
from jurisdiction.models import JURISDICTION_STATES
from multilingual.models import DELIVERY_STATUSES, SCRIPT_TAGS
from review.models import PRIORITY_LEVELS, REVIEW_STATUSES, TRIGGER_REASON_CODES
from safety.models import SAFETY_STATUSES

APPLICATION_SCHEMA_VERSION = "1.0.0"

# [OUR ENHANCEMENT] application-level input-size guard (docs "REQUEST
# LIMITS") - not derived from any upstream contract, a defensive default
# only. Configurable via application.config.BackendConfig, never hard-coded
# as the only bound.
DEFAULT_MAX_QUERY_LENGTH = 4000


class ApplicationSchemaError(ValueError):
    """Raised when an application-layer request/result is malformed or structurally inconsistent."""


class InvalidQueryError(ValueError):
    """Raised for a client-input problem the API layer must map to a 4xx response (docs Section M)."""


def _check_enum(name: str, value, vocabulary) -> None:
    if value not in vocabulary:
        raise ValueError(f"{name} must be one of {sorted(vocabulary)}, got {value!r}")


def _check_optional_enum(name: str, value, vocabulary) -> None:
    if value is not None and value not in vocabulary:
        raise ValueError(f"{name} must be a member of {sorted(vocabulary)} or None, got {value!r}")


@dataclass(frozen=True)
class ApplicationQueryRequest:
    """
    The application-layer request shape (docs Section K). `jurisdiction`/
    `requested_language` are UNTRUSTED, permissive passthrough values -
    exactly like Phase 9's own `CitationReference`/Phase 12's own
    `explicit_jurisdiction` convention: classifying them as valid/invalid
    happens downstream, in Phase 12/14's own real logic, never here.
    """

    schema_version: str
    request_id: str
    query: str
    requested_language: Optional[str] = None
    jurisdiction: Optional[str] = None
    formulation_description: Optional[str] = None
    source_language: Optional[str] = None

    def __post_init__(self):
        for name in ("schema_version", "request_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.query, str):
            raise ValueError("query must be a string")
        for name in ("requested_language", "jurisdiction", "formulation_description", "source_language"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{name} must be a string or None")


@dataclass(frozen=True)
class ClassificationSummary:
    """A read-only summary of Phase 11's own ClassificationResult - never a second classifier."""

    classification_state: str
    user_intent: str
    regulatory_track: str
    requires_evidence: bool
    requires_escalation: bool

    def __post_init__(self):
        _check_enum("classification_state", self.classification_state, CLASSIFICATION_STATES)
        _check_enum("user_intent", self.user_intent, USER_INTENT_VALUES)
        _check_enum("regulatory_track", self.regulatory_track, REGULATORY_TRACK_VALUES)
        if not isinstance(self.requires_evidence, bool):
            raise ValueError("requires_evidence must be a bool")
        if not isinstance(self.requires_escalation, bool):
            raise ValueError("requires_escalation must be a bool")


@dataclass(frozen=True)
class JurisdictionSummary:
    """A read-only summary of Phase 12's own JurisdictionDecision - never a second firewall."""

    state: str
    normalized_jurisdiction: Optional[str]
    requires_escalation: bool

    def __post_init__(self):
        _check_enum("state", self.state, JURISDICTION_STATES)
        if self.normalized_jurisdiction is not None and not isinstance(self.normalized_jurisdiction, str):
            raise ValueError("normalized_jurisdiction must be a string or None")
        if not isinstance(self.requires_escalation, bool):
            raise ValueError("requires_escalation must be a bool")


@dataclass(frozen=True)
class CitationSummary:
    """A read-only summary of Phase 9's own CitationCoverageMetrics (reached via Phase 10) - never re-derived."""

    total_references: int
    valid_count: int
    invalid_count: int
    unresolved_count: int
    citation_integrity_validation_rate: float

    def __post_init__(self):
        for name in ("total_references", "valid_count", "invalid_count", "unresolved_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if isinstance(self.citation_integrity_validation_rate, bool) or not isinstance(self.citation_integrity_validation_rate, (int, float)):
            raise ValueError("citation_integrity_validation_rate must be a number")
        if not (0.0 <= float(self.citation_integrity_validation_rate) <= 1.0):
            raise ValueError("citation_integrity_validation_rate must be within [0.0, 1.0]")


@dataclass(frozen=True)
class ReviewSummary:
    """A read-only summary of Phase 15's own ReviewRequest - never a second escalation engine."""

    review_request_id: str
    trigger_reasons: list
    priority: str
    review_status: str

    def __post_init__(self):
        if not isinstance(self.review_request_id, str) or not self.review_request_id.strip():
            raise ValueError("review_request_id must be a non-empty string")
        if not isinstance(self.trigger_reasons, list) or any(x not in TRIGGER_REASON_CODES for x in self.trigger_reasons) or not self.trigger_reasons:
            raise ValueError(f"trigger_reasons must be a non-empty list drawn from {sorted(TRIGGER_REASON_CODES)}")
        _check_enum("priority", self.priority, PRIORITY_LEVELS)
        _check_enum("review_status", self.review_status, REVIEW_STATUSES)


@dataclass(frozen=True)
class ApplicationQueryResult:
    """
    The application-layer response shape (docs Section L). Every
    security-critical field is a direct, unmodified passthrough from the
    real upstream Phase 9/10/11/12/13/14/15 objects - there is no code
    path anywhere in this dataclass or its construction
    (`application.service.ApplicationService.query`) that derives them
    from client input or from `answer_text`.
    """

    schema_version: str
    request_id: str
    delivery_status: str
    reason_code: str
    explanation: str
    answer_text: Optional[str]
    answer_language: Optional[str]
    translation_applied: bool
    provider_name: Optional[str]
    original_query: str
    canonical_query: str
    detected_script: str
    requested_language: Optional[str]
    classification: Optional[ClassificationSummary]
    jurisdiction: Optional[JurisdictionSummary]
    grounding_status: Optional[str]
    safety_status: Optional[str]
    cited_evidence_ids: list
    citation_summary: Optional[CitationSummary]
    review: Optional[ReviewSummary]
    evidence_preservation_status: str
    synthetic: Optional[bool]

    def __post_init__(self):
        for name in ("schema_version", "request_id", "reason_code", "explanation", "original_query", "canonical_query", "evidence_preservation_status"):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise ValueError(f"{name} must be a string")
        for name in ("schema_version", "request_id", "reason_code", "explanation", "evidence_preservation_status"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must be non-empty")
        _check_enum("delivery_status", self.delivery_status, DELIVERY_STATUSES)
        _check_enum("detected_script", self.detected_script, SCRIPT_TAGS)
        if self.answer_text is not None and not isinstance(self.answer_text, str):
            raise ValueError("answer_text must be a string or None")
        for name in ("answer_language", "provider_name", "requested_language"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{name} must be a string or None")
        if not isinstance(self.translation_applied, bool):
            raise ValueError("translation_applied must be a bool")
        if self.classification is not None and not isinstance(self.classification, ClassificationSummary):
            raise ValueError("classification must be a ClassificationSummary or None")
        if self.jurisdiction is not None and not isinstance(self.jurisdiction, JurisdictionSummary):
            raise ValueError("jurisdiction must be a JurisdictionSummary or None")
        _check_optional_enum("grounding_status", self.grounding_status, GROUNDING_STATUSES)
        _check_optional_enum("safety_status", self.safety_status, SAFETY_STATUSES)
        if not isinstance(self.cited_evidence_ids, list) or any(not isinstance(x, str) for x in self.cited_evidence_ids):
            raise ValueError("cited_evidence_ids must be a list of strings")
        if len(self.cited_evidence_ids) != len(set(self.cited_evidence_ids)):
            raise ValueError("cited_evidence_ids must not contain duplicates")
        if self.citation_summary is not None and not isinstance(self.citation_summary, CitationSummary):
            raise ValueError("citation_summary must be a CitationSummary or None")
        if self.review is not None and not isinstance(self.review, ReviewSummary):
            raise ValueError("review must be a ReviewSummary or None")
        if self.synthetic is not None and not isinstance(self.synthetic, bool):
            raise ValueError("synthetic must be a bool or None")
