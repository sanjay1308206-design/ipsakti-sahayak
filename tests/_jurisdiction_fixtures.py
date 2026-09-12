"""
Phase 12 test-support module: convenience constructors for synthetic
Evidence-shaped objects and classification results, for use by
tests/test_phase_12_*.py.

SYNTHETIC TEST FIXTURE GENERATOR ONLY. Not a test module itself (no test_
prefix) - pytest will not collect it.
"""

from __future__ import annotations

from dataclasses import dataclass

from classification.classifier import classify
from classification.models import ClassificationInput

__all__ = ["FakeEvidence", "make_evidence", "make_classification_input", "classify_query"]


@dataclass(frozen=True)
class FakeEvidence:
    """
    Minimal Evidence-shaped object exposing exactly the attributes
    src/jurisdiction/filtering.py requires (`evidence_id`, `jurisdiction`).
    Deliberately NOT the real evidence.models.Evidence (which requires a
    full, real Phase 3/4/8 pipeline to construct) - filtering.py only
    ever reads these two attributes by duck typing, so a minimal fixture
    is honest and sufficient for Phase 12's own tests. Real end-to-end
    integration with a genuine Evidence object is covered separately in
    tests/test_phase_12_regression.py.
    """

    evidence_id: str
    jurisdiction: object  # deliberately untyped - security/adversarial tests construct malformed values


def make_evidence(evidence_id: str, jurisdiction) -> FakeEvidence:
    return FakeEvidence(evidence_id=evidence_id, jurisdiction=jurisdiction)


def make_classification_input(input_id: str, raw_query: str = "", formulation_description=None, evidence_state=None) -> ClassificationInput:
    return ClassificationInput(
        input_id=input_id, raw_query=raw_query, formulation_description=formulation_description, evidence_state=evidence_state
    )


def classify_query(input_id: str, raw_query: str, **kwargs):
    return classify(make_classification_input(input_id, raw_query=raw_query, **kwargs))
