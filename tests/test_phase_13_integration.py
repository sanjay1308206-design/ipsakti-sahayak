"""
Phase 13 tests: integration with Phase 9/10/11/12's exact reused
semantics (docs/PHASE_13_CONFIDENCE_SAFETY_ABSTENTION.md Sections N, O,
P, Q). Proves Phase 13 reuses, never reimplements, each upstream phase's
own decision.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _safety_fixtures import make_classification, make_grounded_response, make_jurisdiction, make_known_classification

from generation.generator import generate_grounded_response
from generation.providers import FakeGenerationProvider
from jurisdiction.firewall import resolve_jurisdiction
from safety.evaluator import evaluate_safety

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Phase 11 integration
# ---------------------------------------------------------------------------


def test_needs_evidence_classification_proceeds_to_grounding_check(authority_matrix):
    # NEEDS_EVIDENCE means "classification itself is fine, only evidence is
    # outstanding" - it must NOT be treated the same as UNKNOWN; Phase 13
    # lets the actual grounding result (not the classification state alone)
    # decide.
    cls = make_classification(
        "NE1", raw_query="What category does my Ayurveda Aahara product fall under in India under FSSAI rules?"
    )
    assert cls.classification_state == "NEEDS_EVIDENCE"
    jur = resolve_jurisdiction("NE1J", classification_result=cls)
    pack, gr = make_grounded_response(authority_matrix, [("NE1-D1", "Ayurveda Aahara content.")], "NE1-q")
    decision = evaluate_safety("NE1D", classification_result=cls, jurisdiction_decision=jur, grounded_response=gr)
    assert decision.safety_status == "SAFE_TO_PRESENT"


def test_classification_requires_escalation_flag_reused_verbatim():
    cls = make_classification("PI1", raw_query="how can i protect this and what compliance requirement applies in India")
    assert cls.requires_escalation is True
    decision = evaluate_safety("PI1D", classification_result=cls)
    assert decision.safety_status == "ESCALATE"
    assert decision.escalation_required is True


# ---------------------------------------------------------------------------
# Phase 12 integration
# ---------------------------------------------------------------------------


def test_jurisdiction_blocked_state_cannot_be_overridden(authority_matrix):
    # A jurisdiction that resolves to UNKNOWN (fail-closed, zero permitted
    # corpora) must never become SAFE_TO_PRESENT regardless of how good
    # the grounded response looks.
    jur = make_jurisdiction("JB1")
    assert jur.state == "UNKNOWN"
    assert jur.allowed_jurisdictions == frozenset()
    pack, gr = make_grounded_response(authority_matrix, [("JB1-D1", "Content.")], "JB1-q")
    decision = evaluate_safety("JB1D", classification_result=make_known_classification(), jurisdiction_decision=jur, grounded_response=gr)
    assert decision.safety_status == "ABSTAIN"


def test_jurisdiction_requires_escalation_flag_reused_verbatim():
    cls = make_classification("JE1", raw_query="What category applies in India under FSSAI?")
    jur = resolve_jurisdiction("JE1J", classification_result=cls, explicit_jurisdiction="INTERNATIONAL")
    assert jur.requires_escalation is True
    decision = evaluate_safety("JE1D", classification_result=cls, jurisdiction_decision=jur)
    assert decision.escalation_required is True


# ---------------------------------------------------------------------------
# Phase 10 integration
# ---------------------------------------------------------------------------


def test_grounded_status_reused_verbatim_never_recomputed(authority_matrix):
    pack, gr = make_grounded_response(authority_matrix, [("G10-D1", "Content.")], "G10-q")
    assert gr.grounding_status == "GROUNDED"
    decision = evaluate_safety("G10D", classification_result=make_known_classification(), jurisdiction_decision=make_jurisdiction("G10J", explicit_jurisdiction="INDIA"), grounded_response=gr)
    assert decision.input_status_summary["grounding_status"] == "GROUNDED"


def test_generation_failure_reason_surfaced_in_explanation(authority_matrix):
    pack, _ = make_grounded_response(authority_matrix, [("GF1-D1", "Content.")], "GF1-q")
    provider = FakeGenerationProvider(fail_with="a specific simulated failure reason")
    gr = generate_grounded_response("GF1-q", pack, provider)
    decision = evaluate_safety("GF1D", classification_result=make_known_classification(), jurisdiction_decision=make_jurisdiction("GF1J", explicit_jurisdiction="INDIA"), grounded_response=gr)
    assert "a specific simulated failure reason" in decision.explanation


# ---------------------------------------------------------------------------
# Phase 9 integration (via GroundedResponse.citation_validation_summary)
# ---------------------------------------------------------------------------


def test_citation_coverage_metrics_reused_verbatim_never_recomputed(authority_matrix):
    pack, gr = make_grounded_response(authority_matrix, [("C9-D1", "Content.")], "C9-q")
    decision = evaluate_safety("C9D", classification_result=make_known_classification(), jurisdiction_decision=make_jurisdiction("C9J", explicit_jurisdiction="INDIA"), grounded_response=gr)
    assert decision.input_status_summary["unique_valid_evidence_id_count"] == gr.citation_validation_summary.unique_valid_evidence_id_count
    assert decision.input_status_summary["citation_integrity_validation_rate"] == gr.citation_validation_summary.citation_integrity_validation_rate


def test_invalid_citation_attempts_alongside_a_valid_one_do_not_force_abstention(authority_matrix):
    # Phase 13's documented policy: an invalid/unresolved citation ATTEMPT
    # that Phase 9/10 already excluded does not, by itself, force
    # abstention as long as at least one real citation survives - it only
    # affects the (informational) engineering signal band.
    pack, _ = make_grounded_response(authority_matrix, [("IC1-D1", "Content.")], "IC1-q", cite_real=False)
    real_id = pack.evidence_items[0].evidence_id
    provider = FakeGenerationProvider(response_text=f"[[CITE:{real_id}]] [[CITE:fabricated-fake-id]]")
    gr = generate_grounded_response("IC1-q", pack, provider)
    assert gr.grounding_status == "GROUNDED"
    assert gr.citation_validation_summary.unresolved_count == 1
    decision = evaluate_safety("IC1D", classification_result=make_known_classification(), jurisdiction_decision=make_jurisdiction("IC1J", explicit_jurisdiction="INDIA"), grounded_response=gr)
    assert decision.safety_status == "SAFE_TO_PRESENT"
    assert decision.engineering_signal_band in {"MODERATE", "WEAK"}  # penalized informationally, not gated
