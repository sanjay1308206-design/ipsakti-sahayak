"""
Phase 1 test-support module: a small, deterministic reference evaluator for
the regulatory decision tree contract described in
docs/PHASE_01_REGULATORY_DECISION_TREE.md and
config/regulatory_decision_tree.yaml.

This is NOT the Phase 11 "Formulation Classification Engine". It does not
read free text, does not ask clarifying questions, and does not infer any
taxonomy value. It only implements the fixed, ordered rule list (R1..R8)
over already-supplied enum inputs, so the Phase 1 contract can be tested.

Intentionally no eval()/exec() of YAML "condition" strings - the rule
conditions are documented in YAML for human/audit traceability, but the
actual logic here is plain Python matching that documentation exactly,
which is cross-checked for consistency by the test suite.

Not a test module itself (no test_ prefix) - pytest will not collect it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

EVIDENCE_REQUIRING_INTENTS = frozenset(
    {
        "DETERMINE_REGULATORY_CLASSIFICATION",
        "DETERMINE_IP_PROTECTION_PATHWAY",
        "CHECK_COMPLIANCE_REQUIREMENT",
        "LOOKUP_AUTHORITATIVE_SOURCE",
    }
)

VALID_REGULATORY_QUESTION_TYPES = frozenset(
    {
        "INDIA_LEGISLATIVE",
        "IP_REGISTRATION_AND_SEARCH",
        "AYUSH_POLICY",
        "TRADITIONAL_DRUG_REGULATION",
        "AYURVEDA_AAHARA_FOOD_LAW",
        "INTERNATIONAL_IP_TREATY",
        "TRADITIONAL_KNOWLEDGE_DATABASE",
        "UNDETERMINED",
    }
)

TERMINAL_STATES = frozenset({"KNOWN", "UNKNOWN", "AMBIGUOUS", "NEEDS_EVIDENCE"})

RULE_ORDER = ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8")

DISCLAIMER = (
    "This classification is an engineering categorization used for "
    "internal workflow routing only. It is not legal advice and is not "
    "an authoritative legal determination. Consult the cited authoritative "
    "source and, where applicable, a qualified professional before relying "
    "on this result."
)


@dataclass(frozen=True)
class ClassificationInput:
    user_intent: str
    formulation_regulatory_track: str
    jurisdiction: str
    regulatory_question_type: str
    evidence_state: str


@dataclass(frozen=True)
class ClassificationResult:
    classification_state: str
    reason_codes: list = field(default_factory=list)
    rule_id: str = ""
    requires_evidence: bool = False
    requires_escalation: bool = False
    basis: list = field(default_factory=list)
    disclaimer: str = DISCLAIMER


def evaluate(inputs: ClassificationInput) -> ClassificationResult:
    """Evaluate rules R1..R8 in fixed order; first match wins."""

    # R1 — MISSING_USER_INTENT
    if inputs.user_intent == "UNDETERMINED":
        return _result("UNKNOWN", "R1", ["MISSING_USER_INTENT"], basis=["R1"])

    # R2 — MISSING_JURISDICTION
    if inputs.jurisdiction == "UNSPECIFIED":
        return _result("UNKNOWN", "R2", ["MISSING_JURISDICTION"], basis=["R2"])

    # R3 — MISSING_FORMULATION_INFO
    if (
        inputs.user_intent in EVIDENCE_REQUIRING_INTENTS
        and inputs.formulation_regulatory_track == "UNDETERMINED"
    ):
        return _result("UNKNOWN", "R3", ["MISSING_FORMULATION_INFO"], basis=["R3"])

    # R4 — CONFLICTING_FORMULATION_SIGNALS
    if inputs.formulation_regulatory_track == "CONFLICTING":
        return _result(
            "AMBIGUOUS", "R4", ["CONFLICTING_FORMULATION_SIGNALS"], basis=["R4"]
        )

    # R5 — AMBIGUOUS_USER_INTENT
    if inputs.user_intent == "AMBIGUOUS_INTENT":
        return _result("AMBIGUOUS", "R5", ["AMBIGUOUS_USER_INTENT"], basis=["R5"])

    # R6 — UNRECOGNIZED_REGULATORY_QUESTION_TYPE
    if (
        inputs.regulatory_question_type == "UNDETERMINED"
        or inputs.regulatory_question_type not in VALID_REGULATORY_QUESTION_TYPES
    ):
        return _result(
            "UNKNOWN",
            "R6",
            ["UNRECOGNIZED_REGULATORY_QUESTION_TYPE"],
            basis=["R6"],
        )

    # R7 — EVIDENCE_NOT_AVAILABLE
    if (
        inputs.user_intent in EVIDENCE_REQUIRING_INTENTS
        and inputs.evidence_state != "SUFFICIENT_EVIDENCE"
    ):
        return _result(
            "NEEDS_EVIDENCE", "R7", ["EVIDENCE_NOT_AVAILABLE"], basis=["R7"]
        )

    # R8 — DEFAULT_KNOWN
    return _result("KNOWN", "R8", [], basis=["R8"])


def _result(state: str, rule_id: str, reasons: list, basis: list) -> ClassificationResult:
    assert state in TERMINAL_STATES
    return ClassificationResult(
        classification_state=state,
        reason_codes=reasons,
        rule_id=rule_id,
        requires_evidence=(state == "NEEDS_EVIDENCE"),
        requires_escalation=(state == "AMBIGUOUS"),
        basis=basis,
        disclaimer=DISCLAIMER,
    )
