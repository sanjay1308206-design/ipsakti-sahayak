"""
Phase 4 tests: chunk ID determinism, deterministic serialized output, and
stable behavior across repeated runs on identical input.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _chunk_fixtures import make_document
from _pdf_fixtures import make_multi_page_text_pdf

from chunking.chunker import chunk_document
from chunking.identity import compute_chunk_id
from chunking.models import ChunkingConfig
from chunking.serialize import to_json

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def _sample_document(authority_matrix, document_id="D-DETERMINISM"):
    data = (
        b"1. Definitions\n\nBody one.\n\n"
        b"2. Scope\n\nBody two with more words to test wrapping behavior nicely.\n"
    )
    return make_document(data, ".txt", authority_matrix, document_id=document_id)


def test_running_chunk_document_twice_yields_identical_chunk_count_and_order(authority_matrix):
    doc = _sample_document(authority_matrix)
    r1 = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=30))
    r2 = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=30))
    assert len(r1.chunks) == len(r2.chunks)
    assert [c.chunk_sequence for c in r1.chunks] == [c.chunk_sequence for c in r2.chunks]


def test_running_chunk_document_twice_yields_identical_chunk_ids(authority_matrix):
    doc = _sample_document(authority_matrix)
    r1 = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=30))
    r2 = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=30))
    assert [c.chunk_id for c in r1.chunks] == [c.chunk_id for c in r2.chunks]


def test_running_chunk_document_twice_yields_identical_text_and_metadata(authority_matrix):
    doc = _sample_document(authority_matrix)
    r1 = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=30))
    r2 = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=30))
    for c1, c2 in zip(r1.chunks, r2.chunks):
        assert c1.text == c2.text
        assert c1.page_numbers == c2.page_numbers
        assert c1.block_ids == c2.block_ids
        assert c1.warnings == c2.warnings


def test_running_chunk_document_ten_times_produces_byte_identical_json(authority_matrix):
    doc = _sample_document(authority_matrix)
    config = ChunkingConfig(max_chunk_size_chars=45)
    outputs = {to_json(chunk_document(doc, config)) for _ in range(10)}
    assert len(outputs) == 1


def test_pdf_multi_page_chunking_is_also_deterministic_across_runs(authority_matrix):
    pdf = make_multi_page_text_pdf(["1. Heading", "Body on page two.", "1. Second Heading", "More body."])
    doc = make_document(pdf, ".pdf", authority_matrix, document_id="D-DET-PDF")
    config = ChunkingConfig(max_chunk_size_chars=1000)
    outputs = {to_json(chunk_document(doc, config)) for _ in range(5)}
    assert len(outputs) == 1


def test_chunk_id_is_a_pure_function_of_its_canonical_identity_fields():
    id_a = compute_chunk_id("DOC-1", "hash-1", "sig-1", ["DOC-1:p1:b1"], 0)
    id_b = compute_chunk_id("DOC-1", "hash-1", "sig-1", ["DOC-1:p1:b1"], 0)
    assert id_a == id_b


def test_chunk_id_changes_when_any_identity_field_changes():
    base = compute_chunk_id("DOC-1", "hash-1", "sig-1", ["DOC-1:p1:b1"], 0)
    variants = [
        compute_chunk_id("DOC-2", "hash-1", "sig-1", ["DOC-1:p1:b1"], 0),
        compute_chunk_id("DOC-1", "hash-2", "sig-1", ["DOC-1:p1:b1"], 0),
        compute_chunk_id("DOC-1", "hash-1", "sig-2", ["DOC-1:p1:b1"], 0),
        compute_chunk_id("DOC-1", "hash-1", "sig-1", ["DOC-1:p1:b2"], 0),
        compute_chunk_id("DOC-1", "hash-1", "sig-1", ["DOC-1:p1:b1"], 1),
    ]
    assert base not in variants
    assert len(set(variants)) == len(variants)


def test_chunk_id_is_not_a_random_uuid_or_timestamp():
    chunk_id = compute_chunk_id("DOC-1", "hash-1", "sig-1", ["DOC-1:p1:b1"], 0)
    # deterministic SHA-256 hex digest: fixed length, hex charset only
    assert len(chunk_id) == 64
    assert all(c in "0123456789abcdef" for c in chunk_id)


def test_different_chunking_config_produces_different_chunk_ids(authority_matrix):
    doc = _sample_document(authority_matrix, document_id="D-DET-CFG")
    r_small = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=20))
    r_large = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=2000))
    ids_small = {c.chunk_id for c in r_small.chunks}
    ids_large = {c.chunk_id for c in r_large.chunks}
    assert ids_small.isdisjoint(ids_large)


def test_all_chunk_ids_within_one_result_are_unique(authority_matrix):
    pdf = make_multi_page_text_pdf(["1. A", "aaaa " * 100, "1. B", "bbbb " * 100])
    doc = make_document(pdf, ".pdf", authority_matrix, document_id="D-DET-UNIQUE")
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=30))
    ids = [c.chunk_id for c in result.chunks]
    assert len(ids) == len(set(ids))


def test_chunk_sequence_is_gapless_and_starts_at_one(authority_matrix):
    doc = _sample_document(authority_matrix, document_id="D-DET-SEQ")
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=25))
    sequences = [c.chunk_sequence for c in result.chunks]
    assert sequences == list(range(1, len(sequences) + 1))
