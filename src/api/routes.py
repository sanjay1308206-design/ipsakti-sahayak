"""
Phase 17 HTTP routes (docs/PHASE_17_BACKEND_PRODUCTIZATION.md Sections I,
J, N). Every route body is a thin translation: parse -> build an
`application.models.ApplicationQueryRequest` -> call
`ApplicationService.query` -> convert the result to a `QueryResponse`.
No business rule (jurisdiction/classification/safety/grounding decision)
is ever made in this module - see `application.service` for all of that.

Domain status codes (docs "SAFETY RESPONSE SEMANTICS"): a successful HTTP
200 means "the pipeline ran to completion and produced a well-defined
outcome" - `DELIVERED`, `UPSTREAM_BLOCKED` (safety ABSTAIN/ESCALATE or
ungrounded), `TRANSLATION_FAILED`, and `UNSUPPORTED_LANGUAGE` are all
legitimate, honestly-reported outcomes in the response BODY, never
disguised as an error and never disguised as a normal grounded answer
when they are not. HTTP 4xx/5xx are reserved for actual request/server
failures (malformed input, no provider configured, an unexpected
exception) - the HTTP status and the domain `delivery_status` field never
contradict each other.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from application.config import API_VERSION
from application.models import APPLICATION_SCHEMA_VERSION, ApplicationQueryRequest
from application.service import ApplicationService, compute_request_id
from retrieval.production_corpus import sf05_corpus_status

from .dependencies import get_application_service
from .schemas import HealthResponse, QueryRequest, QueryResponse, query_response_from_result

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health(service: ApplicationService = Depends(get_application_service)) -> HealthResponse:
    """
    Verifies that the process is alive, reports STATIC provider
    configuration, and reports real `corpus_status` via LD-2's own
    non-raising probe (`retrieval.production_corpus.sf05_corpus_status`) -
    `"VALIDATED"` once the real, integrity-verified SF-05 corpus has been
    built and cached (at most once per process, per that module's own
    `lru_cache`), `"UNAVAILABLE"` otherwise. The probe never raises, so
    this endpoint never 500s because of corpus state.
    """
    return HealthResponse(
        api_version=API_VERSION,
        corpus_status=sf05_corpus_status(),
        generation_provider_configured=service.generation_provider is not None,
        translation_provider_configured=service.translation_provider is not None,
    )


@router.post(f"/api/{API_VERSION}/query", response_model=QueryResponse, tags=["query"])
def query(payload: QueryRequest, service: ApplicationService = Depends(get_application_service)) -> QueryResponse:
    """The single primary product endpoint - orchestration lives entirely in `ApplicationService.query`."""
    request_id = compute_request_id(payload.query, payload.requested_language, payload.jurisdiction, payload.formulation_description, payload.source_language)
    app_request = ApplicationQueryRequest(
        schema_version=APPLICATION_SCHEMA_VERSION,
        request_id=request_id,
        query=payload.query,
        requested_language=payload.requested_language,
        jurisdiction=payload.jurisdiction,
        formulation_description=payload.formulation_description,
        source_language=payload.source_language,
    )
    result = service.query(app_request)  # any exception is handled by the app's registered exception handlers
    return query_response_from_result(result)
