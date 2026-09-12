"""
Phase 14 tests: each of the eight ordered delivery gates individually
(docs/PHASE_14_MULTILINGUAL_DELIVERY.md Section H). Proves safety/
grounding gates are checked BEFORE any translation attempt, and that
translation can never rescue an abstained/escalated/failed upstream
result.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _multilingual_fixtures import make_context, make_empty_pack, make_known_classification, make_known_jurisdiction, make_safe_grounded_response

from generation.generator import generate_grounded_response
from generation.providers import FakeGenerationProvider
from multilingual.delivery import deliver_response
from multilingual.providers import FakeTranslationProvider
from safety.evaluator import evaluate_safety

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# D2 - SAFETY_NOT_SAFE_TO_PRESENT
def test_d2_missing_safety_decision_blocks(authority_matrix):
    pack, gr, _ = make_safe_grounded_response(authority_matrix, [("D2-D1", "Content.")], "D2-q")
    ctx = make_context("D2", "query")
    result = deliver_response(ctx, grounded_response=gr)
    assert result.delivery_status == "UPSTREAM_BLOCKED"
    assert result.reason_code == "SAFETY_NOT_SAFE_TO_PRESENT"


def test_d2_abstain_safety_blocks(authority_matrix):
    pack, gr, _ = make_safe_grounded_response(authority_matrix, [("D2B-D1", "Content.")], "D2B-q")
    abstain_safety = evaluate_safety("D2B-S")
    ctx = make_context("D2B", "query")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=abstain_safety)
    assert result.delivery_status == "UPSTREAM_BLOCKED"
    assert result.reason_code == "SAFETY_NOT_SAFE_TO_PRESENT"


def test_d2_escalate_safety_blocks():
    from _multilingual_fixtures import make_classification

    cls = make_classification("D2C", raw_query="how can i protect this and what compliance requirement applies in India")
    escalate_safety = evaluate_safety("D2C-S", classification_result=cls)
    assert escalate_safety.safety_status == "ESCALATE"
    ctx = make_context("D2C", "query")
    result = deliver_response(ctx, safety_decision=escalate_safety)
    assert result.delivery_status == "UPSTREAM_BLOCKED"


# D3 - GROUNDING_NOT_GROUNDED. Note: Phase 13's own G5/G7 gates already
# set safety_status=ABSTAIN whenever the SAME grounded_response fed into
# evaluate_safety is missing/abstained/failed - so to test D3 in true
# isolation (grounding blocks even when safety, evaluated over a
# DIFFERENT valid response, is genuinely SAFE_TO_PRESENT), the
# safety_decision and the grounded_response given to deliver_response
# must be decoupled, exactly like test_phase_13's own gate-isolation
# tests do for classification vs jurisdiction.
def test_d3_missing_grounded_response_blocks(authority_matrix):
    _, _, safety = make_safe_grounded_response(authority_matrix, [("D3-D1", "Content.")], "D3-q")
    assert safety.safety_status == "SAFE_TO_PRESENT"
    ctx = make_context("D3", "query")
    result = deliver_response(ctx, safety_decision=safety)  # no grounded_response supplied here
    assert result.delivery_status == "UPSTREAM_BLOCKED"
    assert result.reason_code == "GROUNDING_NOT_GROUNDED"


def test_d3_abstained_grounding_blocks(authority_matrix):
    _, _, safety = make_safe_grounded_response(authority_matrix, [("D3B-D1", "Content.")], "D3B-q")
    assert safety.safety_status == "SAFE_TO_PRESENT"
    empty_pack = make_empty_pack()
    abstained_gr = generate_grounded_response("q", empty_pack, FakeGenerationProvider(response_text="x"))
    assert abstained_gr.grounding_status == "ABSTAINED"
    ctx = make_context("D3B", "query")
    result = deliver_response(ctx, grounded_response=abstained_gr, safety_decision=safety)
    assert result.delivery_status == "UPSTREAM_BLOCKED"
    assert result.reason_code == "GROUNDING_NOT_GROUNDED"


# D4 - UNSUPPORTED_LANGUAGE_REQUESTED
def test_d4_unsupported_language(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("D4-D1", "Content.")], "D4-q")
    ctx = make_context("D4", "query", requested_language="fr")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety)
    assert result.delivery_status == "UNSUPPORTED_LANGUAGE"
    assert result.reason_code == "UNSUPPORTED_LANGUAGE_REQUESTED"
    assert result.answer_text is None


# D5 - LANGUAGE_UNSPECIFIED_NO_TRANSLATION_NEEDED
def test_d5_unspecified_language_delivers_unchanged(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("D5-D1", "Content.")], "D5-q")
    ctx = make_context("D5", "query")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety)
    assert result.delivery_status == "DELIVERED"
    assert result.reason_code == "LANGUAGE_UNSPECIFIED_NO_TRANSLATION_NEEDED"
    assert result.answer_text == gr.answer_text
    assert result.translation_applied is False


# D6 - SOURCE_MATCHES_REQUESTED_NO_TRANSLATION_NEEDED
def test_d6_source_matches_requested(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("D6-D1", "Content.")], "D6-q")
    ctx = make_context("D6", "query", requested_language="en")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety, source_language="en")
    assert result.delivery_status == "DELIVERED"
    assert result.reason_code == "SOURCE_MATCHES_REQUESTED_NO_TRANSLATION_NEEDED"
    assert result.translation_applied is False


# D7 - MISSING_TRANSLATION_PROVIDER
def test_d7_missing_translation_provider(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("D7-D1", "Content.")], "D7-q")
    ctx = make_context("D7", "query", requested_language="hi")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety)
    assert result.delivery_status == "TRANSLATION_FAILED"
    assert result.reason_code == "MISSING_TRANSLATION_PROVIDER"


# D8 - TRANSLATION_PROVIDER_FAILED
def test_d8_translation_provider_reports_failure(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("D8-D1", "Content.")], "D8-q")
    ctx = make_context("D8", "query", requested_language="hi")
    provider = FakeTranslationProvider(fail_with="simulated outage")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety, translation_provider=provider)
    assert result.delivery_status == "TRANSLATION_FAILED"
    assert result.reason_code == "TRANSLATION_PROVIDER_FAILED"
    assert "simulated outage" in result.explanation


def test_d8_translation_provider_raises_exception(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("D8B-D1", "Content.")], "D8B-q")
    ctx = make_context("D8B", "query", requested_language="hi")

    class ExplodingProvider(FakeTranslationProvider):
        def translate(self, text, source_language, target_language):
            raise RuntimeError("boom")

    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety, translation_provider=ExplodingProvider(response_text="x"))
    assert result.delivery_status == "TRANSLATION_FAILED"
    assert "boom" in result.explanation


def test_d8_translation_provider_returns_wrong_type(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("D8C-D1", "Content.")], "D8C-q")
    ctx = make_context("D8C", "query", requested_language="hi")

    class BadProvider(FakeTranslationProvider):
        def translate(self, text, source_language, target_language):
            return "not a TranslationOutput"

    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety, translation_provider=BadProvider(response_text="x"))
    assert result.delivery_status == "TRANSLATION_FAILED"


# D9 - TRANSLATION_SUCCEEDED
def test_d9_translation_succeeds(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("D9-D1", "Content.")], "D9-q")
    ctx = make_context("D9", "query", requested_language="hi")
    provider = FakeTranslationProvider(response_text="[HINDI TRANSLATION]")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety, translation_provider=provider)
    assert result.delivery_status == "DELIVERED"
    assert result.reason_code == "TRANSLATION_SUCCEEDED"
    assert result.answer_text == "[HINDI TRANSLATION]"
    assert result.translation_applied is True
    assert result.answer_language == "hi"


# ---------------------------------------------------------------------------
# Type discipline
# ---------------------------------------------------------------------------


def test_deliver_response_rejects_wrong_context_type():
    with pytest.raises(TypeError):
        deliver_response("not a context")


def test_deliver_response_rejects_wrong_grounded_response_type():
    ctx = make_context("TD1", "query")
    with pytest.raises(TypeError):
        deliver_response(ctx, grounded_response="not a GroundedResponse")


def test_deliver_response_rejects_wrong_safety_decision_type():
    ctx = make_context("TD2", "query")
    with pytest.raises(TypeError):
        deliver_response(ctx, safety_decision="not a SafetyDecision")


def test_deliver_response_rejects_wrong_provider_type():
    ctx = make_context("TD3", "query")
    with pytest.raises(TypeError):
        deliver_response(ctx, translation_provider="not a provider")


def test_deliver_response_rejects_wrong_config_type():
    ctx = make_context("TD4", "query")
    with pytest.raises(TypeError):
        deliver_response(ctx, config="not a config")
