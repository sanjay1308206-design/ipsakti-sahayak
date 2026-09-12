"""
Phase 16 tests: Phase 14 multilingual-preservation evaluation
(docs/PHASE_16_EVALUATION_AND_RED_TEAM.md Section Q). Calls the REAL
`multilingual.preservation`/`multilingual.delivery` - never a re-derived
translation/canonicalization engine. NO translation-quality claim is made
anywhere in this file.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _evaluation_fixtures import make_case
from _multilingual_fixtures import make_context, make_safe_grounded_response

from evaluation.benchmark import score_exact_match_cases
from multilingual.delivery import deliver_response
from multilingual.preservation import detect_script
from multilingual.providers import FakeTranslationProvider

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def test_original_query_preservation(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("ML1-D1", "Content.")], "ML1-q")
    original = "आयुर्वेद औषधि पंजीकरण"
    ctx = make_context("ML1", original, requested_language="hi")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety, translation_provider=FakeTranslationProvider(response_text="translated"))
    assert result.original_query == original


def test_canonical_query_preservation(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("ML2-D1", "Content.")], "ML2-q")
    ctx = make_context("ML2", "é")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety)
    assert result.canonical_query == "é"


def test_script_and_language_are_never_conflated():
    assert detect_script("आयुर्वेद") == "DEVANAGARI"
    assert detect_script("आयुर्वेद") != "hi"


def test_language_never_becomes_jurisdiction(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("ML3-D1", "Content.")], "ML3-q")
    ctx = make_context("ML3", "आयुर्वेद औषधि पंजीकरण", requested_language="hi")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety, translation_provider=FakeTranslationProvider(response_text="x"))
    assert not hasattr(result, "jurisdiction")


def test_translation_failure_handling(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("ML4-D1", "Content.")], "ML4-q")
    ctx = make_context("ML4", "query", requested_language="hi")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety, translation_provider=FakeTranslationProvider(fail_with="outage"))
    assert result.delivery_status == "TRANSLATION_FAILED"
    assert result.answer_text is None


def test_unsupported_language_handling(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("ML5-D1", "Content.")], "ML5-q")
    ctx = make_context("ML5", "query", requested_language="fr")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety)
    assert result.delivery_status == "UNSUPPORTED_LANGUAGE"


def test_evidence_id_and_citation_preservation_through_translation(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("ML6-D1", "Content.")], "ML6-q")
    ctx = make_context("ML6", "query", requested_language="hi")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety, translation_provider=FakeTranslationProvider(response_text="[[CITE:FAKE]] translated"))
    assert result.cited_evidence_ids == list(gr.cited_evidence_ids)


def test_grounding_and_safety_preservation_through_translation(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("ML7-D1", "Content.")], "ML7-q")
    ctx = make_context("ML7", "query", requested_language="hi")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety, translation_provider=FakeTranslationProvider(response_text="translated"))
    assert result.grounding_status == "GROUNDED"
    assert result.safety_status == "SAFE_TO_PRESENT"


def test_real_translation_quality_is_not_validated_in_this_benchmark(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("ML8-D1", "Content.")], "ML8-q")
    ctx = make_context("ML8", "query", requested_language="hi")
    provider = FakeTranslationProvider(response_text="[HI]")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety, translation_provider=provider)
    # FakeTranslationProvider's own docstring already discloses this is not
    # a real translation - the benchmark makes no quality claim about it.
    assert result.provider_name == "fake-translation-provider"


def test_multilingual_preservation_benchmark_aggregate(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("ML9-D1", "Content.")], "ML9-q")
    ctx = make_context("ML9", "query", requested_language="hi")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety, translation_provider=FakeTranslationProvider(response_text="x"))

    entries = [
        (make_case("ML9-a", "MULTILINGUAL_DELIVERY", "STRUCTURAL_EXPECTATION", "delivered", "cited_evidence_ids preserved"), result.cited_evidence_ids == list(gr.cited_evidence_ids)),
        (make_case("ML9-b", "MULTILINGUAL_DELIVERY", "STRUCTURAL_EXPECTATION", "delivered", "grounding preserved"), result.grounding_status == gr.grounding_status),
        (make_case("ML9-c", "MULTILINGUAL_DELIVERY", "STRUCTURAL_EXPECTATION", "delivered", "safety preserved"), result.safety_status == safety.safety_status),
    ]
    report = score_exact_match_cases("MULTILINGUAL_DELIVERY", "MULTILINGUAL_PRESERVATION_RATE", entries)
    assert report.failed_case_ids == []
    assert report.results[0].value == 1.0
