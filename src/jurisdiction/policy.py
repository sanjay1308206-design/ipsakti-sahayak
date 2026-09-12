"""
Phase 12 normalization and corpus-policy mapping
(docs/PHASE_12_JURISDICTION_FIREWALL.md Sections I, J). Deterministic
only - never derived from IP/physical location, language detection, or
any external lookup, and no country database is built.
`[ENGINEERING RECOMMENDATION]`/`[ASSUMPTION]` per explicit instruction:
this project's closed vocabulary has NO country-level granularity (only
INDIA/INTERNATIONAL/BOTH/UNSPECIFIED), so normalization is deliberately
limited to case/whitespace variants of those four exact tokens - never an
invented country-alias database.
"""

from __future__ import annotations

from typing import Optional

from .models import EVIDENCE_JURISDICTION_VALUES, REQUEST_JURISDICTION_VALUES

# Deterministic normalization: uppercase + strip only. No country aliases
# are defined because none are supported by any existing project
# vocabulary (docs "COUNTRY NAMES" - country-level legal behavior remains
# [DEFERRED]). A value that normalizes (after case/whitespace folding) to
# something OTHER than one of the four canonical tokens is NOT_SUPPORTED,
# never guessed into INTERNATIONAL merely because it "sounds foreign."
def normalize_requested_jurisdiction(raw: Optional[str]) -> Optional[str]:
    """Returns a member of REQUEST_JURISDICTION_VALUES, or None if `raw` cannot be normalized to one."""
    if raw is None:
        return None
    if not isinstance(raw, str):
        return None
    candidate = raw.strip().upper()
    if candidate in REQUEST_JURISDICTION_VALUES:
        return candidate
    return None


# The ONLY corpus-policy mapping this phase defines: request-side value ->
# the permitted subset of the EVIDENCE-side vocabulary
# (docs Section J). BOTH legitimately maps to the union (Phase 1's own
# taxonomy: "the question legitimately spans both") - never a guess.
_PERMITTED_EVIDENCE_JURISDICTIONS_BY_REQUEST = {
    "INDIA": frozenset({"INDIA"}),
    "INTERNATIONAL": frozenset({"INTERNATIONAL"}),
    "BOTH": frozenset({"INDIA", "INTERNATIONAL"}),
    # UNSPECIFIED deliberately maps to the empty set - fail closed, never
    # "everything" and never "India by default".
    "UNSPECIFIED": frozenset(),
}


def permitted_evidence_jurisdictions(normalized_jurisdiction: Optional[str]) -> frozenset:
    """
    Maps a normalized REQUEST-side jurisdiction value onto the permitted
    subset of the EVIDENCE-side vocabulary. Returns the empty frozenset
    for anything not a recognized member of REQUEST_JURISDICTION_VALUES -
    fail closed, never an unrestricted default.
    """
    if normalized_jurisdiction not in REQUEST_JURISDICTION_VALUES:
        return frozenset()
    return _PERMITTED_EVIDENCE_JURISDICTIONS_BY_REQUEST[normalized_jurisdiction]


def blocked_evidence_jurisdictions(allowed: frozenset) -> frozenset:
    """The exact complement of `allowed` over the full evidence-jurisdiction vocabulary."""
    return EVIDENCE_JURISDICTION_VALUES - allowed
