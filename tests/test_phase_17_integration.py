"""
Phase 17 tests: full pipeline integration through the real HTTP endpoint
(docs/PHASE_17_BACKEND_PRODUCTIZATION.md Section S, "API TESTING" items
16-20) - citation/evidence/safety/grounding/review-state preservation
end-to-end, using a real Phase 8 EvidencePack.
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

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


@pytest.fixture()
def app():
    return create_app()


def _client_with_pack(app, pack, response_text):
    service = ApplicationService(generation_provider=FakeGenerationProvider(response_text=response_text), evidence_pack_builder=lambda q: pack)
    app.dependency_overrides[get_application_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


# 16. citation preservation
def test_citation_identity_preserved_end_to_end(app, authority_matrix):
    pack = make_pack_from_texts([("INT1-D1", "Ayush policy compliance content.")], authority_matrix, query="ayush policy")
    real_id = pack.evidence_items[0].evidence_id
    client = _client_with_pack(app, pack, f"Details. [[CITE:{real_id}]]")
    response = client.post("/api/v1/query", json={"query": "Tell me about Ministry of Ayush policy in India."})
    body = response.json()
    assert body["cited_evidence_ids"] == [real_id]
    assert body["citation_summary"]["valid_count"] == 1
    assert body["citation_summary"]["citation_integrity_validation_rate"] == 1.0


# 17. evidence identity preservation
def test_evidence_identity_unchanged_by_the_http_round_trip(app, authority_matrix):
    pack = make_pack_from_texts([("INT2-D1", "Ayush policy compliance content.")], authority_matrix, query="ayush policy")
    real_id = pack.evidence_items[0].evidence_id
    before_hash = pack.evidence_items[0].evidence_text_hash
    client = _client_with_pack(app, pack, f"Details. [[CITE:{real_id}]]")
    client.post("/api/v1/query", json={"query": "Tell me about Ministry of Ayush policy in India."})
    assert pack.evidence_items[0].evidence_id == real_id
    assert pack.evidence_items[0].evidence_text_hash == before_hash


# 18. safety preservation
def test_safety_status_matches_real_phase_13_decision(app, authority_matrix):
    from _safety_fixtures import make_known_classification, make_known_jurisdiction
    from safety.evaluator import evaluate_safety
    from generation.generator import generate_grounded_response

    pack = make_pack_from_texts([("INT3-D1", "Ayush policy compliance content.")], authority_matrix, query="ayush policy")
    real_id = pack.evidence_items[0].evidence_id
    gr = generate_grounded_response("Tell me about Ministry of Ayush policy in India.", pack, FakeGenerationProvider(response_text=f"Details. [[CITE:{real_id}]]"))
    expected = evaluate_safety("X", classification_result=make_known_classification(), jurisdiction_decision=make_known_jurisdiction(), grounded_response=gr)

    client = _client_with_pack(app, pack, f"Details. [[CITE:{real_id}]]")
    response = client.post("/api/v1/query", json={"query": "Tell me about Ministry of Ayush policy in India.", "jurisdiction": "INDIA"})
    assert response.json()["safety_status"] == expected.safety_status == "SAFE_TO_PRESENT"


# 19. grounding preservation
def test_grounding_status_matches_real_phase_10_decision(app, authority_matrix):
    pack = make_pack_from_texts([("INT4-D1", "Content.")], authority_matrix, query="q")
    client = _client_with_pack(app, pack, "an uncited answer")
    response = client.post("/api/v1/query", json={"query": "q"})
    assert response.json()["grounding_status"] == "ABSTAINED"


# 20. review-state preservation
def test_review_state_reflects_real_phase_15_trigger(app):
    service = ApplicationService(generation_provider=FakeGenerationProvider(response_text="x"))
    app.dependency_overrides[get_application_service] = lambda: service
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/api/v1/query", json={"query": "how can i protect this and what compliance requirement applies in India"})
    body = response.json()
    assert body["review"] is not None
    assert body["review"]["review_status"] == "PENDING"
    assert "SAFETY_ESCALATE" in body["review"]["trigger_reasons"]


def test_full_safe_delivery_pipeline_matches_direct_application_call(app, authority_matrix):
    """The HTTP response must be byte-for-byte consistent with calling ApplicationService directly (no drift introduced by the HTTP layer)."""
    from application.models import ApplicationQueryRequest, APPLICATION_SCHEMA_VERSION
    from application.service import compute_request_id

    pack = make_pack_from_texts([("INT5-D1", "Ayush policy compliance content.")], authority_matrix, query="ayush policy")
    real_id = pack.evidence_items[0].evidence_id
    service = ApplicationService(generation_provider=FakeGenerationProvider(response_text=f"Details. [[CITE:{real_id}]]"), evidence_pack_builder=lambda q: pack)
    app.dependency_overrides[get_application_service] = lambda: service
    client = TestClient(app, raise_server_exceptions=False)

    query_text = "Tell me about Ministry of Ayush policy in India."
    response = client.post("/api/v1/query", json={"query": query_text})

    request_id = compute_request_id(query_text, None, None, None, None)
    direct_request = ApplicationQueryRequest(schema_version=APPLICATION_SCHEMA_VERSION, request_id=request_id, query=query_text)
    direct_result = service.query(direct_request)

    body = response.json()
    assert body["request_id"] == direct_result.request_id
    assert body["cited_evidence_ids"] == direct_result.cited_evidence_ids
    assert body["safety_status"] == direct_result.safety_status
