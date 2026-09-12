"""
Phase 13 tests: deterministic decisions
(docs/PHASE_13_CONFIDENCE_SAFETY_ABSTENTION.md Section Y). Identical
validated inputs and policy configuration must produce identical
decision, decision identity, and serialized JSON.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _safety_fixtures import make_grounded_response, make_known_classification, make_known_jurisdiction

from safety.evaluator import evaluate_safety
from safety.serialize import safety_decision_to_json

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def test_repeated_evaluation_is_identical(authority_matrix):
    cls = make_known_classification()
    jur = make_known_jurisdiction()
    pack, gr = make_grounded_response(authority_matrix, [("DET1-D1", "Content.")], "DET1-q")
    decisions = [evaluate_safety("DET1", classification_result=cls, jurisdiction_decision=jur, grounded_response=gr) for _ in range(10)]
    assert all(d == decisions[0] for d in decisions)


def test_repeated_evaluation_decision_id_is_identical(authority_matrix):
    cls = make_known_classification()
    jur = make_known_jurisdiction()
    pack, gr = make_grounded_response(authority_matrix, [("DET2-D1", "Content.")], "DET2-q")
    ids = {evaluate_safety("DET2", classification_result=cls, jurisdiction_decision=jur, grounded_response=gr).decision_id for _ in range(10)}
    assert len(ids) == 1


def test_repeated_evaluation_json_is_byte_identical(authority_matrix):
    cls = make_known_classification()
    jur = make_known_jurisdiction()
    pack, gr = make_grounded_response(authority_matrix, [("DET3-D1", "Content.")], "DET3-q")
    jsons = {safety_decision_to_json(evaluate_safety("DET3", classification_result=cls, jurisdiction_decision=jur, grounded_response=gr)) for _ in range(10)}
    assert len(jsons) == 1


def test_decision_id_differs_for_different_input_ids(authority_matrix):
    cls = make_known_classification()
    jur = make_known_jurisdiction()
    pack, gr = make_grounded_response(authority_matrix, [("DET4-D1", "Content.")], "DET4-q")
    d1 = evaluate_safety("DET4A", classification_result=cls, jurisdiction_decision=jur, grounded_response=gr)
    d2 = evaluate_safety("DET4B", classification_result=cls, jurisdiction_decision=jur, grounded_response=gr)
    assert d1.decision_id != d2.decision_id
    assert d1.safety_status == d2.safety_status


def test_decision_id_differs_for_different_outcomes():
    d1 = evaluate_safety("DET5")
    d2 = evaluate_safety("DET5", classification_result=make_known_classification())
    assert d1.decision_id != d2.decision_id


def test_no_evidence_abstention_is_deterministic():
    from _safety_fixtures import make_empty_pack

    from generation.generator import generate_grounded_response
    from generation.providers import FakeGenerationProvider

    empty_pack = make_empty_pack()
    provider = FakeGenerationProvider(response_text="x")
    gr = generate_grounded_response("q", empty_pack, provider)
    decisions = [
        evaluate_safety("DET6", classification_result=make_known_classification(), jurisdiction_decision=make_known_jurisdiction(), grounded_response=gr)
        for _ in range(5)
    ]
    assert all(d == decisions[0] for d in decisions)
