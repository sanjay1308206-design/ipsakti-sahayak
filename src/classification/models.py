"""
Phase 11 classification data shapes
(docs/PHASE_11_FORMULATION_CLASSIFICATION.md Sections E, F, G, H).

CRITICAL: every enum vocabulary below is a Python-side mirror of
config/domain_taxonomy.yaml, not a second/independent taxonomy. No
category name is invented, renamed, or reordered relative to that file.
This mirrors the exact convention Phase 8/9/10 already use throughout
this repository (hardcoded frozensets in src/, cross-checked against the
YAML contract by a dedicated regression test,
tests/test_phase_11_regression.py) rather than parsing YAML at import
time - consistent with every prior phase's own src/ code.

The Phase 1 DECISION TREE's five input fields (`user_intent`,
`formulation_regulatory_track`, `jurisdiction`, `regulatory_question_type`,
`evidence_state`) keep their EXACT Phase 1 names throughout this package -
never renamed for convenience.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

CLASSIFICATION_SCHEMA_VERSION = "1.0.0"

# Mirrors config/domain_taxonomy.yaml taxonomy_version and
# config/regulatory_decision_tree.yaml tree_version exactly - cross-checked
# for drift by tests/test_phase_11_regression.py.
TAXONOMY_VERSION = "1.0.0"
DECISION_TREE_VERSION = "1.0.0"
CLASSIFICATION_CONTRACT_VERSION = "1.0.0"

# --- Phase 1 taxonomy enums (config/domain_taxonomy.yaml), verbatim -------

REGULATORY_TRACK_VALUES = frozenset(
    {
        "CLASSICAL_AYURVEDIC_DRUG",
        "PROPRIETARY_AYURVEDIC_DRUG",
        "NEW_AYURVEDIC_DRUG",
        "AYURVEDA_AAHARA_FOOD",
        "COSMETIC",
        "PHYTOPHARMACEUTICAL",
        "UNDETERMINED",
        "CONFLICTING",
    }
)

IP_PROTECTION_CATEGORY_VALUES = frozenset(
    {"PATENT", "TRADEMARK", "DESIGN", "GEOGRAPHICAL_INDICATION", "NONE", "UNDETERMINED"}
)

ABS_TK_RELATION_VALUES = frozenset(
    {"TRADITIONAL_KNOWLEDGE_RELATED", "ACCESS_AND_BENEFIT_SHARING_RELATED", "NOT_RELATED", "UNDETERMINED"}
)

REGULATORY_QUESTION_TYPE_VALUES = frozenset(
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

USER_INTENT_VALUES = frozenset(
    {
        "DETERMINE_REGULATORY_CLASSIFICATION",
        "DETERMINE_IP_PROTECTION_PATHWAY",
        "CHECK_COMPLIANCE_REQUIREMENT",
        "LOOKUP_AUTHORITATIVE_SOURCE",
        "GENERAL_INFORMATION_REQUEST",
        "OUT_OF_SCOPE_OR_UNSUPPORTED",
        "AMBIGUOUS_INTENT",
        "UNDETERMINED",
    }
)

# Mirrors user_intent_categories[*].evidence_requiring == true.
EVIDENCE_REQUIRING_INTENTS = frozenset(
    {
        "DETERMINE_REGULATORY_CLASSIFICATION",
        "DETERMINE_IP_PROTECTION_PATHWAY",
        "CHECK_COMPLIANCE_REQUIREMENT",
        "LOOKUP_AUTHORITATIVE_SOURCE",
    }
)

JURISDICTION_VALUES = frozenset({"INDIA", "INTERNATIONAL", "BOTH", "UNSPECIFIED"})

EVIDENCE_STATE_VALUES = frozenset(
    {"SUFFICIENT_EVIDENCE", "INSUFFICIENT_EVIDENCE", "NO_EVIDENCE_AVAILABLE", "NOT_YET_EVALUATED"}
)

CLASSIFICATION_STATES = frozenset({"KNOWN", "UNKNOWN", "AMBIGUOUS", "NEEDS_EVIDENCE"})

# Per-dimension explainability state (docs Section K) - deliberately reuses
# the SAME closed vocabulary as CLASSIFICATION_STATES rather than inventing
# a fifth value, per explicit instruction. NEEDS_EVIDENCE is excluded here:
# no single text-extraction dimension can independently signal "needs
# evidence" - that is purely a property of the overall decision tree (rule
# R7, driven by user_intent + evidence_state together), never of one
# dimension's own extraction step. See docs Section M for the full
# disclosure of this design choice.
DIMENSION_STATES = frozenset({"KNOWN", "UNKNOWN", "AMBIGUOUS"})

# Fixed disclaimer text - verbatim from config/classification_contract.yaml
# `disclaimer.constant`. Cross-checked against that file for drift by
# tests/test_phase_11_regression.py.
FIXED_DISCLAIMER = (
    "This classification is an engineering categorization used for "
    "internal workflow routing only. It is not legal advice and is not "
    "an authoritative legal determination. Consult the cited authoritative "
    "source and, where applicable, a qualified professional before relying "
    "on this result."
)


class ClassificationSchemaError(ValueError):
    """Raised when serialized Phase 11 classification data is malformed or structurally inconsistent."""


@dataclass(frozen=True)
class ClassificationInput:
    """
    The untrusted, caller-supplied input (docs Section G). Only two free-
    text fields are accepted - `raw_query` (the user's question) and
    `formulation_description` (free text about the formulation/product) -
    both explicitly named in the Phase 11 instructions' own "Possible
    Inputs" list; no speculative ingredients/dosage-form/manufacturing/
    market schema is introduced (per the explicit instruction not to
    "create a giant speculative schema" beyond what the Phase 1 contract
    justifies). `evidence_state`, if supplied, is an OPAQUE passthrough -
    Phase 11 never computes it itself (docs Section N); it is assumed to
    have been determined upstream by a future orchestrator that already
    ran the Phase 5-9 evidence pipeline.
    """

    input_id: str
    raw_query: str
    formulation_description: Optional[str] = None
    evidence_state: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.input_id, str) or not self.input_id.strip():
            raise ValueError("input_id must be a non-empty string")
        if not isinstance(self.raw_query, str):
            raise ValueError(f"raw_query must be a string, got {type(self.raw_query).__name__}")
        if self.formulation_description is not None and not isinstance(self.formulation_description, str):
            raise ValueError("formulation_description must be a string or None")
        if self.evidence_state is not None and not isinstance(self.evidence_state, str):
            raise ValueError("evidence_state must be a string or None")


@dataclass(frozen=True)
class ClassificationConfig:
    """Explicit, documented classifier configuration. No knob currently changes classification behavior; schema_version is tracked for forward compatibility."""

    schema_version: str = CLASSIFICATION_SCHEMA_VERSION

    def __post_init__(self):
        if not isinstance(self.schema_version, str) or not self.schema_version.strip():
            raise ValueError("schema_version must be a non-empty string")


@dataclass(frozen=True)
class DimensionResult:
    """
    Per-dimension explainability (docs Section K): value / state / reason
    / matched_rule_ids. `matched_rule_ids` names the taxonomy/keyword-rule
    IDs that were consulted (e.g. `["RT-01"]`), never a hidden reasoning
    trace - only observable, rule-level facts.
    """

    dimension: str
    value: str
    state: str
    matched_rule_ids: list
    reason: str

    def __post_init__(self):
        if not isinstance(self.dimension, str) or not self.dimension.strip():
            raise ValueError("dimension must be a non-empty string")
        if not isinstance(self.value, str) or not self.value.strip():
            raise ValueError("value must be a non-empty string")
        if self.state not in DIMENSION_STATES:
            raise ValueError(f"state must be one of {sorted(DIMENSION_STATES)}, got {self.state!r}")
        if not isinstance(self.matched_rule_ids, list) or any(not isinstance(x, str) for x in self.matched_rule_ids):
            raise ValueError("matched_rule_ids must be a list of strings")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be a non-empty string")


@dataclass(frozen=True)
class FormulationClassificationValues:
    """Flat enum values exactly matching classification_contract.yaml's `formulation_classification` object."""

    regulatory_track: str
    ip_protection_category: str
    abs_tk_relation: str

    def __post_init__(self):
        if self.regulatory_track not in REGULATORY_TRACK_VALUES:
            raise ValueError(f"regulatory_track must be one of {sorted(REGULATORY_TRACK_VALUES)}, got {self.regulatory_track!r}")
        if self.ip_protection_category not in IP_PROTECTION_CATEGORY_VALUES:
            raise ValueError(
                f"ip_protection_category must be one of {sorted(IP_PROTECTION_CATEGORY_VALUES)}, got {self.ip_protection_category!r}"
            )
        if self.abs_tk_relation not in ABS_TK_RELATION_VALUES:
            raise ValueError(f"abs_tk_relation must be one of {sorted(ABS_TK_RELATION_VALUES)}, got {self.abs_tk_relation!r}")


@dataclass(frozen=True)
class ClassificationProvenance:
    """Exactly matches classification_contract.yaml's `provenance` object."""

    taxonomy_version: str
    decision_tree_version: str
    contract_version: str

    def __post_init__(self):
        for name in ("taxonomy_version", "decision_tree_version", "contract_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")


@dataclass(frozen=True)
class ClassificationResult:
    """
    The Phase 11 deliverable. The flat fields below exactly satisfy
    `config/classification_contract.yaml`'s output schema (never fewer
    fields than required, values always members of their `enum_ref`
    vocabulary - SAFE-06). `dimension_details` is a Phase-11-owned
    ADDITION beyond that contract, giving the per-dimension explainability
    the Phase 11 instructions separately require - never a replacement for
    the flat fields, never contradicting them.
    """

    schema_version: str
    input_id: str
    user_intent: str
    formulation_classification: FormulationClassificationValues
    regulatory_question_type: str
    jurisdiction_input: str
    evidence_state: str
    classification_state: str
    reason_codes: list
    explanation: str
    requires_evidence: bool
    requires_escalation: bool
    basis: list
    disclaimer: str
    provenance: ClassificationProvenance
    dimension_details: dict

    def __post_init__(self):
        if not isinstance(self.schema_version, str) or not self.schema_version.strip():
            raise ValueError("schema_version must be a non-empty string")
        if not isinstance(self.input_id, str) or not self.input_id.strip():
            raise ValueError("input_id must be a non-empty string")
        if self.user_intent not in USER_INTENT_VALUES:
            raise ValueError(f"user_intent must be one of {sorted(USER_INTENT_VALUES)}, got {self.user_intent!r}")
        if not isinstance(self.formulation_classification, FormulationClassificationValues):
            raise ValueError("formulation_classification must be a FormulationClassificationValues instance")
        if self.regulatory_question_type not in REGULATORY_QUESTION_TYPE_VALUES:
            raise ValueError(
                f"regulatory_question_type must be one of {sorted(REGULATORY_QUESTION_TYPE_VALUES)}, "
                f"got {self.regulatory_question_type!r}"
            )
        if self.jurisdiction_input not in JURISDICTION_VALUES:
            raise ValueError(f"jurisdiction_input must be one of {sorted(JURISDICTION_VALUES)}, got {self.jurisdiction_input!r}")
        if self.evidence_state not in EVIDENCE_STATE_VALUES:
            raise ValueError(f"evidence_state must be one of {sorted(EVIDENCE_STATE_VALUES)}, got {self.evidence_state!r}")
        if self.classification_state not in CLASSIFICATION_STATES:
            raise ValueError(
                f"classification_state must be one of {sorted(CLASSIFICATION_STATES)}, got {self.classification_state!r}"
            )

        if not isinstance(self.reason_codes, list) or any(not isinstance(x, str) for x in self.reason_codes):
            raise ValueError("reason_codes must be a list of strings")
        if self.classification_state != "KNOWN" and not self.reason_codes:
            raise ValueError("reason_codes may be empty only when classification_state == KNOWN")

        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise ValueError("explanation must be a non-empty string")

        if not isinstance(self.requires_evidence, bool):
            raise ValueError("requires_evidence must be a bool")
        if self.requires_evidence != (self.classification_state == "NEEDS_EVIDENCE"):
            raise ValueError("requires_evidence must be true if and only if classification_state == NEEDS_EVIDENCE")

        if not isinstance(self.requires_escalation, bool):
            raise ValueError("requires_escalation must be a bool")
        if self.requires_escalation != (self.classification_state == "AMBIGUOUS"):
            raise ValueError("requires_escalation must be true if and only if classification_state == AMBIGUOUS")

        if not isinstance(self.basis, list) or any(not isinstance(x, str) for x in self.basis) or not self.basis:
            raise ValueError("basis must be a non-empty list of strings")

        if self.disclaimer != FIXED_DISCLAIMER:
            raise ValueError("disclaimer must be exactly the fixed constant text - never altered, never omitted")

        if not isinstance(self.provenance, ClassificationProvenance):
            raise ValueError("provenance must be a ClassificationProvenance instance")

        if not isinstance(self.dimension_details, dict):
            raise ValueError("dimension_details must be a dict")
        for key, value in self.dimension_details.items():
            if not isinstance(key, str):
                raise ValueError("dimension_details keys must be strings")
            if not isinstance(value, DimensionResult):
                raise ValueError(f"dimension_details[{key!r}] must be a DimensionResult instance")
