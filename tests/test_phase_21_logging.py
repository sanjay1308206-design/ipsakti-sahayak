"""
Phase 21 Step 4 tests: structured operational logging convention
(docs/PHASE_21_OBSERVABILITY_BACKUP_CORPUS_REFRESH.md Section 7, 27).

Covers the structured event shape/validation, deterministic
serialization, sensitive-field redaction, and failure-safety guarantees
of `observability.logging`, plus a compatibility check proving this
utility reuses (never replaces or duplicates) `src/api/errors.py`'s own
existing stdlib `logging` usage from Phase 17.
"""

from __future__ import annotations

import json
import logging

import pytest

from observability.logging import (
    LOG_SCHEMA_VERSION,
    StructuredLogEvent,
    build_structured_log_event,
    emit_structured_log_event,
    get_logger,
    is_sensitive_field_name,
    redact_metadata,
    serialize_structured_log_event,
)


# ---------------------------------------------------------------------------
# 1. Basic structured event
# ---------------------------------------------------------------------------


def test_basic_structured_event_has_expected_shape():
    event = build_structured_log_event(event_name="corpus_refresh.stage_started", component="corpus_refresh")
    assert isinstance(event, StructuredLogEvent)
    assert event.schema_version == LOG_SCHEMA_VERSION
    assert event.event_name == "corpus_refresh.stage_started"
    assert event.component == "corpus_refresh"
    assert event.level == "INFO"
    assert event.metadata == {}


# ---------------------------------------------------------------------------
# 2. Required fields
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_event_name", ["", "   ", None])
def test_missing_event_name_is_rejected(bad_event_name):
    with pytest.raises(ValueError):
        build_structured_log_event(event_name=bad_event_name, component="api")


@pytest.mark.parametrize("bad_component", ["", "   ", None])
def test_missing_component_is_rejected(bad_component):
    with pytest.raises(ValueError):
        build_structured_log_event(event_name="request.completed", component=bad_component)


# ---------------------------------------------------------------------------
# 3. Event name/type
# ---------------------------------------------------------------------------


def test_event_name_round_trips_through_serialization():
    event = build_structured_log_event(event_name="backup.snapshot_created", component="backup", timestamp="2026-01-01T00:00:00+00:00")
    payload = json.loads(serialize_structured_log_event(event))
    assert payload["event_name"] == "backup.snapshot_created"


# ---------------------------------------------------------------------------
# 4. Timestamp handling
# ---------------------------------------------------------------------------


def test_default_timestamp_is_iso8601_utc():
    from datetime import datetime

    event = build_structured_log_event(event_name="request.completed", component="api")
    parsed = datetime.fromisoformat(event.timestamp)
    assert parsed.tzinfo is not None


def test_injected_timestamp_is_used_verbatim():
    event = build_structured_log_event(event_name="request.completed", component="api", timestamp="2026-01-01T00:00:00+00:00")
    assert event.timestamp == "2026-01-01T00:00:00+00:00"


def test_empty_timestamp_is_rejected():
    with pytest.raises(ValueError):
        build_structured_log_event(event_name="request.completed", component="api", timestamp="")


# ---------------------------------------------------------------------------
# 5. Severity/level
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
def test_valid_levels_are_accepted(level):
    event = build_structured_log_event(event_name="request.completed", component="api", level=level)
    assert event.level == level


def test_invalid_level_is_rejected():
    with pytest.raises(ValueError):
        build_structured_log_event(event_name="request.completed", component="api", level="TRACE")


# ---------------------------------------------------------------------------
# 6. Operation/component
# ---------------------------------------------------------------------------


def test_component_names_the_operational_owner():
    event = build_structured_log_event(event_name="corpus_refresh.stage_started", component="corpus_refresh")
    assert event.component == "corpus_refresh"


# ---------------------------------------------------------------------------
# 7. Request/correlation ID
# ---------------------------------------------------------------------------


def test_request_id_defaults_to_none_and_can_be_set():
    default_event = build_structured_log_event(event_name="request.completed", component="api")
    assert default_event.request_id is None

    correlated_event = build_structured_log_event(event_name="request.completed", component="api", request_id="req-abc-123")
    assert correlated_event.request_id == "req-abc-123"
    payload = json.loads(serialize_structured_log_event(correlated_event))
    assert payload["request_id"] == "req-abc-123"


# ---------------------------------------------------------------------------
# 8. Status/outcome
# ---------------------------------------------------------------------------


def test_outcome_is_stored_and_serialized():
    event = build_structured_log_event(event_name="request.completed", component="api", outcome="success")
    assert event.outcome == "success"
    payload = json.loads(serialize_structured_log_event(event))
    assert payload["outcome"] == "success"


# ---------------------------------------------------------------------------
# 9. Latency field
# ---------------------------------------------------------------------------


def test_latency_ms_is_stored_as_float():
    event = build_structured_log_event(event_name="request.completed", component="api", latency_ms=42)
    assert event.latency_ms == 42.0
    assert isinstance(event.latency_ms, float)


def test_negative_latency_is_rejected():
    with pytest.raises(ValueError):
        build_structured_log_event(event_name="request.completed", component="api", latency_ms=-1.0)


def test_latency_ms_defaults_to_none():
    event = build_structured_log_event(event_name="request.completed", component="api")
    assert event.latency_ms is None


# ---------------------------------------------------------------------------
# 10. Safe diagnostic metadata
# ---------------------------------------------------------------------------


def test_non_sensitive_metadata_passes_through_unchanged():
    event = build_structured_log_event(
        event_name="corpus_refresh.stage_completed",
        component="corpus_refresh",
        metadata={"document_count": 3, "stage": "validate"},
    )
    assert event.metadata == {"document_count": 3, "stage": "validate"}


def test_none_metadata_becomes_empty_dict():
    event = build_structured_log_event(event_name="request.completed", component="api", metadata=None)
    assert event.metadata == {}


def test_non_dict_metadata_does_not_raise():
    event = build_structured_log_event(event_name="request.completed", component="api", metadata=["not", "a", "dict"])
    assert isinstance(event.metadata, dict)


# ---------------------------------------------------------------------------
# 11. Sensitive-field redaction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field_name",
    ["api_key", "apiKey", "API_KEY", "X-API-Key", "secret", "client_secret", "password", "passwd", "pwd", "token", "access_token", "Authorization", "authorization", "bearer_token", "credential", "credentials"],
)
def test_is_sensitive_field_name_recognizes_common_secret_spellings(field_name):
    assert is_sensitive_field_name(field_name) is True


@pytest.mark.parametrize("field_name", ["document_count", "stage", "status", "jurisdiction", "duration_ms"])
def test_is_sensitive_field_name_leaves_ordinary_fields_alone(field_name):
    assert is_sensitive_field_name(field_name) is False


def test_redact_metadata_replaces_sensitive_values_deterministically():
    redacted = redact_metadata({"api_key": "sk-real-value", "stage": "validate"})
    assert redacted["api_key"] == "***REDACTED***"
    assert redacted["stage"] == "validate"


# ---------------------------------------------------------------------------
# 12. API-key redaction
# ---------------------------------------------------------------------------


def test_api_key_value_never_reaches_serialized_output():
    event = build_structured_log_event(
        event_name="provider.call", component="generation", metadata={"api_key": "sk-super-secret-value"}
    )
    serialized = serialize_structured_log_event(event)
    assert "sk-super-secret-value" not in serialized
    assert "***REDACTED***" in serialized


# ---------------------------------------------------------------------------
# 13. Authorization/bearer-token redaction
# ---------------------------------------------------------------------------


def test_authorization_header_and_bearer_token_are_redacted():
    event = build_structured_log_event(
        event_name="request.received",
        component="api",
        metadata={"Authorization": "Bearer super-secret-jwt", "bearer_token": "super-secret-jwt-2"},
    )
    serialized = serialize_structured_log_event(event)
    assert "super-secret-jwt" not in serialized
    assert "super-secret-jwt-2" not in serialized


# ---------------------------------------------------------------------------
# 14. Password/secret redaction
# ---------------------------------------------------------------------------


def test_password_and_secret_are_redacted():
    event = build_structured_log_event(
        event_name="config.loaded", component="api", metadata={"password": "hunter2", "client_secret": "s3cr3t-value"}
    )
    serialized = serialize_structured_log_event(event)
    assert "hunter2" not in serialized
    assert "s3cr3t-value" not in serialized


# ---------------------------------------------------------------------------
# 15. Unserializable metadata
# ---------------------------------------------------------------------------


class _Unserializable:
    def __repr__(self) -> str:
        return "<_Unserializable instance>"


def test_unserializable_metadata_value_does_not_raise():
    event = build_structured_log_event(
        event_name="diagnostic.captured",
        component="corpus_refresh",
        metadata={"weird_object": _Unserializable(), "a_set": {1, 2, 3}},
    )
    # Must be fully JSON-serializable now, and must not have crashed above.
    serialized = serialize_structured_log_event(event)
    json.loads(serialized)  # re-parses without error


def test_metadata_with_circular_reference_does_not_raise():
    circular: dict = {"self": None}
    circular["self"] = circular
    event = build_structured_log_event(event_name="diagnostic.captured", component="corpus_refresh", metadata={"payload": circular})
    serialized = serialize_structured_log_event(event)
    json.loads(serialized)


# ---------------------------------------------------------------------------
# 16. Logging failure must not crash caller
# ---------------------------------------------------------------------------


class _ExplodingLogger:
    def log(self, level, msg, *args, **kwargs):
        raise RuntimeError("simulated logging backend failure")


def test_emit_structured_log_event_never_raises_on_broken_logger():
    event = build_structured_log_event(event_name="request.completed", component="api")
    result = emit_structured_log_event(_ExplodingLogger(), event)
    assert result is False


def test_emit_structured_log_event_returns_true_on_success(caplog):
    event = build_structured_log_event(event_name="request.completed", component="api", timestamp="2026-01-01T00:00:00+00:00")
    logger = get_logger("test_phase_21_logging")
    with caplog.at_level(logging.INFO, logger=logger.name):
        result = emit_structured_log_event(logger, event)
    assert result is True
    assert any("request.completed" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# 17. Deterministic serialization for equivalent non-time-varying input
# ---------------------------------------------------------------------------


def test_equivalent_events_serialize_identically():
    event_a = build_structured_log_event(
        event_name="corpus_refresh.stage_completed",
        component="corpus_refresh",
        outcome="success",
        request_id="req-1",
        latency_ms=12.5,
        metadata={"stage": "validate", "document_count": 3},
        timestamp="2026-01-01T00:00:00+00:00",
    )
    event_b = build_structured_log_event(
        event_name="corpus_refresh.stage_completed",
        component="corpus_refresh",
        outcome="success",
        request_id="req-1",
        latency_ms=12.5,
        metadata={"document_count": 3, "stage": "validate"},  # different insertion order
        timestamp="2026-01-01T00:00:00+00:00",
    )
    assert serialize_structured_log_event(event_a) == serialize_structured_log_event(event_b)


def test_events_differing_only_in_timestamp_are_not_forced_equal():
    event_a = build_structured_log_event(event_name="request.completed", component="api", timestamp="2026-01-01T00:00:00+00:00")
    event_b = build_structured_log_event(event_name="request.completed", component="api", timestamp="2026-01-01T00:00:01+00:00")
    assert serialize_structured_log_event(event_a) != serialize_structured_log_event(event_b)


# ---------------------------------------------------------------------------
# 18. Compatibility with existing Phase 17 exception logging behavior
# ---------------------------------------------------------------------------


def test_get_logger_reuses_the_existing_api_errors_logger():
    from api.errors import logger as api_errors_logger

    assert get_logger("api") is api_errors_logger


def test_existing_logger_exception_behavior_is_unaffected(caplog):
    from api.errors import logger as api_errors_logger

    with caplog.at_level(logging.ERROR, logger=api_errors_logger.name):
        try:
            raise ValueError("boom")
        except ValueError:
            api_errors_logger.exception("unhandled exception while processing %s %s", "GET", "/health")
    assert any("unhandled exception" in record.message for record in caplog.records)
