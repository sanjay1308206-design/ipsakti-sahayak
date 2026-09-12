"""
Phase 14 tests: deterministic behavior (docs/PHASE_14_MULTILINGUAL_DELIVERY.md
Section Y). Identical inputs must produce identical MultilingualDeliveryResult,
identical result_id, and byte-identical JSON - no randomness, no timestamps,
no dependence on call order.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _multilingual_fixtures import make_context, make_safe_grounded_response

from multilingual.delivery import deliver_response
from multilingual.preservation import build_input_context, canonicalize_query, detect_script
from multilingual.providers import FakeTranslationProvider
from multilingual.serialize import delivery_result_to_json

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def test_repeated_delivery_is_identical(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("DET1-D1", "Content.")], "DET1-q")
    ctx = make_context("DET1", "query", requested_language="hi")
    provider = FakeTranslationProvider(response_text="translated")
    results = [
        deliver_response(ctx, grounded_response=gr, safety_decision=safety, translation_provider=provider)
        for _ in range(10)
    ]
    assert all(r == results[0] for r in results)


def test_repeated_delivery_result_id_is_identical(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("DET2-D1", "Content.")], "DET2-q")
    ctx = make_context("DET2", "query", requested_language="hi")
    provider = FakeTranslationProvider(response_text="translated")
    ids = {
        deliver_response(ctx, grounded_response=gr, safety_decision=safety, translation_provider=provider).result_id
        for _ in range(10)
    }
    assert len(ids) == 1


def test_repeated_delivery_json_is_byte_identical(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("DET3-D1", "Content.")], "DET3-q")
    ctx = make_context("DET3", "query", requested_language="hi")
    provider = FakeTranslationProvider(response_text="translated")
    jsons = {
        delivery_result_to_json(deliver_response(ctx, grounded_response=gr, safety_decision=safety, translation_provider=provider))
        for _ in range(10)
    }
    assert len(jsons) == 1


def test_result_id_differs_for_different_input_ids(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("DET4-D1", "Content.")], "DET4-q")
    ctx_a = make_context("DET4A", "query", requested_language="hi")
    ctx_b = make_context("DET4B", "query", requested_language="hi")
    provider = FakeTranslationProvider(response_text="translated")
    r1 = deliver_response(ctx_a, grounded_response=gr, safety_decision=safety, translation_provider=provider)
    r2 = deliver_response(ctx_b, grounded_response=gr, safety_decision=safety, translation_provider=provider)
    assert r1.result_id != r2.result_id


def test_result_id_differs_for_different_translated_text(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("DET5-D1", "Content.")], "DET5-q")
    ctx = make_context("DET5", "query", requested_language="hi")
    r1 = deliver_response(ctx, grounded_response=gr, safety_decision=safety, translation_provider=FakeTranslationProvider(response_text="A"))
    r2 = deliver_response(ctx, grounded_response=gr, safety_decision=safety, translation_provider=FakeTranslationProvider(response_text="B"))
    assert r1.result_id != r2.result_id


def test_result_id_differs_for_different_delivery_status(authority_matrix):
    pack, gr, safety = make_safe_grounded_response(authority_matrix, [("DET6-D1", "Content.")], "DET6-q")
    ctx_supported = make_context("DET6", "query", requested_language="hi")
    ctx_unsupported = make_context("DET6", "query", requested_language="fr")
    r1 = deliver_response(ctx_supported, grounded_response=gr, safety_decision=safety)  # TRANSLATION_FAILED (no provider)
    r2 = deliver_response(ctx_unsupported, grounded_response=gr, safety_decision=safety)  # UNSUPPORTED_LANGUAGE
    assert r1.result_id != r2.result_id
    assert r1.delivery_status != r2.delivery_status


def test_detect_script_is_deterministic():
    text = "Ayurveda आयुर्वेद மருந்து"
    assert {detect_script(text) for _ in range(20)} == {"MIXED"}


def test_canonicalize_query_is_deterministic():
    text = "é"
    assert {canonicalize_query(text) for _ in range(20)} == {"é"}


def test_build_input_context_is_deterministic_apart_from_identity_fields():
    contexts = [build_input_context("SAME-ID", "query text", requested_language="hi") for _ in range(10)]
    assert all(c == contexts[0] for c in contexts)
