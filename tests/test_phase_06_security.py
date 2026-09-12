"""
Phase 6 tests: security/defensive validation - empty corpus, empty query,
duplicate chunk IDs, mismatched dimensions, NaN/Inf embeddings, invalid
top_k, malformed metadata, corrupted persisted index, incompatible model
configuration, missing files, Unicode edge cases, very long text, and
repeated identical chunks (docs/PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md
Section S).

Explicit scope note: these tests document what Phase 6 protects against.
They do not claim comprehensive security coverage.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from _dense_fixtures import make_fake_model, make_single_chunk

from chunking.models import Chunk
from retrieval.embeddings import EmbeddingConfig
from retrieval.faiss_index import build_dense_index, dense_query
from retrieval.models import DenseIndexCompatibilityError
from retrieval.serialize import load_dense_index, save_dense_index

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def _fake_chunk(chunk_id="FAKE:p1:b1", text="fake text", document_id="FAKE-DOC"):
    return Chunk(
        chunk_id=chunk_id,
        chunk_sequence=1,
        document_id=document_id,
        source_family_id="SF-01",
        jurisdiction="INDIA",
        content_hash="deadbeef",
        synthetic=True,
        text=text,
        text_size=len(text),
        size_unit="UNICODE_CODE_POINTS",
        page_numbers=[1],
        block_ids=["FAKE-DOC:p1:b1"],
        block_types=["PARAGRAPH"],
    )


# ---------------------------------------------------------------------------
# Empty corpus / empty query
# ---------------------------------------------------------------------------


def test_empty_corpus_index_and_query_do_not_crash():
    model = make_fake_model()
    idx = build_dense_index([], model)
    resp = dense_query(idx, model, "anything", top_k=5)
    assert resp.results == []


def test_empty_query_does_not_crash_and_returns_zero_similarity_results(authority_matrix):
    chunk = make_single_chunk("Some content about trademarks.", "D-EMPTYQ", authority_matrix)
    model = make_fake_model()
    idx = build_dense_index([chunk], model)
    resp = dense_query(idx, model, "", top_k=5)
    assert len(resp.results) == 1
    assert resp.results[0].score == 0.0


def test_whitespace_only_query_does_not_crash(authority_matrix):
    chunk = make_single_chunk("Some content about trademarks.", "D-WSQ", authority_matrix)
    model = make_fake_model()
    idx = build_dense_index([chunk], model)
    resp = dense_query(idx, model, "   \t\n  ", top_k=5)
    assert len(resp.results) == 1


# ---------------------------------------------------------------------------
# Invalid top_k
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_k", [0, -1, -100])
def test_non_positive_top_k_raises_value_error(authority_matrix, bad_k):
    chunk = make_single_chunk("Some content.", "D-BADK", authority_matrix)
    model = make_fake_model()
    idx = build_dense_index([chunk], model)
    with pytest.raises(ValueError):
        dense_query(idx, model, "content", top_k=bad_k)


def test_non_integer_top_k_raises_value_error(authority_matrix):
    chunk = make_single_chunk("Some content.", "D-BADK-TYPE", authority_matrix)
    model = make_fake_model()
    idx = build_dense_index([chunk], model)
    with pytest.raises(ValueError):
        dense_query(idx, model, "content", top_k="5")
    with pytest.raises(ValueError):
        dense_query(idx, model, "content", top_k=5.5)
    with pytest.raises(ValueError):
        dense_query(idx, model, "content", top_k=True)


def test_top_k_larger_than_corpus_returns_only_available_matches(authority_matrix):
    chunk = make_single_chunk("Trademark registration content.", "D-TOPK-SMALL", authority_matrix)
    model = make_fake_model()
    idx = build_dense_index([chunk], model)
    resp = dense_query(idx, model, "trademark", top_k=1000)
    assert len(resp.results) == 1


# ---------------------------------------------------------------------------
# Incompatible model configuration
# ---------------------------------------------------------------------------


def test_querying_with_a_different_model_identity_is_rejected(authority_matrix):
    chunk = make_single_chunk("Some content.", "D-MODEL-MISMATCH", authority_matrix)
    model_a = make_fake_model()
    idx = build_dense_index([chunk], model_a)
    model_b = make_fake_model()
    model_b.config = EmbeddingConfig(model_name="a-different-model-name")
    with pytest.raises(ValueError):
        dense_query(idx, model_b, "content", top_k=1)


def test_querying_with_a_different_dimension_is_rejected(authority_matrix):
    chunk = make_single_chunk("Some content.", "D-DIM-MISMATCH", authority_matrix)
    model_16 = make_fake_model(dimension=16)
    idx = build_dense_index([chunk], model_16)
    model_32 = make_fake_model(dimension=32)
    model_32.config = EmbeddingConfig(model_name=model_16.model_identity)
    with pytest.raises(ValueError):
        dense_query(idx, model_32, "content", top_k=1)


def test_dense_query_rejects_unloaded_embedding_model(authority_matrix):
    chunk = make_single_chunk("Some content.", "D-UNLOADED", authority_matrix)
    model = make_fake_model()
    idx = build_dense_index([chunk], model)
    fresh_model = make_fake_model()
    fresh_model._loaded = False
    with pytest.raises(RuntimeError):
        dense_query(idx, fresh_model, "content", top_k=1)


# ---------------------------------------------------------------------------
# Persistence: missing files / corrupted metadata / incompatible index
# ---------------------------------------------------------------------------


def test_loading_missing_faiss_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_dense_index(tmp_path / "does_not_exist.faiss", tmp_path / "does_not_exist.json")


def test_loading_missing_metadata_file_raises_file_not_found(authority_matrix, tmp_path):
    chunk = make_single_chunk("Content.", "D-MISSING-META", authority_matrix)
    model = make_fake_model()
    idx = build_dense_index([chunk], model)
    faiss_path = tmp_path / "index.faiss"
    metadata_path = tmp_path / "index.json"
    save_dense_index(idx, faiss_path, metadata_path)
    metadata_path.unlink()
    with pytest.raises(FileNotFoundError):
        load_dense_index(faiss_path, metadata_path)


def test_loading_corrupted_metadata_json_raises_compatibility_error(authority_matrix, tmp_path):
    chunk = make_single_chunk("Content.", "D-CORRUPT-META", authority_matrix)
    model = make_fake_model()
    idx = build_dense_index([chunk], model)
    faiss_path = tmp_path / "index.faiss"
    metadata_path = tmp_path / "index.json"
    save_dense_index(idx, faiss_path, metadata_path)
    metadata_path.write_text("{not valid json!!", encoding="utf-8")
    with pytest.raises(DenseIndexCompatibilityError):
        load_dense_index(faiss_path, metadata_path)


def test_loading_metadata_with_missing_required_keys_raises_compatibility_error(authority_matrix, tmp_path):
    chunk = make_single_chunk("Content.", "D-MISSING-KEYS", authority_matrix)
    model = make_fake_model()
    idx = build_dense_index([chunk], model)
    faiss_path = tmp_path / "index.faiss"
    metadata_path = tmp_path / "index.json"
    save_dense_index(idx, faiss_path, metadata_path)

    raw = json.loads(metadata_path.read_text(encoding="utf-8"))
    del raw["content"]["signature"]
    metadata_path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(DenseIndexCompatibilityError):
        load_dense_index(faiss_path, metadata_path)


def test_loading_metadata_with_tampered_signature_raises_compatibility_error(authority_matrix, tmp_path):
    chunk = make_single_chunk("Content.", "D-TAMPERED-SIG", authority_matrix)
    model = make_fake_model()
    idx = build_dense_index([chunk], model)
    faiss_path = tmp_path / "index.faiss"
    metadata_path = tmp_path / "index.json"
    save_dense_index(idx, faiss_path, metadata_path)

    raw = json.loads(metadata_path.read_text(encoding="utf-8"))
    raw["content"]["signature"] = "0" * 64  # hand-edited, no longer matches recomputed signature
    metadata_path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(DenseIndexCompatibilityError):
        load_dense_index(faiss_path, metadata_path)


def test_loading_metadata_with_tampered_chunk_count_raises_compatibility_error(authority_matrix, tmp_path):
    chunk = make_single_chunk("Content.", "D-TAMPERED-COUNT", authority_matrix)
    model = make_fake_model()
    idx = build_dense_index([chunk], model)
    faiss_path = tmp_path / "index.faiss"
    metadata_path = tmp_path / "index.json"
    save_dense_index(idx, faiss_path, metadata_path)

    raw = json.loads(metadata_path.read_text(encoding="utf-8"))
    raw["content"]["chunk_count"] = 999
    metadata_path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(DenseIndexCompatibilityError):
        load_dense_index(faiss_path, metadata_path)


def test_loading_corrupted_faiss_binary_raises_compatibility_error(authority_matrix, tmp_path):
    chunk = make_single_chunk("Content.", "D-CORRUPT-FAISS", authority_matrix)
    model = make_fake_model()
    idx = build_dense_index([chunk], model)
    faiss_path = tmp_path / "index.faiss"
    metadata_path = tmp_path / "index.json"
    save_dense_index(idx, faiss_path, metadata_path)
    faiss_path.write_bytes(b"not a real faiss index file")
    with pytest.raises(DenseIndexCompatibilityError):
        load_dense_index(faiss_path, metadata_path)


# ---------------------------------------------------------------------------
# Very long text / repeated identical chunks / duplicate IDs / malformed metadata
# ---------------------------------------------------------------------------


def test_very_long_chunk_text_does_not_crash(authority_matrix):
    long_text = "regulation compliance requirement " * 2000
    chunk = make_single_chunk(long_text, "D-LONG", authority_matrix)
    model = make_fake_model()
    idx = build_dense_index([chunk], model)
    resp = dense_query(idx, model, "regulation compliance", top_k=1)
    assert len(resp.results) == 1


def test_repeated_identical_chunks_are_all_indexed_and_retrievable(authority_matrix):
    chunks = [
        make_single_chunk("Repeated boilerplate clause about jurisdiction.", f"D-REPEAT-{i}", authority_matrix)
        for i in range(10)
    ]
    model = make_fake_model()
    idx = build_dense_index(chunks, model)
    resp = dense_query(idx, model, "repeated boilerplate jurisdiction", top_k=10)
    assert len(resp.results) == 10
    ids = [r.chunk_id for r in resp.results]
    assert len(ids) == len(set(ids))
    scores = {round(r.score, 6) for r in resp.results}
    assert len(scores) == 1  # identical text -> identical score


def test_build_dense_index_rejects_duplicate_chunk_ids():
    a = _fake_chunk(chunk_id="DUP:p1:b1", text="first")
    b = _fake_chunk(chunk_id="DUP:p1:b1", text="second")
    model = make_fake_model()
    with pytest.raises(ValueError):
        build_dense_index([a, b], model)


def test_unusual_unicode_in_query_does_not_crash(authority_matrix):
    chunk = make_single_chunk("Normal English content about patents.", "D-UNICODE-Q", authority_matrix)
    model = make_fake_model()
    idx = build_dense_index([chunk], model)
    resp = dense_query(idx, model, "emoji test \U0001F600 आयुर्वेद 📄", top_k=1)
    assert len(resp.results) == 1


def test_many_chunks_do_not_crash_and_remain_deterministic(authority_matrix):
    chunks = [
        make_single_chunk(f"Document number {i} discusses trademark policy details.", f"D-MANY-{i}", authority_matrix)
        for i in range(300)
    ]
    model = make_fake_model()
    idx = build_dense_index(chunks, model)
    resp1 = dense_query(idx, model, "trademark policy", top_k=10)
    resp2 = dense_query(idx, model, "trademark policy", top_k=10)
    assert [r.chunk_id for r in resp1.results] == [r.chunk_id for r in resp2.results]
    assert len(resp1.results) == 10
