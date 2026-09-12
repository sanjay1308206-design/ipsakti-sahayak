"""
Phase 14 translation-provider abstraction (docs/PHASE_14_MULTILINGUAL_DELIVERY.md
Sections M, N, O, P). Provider selection is always explicit - the caller
passes a concrete provider instance to `delivery.deliver_response`;
nothing in this package chooses, guesses, or silently falls back to a
different provider.

Only `FakeTranslationProvider` is implemented here. `[OFFICIAL SOURCE]`
the Master Reference names Bhashini as the multilingual adapter
direction (`config/authority_matrix.yaml` SF-08); `[DEFERRED]` a real
Bhashini (or any other live) adapter is NOT implemented - neither
credentials, network access, a specific endpoint, a specific language
pair, nor latency/quality guarantees can be assumed to exist in this
environment. A future adapter would subclass `TranslationProvider`
exactly like `FakeTranslationProvider` does, with no other change
required anywhere in this package.
"""

from __future__ import annotations

import abc
from typing import Callable, Optional

from .models import TranslationOutput


class TranslationProvider(abc.ABC):
    """Any translation backend. `translate` must never raise for expected input shapes - see FakeTranslationProvider for the failure-injection convention subclasses may follow."""

    @property
    @abc.abstractmethod
    def provider_name(self) -> str: ...

    @abc.abstractmethod
    def translate(self, text: str, source_language: str, target_language: str) -> TranslationOutput: ...


class FakeTranslationProvider(TranslationProvider):
    """
    Deterministic, offline, no-network provider for tests (docs Section
    O). Three construction modes, mirroring Phase 10's
    `FakeGenerationProvider` exactly:

    - `response_text="..."`: always returns that exact text, successfully.
    - `respond_fn=callable`: calls `respond_fn(text, source_language, target_language) -> str`
      for full control - including, deliberately, for the adversarial
      test in docs Section Z (a `respond_fn` that returns text containing
      fake citation markers/jurisdiction words/status claims, to prove
      `delivery.deliver_response` never treats that text as authoritative
      for anything beyond `answer_text` itself).
    - `fail_with="..."`: always reports failure with that reason.

    Never touches the network, never requires a credential, and its
    transformation is NOT a claim of real translation quality (docs
    Section O) - it is provided solely to test the orchestration boundary.
    """

    def __init__(
        self,
        response_text: Optional[str] = None,
        respond_fn: Optional[Callable[[str, str, str], str]] = None,
        fail_with: Optional[str] = None,
        provider_name: str = "fake-translation-provider",
        metadata: Optional[dict] = None,
    ):
        provided = [x is not None for x in (response_text, respond_fn, fail_with)]
        if sum(provided) != 1:
            raise ValueError("exactly one of response_text, respond_fn, fail_with must be provided")
        if not isinstance(provider_name, str) or not provider_name.strip():
            raise ValueError("provider_name must be a non-empty string")
        self._response_text = response_text
        self._respond_fn = respond_fn
        self._fail_with = fail_with
        self._provider_name = provider_name
        self._metadata = dict(metadata) if metadata is not None else {}

    @property
    def provider_name(self) -> str:
        return self._provider_name

    def translate(self, text: str, source_language: str, target_language: str) -> TranslationOutput:
        if not isinstance(text, str):
            raise TypeError(f"FakeTranslationProvider.translate expects text to be a string, got {type(text).__name__}")
        if not isinstance(source_language, str) or not isinstance(target_language, str):
            raise TypeError("FakeTranslationProvider.translate expects source_language/target_language to be strings")

        if self._fail_with is not None:
            return TranslationOutput(
                translated_text="",
                provider_name=self._provider_name,
                source_language=source_language,
                target_language=target_language,
                success=False,
                failure_reason=self._fail_with,
                metadata=dict(self._metadata),
            )

        translated = self._respond_fn(text, source_language, target_language) if self._respond_fn is not None else self._response_text
        return TranslationOutput(
            translated_text=translated,
            provider_name=self._provider_name,
            source_language=source_language,
            target_language=target_language,
            success=True,
            failure_reason=None,
            metadata=dict(self._metadata),
        )
