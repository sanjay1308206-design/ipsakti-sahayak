"""
Phase 14 multilingual-delivery data shapes
(docs/PHASE_14_MULTILINGUAL_DELIVERY.md Sections E, F, G, H, I).

CRITICAL DISTINCTIONS preserved throughout this module, per explicit
instruction:

1. SCRIPT vs LANGUAGE - `SCRIPT_TAGS` is a deterministic, purely
   Unicode-codepoint-range-based classification (never a language
   claim); `SUPPORTED_LANGUAGE_TAGS` is a small, explicitly-scoped set of
   language identifiers this project's OWN test fixtures have exercised
   at the plumbing level only - detecting Devanagari script never implies
   the language is Hindi, and detecting Tamil script never implies a
   particular jurisdiction.
2. LANGUAGE vs JURISDICTION - nothing in this module, or anywhere in
   `src/multilingual/`, maps a language or script onto a jurisdiction
   value. Phase 12's `JurisdictionDecision` is only ever read/passed
   through, never re-derived from language.
3. TRANSLATED TEXT vs TRUSTED METADATA - `MultilingualDeliveryResult`
   carries `answer_text` (a display string a translation provider may
   freely produce) completely separately from `cited_evidence_ids`/
   `grounding_status`/`safety_status` (always a direct, unmodified
   passthrough from the real upstream Phase 9/10/13 objects, never
   re-derived from provider output).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

MULTILINGUAL_SCHEMA_VERSION = "1.0.0"

# Deterministic, Unicode-codepoint-range-based SCRIPT classification only
# (docs Section F) - never a language identification claim.
SCRIPT_TAGS = frozenset({"LATIN", "DEVANAGARI", "TAMIL", "MIXED", "UNKNOWN"})

# [OUR ENHANCEMENT] A small, explicitly-scoped LANGUAGE vocabulary -
# exactly the languages this project's own prior-phase test fixtures have
# exercised at the Unicode-plumbing level (English, Hindi, Tamil). This is
# NOT a claim of validated translation quality for any of them (docs
# Section P) and is NOT the Master Reference's own language list (the
# Master Reference names no specific language set - only Bhashini as the
# adapter direction, "evaluate only supported languages"). `UNSPECIFIED`
# means "no language was requested" - it is always accepted, and never
# triggers translation.
SUPPORTED_LANGUAGE_TAGS = frozenset({"en", "hi", "ta"})
UNSPECIFIED_LANGUAGE = "UNSPECIFIED"

# Closed delivery-status vocabulary (docs Section H/I). Reused pattern
# from Phase 9/10/13's own closed-status-plus-reason-code convention.
DELIVERY_STATUSES = frozenset({"DELIVERED", "TRANSLATION_FAILED", "UNSUPPORTED_LANGUAGE", "UPSTREAM_BLOCKED"})

REASON_LANGUAGE_UNSPECIFIED = "LANGUAGE_UNSPECIFIED_NO_TRANSLATION_NEEDED"
REASON_SOURCE_MATCHES_REQUESTED = "SOURCE_MATCHES_REQUESTED_NO_TRANSLATION_NEEDED"
REASON_TRANSLATION_SUCCEEDED = "TRANSLATION_SUCCEEDED"
REASON_MISSING_TRANSLATION_PROVIDER = "MISSING_TRANSLATION_PROVIDER"
REASON_TRANSLATION_PROVIDER_FAILED = "TRANSLATION_PROVIDER_FAILED"
REASON_UNSUPPORTED_LANGUAGE_REQUESTED = "UNSUPPORTED_LANGUAGE_REQUESTED"
REASON_SAFETY_NOT_SAFE_TO_PRESENT = "SAFETY_NOT_SAFE_TO_PRESENT"
REASON_GROUNDING_NOT_GROUNDED = "GROUNDING_NOT_GROUNDED"

MULTILINGUAL_REASON_CODES = frozenset(
    {
        REASON_LANGUAGE_UNSPECIFIED,
        REASON_SOURCE_MATCHES_REQUESTED,
        REASON_TRANSLATION_SUCCEEDED,
        REASON_MISSING_TRANSLATION_PROVIDER,
        REASON_TRANSLATION_PROVIDER_FAILED,
        REASON_UNSUPPORTED_LANGUAGE_REQUESTED,
        REASON_SAFETY_NOT_SAFE_TO_PRESENT,
        REASON_GROUNDING_NOT_GROUNDED,
    }
)

STATUS_REASON_CODES = {
    "DELIVERED": frozenset({REASON_LANGUAGE_UNSPECIFIED, REASON_SOURCE_MATCHES_REQUESTED, REASON_TRANSLATION_SUCCEEDED}),
    "TRANSLATION_FAILED": frozenset({REASON_MISSING_TRANSLATION_PROVIDER, REASON_TRANSLATION_PROVIDER_FAILED}),
    "UNSUPPORTED_LANGUAGE": frozenset({REASON_UNSUPPORTED_LANGUAGE_REQUESTED}),
    "UPSTREAM_BLOCKED": frozenset({REASON_SAFETY_NOT_SAFE_TO_PRESENT, REASON_GROUNDING_NOT_GROUNDED}),
}

# Always the only value - a structural, machine-checkable audit field
# (mirrors Phase 11's fixed `disclaimer` pattern) proving evidence was
# never touched, never a genuinely-variable state (docs Section R).
EVIDENCE_PRESERVATION_STATUSES = frozenset({"PRESERVED"})

# Provider output metadata must never carry credential-shaped keys -
# reused verbatim from Phase 10's own GenerationOutput guard.
_FORBIDDEN_METADATA_KEY_SUBSTRINGS = ("api_key", "apikey", "credential", "secret", "password", "access_token", "auth_token", "bearer")


class MultilingualSchemaError(ValueError):
    """Raised when serialized Phase 14 multilingual data is malformed or structurally inconsistent."""


def _check_no_credential_shaped_keys(metadata: dict, *, owner: str) -> None:
    for key in metadata:
        if not isinstance(key, str):
            raise ValueError(f"{owner} metadata keys must be strings, got {key!r}")
        lowered = key.lower()
        for forbidden in _FORBIDDEN_METADATA_KEY_SUBSTRINGS:
            if forbidden in lowered:
                raise ValueError(f"{owner} metadata key {key!r} looks credential-shaped and is forbidden")


@dataclass(frozen=True)
class MultilingualConfig:
    """Explicit, documented configuration. `supported_language_tags` is overridable, never a hidden constant."""

    schema_version: str = MULTILINGUAL_SCHEMA_VERSION
    supported_language_tags: frozenset = SUPPORTED_LANGUAGE_TAGS

    def __post_init__(self):
        if not isinstance(self.schema_version, str) or not self.schema_version.strip():
            raise ValueError("schema_version must be a non-empty string")
        if not isinstance(self.supported_language_tags, frozenset) or any(
            not isinstance(x, str) or not x.strip() for x in self.supported_language_tags
        ):
            raise ValueError("supported_language_tags must be a frozenset of non-empty strings")

    @property
    def signature(self) -> str:
        return f"multilingual-config:v{self.schema_version}:languages={sorted(self.supported_language_tags)}"


@dataclass(frozen=True)
class TranslationOutput:
    """
    A provider's raw output (docs Section M/O). `translated_text` is a
    display string only - never parsed for citation markers, jurisdiction
    words, or any other structured meaning anywhere downstream (docs
    Section Z, the adversarial-translation invariant).
    """

    translated_text: str
    provider_name: str
    source_language: str
    target_language: str
    success: bool
    failure_reason: Optional[str]
    metadata: dict

    def __post_init__(self):
        if not isinstance(self.translated_text, str):
            raise ValueError("translated_text must be a string")
        for name in ("provider_name", "source_language", "target_language"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.success, bool):
            raise ValueError("success must be a bool")
        if self.success and self.failure_reason is not None:
            raise ValueError("a successful TranslationOutput must not carry a failure_reason")
        if not self.success and (not isinstance(self.failure_reason, str) or not self.failure_reason.strip()):
            raise ValueError("a failed TranslationOutput must carry a non-empty failure_reason")
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dict")
        _check_no_credential_shaped_keys(self.metadata, owner="TranslationOutput")


@dataclass(frozen=True)
class MultilingualInputContext:
    """
    The input-side preservation record (docs Section J/K/L). `original_query`
    is always recoverable, byte/character-faithful, and never overwritten.
    `canonical_query` is Unicode NFC normalization ONLY - never a
    translation, never a rewrite of meaning (docs Section L).
    `detected_script` is a SCRIPT classification only (Section F);
    `requested_language` is an untrusted, permissive input (like Phase
    9's `CitationReference`) - unvalidated here, classified as
    supported/unsupported only later, in `delivery.deliver_response`.
    """

    schema_version: str
    input_id: str
    original_query: str
    canonical_query: str
    detected_script: str
    requested_language: Optional[str]

    def __post_init__(self):
        if not isinstance(self.schema_version, str) or not self.schema_version.strip():
            raise ValueError("schema_version must be a non-empty string")
        if not isinstance(self.input_id, str) or not self.input_id.strip():
            raise ValueError("input_id must be a non-empty string")
        if not isinstance(self.original_query, str):
            raise ValueError("original_query must be a string")
        if not isinstance(self.canonical_query, str):
            raise ValueError("canonical_query must be a string")
        if self.detected_script not in SCRIPT_TAGS:
            raise ValueError(f"detected_script must be one of {sorted(SCRIPT_TAGS)}, got {self.detected_script!r}")
        if self.requested_language is not None and not isinstance(self.requested_language, str):
            raise ValueError("requested_language must be a string or None")


@dataclass(frozen=True)
class MultilingualDeliveryResult:
    """
    The Phase 14 deliverable (docs Section I). Every security-critical
    field (`cited_evidence_ids`, `grounding_status`, `safety_status`,
    `synthetic`) is a direct, unmodified passthrough from the real
    upstream Phase 9/10/13 objects - there is no code path anywhere in
    this dataclass or its construction that derives them from
    `answer_text`/translation-provider output.
    """

    schema_version: str
    result_id: str
    input_id: str
    original_query: str
    canonical_query: str
    requested_language: Optional[str]
    detected_script: str
    delivery_status: str
    reason_code: str
    explanation: str
    answer_text: Optional[str]
    answer_language: Optional[str]
    translation_applied: bool
    provider_name: Optional[str]
    cited_evidence_ids: list
    grounding_status: Optional[str]
    safety_status: Optional[str]
    evidence_preservation_status: str
    synthetic: Optional[bool]
    delivery_metadata: dict
    config_signature: str

    def __post_init__(self):
        for name in ("schema_version", "result_id", "input_id", "config_signature", "reason_code"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.original_query, str):
            raise ValueError("original_query must be a string")
        if not isinstance(self.canonical_query, str):
            raise ValueError("canonical_query must be a string")
        if self.requested_language is not None and not isinstance(self.requested_language, str):
            raise ValueError("requested_language must be a string or None")
        if self.detected_script not in SCRIPT_TAGS:
            raise ValueError(f"detected_script must be one of {sorted(SCRIPT_TAGS)}, got {self.detected_script!r}")

        if self.delivery_status not in DELIVERY_STATUSES:
            raise ValueError(f"delivery_status must be one of {sorted(DELIVERY_STATUSES)}, got {self.delivery_status!r}")
        if self.reason_code not in STATUS_REASON_CODES[self.delivery_status]:
            raise ValueError(
                f"reason_code {self.reason_code!r} is not permitted for delivery_status {self.delivery_status!r} "
                f"(allowed: {sorted(STATUS_REASON_CODES[self.delivery_status])})"
            )
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise ValueError("explanation must be a non-empty string")

        is_delivered = self.delivery_status == "DELIVERED"
        if (self.answer_text is not None) != is_delivered:
            raise ValueError("answer_text must be set if and only if delivery_status == DELIVERED")
        if self.answer_text is not None and not isinstance(self.answer_text, str):
            raise ValueError("answer_text must be a string or None")
        if (self.answer_language is not None) != is_delivered:
            raise ValueError("answer_language must be set if and only if delivery_status == DELIVERED")
        if self.answer_language is not None and not isinstance(self.answer_language, str):
            raise ValueError("answer_language must be a string or None")

        if not isinstance(self.translation_applied, bool):
            raise ValueError("translation_applied must be a bool")
        if self.translation_applied and self.reason_code != REASON_TRANSLATION_SUCCEEDED:
            raise ValueError("translation_applied may be true only when reason_code == TRANSLATION_SUCCEEDED")

        if self.provider_name is not None and not isinstance(self.provider_name, str):
            raise ValueError("provider_name must be a string or None")

        if not isinstance(self.cited_evidence_ids, list) or any(not isinstance(x, str) for x in self.cited_evidence_ids):
            raise ValueError("cited_evidence_ids must be a list of strings")
        if len(self.cited_evidence_ids) != len(set(self.cited_evidence_ids)):
            raise ValueError("cited_evidence_ids must not contain duplicates")

        if self.grounding_status is not None and not isinstance(self.grounding_status, str):
            raise ValueError("grounding_status must be a string or None")
        if self.safety_status is not None and not isinstance(self.safety_status, str):
            raise ValueError("safety_status must be a string or None")

        if self.evidence_preservation_status not in EVIDENCE_PRESERVATION_STATUSES:
            raise ValueError(
                f"evidence_preservation_status must be one of {sorted(EVIDENCE_PRESERVATION_STATUSES)}, "
                f"got {self.evidence_preservation_status!r}"
            )
        if self.synthetic is not None and not isinstance(self.synthetic, bool):
            raise ValueError("synthetic must be a bool or None")
        if not isinstance(self.delivery_metadata, dict):
            raise ValueError("delivery_metadata must be a dict")
