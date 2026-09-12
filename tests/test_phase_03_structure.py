"""
Phase 3 tests: src/ingestion/extractors.py structural detection (headings,
paragraphs, lists, tables) and config/document_structure_schema.yaml.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from _document_schema import DocumentSchemaValidationError, validate_document_structure_schema
from _pdf_fixtures import make_minimal_text_pdf

from ingestion.extractors import (
    _classify_line,
    aggregate_document_extraction_status,
    extract_html,
    extract_pdf,
    extract_text,
)
from ingestion.models import Page

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "config" / "document_structure_schema.yaml"
DOC_PATH = REPO_ROOT / "docs" / "PHASE_03_LEGAL_STRUCTURE_EXTRACTION.md"


# ---------------------------------------------------------------------------
# Document structure
# ---------------------------------------------------------------------------


def test_doc_exists_and_nonempty():
    assert DOC_PATH.stat().st_size > 0


@pytest.mark.parametrize(
    "section",
    [
        "1. Structural Elements In Scope",
        "2. Detection States",
        "3. Heading Heuristic",
        "4. Heading Detection (HTML)",
        "5. Table Handling",
        "6. Lists",
        "7. Page Numbers",
        "8. Ordering",
        "9. Non-Goals",
    ],
)
def test_doc_has_required_section(section: str):
    text = DOC_PATH.read_text(encoding="utf-8")
    assert section in text


def test_doc_does_not_claim_legal_interpretation():
    text = DOC_PATH.read_text(encoding="utf-8").lower()
    assert "does not mean legal interpretation" in text or "never a claim about" in text


# ---------------------------------------------------------------------------
# Heading heuristic (unit-level, deterministic)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line,expected_type,expected_level",
    [
        ("1. Definitions", "HEADING", 1),
        ("2.1 Scope", "HEADING", 2),
        ("3.2.1 Sub-clause", "HEADING", 3),
        ("SCOPE", "HEADING", "UNKNOWN"),
        ("This is a normal sentence.", "PARAGRAPH", None),
        ("A line ending with a comma,", "PARAGRAPH", None),
        ("", "PARAGRAPH", None),
    ],
)
def test_classify_line_is_deterministic_and_correct(line, expected_type, expected_level):
    block_type, level = _classify_line(line)
    assert block_type == expected_type
    assert level == expected_level
    # Determinism: repeated calls give identical results.
    assert _classify_line(line) == (block_type, level)


def test_heading_heuristic_never_fabricates_a_level_for_all_caps():
    block_type, level = _classify_line("SCOPE AND APPLICATION")
    assert block_type == "HEADING"
    assert level == "UNKNOWN"  # never a fabricated integer


def test_very_long_line_is_never_a_heading():
    long_line = "A" * 200
    block_type, _ = _classify_line(long_line)
    assert block_type == "PARAGRAPH"


# ---------------------------------------------------------------------------
# TEXT extraction structure
# ---------------------------------------------------------------------------


def test_text_extraction_produces_headings_and_paragraphs_in_order():
    data = "1. Definitions\n\nBody text one.\n\n2. Scope\n\nBody text two.\n".encode()
    pages, warnings, title = extract_text(data, "DOC-STRUCT")
    blocks = pages[0].blocks
    types = [b.block_type for b in blocks]
    assert types == ["HEADING", "PARAGRAPH", "HEADING", "PARAGRAPH"]
    assert [b.sequence for b in blocks] == [1, 2, 3, 4]


def test_text_paragraph_parent_section_points_to_preceding_heading():
    data = "1. Definitions\n\nBody text.\n".encode()
    pages, _, _ = extract_text(data, "DOC-PARENT")
    heading, paragraph = pages[0].blocks
    assert paragraph.parent_section == heading.block_id


def test_text_title_is_never_detected():
    data = b"Just some content.\n"
    _, _, title = extract_text(data, "DOC-T")
    assert title.detection_status == "NOT_DETECTED"
    assert title.text is None


# ---------------------------------------------------------------------------
# HTML extraction structure
# ---------------------------------------------------------------------------


def test_html_heading_levels_are_confident_not_heuristic():
    html = b"<html><body><h2>Sub Chapter</h2><p>Text.</p></body></html>"
    pages, _, _ = extract_html(html, "DOC-H")
    heading = pages[0].blocks[0]
    assert heading.block_type == "HEADING"
    assert heading.heading_level == 2  # confident integer, not UNKNOWN


def test_html_title_tag_detected():
    html = b"<html><head><title>My Title</title></head><body><p>x</p></body></html>"
    _, _, title = extract_html(html, "DOC-TITLE")
    assert title.detection_status == "DETECTED"
    assert title.text == "My Title"


def test_html_no_title_tag_not_detected():
    html = b"<html><body><p>No title here.</p></body></html>"
    _, _, title = extract_html(html, "DOC-NOTITLE")
    assert title.detection_status == "NOT_DETECTED"


def test_html_list_structure_detected():
    html = b"<ul><li>One</li><li>Two</li></ul>"
    pages, _, _ = extract_html(html, "DOC-LIST")
    types = [b.block_type for b in pages[0].blocks]
    assert types == ["LIST", "LIST_ITEM", "LIST_ITEM"]


def test_html_table_rows_and_cells_captured():
    html = b"<table><tr><td>A</td><td>B</td></tr><tr><td>1</td><td>2</td></tr></table>"
    pages, _, _ = extract_html(html, "DOC-TABLE")
    table_block = pages[0].blocks[0]
    assert table_block.block_type == "TABLE"
    assert table_block.table.detection_status == "DETECTED"
    assert table_block.table.rows == [["A", "B"], ["1", "2"]]


def test_html_table_with_colspan_flags_simplification_warning():
    html = b'<table><tr><td colspan="2">Merged</td></tr></table>'
    pages, warnings, _ = extract_html(html, "DOC-COLSPAN")
    assert "TABLE_STRUCTURE_SIMPLIFIED" in warnings
    table_block = pages[0].blocks[0]
    assert "TABLE_STRUCTURE_SIMPLIFIED" in table_block.warnings


def test_html_empty_body_is_empty_page():
    html = b"<html><body></body></html>"
    pages, _, _ = extract_html(html, "DOC-EMPTY")
    assert pages[0].extraction_status == "EMPTY"
    assert "EMPTY_PAGE" in pages[0].warnings


# ---------------------------------------------------------------------------
# Table handling per document type (critical: never fabricate table content)
# ---------------------------------------------------------------------------


def test_pdf_table_extraction_is_never_attempted():
    data = make_minimal_text_pdf("Some text with numbers 1 2 3 in a row")
    pages, warnings, _ = extract_pdf(data, "DOC-PDF-TABLE")
    assert "PDF_TABLE_EXTRACTION_NOT_IMPLEMENTED" in warnings
    for page in pages:
        for block in page.blocks:
            assert block.block_type != "TABLE"  # never fabricated


def test_text_documents_have_no_table_blocks():
    data = b"Row1 Col1   Row1 Col2\nRow2 Col1   Row2 Col2\n"
    pages, _, _ = extract_text(data, "DOC-TXT-TABLE")
    for block in pages[0].blocks:
        assert block.block_type != "TABLE"


# ---------------------------------------------------------------------------
# Parser failure handling / unreliable detection (critical negative tests)
# ---------------------------------------------------------------------------


def test_html_parser_exception_is_caught_not_raised():
    # Pathological but not literally malformed enough to crash html.parser
    # in practice; assert the extractor never raises regardless of input.
    try:
        extract_html(b"<<<not really html>>>", "DOC-BAD-HTML")
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"extract_html raised an exception instead of returning a controlled result: {exc}")


def test_unreliable_heading_detection_falls_back_to_paragraph():
    # A line that could superficially look meaningful but doesn't match
    # either heading signal must be PARAGRAPH, not guessed as a heading.
    block_type, level = _classify_line("the quick brown fox jumps over lazy dog")
    assert block_type == "PARAGRAPH"
    assert level is None


# ---------------------------------------------------------------------------
# Aggregate status determinism
# ---------------------------------------------------------------------------


def test_aggregate_status_all_success():
    pages = [Page(1, "SUCCESS", []), Page(2, "SUCCESS", [])]
    assert aggregate_document_extraction_status(pages) == "EXTRACTION_SUCCESS"


def test_aggregate_status_mixed_is_partial():
    pages = [Page(1, "SUCCESS", []), Page(2, "OCR_REQUIRED", [])]
    assert aggregate_document_extraction_status(pages) == "EXTRACTION_PARTIAL"


def test_aggregate_status_all_ocr_required():
    pages = [Page(1, "OCR_REQUIRED", []), Page(2, "OCR_REQUIRED", [])]
    assert aggregate_document_extraction_status(pages) == "OCR_REQUIRED"


def test_aggregate_status_all_failed():
    pages = [Page(1, "FAILED", []), Page(2, "EMPTY", [])]
    assert aggregate_document_extraction_status(pages) == "EXTRACTION_FAILED"


def test_aggregate_status_empty_page_list():
    assert aggregate_document_extraction_status([]) == "EXTRACTION_FAILED"


def test_aggregate_status_success_with_decode_warning_is_partial():
    pages = [Page(1, "SUCCESS", [])]
    assert aggregate_document_extraction_status(pages, had_decode_warning=True) == "EXTRACTION_PARTIAL"


# ---------------------------------------------------------------------------
# config/document_structure_schema.yaml
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def schema_raw_text() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def schema_data(schema_raw_text: str) -> dict:
    return yaml.safe_load(schema_raw_text)


@pytest.fixture()
def valid_schema_copy(schema_data: dict) -> dict:
    return copy.deepcopy(schema_data)


def test_schema_file_exists_and_nonempty():
    assert SCHEMA_PATH.stat().st_size > 0


def test_schema_yaml_parses(schema_raw_text: str):
    assert isinstance(yaml.safe_load(schema_raw_text), dict)


def test_schema_passes_validation(schema_data: dict):
    validate_document_structure_schema(schema_data)


def test_schema_never_claims_legal_certainty(schema_raw_text: str):
    lowered = schema_raw_text.lower()
    for forbidden in ("is_legally_authoritative", "legally_valid", "legal_certainty"):
        assert forbidden not in lowered


def test_schema_malformed_root_is_rejected():
    with pytest.raises(DocumentSchemaValidationError):
        validate_document_structure_schema(["not", "a", "mapping"])


def test_schema_missing_block_key_is_rejected(valid_schema_copy: dict):
    del valid_schema_copy["block"]
    with pytest.raises(DocumentSchemaValidationError):
        validate_document_structure_schema(valid_schema_copy)


def test_schema_duplicate_field_name_is_rejected(valid_schema_copy: dict):
    valid_schema_copy["block"]["fields"].append(dict(valid_schema_copy["block"]["fields"][0]))
    with pytest.raises(DocumentSchemaValidationError):
        validate_document_structure_schema(valid_schema_copy)


def test_schema_wrong_detection_states_rejected(valid_schema_copy: dict):
    valid_schema_copy["detection_states"] = ["YES", "NO"]
    with pytest.raises(DocumentSchemaValidationError):
        validate_document_structure_schema(valid_schema_copy)
