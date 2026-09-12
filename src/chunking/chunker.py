"""
Phase 4 orchestration (docs/PHASE_04_LEGAL_AWARE_CHUNKING.md).

chunk_document(): the single entry point. Takes a Phase 3
ingestion.models.ExtractedDocument (the actual in-memory output of
ingestion.pipeline.ingest_document/ingest_bytes) and a ChunkingConfig, and
returns a deterministic ChunkingResult.

Never retrieves, embeds, indexes, or generates anything. Never mutates the
input document.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ingestion.models import BLOCK_TYPES, ExtractedDocument

from .identity import compute_chunk_id
from .models import SIZE_UNIT, Chunk, ChunkingConfig, ChunkingResult
from .rules import (
    SECTION_SEPARATOR,
    flatten_blocks,
    iter_section_groups,
    render_table_rows,
    split_table_rows,
    split_text_preserving_all_characters,
)


@dataclass
class _ChunkDraft:
    """Internal, pre-identity chunk representation - not part of the public contract."""

    text: str
    block_ids: list
    block_types: list
    page_numbers: list
    is_split: bool
    split_index: int
    split_count: int
    section_heading_block_id: Optional[str]
    section_heading_text: Optional[str]
    section_heading_level: object
    list_group_id: Optional[str]
    table_rows: Optional[list] = None
    warnings: list = field(default_factory=list)


def _validate_blocks(blocks: list) -> None:
    """
    Defensive precondition check against malformed structural objects
    (docs/PHASE_04_LEGAL_AWARE_CHUNKING.md Section P). Phase 4 trusts Phase
    3's own dataclass invariants (ingestion.models.Block.__post_init__) for
    well-formed input, but does not assume a caller-constructed object graph
    is well-formed - it fails loudly and immediately rather than crashing
    obscurely partway through chunking or silently producing corrupt output.
    """
    for block in blocks:
        if not isinstance(block.text, str):
            raise ValueError(f"block {block.block_id!r} has non-string text: {type(block.text).__name__}")
        if not isinstance(block.block_id, str) or not block.block_id:
            raise ValueError(f"block has invalid/empty block_id: {block.block_id!r}")
        if not isinstance(block.page_number, int):
            raise ValueError(f"block {block.block_id!r} has non-integer page_number")
        if block.block_type not in BLOCK_TYPES:
            raise ValueError(f"block {block.block_id!r} has invalid block_type: {block.block_type!r}")


def _pack_section(heading_block, group_blocks: list, config: ChunkingConfig) -> list:
    drafts: list = []
    buffer: list = []
    current_list_block_id: Optional[str] = None

    heading_block_id = heading_block.block_id if heading_block is not None else None
    heading_text = heading_block.text if heading_block is not None else None
    heading_level = heading_block.heading_level if heading_block is not None else None

    def _draft_from_buffer(buffer_blocks: list) -> _ChunkDraft:
        texts = [b.text for b in buffer_blocks if b.text.strip()]
        text = SECTION_SEPARATOR.join(texts)
        warnings = [] if text else ["CHUNK_TEXT_EMPTY"]
        return _ChunkDraft(
            text=text,
            block_ids=[b.block_id for b in buffer_blocks],
            block_types=[b.block_type for b in buffer_blocks],
            page_numbers=sorted({b.page_number for b in buffer_blocks}),
            is_split=False,
            split_index=0,
            split_count=1,
            section_heading_block_id=heading_block_id,
            section_heading_text=heading_text,
            section_heading_level=heading_level,
            list_group_id=current_list_block_id,
            warnings=warnings,
        )

    def flush() -> None:
        if buffer:
            drafts.append(_draft_from_buffer(list(buffer)))
            buffer.clear()

    def _update_list_tracking(block) -> None:
        nonlocal current_list_block_id
        if block.block_type == "LIST":
            current_list_block_id = block.block_id
        elif block.block_type != "LIST_ITEM":
            current_list_block_id = None

    for block in group_blocks:
        if block.block_type == "TABLE":
            # Flush FIRST, while current_list_block_id still reflects the
            # blocks already in the buffer - a table ends any preceding
            # list run, but must not retroactively erase the list_group_id
            # of blocks that were already buffered before this table arrived.
            flush()
            _update_list_tracking(block)
            rows = block.table.rows if block.table is not None else []
            row_groups = split_table_rows(rows, config.max_chunk_size_chars)
            n = len(row_groups)
            for idx, group_rows in enumerate(row_groups):
                rendered = render_table_rows(group_rows)
                warnings = list(block.warnings)
                if n > 1:
                    warnings.append("TABLE_SPLIT_ACROSS_CHUNKS")
                if len(rendered) > config.max_chunk_size_chars:
                    warnings.append("TABLE_ROW_EXCEEDS_MAX_SIZE")
                drafts.append(
                    _ChunkDraft(
                        text=rendered,
                        block_ids=[block.block_id],
                        block_types=["TABLE"],
                        page_numbers=[block.page_number],
                        is_split=n > 1,
                        split_index=idx,
                        split_count=n,
                        section_heading_block_id=heading_block_id,
                        section_heading_text=heading_text,
                        section_heading_level=heading_level,
                        list_group_id=current_list_block_id,
                        table_rows=group_rows,
                        warnings=_dedupe(warnings),
                    )
                )
            continue

        block_text = block.text
        oversized = bool(block_text.strip()) and len(block_text) > config.max_chunk_size_chars
        if oversized:
            flush()
            _update_list_tracking(block)
            pieces = split_text_preserving_all_characters(block_text, config.max_chunk_size_chars)
            n = len(pieces)
            for idx, piece in enumerate(pieces):
                drafts.append(
                    _ChunkDraft(
                        text=piece,
                        block_ids=[block.block_id],
                        block_types=[block.block_type],
                        page_numbers=[block.page_number],
                        is_split=True,
                        split_index=idx,
                        split_count=n,
                        section_heading_block_id=heading_block_id,
                        section_heading_text=heading_text,
                        section_heading_level=heading_level,
                        list_group_id=current_list_block_id,
                        warnings=["BLOCK_SPLIT_DUE_TO_SIZE"],
                    )
                )
            continue

        prospective = buffer + [block]
        prospective_text = SECTION_SEPARATOR.join(b.text for b in prospective if b.text.strip())
        if buffer and len(prospective_text) > config.max_chunk_size_chars:
            flush()
        _update_list_tracking(block)
        buffer.append(block)

    flush()
    return drafts


def _dedupe(items: list) -> list:
    seen = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen


def chunk_document(document: ExtractedDocument, config: ChunkingConfig = None) -> ChunkingResult:
    """
    The Phase 4 entry point. Transforms a Phase 3 ExtractedDocument into
    deterministic, provenance-preserving chunks.

    Raises TypeError if `document` is not an ingestion.models.ExtractedDocument
    (a programming-contract violation, not a data-quality pipeline state -
    docs/PHASE_04_LEGAL_AWARE_CHUNKING.md Section O). Raises ValueError if
    `config` is invalid (ChunkingConfig.__post_init__) or if the document's
    own blocks violate the ordering/typing invariants Phase 4 depends on
    (Section P).
    """
    if not isinstance(document, ExtractedDocument):
        raise TypeError(
            f"chunk_document expects an ingestion.models.ExtractedDocument, got {type(document).__name__}"
        )
    if config is None:
        config = ChunkingConfig()

    blocks = flatten_blocks(document.pages)
    _validate_blocks(blocks)

    if not blocks:
        return ChunkingResult(
            document_id=document.document_id,
            chunking_status="CHUNKING_SKIPPED",
            config_signature=config.signature,
            chunks=[],
            warnings=["NO_BLOCKS_TO_CHUNK"],
        )

    drafts: list = []
    for heading_block, group_blocks in iter_section_groups(blocks):
        drafts.extend(_pack_section(heading_block, group_blocks, config))

    if not drafts:
        return ChunkingResult(
            document_id=document.document_id,
            chunking_status="CHUNKING_SKIPPED",
            config_signature=config.signature,
            chunks=[],
            warnings=["NO_BLOCKS_TO_CHUNK"],
        )

    content_hash = document.integrity.claimed_content_hash
    chunks = []
    document_warnings: list = []
    for sequence, draft in enumerate(drafts, start=1):
        chunk_id = compute_chunk_id(
            document_id=document.document_id,
            content_hash=content_hash,
            config_signature=config.signature,
            block_ids=draft.block_ids,
            split_index=draft.split_index,
        )
        chunk = Chunk(
            chunk_id=chunk_id,
            chunk_sequence=sequence,
            document_id=document.document_id,
            source_family_id=document.source_family_id,
            jurisdiction=document.jurisdiction,
            content_hash=content_hash,
            synthetic=document.synthetic,
            text=draft.text,
            text_size=len(draft.text),
            size_unit=SIZE_UNIT,
            page_numbers=draft.page_numbers,
            block_ids=draft.block_ids,
            block_types=draft.block_types,
            section_heading_block_id=draft.section_heading_block_id,
            section_heading_text=draft.section_heading_text,
            section_heading_level=draft.section_heading_level,
            list_group_id=draft.list_group_id,
            is_split=draft.is_split,
            split_index=draft.split_index,
            split_count=draft.split_count,
            table_rows=draft.table_rows,
            warnings=draft.warnings,
        )
        chunks.append(chunk)
        for w in draft.warnings:
            if w not in document_warnings:
                document_warnings.append(w)

    status = "CHUNKING_PARTIAL" if document_warnings else "CHUNKING_SUCCESS"
    return ChunkingResult(
        document_id=document.document_id,
        chunking_status=status,
        config_signature=config.signature,
        chunks=chunks,
        warnings=document_warnings,
    )
