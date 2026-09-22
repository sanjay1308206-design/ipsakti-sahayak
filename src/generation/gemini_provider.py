"""
LD-1 (Production Generation Provider): a Google Gemini adapter for the
Phase 10 `GenerationProvider` interface (`src/generation/providers.py`).

This adapter is a thin, isolated wrapper around the official Google Gen
AI Python SDK (`google-genai`, https://github.com/googleapis/python-genai)
- it does exactly two things: send `prompt` (already fully built by
`generation.prompts.build_prompt`, including the `[[CITE:<evidence_id>]]`
citation instruction and the closed ALLOWED EVIDENCE IDS list) to the
Gemini API, and wrap the response text back into a `GenerationOutput`. It
never constructs a prompt, never resolves or validates a citation, and
never decides grounding/abstention/safety - those remain exclusively
`generation.generator.generate_grounded_response` /
`citation.validator.validate_citations` / `safety.evaluator.evaluate_safety`'s
job, completely unchanged by this file.

[OFFICIAL SOURCE] SDK shapes verified directly against the installed
`google-genai` 2.23.0 package: `genai.Client(api_key=..., http_options=...)`,
`client.models.generate_content(model=..., contents=..., config=...)`,
`GenerateContentResponse.text` (Optional[str], never raises for a
blocked/empty response), `google.genai.errors.APIError`
(`code`/`status`/`message`/`details`, never includes the request URL or
API key - the SDK sends the key via the `x-goog-api-key` HTTP header,
confirmed in `google/genai/_api_client.py`, never a query parameter). No
SDK behavior is invented; see this repository's LD-1 implementation
report for the exact verification steps.

Per `GenerationProvider`'s own contract ("`generate` must never raise for
expected input shapes"), every SDK/network/auth failure is caught here
and reported as `GenerationOutput(success=False, ...)`, never propagated
as an exception - `generate_grounded_response` additionally wraps every
`provider.generate` call in its own try/except as a second, independent
safety net (docs/PHASE_10_GROUNDED_GENERATION.md), so this file's own
catching is defense-in-depth, not the only guard.

SECRET-LEAKAGE GUARD: `failure_reason` ends up in the end-user-visible
API response (`safety.evaluator` embeds `GroundedResponse.failure_reason`
directly into its `explanation` string, which flows all the way to
`QueryResponse.explanation`). This file therefore NEVER interpolates a
raw exception's `str()` into `failure_reason` - only a small, explicitly
whitelisted set of fields (exception class name; for `APIError`, the
server-reported `status`/`message` only) is used, and the configured
`api_key` value itself is redacted from that text as a final defensive
layer regardless of source.
"""

from __future__ import annotations

import logging
from typing import Optional

from .models import GenerationOutput
from .providers import GenerationProvider

logger = logging.getLogger("ipsakti.generation.gemini")

# [ENGINEERING RECOMMENDATION] `gemini-2.5-flash` was the original LD-1
# default but started returning `google.genai.errors.APIError(code=404,
# status=NOT_FOUND)` in production (LD-4 diagnosis) - confirmed by a real
# `client.models.generate_content` smoke test (google-genai==2.24.0, same
# API key) that Google no longer serves that model to this key/project.
# `gemini-3.5-flash` is the model that same smoke test confirmed working
# (`GEMINI_SMOKE_OK`) against the identical SDK version and key, so it
# replaces `gemini-2.5-flash` as the default here. This remains an
# engineering choice, not a Master Reference requirement, and is fully
# overridable per-deployment via the GENERATION_MODEL environment
# variable (see generation/provider_factory.py) without any code change.
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"

# [ENGINEERING RECOMMENDATION] A hard per-request timeout so a stalled
# network call can never hang an HTTP request indefinitely - not
# mandated by any Master Reference contract, but a basic production
# safety property for a live-demo backend.
DEFAULT_TIMEOUT_SECONDS = 30.0


def _redact(text: str, secret: str) -> str:
    """Defense-in-depth: strip a known secret value out of outbound text, regardless of where it could have entered."""
    if secret:
        text = text.replace(secret, "[REDACTED]")
    return text


class GeminiGenerationProvider(GenerationProvider):
    """
    Real, network-calling `GenerationProvider` backed by the Gemini API.

    Construction never touches the network - the underlying `genai.Client`
    only opens a connection on the first real call, inside `generate()`.
    `api_key` must be a non-empty string; this class never reads an
    environment variable itself (that boundary belongs to
    `generation.provider_factory.build_generation_provider_from_env`), so
    this adapter stays a small, directly-testable unit with an injected
    credential - exactly like every other provider in this project takes
    its configuration as explicit constructor arguments, never "by magic"
    from the environment (docs/PHASE_17_BACKEND_PRODUCTIZATION.md Section
    U, "PROVIDER BOUNDARIES").
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_GEMINI_MODEL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("api_key must be a non-empty string")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty string")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a positive number")

        # Imported lazily so importing this module - or the `generation`
        # package it lives in - never requires `google-genai` to be
        # installed unless a real Gemini provider is actually
        # constructed. Mirrors `retrieval/embeddings.py`'s own
        # lazy-import convention for `sentence_transformers` elsewhere in
        # this repository. A missing dependency here becomes a clear,
        # typed configuration error (see provider_factory.py), never an
        # ImportError surfacing from deep inside dependency wiring.
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:  # pragma: no cover - exercised via provider_factory when the package is absent
            raise RuntimeError(
                "the 'google-genai' package is required to construct GeminiGenerationProvider but is not installed"
            ) from exc

        self._api_key = api_key
        self._model = model
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
        )
        self._config = types.GenerateContentConfig(temperature=0.0)

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_identifier(self) -> str:
        return self._model

    def generate(self, prompt: str) -> GenerationOutput:
        if not isinstance(prompt, str):
            raise TypeError(f"GeminiGenerationProvider.generate expects a string prompt, got {type(prompt).__name__}")

        from google.genai import errors as genai_errors

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=self._config,
            )
        except genai_errors.APIError as exc:
            reason = _redact(f"Gemini API error {exc.code} ({exc.status}): {exc.message}", self._api_key)
            logger.error(
                "Gemini generate_content APIError: code=%s status=%s reason=%s",
                exc.code, exc.status, reason[:500],
            )
            return GenerationOutput(
                raw_text="", provider_name=self.provider_name, model_identifier=self._model,
                success=False, failure_reason=reason[:500], metadata={},
            )
        except Exception as exc:  # noqa: BLE001 - network/SDK failures must never crash the orchestrator
            logger.exception("Gemini generate_content failed with an unexpected exception")
            reason = _redact(f"Gemini request failed: {exc.__class__.__name__}", self._api_key)
            return GenerationOutput(
                raw_text="", provider_name=self.provider_name, model_identifier=self._model,
                success=False, failure_reason=reason, metadata={},
            )

        text: Optional[str] = response.text
        if not text:
            return GenerationOutput(
                raw_text="", provider_name=self.provider_name, model_identifier=self._model,
                success=False, failure_reason="Gemini returned no text (empty or safety-blocked response)",
                metadata={},
            )

        return GenerationOutput(
            raw_text=text, provider_name=self.provider_name, model_identifier=self._model,
            success=True, failure_reason=None, metadata={},
        )
