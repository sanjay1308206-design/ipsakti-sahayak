"""
Phase 4 tests: empty/whitespace blocks, missing structural metadata,
malformed input objects, invalid configuration, no-text-loss / no-duplication
invariants, and security/robustness edge cases (docs/PHASE_04_LEGAL_AWARE_CHUNKING.md
Section P/Q).

Explicit scope note: these tests document what Phase 4 protects against.
They do not claim comprehensive security coverage.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _chunk_fixtures import make_document
from _pdf_fixtures import make_blank_pages_pdf, make_malformed_pdf

from chunking.chunker import chunk_document
from chunking.models import Chunk, ChunkingConfig, ChunkingResult
from chunking.rules import flatten_blocks, split_table_rows, split_text_preserving_all_characters
from ingestion.models import Block, ExtractedDocument, Integrity, Page, Table, TitleInfo
from ingestion.pipeline import ingest_bytes
from ingestion.hashing import compute_content_hash

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def _make_extracted_document(pages, document_id="D-EDGE", synthetic=True):
    return ExtractedDocument(
        document_id=document_id,
        source_family_id="SF-01",
        jurisdiction="INDIA",
        document_type="TEXT",
        synthetic=synthetic,
        integrity=Integrity(claimed_content_hash="deadbeef", computed_content_hash="deadbeef", match=True),
        extraction_status="EXTRACTION_SUCCESS",
        table_extraction_status="NOT_APPLICABLE",
        title=TitleInfo(detection_status="NOT_DETECTED"),
        pages=pages,
    )


# ---------------------------------------------------------------------------
# 13/14. Empty blocks, whitespace-only blocks
# ---------------------------------------------------------------------------


def test_document_with_zero_blocks_is_chunking_skipped():
    doc = _make_extracted_document(pages=[Page(page_number=1, extraction_status="EMPTY", blocks=[])])
    result = chunk_document(doc, ChunkingConfig())
    assert result.chunking_status == "CHUNKING_SKIPPED"
    assert result.chunks == []
    assert "NO_BLOCKS_TO_CHUNK" in result.warnings


def test_lone_list_marker_with_no_items_produces_empty_text_chunk_with_warning():
    marker = Block(block_id="D:p1:b1", sequence=1, block_type="LIST", text="", page_number=1)
    doc = _make_extracted_document(pages=[Page(page_number=1, extraction_status="SUCCESS", blocks=[marker])])
    result = chunk_document(doc, ChunkingConfig())
    assert len(result.chunks) == 1
    assert result.chunks[0].text == ""
    assert result.chunks[0].text_size == 0
    assert "CHUNK_TEXT_EMPTY" in result.chunks[0].warnings
    assert result.chunking_status == "CHUNKING_PARTIAL"
    # still traceable, never an orphan despite empty text
    assert result.chunks[0].block_ids == ["D:p1:b1"]


def test_blank_pdf_pages_yield_ocr_required_and_chunker_reports_skipped(authority_matrix):
    blank = make_blank_pages_pdf(2)
    doc = make_document(blank, ".pdf", authority_matrix, document_id="D-EDGE-BLANK")
    assert doc.extraction_status == "OCR_REQUIRED"
    result = chunk_document(doc, ChunkingConfig())
    assert result.chunking_status == "CHUNKING_SKIPPED"


# ---------------------------------------------------------------------------
# 15. Missing/uncertain structural metadata
# ---------------------------------------------------------------------------


def test_all_caps_heading_with_unknown_level_is_preserved_not_guessed(authority_matrix):
    data = b"SCOPE\n\nBody text under the all-caps heading.\n"
    doc = make_document(data, ".txt", authority_matrix, document_id="D-EDGE-UNKNOWN-LEVEL")
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=500))
    assert result.chunks[0].section_heading_level == "UNKNOWN"


def test_document_with_no_heading_at_all_has_null_section_context_throughout(authority_matrix):
    data = b"Body text one.\n\nBody text two.\n\nBody text three.\n"
    doc = make_document(data, ".txt", authority_matrix, document_id="D-EDGE-NO-HEADING")
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=15))
    assert all(c.section_heading_block_id is None for c in result.chunks)
    assert all(c.section_heading_text is None for c in result.chunks)


# ---------------------------------------------------------------------------
# Malformed input objects
# ---------------------------------------------------------------------------


def test_chunk_document_rejects_non_extracted_document_input():
    with pytest.raises(TypeError):
        chunk_document({"not": "a document"})
    with pytest.raises(TypeError):
        chunk_document(None)
    with pytest.raises(TypeError):
        chunk_document("a string")


def test_chunk_document_rejects_block_with_non_string_text():
    block = Block(block_id="D:p1:b1", sequence=1, block_type="PARAGRAPH", text="fine", page_number=1)
    object.__setattr__(block, "text", None)
    doc = _make_extracted_document(pages=[Page(page_number=1, extraction_status="SUCCESS", blocks=[block])])
    with pytest.raises(ValueError):
        chunk_document(doc, ChunkingConfig())


def test_flatten_blocks_rejects_out_of_order_sequence():
    b1 = Block(block_id="D:p1:b2", sequence=2, block_type="PARAGRAPH", text="second", page_number=1)
    b2 = Block(block_id="D:p1:b1", sequence=1, block_type="PARAGRAPH", text="first", page_number=1)
    pages = [Page(page_number=1, extraction_status="SUCCESS", blocks=[b1, b2])]
    with pytest.raises(ValueError):
        flatten_blocks(pages)


# ---------------------------------------------------------------------------
# Invalid chunking configuration
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_value", [0, -1, -1000])
def test_negative_or_zero_max_chunk_size_is_rejected(bad_value):
    with pytest.raises(ValueError):
        ChunkingConfig(max_chunk_size_chars=bad_value)


def test_non_integer_max_chunk_size_is_rejected():
    with pytest.raises(ValueError):
        ChunkingConfig(max_chunk_size_chars="1000")
    with pytest.raises(ValueError):
        ChunkingConfig(max_chunk_size_chars=1000.5)
    with pytest.raises(ValueError):
        ChunkingConfig(max_chunk_size_chars=True)  # bool is an int subclass - must not silently pass


def test_split_text_rejects_non_positive_max_size():
    with pytest.raises(ValueError):
        split_text_preserving_all_characters("abc", 0)
    with pytest.raises(ValueError):
        split_table_rows([["a"]], -5)


# ---------------------------------------------------------------------------
# No text loss / no unintended duplication
# ---------------------------------------------------------------------------


def test_no_text_loss_across_a_wide_range_of_split_sizes():
    text = "The quick brown fox jumps over the lazy dog. " * 30
    for max_size in (5, 7, 13, 50, 200, 10000):
        pieces = split_text_preserving_all_characters(text, max_size)
        assert "".join(pieces) == text


def test_split_pieces_never_overlap():
    text = "alpha beta gamma delta epsilon zeta eta theta"
    pieces = split_text_preserving_all_characters(text, 9)
    reconstructed_length = sum(len(p) for p in pieces)
    assert reconstructed_length == len(text)  # overlap would inflate this


def test_table_row_split_never_duplicates_or_drops_rows():
    rows = [[f"cell-{i}-a", f"cell-{i}-b"] for i in range(20)]
    groups = split_table_rows(rows, 15)
    flat = [row for group in groups for row in group]
    assert flat == rows


# ---------------------------------------------------------------------------
# Security / robustness edge cases
# ---------------------------------------------------------------------------


def test_extremely_long_single_block_does_not_crash_and_splits_cleanly(authority_matrix):
    data = b"1. Heading\n\n" + (b"a" * 200_000) + b"\n"
    doc = make_document(data, ".txt", authority_matrix, document_id="D-SEC-LONG")
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=1000))
    assert result.chunking_status == "CHUNKING_PARTIAL"
    big_block_chunks = [c for c in result.chunks if c.is_split]
    assert sum(c.text_size for c in big_block_chunks) == 200_000


def test_repeated_identical_paragraphs_do_not_confuse_chunk_identity(authority_matrix):
    data = b"\n\n".join([b"Repeated paragraph text."] * 50) + b"\n"
    doc = make_document(data, ".txt", authority_matrix, document_id="D-SEC-REPEAT")
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=40))
    ids = [c.chunk_id for c in result.chunks]
    assert len(ids) == len(set(ids))  # identical text does not collapse into fewer, wrong chunks


def test_pathological_whitespace_only_paragraphs_are_handled(authority_matrix):
    data = b"1. Heading\n\n   \n\n\t\t\n\nReal body text.\n"
    doc = make_document(data, ".txt", authority_matrix, document_id="D-SEC-WS")
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=500))
    assert "Real body text." in "".join(c.text for c in result.chunks)


def test_huge_number_of_blocks_does_not_crash(authority_matrix):
    data = b"\n\n".join(f"Paragraph number {i}.".encode() for i in range(3000)) + b"\n"
    doc = make_document(data, ".txt", authority_matrix, document_id="D-SEC-MANY")
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=200))
    assert result.chunking_status in ("CHUNKING_SUCCESS", "CHUNKING_PARTIAL")
    assert len(result.chunks) > 0
    all_ids = [c.chunk_id for c in result.chunks]
    assert len(all_ids) == len(set(all_ids))


def test_unusual_unicode_is_preserved_without_crashing(authority_matrix):
    data = "1. शीर्षक\n\nनमस्ते \U0001F600 text with emoji and Devanagari.\n".encode(
        "utf-8"
    )
    doc = make_document(data, ".txt", authority_matrix, document_id="D-SEC-UNICODE")
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=500))
    assert "\U0001F600" in "".join(c.text for c in result.chunks)


def test_malformed_pdf_produces_no_blocks_and_chunker_skips_cleanly(authority_matrix):
    malformed = make_malformed_pdf()
    provenance = {
        "document_id": "D-SEC-MALFORMED-PDF",
        "source_family_id": "SF-01",
        "jurisdiction": "INDIA",
        "content_hash": compute_content_hash(malformed),
        "admission_status": "ADMIT",
        "synthetic": True,
    }
    result = ingest_bytes(malformed, provenance, ".pdf", authority_matrix=authority_matrix)
    assert result.pipeline_state == "EXTRACTION_FAILED"
    assert result.document is not None  # Phase 3 still returns a document shell with FAILED pages
    chunking_result = chunk_document(result.document, ChunkingConfig())
    assert chunking_result.chunking_status == "CHUNKING_SKIPPED"


def test_deterministic_behavior_under_adversarial_block_ordering_is_refused_not_guessed():
    # Phase 4 explicitly refuses to guess an ordering for out-of-sequence
    # input rather than silently producing a plausible-looking wrong answer.
    a = Block(block_id="D:p2:b5", sequence=5, block_type="PARAGRAPH", text="later", page_number=2)
    b = Block(block_id="D:p1:b1", sequence=1, block_type="PARAGRAPH", text="earlier", page_number=1)
    pages = [Page(page_number=2, extraction_status="SUCCESS", blocks=[a]),
             Page(page_number=1, extraction_status="SUCCESS", blocks=[b])]
    doc = _make_extracted_document(pages=pages)
    with pytest.raises(ValueError):
        chunk_document(doc, ChunkingConfig())
