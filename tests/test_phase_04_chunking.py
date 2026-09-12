"""
Phase 4 tests: basic block-to-chunk conversion, heading/paragraph grouping,
section/subsection boundaries, list preservation, table preservation.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _chunk_fixtures import make_document

from chunking.chunker import chunk_document
from chunking.models import ChunkingConfig

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. Basic block-to-chunk conversion
# ---------------------------------------------------------------------------


def test_single_paragraph_document_produces_one_chunk(authority_matrix):
    data = b"Just one plain paragraph of text with no headings at all.\n"
    doc = make_document(data, ".txt", authority_matrix, document_id="D-BASIC-01")
    result = chunk_document(doc, ChunkingConfig())
    assert result.chunking_status == "CHUNKING_SUCCESS"
    assert len(result.chunks) == 1
    assert result.chunks[0].text == "Just one plain paragraph of text with no headings at all."
    assert result.chunks[0].block_ids == [doc.pages[0].blocks[0].block_id]


def test_chunk_carries_document_type_via_block_types(authority_matrix):
    data = b"A single paragraph.\n"
    doc = make_document(data, ".txt", authority_matrix, document_id="D-BASIC-02")
    result = chunk_document(doc, ChunkingConfig())
    assert result.chunks[0].block_types == ["PARAGRAPH"]


# ---------------------------------------------------------------------------
# 2. Heading + paragraph grouping
# ---------------------------------------------------------------------------


def test_heading_and_its_paragraph_share_one_chunk_when_they_fit(authority_matrix):
    data = b"1. Definitions\n\nShort body text under the heading.\n"
    doc = make_document(data, ".txt", authority_matrix, document_id="D-GROUP-01")
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=500))
    assert len(result.chunks) == 1
    chunk = result.chunks[0]
    assert chunk.block_types == ["HEADING", "PARAGRAPH"]
    assert chunk.text == "1. Definitions\n\nShort body text under the heading."
    assert chunk.section_heading_text == "1. Definitions"


def test_heading_alone_still_forms_a_valid_chunk_when_size_forces_a_split(authority_matrix):
    data = b"1. Definitions\n\n" + b"x" * 200 + b"\n"
    doc = make_document(data, ".txt", authority_matrix, document_id="D-GROUP-02")
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=30))
    heading_chunks = [c for c in result.chunks if c.block_types == ["HEADING"]]
    assert len(heading_chunks) == 1
    assert heading_chunks[0].text == "1. Definitions"


# ---------------------------------------------------------------------------
# 3-4. Section / subsection boundaries
# ---------------------------------------------------------------------------


def test_two_top_level_headings_produce_two_separate_chunks(authority_matrix):
    data = b"1. First\n\nBody one.\n\n2. Second\n\nBody two.\n"
    doc = make_document(data, ".txt", authority_matrix, document_id="D-SECTION-01")
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=500))
    assert len(result.chunks) == 2
    assert result.chunks[0].section_heading_text == "1. First"
    assert result.chunks[1].section_heading_text == "2. Second"
    # no cross-contamination of section text
    assert "Second" not in result.chunks[0].text
    assert "First" not in result.chunks[1].text


def test_subsection_heading_starts_its_own_chunk_group(authority_matrix):
    data = b"2. Scope\n\nTop body.\n\n2.1 Sub-scope\n\nSub body.\n"
    doc = make_document(data, ".txt", authority_matrix, document_id="D-SECTION-02")
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=500))
    assert len(result.chunks) == 2
    assert result.chunks[0].section_heading_level == 1
    assert result.chunks[1].section_heading_level == 2
    assert result.chunks[1].section_heading_text == "2.1 Sub-scope"


def test_leading_content_before_first_heading_has_no_fabricated_heading(authority_matrix):
    data = b"Preamble text with no heading above it.\n\n1. First Real Heading\n\nBody.\n"
    doc = make_document(data, ".txt", authority_matrix, document_id="D-SECTION-03")
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=500))
    assert result.chunks[0].section_heading_block_id is None
    assert result.chunks[0].section_heading_text is None
    assert result.chunks[1].section_heading_text == "1. First Real Heading"


# ---------------------------------------------------------------------------
# 5. List preservation
# ---------------------------------------------------------------------------


def test_list_items_stay_with_their_list_marker_and_heading(authority_matrix):
    html = b"<html><body><h1>H</h1><ul><li>alpha</li><li>beta</li></ul></body></html>"
    doc = make_document(html, ".html", authority_matrix, document_id="D-LIST-01")
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=500))
    assert len(result.chunks) == 1
    chunk = result.chunks[0]
    assert chunk.block_types == ["HEADING", "LIST", "LIST_ITEM", "LIST_ITEM"]
    assert "alpha" in chunk.text and "beta" in chunk.text
    list_block_id = doc.pages[0].blocks[1].block_id  # the LIST marker
    assert chunk.list_group_id == list_block_id


def test_list_text_is_never_rewritten(authority_matrix):
    html = b"<html><body><ul><li>Exact original wording, unchanged.</li></ul></body></html>"
    doc = make_document(html, ".html", authority_matrix, document_id="D-LIST-02")
    result = chunk_document(doc, ChunkingConfig())
    assert "Exact original wording, unchanged." in result.chunks[0].text


# ---------------------------------------------------------------------------
# 6. Table preservation
# ---------------------------------------------------------------------------


def test_table_block_becomes_its_own_chunk_with_structured_rows(authority_matrix):
    html = (
        b"<html><body><h1>H</h1><p>Intro.</p>"
        b"<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
        b"</body></html>"
    )
    doc = make_document(html, ".html", authority_matrix, document_id="D-TABLE-01")
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=500))
    table_chunks = [c for c in result.chunks if "TABLE" in c.block_types]
    assert len(table_chunks) == 1
    table_chunk = table_chunks[0]
    assert table_chunk.block_types == ["TABLE"]
    assert table_chunk.table_rows == [["A", "B"], ["1", "2"]]
    assert table_chunk.text == "A | B\n1 | 2"


def test_table_never_merged_with_surrounding_paragraph_text(authority_matrix):
    html = (
        b"<html><body><p>Before the table.</p>"
        b"<table><tr><td>x</td></tr></table>"
        b"<p>After the table.</p></body></html>"
    )
    doc = make_document(html, ".html", authority_matrix, document_id="D-TABLE-02")
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=500))
    assert len(result.chunks) == 3
    assert result.chunks[0].block_types == ["PARAGRAPH"]
    assert result.chunks[1].block_types == ["TABLE"]
    assert result.chunks[2].block_types == ["PARAGRAPH"]
