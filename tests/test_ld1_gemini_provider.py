"""
LD-1 (Production Generation Provider) unit tests for
`generation.gemini_provider.GeminiGenerationProvider`.

Every test here mocks the Gemini network call directly on the
constructed `genai.Client` instance (`provider._client.models.generate_content`)
- NO test in this file makes a real network call or requires a real API
key (construction itself never touches the network - confirmed by
inspecting the installed `google-genai` SDK - so a syntactically
well-formed placeholder key is enough to exercise every code path here).
A real, credentialed smoke test lives separately (see the LD-1
implementation report, Step G) and is skipped unless a real key is
present in the environment.
"""

from __future__ import annotations

import pytest

from generation.gemini_provider import DEFAULT_GEMINI_MODEL, GeminiGenerationProvider
from generation.models import GenerationOutput
from generation.providers import GenerationProvider

FAKE_KEY = "ld1-test-placeholder-key-not-real"


class _FakeResponse:
    def __init__(self, text):
        self.text = text


def _provider(**kwargs) -> GeminiGenerationProvider:
    kwargs.setdefault("api_key", FAKE_KEY)
    return GeminiGenerationProvider(**kwargs)


# ---------------------------------------------------------------------------
# Construction / interface
# ---------------------------------------------------------------------------


def test_is_a_real_generation_provider_subclass():
    provider = _provider()
    assert isinstance(provider, GenerationProvider)


def test_construction_requires_nonempty_api_key():
    with pytest.raises(ValueError):
        GeminiGenerationProvider(api_key="")
    with pytest.raises(ValueError):
        GeminiGenerationProvider(api_key="   ")


def test_construction_requires_nonempty_model():
    with pytest.raises(ValueError):
        GeminiGenerationProvider(api_key=FAKE_KEY, model="")


def test_construction_requires_positive_timeout():
    with pytest.raises(ValueError):
        GeminiGenerationProvider(api_key=FAKE_KEY, timeout_seconds=0)
    with pytest.raises(ValueError):
        GeminiGenerationProvider(api_key=FAKE_KEY, timeout_seconds=-5)


def test_construction_never_touches_the_network():
    # If this raised anything network-shaped (connection error, DNS
    # failure, auth check), that would prove the client eagerly connects
    # - it must not; the SDK's own Client is a lazy HTTP client.
    _provider()


def test_provider_name_and_model_identifier():
    provider = _provider(model="gemini-2.5-flash")
    assert provider.provider_name == "gemini"
    assert provider.model_identifier == "gemini-2.5-flash"


def test_default_model_is_used_when_not_overridden():
    provider = _provider()
    assert provider.model_identifier == DEFAULT_GEMINI_MODEL


def test_default_gemini_model_is_exactly_gemini_3_5_flash():
    # LD-4 diagnosis follow-up: `gemini-2.5-flash` (the original LD-1
    # default) started returning a real, confirmed
    # `google.genai.errors.APIError(code=404, status=NOT_FOUND)` in
    # production - a live smoke test (google-genai==2.24.0, same API
    # key, `client.models.generate_content`) confirmed `gemini-3.5-flash`
    # responds successfully instead. This test locks in the literal
    # value (not just self-referential equality against the constant) so
    # a future edit cannot silently revert the default back to the
    # broken model.
    assert DEFAULT_GEMINI_MODEL == "gemini-3.5-flash"
    provider = _provider()
    assert provider.model_identifier == "gemini-3.5-flash"


def test_generate_rejects_non_string_prompt():
    provider = _provider()
    with pytest.raises(TypeError):
        provider.generate(12345)


# ---------------------------------------------------------------------------
# Successful generation
# ---------------------------------------------------------------------------


def test_generate_success_returns_grounded_generation_output():
    provider = _provider()
    provider._client.models.generate_content = lambda **kwargs: _FakeResponse("The evidence supports this.")

    output = provider.generate("some fully-built Phase 10 prompt")

    assert isinstance(output, GenerationOutput)
    assert output.success is True
    assert output.failure_reason is None
    assert output.raw_text == "The evidence supports this."
    assert output.provider_name == "gemini"
    assert output.model_identifier == provider.model_identifier


def test_generate_preserves_citation_markers_verbatim():
    # The provider must never parse/rewrite/strip [[CITE:...]] markers -
    # that is generation.grounding.extract_citation_references's job,
    # over this exact raw_text, unmodified.
    provider = _provider()
    text = "Per the regulation [[CITE:EV-REAL-001]], compliance is required."
    provider._client.models.generate_content = lambda **kwargs: _FakeResponse(text)

    output = provider.generate("prompt")

    assert output.raw_text == text


def test_generate_forwards_prompt_and_model_to_the_sdk():
    provider = _provider(model="gemini-2.5-flash")
    seen = {}

    def fake_generate_content(**kwargs):
        seen.update(kwargs)
        return _FakeResponse("ok")

    provider._client.models.generate_content = fake_generate_content
    provider.generate("EXACT PROMPT TEXT")

    assert seen["model"] == "gemini-2.5-flash"
    assert seen["contents"] == "EXACT PROMPT TEXT"


def test_generate_output_metadata_is_always_empty_dict_never_credential_shaped():
    provider = _provider()
    provider._client.models.generate_content = lambda **kwargs: _FakeResponse("x")
    output = provider.generate("p")
    assert output.metadata == {}


# ---------------------------------------------------------------------------
# Failure modes - must never raise, must never leak the API key
# ---------------------------------------------------------------------------


def test_generate_handles_empty_response_text_as_failure_not_crash():
    provider = _provider()
    provider._client.models.generate_content = lambda **kwargs: _FakeResponse(None)

    output = provider.generate("prompt")

    assert isinstance(output, GenerationOutput)
    assert output.success is False
    assert output.raw_text == ""
    assert "no text" in output.failure_reason.lower()


def test_generate_handles_api_error_without_raising():
    from google.genai import errors as genai_errors

    provider = _provider(api_key="super-secret-value-zzz")

    def raise_api_error(**kwargs):
        raise genai_errors.APIError(code=429, response_json={"message": "quota exceeded", "status": "RESOURCE_EXHAUSTED"})

    provider._client.models.generate_content = raise_api_error

    output = provider.generate("prompt")

    assert output.success is False
    assert output.raw_text == ""
    assert "RESOURCE_EXHAUSTED" in output.failure_reason or "429" in output.failure_reason


def test_generate_api_error_never_leaks_the_api_key():
    from google.genai import errors as genai_errors

    secret = "super-secret-value-zzz"
    provider = _provider(api_key=secret)

    def raise_api_error(**kwargs):
        # Adversarial: simulate a server error message that happens to
        # echo the key back - the redaction guard must still strip it.
        raise genai_errors.APIError(code=401, response_json={"message": f"key {secret} rejected", "status": "UNAUTHENTICATED"})

    provider._client.models.generate_content = raise_api_error

    output = provider.generate("prompt")

    assert secret not in output.failure_reason


def test_generate_handles_unexpected_exception_without_raising():
    provider = _provider()

    def raise_unexpected(**kwargs):
        raise RuntimeError("connection reset by peer")

    provider._client.models.generate_content = raise_unexpected

    output = provider.generate("prompt")

    assert isinstance(output, GenerationOutput)
    assert output.success is False
    assert output.raw_text == ""
    assert "RuntimeError" in output.failure_reason


def test_generate_unexpected_exception_never_leaks_the_api_key_or_raw_message():
    secret = "super-secret-value-zzz"
    provider = _provider(api_key=secret)

    def raise_unexpected(**kwargs):
        raise RuntimeError(f"failed while authenticating with key={secret}")

    provider._client.models.generate_content = raise_unexpected

    output = provider.generate("prompt")

    assert secret not in output.failure_reason
    # The raw exception message is deliberately excluded entirely for
    # unrecognized exception types (only the class name is safe to
    # surface to an end user), never merely redacted-in-place.
    assert "authenticating" not in output.failure_reason


def test_generate_api_error_logs_code_status_and_sanitized_reason(caplog):
    # LD-4 diagnosis follow-up: the Render runtime log for a real
    # production APIError only ever showed `code=404 status=NOT_FOUND`
    # with no message text, because the log call omitted the reason
    # string entirely - this test locks in the fix (the same
    # already-redacted `reason` used for `failure_reason` must also
    # reach the log record) so a future failure is diagnosable directly
    # from Render logs without needing a source-code cross-reference.
    from google.genai import errors as genai_errors

    provider = _provider()

    def raise_api_error(**kwargs):
        raise genai_errors.APIError(code=404, response_json={"message": "model not found", "status": "NOT_FOUND"})

    provider._client.models.generate_content = raise_api_error

    with caplog.at_level("ERROR", logger="ipsakti.generation.gemini"):
        output = provider.generate("prompt")

    assert output.success is False
    [record] = [r for r in caplog.records if "APIError" in r.message]
    assert "code=404" in record.message
    assert "status=NOT_FOUND" in record.message
    assert "model not found" in record.message
    # The logged reason must be exactly the same sanitized text handed
    # back to the caller in `failure_reason` - no separate, divergent
    # copy of the message.
    assert output.failure_reason in record.message


def test_generate_api_error_log_never_leaks_the_api_key(caplog):
    from google.genai import errors as genai_errors

    secret = "super-secret-value-zzz"
    provider = _provider(api_key=secret)

    def raise_api_error(**kwargs):
        raise genai_errors.APIError(code=401, response_json={"message": f"key {secret} rejected", "status": "UNAUTHENTICATED"})

    provider._client.models.generate_content = raise_api_error

    with caplog.at_level("ERROR", logger="ipsakti.generation.gemini"):
        provider.generate("prompt")

    for record in caplog.records:
        assert secret not in record.message
        assert secret not in record.getMessage()


def test_generate_api_error_log_never_contains_the_prompt_text(caplog):
    # The log call must only ever carry the SDK's own `code`/`status`/
    # `message` fields - never the caller-supplied prompt (which embeds
    # the EvidencePack/citation-instruction text).
    from google.genai import errors as genai_errors

    provider = _provider()

    def raise_api_error(**kwargs):
        raise genai_errors.APIError(code=404, response_json={"message": "model not found", "status": "NOT_FOUND"})

    provider._client.models.generate_content = raise_api_error
    secret_prompt = "UNIQUE-EVIDENCE-PACK-MARKER-should-never-be-logged"

    with caplog.at_level("ERROR", logger="ipsakti.generation.gemini"):
        provider.generate(secret_prompt)

    for record in caplog.records:
        assert secret_prompt not in record.getMessage()


def test_generate_api_error_failure_reason_format_unchanged():
    # The logging fix must not alter the caller-visible failure_reason
    # contract (format, truncation, redaction) established by the
    # existing failure-mode tests above - only additional logging output
    # was added.
    from google.genai import errors as genai_errors

    provider = _provider()

    def raise_api_error(**kwargs):
        raise genai_errors.APIError(code=404, response_json={"message": "model not found", "status": "NOT_FOUND"})

    provider._client.models.generate_content = raise_api_error
    output = provider.generate("prompt")

    assert output.failure_reason == "Gemini API error 404 (NOT_FOUND): model not found"
    assert len(output.failure_reason) <= 500


def test_generate_never_raises_for_any_sdk_failure_mode():
    # A structural guarantee matching FakeGenerationProvider's own
    # documented contract ("generate must never raise for expected input
    # shapes") - every exception type this adapter can realistically
    # encounter must be converted into a GenerationOutput, not left to
    # propagate (generate_grounded_response's own try/except is a second,
    # independent safety net, not the only one).
    from google.genai import errors as genai_errors

    provider = _provider()
    for exc in (
        genai_errors.ServerError(code=500, response_json={"message": "internal", "status": "INTERNAL"}),
        genai_errors.ClientError(code=400, response_json={"message": "bad request", "status": "INVALID_ARGUMENT"}),
        TimeoutError("timed out"),
        ConnectionError("no route to host"),
        ValueError("unexpected shape"),
    ):
        def raiser(**kwargs):
            raise exc

        provider._client.models.generate_content = raiser
        output = provider.generate("prompt")
        assert output.success is False
