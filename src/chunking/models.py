"""
Phase 4 output data shapes, mirroring config/chunk_schema.yaml and
config/chunking_contract.yaml (docs/PHASE_04_LEGAL_AWARE_CHUNKING.md).

Pure data holders only - no I/O, no chunking logic here (that lives in
rules.py/chunker.py), matching the src/ingestion/models.py convention.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

CHUNKING_STATES = frozenset({"CHUNKING_SUCCESS", "CHUNKING_PARTIAL", "CHUNKING_SKIPPED"})

# Same vocabulary as ingestion.models.BLOCK_TYPES - a chunk always wraps one
# or more Phase 3 blocks and never invents a new block type.
SIZE_UNIT = "UNICODE_CODE_POINTS"  # [ENGINEERING RECOMMENDATION] see docs Section G


@dataclass(frozen=True)
class ChunkingConfig:
    """
    Configurable chunking parameters. `max_chunk_size_chars` is measured in
    Unicode code points (Python `len(str)`), never bytes or tokens - see
    docs/PHASE_04_LEGAL_AWARE_CHUNKING.md Section G for why a tokenizer
    dependency was deliberately not added.
    """

    max_chunk_size_chars: int = 1000
    contract_version: str = "1.0.0"

    def __post_init__(self):
        if not isinstance(self.max_chunk_size_chars, int) or isinstance(self.max_chunk_size_chars, bool):
            raise ValueError(
                f"max_chunk_size_chars must be an int, got {type(self.max_chunk_size_chars).__name__}"
            )
        if self.max_chunk_size_chars <= 0:
            raise ValueError(f"max_chunk_size_chars must be a positive integer, got {self.max_chunk_size_chars}")

    @property
    def signature(self) -> str:
        """Deterministic, canonical string identity for this config - part of chunk_id derivation."""
        return f"chunking-config:v{self.contract_version}:max={self.max_chunk_size_chars}:unit={SIZE_UNIT}"


@dataclass(frozen=True)
class Chunk:
    """
    One retrieval-ready unit. `chunk_id` is an engineering identifier only -
    it must never be presented as, or confused with, a legal citation
    (Phase 8 owns citation architecture). See docs/PHASE_04_LEGAL_AWARE_CHUNKING.md
    Section D/F.
    """

    chunk_id: str
    chunk_sequence: int
    document_id: str
    source_family_id: str
    jurisdiction: str
    content_hash: str
    synthetic: bool
    text: str
    text_size: int
    size_unit: str
    page_numbers: list  # sorted list[int], all pages contributing to this chunk
    block_ids: list  # list[str], contributing Phase 3 block_ids, in document order
    block_types: list  # list[str], block_type of each entry in block_ids, same order
    section_heading_block_id: Optional[str] = None
    section_heading_text: Optional[str] = None
    section_heading_level: Optional[Union[int, str]] = None
    list_group_id: Optional[str] = None
    is_split: bool = False
    split_index: int = 0
    split_count: int = 1
    table_rows: Optional[list] = None  # list[list[str]] when this chunk wraps a TABLE block
    warnings: list = field(default_factory=list)

    def __post_init__(self):
        assert self.size_unit == SIZE_UNIT
        assert self.split_index < self.split_count
        assert self.page_numbers, "a chunk must reference at least one contributing page"
        assert self.block_ids, "a chunk must reference at least one contributing block"
        assert len(self.block_ids) == len(self.block_types)


@dataclass(frozen=True)
class ChunkingResult:
    """Top-level result of chunker.chunk_document()."""

    document_id: str
    chunking_status: str
    config_signature: str
    chunks: list  # list[Chunk]
    warnings: list = field(default_factory=list)

    def __post_init__(self):
        assert self.chunking_status in CHUNKING_STATES
