"""
Phase 15 test-support module: convenience builders producing real Phase
8-14 output objects for use by tests/test_phase_15_*.py, reusing
tests/_multilingual_fixtures.py (and, transitively, _safety_fixtures.py /
_generation_fixtures.py / _citation_fixtures.py) directly rather than
duplicating any construction logic.

SYNTHETIC TEST FIXTURE GENERATOR ONLY. Not a test module itself (no test_
prefix) - pytest will not collect it.
"""

from __future__ import annotations

from _citation_fixtures import fabricated_evidence_id, make_reference
from _multilingual_fixtures import (
    make_classification,
    make_context,
    make_empty_pack,
    make_grounded_response,
    make_jurisdiction,
    make_known_classification,
    make_known_jurisdiction,
    make_safe_grounded_response,
)

from citation.validator import validate_citations
from classification.classifier import classify
from classification.models import ClassificationInput
from generation.generator import generate_grounded_response
from generation.providers import FakeGenerationProvider
from jurisdiction.firewall import resolve_jurisdiction
from multilingual.delivery import deliver_response
from multilingual.preservation import build_input_context
from safety.evaluator import evaluate_safety

__all__ = [
    "make_classification",
    "make_context",
    "make_empty_pack",
    "make_grounded_response",
    "make_jurisdiction",
    "make_known_classification",
    "make_known_jurisdiction",
    "make_safe_grounded_response",
    "make_ambiguous_classification",
    "make_unresolved_classification",
    "make_needs_evidence_classification",
    "make_conflicting_track_classification",
    "make_ambiguous_jurisdiction",
    "make_unresolved_jurisdiction",
    "make_abstained_grounded_response",
    "make_failed_citation_results",
    "make_valid_citation_results",
    "make_unsupported_language_delivery_result",
]


def make_ambiguous_classification(input_id: str = "AMBIG-CLS"):
    """classification_state == AMBIGUOUS via R5 (AMBIGUOUS_USER_INTENT)."""
    return classify(ClassificationInput(input_id=input_id, raw_query="how can i protect this and what compliance requirement applies in India"))


def make_unresolved_classification(input_id: str = "UNRESOLVED-CLS"):
    """classification_state == UNKNOWN via an empty raw_query (no signal at all)."""
    return classify(ClassificationInput(input_id=input_id, raw_query=""))


def make_needs_evidence_classification(input_id: str = "NEEDS-EV-CLS"):
    """classification_state == NEEDS_EVIDENCE - a fully-resolved classification still awaiting evidence."""
    return classify(
        ClassificationInput(
            input_id=input_id,
            raw_query=(
                "what is the compliance requirement for my new ayurvedic drug in India and what license "
                "from CDSCO or state authority do I need"
            ),
        )
    )


def make_conflicting_track_classification(input_id: str = "CONFLICT-CLS"):
    """formulation_classification.regulatory_track == CONFLICTING (R8/R4 - two regulatory-track keywords)."""
    return classify(
        ClassificationInput(
            input_id=input_id,
            raw_query="general information",
            formulation_description="This is a classical ayurvedic drug but also a cosmetic product",
        )
    )


def make_ambiguous_jurisdiction(input_id: str = "AMBIG-JUR"):
    """state == AMBIGUOUS - an explicit override conflicting with the classification-derived signal."""
    cls = classify(ClassificationInput(input_id=input_id, raw_query="tell me about Ministry of Ayush policy in international markets"))
    return resolve_jurisdiction(input_id, classification_result=cls, explicit_jurisdiction="INDIA")


def make_unresolved_jurisdiction(input_id: str = "UNRESOLVED-JUR"):
    """state == UNKNOWN - no signal supplied at all."""
    return resolve_jurisdiction(input_id)


def make_abstained_grounded_response(query: str = "no evidence available"):
    """A real GroundedResponse with grounding_status == ABSTAINED (empty EvidencePack)."""
    empty_pack = make_empty_pack(query)
    return empty_pack, generate_grounded_response(query, empty_pack, FakeGenerationProvider(response_text="x"))


def make_failed_citation_results(authority_matrix, texts_and_doc_ids, query: str):
    """A real EvidencePack plus a batch of CitationValidationResult containing at least one non-VALID entry."""
    from _citation_fixtures import make_pack_from_texts

    pack = make_pack_from_texts(texts_and_doc_ids, authority_matrix, query=query)
    references = [make_reference(fabricated_evidence_id())]
    return pack, validate_citations(references, pack)


def make_valid_citation_results(authority_matrix, texts_and_doc_ids, query: str):
    """A real EvidencePack plus a batch of CitationValidationResult where every entry is VALID."""
    from _citation_fixtures import make_pack_from_texts

    pack = make_pack_from_texts(texts_and_doc_ids, authority_matrix, query=query)
    references = [make_reference(item.evidence_id) for item in pack.evidence_items]
    return pack, validate_citations(references, pack)


def make_unsupported_language_delivery_result(authority_matrix, texts_and_doc_ids, query: str, input_id: str = "ML-UNSUPPORTED"):
    """A real MultilingualDeliveryResult with delivery_status == UNSUPPORTED_LANGUAGE."""
    pack, gr, safety = make_safe_grounded_response(authority_matrix, texts_and_doc_ids, query, input_id=input_id)
    ctx = build_input_context(input_id, query, requested_language="fr")
    result = deliver_response(ctx, grounded_response=gr, safety_decision=safety)
    return pack, gr, safety, result
