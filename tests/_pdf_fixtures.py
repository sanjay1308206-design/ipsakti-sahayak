"""
Phase 3 test-support module: builds minimal, synthetic, in-memory PDF byte
strings for testing src/ingestion/extractors.extract_pdf without ever
downloading or committing a real government document.

SYNTHETIC TEST FIXTURE GENERATOR ONLY. Nothing produced here is, or
resembles, real regulatory material - text content is placeholder only.
Not a test module itself (no test_ prefix) - pytest will not collect it.
"""

from __future__ import annotations

import io


def make_minimal_text_pdf(text: str) -> bytes:
    """A hand-built, single-page, valid PDF containing the given ASCII text."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    ]
    stream = f"BT /F1 12 Tf 10 100 Td ({text}) Tj ET".encode("latin-1")
    objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_offset = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF"
    ).encode()
    return bytes(out)


def make_multi_page_text_pdf(page_texts: list) -> bytes:
    """Multiple pages, each with its own text - built via pypdf's writer + merge."""
    import pypdf

    merger = pypdf.PdfWriter()
    for text in page_texts:
        single = pypdf.PdfReader(io.BytesIO(make_minimal_text_pdf(text)))
        merger.append(single)
    buf = io.BytesIO()
    merger.write(buf)
    return buf.getvalue()


def make_blank_pages_pdf(page_count: int) -> bytes:
    """Pages with no text content at all (simulates a scanned/image-only PDF)."""
    import pypdf

    writer = pypdf.PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def make_encrypted_pdf(text: str, password: str = "secret") -> bytes:
    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(make_minimal_text_pdf(text)))
    writer = pypdf.PdfWriter()
    writer.append(reader)
    writer.encrypt(user_password=password)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def make_malformed_pdf() -> bytes:
    """Not a valid PDF at all - random bytes with a PDF-like header."""
    return b"%PDF-1.4\nthis is not a real pdf structure at all\n%%EOF"
