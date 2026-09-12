"""
Deterministic, per-document-type structural extraction
(docs/PHASE_03_LEGAL_STRUCTURE_EXTRACTION.md).

Every extractor here is a pure function of input bytes -> (pages, warnings,
title). No I/O, no network calls, no OCR, no chunking, no retrieval.
"""

from __future__ import annotations

import io
import re
from html.parser import HTMLParser

from .models import Block, Page, Table, TitleInfo

# --- Heading heuristic (TEXT / PDF-extracted text) ---------------------
# [ENGINEERING RECOMMENDATION] see docs/PHASE_03_LEGAL_STRUCTURE_EXTRACTION.md
# Section 3. Never a claim of legal interpretation.

_NUMBERED_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)[.)]?\s+\S")
_MAX_HEADING_LINE_LENGTH = 120
_SENTENCE_ENDING_PUNCTUATION = (".", ",", ";", ":")


def _classify_line(line: str):
    """Return (block_type, heading_level) for a single line of text."""
    stripped = line.strip()
    if not stripped:
        return ("PARAGRAPH", None)
    if len(stripped) > _MAX_HEADING_LINE_LENGTH:
        return ("PARAGRAPH", None)
    if stripped[-1] in _SENTENCE_ENDING_PUNCTUATION:
        return ("PARAGRAPH", None)

    m = _NUMBERED_HEADING_RE.match(stripped)
    if m:
        depth = m.group(1).count(".") + 1
        return ("HEADING", min(depth, 6))

    letters = [c for c in stripped if c.isalpha()]
    if letters and stripped == stripped.upper():
        return ("HEADING", "UNKNOWN")

    return ("PARAGRAPH", None)


def _split_into_chunks(text: str) -> list:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    chunks = re.split(r"\n\s*\n+", normalized)
    return [c.strip() for c in chunks if c.strip()]


def _chunk_block_type_and_level(chunk: str):
    lines = chunk.split("\n")
    if len(lines) == 1:
        return _classify_line(lines[0])
    return ("PARAGRAPH", None)


def _chunks_to_blocks(chunks, page_number: int, start_sequence: int, document_id: str):
    """Shared by TEXT and PDF-per-page extraction. Returns (blocks, next_sequence)."""
    blocks = []
    sequence = start_sequence
    current_heading_block_id = None

    for chunk in chunks:
        block_type, level = _chunk_block_type_and_level(chunk)
        text = chunk if block_type == "HEADING" else " ".join(
            l.strip() for l in chunk.split("\n") if l.strip()
        )
        block_id = f"{document_id}:p{page_number}:b{sequence}"
        block = Block(
            block_id=block_id,
            sequence=sequence,
            block_type=block_type,
            text=text,
            page_number=page_number,
            heading_level=level,
            parent_section=current_heading_block_id,
        )
        blocks.append(block)
        if block_type == "HEADING":
            current_heading_block_id = block_id
        sequence += 1

    return blocks, sequence


# --- TEXT ----------------------------------------------------------------


def extract_text(data: bytes, document_id: str):
    """Returns (pages: list[Page], document_warnings: list[str], title: TitleInfo)."""
    warnings = []
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
        warnings.append("DECODE_ERROR_REPLACED_CHARACTERS")

    chunks = _split_into_chunks(text)
    blocks, _ = _chunks_to_blocks(chunks, page_number=1, start_sequence=1, document_id=document_id)

    if blocks:
        page = Page(page_number=1, extraction_status="SUCCESS", blocks=blocks, warnings=[])
    else:
        page = Page(page_number=1, extraction_status="EMPTY", blocks=[], warnings=["EMPTY_PAGE"])

    title = TitleInfo(detection_status="NOT_DETECTED")
    return [page], warnings, title


# --- HTML ------------------------------------------------------------------

_CAPTURE_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "title", "td", "th"})


class _StructuralHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.events = []
        self._capturing_tag = None
        self._text_buffer = []
        self._table_depth = 0
        self._current_row = None
        self._current_rows = None
        self._table_warnings = []
        self._cell_has_span_attr = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in _CAPTURE_TAGS:
            self._capturing_tag = tag
            self._text_buffer = []
            if tag in ("td", "th"):
                attr_names = {a[0].lower() for a in attrs}
                if "colspan" in attr_names or "rowspan" in attr_names:
                    self._cell_has_span_attr = True
        elif tag in ("ul", "ol"):
            self.events.append(("list_start",))
        elif tag == "table":
            self._table_depth += 1
            if self._table_depth == 1:
                self._current_rows = []
                self._table_warnings = []
        elif tag == "tr" and self._table_depth == 1:
            self._current_row = []

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = "".join(self._text_buffer).strip()
            if text:
                self.events.append(("heading", int(tag[1]), text))
            self._capturing_tag = None
        elif tag == "p":
            text = "".join(self._text_buffer).strip()
            if text:
                self.events.append(("paragraph", text))
            self._capturing_tag = None
        elif tag == "title":
            self.events.append(("title", "".join(self._text_buffer).strip()))
            self._capturing_tag = None
        elif tag == "li":
            self.events.append(("list_item", "".join(self._text_buffer).strip()))
            self._capturing_tag = None
        elif tag in ("td", "th"):
            text = "".join(self._text_buffer).strip()
            if self._current_row is not None:
                self._current_row.append(text)
            if self._cell_has_span_attr:
                self._table_warnings.append("TABLE_STRUCTURE_SIMPLIFIED")
                self._cell_has_span_attr = False
            self._capturing_tag = None
        elif tag == "tr" and self._table_depth == 1:
            if self._current_row is not None and self._current_rows is not None:
                self._current_rows.append(self._current_row)
            self._current_row = None
        elif tag in ("ul", "ol"):
            self.events.append(("list_end",))
        elif tag == "table":
            if self._table_depth == 1:
                self.events.append(
                    ("table_end", list(self._current_rows or []), sorted(set(self._table_warnings)))
                )
                self._current_rows = None
            self._table_depth = max(0, self._table_depth - 1)

    def handle_data(self, data):
        if self._capturing_tag is not None:
            self._text_buffer.append(data)


def extract_html(data: bytes, document_id: str):
    warnings = []
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
        warnings.append("DECODE_ERROR_REPLACED_CHARACTERS")

    parser = _StructuralHTMLParser()
    try:
        parser.feed(text)
        parser.close()
    except Exception:
        return (
            [Page(page_number=1, extraction_status="FAILED", blocks=[], warnings=["PARSER_EXCEPTION"])],
            warnings + ["PARSER_EXCEPTION"],
            TitleInfo(detection_status="NOT_DETECTED"),
        )

    blocks = []
    sequence = 1
    current_heading_block_id = None
    title_text = None

    for event in parser.events:
        kind = event[0]
        if kind == "title":
            title_text = event[1] or None
            continue

        block_id = f"{document_id}:p1:b{sequence}"
        if kind == "heading":
            level, text = event[1], event[2]
            block = Block(
                block_id=block_id, sequence=sequence, block_type="HEADING", text=text,
                page_number=1, heading_level=level, parent_section=current_heading_block_id,
            )
            blocks.append(block)
            current_heading_block_id = block_id
            sequence += 1
        elif kind == "paragraph":
            block = Block(
                block_id=block_id, sequence=sequence, block_type="PARAGRAPH", text=event[1],
                page_number=1, parent_section=current_heading_block_id,
            )
            blocks.append(block)
            sequence += 1
        elif kind == "list_start":
            block = Block(
                block_id=block_id, sequence=sequence, block_type="LIST", text="",
                page_number=1, parent_section=current_heading_block_id,
            )
            blocks.append(block)
            sequence += 1
        elif kind == "list_item":
            block = Block(
                block_id=block_id, sequence=sequence, block_type="LIST_ITEM", text=event[1],
                page_number=1, parent_section=current_heading_block_id,
            )
            blocks.append(block)
            sequence += 1
        elif kind == "table_end":
            rows, table_warnings = event[1], event[2]
            table = Table(rows=rows, detection_status="DETECTED")
            block = Block(
                block_id=block_id, sequence=sequence, block_type="TABLE", text="",
                page_number=1, parent_section=current_heading_block_id,
                table=table, warnings=table_warnings,
            )
            blocks.append(block)
            warnings.extend(w for w in table_warnings if w not in warnings)
            sequence += 1
        # "list_end" carries no block

    if blocks:
        page = Page(page_number=1, extraction_status="SUCCESS", blocks=blocks, warnings=[])
    else:
        page = Page(page_number=1, extraction_status="EMPTY", blocks=[], warnings=["EMPTY_PAGE"])

    title = TitleInfo(
        detection_status="DETECTED" if title_text else "NOT_DETECTED",
        text=title_text if title_text else None,
    )
    return [page], warnings, title


# --- PDF ---------------------------------------------------------------


def extract_pdf(data: bytes, document_id: str):
    import pypdf

    warnings = []
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
    except Exception:
        return (
            [Page(page_number=1, extraction_status="FAILED", blocks=[], warnings=["PARSER_EXCEPTION"])],
            ["PARSER_EXCEPTION"],
            TitleInfo(detection_status="NOT_DETECTED"),
        )

    if getattr(reader, "is_encrypted", False):
        return (
            [Page(page_number=1, extraction_status="FAILED", blocks=[], warnings=["ENCRYPTED_PDF_UNSUPPORTED"])],
            ["ENCRYPTED_PDF_UNSUPPORTED"],
            TitleInfo(detection_status="NOT_DETECTED"),
        )

    pages = []
    sequence = 1
    try:
        raw_pages = reader.pages
        page_count = len(raw_pages)
    except Exception:
        return (
            [Page(page_number=1, extraction_status="FAILED", blocks=[], warnings=["PARSER_EXCEPTION"])],
            ["PARSER_EXCEPTION"],
            TitleInfo(detection_status="NOT_DETECTED"),
        )

    for i in range(page_count):
        page_number = i + 1
        try:
            text = raw_pages[i].extract_text() or ""
        except Exception:
            pages.append(
                Page(page_number=page_number, extraction_status="FAILED", blocks=[], warnings=["PARSER_EXCEPTION"])
            )
            if "PARSER_EXCEPTION" not in warnings:
                warnings.append("PARSER_EXCEPTION")
            continue

        if not text.strip():
            pages.append(
                Page(page_number=page_number, extraction_status="OCR_REQUIRED", blocks=[], warnings=["EMPTY_PAGE"])
            )
            continue

        chunks = _split_into_chunks(text)
        blocks, sequence = _chunks_to_blocks(
            chunks, page_number=page_number, start_sequence=sequence, document_id=document_id
        )
        pages.append(Page(page_number=page_number, extraction_status="SUCCESS", blocks=blocks, warnings=[]))

    if not pages:
        pages = [Page(page_number=1, extraction_status="EMPTY", blocks=[], warnings=["EMPTY_PAGE"])]

    warnings.append("PDF_TABLE_EXTRACTION_NOT_IMPLEMENTED")
    title = TitleInfo(detection_status="NOT_DETECTED")
    return pages, warnings, title


# --- Shared status aggregation -------------------------------------------


def aggregate_document_extraction_status(pages, had_decode_warning: bool = False) -> str:
    if not pages:
        return "EXTRACTION_FAILED"
    statuses = [p.extraction_status for p in pages]
    if all(s == "OCR_REQUIRED" for s in statuses):
        return "OCR_REQUIRED"
    if all(s in ("FAILED", "EMPTY") for s in statuses):
        return "EXTRACTION_FAILED"
    if all(s == "SUCCESS" for s in statuses) and not had_decode_warning:
        return "EXTRACTION_SUCCESS"
    return "EXTRACTION_PARTIAL"
