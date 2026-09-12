"""
Phase 10 tests: provider abstraction and FakeGenerationProvider
(docs/PHASE_10_GROUNDED_GENERATION.md Sections K, L, M).
"""

from __future__ import annotations

import pytest

from generation.models import GenerationOutput
from generation.providers import FakeGenerationProvider, GenerationProvider


def test_generation_provider_is_abstract():
    with pytest.raises(TypeError):
        GenerationProvider()


def test_fake_provider_with_response_text_succeeds():
    provider = FakeGenerationProvider(response_text="hello")
    output = provider.generate("any prompt")
    assert isinstance(output, GenerationOutput)
    assert output.success is True
    assert output.raw_text == "hello"


def test_fake_provider_with_respond_fn_is_prompt_dependent():
    provider = FakeGenerationProvider(respond_fn=lambda prompt: f"echo:{len(prompt)}")
    output = provider.generate("abc")
    assert output.raw_text == "echo:3"


def test_fake_provider_with_fail_with_always_fails():
    provider = FakeGenerationProvider(fail_with="offline")
    output = provider.generate("prompt")
    assert output.success is False
    assert output.failure_reason == "offline"


def test_fake_provider_exposes_provider_name_and_model_identifier():
    provider = FakeGenerationProvider(response_text="x", provider_name="my-provider", model_identifier="my-model")
    assert provider.provider_name == "my-provider"
    assert provider.model_identifier == "my-model"


def test_fake_provider_requires_exactly_one_response_mode():
    with pytest.raises(ValueError):
        FakeGenerationProvider()
    with pytest.raises(ValueError):
        FakeGenerationProvider(response_text="a", fail_with="b")


def test_fake_provider_rejects_non_string_prompt():
    provider = FakeGenerationProvider(response_text="x")
    with pytest.raises(TypeError):
        provider.generate(12345)


def test_fake_provider_never_carries_a_credential_shaped_metadata_key():
    provider = FakeGenerationProvider(response_text="x", metadata={"tokens_used": 42})
    output = provider.generate("p")
    assert "api_key" not in output.metadata

    # Metadata is validated at the GenerationOutput boundary (generate()
    # time), not merely at FakeGenerationProvider construction time - the
    # constructor only stores it.
    bad_provider = FakeGenerationProvider(response_text="x", metadata={"api_key": "secret"})
    with pytest.raises(ValueError):
        bad_provider.generate("p")


def test_fake_provider_never_touches_network_or_filesystem_model_loading():
    # A purely structural assertion: FakeGenerationProvider's source does
    # not import anything network/model-loading related.
    import inspect

    from generation import providers

    source = inspect.getsource(providers)
    for forbidden in ("requests", "httpx", "urllib", "socket", "torch", "transformers"):
        assert forbidden not in source
