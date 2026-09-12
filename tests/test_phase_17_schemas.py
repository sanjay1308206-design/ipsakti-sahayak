"""
Phase 17 tests: Pydantic wire-schema validation
(docs/PHASE_17_BACKEND_PRODUCTIZATION.md Sections K, L).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from application.models import (
    APPLICATION_SCHEMA_VERSION,
    ApplicationQueryResult,
    CitationSummary,
    ClassificationSummary,
    JurisdictionSummary,
    ReviewSummary,
)
from api.schemas import HealthResponse, QueryRequest, QueryResponse, query_response_from_result


def test_query_request_accepts_minimal_payload():
    request = QueryRequest(query="hello")
    assert request.requested_language is None


def test_query_request_rejects_empty_query():
    with pytest.raises(ValidationError):
        QueryRequest(query="")


def test_query_request_rejects_missing_query():
    with pytest.raises(ValidationError):
        QueryRequest()


def test_query_request_rejects_oversized_query():
    with pytest.raises(ValidationError):
        QueryRequest(query="x" * 20_001)


def test_query_request_rejects_non_string_query():
    with pytest.raises(ValidationError):
        QueryRequest(query=12345)


def test_query_request_accepts_unicode_query():
    request = QueryRequest(query="आयुर्वेद औषधि पंजीकरण")
    assert request.query == "आयुर्वेद औषधि पंजीकरण"


def _result(**overrides) -> ApplicationQueryResult:
    defaults = dict(
        schema_version=APPLICATION_SCHEMA_VERSION, request_id="r" * 64, delivery_status="DELIVERED",
        reason_code="TRANSLATION_SUCCEEDED", explanation="ok", answer_text="answer", answer_language="en",
        translation_applied=False, provider_name="fake", original_query="q", canonical_query="q",
        detected_script="LATIN", requested_language=None,
        classification=ClassificationSummary("KNOWN", "GENERAL_INFORMATION_REQUEST", "UNDETERMINED", False, False),
        jurisdiction=JurisdictionSummary("KNOWN", "INDIA", False),
        grounding_status="GROUNDED", safety_status="SAFE_TO_PRESENT", cited_evidence_ids=["E1"],
        citation_summary=CitationSummary(1, 1, 0, 0, 1.0),
        review=None, evidence_preservation_status="PRESERVED", synthetic=False,
    )
    defaults.update(overrides)
    return ApplicationQueryResult(**defaults)


def test_query_response_from_result_full_round_trip():
    result = _result()
    response = query_response_from_result(result)
    assert response.classification.classification_state == "KNOWN"
    assert response.jurisdiction.normalized_jurisdiction == "INDIA"
    assert response.citation_summary.valid_count == 1


def test_query_response_from_result_handles_none_summaries():
    result = _result(classification=None, jurisdiction=None, citation_summary=None, review=None)
    response = query_response_from_result(result)
    assert response.classification is None
    assert response.jurisdiction is None
    assert response.citation_summary is None
    assert response.review is None


def test_query_response_from_result_includes_review_summary():
    review = ReviewSummary("r" * 64, ["SAFETY_ESCALATE"], "CRITICAL", "PENDING")
    result = _result(review=review, safety_status="ESCALATE", delivery_status="UPSTREAM_BLOCKED", reason_code="SAFETY_NOT_SAFE_TO_PRESENT", answer_text=None, answer_language=None)
    response = query_response_from_result(result)
    assert response.review.priority == "CRITICAL"
    assert response.review.trigger_reasons == ["SAFETY_ESCALATE"]


def test_query_response_json_preserves_unicode():
    result = _result(answer_text="अनुमोदित उत्तर")
    response = query_response_from_result(result)
    assert "अनुमोदित" in response.model_dump_json()


def test_health_response_defaults():
    response = HealthResponse(api_version="v1", generation_provider_configured=False, translation_provider_configured=False)
    assert response.status == "alive"
    assert response.corpus_status == "NOT_VALIDATED"


def test_query_request_model_json_schema_has_no_secret_fields():
    schema = QueryRequest.model_json_schema()
    forbidden_terms = ("api_key", "password", "secret", "token", "credential")
    schema_text = str(schema).lower()
    for term in forbidden_terms:
        assert term not in schema_text
