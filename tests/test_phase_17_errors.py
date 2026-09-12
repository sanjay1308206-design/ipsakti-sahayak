"""
Phase 17 tests: explicit error mapping (docs/PHASE_17_BACKEND_PRODUCTIZATION.md
Section M) - 400-class client/input errors vs 500-class unexpected server
failures vs the one explicit 503 application/domain failure. No handler
ever returns HTTP 200 for an exception, and no handler ever leaks a
Python traceback, exception message with internal detail, filesystem
path, or credential.
"""

from __future__ import annotations

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
    return TestClient(app, raise_server_exceptions=False)


def _override(app, service: ApplicationService) -> None:
    app.dependency_overrides[get_application_service] = lambda: service


def test_missing_provider_maps_to_503_not_500(client):
    response = client.post("/api/v1/query", json={"query": "test"})
    assert response.status_code == 503
    assert response.json()["error_type"] == "GENERATION_PROVIDER_NOT_CONFIGURED"


def test_invalid_payload_maps_to_422_not_500(client):
    response = client.post("/api/v1/query", json={"query": ""})
    assert response.status_code == 422


def test_unexpected_exception_maps_to_500_with_generic_body(app, client):
    def broken_builder(query):
        raise RuntimeError("/etc/secret/config.yaml could not be read - credential XYZ123 invalid")

    _override(app, ApplicationService(generation_provider=FakeGenerationProvider(response_text="x"), evidence_pack_builder=broken_builder))
    response = client.post("/api/v1/query", json={"query": "test"})
    assert response.status_code == 500
    body = response.json()
    assert body == {"detail": "internal server error", "error_type": "INTERNAL_SERVER_ERROR"}


def test_unexpected_exception_never_leaks_exception_message(app, client):
    def broken_builder(query):
        raise RuntimeError("SECRET_API_KEY=sk-abcdef123456 leaked here")

    _override(app, ApplicationService(generation_provider=FakeGenerationProvider(response_text="x"), evidence_pack_builder=broken_builder))
    response = client.post("/api/v1/query", json={"query": "test"})
    assert "SECRET_API_KEY" not in response.text
    assert "sk-abcdef123456" not in response.text


def test_unexpected_exception_never_leaks_traceback(app, client):
    def broken_builder(query):
        raise ValueError("boom")

    _override(app, ApplicationService(generation_provider=FakeGenerationProvider(response_text="x"), evidence_pack_builder=broken_builder))
    response = client.post("/api/v1/query", json={"query": "test"})
    assert "Traceback" not in response.text
    assert "site-packages" not in response.text
    assert ".py" not in response.text


def test_unexpected_exception_never_leaks_filesystem_paths(app, client):
    def broken_builder(query):
        raise RuntimeError(r"failed reading Z:\SIH2026045\secret\file.txt")

    _override(app, ApplicationService(generation_provider=FakeGenerationProvider(response_text="x"), evidence_pack_builder=broken_builder))
    response = client.post("/api/v1/query", json={"query": "test"})
    assert "SIH2026045" not in response.text
    assert "secret" not in response.text


def test_no_exception_response_ever_returns_200(app, client):
    def broken_builder(query):
        raise RuntimeError("boom")

    _override(app, ApplicationService(generation_provider=FakeGenerationProvider(response_text="x"), evidence_pack_builder=broken_builder))
    for payload, expected_status in [({"query": ""}, 422), ({"query": "test"}, 500)]:
        response = client.post("/api/v1/query", json=payload)
        assert response.status_code != 200
        assert response.status_code == expected_status


def test_error_response_always_matches_error_schema(client):
    response = client.post("/api/v1/query", json={"query": "test"})
    body = response.json()
    assert set(body.keys()) == {"detail", "error_type"}
    assert isinstance(body["detail"], str)
    assert isinstance(body["error_type"], str)
