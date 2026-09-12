"""
Phase 17 tests: the ApplicationService orchestrator, tested WITHOUT any
HTTP server (docs/PHASE_17_BACKEND_PRODUCTIZATION.md Section AD,
"TESTABILITY"). Uses only fake/synthetic providers - no network, no GPU,
no API key anywhere in this file.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _citation_fixtures import make_pack_from_texts

from application.config import ApplicationConfig
from application.models import ApplicationQueryRequest, APPLICATION_SCHEMA_VERSION, InvalidQueryError
from application.service import ApplicationService, GenerationProviderNotConfiguredError, compute_request_id
from generation.providers import FakeGenerationProvider
from multilingual.providers import FakeTranslationProvider

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def _request(query: str, **kwargs) -> ApplicationQueryRequest:
    request_id = compute_request_id(query, kwargs.get("requested_language"), kwargs.get("jurisdiction"), kwargs.get("formulation_description"), kwargs.get("source_language"))
    return ApplicationQueryRequest(schema_version=APPLICATION_SCHEMA_VERSION, request_id=request_id, query=query, **kwargs)


def test_query_without_generation_provider_raises_explicit_error():
    service = ApplicationService()
    with pytest.raises(GenerationProviderNotConfiguredError):
        service.query(_request("Tell me about Ministry of Ayush policy in India."))


def test_query_with_empty_corpus_abstains_honestly():
    service = ApplicationService(generation_provider=FakeGenerationProvider(response_text="uncited answer"))
    result = service.query(_request("Tell me about Ministry of Ayush policy in India."))
    assert result.grounding_status == "ABSTAINED"
    assert result.safety_status == "ABSTAIN"
    assert result.delivery_status == "UPSTREAM_BLOCKED"
    assert result.review is not None


def test_query_with_real_evidence_pack_reaches_safe_to_present(authority_matrix):
    pack = make_pack_from_texts([("APP1-D1", "Ayush policy compliance content.")], authority_matrix, query="ayush policy")
    real_id = pack.evidence_items[0].evidence_id
    service = ApplicationService(
        generation_provider=FakeGenerationProvider(response_text=f"Policy details. [[CITE:{real_id}]]"),
        evidence_pack_builder=lambda query: pack,
    )
    result = service.query(_request("Tell me about Ministry of Ayush policy in India."))
    assert result.grounding_status == "GROUNDED"
    assert result.safety_status == "SAFE_TO_PRESENT"
    assert result.delivery_status == "DELIVERED"
    assert result.cited_evidence_ids == [real_id]
    assert result.review is None


def test_query_rejects_empty_query():
    service = ApplicationService(generation_provider=FakeGenerationProvider(response_text="x"))
    with pytest.raises(InvalidQueryError):
        service.query(_request("   "))


def test_query_rejects_oversized_query():
    service = ApplicationService(generation_provider=FakeGenerationProvider(response_text="x"), config=ApplicationConfig(max_query_length=10))
    with pytest.raises(InvalidQueryError):
        service.query(_request("this query is definitely too long for the configured limit"))


def test_query_rejects_oversized_formulation_description():
    service = ApplicationService(generation_provider=FakeGenerationProvider(response_text="x"), config=ApplicationConfig(max_formulation_description_length=10))
    with pytest.raises(InvalidQueryError):
        service.query(_request("short query", formulation_description="this description is far too long"))


def test_query_rejects_wrong_request_type():
    service = ApplicationService(generation_provider=FakeGenerationProvider(response_text="x"))
    with pytest.raises(TypeError):
        service.query("not a request")


def test_query_rejects_wrong_evidence_pack_builder_return_type():
    service = ApplicationService(generation_provider=FakeGenerationProvider(response_text="x"), evidence_pack_builder=lambda query: "not a pack")
    with pytest.raises(TypeError):
        service.query(_request("query"))


def test_jurisdiction_is_delegated_never_reimplemented():
    service = ApplicationService(generation_provider=FakeGenerationProvider(response_text="x"))
    result = service.query(_request("Tell me about Ministry of Ayush policy in India.", jurisdiction="INDIA"))
    assert result.jurisdiction.state == "KNOWN"
    assert result.jurisdiction.normalized_jurisdiction == "INDIA"


def test_unspecified_jurisdiction_fails_closed():
    service = ApplicationService(generation_provider=FakeGenerationProvider(response_text="x"))
    result = service.query(_request("query", jurisdiction="UNSPECIFIED"))
    assert result.jurisdiction.state == "UNKNOWN"


def test_malformed_jurisdiction_input_fails_closed_not_rejected():
    service = ApplicationService(generation_provider=FakeGenerationProvider(response_text="x"))
    result = service.query(_request("query", jurisdiction="ATLANTIS"))
    assert result.jurisdiction.state == "UNKNOWN"


def test_translation_provider_is_used_when_configured(authority_matrix):
    pack = make_pack_from_texts([("APP2-D1", "Ayush policy compliance content.")], authority_matrix, query="ayush policy")
    real_id = pack.evidence_items[0].evidence_id
    service = ApplicationService(
        generation_provider=FakeGenerationProvider(response_text=f"Details. [[CITE:{real_id}]]"),
        translation_provider=FakeTranslationProvider(response_text="[HI] translated"),
        evidence_pack_builder=lambda query: pack,
    )
    result = service.query(_request("Tell me about Ministry of Ayush policy in India.", requested_language="hi"))
    assert result.delivery_status == "DELIVERED"
    assert result.answer_text == "[HI] translated"
    assert result.translation_applied is True


def test_no_translation_provider_and_language_requested_fails_explicitly(authority_matrix):
    pack = make_pack_from_texts([("APP3-D1", "Ayush policy compliance content.")], authority_matrix, query="ayush policy")
    real_id = pack.evidence_items[0].evidence_id
    service = ApplicationService(generation_provider=FakeGenerationProvider(response_text=f"Details. [[CITE:{real_id}]]"), evidence_pack_builder=lambda query: pack)
    result = service.query(_request("Tell me about Ministry of Ayush policy in India.", requested_language="hi"))
    assert result.delivery_status == "TRANSLATION_FAILED"
    assert result.answer_text is None
