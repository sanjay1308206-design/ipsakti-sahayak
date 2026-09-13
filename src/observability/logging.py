"""
Phase 21 structured operational logging convention
(docs/PHASE_21_OBSERVABILITY_BACKUP_CORPUS_REFRESH.md Section 7,
config/phase_21_observability.yaml `logging`).

`[ENGINEERING RECOMMENDATION]` Extends, never replaces, `src/api/errors.py`'s
existing Python stdlib `logging` usage (`logger = logging.getLogger("ipsakti.api")`,
`logger.exception(...)`) - this module reuses the SAME stdlib `logging`
registry (`get_logger` returns `logging.getLogger(f"ipsakti.{component}")`,
so `get_logger("api") is` the identical logger object `api.errors.logger`
already uses, Python's own logger registry being a process-wide singleton
keyed by name). No second, competing logging backend is introduced (no
structlog, no loguru, no external log-aggregation service - docs Section 24).

This module is server-side operational logging only - a structured event
is never returned to a client (unchanged Phase 17 Section M/Y invariant)
and this module performs no HTTP response construction of any kind.

FAILURE SAFETY (docs Section 6 / `[OFFICIAL SOURCE]` "structured logging
must never crash the application merely because diagnostic metadata is
malformed or unserializable"): building a `StructuredLogEvent` validates
its own declared shape (event_name/component/level/etc - a caller
programming error there is a real bug and IS raised, exactly like every
other Phase 21 dataclass in this package); but arbitrary, possibly
untrusted DIAGNOSTIC METADATA values are always made JSON-safe without
raising (`_json_safe`), and `emit_structured_log_event` additionally
catches and swallows any failure in serialization/emission itself. This
module never suppresses or replaces a real application exception - it
only guarantees that ITS OWN instrumentation cannot become a second
source of failure.

REDACTION (docs Section 5): `redact_metadata` conservatively replaces the
value of any metadata key whose name plausibly denotes a secret (API
keys, passwords, tokens, authorization headers, credentials) with a fixed
placeholder, deterministically and before any serialization - so a
redacted value can never leak through the JSON-safety fallback either.
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

LOG_SCHEMA_VERSION = "1.0.0"

LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})

_LEVEL_NUMBERS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

_REDACTED_PLACEHOLDER = "***REDACTED***"

# [ENGINEERING RECOMMENDATION] conservative, deterministic redaction: any
# metadata key whose normalized (lowercased, separator-stripped) form
# CONTAINS one of these substrings is redacted, never emitted - this
# covers compound spellings (`apiKey`, `client_secret`, `Authorization`,
# `access-token`, `Bearer-Token`, `X-API-Key`) without an exhaustive
# enumeration of every possible field-name spelling. An occasional false
# positive (redacting a benign field that happens to contain one of these
# substrings) is an accepted, deliberate cost of staying conservative
# (docs Section 5) - never the reverse.
_SENSITIVE_SUBSTRINGS = (
    "apikey",
    "key",
    "secret",
    "password",
    "passwd",
    "pwd",
    "token",
    "auth",
    "credential",
    "bearer",
)


def _check_non_empty_string(name: str, value) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _normalize_field_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def is_sensitive_field_name(name: str) -> bool:
    """True if `name` (any case/separator style) names a field that must never be logged in the clear."""
    if not isinstance(name, str):
        return False
    normalized = _normalize_field_name(name)
    return any(substring in normalized for substring in _SENSITIVE_SUBSTRINGS)


def redact_metadata(metadata: Optional[dict]) -> dict:
    """
    Returns a NEW dict with every sensitive-named key's value replaced by
    a fixed placeholder (`is_sensitive_field_name`) - deterministic and
    total: never raises regardless of what `metadata` contains. `None`
    yields `{}`. A non-dict input is coerced into a single diagnostic
    key rather than raising, since malformed diagnostic input must never
    crash the caller (docs Section 6).
    """
    if metadata is None:
        return {}
    if not isinstance(metadata, dict):
        return {"_diagnostic_metadata_type_error": f"expected dict, got {type(metadata).__name__}"}

    redacted: dict = {}
    for key, value in metadata.items():
        key_str = key if isinstance(key, str) else repr(key)
        redacted[key_str] = _REDACTED_PLACEHOLDER if is_sensitive_field_name(key_str) else value
    return redacted


def _safe_json_default(value: Any) -> str:
    """`json.dumps(..., default=...)` fallback for anything stdlib `json` cannot serialize natively - always a safe string, never re-raises."""
    try:
        return f"<unserializable:{type(value).__name__}>"
    except Exception:
        return "<unserializable>"


def _json_safe(value: Any) -> Any:
    """
    Best-effort, NEVER-RAISING conversion of `value` into something
    already round-tripped through `json.dumps(..., default=_safe_json_default,
    sort_keys=True)` / `json.loads` - covers ordinary malformed diagnostic
    values (sets, custom objects, bytes) via `default`, and covers the
    rarer case `default` cannot reach (e.g. a circular-reference container,
    which `json` rejects before `default` is ever called) via the
    surrounding `try/except`.
    """
    try:
        return json.loads(json.dumps(value, default=_safe_json_default, sort_keys=True))
    except Exception:
        try:
            return _safe_json_default(value)
        except Exception:
            return "<unserializable>"


@dataclass(frozen=True)
class StructuredLogEvent:
    """
    One operational log record (docs Section 7). Every field is already a
    plain, JSON-serializable value by construction - `metadata` has
    already been redacted (`redact_metadata`) and made JSON-safe
    (`_json_safe`) by `build_structured_log_event`, never a caller's raw
    object graph.
    """

    schema_version: str
    event_name: str
    timestamp: str
    level: str
    component: str
    outcome: Optional[str]
    request_id: Optional[str]
    latency_ms: Optional[float]
    error_type: Optional[str]
    metadata: dict

    def __post_init__(self):
        _check_non_empty_string("schema_version", self.schema_version)
        _check_non_empty_string("event_name", self.event_name)
        _check_non_empty_string("timestamp", self.timestamp)
        _check_non_empty_string("component", self.component)
        if self.level not in LOG_LEVELS:
            raise ValueError(f"level must be one of {sorted(LOG_LEVELS)}, got {self.level!r}")
        for name in ("outcome", "request_id", "error_type"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{name} must be a string or None, got {value!r}")
        if self.latency_ms is not None:
            if isinstance(self.latency_ms, bool) or not isinstance(self.latency_ms, (int, float)):
                raise ValueError(f"latency_ms must be a number or None, got {self.latency_ms!r}")
            if self.latency_ms < 0:
                raise ValueError("latency_ms must be non-negative")
            if not math.isfinite(self.latency_ms):
                raise ValueError("latency_ms must be finite")
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dict")


def build_structured_log_event(
    *,
    event_name: str,
    component: str,
    level: str = "INFO",
    outcome: Optional[str] = None,
    request_id: Optional[str] = None,
    latency_ms: Optional[float] = None,
    error_type: Optional[str] = None,
    metadata: Optional[dict] = None,
    timestamp: Optional[str] = None,
) -> StructuredLogEvent:
    """
    The single Phase 21 entry point for constructing one structured
    operational log event.

    `timestamp` defaults to the current UTC wall-clock time (ISO 8601 via
    `datetime.now(timezone.utc).isoformat()`) but may be supplied
    explicitly - the only mechanism this module offers for deterministic
    comparison of otherwise wall-clock-dependent output (docs Section 21
    determinism note / Section 7 timestamp note). This is never a claim
    that real, un-injected emitted timestamps are themselves deterministic
    or globally synchronized across environments - only that equivalent
    input plus an equivalent (or injected) timestamp yields byte-identical
    serialization (`serialize_structured_log_event`).

    `metadata` is redacted (`redact_metadata`) and made JSON-safe
    (`_json_safe`) here, before the event is ever constructed - a
    malformed or sensitive metadata value can never reach a caller's
    logger unredacted or cause this function to raise.
    """
    resolved_timestamp = timestamp if timestamp is not None else datetime.now(timezone.utc).isoformat()
    safe_metadata = _json_safe(redact_metadata(metadata))
    if not isinstance(safe_metadata, dict):
        safe_metadata = {"_diagnostic_metadata_error": "metadata did not round-trip to a JSON object"}

    return StructuredLogEvent(
        schema_version=LOG_SCHEMA_VERSION,
        event_name=event_name,
        timestamp=resolved_timestamp,
        level=level,
        component=component,
        outcome=outcome,
        request_id=request_id,
        latency_ms=float(latency_ms) if latency_ms is not None else None,
        error_type=error_type,
        metadata=safe_metadata,
    )


def serialize_structured_log_event(event: StructuredLogEvent) -> str:
    """
    Deterministic JSON serialization of `event` - `sort_keys=True` so
    equivalent events (including equivalent, differently-ordered metadata
    dicts) always produce byte-identical output (docs Section 21 "avoid
    nondeterministic dictionary ordering").
    """
    if not isinstance(event, StructuredLogEvent):
        raise TypeError(f"event must be a StructuredLogEvent, got {type(event).__name__}")
    payload = {
        "schema_version": event.schema_version,
        "event_name": event.event_name,
        "timestamp": event.timestamp,
        "level": event.level,
        "component": event.component,
        "outcome": event.outcome,
        "request_id": event.request_id,
        "latency_ms": event.latency_ms,
        "error_type": event.error_type,
        "metadata": event.metadata,
    }
    return json.dumps(payload, sort_keys=True, default=_safe_json_default)


def get_logger(component: str) -> logging.Logger:
    """
    Returns the same stdlib `logging.Logger` object `src/api/errors.py`
    already uses for a given component name - `get_logger("api")` IS
    `logging.getLogger("ipsakti.api")`, the identical object
    `api.errors.logger` already is (Python's logger registry is a
    process-wide singleton keyed by name), so this utility reuses,
    never replaces or duplicates, that existing logging backend.
    """
    _check_non_empty_string("component", component)
    return logging.getLogger(f"ipsakti.{component}")


def emit_structured_log_event(logger: logging.Logger, event: StructuredLogEvent) -> bool:
    """
    Serializes `event` and emits it through `logger` at its own declared
    level.

    FAILURE-SAFE BY DESIGN (docs Section 6): any exception raised while
    serializing or emitting is caught here and never propagated to the
    caller. Returns `True` if the structured record was successfully
    emitted, `False` if emission instead fell back to a minimal,
    best-effort record (or failed silently) because of a defect in this
    logging path itself - a value callers may inspect for their own
    diagnostics, never one they are required to check.

    This function never suppresses or replaces a real application
    exception raised by the caller's own code - it only guarantees that
    ITS OWN instrumentation cannot raise.
    """
    try:
        serialized = serialize_structured_log_event(event)
        level_number = _LEVEL_NUMBERS.get(event.level, logging.INFO)
        logger.log(level_number, serialized)
        return True
    except Exception:
        try:
            logger.log(logging.ERROR, "structured log event could not be serialized/emitted (event_name=%r)", getattr(event, "event_name", None))
        except Exception:
            pass
        return False
