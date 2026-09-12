"""
Phase 19 tests: API-layer adversarial payloads
(docs/PHASE_19_SECURITY_ADVERSARIAL_HARDENING.md) not already covered by
tests/test_phase_17_*.py - specifically a pathologically deeply-nested
JSON body, and the genuine defect this investigation found and fixed:
Starlette's own framework-level HTTPException (raised for invalid UTF-8
or a JSON structure deep enough to exhaust the parser's recursion limit)
bypassed src/api/errors.py entirely before this phase, returning a bare
{"detail": ...} body that violated this API's one documented
ErrorResponse contract (missing `error_type`). Fixed in
src/api/errors.py by registering an explicit StarletteHTTPException
handler - see that file's inline comment for the full explanation.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.app import create_app


@pytest.fixture()
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def test_deeply_nested_json_body_rejected_not_500(client):
    depth = 20_000
    body = b'{"query": ' + b"[" * depth + b'"leaf"' + b"]" * depth + b"}"
    response = client.post("/api/v1/query", content=body, headers={"content-type": "application/json"})
    assert response.status_code != 500
    assert response.status_code != 200


def test_deeply_nested_json_body_response_matches_error_schema(client):
    depth = 20_000
    body = b'{"query": ' + b"[" * depth + b'"leaf"' + b"]" * depth + b"}"
    response = client.post("/api/v1/query", content=body, headers={"content-type": "application/json"})
    body_json = response.json()
    assert set(body_json.keys()) == {"detail", "error_type"}
    assert isinstance(body_json["detail"], str)
    assert isinstance(body_json["error_type"], str)


def test_deeply_nested_json_body_never_leaks_recursion_traceback(client):
    depth = 20_000
    body = b'{"query": ' + b"[" * depth + b'"leaf"' + b"]" * depth + b"}"
    response = client.post("/api/v1/query", content=body, headers={"content-type": "application/json"})
    assert "RecursionError" not in response.text
    assert "Traceback" not in response.text
    assert "site-packages" not in response.text


def test_invalid_utf8_body_response_matches_error_schema(client):
    """The genuine gap this phase found: an invalid-UTF-8 body previously
    returned Starlette's bare {"detail": ...} shape, not this API's
    documented ErrorResponse contract."""
    response = client.post("/api/v1/query", content=b'{"query": "\xff\xfe bad utf8"}', headers={"content-type": "application/json"})
    body_json = response.json()
    assert set(body_json.keys()) == {"detail", "error_type"}
    assert response.status_code != 500


def test_unknown_route_error_body_also_matches_error_schema(client):
    """The same fix must not regress FastAPI's own default 404 handling - the shape is
    normalized, the status code (404) and the fact that a route was not found are unchanged."""
    response = client.post("/api/v2/query", json={"query": "test"})
    assert response.status_code == 404
    body_json = response.json()
    assert set(body_json.keys()) == {"detail", "error_type"}


def test_repeated_deeply_nested_requests_remain_stable(client):
    depth = 5_000
    body = b'{"query": ' + b"[" * depth + b'"leaf"' + b"]" * depth + b"}"
    statuses = set()
    for _ in range(5):
        response = client.post("/api/v1/query", content=body, headers={"content-type": "application/json"})
        statuses.add(response.status_code)
    assert statuses == {400} or (len(statuses) == 1 and 500 not in statuses)
