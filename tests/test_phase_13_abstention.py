"""
Phase 13 tests: abstention vs escalation behavior
(docs/PHASE_13_CONFIDENCE_SAFETY_ABSTENTION.md Sections L, M). Abstention
means "insufficient conditions to answer safely"; escalation means "an
existing project policy flags this for review" - never conflated, and
Phase 13 never implements the human workflow itself.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _safety_fixtures import make_classification, make_empty_pack, make_jurisdiction, make_known_classification

from generation.generator import generate_grounded_response
from generation.providers import FakeGenerationProvider
from safety.evaluator import evaluate_safety

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def test_abstain_never_claims_safe_presentation():
    empty_pack = make_empty_pack()
    provider = FakeGenerationProvider(response_text="x")
    gr = generate_grounded_response("q", empty_pack, provider)
    decision = evaluate_safety("AB1", classification_result=make_known_classification(), jurisdiction_decision=make_jurisdiction("AB1J", explicit_jurisdiction="INDIA"), grounded_response=gr)
    assert decision.safety_status == "ABSTAIN"
    assert decision.abstained is True
    assert decision.escalation_required is False


def test_escalate_never_represented_as_safe_final_answer():
    cls = make_classification("AB2", raw_query="how can i protect this and what compliance requirement applies in India")
    decision = evaluate_safety("AB2D", classification_result=cls)
    assert decision.safety_status == "ESCALATE"
    assert decision.safety_status != "SAFE_TO_PRESENT"
    assert decision.escalation_required is True
    assert decision.abstained is False


def test_abstain_and_escalate_are_mutually_exclusive():
    decision = evaluate_safety("AB3")
    assert not (decision.abstained and decision.escalation_required)


def test_phase_13_does_not_implement_human_workflow():
    # Structural proof: no queue/reviewer/assignment/notification concept
    # exists anywhere in src/safety/ - escalation_required is a boolean
    # flag only.
    import dataclasses

    from safety.models import SafetyDecision

    field_names = {f.name for f in dataclasses.fields(SafetyDecision)}
    forbidden = {"reviewer_id", "queue_id", "assigned_to", "notification_sent", "case_id"}
    assert field_names.isdisjoint(forbidden)


def test_no_human_workflow_terms_in_safety_source():
    forbidden_terms = ("reviewer_queue", "assign_case", "send_notification", "human_review_queue")
    for py_file in (REPO_ROOT / "src" / "safety").glob("*.py"):
        text = py_file.read_text(encoding="utf-8").lower()
        for term in forbidden_terms:
            assert term not in text


def test_deterministic_abstention_across_repeated_evaluation():
    empty_pack = make_empty_pack()
    provider = FakeGenerationProvider(response_text="x")
    gr = generate_grounded_response("q", empty_pack, provider)
    decisions = [
        evaluate_safety("AB4", classification_result=make_known_classification(), jurisdiction_decision=make_jurisdiction("AB4J", explicit_jurisdiction="INDIA"), grounded_response=gr)
        for _ in range(5)
    ]
    assert all(d == decisions[0] for d in decisions)


def test_deterministic_escalation_across_repeated_evaluation():
    def build():
        cls = make_classification("AB5", raw_query="how can i protect this and what compliance requirement applies in India")
        return evaluate_safety("AB5D", classification_result=cls)

    decisions = [build() for _ in range(5)]
    assert all(d == decisions[0] for d in decisions)
