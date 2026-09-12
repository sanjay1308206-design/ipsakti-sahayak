"""
Phase 13 safety-decision data shapes
(docs/PHASE_13_CONFIDENCE_SAFETY_ABSTENTION.md Sections E, F, G, H, J).

CRITICAL: `engineering_signal_band` is an ENGINEERING signal about
citation-integrity/grounding structure only - it is NEVER a probability
that a legal answer is correct, a probability of regulatory approval,
legal certainty, legal compliance, patentability, or infringement.
Nothing in this module computes, stores, or exposes a calibrated
probability - no such calibration has ever been performed for this
project, and none is claimed here (docs Section J/K).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

SAFETY_SCHEMA_VERSION = "1.0.0"

# Closed decision vocabulary (docs Section F). Preferred over inventing a
# new one - matches the "controlled outcome" concept the Master Reference
# names for this pipeline stage (Answer / Abstain / Escalate).
SAFETY_STATUSES = frozenset({"SAFE_TO_PRESENT", "ABSTAIN", "ESCALATE"})

REASON_CLASSIFICATION_AMBIGUOUS = "CLASSIFICATION_AMBIGUOUS"
REASON_CLASSIFICATION_UNRESOLVED = "CLASSIFICATION_UNRESOLVED"
REASON_JURISDICTION_AMBIGUOUS = "JURISDICTION_AMBIGUOUS"
REASON_JURISDICTION_UNRESOLVED = "JURISDICTION_UNRESOLVED"
REASON_MISSING_GROUNDED_RESPONSE = "MISSING_GROUNDED_RESPONSE"
REASON_GENERATION_FAILED = "GENERATION_FAILED"
REASON_GENERATION_ABSTAINED = "GENERATION_ABSTAINED"
REASON_NO_VALID_CITATIONS = "NO_VALID_CITATIONS"
REASON_SAFE_GROUNDED_RESPONSE = "SAFE_GROUNDED_RESPONSE"

# Closed, every member independently reachable and tested (docs Section
# H). Deliberately NOT the instructions' literal example list - inspected
# against what this phase's actual design can reach: no separate
# NO_EVIDENCE/INVALID_EVIDENCE/INVALID_CITATION/ESCALATION_REQUIRED codes
# exist, because those cases are already subsumed by GENERATION_ABSTAINED
# (Phase 10 already distinguishes its own abstention reasons, surfaced in
# `explanation`/`input_status_summary`, not duplicated as a second
# top-level code) or by the two specific *_AMBIGUOUS codes (a generic
# ESCALATION_REQUIRED would be dead code given those already cover every
# escalation path this phase reaches).
SAFETY_REASON_CODES = frozenset(
    {
        REASON_CLASSIFICATION_AMBIGUOUS,
        REASON_CLASSIFICATION_UNRESOLVED,
        REASON_JURISDICTION_AMBIGUOUS,
        REASON_JURISDICTION_UNRESOLVED,
        REASON_MISSING_GROUNDED_RESPONSE,
        REASON_GENERATION_FAILED,
        REASON_GENERATION_ABSTAINED,
        REASON_NO_VALID_CITATIONS,
        REASON_SAFE_GROUNDED_RESPONSE,
    }
)

# Which reason codes are structurally permitted for each status - enforced
# in SafetyDecision.__post_init__, mirroring Phase 9/11/12's own
# status-to-reason-code closed mapping convention.
STATUS_REASON_CODES = {
    "SAFE_TO_PRESENT": frozenset({REASON_SAFE_GROUNDED_RESPONSE}),
    "ABSTAIN": frozenset(
        {
            REASON_CLASSIFICATION_UNRESOLVED,
            REASON_JURISDICTION_UNRESOLVED,
            REASON_MISSING_GROUNDED_RESPONSE,
            REASON_GENERATION_FAILED,
            REASON_GENERATION_ABSTAINED,
            REASON_NO_VALID_CITATIONS,
        }
    ),
    "ESCALATE": frozenset({REASON_CLASSIFICATION_AMBIGUOUS, REASON_JURISDICTION_AMBIGUOUS}),
}

# A CATEGORICAL engineering signal, not a numeric probability (docs
# Section J) - "prefer a categorical trust/safety assessment" over a
# fabricated calibrated score. NOT_APPLICABLE is the only value reachable
# when safety_status != SAFE_TO_PRESENT (no answer was presented, so no
# signal about its citation structure is meaningful).
ENGINEERING_SIGNAL_BANDS = frozenset({"STRONG", "MODERATE", "WEAK", "NOT_APPLICABLE"})


class SafetySchemaError(ValueError):
    """Raised when serialized Phase 13 safety data is malformed or structurally inconsistent."""


@dataclass(frozen=True)
class SafetyPolicyConfig:
    """
    Explicit, documented policy configuration (docs Section K).
    `[ASSUMPTION]` - every threshold below is an engineering heuristic,
    not an empirically validated or legally-derived value. No project
    source establishes any of these numbers; they exist only to make an
    otherwise-arbitrary-if-implicit policy explicit, inspectable, and
    overridable. They must never be described as calibrated.

    - `require_at_least_one_valid_citation` (default True, the
      conservative choice): even if Phase 10 was configured to allow an
      uncited GROUNDED response, Phase 13's own presentation-safety
      policy may be stricter than Phase 10's generation-time policy.
    - `strong_min_unique_citations` / `strong_min_integrity_rate` /
      `moderate_min_integrity_rate`: the three coefficients behind
      `policy.compute_engineering_signal_band` (Section J/K) - each
      documented individually there.
    """

    schema_version: str = SAFETY_SCHEMA_VERSION
    require_at_least_one_valid_citation: bool = True
    strong_min_unique_citations: int = 2
    strong_min_integrity_rate: float = 1.0
    moderate_min_integrity_rate: float = 0.5

    def __post_init__(self):
        if not isinstance(self.schema_version, str) or not self.schema_version.strip():
            raise ValueError("schema_version must be a non-empty string")
        if not isinstance(self.require_at_least_one_valid_citation, bool):
            raise ValueError("require_at_least_one_valid_citation must be a bool")
        if (
            isinstance(self.strong_min_unique_citations, bool)
            or not isinstance(self.strong_min_unique_citations, int)
            or self.strong_min_unique_citations < 1
        ):
            raise ValueError(
                f"strong_min_unique_citations must be a positive integer, got {self.strong_min_unique_citations!r}"
            )
        for name in ("strong_min_integrity_rate", "moderate_min_integrity_rate"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number, got {value!r}")
            if not (0.0 <= float(value) <= 1.0):
                raise ValueError(f"{name} must be within [0.0, 1.0], got {value!r}")
        if self.moderate_min_integrity_rate > self.strong_min_integrity_rate:
            raise ValueError("moderate_min_integrity_rate must not exceed strong_min_integrity_rate")

    @property
    def signature(self) -> str:
        return (
            f"safety-policy-config:v{self.schema_version}:"
            f"require_citation={self.require_at_least_one_valid_citation}:"
            f"strong_count={self.strong_min_unique_citations}:"
            f"strong_rate={self.strong_min_integrity_rate}:"
            f"moderate_rate={self.moderate_min_integrity_rate}"
        )


@dataclass(frozen=True)
class SafetyDecision:
    """
    The Phase 13 deliverable (docs Section G). Invariants enforced every
    time, mirroring Phase 9/11/12's own discipline:

    - `safety_status` is one of `SAFETY_STATUSES`.
    - `reason_code` is permitted for that status (`STATUS_REASON_CODES`).
    - `abstained == (safety_status == "ABSTAIN")`.
    - `escalation_required == (safety_status == "ESCALATE")`.
    - `engineering_signal_band == "NOT_APPLICABLE"` unless
      `safety_status == "SAFE_TO_PRESENT"` - no engineering signal is
      ever computed or exposed for a response that was not presented.

    `synthetic` is `Optional[bool]`: `None` means "not known" (no
    `GroundedResponse` was supplied to inspect), never defaulted to
    `False` - defaulting to "not synthetic" when genuinely unknown would
    itself be an unsupported claim.
    """

    schema_version: str
    decision_id: str
    input_id: str
    safety_status: str
    reason_code: str
    explanation: str
    engineering_signal_band: str
    hard_gate_results: list
    input_status_summary: dict
    abstained: bool
    escalation_required: bool
    synthetic: Optional[bool]
    config_signature: str

    def __post_init__(self):
        for name in ("schema_version", "decision_id", "input_id", "config_signature"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")

        if self.safety_status not in SAFETY_STATUSES:
            raise ValueError(f"safety_status must be one of {sorted(SAFETY_STATUSES)}, got {self.safety_status!r}")
        if self.reason_code not in STATUS_REASON_CODES[self.safety_status]:
            raise ValueError(
                f"reason_code {self.reason_code!r} is not permitted for safety_status {self.safety_status!r} "
                f"(allowed: {sorted(STATUS_REASON_CODES[self.safety_status])})"
            )

        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise ValueError("explanation must be a non-empty string")

        if self.engineering_signal_band not in ENGINEERING_SIGNAL_BANDS:
            raise ValueError(
                f"engineering_signal_band must be one of {sorted(ENGINEERING_SIGNAL_BANDS)}, "
                f"got {self.engineering_signal_band!r}"
            )
        is_safe = self.safety_status == "SAFE_TO_PRESENT"
        if not is_safe and self.engineering_signal_band != "NOT_APPLICABLE":
            raise ValueError("engineering_signal_band must be NOT_APPLICABLE unless safety_status == SAFE_TO_PRESENT")
        if is_safe and self.engineering_signal_band == "NOT_APPLICABLE":
            raise ValueError("a SAFE_TO_PRESENT decision must carry a real engineering_signal_band")

        if not isinstance(self.hard_gate_results, list) or any(not isinstance(x, str) for x in self.hard_gate_results) or not self.hard_gate_results:
            raise ValueError("hard_gate_results must be a non-empty list of strings")
        if not isinstance(self.input_status_summary, dict):
            raise ValueError("input_status_summary must be a dict")

        if not isinstance(self.abstained, bool):
            raise ValueError("abstained must be a bool")
        if self.abstained != (self.safety_status == "ABSTAIN"):
            raise ValueError("abstained must be true if and only if safety_status == ABSTAIN")
        if not isinstance(self.escalation_required, bool):
            raise ValueError("escalation_required must be a bool")
        if self.escalation_required != (self.safety_status == "ESCALATE"):
            raise ValueError("escalation_required must be true if and only if safety_status == ESCALATE")

        if self.synthetic is not None and not isinstance(self.synthetic, bool):
            raise ValueError("synthetic must be a bool or None")
