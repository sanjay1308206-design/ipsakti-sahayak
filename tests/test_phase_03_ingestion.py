"""
Phase 3 tests: src/ingestion/pipeline.py end-to-end behavior - admission
boundary, file-level safety checks, integrity verification, and extraction
outcome states.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from _pdf_fixtures import make_malformed_pdf, make_minimal_text_pdf
from _provenance_fixtures import make_provenance

from ingestion.hashing import compute_content_hash
from ingestion.pipeline import ingest_bytes, ingest_document
from ingestion.serialize import to_json

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def _ingest(data: bytes, extension: str, authority_matrix: dict, **provenance_overrides):
    provenance = make_provenance(compute_content_hash(data), **provenance_overrides)
    return ingest_bytes(data, provenance, extension, authority_matrix=authority_matrix)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_valid_admitted_text_input_succeeds(authority_matrix: dict):
    data = b"1. Purpose\n\nThis document sets out the purpose.\n"
    result = _ingest(data, ".txt", authority_matrix)
    assert result.pipeline_state == "EXTRACTION_SUCCESS"
    assert result.document is not None
    assert result.document.extraction_status == "EXTRACTION_SUCCESS"


def test_admit_with_restriction_is_accepted(authority_matrix: dict):
    data = b"Some restricted-but-admitted content.\n"
    result = _ingest(data, ".txt", authority_matrix, admission_status="ADMIT_WITH_RESTRICTION")
    assert result.pipeline_state != "REJECTED_INPUT"


# ---------------------------------------------------------------------------
# Admission-boundary rejections (critical negative tests 1-6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_status", ["REJECT", "HOLD_FOR_VALIDATION", "SUPERSEDED"])
def test_invalid_admission_states_are_rejected(authority_matrix: dict, bad_status: str):
    data = b"content"
    result = _ingest(data, ".txt", authority_matrix, admission_status=bad_status)
    assert result.pipeline_state == "REJECTED_INPUT"
    assert "INVALID_ADMISSION_STATE" in result.reason_codes


def test_missing_document_id_is_rejected(authority_matrix: dict):
    data = b"content"
    result = _ingest(data, ".txt", authority_matrix, document_id="")
    assert result.pipeline_state == "REJECTED_INPUT"
    assert "MISSING_DOCUMENT_IDENTITY" in result.reason_codes


def test_missing_source_family_is_rejected(authority_matrix: dict):
    data = b"content"
    provenance = make_provenance(compute_content_hash(data))
    del provenance["source_family_id"]
    result = ingest_bytes(data, provenance, ".txt", authority_matrix=authority_matrix)
    assert result.pipeline_state == "REJECTED_INPUT"
    assert "MISSING_SOURCE_FAMILY" in result.reason_codes


def test_unknown_source_family_is_rejected(authority_matrix: dict):
    data = b"content"
    result = _ingest(data, ".txt", authority_matrix, source_family_id="SF-99")
    assert result.pipeline_state == "REJECTED_INPUT"
    assert "UNKNOWN_SOURCE_FAMILY" in result.reason_codes


def test_service_adapter_source_family_is_rejected(authority_matrix: dict):
    # SF-08 (Bhashini) is a service adapter, never an evidence source.
    data = b"content"
    result = _ingest(data, ".txt", authority_matrix, source_family_id="SF-08")
    assert result.pipeline_state == "REJECTED_INPUT"
    assert "SOURCE_FAMILY_NOT_EVIDENCE_SOURCE" in result.reason_codes


def test_invalid_jurisdiction_is_rejected(authority_matrix: dict):
    data = b"content"
    result = _ingest(data, ".txt", authority_matrix, jurisdiction="MARS")
    assert result.pipeline_state == "REJECTED_INPUT"
    assert "UNKNOWN_JURISDICTION" in result.reason_codes


def test_jurisdiction_mismatch_is_rejected(authority_matrix: dict):
    # SF-06 (WIPO) is INTERNATIONAL; claiming INDIA is a mismatch.
    data = b"content"
    result = _ingest(data, ".txt", authority_matrix, source_family_id="SF-06", jurisdiction="INDIA")
    assert result.pipeline_state == "REJECTED_INPUT"
    assert "JURISDICTION_MISMATCH" in result.reason_codes


def test_missing_content_hash_is_rejected(authority_matrix: dict):
    data = b"content"
    provenance = make_provenance(compute_content_hash(data))
    provenance["content_hash"] = ""
    result = ingest_bytes(data, provenance, ".txt", authority_matrix=authority_matrix)
    assert result.pipeline_state == "REJECTED_INPUT"
    assert "MISSING_CONTENT_HASH" in result.reason_codes


# ---------------------------------------------------------------------------
# Integrity / hash correctness (critical negative test #7)
# ---------------------------------------------------------------------------


def test_content_hash_mismatch_is_quarantined(authority_matrix: dict):
    data = b"real content"
    provenance = make_provenance("0" * 64)  # fabricated/mismatched hash
    result = ingest_bytes(data, provenance, ".txt", authority_matrix=authority_matrix)
    assert result.pipeline_state == "QUARANTINED"
    assert "CONTENT_HASH_MISMATCH" in result.reason_codes


def test_content_hash_correctness_when_matching(authority_matrix: dict):
    data = b"exact bytes"
    result = _ingest(data, ".txt", authority_matrix)
    assert result.document.integrity.claimed_content_hash == compute_content_hash(data)
    assert result.document.integrity.computed_content_hash == compute_content_hash(data)
    assert result.document.integrity.match is True


# ---------------------------------------------------------------------------
# Duplicate / different content (critical negative test #13)
# ---------------------------------------------------------------------------


def test_duplicate_byte_identical_input_produces_same_hash(authority_matrix: dict):
    data = b"identical content"
    r1 = _ingest(data, ".txt", authority_matrix, document_id="DOC-A")
    r2 = _ingest(data, ".txt", authority_matrix, document_id="DOC-B")
    assert r1.document.integrity.computed_content_hash == r2.document.integrity.computed_content_hash


def test_different_content_produces_different_hash(authority_matrix: dict):
    r1 = _ingest(b"content A", ".txt", authority_matrix)
    r2 = _ingest(b"content B", ".txt", authority_matrix)
    assert r1.document.integrity.computed_content_hash != r2.document.integrity.computed_content_hash


# ---------------------------------------------------------------------------
# Empty / malformed / unsupported (critical negative tests #8, #9, #11)
# ---------------------------------------------------------------------------


def test_empty_document_is_quarantined(authority_matrix: dict):
    result = _ingest(b"", ".txt", authority_matrix)
    assert result.pipeline_state == "QUARANTINED"
    assert "EMPTY_FILE" in result.reason_codes


def test_malformed_pdf_extraction_failed(authority_matrix: dict):
    data = make_malformed_pdf()
    result = _ingest(data, ".pdf", authority_matrix)
    assert result.pipeline_state == "EXTRACTION_FAILED"
    assert "PARSER_EXCEPTION" in result.document.warnings


def test_unsupported_file_type_is_rejected(authority_matrix: dict):
    data = b"whatever"
    result = _ingest(data, ".docx", authority_matrix)
    assert result.pipeline_state == "REJECTED_INPUT"
    assert "UNSUPPORTED_DOCUMENT_TYPE" in result.reason_codes


# ---------------------------------------------------------------------------
# Extraction success / partial / failed / OCR_REQUIRED
# ---------------------------------------------------------------------------


def test_extraction_partial_on_decode_error(authority_matrix: dict):
    invalid_utf8 = b"Valid text \xff\xfe more text"
    result = _ingest(invalid_utf8, ".txt", authority_matrix)
    assert result.pipeline_state == "EXTRACTION_PARTIAL"
    assert "DECODE_ERROR_REPLACED_CHARACTERS" in result.document.warnings


def test_extraction_failed_on_whitespace_only_text(authority_matrix: dict):
    result = _ingest(b"   \n\n   \n", ".txt", authority_matrix)
    assert result.pipeline_state == "EXTRACTION_FAILED"


def test_pdf_all_blank_pages_is_ocr_required(authority_matrix: dict):
    from _pdf_fixtures import make_blank_pages_pdf

    data = make_blank_pages_pdf(2)
    result = _ingest(data, ".pdf", authority_matrix)
    assert result.pipeline_state == "OCR_REQUIRED"
    assert all(p.extraction_status == "OCR_REQUIRED" for p in result.document.pages)


# ---------------------------------------------------------------------------
# Page preservation / block ordering / determinism
# ---------------------------------------------------------------------------


def test_pdf_page_boundaries_preserved(authority_matrix: dict):
    from _pdf_fixtures import make_multi_page_text_pdf

    data = make_multi_page_text_pdf(["First page text", "Second page text"])
    result = _ingest(data, ".pdf", authority_matrix)
    assert [p.page_number for p in result.document.pages] == [1, 2]
    assert result.document.pages[0].blocks[0].text == "First page text"
    assert result.document.pages[1].blocks[0].text == "Second page text"


def test_block_sequence_is_monotonically_increasing_across_pages():
    from _pdf_fixtures import make_multi_page_text_pdf

    data = make_multi_page_text_pdf(["Alpha", "Beta"])
    from ingestion.extractors import extract_pdf

    pages, _, _ = extract_pdf(data, "DOC-SEQ")
    all_blocks = [b for p in pages for b in p.blocks]
    sequences = [b.sequence for b in all_blocks]
    assert sequences == sorted(sequences)
    assert len(set(sequences)) == len(sequences)


def test_deterministic_output_for_identical_input(authority_matrix: dict):
    data = b"1. Scope\n\nApplies to all cases.\n"
    r1 = _ingest(data, ".txt", authority_matrix, document_id="DET-DOC")
    r2 = _ingest(data, ".txt", authority_matrix, document_id="DET-DOC")
    assert to_json(r1.document) == to_json(r2.document)


def test_deterministic_output_excludes_wall_clock_by_default(authority_matrix: dict):
    data = b"content"
    result = _ingest(data, ".txt", authority_matrix)
    json_str = to_json(result.document)
    assert "ingestion_metadata" not in json_str


def test_ingestion_metadata_kept_separate_from_content(authority_matrix: dict):
    data = b"content"
    result = _ingest(data, ".txt", authority_matrix)
    json_a = to_json(result.document, ingested_at="2026-01-01T00:00:00Z")
    json_b = to_json(result.document, ingested_at="2099-12-31T23:59:59Z")
    import json as _json

    content_a = _json.loads(json_a)["content"]
    content_b = _json.loads(json_b)["content"]
    assert content_a == content_b  # timestamp differs but content payload does not


# ---------------------------------------------------------------------------
# File-path entry point / duplicate on-disk fixture handling
# ---------------------------------------------------------------------------


def test_ingest_document_from_disk_within_allowed_root(tmp_path: Path, authority_matrix: dict):
    data = b"1. Title\n\nBody text.\n"
    file_path = tmp_path / "sample.txt"
    file_path.write_bytes(data)
    provenance = make_provenance(compute_content_hash(data))
    result = ingest_document(file_path, provenance, allowed_root=tmp_path, authority_matrix=authority_matrix)
    assert result.pipeline_state == "EXTRACTION_SUCCESS"


def test_ingest_document_missing_file(tmp_path: Path, authority_matrix: dict):
    provenance = make_provenance("0" * 64)
    result = ingest_document(
        tmp_path / "does_not_exist.txt", provenance, allowed_root=tmp_path, authority_matrix=authority_matrix
    )
    assert result.pipeline_state == "QUARANTINED"
    assert "FILE_NOT_FOUND" in result.reason_codes
