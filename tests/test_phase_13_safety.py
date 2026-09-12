"""
Phase 13 tests: core model invariants and end-to-end safety evaluation
(docs/PHASE_13_CONFIDENCE_SAFETY_ABSTENTION.md Sections F, G, H).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
import yaml
from _safety_fixtures import make_grounded_response, make_known_classification, make_known_jurisdiction

from safety.evaluator import evaluate_safety
from safety.models import (
    ENGINEERING_SIGNAL_BANDS,
    SAFETY_REASON_CODES,
    SAFETY_STATUSES,
    SafetyDecision,
    SafetyPolicyConfig,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Vocabularies
# ---------------------------------------------------------------------------


def test_safety_statuses_closed_vocabulary():
    assert SAFETY_STATUSES == {"SAFE_TO_PRESENT", "ABSTAIN", "ESCALATE"}


def test_reason_codes_closed_vocabulary():
    assert SAFETY_REASON_CODES == {
        "CLASSIFICATION_AMBIGUOUS",
        "CLASSIFICATION_UNRESOLVED",
        "JURISDICTION_AMBIGUOUS",
        "JURISDICTION_UNRESOLVED",
        "MISSING_GROUNDED_RESPONSE",
        "GENERATION_FAILED",
        "GENERATION_ABSTAINED",
        "NO_VALID_CITATIONS",
        "SAFE_GROUNDED_RESPONSE",
    }


def test_engineering_signal_bands_closed_vocabulary():
    assert ENGINEERING_SIGNAL_BANDS == {"STRONG", "MODERATE", "WEAK", "NOT_APPLICABLE"}


# ---------------------------------------------------------------------------
# End-to-end
# ---------------------------------------------------------------------------


def test_full_safe_case(authority_matrix):
    cls = make_known_classification()
    jur = make_known_jurisdiction()
    pack, gr = make_grounded_response(authority_matrix, [("D1", "Trademark content.")], "trademark")
    decision = evaluate_safety("S1", classification_result=cls, jurisdiction_decision=jur, grounded_response=gr)
    assert decision.safety_status == "SAFE_TO_PRESENT"
    assert decision.reason_code == "SAFE_GROUNDED_RESPONSE"
    assert decision.abstained is False
    assert decision.escalation_required is False
    assert decision.engineering_signal_band != "NOT_APPLICABLE"


def test_no_inputs_at_all_aborts_safely():
    decision = evaluate_safety("S2")
    assert decision.safety_status == "ABSTAIN"
    assert decision.reason_code == "CLASSIFICATION_UNRESOLVED"


# ---------------------------------------------------------------------------
# Type discipline
# ---------------------------------------------------------------------------


def test_evaluate_safety_rejects_empty_input_id():
    with pytest.raises(ValueError):
        evaluate_safety("")


def test_evaluate_safety_rejects_wrong_classification_type():
    with pytest.raises(TypeError):
        evaluate_safety("S3", classification_result="not a ClassificationResult")


def test_evaluate_safety_rejects_wrong_jurisdiction_type():
    with pytest.raises(TypeError):
        evaluate_safety("S4", jurisdiction_decision="not a JurisdictionDecision")


def test_evaluate_safety_rejects_wrong_grounded_response_type():
    with pytest.raises(TypeError):
        evaluate_safety("S5", grounded_response="not a GroundedResponse")


def test_evaluate_safety_rejects_wrong_config_type():
    with pytest.raises(TypeError):
        evaluate_safety("S6", config="not a config")


# ---------------------------------------------------------------------------
# SafetyDecision invariants
# ---------------------------------------------------------------------------


def _summary():
    return {"classification_state": None, "jurisdiction_state": None, "grounding_status": None, "cited_evidence_count": None, "unique_valid_evidence_id_count": None, "citation_integrity_validation_rate": None}


def test_decision_rejects_engineering_band_when_not_safe():
    with pytest.raises(ValueError):
        SafetyDecision(
            schema_version="1.0.0", decision_id="a" * 64, input_id="X", safety_status="ABSTAIN",
            reason_code="CLASSIFICATION_UNRESOLVED", explanation="x", engineering_signal_band="STRONG",
            hard_gate_results=["G2:FIRED"], input_status_summary=_summary(), abstained=True,
            escalation_required=False, synthetic=None, config_signature="sig",
        )


def test_decision_requires_engineering_band_when_safe():
    with pytest.raises(ValueError):
        SafetyDecision(
            schema_version="1.0.0", decision_id="a" * 64, input_id="X", safety_status="SAFE_TO_PRESENT",
            reason_code="SAFE_GROUNDED_RESPONSE", explanation="x", engineering_signal_band="NOT_APPLICABLE",
            hard_gate_results=["G9:FIRED"], input_status_summary=_summary(), abstained=False,
            escalation_required=False, synthetic=None, config_signature="sig",
        )


def test_decision_rejects_reason_code_not_permitted_for_status():
    with pytest.raises(ValueError):
        SafetyDecision(
            schema_version="1.0.0", decision_id="a" * 64, input_id="X", safety_status="SAFE_TO_PRESENT",
            reason_code="CLASSIFICATION_UNRESOLVED", explanation="x", engineering_signal_band="STRONG",
            hard_gate_results=["G9:FIRED"], input_status_summary=_summary(), abstained=False,
            escalation_required=False, synthetic=None, config_signature="sig",
        )


def test_decision_rejects_mismatched_abstained_flag():
    with pytest.raises(ValueError):
        SafetyDecision(
            schema_version="1.0.0", decision_id="a" * 64, input_id="X", safety_status="ABSTAIN",
            reason_code="CLASSIFICATION_UNRESOLVED", explanation="x", engineering_signal_band="NOT_APPLICABLE",
            hard_gate_results=["G2:FIRED"], input_status_summary=_summary(), abstained=False,
            escalation_required=False, synthetic=None, config_signature="sig",
        )


def test_decision_rejects_empty_hard_gate_results():
    with pytest.raises(ValueError):
        SafetyDecision(
            schema_version="1.0.0", decision_id="a" * 64, input_id="X", safety_status="ABSTAIN",
            reason_code="CLASSIFICATION_UNRESOLVED", explanation="x", engineering_signal_band="NOT_APPLICABLE",
            hard_gate_results=[], input_status_summary=_summary(), abstained=True,
            escalation_required=False, synthetic=None, config_signature="sig",
        )


def test_decision_never_contains_a_legal_conclusion_or_probability_field():
    field_names = {f.name for f in dataclasses.fields(SafetyDecision)}
    forbidden = {
        "legally_certain", "is_legally_valid", "legal_determination", "legal_conclusion",
        "probability", "legal_confidence", "compliance_probability", "patentability_probability",
    }
    assert field_names.isdisjoint(forbidden)


def test_policy_config_rejects_invalid_numeric_fields():
    with pytest.raises(ValueError):
        SafetyPolicyConfig(strong_min_unique_citations=0)
    with pytest.raises(ValueError):
        SafetyPolicyConfig(strong_min_integrity_rate=1.5)
    with pytest.raises(ValueError):
        SafetyPolicyConfig(moderate_min_integrity_rate=-0.1)
    with pytest.raises(ValueError):
        SafetyPolicyConfig(strong_min_integrity_rate=0.3, moderate_min_integrity_rate=0.5)


def test_config_signature_is_stable():
    assert SafetyPolicyConfig().signature == SafetyPolicyConfig().signature
