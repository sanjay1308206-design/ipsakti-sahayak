"""
Phase 16 tests: Phase 13 safety-gate evaluation
(docs/PHASE_16_EVALUATION_AND_RED_TEAM.md Section P). Calls the REAL
`safety.evaluator.evaluate_safety` - never a re-derived gate engine, and
never modifies `SafetyPolicyConfig`'s own [ASSUMPTION]-labeled thresholds.
Measures behavior under the CURRENT configuration only.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _safety_fixtures import (
    make_classification,
    make_empty_pack,
    make_grounded_response,
    make_jurisdiction,
    make_known_classification,
    make_known_jurisdiction,
)

from evaluation.benchmark import score_exact_match_cases
from evaluation.models import BenchmarkCase
from generation.generator import generate_grounded_response
from generation.models import GenerationConfig
from generation.providers import FakeGenerationProvider
from safety.evaluator import evaluate_safety

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def _gate_fired(decision) -> str:
    fired = [g for g in decision.hard_gate_results if g.endswith(":FIRED")]
    assert len(fired) == 1, f"expected exactly one FIRED gate, got {fired}"
    return fired[0].split(":")[0]


def test_g1_classification_ambiguous_escalates():
    cls = make_classification("G1", raw_query="how can i protect this and what compliance requirement applies in India")
    decision = evaluate_safety("G1-S", classification_result=cls)
    assert decision.safety_status == "ESCALATE"
    assert _gate_fired(decision) == "G1"


def test_g2_classification_unresolved_abstains():
    decision = evaluate_safety("G2-S")
    assert decision.safety_status == "ABSTAIN"
    assert _gate_fired(decision) == "G2"


def test_g3_jurisdiction_ambiguous_escalates():
    cls = make_known_classification()
    jur = make_jurisdiction("G3-J", classification_result=make_classification("G3", raw_query="tell me about Ministry of Ayush policy in international markets"), explicit_jurisdiction="INDIA")
    decision = evaluate_safety("G3-S", classification_result=cls, jurisdiction_decision=jur)
    assert decision.safety_status == "ESCALATE"
    assert _gate_fired(decision) == "G3"


def test_g4_jurisdiction_unresolved_abstains():
    cls = make_known_classification()
    decision = evaluate_safety("G4-S", classification_result=cls)
    assert decision.safety_status == "ABSTAIN"
    assert _gate_fired(decision) == "G4"


def test_g5_missing_grounded_response_abstains():
    cls = make_known_classification()
    jur = make_known_jurisdiction()
    decision = evaluate_safety("G5-S", classification_result=cls, jurisdiction_decision=jur)
    assert decision.safety_status == "ABSTAIN"
    assert _gate_fired(decision) == "G5"


def test_g6_generation_failed_abstains(authority_matrix):
    cls = make_known_classification()
    jur = make_known_jurisdiction()
    pack, _ = make_grounded_response(authority_matrix, [("G6-D1", "Content.")], "G6-q", cite_real=False)
    gr = generate_grounded_response("G6-q", pack, FakeGenerationProvider(fail_with="down"))
    decision = evaluate_safety("G6-S", classification_result=cls, jurisdiction_decision=jur, grounded_response=gr)
    assert decision.safety_status == "ABSTAIN"
    assert _gate_fired(decision) == "G6"


def test_g7_generation_abstained_abstains():
    cls = make_known_classification()
    jur = make_known_jurisdiction()
    empty_pack = make_empty_pack()
    gr = generate_grounded_response("q", empty_pack, FakeGenerationProvider(response_text="x"))
    decision = evaluate_safety("G7-S", classification_result=cls, jurisdiction_decision=jur, grounded_response=gr)
    assert decision.safety_status == "ABSTAIN"
    assert _gate_fired(decision) == "G7"


def test_g8_no_valid_citations_abstains(authority_matrix):
    cls = make_known_classification()
    jur = make_known_jurisdiction()
    pack, _ = make_grounded_response(authority_matrix, [("G8-D1", "Content.")], "G8-q", cite_real=False)
    gr = generate_grounded_response("G8-q", pack, FakeGenerationProvider(response_text="uncited"), config=GenerationConfig(require_citations=False))
    assert gr.grounding_status == "GROUNDED"
    assert gr.cited_evidence_ids == []
    decision = evaluate_safety("G8-S", classification_result=cls, jurisdiction_decision=jur, grounded_response=gr)
    assert decision.safety_status == "ABSTAIN"
    assert _gate_fired(decision) == "G8"


def test_g9_default_safe(authority_matrix):
    cls = make_known_classification()
    jur = make_known_jurisdiction()
    pack, gr = make_grounded_response(authority_matrix, [("G9-D1", "Content.")], "G9-q")
    decision = evaluate_safety("G9-S", classification_result=cls, jurisdiction_decision=jur, grounded_response=gr)
    assert decision.safety_status == "SAFE_TO_PRESENT"
    assert _gate_fired(decision) == "G9"


def test_all_nine_gates_are_independently_reachable(authority_matrix):
    """Structural coverage benchmark - proves every gate actually fires at least once under the CURRENT (unmodified) policy configuration."""
    fired_gates = set()
    fired_gates.add(_gate_fired(evaluate_safety("ALL-G1", classification_result=make_classification("ALL-G1-C", raw_query="how can i protect this and what compliance requirement applies in India"))))
    fired_gates.add(_gate_fired(evaluate_safety("ALL-G2")))

    cls_known = make_known_classification()
    jur_ambiguous = make_jurisdiction("ALL-G3-J", classification_result=make_classification("ALL-G3", raw_query="tell me about Ministry of Ayush policy in international markets"), explicit_jurisdiction="INDIA")
    fired_gates.add(_gate_fired(evaluate_safety("ALL-G3-S", classification_result=cls_known, jurisdiction_decision=jur_ambiguous)))
    fired_gates.add(_gate_fired(evaluate_safety("ALL-G4-S", classification_result=cls_known)))
    fired_gates.add(_gate_fired(evaluate_safety("ALL-G5-S", classification_result=cls_known, jurisdiction_decision=make_known_jurisdiction())))

    pack6, _ = make_grounded_response(authority_matrix, [("ALL-G6-D1", "Content.")], "ALL-G6-q", cite_real=False)
    gr6 = generate_grounded_response("ALL-G6-q", pack6, FakeGenerationProvider(fail_with="down"))
    fired_gates.add(_gate_fired(evaluate_safety("ALL-G6-S", classification_result=cls_known, jurisdiction_decision=make_known_jurisdiction(), grounded_response=gr6)))

    empty_pack = make_empty_pack()
    gr7 = generate_grounded_response("q", empty_pack, FakeGenerationProvider(response_text="x"))
    fired_gates.add(_gate_fired(evaluate_safety("ALL-G7-S", classification_result=cls_known, jurisdiction_decision=make_known_jurisdiction(), grounded_response=gr7)))

    pack8, _ = make_grounded_response(authority_matrix, [("ALL-G8-D1", "Content.")], "ALL-G8-q", cite_real=False)
    gr8 = generate_grounded_response("ALL-G8-q", pack8, FakeGenerationProvider(response_text="uncited"), config=GenerationConfig(require_citations=False))
    fired_gates.add(_gate_fired(evaluate_safety("ALL-G8-S", classification_result=cls_known, jurisdiction_decision=make_known_jurisdiction(), grounded_response=gr8)))

    pack9, gr9 = make_grounded_response(authority_matrix, [("ALL-G9-D1", "Content.")], "ALL-G9-q")
    fired_gates.add(_gate_fired(evaluate_safety("ALL-G9-S", classification_result=cls_known, jurisdiction_decision=make_known_jurisdiction(), grounded_response=gr9)))

    assert fired_gates == {f"G{i}" for i in range(1, 10)}


def test_safety_status_exact_match_benchmark(authority_matrix):
    pack, gr = make_grounded_response(authority_matrix, [("SB-D1", "Content.")], "SB-q")
    cases_and_match = [
        (
            BenchmarkCase(schema_version="1.0.0", case_id="SB-1", category="SAFETY_ABSTENTION", ground_truth_origin="STRUCTURAL_EXPECTATION", input_summary="known+known+grounded", expected_behavior="SAFE_TO_PRESENT", expected_safety_status="SAFE_TO_PRESENT"),
            evaluate_safety("SB-1-S", classification_result=make_known_classification(), jurisdiction_decision=make_known_jurisdiction(), grounded_response=gr).safety_status == "SAFE_TO_PRESENT",
        ),
        (
            BenchmarkCase(schema_version="1.0.0", case_id="SB-2", category="SAFETY_ABSTENTION", ground_truth_origin="STRUCTURAL_EXPECTATION", input_summary="missing everything", expected_behavior="ABSTAIN", expected_safety_status="ABSTAIN"),
            evaluate_safety("SB-2-S").safety_status == "ABSTAIN",
        ),
    ]
    report = score_exact_match_cases("SAFETY_ABSTENTION", "SAFETY_STATUS_EXACT_MATCH", cases_and_match)
    assert report.failed_case_ids == []


def test_thresholds_are_not_modified_by_this_benchmark():
    from safety.models import SafetyPolicyConfig

    default_config = SafetyPolicyConfig()
    assert default_config.strong_min_unique_citations == 2
    assert default_config.strong_min_integrity_rate == 1.0
    assert default_config.moderate_min_integrity_rate == 0.5
