"""
Phase 10 grounding primitives (docs/PHASE_10_GROUNDED_GENERATION.md
Sections F, G, H, J).

Two responsibilities, both deliberately thin wrappers around Phase 8/9,
never a reimplementation of either:

1. `extract_citation_references`: parses a provider's raw ANSWER text
   (never evidence_text) for citation markers, producing untrusted
   `citation.models.CitationReference` objects. This is parsing only -
   it does not decide validity. A malformed/fabricated marker becomes a
   perfectly constructible (per Phase 9's own deliberately-permissive
   `CitationReference`) reference that Phase 9's validator will later
   classify INVALID/UNRESOLVED - never repaired, never guessed here.

2. `evidence_context_lines` / `allowed_evidence_ids`: read directly from
   a Phase 8 `EvidencePack` - no second, independent evidence
   representation is created (per explicit instruction). `EvidencePack`
   IS the evidence context.
"""

from __future__ import annotations

import re

from citation.models import CitationReference
from evidence.models import EvidencePack

# [OUR ENHANCEMENT] Citation-marker convention: a provider cites evidence
# by emitting `[[CITE:<evidence_id>]]` inline in its answer text. This is
# a Phase 10 design choice (not established by the Master Reference) -
# chosen because it lets a real free-text-generating LLM name citations
# without requiring a separate structured output channel, while keeping
# extraction a single, auditable regex with no code execution risk.
# `[^\]]*` never spans a `]`, so a citation marker can never itself
# contain another `]]`-terminated marker; this is a linear-time scan with
# no catastrophic-backtracking risk on adversarially large input.
CITATION_MARKER_PATTERN = re.compile(r"\[\[CITE:([^\]]*)\]\]")


def extract_citation_references(raw_text: str) -> list:
    """
    Parses `raw_text` (a provider's ANSWER, never evidence_text) for
    `[[CITE:<id>]]` markers, in occurrence order. The captured `<id>` is
    passed through completely unchanged - it is untrusted DATA, never
    executed, never repaired, never fuzzy-matched. Classifying it is
    Phase 9's job (`citation.validator.validate_citations`), never this
    function's.
    """
    if not isinstance(raw_text, str):
        raise TypeError(f"extract_citation_references expects a string, got {type(raw_text).__name__}")
    return [CitationReference(evidence_id=match.group(1)) for match in CITATION_MARKER_PATTERN.finditer(raw_text)]


def allowed_evidence_ids(pack: EvidencePack) -> frozenset:
    """The real, backend-owned evidence_id values a provider may cite - never invented, always read from Phase 8's own EvidencePack."""
    if not isinstance(pack, EvidencePack):
        raise TypeError(f"allowed_evidence_ids expects an EvidencePack, got {type(pack).__name__}")
    return frozenset(e.evidence_id for e in pack.evidence_items)


def evidence_context_items(pack: EvidencePack, max_items=None) -> list:
    """
    Returns the Evidence objects to include in the prompt, in the pack's
    own existing (already-deterministic) order - never re-ranked,
    re-selected, or filtered here (that would duplicate Phase 8's own
    selection logic, `evidence.builder.build_evidence_pack`). `max_items`
    only ever truncates from the end of that existing order.
    """
    if not isinstance(pack, EvidencePack):
        raise TypeError(f"evidence_context_items expects an EvidencePack, got {type(pack).__name__}")
    items = list(pack.evidence_items)
    if max_items is not None:
        items = items[:max_items]
    return items
