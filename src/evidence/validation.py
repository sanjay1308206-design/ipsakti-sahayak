"""
Cross-object integrity verification (docs/PHASE_08_EVIDENCE_OBJECT_AND_CITATION_ARCHITECTURE.md
Section Y). Per-object structural validation (missing fields, wrong
types, empty text, malformed page numbers/block IDs) already happens in
each dataclass's own `__post_init__` (models.py) - the functions here
verify identity/hash CONSISTENCY, which cannot be checked at construction
time alone (a hand-crafted or corrupted-after-load Evidence/EvidencePack
can have internally well-typed but mutually inconsistent fields).

Tampering must be detectable: every function here recomputes an identity
or hash from an object's OWN other fields and compares it to the stored
value, raising EvidenceIntegrityError on any mismatch - never silently
accepting a forged evidence_id, a corrupted evidence_text_hash, or a
tampered pack_id.
"""

from __future__ import annotations

import hashlib

from .identity import compute_evidence_id, compute_pack_id
from .models import Evidence, EvidenceIntegrityError, EvidencePack


def verify_evidence_text_integrity(evidence: Evidence) -> None:
    """Detects evidence_text tampering: recomputes the hash and compares."""
    recomputed = hashlib.sha256(evidence.evidence_text.encode("utf-8")).hexdigest()
    if recomputed != evidence.evidence_text_hash:
        raise EvidenceIntegrityError(
            f"evidence_text_hash mismatch for evidence_id {evidence.evidence_id!r} - "
            f"the text may have been tampered with"
        )


def verify_evidence_identity(evidence: Evidence) -> None:
    """Detects a forged/hand-edited evidence_id: recomputes it from the evidence's own other fields."""
    recomputed = compute_evidence_id(
        evidence.evidence_schema_version,
        evidence.chunk_id,
        evidence.content_hash,
        evidence.document_id,
        evidence.source_family_id,
        evidence.jurisdiction,
        evidence.block_ids,
        evidence.page_numbers,
    )
    if recomputed != evidence.evidence_id:
        raise EvidenceIntegrityError(
            f"evidence_id {evidence.evidence_id!r} does not match the identity recomputed from its own "
            f"provenance fields - possible fabricated or tampered evidence ID"
        )


def verify_pack_identity(pack: EvidencePack) -> None:
    """
    Detects a forged/hand-edited pack_id. Requires `construction_metadata`
    to carry `config_signature` (always true for packs produced by
    builder.build_evidence_pack) - raises EvidenceIntegrityError if absent
    rather than silently skipping the check.
    """
    config_signature = pack.construction_metadata.get("config_signature")
    if config_signature is None:
        raise EvidenceIntegrityError(
            "EvidencePack.construction_metadata is missing 'config_signature' - cannot verify pack identity"
        )
    recomputed = compute_pack_id(
        pack.schema_version, pack.query, [e.evidence_id for e in pack.evidence_items], config_signature
    )
    if recomputed != pack.pack_id:
        raise EvidenceIntegrityError(
            f"pack_id {pack.pack_id!r} does not match the identity recomputed from its own fields - "
            f"the pack metadata may be corrupted or tampered"
        )


def verify_pack_integrity(pack: EvidencePack) -> None:
    """
    Full pack-level integrity check: every evidence item's text and
    identity are self-consistent, no duplicate evidence_id or chunk_id
    exists (EvidencePack.__post_init__ already guarantees this for
    freshly-constructed packs, re-checked here for defense-in-depth after
    deserialization), and the pack's own identity matches its contents.
    """
    if not isinstance(pack, EvidencePack):
        raise TypeError(f"verify_pack_integrity expects an EvidencePack, got {type(pack).__name__}")
    for evidence in pack.evidence_items:
        verify_evidence_text_integrity(evidence)
        verify_evidence_identity(evidence)

    evidence_ids = [e.evidence_id for e in pack.evidence_items]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise EvidenceIntegrityError("EvidencePack contains duplicate evidence_id values")
    chunk_ids = [e.chunk_id for e in pack.evidence_items]
    if len(chunk_ids) != len(set(chunk_ids)):
        raise EvidenceIntegrityError("EvidencePack contains duplicate underlying chunk_id values")

    verify_pack_identity(pack)
