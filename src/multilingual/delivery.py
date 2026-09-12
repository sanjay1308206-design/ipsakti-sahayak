"""
Phase 14 output-side orchestration (docs/PHASE_14_MULTILINGUAL_DELIVERY.md
Sections H, I, Q, R, S, T, U). The only place in this package that ties
an already-produced GroundedResponse (Phase 10) and SafetyDecision
(Phase 13) together with an optional translation attempt into one
deterministic, explainable MultilingualDeliveryResult.

Eight ordered, deterministic, first-match-wins gates (D2..D9, mirroring
D1's type-validation step), matching the exact "ordered rule list"
convention Phase 1/9/11/12/13 already established. Hard gates on
`safety_decision`/`grounded_response` are checked BEFORE any translation
is even attempted - an ABSTAIN/ESCALATE/GENERATION_FAILED/ABSTAINED
upstream result can never be "rescued" into a delivered answer by
translation.

CRITICAL: `cited_evidence_ids`, `grounding_status`, `safety_status`, and
`synthetic` are always copied directly from the real upstream objects.
`translation_provider.translate(...)`'s return value is consulted ONLY
for `translated_text` - never for any of those fields. This is the
structural (not merely documented) answer to the adversarial-translation
requirement (docs Section Z).
"""

from __future__ import annotations

import hashlib
from typing import Optional

from generation.models import GroundedResponse
from safety.models import SafetyDecision

from .models import (
    EVIDENCE_PRESERVATION_STATUSES,
    REASON_GROUNDING_NOT_GROUNDED,
    REASON_LANGUAGE_UNSPECIFIED,
    REASON_MISSING_TRANSLATION_PROVIDER,
    REASON_SAFETY_NOT_SAFE_TO_PRESENT,
    REASON_SOURCE_MATCHES_REQUESTED,
    REASON_TRANSLATION_PROVIDER_FAILED,
    REASON_TRANSLATION_SUCCEEDED,
    REASON_UNSUPPORTED_LANGUAGE_REQUESTED,
    UNSPECIFIED_LANGUAGE,
    MultilingualConfig,
    MultilingualDeliveryResult,
    MultilingualInputContext,
    TranslationOutput,
)
from .providers import TranslationProvider


def compute_result_id(
    schema_version: str,
    input_id: str,
    original_query: str,
    requested_language: Optional[str],
    delivery_status: str,
    reason_code: str,
    answer_text: Optional[str],
    config_signature: str,
) -> str:
    """Deterministic, backend-owned result identity - never a random UUID, never a timestamp."""
    canonical = "|".join(
        [
            "multilingual-delivery-v1",
            schema_version,
            input_id,
            original_query,
            requested_language or "",
            delivery_status,
            reason_code,
            answer_text or "",
            config_signature,
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_result(
    *,
    input_context: MultilingualInputContext,
    grounded_response: Optional[GroundedResponse],
    safety_decision: Optional[SafetyDecision],
    delivery_status: str,
    reason_code: str,
    explanation: str,
    answer_text: Optional[str],
    answer_language: Optional[str],
    translation_applied: bool,
    provider_name: Optional[str],
    delivery_metadata: dict,
    config: MultilingualConfig,
) -> MultilingualDeliveryResult:
    result_id = compute_result_id(
        config.schema_version, input_context.input_id, input_context.original_query, input_context.requested_language,
        delivery_status, reason_code, answer_text, config.signature,
    )
    return MultilingualDeliveryResult(
        schema_version=config.schema_version,
        result_id=result_id,
        input_id=input_context.input_id,
        original_query=input_context.original_query,
        canonical_query=input_context.canonical_query,
        requested_language=input_context.requested_language,
        detected_script=input_context.detected_script,
        delivery_status=delivery_status,
        reason_code=reason_code,
        explanation=explanation,
        answer_text=answer_text,
        answer_language=answer_language,
        translation_applied=translation_applied,
        provider_name=provider_name,
        # Always a direct passthrough - never re-derived from
        # answer_text/translated_text (docs Section Z).
        cited_evidence_ids=list(grounded_response.cited_evidence_ids) if grounded_response is not None else [],
        grounding_status=grounded_response.grounding_status if grounded_response is not None else None,
        safety_status=safety_decision.safety_status if safety_decision is not None else None,
        evidence_preservation_status=next(iter(EVIDENCE_PRESERVATION_STATUSES)),
        synthetic=grounded_response.synthetic if grounded_response is not None else None,
        delivery_metadata=delivery_metadata,
        config_signature=config.signature,
    )


def deliver_response(
    input_context: MultilingualInputContext,
    grounded_response: Optional[GroundedResponse] = None,
    safety_decision: Optional[SafetyDecision] = None,
    translation_provider: Optional[TranslationProvider] = None,
    source_language: Optional[str] = None,
    config: Optional[MultilingualConfig] = None,
) -> MultilingualDeliveryResult:
    """The sole Phase 14 output-side entry point. See module docstring for the eight-gate decision flow."""
    if not isinstance(input_context, MultilingualInputContext):
        raise TypeError(f"deliver_response expects input_context to be a MultilingualInputContext, got {type(input_context).__name__}")
    if grounded_response is not None and not isinstance(grounded_response, GroundedResponse):
        raise TypeError(f"deliver_response expects grounded_response to be a GroundedResponse or None, got {type(grounded_response).__name__}")
    if safety_decision is not None and not isinstance(safety_decision, SafetyDecision):
        raise TypeError(f"deliver_response expects safety_decision to be a SafetyDecision or None, got {type(safety_decision).__name__}")
    if translation_provider is not None and not isinstance(translation_provider, TranslationProvider):
        raise TypeError(
            f"deliver_response expects translation_provider to be a TranslationProvider or None, "
            f"got {type(translation_provider).__name__}"
        )
    if source_language is not None and not isinstance(source_language, str):
        raise TypeError(f"deliver_response expects source_language to be a string or None, got {type(source_language).__name__}")
    if config is None:
        config = MultilingualConfig()
    elif not isinstance(config, MultilingualConfig):
        raise TypeError(f"deliver_response expects config to be a MultilingualConfig or None, got {type(config).__name__}")

    def blocked(reason, explanation):
        return _build_result(
            input_context=input_context, grounded_response=grounded_response, safety_decision=safety_decision,
            delivery_status="UPSTREAM_BLOCKED", reason_code=reason, explanation=explanation, answer_text=None,
            answer_language=None, translation_applied=False, provider_name=None, delivery_metadata={}, config=config,
        )

    # D2 - SAFETY_NOT_SAFE_TO_PRESENT: Phase 13's own decision is never
    # overridden, and a missing SafetyDecision is treated the same as an
    # unsafe one - never optimistically assumed safe.
    if safety_decision is None or safety_decision.safety_status != "SAFE_TO_PRESENT":
        return blocked(
            REASON_SAFETY_NOT_SAFE_TO_PRESENT,
            "Blocked: no safety decision was supplied, or Phase 13 did not mark this response SAFE_TO_PRESENT - "
            "translation is never attempted on an abstained/escalated result.",
        )

    # D3 - GROUNDING_NOT_GROUNDED: Phase 10's own status is never
    # overridden, and a missing GroundedResponse is treated the same way.
    if grounded_response is None or grounded_response.grounding_status != "GROUNDED":
        return blocked(
            REASON_GROUNDING_NOT_GROUNDED,
            "Blocked: no grounded response was supplied, or Phase 10 did not mark it GROUNDED - translation is "
            "never attempted on an abstained/failed generation.",
        )

    requested_language = input_context.requested_language

    # D4 - UNSUPPORTED_LANGUAGE_REQUESTED
    if requested_language is not None and requested_language != UNSPECIFIED_LANGUAGE and requested_language not in config.supported_language_tags:
        return _build_result(
            input_context=input_context, grounded_response=grounded_response, safety_decision=safety_decision,
            delivery_status="UNSUPPORTED_LANGUAGE", reason_code=REASON_UNSUPPORTED_LANGUAGE_REQUESTED,
            explanation=(
                f"Unsupported language requested ({requested_language!r}); this system only recognizes "
                f"{sorted(config.supported_language_tags)} as delivery targets - none has validated translation "
                f"quality (see docs Section P)."
            ),
            answer_text=None, answer_language=None, translation_applied=False, provider_name=None,
            delivery_metadata={}, config=config,
        )

    # D5 - LANGUAGE_UNSPECIFIED_NO_TRANSLATION_NEEDED. `answer_language`
    # is honestly UNSPECIFIED here (never guessed) - Phase 10 does not
    # tell Phase 14 what language the generated answer is actually in;
    # `UNSPECIFIED_LANGUAGE` is used rather than `None` so the invariant
    # "answer_language is set iff DELIVERED" stays simple and exceptionless.
    if requested_language is None or requested_language == UNSPECIFIED_LANGUAGE:
        return _build_result(
            input_context=input_context, grounded_response=grounded_response, safety_decision=safety_decision,
            delivery_status="DELIVERED", reason_code=REASON_LANGUAGE_UNSPECIFIED,
            explanation="Delivered unchanged: no language was requested, so no translation was attempted.",
            answer_text=grounded_response.answer_text, answer_language=UNSPECIFIED_LANGUAGE, translation_applied=False,
            provider_name=None, delivery_metadata={}, config=config,
        )

    # D6 - SOURCE_MATCHES_REQUESTED_NO_TRANSLATION_NEEDED (only when the
    # caller explicitly asserts the source language - never guessed).
    if source_language is not None and source_language == requested_language:
        return _build_result(
            input_context=input_context, grounded_response=grounded_response, safety_decision=safety_decision,
            delivery_status="DELIVERED", reason_code=REASON_SOURCE_MATCHES_REQUESTED,
            explanation=f"Delivered unchanged: the answer is already asserted to be in {requested_language!r}.",
            answer_text=grounded_response.answer_text, answer_language=requested_language, translation_applied=False,
            provider_name=None, delivery_metadata={}, config=config,
        )

    # D7 - MISSING_TRANSLATION_PROVIDER
    if translation_provider is None:
        return _build_result(
            input_context=input_context, grounded_response=grounded_response, safety_decision=safety_decision,
            delivery_status="TRANSLATION_FAILED", reason_code=REASON_MISSING_TRANSLATION_PROVIDER,
            explanation=(
                f"Translation to {requested_language!r} was required but no translation_provider was supplied - "
                f"failing explicitly rather than silently delivering an untranslated or fabricated answer."
            ),
            answer_text=None, answer_language=None, translation_applied=False, provider_name=None,
            delivery_metadata={}, config=config,
        )

    # D8/D9 - attempt translation. The provider is untrusted (docs Section
    # Z) - its exception, wrong return type, or reported failure all
    # surface as TRANSLATION_FAILED, never a crash and never a silent
    # pass-through of unrelated content.
    try:
        output = translation_provider.translate(
            grounded_response.answer_text, source_language or "UNKNOWN", requested_language
        )
    except Exception as exc:  # noqa: BLE001 - a third-party provider must never crash this orchestrator
        return _build_result(
            input_context=input_context, grounded_response=grounded_response, safety_decision=safety_decision,
            delivery_status="TRANSLATION_FAILED", reason_code=REASON_TRANSLATION_PROVIDER_FAILED,
            explanation=f"Translation provider raised an exception: {exc}", answer_text=None, answer_language=None,
            translation_applied=False, provider_name=translation_provider.provider_name, delivery_metadata={}, config=config,
        )

    if not isinstance(output, TranslationOutput):
        return _build_result(
            input_context=input_context, grounded_response=grounded_response, safety_decision=safety_decision,
            delivery_status="TRANSLATION_FAILED", reason_code=REASON_TRANSLATION_PROVIDER_FAILED,
            explanation=f"Translation provider returned an invalid output type: {type(output).__name__}",
            answer_text=None, answer_language=None, translation_applied=False,
            provider_name=translation_provider.provider_name, delivery_metadata={}, config=config,
        )
    if not output.success:
        return _build_result(
            input_context=input_context, grounded_response=grounded_response, safety_decision=safety_decision,
            delivery_status="TRANSLATION_FAILED", reason_code=REASON_TRANSLATION_PROVIDER_FAILED,
            explanation=f"Translation provider reported failure: {output.failure_reason}", answer_text=None,
            answer_language=None, translation_applied=False, provider_name=translation_provider.provider_name,
            delivery_metadata={}, config=config,
        )

    # D9 - success. `output.translated_text` becomes `answer_text` - a
    # display string ONLY. Nothing else about this result is derived from
    # it (docs Section Z).
    return _build_result(
        input_context=input_context, grounded_response=grounded_response, safety_decision=safety_decision,
        delivery_status="DELIVERED", reason_code=REASON_TRANSLATION_SUCCEEDED,
        explanation=f"Delivered: translated to {requested_language!r} via {translation_provider.provider_name!r}.",
        answer_text=output.translated_text, answer_language=requested_language, translation_applied=True,
        provider_name=translation_provider.provider_name, delivery_metadata={"translation_metadata": dict(output.metadata)},
        config=config,
    )
