"""
Phase 9 deterministic citation validation
(docs/PHASE_09_CITATION_VALIDATION.md Sections J, K, L, M, N, O).

Answers exactly one question per CitationReference: "does this reference
resolve to real, valid Evidence in this EvidencePack?" Never "is the
underlying legal claim correct?" - see docs Section Q for that boundary.

Deliberately REUSES Phase 8 validation instead of duplicating it:
- exact-match resolution reuses `evidence.models.CitationTarget` +
  `evidence.builder.resolve_citation_target` verbatim (the same
  exact-`==`-only lookup Phase 8 already implements - never
  reimplemented here with subtly different semantics).
- evidence integrity reuses `evidence.validation.verify_evidence_text_integrity`
  and `verify_evidence_identity` verbatim, scoped to the ONE Evidence
  object a citation actually resolves to.
- EvidencePack-identity validation reuses `evidence.validation.verify_pack_identity`
  verbatim (deliberately NOT the heavier `verify_pack_integrity`, which
  would shadow per-evidence integrity checking - see
  `check_evidence_pack_validity`'s own docstring for why).

No LLM, no network, no filesystem access, no randomness anywhere in this
module. Citation reference content (evidence_id, display metadata) and
Evidence text are always treated as DATA - never executed, never
interpreted as configuration, never allowed to alter validator behavior,
selection, or resolution (docs Section U).
"""

from __future__ import annotations

from typing import Optional

from evidence.builder import resolve_citation_target
from evidence.models import (
    PACK_SCHEMA_VERSION,
    CitationTarget,
    Evidence,
    EvidenceIntegrityError,
    EvidenceNotFoundError,
    EvidencePack,
)
from evidence.validation import verify_evidence_identity, verify_evidence_text_integrity, verify_pack_identity

from .models import (
    REASON_EVIDENCE_ID_MISSING,
    REASON_EVIDENCE_INTEGRITY_FAILURE,
    REASON_EVIDENCE_NOT_FOUND,
    REASON_EVIDENCE_PROVENANCE_FAILURE,
    REASON_INVALID_PACK,
    REASON_MALFORMED_REFERENCE,
    REASON_SCHEMA_MISMATCH,
    SUPPORTED_CITATION_REFERENCE_SCHEMA_VERSIONS,
    CitationReference,
    CitationValidationResult,
    ResolvedEvidenceSummary,
)

# EvidencePack schema versions this validator knows how to resolve
# against. A pack declaring any other value is treated as INVALID_PACK -
# never assumed compatible, never guessed.
SUPPORTED_EVIDENCE_PACK_SCHEMA_VERSIONS = frozenset({PACK_SCHEMA_VERSION})


def check_evidence_pack_validity(pack: EvidencePack) -> Optional[str]:
    """
    EvidencePack validation BEFORE any citation is resolved against it
    (docs Section J). Returns None if the pack's own identity/shape may be
    trusted for resolution; otherwise a human-readable (never fabricated)
    description of why it fails safely. Never repairs, never partially
    trusts a tampered pack.

    Deliberately a PACK-IDENTITY-LEVEL gate, not a full per-evidence-item
    integrity walk: it reuses Phase 8's `verify_pack_identity` (catches a
    forged/tampered `pack_id`, and requires `construction_metadata` to
    carry `config_signature`) plus a defense-in-depth duplicate-ID
    re-check (structurally impossible through normal construction -
    `EvidencePack.__post_init__` already guarantees it - but checked
    again here in case an `EvidencePack` reached this function via some
    path that bypassed its own constructor).

    Per-evidence text/identity integrity (docs Section N) is deliberately
    NOT checked here - it is checked in `_validate_single`, scoped to the
    ONE Evidence object a specific citation actually resolves to. This
    means one tampered Evidence item inside an otherwise-intact pack
    invalidates only citations pointing AT that item (EVIDENCE_INTEGRITY_FAILURE)
    - it does not silently invalidate citations to the pack's other,
    untampered evidence. Using the heavier `verify_pack_integrity` here
    instead would make EVIDENCE_INTEGRITY_FAILURE unreachable dead code,
    since it already walks every evidence item itself.
    """
    if not isinstance(pack, EvidencePack):
        raise TypeError(f"check_evidence_pack_validity expects an EvidencePack, got {type(pack).__name__}")
    if pack.schema_version not in SUPPORTED_EVIDENCE_PACK_SCHEMA_VERSIONS:
        return (
            f"EvidencePack.schema_version {pack.schema_version!r} is not a schema version this "
            f"validator supports ({sorted(SUPPORTED_EVIDENCE_PACK_SCHEMA_VERSIONS)})"
        )
    evidence_ids = [e.evidence_id for e in pack.evidence_items]
    if len(evidence_ids) != len(set(evidence_ids)):
        return "EvidencePack contains duplicate evidence_id values"
    chunk_ids = [e.chunk_id for e in pack.evidence_items]
    if len(chunk_ids) != len(set(chunk_ids)):
        return "EvidencePack contains duplicate underlying chunk_id values"
    try:
        verify_pack_identity(pack)
    except EvidenceIntegrityError as exc:
        return str(exc)
    return None


def _check_evidence_provenance_shape(evidence: Evidence) -> Optional[str]:
    """
    Defensive structural re-check of an already-resolved Evidence object's
    provenance fields (docs Section M). In practice unreachable through
    the normal construction path - `Evidence.__post_init__` already
    enforces every one of these invariants - but Phase 9 does not assume
    every Evidence object it is ever handed necessarily passed through
    that constructor (e.g. a hand-corrupted in-memory object). Fails
    closed rather than trusting silently.
    """
    for name in ("document_id", "source_family_id", "jurisdiction"):
        value = getattr(evidence, name, None)
        if not isinstance(value, str) or not value.strip():
            return f"evidence.{name} is missing or empty"
    content_hash = getattr(evidence, "content_hash", None)
    if not isinstance(content_hash, str) or len(content_hash) != 64:
        return "evidence.content_hash is not a well-formed 64-character hex digest"
    if not getattr(evidence, "page_numbers", None):
        return "evidence.page_numbers is empty"
    if not getattr(evidence, "block_ids", None):
        return "evidence.block_ids is empty"
    return None


def _safe_requested_id(evidence_id) -> Optional[str]:
    """Never store a non-string value into a field typed Optional[str] - the raw value still reaches `detail`."""
    return evidence_id if isinstance(evidence_id, str) else None


def _result(
    reference: CitationReference,
    *,
    status: str,
    reason_code: Optional[str],
    requested_evidence_id: Optional[str],
    resolved_evidence: Optional[ResolvedEvidenceSummary],
    occurrence_index: int,
    is_duplicate_occurrence: bool,
    detail: Optional[str],
) -> CitationValidationResult:
    return CitationValidationResult(
        citation_reference=reference,
        status=status,
        reason_code=reason_code,
        requested_evidence_id=requested_evidence_id,
        resolved_evidence=resolved_evidence,
        occurrence_index=occurrence_index,
        is_duplicate_occurrence=is_duplicate_occurrence,
        detail=detail,
    )


def _validate_single(
    reference: CitationReference,
    pack: EvidencePack,
    pack_error: Optional[str],
    occurrence_index: int,
    is_duplicate_occurrence: bool,
) -> CitationValidationResult:
    # 1. EvidencePack must already be trustworthy - never validate a
    #    citation "against" a pack we know is corrupted/tampered (docs
    #    Section J). This applies uniformly to every reference in the
    #    batch, regardless of that reference's own shape.
    if pack_error is not None:
        return _result(
            reference,
            status="INVALID",
            reason_code=REASON_INVALID_PACK,
            requested_evidence_id=_safe_requested_id(reference.evidence_id),
            resolved_evidence=None,
            occurrence_index=occurrence_index,
            is_duplicate_occurrence=is_duplicate_occurrence,
            detail=f"EvidencePack failed validation, so no citation can be resolved against it: {pack_error}",
        )

    # 2. Citation reference schema version (docs Section I/F).
    schema_version = reference.schema_version
    if not isinstance(schema_version, str) or schema_version not in SUPPORTED_CITATION_REFERENCE_SCHEMA_VERSIONS:
        return _result(
            reference,
            status="INVALID",
            reason_code=REASON_SCHEMA_MISMATCH,
            requested_evidence_id=_safe_requested_id(reference.evidence_id),
            resolved_evidence=None,
            occurrence_index=occurrence_index,
            is_duplicate_occurrence=is_duplicate_occurrence,
            detail=f"unsupported citation reference schema_version: {schema_version!r}",
        )

    # 3. evidence_id presence/shape (docs Section K/L) - no fuzzy repair,
    #    ever. A missing evidence_id is distinguished from a
    #    present-but-malformed one only for a clearer reason code; both
    #    are INVALID.
    evidence_id = reference.evidence_id
    if evidence_id is None:
        return _result(
            reference,
            status="INVALID",
            reason_code=REASON_EVIDENCE_ID_MISSING,
            requested_evidence_id=None,
            resolved_evidence=None,
            occurrence_index=occurrence_index,
            is_duplicate_occurrence=is_duplicate_occurrence,
            detail="citation reference has no evidence_id",
        )

    # CitationTarget's own __post_init__ (Phase 8) is the single source of
    # truth for "is this a well-formed evidence_id string" - reused here
    # rather than re-implementing the same non-empty-string check.
    try:
        target = CitationTarget(evidence_id=evidence_id)
    except (ValueError, TypeError) as exc:
        return _result(
            reference,
            status="INVALID",
            reason_code=REASON_MALFORMED_REFERENCE,
            requested_evidence_id=_safe_requested_id(evidence_id),
            resolved_evidence=None,
            occurrence_index=occurrence_index,
            is_duplicate_occurrence=is_duplicate_occurrence,
            detail=str(exc),
        )

    # 4. Exact-match resolution (docs Section K/L) - reuses Phase 8's
    #    resolve_citation_target verbatim: exact `==` comparison only, no
    #    fuzzy/partial/case-insensitive matching, no filesystem search.
    try:
        evidence = resolve_citation_target(target, pack)
    except EvidenceNotFoundError as exc:
        return _result(
            reference,
            status="UNRESOLVED",
            reason_code=REASON_EVIDENCE_NOT_FOUND,
            requested_evidence_id=evidence_id,
            resolved_evidence=None,
            occurrence_index=occurrence_index,
            is_duplicate_occurrence=is_duplicate_occurrence,
            detail=str(exc),
        )

    # 5. Provenance structural shape re-check (docs Section M) - defensive,
    #    see _check_evidence_provenance_shape docstring. Deliberately
    #    BEFORE the cryptographic identity check (step 6): every field
    #    this shape check inspects (document_id, source_family_id,
    #    jurisdiction, content_hash, page_numbers, block_ids) is ALSO an
    #    input to Phase 8's evidence_id hash (evidence.identity.compute_evidence_id)
    #    - so a shape violation in any of them would ALSO make the hash
    #    fail to recompute. Checking shape first keeps
    #    EVIDENCE_PROVENANCE_FAILURE independently reachable (a
    #    structurally malformed field) rather than always being shadowed
    #    by EVIDENCE_INTEGRITY_FAILURE (a well-shaped but forged/tampered
    #    value) - the two reason codes describe genuinely different
    #    failures and this ordering is what makes both reachable.
    provenance_error = _check_evidence_provenance_shape(evidence)
    if provenance_error is not None:
        return _result(
            reference,
            status="INVALID",
            reason_code=REASON_EVIDENCE_PROVENANCE_FAILURE,
            requested_evidence_id=evidence_id,
            resolved_evidence=None,
            occurrence_index=occurrence_index,
            is_duplicate_occurrence=is_duplicate_occurrence,
            detail=provenance_error,
        )

    # 6. Evidence integrity (docs Section N) - reuses Phase 8's own
    #    tamper-detection functions verbatim.
    try:
        verify_evidence_text_integrity(evidence)
        verify_evidence_identity(evidence)
    except EvidenceIntegrityError as exc:
        return _result(
            reference,
            status="INVALID",
            reason_code=REASON_EVIDENCE_INTEGRITY_FAILURE,
            requested_evidence_id=evidence_id,
            resolved_evidence=None,
            occurrence_index=occurrence_index,
            is_duplicate_occurrence=is_duplicate_occurrence,
            detail=str(exc),
        )

    # 7. VALID - synthetic is preserved verbatim, never treated as a
    #    failure (docs Section S).
    summary = ResolvedEvidenceSummary(
        evidence_id=evidence.evidence_id,
        chunk_id=evidence.chunk_id,
        document_id=evidence.document_id,
        source_family_id=evidence.source_family_id,
        jurisdiction=evidence.jurisdiction,
        synthetic=evidence.synthetic,
    )
    return _result(
        reference,
        status="VALID",
        reason_code=None,
        requested_evidence_id=evidence_id,
        resolved_evidence=summary,
        occurrence_index=occurrence_index,
        is_duplicate_occurrence=is_duplicate_occurrence,
        detail=None,
    )


def validate_citation(reference: CitationReference, pack: EvidencePack) -> CitationValidationResult:
    """Validate exactly one CitationReference against one EvidencePack. Safe to call standalone."""
    if not isinstance(reference, CitationReference):
        raise TypeError(f"validate_citation expects a CitationReference, got {type(reference).__name__}")
    pack_error = check_evidence_pack_validity(pack)
    return _validate_single(reference, pack, pack_error, occurrence_index=0, is_duplicate_occurrence=False)


def validate_citations(references: list, pack: EvidencePack) -> list:
    """
    Validate a list of CitationReferences (zero, one, or many) against one
    EvidencePack, in deterministic input order (docs Section O/P/CITATION
    ORDERING). Duplicate occurrences of the same requested evidence_id
    string are flagged (`is_duplicate_occurrence`) but never merged into a
    single result and never treated as an automatic failure - each
    occurrence is independently, identically validated.
    """
    if not isinstance(references, list):
        raise TypeError(f"validate_citations expects a list of CitationReference, got {type(references).__name__}")
    for index, reference in enumerate(references):
        if not isinstance(reference, CitationReference):
            raise TypeError(
                f"validate_citations expects every element to be a CitationReference, "
                f"got {type(reference).__name__} at index {index}"
            )

    # Computed once per call - never re-derived per-reference, so all
    # references in one batch see an identical pack-validity verdict.
    pack_error = check_evidence_pack_validity(pack)

    seen_first_occurrence: dict = {}
    results = []
    for index, reference in enumerate(references):
        evidence_id = reference.evidence_id
        is_duplicate = False
        if isinstance(evidence_id, str) and evidence_id.strip():
            if evidence_id in seen_first_occurrence:
                is_duplicate = True
            else:
                seen_first_occurrence[evidence_id] = index
        results.append(_validate_single(reference, pack, pack_error, index, is_duplicate))
    return results
