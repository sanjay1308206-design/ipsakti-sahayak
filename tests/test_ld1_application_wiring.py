"""
LD-1 (Production Generation Provider) integration tests: proves the new
`src/api/dependencies.py` wiring (`get_generation_provider`) preserves
every existing fail-closed/grounding/citation/safety property end-to-end,
and that a real `GeminiGenerationProvider` (network mocked - no test here
makes a real network call or requires a real API key) flows through the
UNCHANGED Phase 9/10/13 pipeline exactly like `FakeGenerationProvider`
always has.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _citation_fixtures import make_pack_from_texts
from fastapi.testclient import TestClient

from api.app import create_app
from api.dependencies import get_application_service, get_backend_config, get_generation_provider
from application.service import ApplicationService, ApplicationQueryRequest, APPLICATION_SCHEMA_VERSION
from generation.gemini_provider import GeminiGenerationProvider
from generation.generator import generate_grounded_response

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


class _FakeResponse:
    def __init__(self, text):
        self.text = text


def _mocked_gemini_provider(response_text=None, raise_exc=None, api_key="placeholder-key") -> GeminiGenerationProvider:
    provider = GeminiGenerationProvider(api_key=api_key)

    def fake_generate_content(**kwargs):
        if raise_exc is not None:
            raise raise_exc
        return _FakeResponse(response_text)

    provider._client.models.generate_content = fake_generate_content
    return provider


@pytest.fixture(autouse=True)
def _clear_dependency_caches():
    # get_backend_config/get_generation_provider are process-lifetime
    # lru_cache singletons (mirrors Phase 17's own get_backend_config
    # convention) - tests that vary the environment must not leak a
    # cached provider/config into a later, differently-configured test.
    get_backend_config.cache_clear()
    get_generation_provider.cache_clear()
    yield
    get_backend_config.cache_clear()
    get_generation_provider.cache_clear()


# ---------------------------------------------------------------------------
# get_generation_provider: fail-closed environment wiring
# ---------------------------------------------------------------------------


def test_get_generation_provider_returns_none_when_env_unset(monkeypatch):
    monkeypatch.delenv("GENERATION_PROVIDER", raising=False)
    assert get_generation_provider() is None


def test_get_generation_provider_falls_back_to_none_on_invalid_config_without_raising(monkeypatch):
    # A typo'd/partial GENERATION_PROVIDER must never crash dependency
    # resolution (which would take the whole backend process down) - it
    # must be logged and treated exactly like "not configured."
    monkeypatch.setenv("GENERATION_PROVIDER", "not-a-real-provider")
    monkeypatch.delenv("GENERATION_API_KEY", raising=False)
    assert get_generation_provider() is None


def test_get_generation_provider_falls_back_to_none_when_api_key_missing(monkeypatch):
    monkeypatch.setenv("GENERATION_PROVIDER", "gemini")
    monkeypatch.delenv("GENERATION_API_KEY", raising=False)
    assert get_generation_provider() is None


def test_get_generation_provider_constructs_real_provider_when_configured(monkeypatch):
    monkeypatch.setenv("GENERATION_PROVIDER", "gemini")
    monkeypatch.setenv("GENERATION_API_KEY", "placeholder-key")
    provider = get_generation_provider()
    assert isinstance(provider, GeminiGenerationProvider)


# ---------------------------------------------------------------------------
# HTTP surface: /health and /api/v1/query against the REAL (unpatched)
# get_application_service dependency - no dependency_overrides here,
# proving the actual production wiring, not just a test double.
# ---------------------------------------------------------------------------


def test_query_endpoint_still_returns_503_when_unconfigured(monkeypatch):
    monkeypatch.delenv("GENERATION_PROVIDER", raising=False)
    monkeypatch.delenv("GENERATION_API_KEY", raising=False)
    client = TestClient(create_app())

    response = client.post("/api/v1/query", json={"query": "Ayurveda Aahara"})

    assert response.status_code == 503
    assert response.json()["error_type"] == "GENERATION_PROVIDER_NOT_CONFIGURED"


def test_health_endpoint_honestly_reports_unconfigured_by_default(monkeypatch):
    monkeypatch.delenv("GENERATION_PROVIDER", raising=False)
    client = TestClient(create_app())
    assert client.get("/health").json()["generation_provider_configured"] is False


def test_health_endpoint_reports_configured_true_once_env_is_set(monkeypatch):
    monkeypatch.setenv("GENERATION_PROVIDER", "gemini")
    monkeypatch.setenv("GENERATION_API_KEY", "placeholder-key")
    client = TestClient(create_app())
    assert client.get("/health").json()["generation_provider_configured"] is True


def test_misconfigured_env_keeps_query_endpoint_at_503_not_500(monkeypatch):
    monkeypatch.setenv("GENERATION_PROVIDER", "not-a-real-provider")
    client = TestClient(create_app())

    response = client.post("/api/v1/query", json={"query": "Ayurveda Aahara"})

    assert response.status_code == 503


# ---------------------------------------------------------------------------
# Full grounded-generation contract with a real (network-mocked) Gemini
# provider - proves EvidencePack -> GeminiGenerationProvider -> citation
# validation -> safety gates is unbroken.
# ---------------------------------------------------------------------------


def test_gemini_provider_produces_grounded_response_for_a_valid_citation(authority_matrix):
    pack = make_pack_from_texts([("LD1-D1", "Ayurveda Aahara labelling requires disclosure.")], authority_matrix, query="labelling")
    real_id = pack.evidence_items[0].evidence_id
    provider = _mocked_gemini_provider(response_text=f"Disclosure is required. [[CITE:{real_id}]]")

    response = generate_grounded_response("labelling query", pack, provider)

    assert response.grounding_status == "GROUNDED"
    assert response.cited_evidence_ids == [real_id]
    assert response.provider_name == "gemini"


def test_gemini_provider_fabricated_citation_is_rejected_by_existing_validator(authority_matrix):
    pack = make_pack_from_texts([("LD1-D2", "Real evidence text.")], authority_matrix, query="q")
    provider = _mocked_gemini_provider(response_text="This cites a fake source. [[CITE:EV-TOTALLY-FABRICATED-999]]")

    response = generate_grounded_response("q", pack, provider)

    assert response.grounding_status == "ABSTAINED"
    assert response.abstention_reason == "NO_VALID_CITATIONS_PRODUCED"
    assert response.cited_evidence_ids == []
    assert response.answer_text is None


def test_gemini_provider_failure_never_produces_an_unsafe_answer(authority_matrix):
    pack = make_pack_from_texts([("LD1-D3", "Real evidence text.")], authority_matrix, query="q")
    provider = _mocked_gemini_provider(raise_exc=RuntimeError("simulated network failure"))

    response = generate_grounded_response("q", pack, provider)

    assert response.grounding_status == "GENERATION_FAILED"
    assert response.answer_text is None
    assert response.cited_evidence_ids == []


def test_gemini_provider_failure_is_never_delivered_end_to_end_through_application_service(authority_matrix):
    pack = make_pack_from_texts([("LD1-D4", "Real evidence text.")], authority_matrix, query="q")
    provider = _mocked_gemini_provider(raise_exc=RuntimeError("simulated network failure"))
    service = ApplicationService(generation_provider=provider, evidence_pack_builder=lambda q: pack)

    request = ApplicationQueryRequest(
        schema_version=APPLICATION_SCHEMA_VERSION, request_id="ld1-fail-1", query="Ayurveda Aahara labelling",
        requested_language=None, jurisdiction="INDIA", formulation_description=None, source_language=None,
    )
    result = service.query(request)

    assert result.delivery_status != "DELIVERED"
    assert result.answer_text is None


def test_gemini_provider_grounded_answer_still_passes_through_safety_gates_end_to_end(authority_matrix):
    # Proves the new provider type is not special-cased anywhere in
    # ApplicationService/safety.evaluator - a valid, cited GROUNDED
    # response from GeminiGenerationProvider is evaluated by the exact
    # same Phase 13 gate chain as any FakeGenerationProvider response.
    pack = make_pack_from_texts([("LD1-D5", "Ayurveda Aahara labelling requires disclosure.")], authority_matrix, query="labelling")
    real_id = pack.evidence_items[0].evidence_id
    provider = _mocked_gemini_provider(response_text=f"Disclosure is required. [[CITE:{real_id}]]")
    service = ApplicationService(generation_provider=provider, evidence_pack_builder=lambda q: pack)

    request = ApplicationQueryRequest(
        schema_version=APPLICATION_SCHEMA_VERSION, request_id="ld1-ok-1", query="Ayurveda Aahara labelling",
        requested_language=None, jurisdiction="INDIA", formulation_description=None, source_language=None,
    )
    result = service.query(request)

    assert result.grounding_status == "GROUNDED"
    assert real_id in result.cited_evidence_ids


def test_invalid_provider_object_type_still_rejected_with_real_wiring_present(monkeypatch):
    # Category-9-equivalent (docs P4 finding, unchanged): the isinstance
    # gate in ApplicationService.query lives in application/service.py,
    # completely independent of LD-1's new environment-driven wiring -
    # confirmed here so LD-1 cannot be read as having weakened it.
    monkeypatch.delenv("GENERATION_PROVIDER", raising=False)
    service = ApplicationService(generation_provider="not-a-provider")
    request = ApplicationQueryRequest(
        schema_version=APPLICATION_SCHEMA_VERSION, request_id="ld1-invalid-type", query="Ayurveda Aahara",
        requested_language=None, jurisdiction=None, formulation_description=None, source_language=None,
    )
    with pytest.raises(TypeError):
        service.query(request)
