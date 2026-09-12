"""
Phase 17 tests: deterministic behavior (docs/PHASE_17_BACKEND_PRODUCTIZATION.md
Section X). Identical requests against identical fake providers/config
must produce identical request_id and identical response bodies.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _citation_fixtures import make_pack_from_texts
from fastapi.testclient import TestClient

from api.app import create_app
from api.dependencies import get_application_service
from application.service import ApplicationService, compute_request_id
from generation.providers import FakeGenerationProvider

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def test_request_id_is_deterministic_for_identical_inputs():
    ids = {compute_request_id("same query", "hi", "INDIA", None, None) for _ in range(20)}
    assert len(ids) == 1


def test_request_id_differs_for_different_queries():
    a = compute_request_id("query one", None, None, None, None)
    b = compute_request_id("query two", None, None, None, None)
    assert a != b


def test_request_id_differs_for_different_jurisdiction():
    a = compute_request_id("same query", None, "INDIA", None, None)
    b = compute_request_id("same query", None, "INTERNATIONAL", None, None)
    assert a != b


def test_repeated_http_calls_produce_identical_request_id():
    app = create_app()
    service = ApplicationService(generation_provider=FakeGenerationProvider(response_text="uncited"))
    app.dependency_overrides[get_application_service] = lambda: service
    client = TestClient(app, raise_server_exceptions=False)

    request_ids = {client.post("/api/v1/query", json={"query": "same query text"}).json()["request_id"] for _ in range(10)}
    assert len(request_ids) == 1


def test_repeated_http_calls_produce_identical_response_body(authority_matrix):
    app = create_app()
    pack = make_pack_from_texts([("DET1-D1", "Ayush policy compliance content.")], authority_matrix, query="ayush policy")
    real_id = pack.evidence_items[0].evidence_id
    service = ApplicationService(generation_provider=FakeGenerationProvider(response_text=f"Details. [[CITE:{real_id}]]"), evidence_pack_builder=lambda q: pack)
    app.dependency_overrides[get_application_service] = lambda: service
    client = TestClient(app, raise_server_exceptions=False)

    bodies = {client.post("/api/v1/query", json={"query": "Tell me about Ministry of Ayush policy in India."}).text for _ in range(5)}
    assert len(bodies) == 1


def test_application_service_query_is_deterministic(authority_matrix):
    pack = make_pack_from_texts([("DET2-D1", "Content.")], authority_matrix, query="q")
    service = ApplicationService(generation_provider=FakeGenerationProvider(response_text="uncited"), evidence_pack_builder=lambda q: pack)
    from application.models import ApplicationQueryRequest, APPLICATION_SCHEMA_VERSION

    rid = compute_request_id("q", None, None, None, None)
    request = ApplicationQueryRequest(schema_version=APPLICATION_SCHEMA_VERSION, request_id=rid, query="q")
    results = [service.query(request) for _ in range(10)]
    assert all(r == results[0] for r in results)
