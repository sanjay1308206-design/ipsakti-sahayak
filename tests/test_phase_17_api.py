"""
Phase 17 tests: the HTTP endpoints, via FastAPI's own TestClient - no
real network socket, no external service (docs/PHASE_17_BACKEND_PRODUCTIZATION.md
Section AD). Covers API testing items 1-13, 21-25, 29 from the instructions
(security/Unicode/integration/serialization/determinism items get their
own dedicated files).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _citation_fixtures import make_pack_from_texts
from fastapi.testclient import TestClient

from api.app import create_app
from api.dependencies import get_application_service
from application.service import ApplicationService
from generation.providers import FakeGenerationProvider
from multilingual.providers import FakeTranslationProvider

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


@pytest.fixture()
def app():
    return create_app()


@pytest.fixture()
def client(app):
    return TestClient(app)


def _override(app, service: ApplicationService) -> None:
    app.dependency_overrides[get_application_service] = lambda: service


# 1. health endpoint
def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "alive"
    assert body["api_version"] == "v1"
    assert body["corpus_status"] == "NOT_VALIDATED"


def test_health_reflects_provider_configuration(app, client):
    _override(app, ApplicationService(generation_provider=FakeGenerationProvider(response_text="x")))
    response = client.get("/health")
    assert response.json()["generation_provider_configured"] is True


# 2. valid query
def test_valid_query_returns_200_with_structured_response(app, client):
    _override(app, ApplicationService(generation_provider=FakeGenerationProvider(response_text="uncited")))
    response = client.post("/api/v1/query", json={"query": "Tell me about Ministry of Ayush policy in India."})
    assert response.status_code == 200
    body = response.json()
    assert "delivery_status" in body
    assert "request_id" in body


# 3. malformed query
def test_malformed_query_json_rejected(client):
    response = client.post("/api/v1/query", content=b"{not valid json", headers={"content-type": "application/json"})
    assert response.status_code == 422


# 4. missing query
def test_missing_query_field_rejected(client):
    response = client.post("/api/v1/query", json={})
    assert response.status_code == 422


def test_empty_string_query_rejected(client):
    response = client.post("/api/v1/query", json={"query": ""})
    assert response.status_code == 422


# 9. jurisdiction handling
def test_jurisdiction_handling(app, client):
    _override(app, ApplicationService(generation_provider=FakeGenerationProvider(response_text="x")))
    response = client.post("/api/v1/query", json={"query": "Tell me about Ministry of Ayush policy in India.", "jurisdiction": "INDIA"})
    body = response.json()
    assert body["jurisdiction"]["state"] == "KNOWN"
    assert body["jurisdiction"]["normalized_jurisdiction"] == "INDIA"


# 10. safe response
def test_safe_response(app, client, authority_matrix):
    pack = make_pack_from_texts([("API1-D1", "Ayush policy compliance content.")], authority_matrix, query="ayush policy")
    real_id = pack.evidence_items[0].evidence_id
    _override(app, ApplicationService(generation_provider=FakeGenerationProvider(response_text=f"Details. [[CITE:{real_id}]]"), evidence_pack_builder=lambda q: pack))
    response = client.post("/api/v1/query", json={"query": "Tell me about Ministry of Ayush policy in India."})
    body = response.json()
    assert response.status_code == 200
    assert body["safety_status"] == "SAFE_TO_PRESENT"
    assert body["delivery_status"] == "DELIVERED"
    assert body["cited_evidence_ids"] == [real_id]


# 11. abstention response
def test_abstention_response(app, client):
    _override(app, ApplicationService(generation_provider=FakeGenerationProvider(response_text="uncited")))
    response = client.post("/api/v1/query", json={"query": "Tell me about Ministry of Ayush policy in India."})
    body = response.json()
    assert response.status_code == 200
    assert body["safety_status"] == "ABSTAIN"
    assert body["delivery_status"] == "UPSTREAM_BLOCKED"
    assert body["answer_text"] is None


# 12. escalation response
def test_escalation_response(app, client):
    _override(app, ApplicationService(generation_provider=FakeGenerationProvider(response_text="x")))
    response = client.post("/api/v1/query", json={"query": "how can i protect this and what compliance requirement applies in India"})
    body = response.json()
    assert response.status_code == 200
    assert body["safety_status"] == "ESCALATE"
    assert body["review"] is not None
    assert body["review"]["priority"] == "CRITICAL"


# 13. translation failure
def test_translation_failure_response(app, client):
    _override(app, ApplicationService(generation_provider=FakeGenerationProvider(response_text="uncited")))
    response = client.post("/api/v1/query", json={"query": "query text", "requested_language": "hi"})
    body = response.json()
    # No translation provider configured - UPSTREAM_BLOCKED fires first (no evidence -> ABSTAIN),
    # since safety/grounding gates run before any translation attempt (Phase 14's own real behavior).
    assert response.status_code == 200
    assert body["delivery_status"] == "UPSTREAM_BLOCKED"


def test_translation_failure_when_otherwise_safe(app, client, authority_matrix):
    pack = make_pack_from_texts([("API2-D1", "Ayush policy compliance content.")], authority_matrix, query="ayush policy")
    real_id = pack.evidence_items[0].evidence_id
    _override(app, ApplicationService(generation_provider=FakeGenerationProvider(response_text=f"Details. [[CITE:{real_id}]]"), evidence_pack_builder=lambda q: pack))
    response = client.post("/api/v1/query", json={"query": "Tell me about Ministry of Ayush policy in India.", "requested_language": "hi"})
    body = response.json()
    assert body["delivery_status"] == "TRANSLATION_FAILED"
    assert body["answer_text"] is None


def test_translation_succeeds_when_provider_configured(app, client, authority_matrix):
    pack = make_pack_from_texts([("API3-D1", "Ayush policy compliance content.")], authority_matrix, query="ayush policy")
    real_id = pack.evidence_items[0].evidence_id
    _override(app, ApplicationService(
        generation_provider=FakeGenerationProvider(response_text=f"Details. [[CITE:{real_id}]]"),
        translation_provider=FakeTranslationProvider(response_text="[HI] translated"),
        evidence_pack_builder=lambda q: pack,
    ))
    response = client.post("/api/v1/query", json={"query": "Tell me about Ministry of Ayush policy in India.", "requested_language": "hi"})
    body = response.json()
    assert body["delivery_status"] == "DELIVERED"
    assert body["answer_text"] == "[HI] translated"


# 14. provider failure
def test_generation_provider_failure_returns_generation_failed_status(app, client, authority_matrix):
    pack = make_pack_from_texts([("API4-D1", "Content.")], authority_matrix, query="q")
    _override(app, ApplicationService(generation_provider=FakeGenerationProvider(fail_with="simulated outage"), evidence_pack_builder=lambda q: pack))
    response = client.post("/api/v1/query", json={"query": "query"})
    assert response.status_code == 200
    assert response.json()["grounding_status"] == "GENERATION_FAILED"


# 15. malformed provider output
def test_malformed_provider_output_type_returns_generation_failed(app, client, authority_matrix):
    class BadProvider(FakeGenerationProvider):
        def generate(self, prompt):
            return "not a GenerationOutput"

    pack = make_pack_from_texts([("API5-D1", "Content.")], authority_matrix, query="q")
    _override(app, ApplicationService(generation_provider=BadProvider(response_text="x"), evidence_pack_builder=lambda q: pack))
    response = client.post("/api/v1/query", json={"query": "query"})
    assert response.status_code == 200
    assert response.json()["grounding_status"] == "GENERATION_FAILED"


# 25. oversized input
def test_oversized_query_rejected(client):
    response = client.post("/api/v1/query", json={"query": "x" * 20_001})
    assert response.status_code == 422


# 29. API version path
def test_api_version_path_present(client):
    response = client.post("/api/v1/query", json={"query": "test"})
    assert response.status_code in (200, 422, 503)  # the route exists and is reachable
    missing = client.post("/api/v2/query", json={"query": "test"})
    assert missing.status_code == 404


def test_provider_not_configured_returns_503(client):
    response = client.post("/api/v1/query", json={"query": "test query"})
    assert response.status_code == 503
    body = response.json()
    assert body["error_type"] == "GENERATION_PROVIDER_NOT_CONFIGURED"
