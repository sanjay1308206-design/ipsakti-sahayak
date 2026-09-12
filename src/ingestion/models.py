"""
Normalized document representation shapes, mirroring
config/document_structure_schema.yaml and config/document_ingestion_contract.yaml.

Pure data holders only - no I/O, no parsing logic here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

PIPELINE_STATES = frozenset(
    {
        "READY_FOR_INGESTION",
        "REJECTED_INPUT",
        "EXTRACTION_SUCCESS",
        "EXTRACTION_PARTIAL",
        "EXTRACTION_FAILED",
        "OCR_REQUIRED",
        "QUARANTINED",
    }
)

DETECTION_STATES = frozenset({"DETECTED", "NOT_DETECTED", "UNKNOWN"})
BLOCK_TYPES = frozenset({"HEADING", "PARAGRAPH", "TABLE", "LIST", "LIST_ITEM", "UNKNOWN"})
PAGE_EXTRACTION_STATUSES = frozenset({"SUCCESS", "EMPTY", "OCR_REQUIRED", "FAILED"})
TABLE_EXTRACTION_STATUSES = frozenset({"DETECTED", "NOT_ATTEMPTED_FOR_PDF", "NOT_APPLICABLE"})
DOCUMENT_TYPES = frozenset({"TEXT", "HTML", "PDF"})


@dataclass(frozen=True)
class Table:
    rows: list  # list[list[str]]
    detection_status: str

    def __post_init__(self):
        assert self.detection_status in DETECTION_STATES


@dataclass(frozen=True)
class Block:
    block_id: str
    sequence: int
    block_type: str
    text: str
    page_number: int
    heading_level: Optional[Union[int, str]] = None  # int 1-6, "UNKNOWN", or None
    parent_section: Optional[str] = None
    table: Optional[Table] = None
    warnings: list = field(default_factory=list)

    def __post_init__(self):
        assert self.block_type in BLOCK_TYPES, f"invalid block_type: {self.block_type!r}"


@dataclass(frozen=True)
class Page:
    page_number: int
    extraction_status: str
    blocks: list  # list[Block]
    warnings: list = field(default_factory=list)

    def __post_init__(self):
        assert self.extraction_status in PAGE_EXTRACTION_STATUSES


@dataclass(frozen=True)
class Integrity:
    claimed_content_hash: str
    computed_content_hash: str
    match: bool


@dataclass(frozen=True)
class TitleInfo:
    detection_status: str
    text: Optional[str] = None

    def __post_init__(self):
        assert self.detection_status in DETECTION_STATES


@dataclass(frozen=True)
class ExtractedDocument:
    document_id: str
    source_family_id: str
    jurisdiction: str
    document_type: str
    synthetic: bool
    integrity: Integrity
    extraction_status: str
    table_extraction_status: str
    title: TitleInfo
    pages: list  # list[Page]
    warnings: list = field(default_factory=list)

    def __post_init__(self):
        assert self.document_type in DOCUMENT_TYPES
        assert self.table_extraction_status in TABLE_EXTRACTION_STATUSES


@dataclass(frozen=True)
class IngestionResult:
    """Top-level result of ingest_document()/ingest_bytes()."""

    pipeline_state: str
    document: Optional[ExtractedDocument] = None
    reason_codes: list = field(default_factory=list)

    def __post_init__(self):
        assert self.pipeline_state in PIPELINE_STATES
