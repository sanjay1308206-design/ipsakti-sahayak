"""
Phase 17 HTTP wire schemas (docs/PHASE_17_BACKEND_PRODUCTIZATION.md
Sections K, L). Pydantic models ONLY - branching on a domain field's
value is structurally impossible here, since these classes only validate
shape and convert to/from `application.models` dataclasses.

Two size guards, deliberately different (docs "REQUEST LIMITS"):
- `_WIRE_MAX_LENGTH` is a coarse, generous wire-level sanity bound
  (`[OUR ENHANCEMENT]`, not derived from any upstream contract) - rejects
  obviously pathological payloads before they reach the application layer.
- `application.config.ApplicationConfig.max_query_length` is the real,
  configurable business-level limit, enforced once, in
  `application.service.ApplicationService.query` - never duplicated or
  silently drifted here.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from application.models import ApplicationQueryResult

_WIRE_MAX_LENGTH = 20_000


class QueryRequest(BaseModel):
    """The public request shape for `POST /api/v1/query`. Untrusted fields are passed through verbatim to the real Phase 11/12/14 contracts - never re-validated against a second, API-specific vocabulary."""

    query: str = Field(..., min_length=1, max_length=_WIRE_MAX_LENGTH, description="The user's natural-language query.")
    requested_language: Optional[str] = Field(None, max_length=64, description="Untrusted passthrough to Phase 14 - validity is decided by multilingual.delivery, never here.")
    jurisdiction: Optional[str] = Field(None, max_length=64, description="Untrusted passthrough to Phase 12 - validity is decided by jurisdiction.firewall, never here.")
    formulation_description: Optional[str] = Field(None, max_length=_WIRE_MAX_LENGTH, description="Optional free text passed to Phase 11 classification.")
    source_language: Optional[str] = Field(None, max_length=64, description="Optional caller assertion of the answer's source language, passed to Phase 14.")


class ClassificationSummarySchema(BaseModel):
    classification_state: str
    user_intent: str
    regulatory_track: str
    requires_evidence: bool
    requires_escalation: bool


class JurisdictionSummarySchema(BaseModel):
    state: str
    normalized_jurisdiction: Optional[str]
    requires_escalation: bool


class CitationSummarySchema(BaseModel):
    total_references: int
    valid_count: int
    invalid_count: int
    unresolved_count: int
    citation_integrity_validation_rate: float


class ReviewSummarySchema(BaseModel):
    review_request_id: str
    trigger_reasons: List[str]
    priority: str
    review_status: str


class QueryResponse(BaseModel):
    """
    The public response shape. Every field here is a direct passthrough
    from `application.models.ApplicationQueryResult` (itself a direct
    passthrough from the real Phase 9/10/11/12/13/14/15 objects) - no
    internal implementation class or sensitive runtime detail is ever
    exposed through this model.
    """

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
    classification: Optional[ClassificationSummarySchema]
    jurisdiction: Optional[JurisdictionSummarySchema]
    grounding_status: Optional[str]
    safety_status: Optional[str]
    cited_evidence_ids: List[str]
    citation_summary: Optional[CitationSummarySchema]
    review: Optional[ReviewSummarySchema]
    evidence_preservation_status: str
    synthetic: Optional[bool]


def query_response_from_result(result: ApplicationQueryResult) -> QueryResponse:
    """The ONLY conversion from the application layer to the wire format - a straight field mapping, never a re-derivation."""
    return QueryResponse(
        request_id=result.request_id,
        delivery_status=result.delivery_status,
        reason_code=result.reason_code,
        explanation=result.explanation,
        answer_text=result.answer_text,
        answer_language=result.answer_language,
        translation_applied=result.translation_applied,
        provider_name=result.provider_name,
        original_query=result.original_query,
        canonical_query=result.canonical_query,
        detected_script=result.detected_script,
        requested_language=result.requested_language,
        classification=ClassificationSummarySchema(**vars(result.classification)) if result.classification is not None else None,
        jurisdiction=JurisdictionSummarySchema(**vars(result.jurisdiction)) if result.jurisdiction is not None else None,
        grounding_status=result.grounding_status,
        safety_status=result.safety_status,
        cited_evidence_ids=list(result.cited_evidence_ids),
        citation_summary=CitationSummarySchema(**vars(result.citation_summary)) if result.citation_summary is not None else None,
        review=ReviewSummarySchema(**vars(result.review)) if result.review is not None else None,
        evidence_preservation_status=result.evidence_preservation_status,
        synthetic=result.synthetic,
    )


class HealthResponse(BaseModel):
    """
    Distinguishes "process is alive" (the ONLY thing actually verified
    here - no retrieval/model call is performed) from provider
    configuration (a cheap, static check) from corpus currentness (always
    `NOT_VALIDATED` - no corpus is ingested anywhere in this repository,
    docs Section I).
    """

    status: str = "alive"
    api_version: str
    corpus_status: str = "NOT_VALIDATED"
    generation_provider_configured: bool
    translation_provider_configured: bool


class ErrorResponse(BaseModel):
    """A safe, generic error shape - never a Python traceback or other sensitive runtime detail (docs Section M)."""

    detail: str
    error_type: str
