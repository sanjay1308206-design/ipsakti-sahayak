"""
Phase 10 grounded-generation data shapes
(docs/PHASE_10_GROUNDED_GENERATION.md Sections D, E, F, K, L, N).

Pure data holders only - no I/O, no prompt construction, no provider
calls, no citation resolution here (those live in prompts.py/providers.py/
grounding.py/generator.py), matching the src/evidence/models.py and
src/citation/models.py convention.

Reuses Phase 9's `citation.metrics.CitationCoverageMetrics` directly for
`GroundedResponse.citation_validation_summary` - never a second,
independently-invented coverage representation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from citation.metrics import CitationCoverageMetrics

GENERATION_SCHEMA_VERSION = "1.0.0"

# Closed status vocabulary (docs Section N). Exactly these three values -
# "Do not invent unnecessary status values."
GROUNDING_STATUSES = frozenset({"GROUNDED", "ABSTAINED", "GENERATION_FAILED"})

# Closed abstention-reason vocabulary. NO_EVIDENCE_AVAILABLE: the
# EvidencePack had no usable evidence (empty, or itself failed Phase 9's
# pack-validity check) - the provider is never even called. NO_VALID_CITATIONS_PRODUCED:
# the provider produced output, but zero of its claimed citations survived
# Phase 9 validation - a conservative, deterministic stand-in for "the
# answer isn't verifiably grounded in anything," WITHOUT deciding whether
# the evidence text actually semantically supports the claim (docs
# Section Q's Phase 9 boundary, inherited here - Phase 10 does not judge
# whether the text is "correct," only whether it cites real, valid
# evidence).
REASON_NO_EVIDENCE_AVAILABLE = "NO_EVIDENCE_AVAILABLE"
REASON_NO_VALID_CITATIONS_PRODUCED = "NO_VALID_CITATIONS_PRODUCED"
ABSTENTION_REASONS = frozenset({REASON_NO_EVIDENCE_AVAILABLE, REASON_NO_VALID_CITATIONS_PRODUCED})

# Provider output metadata must never carry credential-shaped keys - a
# structural guarantee, not just a policy statement (docs Section S).
# Deliberately NOT a bare "token" substring - "tokens_used"/"prompt_tokens"/
# "completion_tokens" are common, entirely legitimate LLM usage metadata
# fields, not credentials; only the more specific auth/access-token and
# bearer-token shapes are blocked.
_FORBIDDEN_METADATA_KEY_SUBSTRINGS = (
    "api_key",
    "apikey",
    "credential",
    "secret",
    "password",
    "access_token",
    "auth_token",
    "bearer",
)


class GenerationSchemaError(ValueError):
    """Raised when serialized Phase 10 data is malformed or structurally inconsistent."""


def _check_no_credential_shaped_keys(metadata: dict, *, owner: str) -> None:
    for key in metadata:
        if not isinstance(key, str):
            raise ValueError(f"{owner} metadata keys must be strings, got {key!r}")
        lowered = key.lower()
        for forbidden in _FORBIDDEN_METADATA_KEY_SUBSTRINGS:
            if forbidden in lowered:
                raise ValueError(f"{owner} metadata key {key!r} looks credential-shaped and is forbidden")


@dataclass(frozen=True)
class GenerationConfig:
    """
    Explicit, documented generation-orchestration parameters (mirrors
    Phase 8's `EvidenceSelectionConfig` convention - every parameter
    explicit, no hidden default buried in a function body).

    `require_citations`: if True (the default, conservative choice), a
    provider output with zero VALID citations is downgraded to
    ABSTAINED/NO_VALID_CITATIONS_PRODUCED rather than presented as
    GROUNDED - this is how "unsupported claims are detected/rejected"
    (CAP-10) is satisfied deterministically, without deciding whether the
    evidence actually semantically supports the claim.

    `max_evidence_items_in_prompt`: None means every item in the supplied
    EvidencePack is included in the prompt; otherwise the prompt is built
    from only the first N items in the pack's own existing order (never
    re-ranked, never re-selected - that would duplicate Phase 8's own
    selection logic).
    """

    schema_version: str = GENERATION_SCHEMA_VERSION
    require_citations: bool = True
    max_evidence_items_in_prompt: Optional[int] = None

    def __post_init__(self):
        if not isinstance(self.schema_version, str) or not self.schema_version.strip():
            raise ValueError("schema_version must be a non-empty string")
        if not isinstance(self.require_citations, bool):
            raise ValueError("require_citations must be a bool")
        if self.max_evidence_items_in_prompt is not None and (
            isinstance(self.max_evidence_items_in_prompt, bool)
            or not isinstance(self.max_evidence_items_in_prompt, int)
            or self.max_evidence_items_in_prompt < 1
        ):
            raise ValueError(
                f"max_evidence_items_in_prompt must be a positive integer or None, "
                f"got {self.max_evidence_items_in_prompt!r}"
            )


@dataclass(frozen=True)
class GenerationOutput:
    """
    A provider's raw output (docs Section K). `raw_text` is verbatim -
    never parsed for meaning here (citation-marker extraction happens in
    grounding.py, over this same raw text, never over evidence_text).

    `metadata` is opaque, provider-specific (e.g. a token count) and
    structurally forbidden from carrying anything credential-shaped -
    enforced here, not merely documented, because this is the exact
    boundary where a real (currently undeployed) provider adapter's
    output would enter this system.
    """

    raw_text: str
    provider_name: str
    model_identifier: str
    success: bool
    failure_reason: Optional[str]
    metadata: dict

    def __post_init__(self):
        if not isinstance(self.raw_text, str):
            raise ValueError("raw_text must be a string")
        if not isinstance(self.provider_name, str) or not self.provider_name.strip():
            raise ValueError("provider_name must be a non-empty string")
        if not isinstance(self.model_identifier, str) or not self.model_identifier.strip():
            raise ValueError("model_identifier must be a non-empty string")
        if not isinstance(self.success, bool):
            raise ValueError("success must be a bool")
        if self.success and self.failure_reason is not None:
            raise ValueError("a successful GenerationOutput must not carry a failure_reason")
        if not self.success and (not isinstance(self.failure_reason, str) or not self.failure_reason.strip()):
            raise ValueError("a failed GenerationOutput must carry a non-empty failure_reason")
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dict")
        _check_no_credential_shaped_keys(self.metadata, owner="GenerationOutput")


@dataclass(frozen=True)
class GroundedResponse:
    """
    The Phase 10 deliverable (docs Section E/N). Exactly one of
    GROUNDED/ABSTAINED/GENERATION_FAILED. Invariants enforced every time
    (mirrors Phase 9's `CitationValidationResult` discipline):

    - `abstained == (grounding_status == "ABSTAINED")`.
    - `answer_text is not None`  <=>  `grounding_status == "GROUNDED"` -
      an abstained or failed response never carries fabricated/partial
      answer text.
    - `abstention_reason` is set (from the closed vocabulary) iff status
      is ABSTAINED; `failure_reason` is set iff status is GENERATION_FAILED.
    - `cited_evidence_ids` is non-empty only when GROUNDED, contains no
      duplicates, and (by construction in generator.py) every ID in it
      already passed Phase 9 validation - never a raw, unvalidated model
      claim.

    `citation_validation_summary` reuses Phase 9's own
    `CitationCoverageMetrics` unchanged - never a second, competing
    coverage representation, and never described as legal correctness
    (docs Section Q, inherited from Phase 9).
    """

    schema_version: str
    response_id: str
    query: str
    canonical_query: Optional[str]
    answer_text: Optional[str]
    cited_evidence_ids: list
    citation_validation_summary: CitationCoverageMetrics
    grounding_status: str
    abstained: bool
    abstention_reason: Optional[str]
    failure_reason: Optional[str]
    provider_name: str
    model_identifier: str
    generation_metadata: dict
    synthetic: bool
    evidence_pack_id: str

    def __post_init__(self):
        if self.grounding_status not in GROUNDING_STATUSES:
            raise ValueError(f"grounding_status must be one of {sorted(GROUNDING_STATUSES)}, got {self.grounding_status!r}")
        if not isinstance(self.abstained, bool):
            raise ValueError("abstained must be a bool")
        if self.abstained != (self.grounding_status == "ABSTAINED"):
            raise ValueError("abstained must be True if and only if grounding_status is ABSTAINED")

        is_grounded = self.grounding_status == "GROUNDED"
        if (self.answer_text is not None) != is_grounded:
            raise ValueError("answer_text must be set if and only if grounding_status is GROUNDED")
        if self.answer_text is not None and not isinstance(self.answer_text, str):
            raise ValueError("answer_text must be a string or None")

        if self.grounding_status == "ABSTAINED":
            if self.abstention_reason not in ABSTENTION_REASONS:
                raise ValueError(
                    f"an ABSTAINED response must carry an abstention_reason from {sorted(ABSTENTION_REASONS)}, "
                    f"got {self.abstention_reason!r}"
                )
        elif self.abstention_reason is not None:
            raise ValueError("abstention_reason must be None unless grounding_status is ABSTAINED")

        if self.grounding_status == "GENERATION_FAILED":
            if not isinstance(self.failure_reason, str) or not self.failure_reason.strip():
                raise ValueError("a GENERATION_FAILED response must carry a non-empty failure_reason")
        elif self.failure_reason is not None:
            raise ValueError("failure_reason must be None unless grounding_status is GENERATION_FAILED")

        if not isinstance(self.cited_evidence_ids, list) or any(not isinstance(x, str) for x in self.cited_evidence_ids):
            raise ValueError("cited_evidence_ids must be a list of strings")
        if len(self.cited_evidence_ids) != len(set(self.cited_evidence_ids)):
            raise ValueError("cited_evidence_ids must not contain duplicates")
        if not is_grounded and self.cited_evidence_ids:
            raise ValueError("only a GROUNDED response may carry cited_evidence_ids")

        if not isinstance(self.citation_validation_summary, CitationCoverageMetrics):
            raise ValueError("citation_validation_summary must be a CitationCoverageMetrics instance")

        for name in ("schema_version", "query", "provider_name", "model_identifier", "evidence_pack_id", "response_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if self.canonical_query is not None and not isinstance(self.canonical_query, str):
            raise ValueError("canonical_query must be a string or None")
        if not isinstance(self.synthetic, bool):
            raise ValueError("synthetic must be a bool")
        if not isinstance(self.generation_metadata, dict):
            raise ValueError("generation_metadata must be a dict")
