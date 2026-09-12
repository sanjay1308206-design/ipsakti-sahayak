"""
Phase 13 test-support module: convenience builders that produce real
Phase 10/11/12 output objects (ClassificationResult, JurisdictionDecision,
GroundedResponse), reusing tests/_generation_fixtures.py directly, for
use by tests/test_phase_13_*.py.

SYNTHETIC TEST FIXTURE GENERATOR ONLY. Not a test module itself (no test_
prefix) - pytest will not collect it.
"""

from __future__ import annotations

from _generation_fixtures import citing_provider, make_pack_from_texts

from classification.classifier import classify
from classification.models import ClassificationInput
from evidence.builder import build_evidence_pack
from generation.generator import generate_grounded_response
from generation.providers import FakeGenerationProvider
from jurisdiction.firewall import resolve_jurisdiction

__all__ = [
    "citing_provider",
    "make_pack_from_texts",
    "make_known_classification",
    "make_classification",
    "make_known_jurisdiction",
    "make_jurisdiction",
    "make_grounded_response",
    "make_empty_pack",
]


def make_classification(input_id: str, raw_query: str = "", **kwargs):
    return classify(ClassificationInput(input_id=input_id, raw_query=raw_query, **kwargs))


def make_known_classification(input_id: str = "CLS", authority_matrix=None):
    """A classification_state == KNOWN, non-evidence-requiring result - no jurisdiction ambiguity risk."""
    return make_classification(input_id, raw_query="Tell me about Ministry of Ayush policy in India.")


def make_jurisdiction(input_id: str, **kwargs):
    return resolve_jurisdiction(input_id, **kwargs)


def make_known_jurisdiction(input_id: str = "JUR"):
    return resolve_jurisdiction(input_id, explicit_jurisdiction="INDIA")


def make_empty_pack(query: str = "no evidence"):
    return build_evidence_pack([], query)


def make_grounded_response(authority_matrix, texts_and_doc_ids, query: str, cite_real: bool = True, **provider_kwargs):
    """Builds a real EvidencePack via _generation_fixtures.make_pack_from_texts, then a real GroundedResponse citing its first evidence item (or per provider_kwargs)."""
    pack = make_pack_from_texts(texts_and_doc_ids, authority_matrix, query=query)
    if provider_kwargs:
        provider = FakeGenerationProvider(**provider_kwargs)
    elif cite_real:
        real_id = pack.evidence_items[0].evidence_id
        provider = citing_provider(real_id)
    else:
        provider = FakeGenerationProvider(response_text="Uncited answer.")
    return pack, generate_grounded_response(query, pack, provider)
