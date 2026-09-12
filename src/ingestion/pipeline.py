"""
Ingestion pipeline orchestration (docs/PHASE_03_DOCUMENT_INGESTION.md).

ingest_bytes(): the pure, testable core - admission boundary -> file-level
safety checks -> integrity check -> type-specific extraction.
ingest_document(): a thin path-based wrapper adding path-traversal
protection, for callers working with files already on local disk.

Never downloads anything. Never chunks. Never retrieves. Never generates.
"""

from __future__ import annotations

from pathlib import Path

from .admission import DEFAULT_AUTHORITY_MATRIX_PATH, check_admission_boundary, load_authority_matrix
from .extractors import (
    aggregate_document_extraction_status,
    extract_html,
    extract_pdf,
    extract_text,
)
from .hashing import compute_content_hash
from .models import ExtractedDocument, IngestionResult, Integrity

MAX_INPUT_BYTES = 50_000_000  # [ENGINEERING RECOMMENDATION] see config/document_ingestion_contract.yaml

DOCUMENT_TYPE_BY_EXTENSION = {".txt": "TEXT", ".html": "HTML", ".htm": "HTML", ".pdf": "PDF"}

EXTRACTOR_BY_TYPE = {"TEXT": extract_text, "HTML": extract_html, "PDF": extract_pdf}


def ingest_bytes(
    data: bytes,
    provenance: dict,
    file_extension: str,
    authority_matrix: dict = None,
) -> IngestionResult:
    if authority_matrix is None:
        authority_matrix = load_authority_matrix()

    admission = check_admission_boundary(provenance, authority_matrix)
    if not admission.passed:
        return IngestionResult(pipeline_state="REJECTED_INPUT", reason_codes=admission.reason_codes)

    doc_type = DOCUMENT_TYPE_BY_EXTENSION.get(file_extension.lower())
    if doc_type is None:
        return IngestionResult(pipeline_state="REJECTED_INPUT", reason_codes=["UNSUPPORTED_DOCUMENT_TYPE"])

    if len(data) == 0:
        return IngestionResult(pipeline_state="QUARANTINED", reason_codes=["EMPTY_FILE"])
    if len(data) > MAX_INPUT_BYTES:
        return IngestionResult(pipeline_state="QUARANTINED", reason_codes=["OVERSIZED_INPUT"])

    claimed_hash = str(provenance["content_hash"]).strip().lower()
    computed_hash = compute_content_hash(data)
    if computed_hash != claimed_hash:
        return IngestionResult(pipeline_state="QUARANTINED", reason_codes=["CONTENT_HASH_MISMATCH"])

    integrity = Integrity(claimed_content_hash=claimed_hash, computed_content_hash=computed_hash, match=True)

    document_id = str(provenance["document_id"])
    extractor = EXTRACTOR_BY_TYPE[doc_type]
    pages, warnings, title = extractor(data, document_id)

    had_decode_warning = "DECODE_ERROR_REPLACED_CHARACTERS" in warnings
    extraction_status = aggregate_document_extraction_status(pages, had_decode_warning)

    table_extraction_status = {
        "PDF": "NOT_ATTEMPTED_FOR_PDF",
        "HTML": "DETECTED",
        "TEXT": "NOT_APPLICABLE",
    }[doc_type]

    document = ExtractedDocument(
        document_id=document_id,
        source_family_id=str(provenance["source_family_id"]),
        jurisdiction=str(provenance["jurisdiction"]),
        document_type=doc_type,
        synthetic=bool(provenance.get("synthetic", False)),
        integrity=integrity,
        extraction_status=extraction_status,
        table_extraction_status=table_extraction_status,
        title=title,
        pages=pages,
        warnings=warnings,
    )

    return IngestionResult(pipeline_state=extraction_status, document=document, reason_codes=[])


def ingest_document(
    path,
    provenance: dict,
    allowed_root,
    authority_matrix: dict = None,
) -> IngestionResult:
    """Path-based entry point. `path` must resolve to a location inside `allowed_root`."""
    allowed_root = Path(allowed_root).resolve()
    candidate = Path(path)

    try:
        resolved = (allowed_root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    except (OSError, RuntimeError):
        return IngestionResult(pipeline_state="QUARANTINED", reason_codes=["PATH_TRAVERSAL_ATTEMPT"])

    try:
        resolved.relative_to(allowed_root)
    except ValueError:
        return IngestionResult(pipeline_state="QUARANTINED", reason_codes=["PATH_TRAVERSAL_ATTEMPT"])

    if not resolved.is_file():
        return IngestionResult(pipeline_state="QUARANTINED", reason_codes=["FILE_NOT_FOUND"])

    data = resolved.read_bytes()
    return ingest_bytes(data, provenance, resolved.suffix, authority_matrix=authority_matrix)
