"""
Phase 17 tests: Unicode/Hindi/Tamil/mixed-script queries through the real
HTTP endpoint (docs/PHASE_17_BACKEND_PRODUCTIZATION.md Section S, "API
TESTING" items 5-8).
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
    service = ApplicationService(generation_provider=FakeGenerationProvider(response_text="uncited answer"))
    app.dependency_overrides[get_application_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


def test_hindi_devanagari_query(client):
    query = "आयुर्वेद औषधि पंजीकरण के लिए आवेदन आवश्यक है।"
    response = client.post("/api/v1/query", json={"query": query})
    assert response.status_code == 200
    body = response.json()
    assert body["original_query"] == query
    assert body["detected_script"] == "DEVANAGARI"


def test_tamil_query(client):
    query = "மருந்து பதிவு விண்ணப்பம் தேவை"
    response = client.post("/api/v1/query", json={"query": query})
    body = response.json()
    assert body["original_query"] == query
    assert body["detected_script"] == "TAMIL"


def test_mixed_script_query(client):
    query = "Ayurveda आयुर்வेद மருந்து registration"
    response = client.post("/api/v1/query", json={"query": query})
    body = response.json()
    assert body["detected_script"] == "MIXED"


def test_emoji_and_unicode_symbols_preserved(client):
    query = "Ayurveda registration query 🌿📋✅"
    response = client.post("/api/v1/query", json={"query": query})
    body = response.json()
    assert body["original_query"] == query


def test_requested_language_hindi_with_no_translation_provider(client):
    response = client.post("/api/v1/query", json={"query": "query", "requested_language": "hi"})
    body = response.json()
    assert body["requested_language"] == "hi"


def test_canonical_query_normalizes_combining_characters(client):
    decomposed = "é"  # 'e' + combining acute accent
    response = client.post("/api/v1/query", json={"query": decomposed})
    body = response.json()
    assert body["canonical_query"] == "é"  # precomposed 'é'
    assert body["original_query"] == decomposed


def test_unicode_response_json_is_not_ascii_escaped(client):
    query = "आयुर्वेद"
    response = client.post("/api/v1/query", json={"query": query})
    assert "आयुर्वेद" in response.text
