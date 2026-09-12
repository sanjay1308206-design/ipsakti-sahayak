"""
Phase 11 test-support module: convenience constructors for
classification.models.ClassificationInput, for use by
tests/test_phase_11_*.py.

SYNTHETIC TEST FIXTURE GENERATOR ONLY. Not a test module itself (no test_
prefix) - pytest will not collect it.
"""

from __future__ import annotations

from classification.models import ClassificationInput

__all__ = ["make_input"]


def make_input(input_id: str, raw_query: str = "", formulation_description=None, evidence_state=None) -> ClassificationInput:
    return ClassificationInput(
        input_id=input_id,
        raw_query=raw_query,
        formulation_description=formulation_description,
        evidence_state=evidence_state,
    )
