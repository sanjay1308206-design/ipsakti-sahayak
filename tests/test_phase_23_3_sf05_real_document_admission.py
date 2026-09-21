"""
Phase 23.3 Step 2E: the FIRST real, non-synthetic corpus document ever
admitted in this project - "Food Safety and Standards (Ayurveda Aahara)
Regulations, 2022" (SF-05, FSSAI), independently verified in Phase 23.3
Step 2C against the actual downloaded PDF (not merely its filename/URL).

These tests exercise the REAL, unmodified Phase 3 ingestion pipeline
(`src/ingestion/pipeline.py::ingest_bytes`, `src/ingestion/admission.py::
check_admission_boundary`) against the REAL persisted PDF bytes in
`data/raw/SF-05/` - never a synthetic fixture standing in for it. No
Phase 3/2 code is modified or bypassed anywhere in this file.

Negative-path tests (hash mismatch, wrong source family, wrong
jurisdiction) reuse the exact same real provenance dict, only mutating
the one field under test - proving the admission boundary itself
rejects bad input, not merely that a hand-built bad fixture looks wrong.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ingestion.admission import load_authority_matrix  # noqa: E402
from ingestion.pipeline import ingest_bytes  # noqa: E402

DOCUMENT_ID = "SF05-FSSAI-AYURVEDA-AAHARA-REGULATIONS-2022"
EXPECTED_SHA256 = "1ae8cfc632fad0a775316a84999a48adb6cf4b47d05bd4faa75f5190c511f699"
EXPECTED_SIZE_BYTES = 2307105

RAW_PDF_PATH = REPO_ROOT / "data" / "raw" / "SF-05" / f"{DOCUMENT_ID}.pdf"
MANIFEST_PATH = REPO_ROOT / "data" / "manifest" / "SF-05" / f"{DOCUMENT_ID}.json"
PROVENANCE_SCHEMA_PATH = REPO_ROOT / "config" / "corpus_provenance_schema.yaml"


@pytest.fixture(scope="module")
def real_pdf_bytes() -> bytes:
    if not RAW_PDF_PATH.is_file():
        pytest.skip(f"real SF-05 PDF not present at {RAW_PDF_PATH} - Phase 23.3.2E admission has not been run in this checkout")
    return RAW_PDF_PATH.read_bytes()


@pytest.fixture(scope="module")
def real_provenance() -> dict:
    if not MANIFEST_PATH.is_file():
        pytest.skip(f"real SF-05 manifest not present at {MANIFEST_PATH} - Phase 23.3.2E admission has not been run in this checkout")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return load_authority_matrix()


@pytest.fixture(scope="module")
def required_provenance_field_names() -> set:
    schema = yaml.safe_load(PROVENANCE_SCHEMA_PATH.read_text(encoding="utf-8"))
    return {f["name"] for f in schema["fields"] if f.get("required")}


# ---------------------------------------------------------------------------
# 1. The real document is genuinely admitted through the unmodified Phase 3 pipeline
# ---------------------------------------------------------------------------


def test_real_pdf_matches_the_independently_verified_hash_and_size(real_pdf_bytes):
    assert len(real_pdf_bytes) == EXPECTED_SIZE_BYTES
    assert hashlib.sha256(real_pdf_bytes).hexdigest() == EXPECTED_SHA256


def test_real_provenance_content_hash_matches_actual_bytes(real_pdf_bytes, real_provenance):
    assert real_provenance["content_hash"] == hashlib.sha256(real_pdf_bytes).hexdigest()


def test_real_provenance_has_every_schema_required_field(real_provenance, required_provenance_field_names):
    missing = required_provenance_field_names - real_provenance.keys()
    assert not missing, f"real SF-05 provenance is missing required fields: {sorted(missing)}"


def test_real_provenance_core_identity_fields(real_provenance):
    assert real_provenance["source_family_id"] == "SF-05"
    assert real_provenance["jurisdiction"] == "INDIA"
    assert real_provenance["synthetic"] is False
    assert real_provenance["document_id"] == DOCUMENT_ID


def test_phase_3_admission_succeeds_for_the_real_document(real_pdf_bytes, real_provenance, authority_matrix):
    result = ingest_bytes(real_pdf_bytes, real_provenance, ".pdf", authority_matrix)
    assert result.pipeline_state == "EXTRACTION_SUCCESS"
    assert result.reason_codes == []
    assert result.document is not None
    assert result.document.synthetic is False
    assert result.document.source_family_id == "SF-05"
    assert result.document.jurisdiction == "INDIA"
    assert result.document.integrity.match is True
    assert result.document.integrity.computed_content_hash == EXPECTED_SHA256
    assert len(result.document.pages) == 27
    assert all(p.extraction_status == "SUCCESS" for p in result.document.pages)


def test_real_document_title_text_appears_somewhere_in_extracted_pages(real_pdf_bytes, real_provenance, authority_matrix):
    # Proves the persisted bytes really are the expected regulation, not
    # merely a same-sized file - the regulation's own declared short name
    # (Devanagari) must appear verbatim in the extracted text.
    result = ingest_bytes(real_pdf_bytes, real_provenance, ".pdf", authority_matrix)
    full_text = "\n".join(b.text for page in result.document.pages for b in page.blocks if getattr(b, "text", None))
    assert "आयुर्वेद आहार" in full_text or "आयुवेि आहार" in full_text or "3092 GI/2022" in full_text


# ---------------------------------------------------------------------------
# 2. Fail-closed: hash mismatch, wrong source family, wrong jurisdiction
# ---------------------------------------------------------------------------


def test_hash_mismatch_is_rejected(real_pdf_bytes, real_provenance, authority_matrix):
    tampered = dict(real_provenance)
    tampered["content_hash"] = "0" * 64  # syntactically valid, definitely wrong
    result = ingest_bytes(real_pdf_bytes, tampered, ".pdf", authority_matrix)
    assert result.pipeline_state == "QUARANTINED"
    assert "CONTENT_HASH_MISMATCH" in result.reason_codes
    assert result.document is None


def test_wrong_source_family_is_rejected(real_pdf_bytes, real_provenance, authority_matrix):
    # SF-08 (Bhashini) is a registered family but corpus_role=SERVICE_ADAPTER,
    # never an evidence source - this document must not be admitted under it.
    wrong_family = dict(real_provenance)
    wrong_family["source_family_id"] = "SF-08"
    result = ingest_bytes(real_pdf_bytes, wrong_family, ".pdf", authority_matrix)
    assert result.pipeline_state == "REJECTED_INPUT"
    assert "SOURCE_FAMILY_NOT_EVIDENCE_SOURCE" in result.reason_codes
    assert result.document is None


def test_unknown_source_family_is_rejected(real_pdf_bytes, real_provenance, authority_matrix):
    unknown_family = dict(real_provenance)
    unknown_family["source_family_id"] = "SF-99"
    result = ingest_bytes(real_pdf_bytes, unknown_family, ".pdf", authority_matrix)
    assert result.pipeline_state == "REJECTED_INPUT"
    assert "UNKNOWN_SOURCE_FAMILY" in result.reason_codes
    assert result.document is None


def test_wrong_jurisdiction_is_rejected(real_pdf_bytes, real_provenance, authority_matrix):
    # SF-05's fixed jurisdiction_scope is INDIA - claiming INTERNATIONAL
    # for the same source family must be rejected as a mismatch, never
    # silently accepted or corrected.
    wrong_jurisdiction = dict(real_provenance)
    wrong_jurisdiction["jurisdiction"] = "INTERNATIONAL"
    result = ingest_bytes(real_pdf_bytes, wrong_jurisdiction, ".pdf", authority_matrix)
    assert result.pipeline_state == "REJECTED_INPUT"
    assert "JURISDICTION_MISMATCH" in result.reason_codes
    assert result.document is None


# ---------------------------------------------------------------------------
# 3. synthetic=true must never be accepted as / mistaken for the real record
# ---------------------------------------------------------------------------


def test_persisted_real_manifest_is_never_synthetic(real_provenance):
    # Regression guard: the tracked, persisted manifest for this specific
    # real document must always declare synthetic=false - never true.
    assert real_provenance["synthetic"] is False


def test_synthetic_true_variant_of_the_same_document_is_distinguishable_and_propagated_not_silently_dropped(real_pdf_bytes, real_provenance, authority_matrix):
    # PROV-SAFE-01 (config/corpus_provenance_schema.yaml): a synthetic=true
    # record may be processed (for testing) but the flag must survive,
    # verbatim, into the pipeline's own output - it must never be silently
    # coerced to false (which would let a test fixture masquerade as real
    # corpus evidence) nor silently coerced to true on a real record.
    synthetic_variant = dict(real_provenance)
    synthetic_variant["synthetic"] = True
    result = ingest_bytes(real_pdf_bytes, synthetic_variant, ".pdf", authority_matrix)
    assert result.pipeline_state == "EXTRACTION_SUCCESS"
    assert result.document.synthetic is True  # faithfully propagated, not silently reset to False

    # The REAL, tracked corpus artifact must remain the synthetic=false
    # one - this synthetic=true variant is constructed only in-memory
    # here and is never what is persisted under data/manifest/SF-05/.
    assert real_provenance["synthetic"] is False
