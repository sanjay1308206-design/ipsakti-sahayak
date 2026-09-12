"""
Phase 8 — Evidence Object + Citation Architecture.

A deterministic, provenance-preserving evidence layer between retrieval
(Phases 5-7) and future grounded generation (Phase 10) - see
docs/PHASE_08_EVIDENCE_OBJECT_AND_CITATION_ARCHITECTURE.md.

The Evidence layer is the trust boundary: retrieval says "this chunk may
be relevant"; Evidence says "this exact chunk, with this exact provenance
and source location, is the evidence object available to downstream
systems." No LLM is required anywhere in this package.

Explicitly out of scope here: generated-answer citation validation
(Phase 9), claim/evidence binding from generated answers (Phase 9),
grounded generation (Phase 10), the jurisdiction firewall (Phase 12), the
confidence engine (Phase 13).
"""

from .builder import build_evidence_from_candidate, build_evidence_pack, resolve_citation_target
from .models import (
    EVIDENCE_SCHEMA_VERSION,
    EVIDENCE_TYPES,
    PACK_SCHEMA_VERSION,
    CitationTarget,
    Evidence,
    EvidenceIntegrityError,
    EvidenceNotFoundError,
    EvidencePack,
    EvidenceSelectionConfig,
    RetrievalMetadata,
    SourceLocation,
    VersionInfo,
)
from .validation import verify_evidence_identity, verify_evidence_text_integrity, verify_pack_identity, verify_pack_integrity

__all__ = [
    "build_evidence_from_candidate",
    "build_evidence_pack",
    "resolve_citation_target",
    "Evidence",
    "EvidencePack",
    "CitationTarget",
    "EvidenceSelectionConfig",
    "RetrievalMetadata",
    "SourceLocation",
    "VersionInfo",
    "EvidenceIntegrityError",
    "EvidenceNotFoundError",
    "EVIDENCE_SCHEMA_VERSION",
    "PACK_SCHEMA_VERSION",
    "EVIDENCE_TYPES",
    "verify_evidence_text_integrity",
    "verify_evidence_identity",
    "verify_pack_identity",
    "verify_pack_integrity",
]
