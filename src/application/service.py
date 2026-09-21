"""
Phase 17 application orchestrator
(docs/PHASE_17_BACKEND_PRODUCTIZATION.md Section F). `ApplicationService.query`
is the ONLY place that wires Phase 11 (classification) -> Phase 12
(jurisdiction) -> retrieval/evidence (Phase 5-8, via an injected
`evidence_pack_builder`) -> Phase 10 (grounded generation, which itself
calls Phase 9 citation validation internally) -> Phase 13 (safety) ->
Phase 14 (multilingual delivery) -> Phase 15 (human review) together for
one request. It never re-implements any of their decisions.

HONESTY ABOUT WHAT IS ACTUALLY EXECUTABLE (docs Section F, "do NOT fake an
end-to-end pipeline"): `default_evidence_pack_builder` (this module's own
`evidence_pack_builder` dataclass-field default) returns a REAL, honestly
EMPTY Phase 8 `EvidencePack` for every query - this drives Phase 10's own
already-real "no evidence -> ABSTAIN" path, never a fabricated one. A
real corpus/retrieval index is wired in by passing a different
`evidence_pack_builder` callable - no change to this module was required
to do so: `retrieval.production_corpus.sf05_evidence_pack_builder` (LD-2,
the one real, admitted SF-05 document) is that callable, wired in for the
running app by `src/api/dependencies.py::get_application_service` (LD-3).
This class's own default remains the empty builder - only the dependency
wiring changed.

A `GenerationProvider` MUST be explicitly supplied - this class itself
never chooses, constructs, or falls back to one. A real, network-calling
adapter now exists (`generation.gemini_provider.GeminiGenerationProvider`,
LD-1), wired in for the running app by
`src/api/dependencies.py::get_application_service` when the environment
is configured for it (`generation.provider_factory`); this module is
unchanged either way. If no provider is configured, `query()` raises
`GenerationProviderNotConfiguredError` immediately, before any other
work - an explicit application failure, never a silent substitution or a
fabricated answer.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Callable, Optional

from classification.classifier import classify
from classification.models import ClassificationInput, ClassificationResult
from evidence.builder import build_evidence_pack
from evidence.models import EvidencePack
from generation.generator import generate_grounded_response
from generation.providers import GenerationProvider
from jurisdiction.firewall import resolve_jurisdiction
from jurisdiction.models import JurisdictionDecision
from multilingual.delivery import deliver_response
from multilingual.preservation import build_input_context
from multilingual.providers import TranslationProvider
from review.policy import build_review_request

from .config import ApplicationConfig
from .models import (
    APPLICATION_SCHEMA_VERSION,
    ApplicationQueryRequest,
    ApplicationQueryResult,
    CitationSummary,
    ClassificationSummary,
    InvalidQueryError,
    JurisdictionSummary,
    ReviewSummary,
)
from safety.evaluator import evaluate_safety


class GenerationProviderNotConfiguredError(RuntimeError):
    """Raised when ApplicationService.query() needs a GenerationProvider but none was configured (docs Section V/AF - live Gemini/Qwen remain [DEFERRED])."""


def compute_request_id(query: str, requested_language: Optional[str], jurisdiction: Optional[str], formulation_description: Optional[str], source_language: Optional[str]) -> str:
    """
    Deterministic, backend-owned request identity - never a random UUID,
    never a timestamp, and (docs Section X, CRITICAL) never derived from,
    or confusable with, an Evidence ID / Document ID / Review Request ID
    / GroundedResponse ID (each of those uses a completely separate
    canonical-string namespace in its own phase's own identity function).
    """
    canonical = "|".join(
        [
            "api-query-request-v1", query, requested_language or "", jurisdiction or "",
            formulation_description or "", source_language or "",
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def default_evidence_pack_builder(query: str) -> EvidencePack:
    """No authoritative corpus is ingested anywhere in this repository - see module docstring. Returns a real, honestly empty EvidencePack."""
    return build_evidence_pack([], query)


def _classification_summary(result: ClassificationResult) -> ClassificationSummary:
    return ClassificationSummary(
        classification_state=result.classification_state, user_intent=result.user_intent,
        regulatory_track=result.formulation_classification.regulatory_track,
        requires_evidence=result.requires_evidence, requires_escalation=result.requires_escalation,
    )


def _jurisdiction_summary(decision: JurisdictionDecision) -> JurisdictionSummary:
    return JurisdictionSummary(state=decision.state, normalized_jurisdiction=decision.normalized_jurisdiction, requires_escalation=decision.requires_escalation)


def _citation_summary(coverage) -> CitationSummary:
    return CitationSummary(
        total_references=coverage.total_references, valid_count=coverage.valid_count,
        invalid_count=coverage.invalid_count, unresolved_count=coverage.unresolved_count,
        citation_integrity_validation_rate=coverage.citation_integrity_validation_rate,
    )


def _review_summary(review_request) -> Optional[ReviewSummary]:
    if review_request is None:
        return None
    return ReviewSummary(
        review_request_id=review_request.review_request_id, trigger_reasons=list(review_request.trigger_reasons),
        priority=review_request.priority, review_status=review_request.review_status,
    )


@dataclass
class ApplicationService:
    """
    The Phase 17 orchestrator. Provider objects are explicit constructor
    arguments - never silently chosen or substituted (docs "PROVIDER
    BOUNDARIES"). Fully testable without HTTP: construct directly with
    fake providers (`generation.providers.FakeGenerationProvider`,
    `multilingual.providers.FakeTranslationProvider`) exactly like every
    earlier phase's own tests already do.
    """

    generation_provider: Optional[GenerationProvider] = None
    translation_provider: Optional[TranslationProvider] = None
    evidence_pack_builder: Callable[[str], EvidencePack] = field(default=default_evidence_pack_builder)
    config: ApplicationConfig = field(default_factory=ApplicationConfig)

    def query(self, request: ApplicationQueryRequest) -> ApplicationQueryResult:
        if not isinstance(request, ApplicationQueryRequest):
            raise TypeError(f"query expects an ApplicationQueryRequest, got {type(request).__name__}")

        if self.generation_provider is None:
            raise GenerationProviderNotConfiguredError(
                "no GenerationProvider is configured for this backend - a live Gemini/Qwen adapter is not "
                "implemented anywhere in this repository (Phase 10's own [DEFERRED] boundary); this is an "
                "explicit application failure, never a fabricated answer"
            )
        if not isinstance(self.generation_provider, GenerationProvider):
            raise TypeError(f"generation_provider must be a GenerationProvider, got {type(self.generation_provider).__name__}")
        if self.translation_provider is not None and not isinstance(self.translation_provider, TranslationProvider):
            raise TypeError(f"translation_provider must be a TranslationProvider or None, got {type(self.translation_provider).__name__}")

        if not request.query.strip():
            raise InvalidQueryError("query must not be empty or whitespace-only")
        if len(request.query) > self.config.max_query_length:
            raise InvalidQueryError(f"query exceeds max_query_length ({self.config.max_query_length} characters)")
        if request.formulation_description is not None and len(request.formulation_description) > self.config.max_formulation_description_length:
            raise InvalidQueryError(f"formulation_description exceeds max_formulation_description_length ({self.config.max_formulation_description_length} characters)")

        # --- Phase 14 (input side): script detection + canonicalization ---
        input_context = build_input_context(request.request_id, request.query, requested_language=request.requested_language)

        # --- Phase 11: classification ---
        classification_result = classify(
            ClassificationInput(input_id=request.request_id, raw_query=request.query, formulation_description=request.formulation_description)
        )

        # --- Phase 12: jurisdiction firewall ---
        jurisdiction_decision = resolve_jurisdiction(
            request.request_id, classification_result=classification_result, explicit_jurisdiction=request.jurisdiction
        )

        # --- Retrieval + Phase 8 evidence construction (injected - see module docstring) ---
        pack = self.evidence_pack_builder(request.query)
        if not isinstance(pack, EvidencePack):
            raise TypeError(f"evidence_pack_builder must return an EvidencePack, got {type(pack).__name__}")

        # --- Phase 10 grounded generation (calls Phase 9 citation validation internally) ---
        grounded_response = generate_grounded_response(request.query, pack, self.generation_provider, canonical_query=input_context.canonical_query)

        # --- Phase 13: safety / abstention ---
        safety_decision = evaluate_safety(
            request.request_id, classification_result=classification_result, jurisdiction_decision=jurisdiction_decision, grounded_response=grounded_response
        )

        # --- Phase 14 (output side): translated delivery ---
        delivery = deliver_response(
            input_context, grounded_response=grounded_response, safety_decision=safety_decision,
            translation_provider=self.translation_provider, source_language=request.source_language,
        )

        # --- Phase 15: human-review trigger (may legitimately be None) ---
        review_request = build_review_request(
            request.request_id, request.query, canonical_query=input_context.canonical_query,
            classification_result=classification_result, jurisdiction_decision=jurisdiction_decision,
            grounded_response=grounded_response, safety_decision=safety_decision, multilingual_result=delivery,
        )

        return ApplicationQueryResult(
            schema_version=APPLICATION_SCHEMA_VERSION,
            request_id=request.request_id,
            delivery_status=delivery.delivery_status,
            reason_code=delivery.reason_code,
            explanation=delivery.explanation,
            answer_text=delivery.answer_text,
            answer_language=delivery.answer_language,
            translation_applied=delivery.translation_applied,
            provider_name=delivery.provider_name,
            original_query=delivery.original_query,
            canonical_query=delivery.canonical_query,
            detected_script=delivery.detected_script,
            requested_language=delivery.requested_language,
            classification=_classification_summary(classification_result),
            jurisdiction=_jurisdiction_summary(jurisdiction_decision),
            grounding_status=delivery.grounding_status,
            safety_status=delivery.safety_status,
            cited_evidence_ids=list(delivery.cited_evidence_ids),
            citation_summary=_citation_summary(grounded_response.citation_validation_summary),
            review=_review_summary(review_request),
            evidence_preservation_status=delivery.evidence_preservation_status,
            synthetic=delivery.synthetic,
        )
