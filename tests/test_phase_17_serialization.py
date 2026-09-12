"""
Phase 17 tests: HTTP response serialization and OpenAPI schema content
(docs/PHASE_17_BACKEND_PRODUCTIZATION.md Sections AC, "API TESTING" items
27-29). No pickle exists anywhere in this package - JSON only.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.dependencies import get_application_service
from application.service import ApplicationService
from generation.providers import FakeGenerationProvider


@pytest.fixture()
def app():
    return create_app()


@pytest.fixture()
def client(app):
    service = ApplicationService(generation_provider=FakeGenerationProvider(response_text="uncited answer"))
    app.dependency_overrides[get_application_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


def test_health_response_is_valid_json_matching_schema(client):
    response = client.get("/health")
    body = json.loads(response.text)
    assert set(body.keys()) == {"status", "api_version", "corpus_status", "generation_provider_configured", "translation_provider_configured"}


def test_query_response_is_valid_json_matching_schema(client):
    response = client.post("/api/v1/query", json={"query": "test query"})
    body = json.loads(response.text)
    expected_keys = {
        "request_id", "delivery_status", "reason_code", "explanation", "answer_text", "answer_language",
        "translation_applied", "provider_name", "original_query", "canonical_query", "detected_script",
        "requested_language", "classification", "jurisdiction", "grounding_status", "safety_status",
        "cited_evidence_ids", "citation_summary", "review", "evidence_preservation_status", "synthetic",
    }
    assert set(body.keys()) == expected_keys


def test_query_response_field_ordering_is_deterministic_across_calls(client):
    r1 = client.post("/api/v1/query", json={"query": "test query"})
    r2 = client.post("/api/v1/query", json={"query": "test query"})
    assert list(json.loads(r1.text).keys()) == list(json.loads(r2.text).keys())


def test_query_response_content_type_is_json(client):
    response = client.post("/api/v1/query", json={"query": "test query"})
    assert response.headers["content-type"].startswith("application/json")


def test_openapi_schema_contains_intended_endpoints(app):
    paths = app.openapi()["paths"]
    assert "/health" in paths
    assert "/api/v1/query" in paths
    assert "get" in paths["/health"]
    assert "post" in paths["/api/v1/query"]


def test_openapi_schema_contains_request_and_response_models(app):
    schema = app.openapi()
    components = schema.get("components", {}).get("schemas", {})
    assert "QueryRequest" in components
    assert "QueryResponse" in components
    assert "HealthResponse" in components


def test_openapi_schema_query_endpoint_documents_request_body(app):
    schema = app.openapi()
    query_op = schema["paths"]["/api/v1/query"]["post"]
    assert "requestBody" in query_op
    assert "200" in query_op["responses"]


def test_no_evaluation_or_review_internal_classes_exposed_in_openapi(app):
    schema = app.openapi()
    components = schema.get("components", {}).get("schemas", {})
    forbidden = {"ReviewAction", "EvidencePack", "GroundedResponse", "SafetyDecision", "ClassificationResult", "JurisdictionDecision"}
    assert forbidden.isdisjoint(components.keys())


def test_empty_dataset_evidence_pack_response_serializes_cleanly(client):
    response = client.post("/api/v1/query", json={"query": "no evidence anywhere for this query"})
    body = response.json()
    assert body["cited_evidence_ids"] == []
    assert body["citation_summary"]["total_references"] == 0
    assert body["citation_summary"]["citation_integrity_validation_rate"] == 0.0


def test_nested_review_object_serializes_correctly(app):
    service = ApplicationService(generation_provider=FakeGenerationProvider(response_text="x"))
    app.dependency_overrides[get_application_service] = lambda: service
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/api/v1/query", json={"query": "how can i protect this and what compliance requirement applies in India"})
    body = response.json()
    assert isinstance(body["review"], dict)
    assert isinstance(body["review"]["trigger_reasons"], list)
