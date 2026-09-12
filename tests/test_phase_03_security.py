"""
Phase 3 tests: safe handling of untrusted document input
(docs/PHASE_03_DOCUMENT_INGESTION.md Section P).

No claim of complete security - only the specific, documented Phase 3
safeguards are tested here.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from _pdf_fixtures import make_encrypted_pdf, make_malformed_pdf, make_minimal_text_pdf
from _provenance_fixtures import make_provenance

from ingestion import pipeline as pipeline_module
from ingestion.hashing import compute_content_hash
from ingestion.pipeline import ingest_bytes, ingest_document

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Path traversal (critical negative test #12)
# ---------------------------------------------------------------------------


def test_path_traversal_via_dotdot_is_quarantined(tmp_path: Path, authority_matrix: dict):
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    secret_file = outside_dir / "secret.txt"
    secret_file.write_bytes(b"outside content")

    provenance = make_provenance(compute_content_hash(b"outside content"))
    traversal_path = allowed_root / ".." / "outside" / "secret.txt"
    result = ingest_document(traversal_path, provenance, allowed_root=allowed_root, authority_matrix=authority_matrix)
    assert result.pipeline_state == "QUARANTINED"
    assert "PATH_TRAVERSAL_ATTEMPT" in result.reason_codes


def test_path_traversal_via_absolute_path_outside_root_is_quarantined(tmp_path: Path, authority_matrix: dict):
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    outside_file = tmp_path / "elsewhere.txt"
    outside_file.write_bytes(b"elsewhere content")

    provenance = make_provenance(compute_content_hash(b"elsewhere content"))
    result = ingest_document(outside_file, provenance, allowed_root=allowed_root, authority_matrix=authority_matrix)
    assert result.pipeline_state == "QUARANTINED"
    assert "PATH_TRAVERSAL_ATTEMPT" in result.reason_codes


def test_relative_path_within_root_succeeds(tmp_path: Path, authority_matrix: dict):
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    data = b"legitimate content"
    (allowed_root / "doc.txt").write_bytes(data)

    provenance = make_provenance(compute_content_hash(data))
    result = ingest_document("doc.txt", provenance, allowed_root=allowed_root, authority_matrix=authority_matrix)
    assert result.pipeline_state == "EXTRACTION_SUCCESS"


# ---------------------------------------------------------------------------
# Oversized input
# ---------------------------------------------------------------------------


def test_oversized_input_is_quarantined(monkeypatch: pytest.MonkeyPatch, authority_matrix: dict):
    monkeypatch.setattr(pipeline_module, "MAX_INPUT_BYTES", 10)
    data = b"this is definitely more than ten bytes"
    provenance = make_provenance(compute_content_hash(data))
    result = ingest_bytes(data, provenance, ".txt", authority_matrix=authority_matrix)
    assert result.pipeline_state == "QUARANTINED"
    assert "OVERSIZED_INPUT" in result.reason_codes


def test_input_at_exactly_the_limit_is_not_oversized(monkeypatch: pytest.MonkeyPatch, authority_matrix: dict):
    monkeypatch.setattr(pipeline_module, "MAX_INPUT_BYTES", 20)
    data = b"x" * 20
    provenance = make_provenance(compute_content_hash(data))
    result = ingest_bytes(data, provenance, ".txt", authority_matrix=authority_matrix)
    assert "OVERSIZED_INPUT" not in result.reason_codes


# ---------------------------------------------------------------------------
# Empty file (critical negative test #8)
# ---------------------------------------------------------------------------


def test_empty_file_is_quarantined(authority_matrix: dict):
    provenance = make_provenance(compute_content_hash(b""))
    result = ingest_bytes(b"", provenance, ".txt", authority_matrix=authority_matrix)
    assert result.pipeline_state == "QUARANTINED"
    assert "EMPTY_FILE" in result.reason_codes


def test_empty_file_on_disk_is_quarantined(tmp_path: Path, authority_matrix: dict):
    allowed_root = tmp_path
    (allowed_root / "empty.txt").write_bytes(b"")
    provenance = make_provenance(compute_content_hash(b""))
    result = ingest_document("empty.txt", provenance, allowed_root=allowed_root, authority_matrix=authority_matrix)
    assert result.pipeline_state == "QUARANTINED"
    assert "EMPTY_FILE" in result.reason_codes


# ---------------------------------------------------------------------------
# Malformed / encrypted PDF (critical negative test #9)
# ---------------------------------------------------------------------------


def test_malformed_pdf_never_crashes_pipeline(authority_matrix: dict):
    data = make_malformed_pdf()
    provenance = make_provenance(compute_content_hash(data))
    result = ingest_bytes(data, provenance, ".pdf", authority_matrix=authority_matrix)
    assert result.pipeline_state == "EXTRACTION_FAILED"


def test_encrypted_pdf_is_reported_not_fabricated(authority_matrix: dict):
    data = make_encrypted_pdf("Confidential content")
    provenance = make_provenance(compute_content_hash(data))
    result = ingest_bytes(data, provenance, ".pdf", authority_matrix=authority_matrix)
    assert result.pipeline_state == "EXTRACTION_FAILED"
    assert "ENCRYPTED_PDF_UNSUPPORTED" in result.document.warnings
    # No block anywhere fabricates text from an encrypted document.
    for page in result.document.pages:
        assert page.blocks == []


# ---------------------------------------------------------------------------
# Unexpected/binary content presented as TEXT
# ---------------------------------------------------------------------------


def test_binary_content_as_text_does_not_crash(authority_matrix: dict):
    binary_data = bytes(range(256))
    provenance = make_provenance(compute_content_hash(binary_data))
    result = ingest_bytes(binary_data, provenance, ".txt", authority_matrix=authority_matrix)
    assert result.pipeline_state in {"EXTRACTION_PARTIAL", "EXTRACTION_SUCCESS", "EXTRACTION_FAILED"}


def test_pdf_bytes_presented_with_txt_extension_is_handled_without_crash(authority_matrix: dict):
    # Adversarial: PDF bytes but a .txt extension - the TEXT extractor must
    # not crash; it will simply attempt UTF-8 decoding (likely triggering
    # the replacement-character warning path) rather than mis-parsing PDF
    # structure as text.
    pdf_bytes = make_minimal_text_pdf("hello")
    provenance = make_provenance(compute_content_hash(pdf_bytes))
    result = ingest_bytes(pdf_bytes, provenance, ".txt", authority_matrix=authority_matrix)
    assert result.pipeline_state in {"EXTRACTION_PARTIAL", "EXTRACTION_SUCCESS", "EXTRACTION_FAILED"}


# ---------------------------------------------------------------------------
# Unsupported extension (critical negative test #11)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("extension", [".exe", ".sh", ".bat", ".docx", ".zip", ""])
def test_unsupported_extensions_are_rejected(authority_matrix: dict, extension: str):
    data = b"content"
    provenance = make_provenance(compute_content_hash(data))
    result = ingest_bytes(data, provenance, extension, authority_matrix=authority_matrix)
    assert result.pipeline_state == "REJECTED_INPUT"
    assert "UNSUPPORTED_DOCUMENT_TYPE" in result.reason_codes


# ---------------------------------------------------------------------------
# No uncaught exceptions anywhere (INGEST-SAFE-03)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "data,extension",
    [
        (b"", ".pdf"),
        (b"not a pdf at all", ".pdf"),
        (b"\x00\x01\x02\x03", ".html"),
        (b"<html><body><unclosed>", ".html"),
        (bytes(range(256)) * 100, ".txt"),
    ],
    ids=["empty-pdf", "fake-pdf", "null-bytes-html", "unclosed-html", "large-binary-txt"],
)
def test_no_input_ever_raises_an_uncaught_exception(authority_matrix: dict, data: bytes, extension: str):
    provenance = make_provenance(compute_content_hash(data))
    try:
        ingest_bytes(data, provenance, extension, authority_matrix=authority_matrix)
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"ingest_bytes raised an uncaught exception for adversarial input: {exc}")
