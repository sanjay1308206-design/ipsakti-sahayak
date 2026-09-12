"""
Phase 10 tests: core model invariants and end-to-end grounded-generation
behavior (docs/PHASE_10_GROUNDED_GENERATION.md Sections D, E, N, O).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
import yaml
from _generation_fixtures import citing_provider, make_pack_from_texts

from citation.metrics import compute_citation_coverage
from generation.generator import generate_grounded_response
from generation.models import (
    ABSTENTION_REASONS,
    GROUNDING_STATUSES,
    GenerationConfig,
    GenerationOutput,
    GroundedResponse,
)
from generation.providers import FakeGenerationProvider

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# End-to-end grounding outcomes
# ---------------------------------------------------------------------------


def test_grounded_when_provider_cites_real_evidence(authority_matrix):
    pack = make_pack_from_texts([("D-GEN-1", "Trademark registration requires an application.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    response = generate_grounded_response("How to register a trademark?", pack, citing_provider(real_id))
    assert response.grounding_status == "GROUNDED"
    assert response.abstained is False
    assert response.cited_evidence_ids == [real_id]
    assert response.answer_text is not None


def test_abstains_when_evidence_pack_is_empty(authority_matrix):
    from evidence.builder import build_evidence_pack

    pack = build_evidence_pack([], "no results query")
    response = generate_grounded_response("q", pack, citing_provider("irrelevant"))
    assert response.grounding_status == "ABSTAINED"
    assert response.abstained is True
    assert response.abstention_reason == "NO_EVIDENCE_AVAILABLE"
    assert response.answer_text is None
    assert response.cited_evidence_ids == []


def test_abstains_when_provider_cites_only_fabricated_ids(authority_matrix):
    pack = make_pack_from_texts([("D-GEN-2", "Patent filing content.")], authority_matrix)
    provider = citing_provider("fabricated-evidence-id-does-not-exist")
    response = generate_grounded_response("q", pack, provider)
    assert response.grounding_status == "ABSTAINED"
    assert response.abstention_reason == "NO_VALID_CITATIONS_PRODUCED"
    assert response.answer_text is None


def test_generation_failed_when_provider_reports_failure(authority_matrix):
    pack = make_pack_from_texts([("D-GEN-3", "Content.")], authority_matrix)
    provider = FakeGenerationProvider(fail_with="simulated provider outage")
    response = generate_grounded_response("q", pack, provider)
    assert response.grounding_status == "GENERATION_FAILED"
    assert response.failure_reason == "simulated provider outage"
    assert response.answer_text is None
    assert response.abstained is False


def test_generation_failed_when_provider_raises(authority_matrix):
    pack = make_pack_from_texts([("D-GEN-4", "Content.")], authority_matrix)

    from generation.providers import GenerationProvider

    class RealExplodingProvider(GenerationProvider):
        @property
        def provider_name(self):
            return "exploding"

        @property
        def model_identifier(self):
            return "exploding-v1"

        def generate(self, prompt):
            raise RuntimeError("boom")

    response = generate_grounded_response("q", pack, RealExplodingProvider())
    assert response.grounding_status == "GENERATION_FAILED"
    assert "boom" in response.failure_reason


def test_generation_failed_when_provider_returns_wrong_type(authority_matrix):
    from generation.providers import GenerationProvider

    class BadProvider(GenerationProvider):
        @property
        def provider_name(self):
            return "bad"

        @property
        def model_identifier(self):
            return "bad-v1"

        def generate(self, prompt):
            return "not a GenerationOutput"

    pack = make_pack_from_texts([("D-GEN-5", "Content.")], authority_matrix)
    response = generate_grounded_response("q", pack, BadProvider())
    assert response.grounding_status == "GENERATION_FAILED"


def test_require_citations_false_allows_uncited_grounded_response(authority_matrix):
    pack = make_pack_from_texts([("D-GEN-6", "Content.")], authority_matrix)
    provider = FakeGenerationProvider(response_text="An uncited but permitted answer.")
    response = generate_grounded_response("q", pack, provider, config=GenerationConfig(require_citations=False))
    assert response.grounding_status == "GROUNDED"
    assert response.cited_evidence_ids == []


def test_pack_that_fails_phase_9_validity_causes_abstention(authority_matrix):
    pack = make_pack_from_texts([("D-GEN-7", "Content.")], authority_matrix)
    forged = dataclasses.replace(pack, pack_id="0" * 64)
    response = generate_grounded_response("q", forged, citing_provider(pack.evidence_items[0].evidence_id))
    assert response.grounding_status == "ABSTAINED"
    assert response.abstention_reason == "NO_EVIDENCE_AVAILABLE"


def test_synthetic_flag_survives_onto_response(authority_matrix):
    pack = make_pack_from_texts([("D-GEN-8", "Content.")], authority_matrix)
    assert pack.evidence_items[0].synthetic is True  # fixtures are always synthetic
    real_id = pack.evidence_items[0].evidence_id
    response = generate_grounded_response("q", pack, citing_provider(real_id))
    assert response.synthetic is True


def test_evidence_pack_id_traceability(authority_matrix):
    pack = make_pack_from_texts([("D-GEN-9", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    response = generate_grounded_response("q", pack, citing_provider(real_id))
    assert response.evidence_pack_id == pack.pack_id


def test_citation_validation_summary_is_reused_phase_9_metrics(authority_matrix):
    pack = make_pack_from_texts([("D-GEN-10", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    response = generate_grounded_response("q", pack, citing_provider(real_id))
    assert response.citation_validation_summary.valid_count == 1
    assert response.citation_validation_summary.citation_integrity_validation_rate == 1.0


# ---------------------------------------------------------------------------
# Type discipline
# ---------------------------------------------------------------------------


def test_generate_rejects_non_string_query(authority_matrix):
    pack = make_pack_from_texts([("D-GEN-11", "Content.")], authority_matrix)
    with pytest.raises(TypeError):
        generate_grounded_response(12345, pack, citing_provider("x"))


def test_generate_rejects_non_pack():
    with pytest.raises(TypeError):
        generate_grounded_response("q", "not a pack", citing_provider("x"))


def test_generate_rejects_non_provider(authority_matrix):
    pack = make_pack_from_texts([("D-GEN-12", "Content.")], authority_matrix)
    with pytest.raises(TypeError):
        generate_grounded_response("q", pack, "not a provider")


def test_generate_rejects_none_provider(authority_matrix):
    pack = make_pack_from_texts([("D-GEN-13", "Content.")], authority_matrix)
    with pytest.raises(TypeError):
        generate_grounded_response("q", pack, None)


def test_generate_rejects_wrong_config_type(authority_matrix):
    pack = make_pack_from_texts([("D-GEN-14", "Content.")], authority_matrix)
    with pytest.raises(TypeError):
        generate_grounded_response("q", pack, citing_provider("x"), config="not a config")


# ---------------------------------------------------------------------------
# GroundedResponse invariants
# ---------------------------------------------------------------------------


def _summary():
    return compute_citation_coverage([])


def test_status_vocabulary_closed():
    assert GROUNDING_STATUSES == {"GROUNDED", "ABSTAINED", "GENERATION_FAILED"}


def test_abstention_reason_vocabulary_closed():
    assert ABSTENTION_REASONS == {"NO_EVIDENCE_AVAILABLE", "NO_VALID_CITATIONS_PRODUCED"}


def test_grounded_response_rejects_answer_text_when_not_grounded():
    with pytest.raises(ValueError):
        GroundedResponse(
            schema_version="1.0.0", response_id="a" * 64, query="q", canonical_query=None,
            answer_text="should not be here", cited_evidence_ids=[], citation_validation_summary=_summary(),
            grounding_status="ABSTAINED", abstained=True, abstention_reason="NO_EVIDENCE_AVAILABLE",
            failure_reason=None, provider_name="p", model_identifier="m", generation_metadata={},
            synthetic=False, evidence_pack_id="pack1",
        )


def test_grounded_response_requires_answer_text_when_grounded():
    with pytest.raises(ValueError):
        GroundedResponse(
            schema_version="1.0.0", response_id="a" * 64, query="q", canonical_query=None,
            answer_text=None, cited_evidence_ids=[], citation_validation_summary=_summary(),
            grounding_status="GROUNDED", abstained=False, abstention_reason=None,
            failure_reason=None, provider_name="p", model_identifier="m", generation_metadata={},
            synthetic=False, evidence_pack_id="pack1",
        )


def test_grounded_response_rejects_mismatched_abstained_flag():
    with pytest.raises(ValueError):
        GroundedResponse(
            schema_version="1.0.0", response_id="a" * 64, query="q", canonical_query=None,
            answer_text=None, cited_evidence_ids=[], citation_validation_summary=_summary(),
            grounding_status="ABSTAINED", abstained=False, abstention_reason="NO_EVIDENCE_AVAILABLE",
            failure_reason=None, provider_name="p", model_identifier="m", generation_metadata={},
            synthetic=False, evidence_pack_id="pack1",
        )


def test_grounded_response_rejects_cited_ids_when_not_grounded():
    with pytest.raises(ValueError):
        GroundedResponse(
            schema_version="1.0.0", response_id="a" * 64, query="q", canonical_query=None,
            answer_text=None, cited_evidence_ids=["x" * 64], citation_validation_summary=_summary(),
            grounding_status="ABSTAINED", abstained=True, abstention_reason="NO_EVIDENCE_AVAILABLE",
            failure_reason=None, provider_name="p", model_identifier="m", generation_metadata={},
            synthetic=False, evidence_pack_id="pack1",
        )


def test_grounded_response_rejects_duplicate_cited_ids():
    with pytest.raises(ValueError):
        GroundedResponse(
            schema_version="1.0.0", response_id="a" * 64, query="q", canonical_query=None,
            answer_text="answer", cited_evidence_ids=["x" * 64, "x" * 64], citation_validation_summary=_summary(),
            grounding_status="GROUNDED", abstained=False, abstention_reason=None,
            failure_reason=None, provider_name="p", model_identifier="m", generation_metadata={},
            synthetic=False, evidence_pack_id="pack1",
        )


def test_generation_output_rejects_credential_shaped_metadata_key():
    with pytest.raises(ValueError):
        GenerationOutput(
            raw_text="text", provider_name="p", model_identifier="m", success=True, failure_reason=None,
            metadata={"api_key": "should-not-be-here"},
        )


def test_generation_output_requires_failure_reason_when_not_success():
    with pytest.raises(ValueError):
        GenerationOutput(raw_text="", provider_name="p", model_identifier="m", success=False, failure_reason=None, metadata={})
