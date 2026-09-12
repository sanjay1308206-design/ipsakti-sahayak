"""
Phase 14 tests: translation-provider abstraction and FakeTranslationProvider
(docs/PHASE_14_MULTILINGUAL_DELIVERY.md Sections M, N, O, P).
"""

from __future__ import annotations

import pytest

from multilingual.models import TranslationOutput
from multilingual.providers import FakeTranslationProvider, TranslationProvider


def test_translation_provider_is_abstract():
    with pytest.raises(TypeError):
        TranslationProvider()


def test_fake_provider_with_response_text_succeeds():
    provider = FakeTranslationProvider(response_text="hello")
    output = provider.translate("text", "en", "hi")
    assert isinstance(output, TranslationOutput)
    assert output.success is True
    assert output.translated_text == "hello"


def test_fake_provider_with_respond_fn_is_input_dependent():
    provider = FakeTranslationProvider(respond_fn=lambda text, src, tgt: f"{tgt}:{text}")
    output = provider.translate("abc", "en", "hi")
    assert output.translated_text == "hi:abc"


def test_fake_provider_with_fail_with_always_fails():
    provider = FakeTranslationProvider(fail_with="offline")
    output = provider.translate("text", "en", "hi")
    assert output.success is False
    assert output.failure_reason == "offline"


def test_fake_provider_exposes_provider_name():
    provider = FakeTranslationProvider(response_text="x", provider_name="my-provider")
    assert provider.provider_name == "my-provider"


def test_fake_provider_requires_exactly_one_response_mode():
    with pytest.raises(ValueError):
        FakeTranslationProvider()
    with pytest.raises(ValueError):
        FakeTranslationProvider(response_text="a", fail_with="b")


def test_fake_provider_rejects_non_string_text():
    provider = FakeTranslationProvider(response_text="x")
    with pytest.raises(TypeError):
        provider.translate(12345, "en", "hi")


def test_fake_provider_never_carries_a_credential_shaped_metadata_key():
    provider = FakeTranslationProvider(response_text="x", metadata={"api_key": "secret"})
    with pytest.raises(ValueError):
        provider.translate("text", "en", "hi")


def test_translation_output_requires_failure_reason_when_not_success():
    with pytest.raises(ValueError):
        TranslationOutput(translated_text="", provider_name="p", source_language="en", target_language="hi", success=False, failure_reason=None, metadata={})


def test_translation_output_rejects_success_with_failure_reason():
    with pytest.raises(ValueError):
        TranslationOutput(translated_text="x", provider_name="p", source_language="en", target_language="hi", success=True, failure_reason="oops", metadata={})


def test_fake_provider_never_touches_network_or_filesystem():
    import inspect

    from multilingual import providers

    source = inspect.getsource(providers)
    for forbidden in ("requests", "httpx", "urllib", "socket", "torch", "transformers"):
        assert forbidden not in source
