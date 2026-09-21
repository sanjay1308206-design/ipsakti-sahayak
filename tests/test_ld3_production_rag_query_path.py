"""
LD-3 (Production RAG Query Path) integration tests.

Proves the REAL production query architecture - ApplicationService wired
with LD-2's real `sf05_evidence_pack_builder` and LD-1's real
`GeminiGenerationProvider` - works end-to-end, entirely locally. Every
test here mocks the Gemini network call at the outermost possible
boundary (`provider._client.models.generate_content`) - no test requires
a real API key or makes a real network call (LD-3 Step H explicit
requirement). Where the real, admitted SF-05 asset is required, tests
skip (not fail) if it is not present in this checkout, matching every
other phase's own convention.

Nothing here duplicates EvidencePack construction, citation validation,
jurisdiction resolution, classification, or grounded-generation logic -
every test drives the real, unmodified `application.service.ApplicationService`
and/or the real, unmodified Phase 8-14 modules directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from api.app import create_app  # noqa: E402
from api.dependencies import (  # noqa: E402
    get_application_service,
    get_backend_config,
    get_generation_provider,
)
from application.models import APPLICATION_SCHEMA_VERSION, ApplicationQueryRequest  # noqa: E402
from application.service import ApplicationService  # noqa: E402
from citation.validator import check_evidence_pack_validity  # noqa: E402
from evidence.models import Evidence, EvidencePack, RetrievalMetadata, VersionInfo  # noqa: E402
from generation.gemini_provider import GeminiGenerationProvider  # noqa: E402
from generation.generator import generate_grounded_response  # noqa: E402
from generation.providers import FakeGenerationProvider  # noqa: E402
from jurisdiction.filtering import filter_evidence  # noqa: E402
from multilingual.providers import FakeTranslationProvider  # noqa: E402
from retrieval.production_corpus import MANIFEST_PATH, RAW_PDF_PATH, sf05_evidence_pack_builder  # noqa: E402

DOCUMENT_ID = "SF05-FSSAI-AYURVEDA-AAHARA-REGULATIONS-2022"
REAL_QUERY = "आयुर्वेद आहार"
# DISCLOSED FINDING (see LD-3 implementation report "Query Architecture"):
# the real, unmodified Phase 11 classifier (src/classification/rules.py)
# is keyword-based and English-only. A Devanagari-script query like
# REAL_QUERY above retrieves real evidence correctly (Phase 5 BM25 has no
# such limitation) but classification_state resolves to UNKNOWN for it
# (R2/R6 in the decision tree never match a Hindi keyword), so
# ApplicationService.query's own Phase 13 safety gate G2 always abstains
# for it - never reaching SAFE_TO_PRESENT/DELIVERED, regardless of how
# good the retrieval/citation is. This is a pre-existing property of
# Phase 11, unrelated to and unmodified by LD-3. DELIVERABLE_QUERY below
# is an English query, verified against the REAL classifier and REAL
# BM25 index, that resolves to classification_state=KNOWN AND retrieves
# real SF-05 evidence - used wherever a test needs to observe the full
# DELIVERED/SAFE_TO_PRESENT path, not just Phase 10 grounding.
DELIVERABLE_QUERY = "Ayurveda Aahara food safety requirements in India"


def _skip_if_not_admitted():
    if not RAW_PDF_PATH.is_file() or not MANIFEST_PATH.is_file():
        pytest.skip("real SF-05 document has not been admitted in this checkout")


@pytest.fixture()
def real_asset():
    _skip_if_not_admitted()


@pytest.fixture(autouse=True)
def _clear_dependency_caches():
    get_backend_config.cache_clear()
    get_generation_provider.cache_clear()
    yield
    get_backend_config.cache_clear()
    get_generation_provider.cache_clear()


class _FakeGeminiResponse:
    def __init__(self, text):
        self.text = text


def _mocked_gemini(response_text=None, raise_exc=None, api_key="placeholder-key") -> GeminiGenerationProvider:
    """A real GeminiGenerationProvider with its network call mocked at the outermost SDK boundary - no test in this file touches the network."""
    provider = GeminiGenerationProvider(api_key=api_key)
    captured = {}

    def fake_generate_content(**kwargs):
        captured["prompt"] = kwargs.get("contents")
        if raise_exc is not None:
            raise raise_exc
        return _FakeGeminiResponse(response_text)

    provider._client.models.generate_content = fake_generate_content
    provider._captured = captured
    return provider


# ---------------------------------------------------------------------------
# 1-4. Construction, real retrieval reached, EvidencePack contents/flow
# ---------------------------------------------------------------------------


def test_application_service_constructs_with_real_evidence_builder_and_gemini_provider(real_asset):
    provider = _mocked_gemini(response_text="ok")
    service = ApplicationService(generation_provider=provider, evidence_pack_builder=sf05_evidence_pack_builder)
    assert service.generation_provider is provider
    assert service.evidence_pack_builder is sf05_evidence_pack_builder


def test_real_query_reaches_real_retrieval_and_evidence_pack_contains_real_sf05_evidence(real_asset):
    pack = sf05_evidence_pack_builder(REAL_QUERY)
    assert len(pack.evidence_items) > 0
    for evidence in pack.evidence_items:
        assert evidence.document_id == DOCUMENT_ID
        assert evidence.source_family_id == "SF-05"
        assert evidence.jurisdiction == "INDIA"
        assert evidence.synthetic is False


def test_evidence_pack_reaches_the_generation_layer_and_gemini_receives_the_grounded_prompt(real_asset):
    pack = sf05_evidence_pack_builder(REAL_QUERY)
    real_id = pack.evidence_items[0].evidence_id
    provider = _mocked_gemini(response_text=f"Per the regulation. [[CITE:{real_id}]]")

    generate_grounded_response(REAL_QUERY, pack, provider)

    prompt = provider._captured["prompt"]
    assert isinstance(prompt, str)
    assert real_id in prompt  # ALLOWED EVIDENCE IDS / evidence block
    assert pack.evidence_items[0].evidence_text[:30] in prompt  # real evidence text actually present in the prompt
    assert "[[CITE:<evidence_id>]]" in prompt  # citation-marker instruction is present


# ---------------------------------------------------------------------------
# 5-9. Citation acceptance / rejection over real evidence
# ---------------------------------------------------------------------------


def test_generated_response_citing_a_real_valid_evidence_id_is_accepted(real_asset):
    pack = sf05_evidence_pack_builder(REAL_QUERY)
    real_id = pack.evidence_items[0].evidence_id
    provider = _mocked_gemini(response_text=f"Per the regulation. [[CITE:{real_id}]]")

    response = generate_grounded_response(REAL_QUERY, pack, provider)

    assert response.grounding_status == "GROUNDED"
    assert real_id in response.cited_evidence_ids
    assert response.citation_validation_summary.valid_count >= 1


def test_malformed_citation_id_is_rejected(real_asset):
    pack = sf05_evidence_pack_builder(REAL_QUERY)
    assert check_evidence_pack_validity(pack) is None
    provider = _mocked_gemini(response_text="See it. [[CITE:not-a-real-evidence-id]]")

    response = generate_grounded_response(REAL_QUERY, pack, provider)

    assert response.grounding_status == "ABSTAINED"
    assert response.cited_evidence_ids == []


def test_fabricated_citation_over_real_evidence_is_rejected(real_asset):
    pack = sf05_evidence_pack_builder(REAL_QUERY)
    real_id = pack.evidence_items[0].evidence_id
    fabricated_id = real_id[:-4] + "0000"  # plausible-looking but not a real evidence_id
    provider = _mocked_gemini(response_text=f"See it. [[CITE:{fabricated_id}]]")

    response = generate_grounded_response(REAL_QUERY, pack, provider)

    assert response.grounding_status == "ABSTAINED"
    assert response.abstention_reason == "NO_VALID_CITATIONS_PRODUCED"
    assert fabricated_id not in response.cited_evidence_ids


# ---------------------------------------------------------------------------
# 10-11. Empty evidence abstains; provider failure fails safely
# ---------------------------------------------------------------------------


def test_empty_retrieval_result_causes_abstention_never_a_fabricated_answer(real_asset):
    pack = sf05_evidence_pack_builder("zzz_totally_absent_nonsense_term_zzz_qqq")
    assert pack.evidence_items == []
    provider = _mocked_gemini(response_text="should never be called meaningfully")

    response = generate_grounded_response("zzz_totally_absent_nonsense_term_zzz_qqq", pack, provider)

    assert response.grounding_status == "ABSTAINED"
    assert response.abstention_reason == "NO_EVIDENCE_AVAILABLE"
    assert response.answer_text is None


def test_gemini_provider_failure_fails_safely_never_an_unsafe_answer(real_asset):
    pack = sf05_evidence_pack_builder(REAL_QUERY)
    provider = _mocked_gemini(raise_exc=RuntimeError("simulated network failure"))

    response = generate_grounded_response(REAL_QUERY, pack, provider)

    assert response.grounding_status == "GENERATION_FAILED"
    assert response.answer_text is None
    assert response.cited_evidence_ids == []


def test_gemini_provider_failure_is_never_delivered_end_to_end(real_asset):
    provider = _mocked_gemini(raise_exc=RuntimeError("simulated network failure"))
    service = ApplicationService(generation_provider=provider, evidence_pack_builder=sf05_evidence_pack_builder)
    request = ApplicationQueryRequest(
        schema_version=APPLICATION_SCHEMA_VERSION, request_id="ld3-fail-1", query=REAL_QUERY,
        requested_language=None, jurisdiction="INDIA", formulation_description=None, source_language=None,
    )
    result = service.query(request)
    assert result.delivery_status != "DELIVERED"
    assert result.answer_text is None


# ---------------------------------------------------------------------------
# 12. Jurisdiction firewall
# ---------------------------------------------------------------------------


def _fake_indian_evidence(evidence_id: str, jurisdiction: str) -> Evidence:
    return Evidence(
        evidence_id=evidence_id, evidence_schema_version="1.0.0", evidence_type="CHUNK",
        evidence_text="sample text", evidence_text_hash="0" * 64, chunk_id="chunk-1",
        document_id="D-1", source_family_id="SF-01" if jurisdiction == "INDIA" else "SF-99",
        jurisdiction=jurisdiction, content_hash="0" * 64, synthetic=True, page_numbers=[1], block_ids=["b1"],
        retrieval_metadata=RetrievalMetadata(rank=1), version_info=VersionInfo(),
        section_heading_text=None, section_heading_level=None,
    )


def test_request_level_jurisdiction_firewall_resolves_india_for_real_sf05_evidence(real_asset):
    provider = _mocked_gemini(response_text="ok")
    service = ApplicationService(generation_provider=provider, evidence_pack_builder=sf05_evidence_pack_builder)
    request = ApplicationQueryRequest(
        schema_version=APPLICATION_SCHEMA_VERSION, request_id="ld3-jur-1", query=REAL_QUERY,
        requested_language=None, jurisdiction="INDIA", formulation_description=None, source_language=None,
    )
    result = service.query(request)
    assert result.jurisdiction.normalized_jurisdiction == "INDIA"
    assert result.jurisdiction.state != "UNKNOWN"


def test_real_sf05_retrieval_never_mixes_in_a_non_india_jurisdiction(real_asset):
    pack = sf05_evidence_pack_builder(REAL_QUERY)
    assert len(pack.evidence_items) > 0
    assert {e.jurisdiction for e in pack.evidence_items} == {"INDIA"}


def test_cross_jurisdiction_evidence_filtering_capability_remains_intact_and_unmodified():
    # Step F literal requirement ("test that cross-jurisdiction evidence
    # remains blocked"). jurisdiction.filtering.filter_evidence exists,
    # is fully tested elsewhere (Phase 12's own suite, Phase 23.4
    # Category 6), and is exercised here unmodified against a
    # hand-built mixed pack - proving the capability itself is intact.
    #
    # DISCLOSED FINDING (see LD-3 implementation report "Jurisdiction
    # Integrity"): application.service.ApplicationService.query does NOT
    # currently call filter_evidence anywhere in its own orchestration -
    # this is a pre-existing fact, unchanged by LD-3 (grep-verified
    # below), not a regression LD-3 introduced. It is currently benign
    # in production because the only real corpus (SF-05) is
    # single-jurisdiction (see the test above) - there is no second,
    # non-INDIA evidence source for a real query to ever mix with.
    from classification.classifier import classify
    from classification.models import ClassificationInput
    from jurisdiction.firewall import resolve_jurisdiction

    classification = classify(ClassificationInput(input_id="jur-test-1", raw_query="Ayurveda Aahara in India", formulation_description=None))
    decision = resolve_jurisdiction("jur-test-1", classification_result=classification, explicit_jurisdiction="INDIA")
    assert decision.state == "KNOWN"
    mixed_items = [_fake_indian_evidence("EV-INDIA-1", "INDIA"), _fake_indian_evidence("EV-INTL-1", "INTERNATIONAL")]

    result = filter_evidence(decision, mixed_items)

    assert [e.evidence_id for e in result.allowed_evidence] == ["EV-INDIA-1"]
    assert result.blocked_evidence_ids == ["EV-INTL-1"]


def test_application_service_query_does_not_itself_call_filter_evidence():
    # Structural confirmation of the disclosed finding above - a
    # grep-level check so this stays honestly documented rather than
    # silently assumed either way.
    service_source = (SRC_DIR / "application" / "service.py").read_text(encoding="utf-8")
    assert "filter_evidence" not in service_source


# ---------------------------------------------------------------------------
# 13. Phase 13 safety gates remain active
# ---------------------------------------------------------------------------


def test_ambiguous_classification_still_escalates_even_with_real_evidence_and_a_valid_citation(real_asset):
    pack = sf05_evidence_pack_builder(REAL_QUERY)
    real_id = pack.evidence_items[0].evidence_id if pack.evidence_items else None
    response_text = f"Per the regulation. [[CITE:{real_id}]]" if real_id else "ok"
    provider = _mocked_gemini(response_text=response_text)

    service = ApplicationService(generation_provider=provider, evidence_pack_builder=lambda q: pack)
    request = ApplicationQueryRequest(
        schema_version=APPLICATION_SCHEMA_VERSION, request_id="ld3-ambig-1",
        query="how can i protect this and what compliance requirement applies in India",
        requested_language=None, jurisdiction=None, formulation_description=None, source_language=None,
    )
    result = service.query(request)

    # G1 (CLASSIFICATION_AMBIGUOUS) fires before grounding/citation are
    # ever consulted for the delivery decision - real, valid evidence and
    # a real, valid citation must not override a Phase 11 escalation.
    assert result.delivery_status != "DELIVERED"
    assert result.safety_status == "ESCALATE"


def test_safety_gates_deliver_a_grounded_answer_for_a_clean_real_query(real_asset):
    # Uses DELIVERABLE_QUERY (see its own comment above) - the ONE
    # genuine, fully-delivered local RAG query LD-3 set out to prove:
    # real classification (KNOWN) + real jurisdiction (INDIA) + real
    # SF-05 retrieval + a validly-cited (mocked) Gemini answer together
    # reach SAFE_TO_PRESENT/DELIVERED, not merely Phase 10 GROUNDED.
    pack = sf05_evidence_pack_builder(DELIVERABLE_QUERY)
    assert len(pack.evidence_items) > 0
    real_id = pack.evidence_items[0].evidence_id
    provider = _mocked_gemini(response_text=f"Per the regulation. [[CITE:{real_id}]]")

    service = ApplicationService(generation_provider=provider, evidence_pack_builder=lambda q: pack)
    request = ApplicationQueryRequest(
        schema_version=APPLICATION_SCHEMA_VERSION, request_id="ld3-clean-1", query=DELIVERABLE_QUERY,
        requested_language=None, jurisdiction="INDIA", formulation_description=None, source_language=None,
    )
    result = service.query(request)

    assert result.grounding_status == "GROUNDED"
    assert result.safety_status == "SAFE_TO_PRESENT"
    assert result.delivery_status == "DELIVERED"
    assert result.answer_text is not None
    assert real_id in result.cited_evidence_ids


# ---------------------------------------------------------------------------
# 14. Multilingual delivery compatibility
# ---------------------------------------------------------------------------


def test_multilingual_delivery_remains_compatible_with_real_evidence_and_gemini(real_asset):
    pack = sf05_evidence_pack_builder(DELIVERABLE_QUERY)
    assert len(pack.evidence_items) > 0
    real_id = pack.evidence_items[0].evidence_id
    provider = _mocked_gemini(response_text=f"Per the regulation. [[CITE:{real_id}]]")
    translation_provider = FakeTranslationProvider(response_text="अनुवादित उत्तर")

    service = ApplicationService(
        generation_provider=provider, translation_provider=translation_provider, evidence_pack_builder=lambda q: pack,
    )
    request = ApplicationQueryRequest(
        schema_version=APPLICATION_SCHEMA_VERSION, request_id="ld3-i18n-1", query=DELIVERABLE_QUERY,
        requested_language="hi", jurisdiction="INDIA", formulation_description=None, source_language=None,
    )
    result = service.query(request)

    assert result.grounding_status == "GROUNDED"
    assert result.delivery_status == "DELIVERED"
    assert result.answer_text is not None
    assert result.translation_applied is True


# ---------------------------------------------------------------------------
# 15. /api/v1/query using the REAL dependency graph (Step J)
# ---------------------------------------------------------------------------


def test_api_query_endpoint_works_through_the_real_dependency_graph(monkeypatch, real_asset):
    # Uses the REAL, un-overridden get_application_service - the actual
    # production dependency graph, including real SF-05 retrieval. Only
    # the outbound Gemini network call is mocked, deep inside the real
    # GeminiGenerationProvider instance the real factory constructs.
    monkeypatch.setenv("GENERATION_PROVIDER", "gemini")
    monkeypatch.setenv("GENERATION_API_KEY", "placeholder-key")

    app = create_app()
    client = TestClient(app)

    real_provider = get_generation_provider()
    assert isinstance(real_provider, GeminiGenerationProvider)

    pack = sf05_evidence_pack_builder(DELIVERABLE_QUERY)
    assert len(pack.evidence_items) > 0
    real_id = pack.evidence_items[0].evidence_id
    real_provider._client.models.generate_content = lambda **kwargs: _FakeGeminiResponse(f"Per the regulation. [[CITE:{real_id}]]")

    response = client.post("/api/v1/query", json={"query": DELIVERABLE_QUERY, "jurisdiction": "INDIA"})

    assert response.status_code == 200
    body = response.json()
    # The ONE genuine local end-to-end RAG query LD-3 exists to prove:
    # real retrieval -> real EvidencePack -> real (mocked-network) Gemini
    # -> real citation validation -> real safety gates -> DELIVERED.
    assert body["delivery_status"] == "DELIVERED"
    assert body["answer_text"] is not None
    assert body["grounding_status"] == "GROUNDED"
    assert body["safety_status"] == "SAFE_TO_PRESENT"
    assert real_id in body["cited_evidence_ids"]
    assert body["jurisdiction"]["normalized_jurisdiction"] == "INDIA"
    assert set(body.keys()) >= {
        "request_id", "delivery_status", "reason_code", "explanation", "answer_text", "grounding_status",
        "safety_status", "cited_evidence_ids", "citation_summary", "jurisdiction", "classification",
    }


def test_api_query_endpoint_still_fails_closed_when_provider_unconfigured(monkeypatch):
    monkeypatch.delenv("GENERATION_PROVIDER", raising=False)
    monkeypatch.delenv("GENERATION_API_KEY", raising=False)
    client = TestClient(create_app())

    response = client.post("/api/v1/query", json={"query": REAL_QUERY})

    assert response.status_code == 503
    assert response.json()["error_type"] == "GENERATION_PROVIDER_NOT_CONFIGURED"


def test_api_health_endpoint_stays_cheap_and_does_not_touch_the_corpus(monkeypatch):
    # /health must never perform retrieval/model calls (Phase 17's own
    # contract, unchanged by LD-3) - constructing ApplicationService via
    # the real dependency graph must not itself load the SF-05 corpus.
    monkeypatch.delenv("GENERATION_PROVIDER", raising=False)
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["generation_provider_configured"] is False
