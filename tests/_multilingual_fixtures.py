"""
Phase 14 test-support module: convenience builders producing real Phase
10/13 output objects (GroundedResponse, SafetyDecision), reusing
tests/_safety_fixtures.py directly, for use by tests/test_phase_14_*.py.

SYNTHETIC TEST FIXTURE GENERATOR ONLY. Not a test module itself (no test_
prefix) - pytest will not collect it.
"""

from __future__ import annotations

from _safety_fixtures import (
    make_classification,
    make_empty_pack,
    make_grounded_response,
    make_jurisdiction,
    make_known_classification,
    make_known_jurisdiction,
)

from generation.generator import generate_grounded_response
from generation.providers import FakeGenerationProvider
from multilingual.delivery import deliver_response
from multilingual.preservation import build_input_context
from multilingual.providers import FakeTranslationProvider
from safety.evaluator import evaluate_safety

__all__ = [
    "make_classification",
    "make_empty_pack",
    "make_grounded_response",
    "make_jurisdiction",
    "make_known_classification",
    "make_known_jurisdiction",
    "make_safe_grounded_response",
    "make_context",
]


def make_safe_grounded_response(authority_matrix, texts_and_doc_ids, query: str, input_id: str = "SAFE"):
    """Builds a real GROUNDED GroundedResponse plus a real SAFE_TO_PRESENT SafetyDecision over it."""
    pack, gr = make_grounded_response(authority_matrix, texts_and_doc_ids, query)
    cls = make_known_classification()
    jur = make_known_jurisdiction()
    safety = evaluate_safety(input_id, classification_result=cls, jurisdiction_decision=jur, grounded_response=gr)
    return pack, gr, safety


def make_context(input_id: str, original_query: str = "", requested_language=None):
    return build_input_context(input_id, original_query, requested_language=requested_language)
