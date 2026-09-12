"""
Phase 2 test-support module: a small, deterministic reference evaluator for
the corpus admission policy described in
docs/PHASE_02_CORPUS_ADMISSION_POLICY.md and
docs/PHASE_02_SOURCE_CONFLICT_POLICY.md.

This is NOT a document ingestion, download, scraping, OCR, or parsing
component. It never touches a real file and never performs network I/O.
It only evaluates an already-fully-specified, in-memory provenance record
(real records do not exist yet; this project's own tests pass only
synthetic fixtures, each required to set synthetic=True).

Not a test module itself (no test_ prefix) - pytest will not collect it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

ADMISSION_STATES = frozenset(
    {"ADMIT", "ADMIT_WITH_RESTRICTION", "HOLD_FOR_VALIDATION", "REJECT", "SUPERSEDED"}
)

VALID_JURISDICTIONS = frozenset({"INDIA", "INTERNATIONAL", "NOT_APPLICABLE", "OTHER_UNSPECIFIED"})

RULE_ORDER = ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A10", "A11", "A12")


@dataclass(frozen=True)
class ProvenanceRecord:
    synthetic: bool  # must be True for any record passed by this project's tests
    source_family_id: str
    jurisdiction: str
    document_id: str
    content_hash: str
    validation_status: str  # UNVALIDATED | VALIDATED | VALIDATION_FAILED
    supersession_status: str  # CURRENT | SUPERSEDED | SUPERSEDES_ANOTHER | UNKNOWN
    version_known: bool
    effective_date_known: bool
    conflict_status: str | None = None  # NONE | CONFLICTING | RESOLVED | None
    known_conflicting_with: list = field(default_factory=list)


@dataclass(frozen=True)
class AdmissionResult:
    admission_status: str
    rule_id: str
    reason_codes: list = field(default_factory=list)


def evaluate_admission(
    record: ProvenanceRecord,
    known_source_family_ids: frozenset,
    source_family_jurisdictions: dict,
) -> AdmissionResult:
    """
    Evaluate rules A1..A12 in fixed order; first match wins.

    known_source_family_ids: the set of registered source_family_id values
      (from config/authority_matrix.yaml).
    source_family_jurisdictions: mapping of source_family_id -> its fixed
      jurisdiction_scope (from config/authority_matrix.yaml), used to
      detect jurisdiction/source-family mismatches (rule A3).
    """
    assert record.synthetic is True, (
        "the reference evaluator only accepts records explicitly marked synthetic=True; "
        "this project never evaluates a real document in Phase 2"
    )

    # A1 — UNKNOWN_SOURCE_FAMILY
    if record.source_family_id not in known_source_family_ids:
        return _result("REJECT", "A1", ["UNKNOWN_SOURCE_FAMILY"])

    # A2 — UNKNOWN_JURISDICTION
    if record.jurisdiction not in VALID_JURISDICTIONS:
        return _result("REJECT", "A2", ["UNKNOWN_JURISDICTION"])

    # A3 — JURISDICTION_MISMATCH
    expected_jurisdiction = source_family_jurisdictions.get(record.source_family_id)
    if expected_jurisdiction is not None and record.jurisdiction != expected_jurisdiction:
        return _result("REJECT", "A3", ["JURISDICTION_MISMATCH"])

    # A4 — MISSING_DOCUMENT_IDENTITY
    if not record.document_id or not record.document_id.strip():
        return _result("HOLD_FOR_VALIDATION", "A4", ["MISSING_DOCUMENT_IDENTITY"])

    # A5 — MISSING_CONTENT_HASH
    if not record.content_hash or not record.content_hash.strip():
        return _result("HOLD_FOR_VALIDATION", "A5", ["MISSING_CONTENT_HASH"])

    # A6 — VALIDATION_NOT_CONFIRMED
    if record.validation_status != "VALIDATED":
        return _result("HOLD_FOR_VALIDATION", "A6", ["VALIDATION_NOT_CONFIRMED"])

    # A7 — DOCUMENT_SUPERSEDED
    if record.supersession_status == "SUPERSEDED":
        return _result("SUPERSEDED", "A7", ["DOCUMENT_SUPERSEDED"])

    # A8 — UNRESOLVED_CONFLICT
    if record.conflict_status == "CONFLICTING":
        return _result("HOLD_FOR_VALIDATION", "A8", ["UNRESOLVED_CONFLICT"])

    # A9 — MISSING_CONFLICT_STATUS_DESPITE_KNOWN_CONFLICT
    if record.known_conflicting_with and record.conflict_status in (None, "", "NONE"):
        return _result(
            "HOLD_FOR_VALIDATION", "A9", ["MISSING_CONFLICT_STATUS_DESPITE_KNOWN_CONFLICT"]
        )

    # A10 — VERSION_UNKNOWN_RESTRICTED
    if not record.version_known and not record.effective_date_known:
        return _result("ADMIT_WITH_RESTRICTION", "A10", ["VERSION_UNKNOWN_RESTRICTED"])

    # A11 — SUPERSESSION_STATUS_UNKNOWN
    if record.supersession_status == "UNKNOWN":
        return _result("ADMIT_WITH_RESTRICTION", "A11", ["SUPERSESSION_STATUS_UNKNOWN"])

    # A12 — DEFAULT_ADMIT
    return _result("ADMIT", "A12", [])


def _result(status: str, rule_id: str, reasons: list) -> AdmissionResult:
    assert status in ADMISSION_STATES
    return AdmissionResult(admission_status=status, rule_id=rule_id, reason_codes=reasons)
