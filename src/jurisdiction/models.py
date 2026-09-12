"""
Phase 12 jurisdiction-firewall data shapes
(docs/PHASE_12_JURISDICTION_FIREWALL.md Sections E, F, G, H).

CRITICAL DISTINCTION preserved throughout this module: this project
already has TWO separate, non-interchangeable jurisdiction vocabularies,
neither of which Phase 12 redefines:

1. `REQUEST_JURISDICTION_VALUES` - the REQUEST-side vocabulary, mirrored
   from `config/domain_taxonomy.yaml`'s `jurisdiction_inputs` (Phase 1):
   `INDIA`, `INTERNATIONAL`, `BOTH`, `UNSPECIFIED`. This describes what a
   USER is asking about - `BOTH` is a legitimate resolved value ("the
   question spans both"), not an error.

2. `EVIDENCE_JURISDICTION_VALUES` - the EVIDENCE-side vocabulary, mirrored
   from `config/authority_matrix.yaml`'s `valid_jurisdictions` (Phase 2):
   `INDIA`, `INTERNATIONAL`, `NOT_APPLICABLE`, `OTHER_UNSPECIFIED`. This
   describes what a single Evidence object's `jurisdiction` field may
   legitimately be tagged with - no evidence document is ever "BOTH".

Phase 12's whole job is to deterministically map (1) onto a permitted
subset of (2), never to invent a third vocabulary or collapse these two
together.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

JURISDICTION_SCHEMA_VERSION = "1.0.0"

# Mirrors config/domain_taxonomy.yaml jurisdiction_inputs exactly - cross-
# checked for drift by tests/test_phase_12_regression.py.
REQUEST_JURISDICTION_VALUES = frozenset({"INDIA", "INTERNATIONAL", "BOTH", "UNSPECIFIED"})

# Mirrors config/authority_matrix.yaml valid_jurisdictions exactly - cross-
# checked for drift by tests/test_phase_12_regression.py.
EVIDENCE_JURISDICTION_VALUES = frozenset({"INDIA", "INTERNATIONAL", "NOT_APPLICABLE", "OTHER_UNSPECIFIED"})

# Reused wholesale from Phase 1 (docs/PHASE_01_DOMAIN_TAXONOMY.md Section
# H) - no parallel state system is invented. NEEDS_EVIDENCE is retained
# for vocabulary consistency but is DOCUMENTED AS CURRENTLY UNREACHABLE
# (docs Section F/W): no reason code maps to it, and no code path in this
# phase ever constructs one - there is no scenario in this project's
# actual contracts where retrieving MORE evidence would help determine
# WHICH corpus is permitted (that determination is either immediate from
# the input signal or blocked/unknown/ambiguous, never evidence-
# resolvable - resolving it would be circular).
JURISDICTION_STATES = frozenset({"KNOWN", "UNKNOWN", "AMBIGUOUS", "NEEDS_EVIDENCE"})

REASON_EXPLICIT_JURISDICTION_ACCEPTED = "EXPLICIT_JURISDICTION_ACCEPTED"
REASON_JURISDICTION_UNKNOWN = "JURISDICTION_UNKNOWN"
REASON_JURISDICTION_AMBIGUOUS = "JURISDICTION_AMBIGUOUS"
REASON_JURISDICTION_NOT_SUPPORTED = "JURISDICTION_NOT_SUPPORTED"
REASON_JURISDICTION_METADATA_INVALID = "JURISDICTION_METADATA_INVALID"
REASON_CORPUS_NOT_PERMITTED = "CORPUS_NOT_PERMITTED"
REASON_CROSS_JURISDICTION_EVIDENCE_BLOCKED = "CROSS_JURISDICTION_EVIDENCE_BLOCKED"

# Closed, and every member is independently reachable and tested
# (docs Section F). No "JURISDICTION_NEEDS_EVIDENCE" code exists - per the
# NEEDS_EVIDENCE unreachability note above, inventing a reason code with
# no reachable code path would violate "do not create dead reason codes."
JURISDICTION_REASON_CODES = frozenset(
    {
        REASON_EXPLICIT_JURISDICTION_ACCEPTED,
        REASON_JURISDICTION_UNKNOWN,
        REASON_JURISDICTION_AMBIGUOUS,
        REASON_JURISDICTION_NOT_SUPPORTED,
        REASON_JURISDICTION_METADATA_INVALID,
        REASON_CORPUS_NOT_PERMITTED,
        REASON_CROSS_JURISDICTION_EVIDENCE_BLOCKED,
    }
)

# Which reason codes are structurally permitted for each state - enforced
# in JurisdictionDecision.__post_init__. NEEDS_EVIDENCE maps to an empty
# set, making it genuinely unconstructable rather than silently allowed.
STATE_REASON_CODES = {
    "KNOWN": frozenset({REASON_EXPLICIT_JURISDICTION_ACCEPTED}),
    "UNKNOWN": frozenset(
        {REASON_JURISDICTION_UNKNOWN, REASON_JURISDICTION_NOT_SUPPORTED, REASON_JURISDICTION_METADATA_INVALID}
    ),
    "AMBIGUOUS": frozenset({REASON_JURISDICTION_AMBIGUOUS}),
    "NEEDS_EVIDENCE": frozenset(),
}


class JurisdictionSchemaError(ValueError):
    """Raised when serialized Phase 12 jurisdiction data is malformed or structurally inconsistent."""


@dataclass(frozen=True)
class JurisdictionFirewallConfig:
    """Explicit, documented firewall configuration. No knob currently changes routing behavior beyond schema_version; kept for forward compatibility and a stable, inspectable config_signature."""

    schema_version: str = JURISDICTION_SCHEMA_VERSION

    def __post_init__(self):
        if not isinstance(self.schema_version, str) or not self.schema_version.strip():
            raise ValueError("schema_version must be a non-empty string")

    @property
    def signature(self) -> str:
        return f"jurisdiction-firewall-config:v{self.schema_version}"


@dataclass(frozen=True)
class JurisdictionDecision:
    """
    The Phase 12 deliverable (docs Section H). `allowed_jurisdictions`/
    `blocked_jurisdictions` are always drawn from `EVIDENCE_JURISDICTION_VALUES`
    (the evidence-side vocabulary) and are always exact complements of one
    another over that vocabulary - `allowed_jurisdictions` is non-empty
    only when `state == "KNOWN"` (fail-closed by construction, never by
    convention alone).

    `allowed_corpora`/`blocked_corpora` are, in this repository today,
    definitionally identical to `allowed_jurisdictions`/`blocked_jurisdictions`
    - disclosed honestly (docs Section K/L): Phase 5-7 does not yet expose
    distinct named per-jurisdiction indices, so "corpus" and "jurisdiction"
    are not yet separate infrastructure concepts here. The field is
    retained for forward compatibility with the Master Reference's own
    architecture (separate indices per jurisdiction), not to imply
    infrastructure that does not exist.
    """

    schema_version: str
    decision_id: str
    input_id: str
    requested_jurisdiction: Optional[str]
    normalized_jurisdiction: Optional[str]
    state: str
    reason_code: str
    explanation: str
    allowed_jurisdictions: frozenset
    blocked_jurisdictions: frozenset
    allowed_corpora: frozenset
    blocked_corpora: frozenset
    requires_evidence: bool
    requires_escalation: bool
    basis: list
    config_signature: str

    def __post_init__(self):
        for name in ("schema_version", "decision_id", "input_id", "reason_code", "config_signature"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")

        if self.requested_jurisdiction is not None and not isinstance(self.requested_jurisdiction, str):
            raise ValueError("requested_jurisdiction must be a string or None")
        if self.normalized_jurisdiction is not None:
            if not isinstance(self.normalized_jurisdiction, str):
                raise ValueError("normalized_jurisdiction must be a string or None")
            if self.normalized_jurisdiction not in REQUEST_JURISDICTION_VALUES:
                raise ValueError(
                    f"normalized_jurisdiction must be a member of {sorted(REQUEST_JURISDICTION_VALUES)} or None, "
                    f"got {self.normalized_jurisdiction!r}"
                )

        if self.state not in JURISDICTION_STATES:
            raise ValueError(f"state must be one of {sorted(JURISDICTION_STATES)}, got {self.state!r}")
        if self.reason_code not in STATE_REASON_CODES[self.state]:
            raise ValueError(
                f"reason_code {self.reason_code!r} is not permitted for state {self.state!r} "
                f"(allowed: {sorted(STATE_REASON_CODES[self.state])})"
            )

        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise ValueError("explanation must be a non-empty string")

        for name in ("allowed_jurisdictions", "blocked_jurisdictions", "allowed_corpora", "blocked_corpora"):
            value = getattr(self, name)
            if not isinstance(value, frozenset) or any(not isinstance(x, str) for x in value):
                raise ValueError(f"{name} must be a frozenset of strings")
            if not value.issubset(EVIDENCE_JURISDICTION_VALUES):
                raise ValueError(f"{name} must be a subset of {sorted(EVIDENCE_JURISDICTION_VALUES)}, got {sorted(value)}")

        if self.allowed_jurisdictions | self.blocked_jurisdictions != EVIDENCE_JURISDICTION_VALUES:
            raise ValueError("allowed_jurisdictions and blocked_jurisdictions must together cover every evidence jurisdiction value")
        if self.allowed_jurisdictions & self.blocked_jurisdictions:
            raise ValueError("allowed_jurisdictions and blocked_jurisdictions must not overlap")
        if self.state != "KNOWN" and self.allowed_jurisdictions:
            raise ValueError("allowed_jurisdictions must be empty unless state == KNOWN - fail closed")
        if self.state == "KNOWN" and not self.allowed_jurisdictions:
            raise ValueError("a KNOWN decision must permit at least one evidence jurisdiction")

        if self.allowed_corpora != self.allowed_jurisdictions:
            raise ValueError("allowed_corpora must equal allowed_jurisdictions in this repository (docs Section K/L)")
        if self.blocked_corpora != self.blocked_jurisdictions:
            raise ValueError("blocked_corpora must equal blocked_jurisdictions in this repository (docs Section K/L)")

        if not isinstance(self.requires_evidence, bool):
            raise ValueError("requires_evidence must be a bool")
        if self.requires_evidence != (self.state == "NEEDS_EVIDENCE"):
            raise ValueError("requires_evidence must be true if and only if state == NEEDS_EVIDENCE")
        if not isinstance(self.requires_escalation, bool):
            raise ValueError("requires_escalation must be a bool")
        if self.requires_escalation != (self.state == "AMBIGUOUS"):
            raise ValueError("requires_escalation must be true if and only if state == AMBIGUOUS")

        if not isinstance(self.basis, list) or any(not isinstance(x, str) for x in self.basis) or not self.basis:
            raise ValueError("basis must be a non-empty list of strings")


@dataclass(frozen=True)
class EvidenceFilterResult:
    """
    Deterministic outcome of filtering a list of Evidence-shaped objects
    against a JurisdictionDecision (docs Section O). `allowed_evidence`
    preserves input order; `block_reasons` maps each blocked item's
    `evidence_id` to the specific reason it was excluded - never a silent
    drop.
    """

    schema_version: str
    decision_id: str
    total_count: int
    allowed_evidence: list
    blocked_evidence_ids: list
    block_reasons: dict

    def __post_init__(self):
        if not isinstance(self.schema_version, str) or not self.schema_version.strip():
            raise ValueError("schema_version must be a non-empty string")
        if not isinstance(self.decision_id, str) or not self.decision_id.strip():
            raise ValueError("decision_id must be a non-empty string")
        if isinstance(self.total_count, bool) or not isinstance(self.total_count, int) or self.total_count < 0:
            raise ValueError("total_count must be a non-negative integer")
        if not isinstance(self.allowed_evidence, list):
            raise ValueError("allowed_evidence must be a list")
        if not isinstance(self.blocked_evidence_ids, list) or any(not isinstance(x, str) for x in self.blocked_evidence_ids):
            raise ValueError("blocked_evidence_ids must be a list of strings")
        if len(self.allowed_evidence) + len(self.blocked_evidence_ids) != self.total_count:
            raise ValueError("allowed_evidence and blocked_evidence_ids counts must sum to total_count")
        if not isinstance(self.block_reasons, dict):
            raise ValueError("block_reasons must be a dict")
        if set(self.block_reasons.keys()) != set(self.blocked_evidence_ids):
            raise ValueError("block_reasons keys must exactly match blocked_evidence_ids")
        for reason in self.block_reasons.values():
            if reason not in JURISDICTION_REASON_CODES:
                raise ValueError(f"block_reasons values must be members of JURISDICTION_REASON_CODES, got {reason!r}")

    @property
    def allowed_count(self) -> int:
        return len(self.allowed_evidence)

    @property
    def blocked_count(self) -> int:
        return len(self.blocked_evidence_ids)
