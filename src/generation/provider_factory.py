"""
LD-1 (Production Generation Provider): reads `GENERATION_PROVIDER` /
`GENERATION_MODEL` / `GENERATION_API_KEY` from the process environment
and constructs the matching real `GenerationProvider`, or returns `None`
if no provider is configured at all.

This is the ONLY place in this repository that reads a generation-related
environment variable or a generation provider's credential - kept
deliberately separate from `application.config.EnvironmentConfig` so that
no secret value is ever stored on a long-lived, potentially-logged or
-serialized dataclass instance (`EnvironmentConfig`'s own docstring
promise, "No API key, token, password, or credential is ever read,
stored, or exposed by this class", stays true; the credential is read
here, handed straight into a provider constructor, and never stored
anywhere else).

FAIL-CLOSED CONTRACT (unchanged from Phase 17):
- `GENERATION_PROVIDER` unset/empty -> returns `None`. This is not an
  error - it is the same "no provider configured" state Phase 17 has
  always defaulted to. `ApplicationService.query` then raises
  `GenerationProviderNotConfiguredError` exactly as before, mapped to
  HTTP 503 by `api/errors.py`, unchanged.
- `GENERATION_PROVIDER` set to an unsupported value, or set with a
  missing/empty `GENERATION_API_KEY` -> raises
  `GenerationProviderConfigError` (never a silent fallback to `None` -
  that would make a real deployment mistake look identical to "nobody
  configured a provider yet"). The caller (`api/dependencies.py`)
  decides how to handle that - logging it and falling back to `None`
  (still fail-closed HTTP 503, never a fabricated answer) so that a
  misconfigured environment variable cannot take down the whole backend
  process.
"""

from __future__ import annotations

import os
from typing import Mapping, Optional

from .gemini_provider import DEFAULT_GEMINI_MODEL, GeminiGenerationProvider
from .providers import GenerationProvider

# Closed set - extend only by adding a real, tested adapter (mirrors the
# closed GROUNDING_STATUSES/ABSTENTION_REASONS vocabulary convention used
# throughout this project). "fake" is deliberately NOT included here -
# FakeGenerationProvider is constructed directly in tests, never
# reachable through environment configuration (docs "NO mock provider in
# production").
SUPPORTED_PROVIDERS = frozenset({"gemini"})


class GenerationProviderConfigError(ValueError):
    """Raised when GENERATION_PROVIDER is explicitly set but the rest of the environment does not describe a usable, real provider."""


def build_generation_provider_from_env(env: Optional[Mapping[str, str]] = None) -> Optional[GenerationProvider]:
    """
    `env` defaults to `os.environ`; a test may pass an explicit mapping
    instead of mutating real process environment variables.
    """
    if env is None:
        env = os.environ

    provider_name = (env.get("GENERATION_PROVIDER") or "").strip().lower()
    if not provider_name:
        return None

    if provider_name not in SUPPORTED_PROVIDERS:
        raise GenerationProviderConfigError(
            f"GENERATION_PROVIDER={provider_name!r} is not a supported value; supported values are "
            f"{sorted(SUPPORTED_PROVIDERS)}"
        )

    api_key = (env.get("GENERATION_API_KEY") or "").strip()
    if not api_key:
        raise GenerationProviderConfigError(
            "GENERATION_PROVIDER is set but GENERATION_API_KEY is missing or empty - refusing to construct a "
            "generation provider without a credential"
        )

    model = (env.get("GENERATION_MODEL") or "").strip() or DEFAULT_GEMINI_MODEL

    if provider_name == "gemini":
        try:
            return GeminiGenerationProvider(api_key=api_key, model=model)
        except RuntimeError as exc:
            # Raised by GeminiGenerationProvider.__init__ when the
            # `google-genai` package is not installed - a deployment
            # dependency-closure mistake, not a code bug, so it is
            # surfaced through this module's own typed config-error
            # vocabulary rather than propagating a bare RuntimeError.
            raise GenerationProviderConfigError(str(exc)) from exc

    raise AssertionError(f"unreachable: {provider_name!r} passed the SUPPORTED_PROVIDERS check")
