"""
Phase 10 provider abstraction (docs/PHASE_10_GROUNDED_GENERATION.md
Sections K, L, M).

`GenerationProvider` is the interface any generation backend must
satisfy. Provider selection is always explicit - the caller passes a
concrete provider instance to `generator.generate_grounded_response`;
nothing in this package chooses, guesses, or silently falls back to a
different provider.

Only `FakeGenerationProvider` is implemented here. A real Gemini Flash or
local Qwen2.5-3B adapter is `[DEFERRED]`/`[ASSUMPTION]` - neither
credentials nor a downloaded model can be assumed to exist in this
environment (per explicit instruction), and forcing either would violate
"do not require an API key for the test suite" / "do not download a
large model automatically." A future adapter would subclass
`GenerationProvider` exactly like `FakeGenerationProvider` does, with no
change required anywhere else in this package.
"""

from __future__ import annotations

import abc
from typing import Callable, Optional

from .models import GenerationOutput


class GenerationProvider(abc.ABC):
    """Any generation backend. `generate` must never raise for expected input shapes - see FakeGenerationProvider for the failure-injection convention subclasses may follow."""

    @property
    @abc.abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abc.abstractmethod
    def model_identifier(self) -> str: ...

    @abc.abstractmethod
    def generate(self, prompt: str) -> GenerationOutput: ...


class FakeGenerationProvider(GenerationProvider):
    """
    Deterministic, offline, no-network provider for tests
    (docs Section L). Two construction modes:

    - `FakeGenerationProvider(response_text="...")`: always returns that
      exact text, successfully.
    - `FakeGenerationProvider(respond_fn=callable)`: calls `respond_fn(prompt) -> str`
      for full control (e.g. echoing back an evidence_id seen in the
      prompt, for a deterministic-but-prompt-dependent test).
    - `FakeGenerationProvider(fail_with="...")`: always reports failure
      with that reason, never returns success.

    Never touches the network, never requires a credential, never reads
    a model file from disk.
    """

    def __init__(
        self,
        response_text: Optional[str] = None,
        respond_fn: Optional[Callable[[str], str]] = None,
        fail_with: Optional[str] = None,
        provider_name: str = "fake-provider",
        model_identifier: str = "fake-model-v1",
        metadata: Optional[dict] = None,
    ):
        provided = [x is not None for x in (response_text, respond_fn, fail_with)]
        if sum(provided) != 1:
            raise ValueError("exactly one of response_text, respond_fn, fail_with must be provided")
        if not isinstance(provider_name, str) or not provider_name.strip():
            raise ValueError("provider_name must be a non-empty string")
        if not isinstance(model_identifier, str) or not model_identifier.strip():
            raise ValueError("model_identifier must be a non-empty string")
        self._response_text = response_text
        self._respond_fn = respond_fn
        self._fail_with = fail_with
        self._provider_name = provider_name
        self._model_identifier = model_identifier
        self._metadata = dict(metadata) if metadata is not None else {}

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model_identifier(self) -> str:
        return self._model_identifier

    def generate(self, prompt: str) -> GenerationOutput:
        if not isinstance(prompt, str):
            raise TypeError(f"FakeGenerationProvider.generate expects a string prompt, got {type(prompt).__name__}")

        if self._fail_with is not None:
            return GenerationOutput(
                raw_text="",
                provider_name=self._provider_name,
                model_identifier=self._model_identifier,
                success=False,
                failure_reason=self._fail_with,
                metadata=dict(self._metadata),
            )

        text = self._respond_fn(prompt) if self._respond_fn is not None else self._response_text
        return GenerationOutput(
            raw_text=text,
            provider_name=self._provider_name,
            model_identifier=self._model_identifier,
            success=True,
            failure_reason=None,
            metadata=dict(self._metadata),
        )
