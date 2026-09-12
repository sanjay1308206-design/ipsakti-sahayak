"""
Phase 4 tests: page boundaries, multi-page chunks, oversized-block/table
splitting, and cross-page/cross-section structural behavior.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _chunk_fixtures import make_document
from _pdf_fixtures import make_multi_page_text_pdf

from chunking.chunker import chunk_document
from chunking.models import ChunkingConfig
from chunking.rules import split_table_rows, split_text_preserving_all_characters

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 7. Page provenance
# ---------------------------------------------------------------------------


def test_chunk_page_numbers_match_contributing_blocks(authority_matrix):
    data = b"1. Heading\n\nBody text.\n"
    doc = make_document(data, ".txt", authority_matrix, document_id="D-PAGE-01")
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=500))
    chunk = result.chunks[0]
    assert chunk.page_numbers == [1]


# ---------------------------------------------------------------------------
# 8. Multi-page chunks
# ---------------------------------------------------------------------------


def test_pdf_multi_page_document_produces_page_spanning_chunk(authority_matrix):
    pdf = make_multi_page_text_pdf(
        ["1. Cross-page Heading", "Continuation text that lives on the second PDF page."]
    )
    doc = make_document(pdf, ".pdf", authority_matrix, document_id="D-PAGE-02")
    assert len(doc.pages) == 2
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=1000))
    spanning = [c for c in result.chunks if len(c.page_numbers) > 1]
    assert len(spanning) == 1
    assert spanning[0].page_numbers == [1, 2]
    assert "Cross-page Heading" in spanning[0].text
    assert "Continuation text" in spanning[0].text


def test_pdf_each_page_contributes_its_own_block_ids_to_the_spanning_chunk(authority_matrix):
    pdf = make_multi_page_text_pdf(["1. Heading", "Body on page two."])
    doc = make_document(pdf, ".pdf", authority_matrix, document_id="D-PAGE-03")
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=1000))
    all_source_block_ids = {b.block_id for p in doc.pages for b in p.blocks}
    chunk_block_ids = {bid for c in result.chunks for bid in c.block_ids}
    assert chunk_block_ids == all_source_block_ids


def test_size_limit_forces_a_new_chunk_at_a_page_boundary_when_needed(authority_matrix):
    pdf = make_multi_page_text_pdf(["1. Heading", "x" * 300])
    doc = make_document(pdf, ".pdf", authority_matrix, document_id="D-PAGE-04")
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=50))
    # the oversized page-two paragraph must be split into multiple chunks,
    # each still traceable to page 2 - never silently merged across the size limit
    page_two_chunks = [c for c in result.chunks if 2 in c.page_numbers]
    assert len(page_two_chunks) > 1
    for c in page_two_chunks:
        assert c.text_size <= 50 or c.is_split


# ---------------------------------------------------------------------------
# 9. Oversized block splitting (rules-level + chunk-level)
# ---------------------------------------------------------------------------


def test_oversized_block_is_split_with_split_metadata(authority_matrix):
    data = b"1. Heading\n\n" + b"word " * 50 + b"\n"
    doc = make_document(data, ".txt", authority_matrix, document_id="D-SPLIT-01")
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=40))
    split_chunks = [c for c in result.chunks if c.is_split]
    assert split_chunks
    for i, c in enumerate(split_chunks):
        assert c.split_count == len(split_chunks)
        assert c.split_index == i
        assert c.block_ids == split_chunks[0].block_ids  # same origin block


def test_oversized_block_split_reconstructs_exactly(authority_matrix):
    data = b"1. Heading\n\n" + b"abcdefgh " * 40 + b"\n"
    doc = make_document(data, ".txt", authority_matrix, document_id="D-SPLIT-02")
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=25))
    split_chunks = sorted((c for c in result.chunks if c.is_split), key=lambda c: c.split_index)
    original_block = next(b for p in doc.pages for b in p.blocks if b.block_id == split_chunks[0].block_ids[0])
    assert "".join(c.text for c in split_chunks) == original_block.text


def test_rules_split_text_preserves_all_characters_exactly():
    text = "one two three four five six seven eight nine ten"
    pieces = split_text_preserving_all_characters(text, 12)
    assert "".join(pieces) == text
    assert all(len(p) <= 12 for p in pieces[:-1]) or len(pieces) == 1


def test_rules_split_text_no_whitespace_still_makes_progress():
    text = "x" * 500
    pieces = split_text_preserving_all_characters(text, 17)
    assert "".join(pieces) == text
    assert all(len(p) == 17 for p in pieces[:-1])


def test_rules_split_table_rows_never_splits_inside_a_row():
    rows = [["a", "b"], ["c", "d"], ["e", "f"]]
    groups = split_table_rows(rows, 8)
    flat = [row for group in groups for row in group]
    assert flat == rows  # every row present, in order, none divided


def test_oversized_table_is_split_across_multiple_chunks(authority_matrix):
    html = (
        b"<html><body><table>"
        b"<tr><td>row one long enough</td></tr>"
        b"<tr><td>row two long enough</td></tr>"
        b"<tr><td>row three long enough</td></tr>"
        b"</table></body></html>"
    )
    doc = make_document(html, ".html", authority_matrix, document_id="D-SPLIT-03")
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=25))
    table_chunks = [c for c in result.chunks if "TABLE" in c.block_types]
    assert len(table_chunks) > 1
    all_rows = [row for c in table_chunks for row in c.table_rows]
    assert all_rows == [["row one long enough"], ["row two long enough"], ["row three long enough"]]
    for c in table_chunks:
        assert c.is_split
        assert "TABLE_SPLIT_ACROSS_CHUNKS" in c.warnings
