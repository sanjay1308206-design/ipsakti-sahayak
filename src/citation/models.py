"""
Phase 9 citation-validation data shapes
(docs/PHASE_09_CITATION_VALIDATION.md Sections F, G, H, I).

Pure data holders only - no I/O, no evidence resolution logic here (that
lives in validator.py), matching the src/evidence/models.py convention.

Two deliberately different trust postures, both documented here and in
docs Section F/G/T:

- `CitationReference` is the UNTRUSTED-INPUT shape: conceptually "what an
  LLM-generated citation reference looks like before validation" (docs
  "IMPORTANT TRUST BOUNDARY"). It intentionally performs NO validation in
  `__post_init__` - a malformed evidence_id (None, empty, wrong type) is a
  legitimate value to construct, because classifying it (VALID/INVALID/
  UNRESOLVED, with a reason code) is the validator's job, not the
  container's. This is a deliberate, documented deviation from Phase 8's
  `CitationTarget` (which IS validated at construction, because it is a
  backend-owned, already-trusted lookup key, never untrusted LLM output).

- `CitationValidationResult` is the TRUSTED-OUTPUT shape: the validator's
  own deterministic answer. It IS validated at construction, exactly like
  Phase 8's `Evidence` - its invariants (status/reason_code consistency,
  resolved-evidence-only-on-VALID) are enforced every time, never
  optional.

Nothing in this module ever stores a generated legal conclusion, a
generated answer, or a generated claim - there is no field on any
dataclass here that could hold one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

CITATION_REFERENCE_SCHEMA_VERSION = "1.0.0"
CITATION_RESULT_SCHEMA_VERSION = "1.0.0"

# Closed vocabulary of citation reference schema versions this validator
# knows how to interpret. A reference declaring any other value is
# reported INVALID/SCHEMA_MISMATCH - never silently accepted, never
# silently upgraded/downgraded.
SUPPORTED_CITATION_REFERENCE_SCHEMA_VERSIONS = frozenset({CITATION_REFERENCE_SCHEMA_VERSION})

# Closed status vocabulary (docs Section H). Exactly these three values -
# never a fourth ad hoc status invented ad lib elsewhere in the codebase.
CITATION_STATUSES = frozenset({"VALID", "INVALID", "UNRESOLVED"})

# Closed reason-code vocabulary (docs Section I). Only codes that are
# actually reachable by validator.py are defined here - "duplicate
# citation" and "synthetic evidence" are deliberately NOT reason codes:
# neither condition is, by itself, a validation failure (docs Section
# O/S; see also the explicit instruction not to treat synthetic evidence
# as automatically invalid). "unsupported_reference_type" is also
# deliberately absent - Phase 8/9 currently define exactly one evidence
# type ("CHUNK") and exactly one way to reference it (by evidence_id), so
# there is no second reference "type" to be unsupported yet.
REASON_EVIDENCE_ID_MISSING = "EVIDENCE_ID_MISSING"
REASON_MALFORMED_REFERENCE = "MALFORMED_REFERENCE"
REASON_SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
REASON_EVIDENCE_NOT_FOUND = "EVIDENCE_NOT_FOUND"
REASON_INVALID_PACK = "INVALID_PACK"
REASON_EVIDENCE_INTEGRITY_FAILURE = "EVIDENCE_INTEGRITY_FAILURE"
REASON_EVIDENCE_PROVENANCE_FAILURE = "EVIDENCE_PROVENANCE_FAILURE"

CITATION_REASON_CODES = frozenset(
    {
        REASON_EVIDENCE_ID_MISSING,
        REASON_MALFORMED_REFERENCE,
        REASON_SCHEMA_MISMATCH,
        REASON_EVIDENCE_NOT_FOUND,
        REASON_INVALID_PACK,
        REASON_EVIDENCE_INTEGRITY_FAILURE,
        REASON_EVIDENCE_PROVENANCE_FAILURE,
    }
)


class CitationSchemaError(ValueError):
    """Raised when serialized citation-validation data is malformed or structurally inconsistent."""


@dataclass(frozen=True)
class CitationReference:
    """
    The untrusted input shape (docs Section F): conceptually "a citation
    reference as it arrives from a generated claim", before validation.

    Deliberately NOT validated in __post_init__ - see module docstring.
    `evidence_id` is typed Optional[str] but nothing prevents constructing
    one with a non-string value (None, an int, a list, ...); validator.py
    is responsible for classifying every such case deterministically,
    never this constructor. `citation_ref_id` and `display_order` are
    inert display/ordering metadata only - never used for evidence
    identity, resolution, or any validator behavior.
    """

    evidence_id: Optional[str] = None
    schema_version: str = CITATION_REFERENCE_SCHEMA_VERSION
    citation_ref_id: Optional[str] = None
    display_order: Optional[int] = None


@dataclass(frozen=True)
class ResolvedEvidenceSummary:
    """
    Evidence identity information "where safely available" (docs Section
    G) - populated ONLY when the referenced Evidence has passed integrity
    verification (validator.py never exposes fields from an object it has
    not just verified). Never carries evidence_text, a legal conclusion,
    or anything beyond stable provenance identifiers - deliberately a
    strict subset of Phase 8's `Evidence`, not a duplicate of it.
    """

    evidence_id: str
    chunk_id: str
    document_id: str
    source_family_id: str
    jurisdiction: str
    synthetic: bool

    def __post_init__(self):
        for name in ("evidence_id", "chunk_id", "document_id", "source_family_id", "jurisdiction"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.synthetic, bool):
            raise ValueError("synthetic must be a bool")


@dataclass(frozen=True)
class CitationValidationResult:
    """
    The validator's deterministic, trusted output (docs Section G).
    Exactly one of VALID/INVALID/UNRESOLVED. Invariants enforced every
    time, unlike `CitationReference`:

    - status must be one of CITATION_STATUSES.
    - status == VALID  <=>  reason_code is None  <=>  resolved_evidence is not None.
    - status != VALID  =>  reason_code is one of CITATION_REASON_CODES.

    Never contains a generated legal conclusion, an answer, or a claim -
    no such field exists on this dataclass.
    """

    citation_reference: CitationReference
    status: str
    reason_code: Optional[str]
    requested_evidence_id: Optional[str]
    resolved_evidence: Optional[ResolvedEvidenceSummary]
    occurrence_index: int
    is_duplicate_occurrence: bool
    detail: Optional[str]
    validator_schema_version: str = CITATION_RESULT_SCHEMA_VERSION

    def __post_init__(self):
        if not isinstance(self.citation_reference, CitationReference):
            raise ValueError("citation_reference must be a CitationReference instance")
        if self.status not in CITATION_STATUSES:
            raise ValueError(f"status must be one of {sorted(CITATION_STATUSES)}, got {self.status!r}")
        if self.status == "VALID":
            if self.reason_code is not None:
                raise ValueError("a VALID result must not carry a reason_code")
            if self.resolved_evidence is None:
                raise ValueError("a VALID result must carry resolved_evidence")
        else:
            if self.reason_code not in CITATION_REASON_CODES:
                raise ValueError(
                    f"a non-VALID result must carry a reason_code from {sorted(CITATION_REASON_CODES)}, "
                    f"got {self.reason_code!r}"
                )
            if self.resolved_evidence is not None:
                raise ValueError(
                    "a non-VALID result must not carry resolved_evidence - evidence identity is only "
                    "exposed once it has been verified"
                )
        if not isinstance(self.resolved_evidence, (ResolvedEvidenceSummary, type(None))):
            raise ValueError("resolved_evidence must be a ResolvedEvidenceSummary or None")
        if self.requested_evidence_id is not None and not isinstance(self.requested_evidence_id, str):
            raise ValueError("requested_evidence_id must be a string or None")
        if isinstance(self.occurrence_index, bool) or not isinstance(self.occurrence_index, int) or self.occurrence_index < 0:
            raise ValueError(f"occurrence_index must be a non-negative integer, got {self.occurrence_index!r}")
        if not isinstance(self.is_duplicate_occurrence, bool):
            raise ValueError("is_duplicate_occurrence must be a bool")
        if self.detail is not None and not isinstance(self.detail, str):
            raise ValueError("detail must be a string or None")
        if not isinstance(self.validator_schema_version, str) or not self.validator_schema_version.strip():
            raise ValueError("validator_schema_version must be a non-empty string")
