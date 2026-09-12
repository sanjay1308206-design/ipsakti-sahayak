"""
Phase 16 evaluation/red-team data shapes
(docs/PHASE_16_EVALUATION_AND_RED_TEAM.md Sections F, G, Y, AD).

CRITICAL DISTINCTIONS preserved throughout this module:

1. COMPONENT METRICS vs END-TO-END METRICS - `COMPONENT_NAMES` includes
   both individual pipeline stages (`BM25_RETRIEVAL`, `CLASSIFICATION`,
   ...) AND `END_TO_END` as a DISTINCT, separately-reported member -
   nothing here ever folds a per-component result into the end-to-end
   number, or vice versa.
2. ZERO-DENOMINATOR POLICY - `EvaluationResult.value` is `None` (NOT
   `0.0`, NOT `NaN`, NOT infinity) whenever the metric is undefined for
   the case count actually run (`applicable=False`) - a real, computed
   `0.0` (e.g. "zero relevant items were found, out of five that
   exist") is always structurally distinguishable from "there was
   nothing to measure."
3. GROUND-TRUTH DISCIPLINE - every `BenchmarkCase` declares its own
   `ground_truth_origin` - a model-generated expectation is never
   silently treated as authoritative.
4. NO NUMERIC CONFIDENCE INVENTION - `severity` (on a failure-triage
   entry or red-team case) is a small CATEGORICAL vocabulary, never a
   fabricated numeric vulnerability-scoring scale.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

EVALUATION_SCHEMA_VERSION = "1.0.0"

# [ENGINEERING RECOMMENDATION] versioned independently of
# EVALUATION_SCHEMA_VERSION (docs Section AD / "BENCHMARK VERSIONING") -
# the benchmark CASE CATALOGUE (config/redteam_cases.yaml's vocabulary,
# and the fixed synthetic cases defined in src/evaluation/benchmark.py
# and tests/test_phase_16_*.py) can evolve independently of the RESULT
# dataclass shapes. Never a timestamp - an explicit, hand-incremented
# string, exactly like every other *_SCHEMA_VERSION in this project.
BENCHMARK_SCHEMA_VERSION = "1.0.0"

# Component vs end-to-end vs red-team, all in ONE closed vocabulary so a
# report can never claim to be about a component that does not exist -
# but END_TO_END and RED_TEAM_SECURITY are always reported as their own,
# separate members, never merged into a per-stage component number.
COMPONENT_NAMES = frozenset(
    {
        "CORPUS_PROVENANCE",
        "DOCUMENT_STRUCTURE",
        "EVIDENCE_CONSTRUCTION",
        "BM25_RETRIEVAL",
        "DENSE_RETRIEVAL",
        "HYBRID_RRF_RETRIEVAL",
        "RERANKED_RETRIEVAL",
        "CITATION_INTEGRITY",
        "GROUNDED_GENERATION",
        "CLASSIFICATION",
        "JURISDICTION",
        "SAFETY_ABSTENTION",
        "MULTILINGUAL_DELIVERY",
        "HUMAN_REVIEW",
        "END_TO_END",
        "RED_TEAM_SECURITY",
        # [OUR ENHANCEMENT] Phase 19 additions - Phase 17 (API) and Phase 18
        # (frontend) did not exist yet when this vocabulary was first
        # closed, so their trust boundaries had no component name to
        # attach a red-team case to. Purely additive - no existing member
        # renamed or removed.
        "API_LAYER",
        "FRONTEND_DELIVERY",
    }
)

# Components covered by an EARLIER phase's own already-exhaustive test
# suite (docs Section B) - Phase 16 references that existing coverage
# rather than duplicating it ("Do NOT duplicate existing metrics
# unnecessarily").
REFERENCED_EXISTING_COVERAGE_COMPONENTS = frozenset({"CORPUS_PROVENANCE", "DOCUMENT_STRUCTURE", "EVIDENCE_CONSTRUCTION"})

# docs Section F - every benchmark expectation identifies its own origin;
# a model-generated expectation is never silently authoritative.
GROUND_TRUTH_ORIGINS = frozenset(
    {"SYNTHETIC_EXPECTATION", "AUTHORITATIVE_EXPECTATION", "STRUCTURAL_EXPECTATION", "SECURITY_EXPECTATION"}
)

# docs Section U - exactly the 21 categories named in the instructions.
ATTACK_CATEGORIES = frozenset(
    {
        "PROMPT_INJECTION",
        "EVIDENCE_INJECTION",
        "CITATION_FORGERY",
        "FAKE_EVIDENCE_ID",
        "EVIDENCE_ID_MUTATION",
        "CONTENT_HASH_MUTATION",
        "JURISDICTION_LEAKAGE",
        "LANGUAGE_TO_JURISDICTION_MANIPULATION",
        "CLASSIFICATION_MANIPULATION",
        "SAFETY_OVERRIDE_ATTEMPT",
        "GROUNDING_OVERRIDE_ATTEMPT",
        "REVIEWER_PRIVILEGE_ESCALATION",
        "MALICIOUS_REVIEWER_COMMENT",
        "UNICODE_ATTACK",
        "MIXED_SCRIPT_ATTACK",
        "OVERSIZED_INPUT",
        "MALFORMED_SERIALIZATION",
        "PROVIDER_FAILURE",
        "EMPTY_PROVIDER_OUTPUT",
        "WRONG_PROVIDER_OUTPUT_TYPE",
        "CROSS_PHASE_METADATA_MUTATION",
        # [OUR ENHANCEMENT] Phase 19 additions (docs/PHASE_19_SECURITY_ADVERSARIAL_HARDENING.md
        # Section on red-team extension) - additive only, RT-01..RT-21 and
        # their 21 original categories above are untouched.
        "USER_QUERY_INJECTION_FULL_PIPELINE",
        "RETRIEVED_DOCUMENT_INJECTION_TO_SAFETY",
        "JURISDICTION_UNICODE_NORMALIZATION_BYPASS",
        "EVIDENCE_ID_CONFUSABLE_BYPASS",
        "REVIEW_SEQUENCE_REPLAY",
        "FRONTEND_XSS_RENDERING_ATTEMPT",
        "API_OVERSIZED_PAYLOAD",
        "API_MALFORMED_JSON",
        "API_REPEATED_MALFORMED_REQUESTS",
        "SERIALIZATION_FIELD_INJECTION_CROSS_OBJECT",
        "CASE_FOLDING_EVIDENCE_ID_CONFUSION",
        "ERROR_MESSAGE_INFORMATION_DISCLOSURE",
        "CROSS_JURISDICTION_LEAKAGE_UNDER_ADVERSARIAL_NORMALIZATION",
        "HUMAN_REVIEW_STATE_INJECTION_VIA_TRANSLATED_METADATA",
        "DESERIALIZATION_TYPE_CONFUSION",
    }
)

# docs Section V - what a red-team case expects to happen to the attack
# itself (never "the attack succeeded").
EXPECTED_ATTACK_OUTCOMES = frozenset({"BLOCKED", "REJECTED", "INERT"})

# docs Section V - precisely-defined attack-success predicates, named
# exactly as the instructions define them (plus two documented,
# necessary catch-alls for the remaining categories - Section V explains
# each mapping).
SUCCESS_DEFINITIONS = frozenset(
    {
        "JURISDICTION_BYPASS",
        "CITATION_FORGERY_SUCCESS",
        "SAFETY_OVERRIDE",
        "GROUNDING_BYPASS",
        "EVIDENCE_MUTATION",
        "REVIEWER_PRIVILEGE_ESCALATION",
        "GENERIC_TRUSTED_STATE_UNCHANGED",
        "GENERIC_INPUT_REJECTED",
    }
)

# Fixed, documented mapping - every attack category maps to exactly one
# success definition (docs Section V).
ATTACK_CATEGORY_SUCCESS_DEFINITION = {
    "PROMPT_INJECTION": "GENERIC_TRUSTED_STATE_UNCHANGED",
    "EVIDENCE_INJECTION": "GENERIC_TRUSTED_STATE_UNCHANGED",
    "CITATION_FORGERY": "CITATION_FORGERY_SUCCESS",
    "FAKE_EVIDENCE_ID": "GENERIC_INPUT_REJECTED",
    "EVIDENCE_ID_MUTATION": "EVIDENCE_MUTATION",
    "CONTENT_HASH_MUTATION": "EVIDENCE_MUTATION",
    "JURISDICTION_LEAKAGE": "JURISDICTION_BYPASS",
    "LANGUAGE_TO_JURISDICTION_MANIPULATION": "JURISDICTION_BYPASS",
    "CLASSIFICATION_MANIPULATION": "GENERIC_TRUSTED_STATE_UNCHANGED",
    "SAFETY_OVERRIDE_ATTEMPT": "SAFETY_OVERRIDE",
    "GROUNDING_OVERRIDE_ATTEMPT": "GROUNDING_BYPASS",
    "REVIEWER_PRIVILEGE_ESCALATION": "REVIEWER_PRIVILEGE_ESCALATION",
    "MALICIOUS_REVIEWER_COMMENT": "GENERIC_TRUSTED_STATE_UNCHANGED",
    "UNICODE_ATTACK": "GENERIC_TRUSTED_STATE_UNCHANGED",
    "MIXED_SCRIPT_ATTACK": "GENERIC_TRUSTED_STATE_UNCHANGED",
    "OVERSIZED_INPUT": "GENERIC_INPUT_REJECTED",
    "MALFORMED_SERIALIZATION": "GENERIC_INPUT_REJECTED",
    "PROVIDER_FAILURE": "GENERIC_INPUT_REJECTED",
    "EMPTY_PROVIDER_OUTPUT": "GENERIC_TRUSTED_STATE_UNCHANGED",
    "WRONG_PROVIDER_OUTPUT_TYPE": "GENERIC_INPUT_REJECTED",
    "CROSS_PHASE_METADATA_MUTATION": "GENERIC_TRUSTED_STATE_UNCHANGED",
    # [OUR ENHANCEMENT] Phase 19 additions - reuse the same 8 closed
    # SUCCESS_DEFINITIONS values; no new success-definition vocabulary
    # was needed.
    "USER_QUERY_INJECTION_FULL_PIPELINE": "GENERIC_TRUSTED_STATE_UNCHANGED",
    "RETRIEVED_DOCUMENT_INJECTION_TO_SAFETY": "GENERIC_TRUSTED_STATE_UNCHANGED",
    "JURISDICTION_UNICODE_NORMALIZATION_BYPASS": "JURISDICTION_BYPASS",
    "EVIDENCE_ID_CONFUSABLE_BYPASS": "GENERIC_INPUT_REJECTED",
    "REVIEW_SEQUENCE_REPLAY": "GENERIC_INPUT_REJECTED",
    "FRONTEND_XSS_RENDERING_ATTEMPT": "GENERIC_TRUSTED_STATE_UNCHANGED",
    "API_OVERSIZED_PAYLOAD": "GENERIC_INPUT_REJECTED",
    "API_MALFORMED_JSON": "GENERIC_INPUT_REJECTED",
    "API_REPEATED_MALFORMED_REQUESTS": "GENERIC_INPUT_REJECTED",
    "SERIALIZATION_FIELD_INJECTION_CROSS_OBJECT": "GENERIC_TRUSTED_STATE_UNCHANGED",
    "CASE_FOLDING_EVIDENCE_ID_CONFUSION": "CITATION_FORGERY_SUCCESS",
    "ERROR_MESSAGE_INFORMATION_DISCLOSURE": "GENERIC_TRUSTED_STATE_UNCHANGED",
    "CROSS_JURISDICTION_LEAKAGE_UNDER_ADVERSARIAL_NORMALIZATION": "JURISDICTION_BYPASS",
    "HUMAN_REVIEW_STATE_INJECTION_VIA_TRANSLATED_METADATA": "GENERIC_TRUSTED_STATE_UNCHANGED",
    "DESERIALIZATION_TYPE_CONFUSION": "GENERIC_INPUT_REJECTED",
}
assert set(ATTACK_CATEGORY_SUCCESS_DEFINITION) == ATTACK_CATEGORIES

# Categorical severity only - never a fabricated numeric
# vulnerability-scoring scale (docs Section U).
SEVERITY_LEVELS = frozenset({"LOW", "MEDIUM", "HIGH", "CRITICAL"})

# docs Section Y - a small, closed failure-category vocabulary for
# triage entries; "OTHER" exists for anything genuinely uncategorized,
# never as a default dumping ground used without justification.
FAILURE_CATEGORIES = frozenset(
    {
        "INCORRECT_CLASSIFICATION",
        "INCORRECT_JURISDICTION",
        "UNEXPECTED_SAFETY_STATUS",
        "UNEXPECTED_GROUNDING_STATUS",
        "UNEXPECTED_REVIEW_TRIGGER",
        "RETRIEVAL_MISS",
        "CITATION_MISMATCH",
        "MULTILINGUAL_PRESERVATION_FAILURE",
        "SECURITY_ATTACK_SUCCEEDED",
        "OTHER",
    }
)


class EvaluationSchemaError(ValueError):
    """Raised when serialized Phase 16 evaluation/red-team data is malformed or structurally inconsistent."""


def _check_enum(name: str, value, vocabulary) -> None:
    if value not in vocabulary:
        raise ValueError(f"{name} must be one of {sorted(vocabulary)}, got {value!r}")


def _check_optional_enum(name: str, value, vocabulary) -> None:
    if value is not None and value not in vocabulary:
        raise ValueError(f"{name} must be a member of {sorted(vocabulary)} or None, got {value!r}")


@dataclass(frozen=True)
class EvaluationConfig:
    """Explicit, documented configuration - no knob currently changes scoring behavior beyond the two schema versions."""

    schema_version: str = EVALUATION_SCHEMA_VERSION
    benchmark_schema_version: str = BENCHMARK_SCHEMA_VERSION

    def __post_init__(self):
        for name in ("schema_version", "benchmark_schema_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")

    @property
    def signature(self) -> str:
        return f"evaluation-config:v{self.schema_version}:benchmark:v{self.benchmark_schema_version}"


@dataclass(frozen=True)
class BenchmarkCase:
    """
    A structured benchmark expectation (docs Section G). Deliberately NOT
    every field is required - only `case_id`/`category`/`ground_truth_origin`/
    `input_summary`/`expected_behavior` are mandatory; every `expected_*`
    field is optional so the schema supports category-specific
    expectations without forcing an irrelevant field onto every case
    (e.g. a classification case has no `expected_jurisdiction`).
    """

    schema_version: str
    case_id: str
    category: str
    ground_truth_origin: str
    input_summary: str
    expected_behavior: str
    expected_evidence_ids: Optional[list] = None
    expected_jurisdiction: Optional[str] = None
    expected_classification_state: Optional[str] = None
    expected_safety_status: Optional[str] = None
    expected_review_status: Optional[str] = None
    expected_language: Optional[str] = None
    adversarial: bool = False
    synthetic: bool = True
    notes: Optional[str] = None

    def __post_init__(self):
        for name in ("schema_version", "case_id", "input_summary", "expected_behavior"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        _check_enum("category", self.category, COMPONENT_NAMES)
        _check_enum("ground_truth_origin", self.ground_truth_origin, GROUND_TRUTH_ORIGINS)
        if self.expected_evidence_ids is not None:
            if not isinstance(self.expected_evidence_ids, list) or any(not isinstance(x, str) for x in self.expected_evidence_ids):
                raise ValueError("expected_evidence_ids must be a list of strings or None")
            if len(self.expected_evidence_ids) != len(set(self.expected_evidence_ids)):
                raise ValueError("expected_evidence_ids must not contain duplicates")
        for name in ("expected_jurisdiction", "expected_classification_state", "expected_safety_status", "expected_review_status", "expected_language"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{name} must be a string or None")
        if not isinstance(self.adversarial, bool):
            raise ValueError("adversarial must be a bool")
        if not isinstance(self.synthetic, bool):
            raise ValueError("synthetic must be a bool")
        if self.notes is not None and not isinstance(self.notes, str):
            raise ValueError("notes must be a string or None")


@dataclass(frozen=True)
class EvaluationResult:
    """
    One metric measurement (docs Section Z - "ZERO-DENOMINATOR POLICY").
    `value is None` if and only if `applicable is False` - the ONLY
    representation of "undefined metric" anywhere in this package; never
    `0.0`, `nan`, or infinity used to mean "not applicable".
    """

    schema_version: str
    metric_name: str
    component: str
    applicable: bool
    value: Optional[float]
    numerator: Optional[int]
    denominator: Optional[int]
    explanation: str
    ground_truth_origin: Optional[str] = None

    def __post_init__(self):
        for name in ("schema_version", "metric_name"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        _check_enum("component", self.component, COMPONENT_NAMES)
        if not isinstance(self.applicable, bool):
            raise ValueError("applicable must be a bool")
        if self.applicable and self.value is None:
            raise ValueError("value must be set when applicable is True")
        if not self.applicable and self.value is not None:
            raise ValueError("value must be None when applicable is False (zero-denominator policy)")
        if self.value is not None:
            if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
                raise ValueError("value must be a number or None")
            if not math.isfinite(self.value):
                raise ValueError("value must be finite - NaN/infinity are never used to represent an undefined metric")
        for name in ("numerator", "denominator"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise ValueError(f"{name} must be a non-negative integer or None, got {value!r}")
        if self.denominator == 0 and self.applicable:
            raise ValueError("a zero denominator can never produce an applicable (defined) result")
        if self.numerator is not None and self.denominator is not None and self.numerator > self.denominator:
            raise ValueError("numerator must not exceed denominator")
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise ValueError("explanation must be a non-empty string")
        _check_optional_enum("ground_truth_origin", self.ground_truth_origin, GROUND_TRUTH_ORIGINS)


@dataclass(frozen=True)
class ComponentBenchmarkReport:
    """One component's (or END_TO_END's) full set of measurements (docs Section Y/Z)."""

    schema_version: str
    report_id: str
    component: str
    case_count: int
    results: list
    passed_case_ids: list
    failed_case_ids: list
    notes: Optional[str]
    config_signature: str

    def __post_init__(self):
        for name in ("schema_version", "report_id", "config_signature"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        _check_enum("component", self.component, COMPONENT_NAMES)
        if isinstance(self.case_count, bool) or not isinstance(self.case_count, int) or self.case_count < 0:
            raise ValueError("case_count must be a non-negative integer")
        if not isinstance(self.results, list) or any(not isinstance(r, EvaluationResult) for r in self.results):
            raise ValueError("results must be a list of EvaluationResult")
        for name in ("passed_case_ids", "failed_case_ids"):
            value = getattr(self, name)
            if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
                raise ValueError(f"{name} must be a list of strings")
        if set(self.passed_case_ids) & set(self.failed_case_ids):
            raise ValueError("passed_case_ids and failed_case_ids must not overlap")
        if len(self.passed_case_ids) + len(self.failed_case_ids) > self.case_count:
            raise ValueError("passed_case_ids + failed_case_ids must not exceed case_count")
        if self.notes is not None and not isinstance(self.notes, str):
            raise ValueError("notes must be a string or None")


@dataclass(frozen=True)
class FailureTriageEntry:
    """Structured triage for one failed benchmark case (docs Section X)."""

    schema_version: str
    case_id: str
    component: str
    failure_category: str
    expected_behavior: str
    actual_behavior: str
    reproducible: bool
    severity: Optional[str]
    severity_rationale: Optional[str]
    suggested_owner_phase: Optional[str]
    notes: Optional[str]

    def __post_init__(self):
        for name in ("schema_version", "case_id", "expected_behavior", "actual_behavior"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        _check_enum("component", self.component, COMPONENT_NAMES)
        _check_enum("failure_category", self.failure_category, FAILURE_CATEGORIES)
        if not isinstance(self.reproducible, bool):
            raise ValueError("reproducible must be a bool")
        _check_optional_enum("severity", self.severity, SEVERITY_LEVELS)
        if self.severity is not None and (self.severity_rationale is None or not self.severity_rationale.strip()):
            raise ValueError("severity_rationale is required whenever severity is set (docs: 'document the engineering rationale')")
        if self.severity is None and self.severity_rationale is not None:
            raise ValueError("severity_rationale must be None when severity is None")
        for name in ("suggested_owner_phase", "notes"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{name} must be a string or None")


@dataclass(frozen=True)
class RedTeamCase:
    """One fixed, deterministic adversarial case (docs Section U/V). No randomness anywhere - a fixed catalogue."""

    schema_version: str
    case_id: str
    attack_category: str
    attack_input_summary: str
    target_component: str
    expected_security_property: str
    expected_result: str
    synthetic: bool = True
    severity: Optional[str] = None
    severity_rationale: Optional[str] = None
    notes: Optional[str] = None

    def __post_init__(self):
        for name in ("schema_version", "case_id", "attack_input_summary", "expected_security_property"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        _check_enum("attack_category", self.attack_category, ATTACK_CATEGORIES)
        _check_enum("target_component", self.target_component, COMPONENT_NAMES)
        _check_enum("expected_result", self.expected_result, EXPECTED_ATTACK_OUTCOMES)
        if not isinstance(self.synthetic, bool):
            raise ValueError("synthetic must be a bool")
        _check_optional_enum("severity", self.severity, SEVERITY_LEVELS)
        if self.severity is not None and (self.severity_rationale is None or not self.severity_rationale.strip()):
            raise ValueError("severity_rationale is required whenever severity is set")
        if self.severity is None and self.severity_rationale is not None:
            raise ValueError("severity_rationale must be None when severity is None")
        if self.notes is not None and not isinstance(self.notes, str):
            raise ValueError("notes must be a string or None")


@dataclass(frozen=True)
class RedTeamResult:
    """The observed outcome of running one RedTeamCase (docs Section V)."""

    schema_version: str
    case_id: str
    attack_category: str
    target_component: str
    success_definition: str
    attack_success: bool
    detail: str
    config_signature: str

    def __post_init__(self):
        for name in ("schema_version", "case_id", "detail", "config_signature"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        _check_enum("attack_category", self.attack_category, ATTACK_CATEGORIES)
        _check_enum("target_component", self.target_component, COMPONENT_NAMES)
        _check_enum("success_definition", self.success_definition, SUCCESS_DEFINITIONS)
        if ATTACK_CATEGORY_SUCCESS_DEFINITION[self.attack_category] != self.success_definition:
            raise ValueError(
                f"attack_category {self.attack_category!r} must use success_definition "
                f"{ATTACK_CATEGORY_SUCCESS_DEFINITION[self.attack_category]!r}, got {self.success_definition!r}"
            )
        if not isinstance(self.attack_success, bool):
            raise ValueError("attack_success must be a bool")


@dataclass(frozen=True)
class RedTeamSummary:
    """
    Structural red-team metrics only (docs Section W). `attack_success_rate`/
    `detection_rate` are `None` (NOT 0.0) when `attack_cases == 0`.
    """

    schema_version: str
    attack_cases: int
    successful_attacks: int
    blocked_attacks: int
    detection_rate: Optional[float]
    attack_success_rate: Optional[float]
    results: list

    def __post_init__(self):
        if not isinstance(self.schema_version, str) or not self.schema_version.strip():
            raise ValueError("schema_version must be a non-empty string")
        for name in ("attack_cases", "successful_attacks", "blocked_attacks"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.successful_attacks + self.blocked_attacks != self.attack_cases:
            raise ValueError("successful_attacks + blocked_attacks must equal attack_cases")
        if self.attack_cases == 0:
            if self.detection_rate is not None or self.attack_success_rate is not None:
                raise ValueError("detection_rate/attack_success_rate must be None when attack_cases == 0")
        else:
            for name in ("detection_rate", "attack_success_rate"):
                value = getattr(self, name)
                if value is None or isinstance(value, bool) or not isinstance(value, (int, float)) or not (0.0 <= float(value) <= 1.0):
                    raise ValueError(f"{name} must be a number in [0.0, 1.0] when attack_cases > 0")
        if not isinstance(self.results, list) or any(not isinstance(r, RedTeamResult) for r in self.results):
            raise ValueError("results must be a list of RedTeamResult")
        if len(self.results) != self.attack_cases:
            raise ValueError("len(results) must equal attack_cases")


@dataclass(frozen=True)
class EvaluationReport:
    """The top-level Phase 16 aggregate (docs Section Y)."""

    schema_version: str
    benchmark_schema_version: str
    report_id: str
    component_reports: list
    redteam_summary: Optional[RedTeamSummary]
    failure_triage: list
    config_signature: str

    def __post_init__(self):
        for name in ("schema_version", "benchmark_schema_version", "report_id", "config_signature"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.component_reports, list) or any(not isinstance(r, ComponentBenchmarkReport) for r in self.component_reports):
            raise ValueError("component_reports must be a list of ComponentBenchmarkReport")
        components = [r.component for r in self.component_reports]
        if len(components) != len(set(components)):
            raise ValueError("component_reports must not contain more than one report for the same component")
        if self.redteam_summary is not None and not isinstance(self.redteam_summary, RedTeamSummary):
            raise ValueError("redteam_summary must be a RedTeamSummary or None")
        if not isinstance(self.failure_triage, list) or any(not isinstance(x, FailureTriageEntry) for x in self.failure_triage):
            raise ValueError("failure_triage must be a list of FailureTriageEntry")
