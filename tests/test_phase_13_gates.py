"""
Phase 13 tests: each of the nine ordered hard gates individually
(docs/PHASE_13_CONFIDENCE_SAFETY_ABSTENTION.md Section H). Hard gates
must override any soft/engineering signal - proven directly by
constructing a "high quality" GroundedResponse and confirming an earlier
gate still blocks it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _safety_fixtures import (
    make_empty_pack,
    make_grounded_response,
    make_known_classification,
    make_known_jurisdiction,
)

from generation.generator import generate_grounded_response
from generation.providers import FakeGenerationProvider
from safety.evaluator import evaluate_safety

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def _strong_grounded_response(authority_matrix, input_id):
    # Two independent, cleanly-valid citations - the "highest quality"
    # soft signal this policy can produce (STRONG band).
    pack, gr = make_grounded_response(
        authority_matrix, [(f"{input_id}-D1", "Trademark content."), (f"{input_id}-D2", "Patent content.")], f"{input_id}-q",
        cite_real=False,
    )
    ids = [e.evidence_id for e in pack.evidence_items]
    provider = FakeGenerationProvider(response_text=f"[[CITE:{ids[0]}]] [[CITE:{ids[1]}]]")
    gr = generate_grounded_response(f"{input_id}-q", pack, provider)
    assert gr.grounding_status == "GROUNDED"
    return gr


# G1 - CLASSIFICATION_AMBIGUOUS
def test_g1_classification_ambiguous_overrides_strong_signal(authority_matrix):
    from _safety_fixtures import make_classification

    ambiguous_cls = make_classification("G1", raw_query="how can i protect this and what compliance requirement applies in India")
    assert ambiguous_cls.classification_state == "AMBIGUOUS"
    gr = _strong_grounded_response(authority_matrix, "G1")
    decision = evaluate_safety("G1D", classification_result=ambiguous_cls, jurisdiction_decision=make_known_jurisdiction(), grounded_response=gr)
    assert decision.safety_status == "ESCALATE"
    assert decision.reason_code == "CLASSIFICATION_AMBIGUOUS"
    assert decision.hard_gate_results[0] == "G1:FIRED"


# G2 - CLASSIFICATION_UNRESOLVED
def test_g2_classification_unresolved_overrides_strong_signal(authority_matrix):
    from _safety_fixtures import make_classification

    unresolved_cls = make_classification("G2", raw_query="")
    assert unresolved_cls.classification_state == "UNKNOWN"
    gr = _strong_grounded_response(authority_matrix, "G2")
    decision = evaluate_safety("G2D", classification_result=unresolved_cls, jurisdiction_decision=make_known_jurisdiction(), grounded_response=gr)
    assert decision.safety_status == "ABSTAIN"
    assert decision.reason_code == "CLASSIFICATION_UNRESOLVED"


def test_g2_fires_when_classification_missing_entirely(authority_matrix):
    gr = _strong_grounded_response(authority_matrix, "G2B")
    decision = evaluate_safety("G2BD", jurisdiction_decision=make_known_jurisdiction(), grounded_response=gr)
    assert decision.safety_status == "ABSTAIN"
    assert decision.reason_code == "CLASSIFICATION_UNRESOLVED"


# G3 - JURISDICTION_AMBIGUOUS
def test_g3_jurisdiction_ambiguous_overrides_strong_signal(authority_matrix):
    from jurisdiction.firewall import resolve_jurisdiction

    cls = make_known_classification()
    ambiguous_jur = resolve_jurisdiction("G3", classification_result=cls, explicit_jurisdiction="INTERNATIONAL")
    assert ambiguous_jur.state == "AMBIGUOUS"
    gr = _strong_grounded_response(authority_matrix, "G3")
    decision = evaluate_safety("G3D", classification_result=cls, jurisdiction_decision=ambiguous_jur, grounded_response=gr)
    assert decision.safety_status == "ESCALATE"
    assert decision.reason_code == "JURISDICTION_AMBIGUOUS"


# G4 - JURISDICTION_UNRESOLVED
def test_g4_jurisdiction_unresolved_overrides_strong_signal(authority_matrix):
    from jurisdiction.firewall import resolve_jurisdiction

    unresolved_jur = resolve_jurisdiction("G4")
    assert unresolved_jur.state == "UNKNOWN"
    gr = _strong_grounded_response(authority_matrix, "G4")
    decision = evaluate_safety("G4D", classification_result=make_known_classification(), jurisdiction_decision=unresolved_jur, grounded_response=gr)
    assert decision.safety_status == "ABSTAIN"
    assert decision.reason_code == "JURISDICTION_UNRESOLVED"


def test_g4_fires_when_jurisdiction_missing_entirely(authority_matrix):
    gr = _strong_grounded_response(authority_matrix, "G4B")
    decision = evaluate_safety("G4BD", classification_result=make_known_classification(), grounded_response=gr)
    assert decision.safety_status == "ABSTAIN"
    assert decision.reason_code == "JURISDICTION_UNRESOLVED"


# G5 - MISSING_GROUNDED_RESPONSE
def test_g5_missing_grounded_response():
    decision = evaluate_safety("G5D", classification_result=make_known_classification(), jurisdiction_decision=make_known_jurisdiction())
    assert decision.safety_status == "ABSTAIN"
    assert decision.reason_code == "MISSING_GROUNDED_RESPONSE"


# G6 - GENERATION_FAILED
def test_g6_generation_failed(authority_matrix):
    pack, _ = make_grounded_response(authority_matrix, [("G6-D1", "Content.")], "G6-q")
    provider = FakeGenerationProvider(fail_with="simulated outage")
    gr = generate_grounded_response("G6-q", pack, provider)
    decision = evaluate_safety("G6D", classification_result=make_known_classification(), jurisdiction_decision=make_known_jurisdiction(), grounded_response=gr)
    assert decision.safety_status == "ABSTAIN"
    assert decision.reason_code == "GENERATION_FAILED"


# G7 - GENERATION_ABSTAINED
def test_g7_generation_abstained_no_evidence():
    empty_pack = make_empty_pack()
    provider = FakeGenerationProvider(response_text="anything")
    gr = generate_grounded_response("q", empty_pack, provider)
    assert gr.grounding_status == "ABSTAINED"
    decision = evaluate_safety("G7D", classification_result=make_known_classification(), jurisdiction_decision=make_known_jurisdiction(), grounded_response=gr)
    assert decision.safety_status == "ABSTAIN"
    assert decision.reason_code == "GENERATION_ABSTAINED"


def test_g7_generation_abstained_no_valid_citations(authority_matrix):
    pack, _ = make_grounded_response(authority_matrix, [("G7B-D1", "Content.")], "G7B-q")
    provider = FakeGenerationProvider(response_text="[[CITE:fabricated-nonexistent-id]]")
    gr = generate_grounded_response("G7B-q", pack, provider)
    assert gr.grounding_status == "ABSTAINED"
    decision = evaluate_safety("G7BD", classification_result=make_known_classification(), jurisdiction_decision=make_known_jurisdiction(), grounded_response=gr)
    assert decision.safety_status == "ABSTAIN"
    assert decision.reason_code == "GENERATION_ABSTAINED"


# G8 - NO_VALID_CITATIONS (Phase 13's own stricter policy)
def test_g8_no_valid_citations_when_phase_10_allowed_uncited_grounded(authority_matrix):
    from generation.models import GenerationConfig

    pack, _ = make_grounded_response(authority_matrix, [("G8-D1", "Content.")], "G8-q")
    provider = FakeGenerationProvider(response_text="An uncited but permitted answer.")
    gr = generate_grounded_response("G8-q", pack, provider, config=GenerationConfig(require_citations=False))
    assert gr.grounding_status == "GROUNDED"
    assert gr.cited_evidence_ids == []
    decision = evaluate_safety("G8D", classification_result=make_known_classification(), jurisdiction_decision=make_known_jurisdiction(), grounded_response=gr)
    assert decision.safety_status == "ABSTAIN"
    assert decision.reason_code == "NO_VALID_CITATIONS"


def test_g8_can_be_disabled_via_policy_config(authority_matrix):
    from generation.models import GenerationConfig

    from safety.models import SafetyPolicyConfig

    pack, _ = make_grounded_response(authority_matrix, [("G8B-D1", "Content.")], "G8B-q")
    provider = FakeGenerationProvider(response_text="An uncited but permitted answer.")
    gr = generate_grounded_response("G8B-q", pack, provider, config=GenerationConfig(require_citations=False))
    decision = evaluate_safety(
        "G8BD", classification_result=make_known_classification(), jurisdiction_decision=make_known_jurisdiction(),
        grounded_response=gr, config=SafetyPolicyConfig(require_at_least_one_valid_citation=False),
    )
    assert decision.safety_status == "SAFE_TO_PRESENT"


# G9 - DEFAULT_SAFE
def test_g9_default_safe_reachable(authority_matrix):
    gr = _strong_grounded_response(authority_matrix, "G9")
    decision = evaluate_safety("G9D", classification_result=make_known_classification(), jurisdiction_decision=make_known_jurisdiction(), grounded_response=gr)
    assert decision.safety_status == "SAFE_TO_PRESENT"
    assert decision.hard_gate_results[-1] == "G9:FIRED"
    assert decision.engineering_signal_band == "STRONG"


def test_all_nine_gates_pass_records_full_gate_log(authority_matrix):
    gr = _strong_grounded_response(authority_matrix, "GLOG")
    decision = evaluate_safety("GLOGD", classification_result=make_known_classification(), jurisdiction_decision=make_known_jurisdiction(), grounded_response=gr)
    assert decision.hard_gate_results == [
        "G1:PASS", "G2:PASS", "G3:PASS", "G4:PASS", "G5:PASS", "G6:PASS", "G7:PASS", "G8:PASS", "G9:FIRED",
    ]
