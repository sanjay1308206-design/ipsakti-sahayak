"""
Phase 14 input-side preservation (docs/PHASE_14_MULTILINGUAL_DELIVERY.md
Sections J, K, L). `detect_script` is a deterministic, Unicode-codepoint-
range classification ONLY - never a language identification claim, never
a jurisdiction signal, and never used to infer either. `canonicalize_query`
is Unicode NFC normalization ONLY - a meaning-preserving text-representation
normalization, never a translation and never a rewrite of user intent.

No language-detection model, no external service, no network call
anywhere in this module - this is deliberately "the smallest safe
language-handling mechanism" the project can honestly claim (per explicit
instruction not to claim universal or perfect language detection).
"""

from __future__ import annotations

import unicodedata
from typing import Optional

from .models import MULTILINGUAL_SCHEMA_VERSION, MultilingualInputContext

# Unicode codepoint ranges - Basic Latin + Latin-1 Supplement letters,
# Devanagari, Tamil. [OFFICIAL SOURCE - Unicode Standard block
# assignments, not project-specific]. Deliberately narrow: only the
# scripts this project's own prior-phase tests (Phase 5/6/7/8/9/10/11/12/13)
# already exercise are named; anything else is honestly reported UNKNOWN
# rather than guessed.
_LATIN_RANGES = ((0x0041, 0x005A), (0x0061, 0x007A), (0x00C0, 0x00FF))
_DEVANAGARI_RANGE = (0x0900, 0x097F)
_TAMIL_RANGE = (0x0B80, 0x0BFF)


def detect_script(text: str) -> str:
    """
    Returns one of `models.SCRIPT_TAGS`. Purely a count of which of the
    three known Unicode letter ranges appear in `text` - zero matches is
    UNKNOWN (never guessed), more than one distinct script is MIXED
    (never silently collapsed to either), exactly one is that script's tag.
    """
    if not isinstance(text, str):
        raise TypeError(f"detect_script expects a string, got {type(text).__name__}")

    found = set()
    for ch in text:
        cp = ord(ch)
        if _DEVANAGARI_RANGE[0] <= cp <= _DEVANAGARI_RANGE[1]:
            found.add("DEVANAGARI")
        elif _TAMIL_RANGE[0] <= cp <= _TAMIL_RANGE[1]:
            found.add("TAMIL")
        elif any(lo <= cp <= hi for lo, hi in _LATIN_RANGES):
            found.add("LATIN")

    if not found:
        return "UNKNOWN"
    if len(found) > 1:
        return "MIXED"
    return next(iter(found))


def canonicalize_query(text: str) -> str:
    """
    Unicode NFC normalization ONLY (docs Section L) - collapses combining-
    character variants into one canonical representation. This is a
    well-established, meaning-preserving standard text transformation
    (`[OFFICIAL SOURCE]` - Unicode Standard Annex #15), never a
    translation, never a rewrite of user intent, never dependent on
    detected script or requested language.
    """
    if not isinstance(text, str):
        raise TypeError(f"canonicalize_query expects a string, got {type(text).__name__}")
    return unicodedata.normalize("NFC", text)


def build_input_context(input_id: str, original_query: str, requested_language: Optional[str] = None) -> MultilingualInputContext:
    """
    The sole input-side entry point. `original_query` is preserved
    verbatim on the returned object - it is never overwritten by
    `canonical_query`, and remains recoverable from the structured result
    (docs Section J).
    """
    if not isinstance(input_id, str) or not input_id.strip():
        raise ValueError("input_id must be a non-empty string")
    if not isinstance(original_query, str):
        raise TypeError(f"build_input_context expects original_query to be a string, got {type(original_query).__name__}")
    if requested_language is not None and not isinstance(requested_language, str):
        raise TypeError(
            f"build_input_context expects requested_language to be a string or None, got {type(requested_language).__name__}"
        )

    return MultilingualInputContext(
        schema_version=MULTILINGUAL_SCHEMA_VERSION,
        input_id=input_id,
        original_query=original_query,
        canonical_query=canonicalize_query(original_query),
        detected_script=detect_script(original_query),
        requested_language=requested_language,
    )
