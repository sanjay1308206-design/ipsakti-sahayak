"""
Admission-boundary enforcement (docs/PHASE_03_DOCUMENT_INGESTION.md Section C).

Verifies a caller-supplied provenance record (shape:
config/corpus_provenance_schema.yaml) against the Phase 2 corpus policy
(config/authority_matrix.yaml) BEFORE any byte of the document is parsed.

This is real production code (unlike tests/_admission_policy_reference_impl.py,
which is Phase 2 test-support only) - it is the actual boundary Phase 3's
pipeline enforces. It reimplements the same policy shape documented in
docs/PHASE_02_CORPUS_ADMISSION_POLICY.md, applied specifically to the
"may this document enter extraction at all" question.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

ACCEPTED_ADMISSION_STATES = frozenset({"ADMIT", "ADMIT_WITH_RESTRICTION"})

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_AUTHORITY_MATRIX_PATH = REPO_ROOT / "config" / "authority_matrix.yaml"


@dataclass(frozen=True)
class AdmissionCheckResult:
    passed: bool
    reason_codes: list = field(default_factory=list)


def load_authority_matrix(path: Path = DEFAULT_AUTHORITY_MATRIX_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def check_admission_boundary(provenance: dict, authority_matrix: dict) -> AdmissionCheckResult:
    """Ordered, first-failure-wins. See docs/PHASE_03_DOCUMENT_INGESTION.md Section C."""

    families_by_id = {
        fam["source_family_id"]: fam for fam in authority_matrix["source_families"]
    }

    document_id = provenance.get("document_id")
    if not document_id or not str(document_id).strip():
        return AdmissionCheckResult(False, ["MISSING_DOCUMENT_IDENTITY"])

    source_family_id = provenance.get("source_family_id")
    if not source_family_id:
        return AdmissionCheckResult(False, ["MISSING_SOURCE_FAMILY"])

    family = families_by_id.get(source_family_id)
    if family is None:
        return AdmissionCheckResult(False, ["UNKNOWN_SOURCE_FAMILY"])

    if family.get("corpus_role") != "EVIDENCE_SOURCE":
        return AdmissionCheckResult(False, ["SOURCE_FAMILY_NOT_EVIDENCE_SOURCE"])

    jurisdiction = provenance.get("jurisdiction")
    valid_jurisdictions = set(authority_matrix.get("valid_jurisdictions", []))
    if not jurisdiction or jurisdiction not in valid_jurisdictions:
        return AdmissionCheckResult(False, ["UNKNOWN_JURISDICTION"])

    if jurisdiction != family.get("jurisdiction_scope"):
        return AdmissionCheckResult(False, ["JURISDICTION_MISMATCH"])

    content_hash = provenance.get("content_hash")
    if not content_hash or not str(content_hash).strip():
        return AdmissionCheckResult(False, ["MISSING_CONTENT_HASH"])

    admission_status = provenance.get("admission_status")
    if admission_status not in ACCEPTED_ADMISSION_STATES:
        return AdmissionCheckResult(False, ["INVALID_ADMISSION_STATE"])

    return AdmissionCheckResult(True, [])
