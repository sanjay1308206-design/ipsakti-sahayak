"""
LD-1 (Production Generation Provider) tests for
`generation.provider_factory.build_generation_provider_from_env`.

Every test passes an explicit `env` mapping (never mutates real process
environment variables / `os.environ`), and no test here makes a real
network call or requires a real API key.
"""

from __future__ import annotations

import pytest

from generation.gemini_provider import DEFAULT_GEMINI_MODEL, GeminiGenerationProvider
from generation.provider_factory import GenerationProviderConfigError, build_generation_provider_from_env
from generation.providers import GenerationProvider


def test_returns_none_when_generation_provider_env_is_unset():
    assert build_generation_provider_from_env(env={}) is None


def test_returns_none_when_generation_provider_env_is_blank():
    assert build_generation_provider_from_env(env={"GENERATION_PROVIDER": "   "}) is None


def test_unsupported_provider_value_raises_config_error():
    with pytest.raises(GenerationProviderConfigError):
        build_generation_provider_from_env(env={"GENERATION_PROVIDER": "not-a-real-provider"})


def test_gemini_without_api_key_raises_config_error():
    with pytest.raises(GenerationProviderConfigError):
        build_generation_provider_from_env(env={"GENERATION_PROVIDER": "gemini"})


def test_gemini_with_blank_api_key_raises_config_error():
    with pytest.raises(GenerationProviderConfigError):
        build_generation_provider_from_env(env={"GENERATION_PROVIDER": "gemini", "GENERATION_API_KEY": "   "})


def test_gemini_with_valid_config_constructs_a_real_provider():
    provider = build_generation_provider_from_env(
        env={"GENERATION_PROVIDER": "gemini", "GENERATION_API_KEY": "placeholder-key", "GENERATION_MODEL": "gemini-2.5-flash"}
    )
    assert isinstance(provider, GeminiGenerationProvider)
    assert isinstance(provider, GenerationProvider)
    assert provider.provider_name == "gemini"
    assert provider.model_identifier == "gemini-2.5-flash"


def test_gemini_default_model_used_when_generation_model_unset():
    provider = build_generation_provider_from_env(env={"GENERATION_PROVIDER": "gemini", "GENERATION_API_KEY": "placeholder-key"})
    assert provider.model_identifier == DEFAULT_GEMINI_MODEL


def test_gemini_default_model_used_when_generation_model_blank():
    provider = build_generation_provider_from_env(
        env={"GENERATION_PROVIDER": "gemini", "GENERATION_API_KEY": "placeholder-key", "GENERATION_MODEL": "  "}
    )
    assert provider.model_identifier == DEFAULT_GEMINI_MODEL


def test_provider_name_is_case_and_whitespace_insensitive():
    provider = build_generation_provider_from_env(env={"GENERATION_PROVIDER": "  Gemini  ", "GENERATION_API_KEY": "placeholder-key"})
    assert isinstance(provider, GeminiGenerationProvider)


def test_fake_is_never_reachable_through_environment_configuration():
    # No deployment misconfiguration can select the test-only fake
    # provider in production (docs "no mock provider in production") -
    # "fake" is simply not in the supported-provider vocabulary.
    with pytest.raises(GenerationProviderConfigError):
        build_generation_provider_from_env(env={"GENERATION_PROVIDER": "fake", "GENERATION_API_KEY": "x"})


def test_missing_google_genai_dependency_is_wrapped_as_config_error(monkeypatch):
    import generation.provider_factory as factory

    class _StubMissingDependency:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("the 'google-genai' package is required to construct GeminiGenerationProvider but is not installed")

    monkeypatch.setattr(factory, "GeminiGenerationProvider", _StubMissingDependency)

    with pytest.raises(GenerationProviderConfigError):
        factory.build_generation_provider_from_env(env={"GENERATION_PROVIDER": "gemini", "GENERATION_API_KEY": "placeholder-key"})


def test_defaults_to_os_environ_when_env_not_passed(monkeypatch):
    monkeypatch.delenv("GENERATION_PROVIDER", raising=False)
    assert build_generation_provider_from_env() is None
