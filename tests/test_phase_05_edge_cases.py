"""
Phase 5 tests: empty/whitespace queries, top-k edge cases, invalid
configuration, invalid chunk objects, and security/resource robustness
(docs/PHASE_05_BM25_BASELINE.md Sections K/L/O).

Explicit scope note: these tests document what Phase 5 protects against.
They do not claim comprehensive security coverage.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _bm25_fixtures import make_single_chunk

from chunking.models import Chunk
from retrieval.index import build_index, query
from retrieval.models import Bm25Config

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
# 14/15. Empty / whitespace-only query
# ---------------------------------------------------------------------------


def test_empty_query_returns_no_results(authority_matrix):
    chunk = make_single_chunk("Some content about trademarks.", "D-EMPTYQ", authority_matrix)
    idx = build_index([chunk])
    resp = query(idx, "", top_k=5)
    assert resp.results == []
    assert resp.normalized_query_tokens == []


def test_whitespace_only_query_returns_no_results(authority_matrix):
    chunk = make_single_chunk("Some content about trademarks.", "D-WSQ", authority_matrix)
    idx = build_index([chunk])
    resp = query(idx, "   \t\n  ", top_k=5)
    assert resp.results == []


# ---------------------------------------------------------------------------
# 16/17. top_k edge cases
# ---------------------------------------------------------------------------


def test_top_k_larger_than_corpus_returns_only_available_matches(authority_matrix):
    chunk = make_single_chunk("Trademark registration content.", "D-TOPK-SMALL", authority_matrix)
    idx = build_index([chunk])
    resp = query(idx, "trademark", top_k=1000)
    assert len(resp.results) == 1


@pytest.mark.parametrize("bad_k", [0, -1, -100])
def test_non_positive_top_k_raises_value_error(authority_matrix, bad_k):
    chunk = make_single_chunk("Some content.", "D-BADK", authority_matrix)
    idx = build_index([chunk])
    with pytest.raises(ValueError):
        query(idx, "content", top_k=bad_k)


def test_non_integer_top_k_raises_value_error(authority_matrix):
    chunk = make_single_chunk("Some content.", "D-BADK-TYPE", authority_matrix)
    idx = build_index([chunk])
    with pytest.raises(ValueError):
        query(idx, "content", top_k="5")
    with pytest.raises(ValueError):
        query(idx, "content", top_k=5.5)
    with pytest.raises(ValueError):
        query(idx, "content", top_k=True)  # bool is an int subclass - must not silently pass


def test_query_rejects_non_string_query_text(authority_matrix):
    chunk = make_single_chunk("Some content.", "D-BADQ", authority_matrix)
    idx = build_index([chunk])
    with pytest.raises(TypeError):
        query(idx, None, top_k=5)
    with pytest.raises(TypeError):
        query(idx, 12345, top_k=5)


def test_query_rejects_non_index_first_argument():
    with pytest.raises(TypeError):
        query("not an index", "text", top_k=5)


# ---------------------------------------------------------------------------
# 22. Invalid chunk objects
# ---------------------------------------------------------------------------


def test_build_index_rejects_non_list_input():
    with pytest.raises(TypeError):
        build_index("not a list")
    with pytest.raises(TypeError):
        build_index(None)


def test_build_index_rejects_non_chunk_elements():
    with pytest.raises(TypeError):
        build_index([{"chunk_id": "fake", "text": "fake"}])
    with pytest.raises(TypeError):
        build_index(["just a string"])


def test_build_index_rejects_duplicate_chunk_ids():
    a = _fake_chunk(chunk_id="DUP:p1:b1", text="first version")
    b = _fake_chunk(chunk_id="DUP:p1:b1", text="second version")
    with pytest.raises(ValueError):
        build_index([a, b])


# ---------------------------------------------------------------------------
# 23. Invalid configuration
# ---------------------------------------------------------------------------


def test_bm25_config_rejects_negative_k1():
    with pytest.raises(ValueError):
        Bm25Config(k1=-1.0)


@pytest.mark.parametrize("bad_b", [-0.1, 1.1, 2.0])
def test_bm25_config_rejects_b_out_of_bounds(bad_b):
    with pytest.raises(ValueError):
        Bm25Config(b=bad_b)


def test_bm25_config_rejects_non_numeric_k1_or_b():
    with pytest.raises(ValueError):
        Bm25Config(k1="1.5")
    with pytest.raises(ValueError):
        Bm25Config(b=None)
    with pytest.raises(ValueError):
        Bm25Config(k1=True)  # bool is an int subclass


def test_bm25_config_rejects_unsupported_tokenizer_version():
    with pytest.raises(ValueError):
        Bm25Config(tokenizer_version="v2-does-not-exist")


# ---------------------------------------------------------------------------
# 24/25. Very long text / many chunks (security/resource)
# ---------------------------------------------------------------------------


def test_very_long_chunk_text_does_not_crash(authority_matrix):
    long_text = "regulation compliance requirement " * 2000  # ~70,000 characters, one chunk
    chunk = make_single_chunk(long_text, "D-LONG", authority_matrix)
    idx = build_index([chunk])
    resp = query(idx, "regulation compliance", top_k=1)
    assert len(resp.results) == 1
    assert resp.results[0].score > 0.0


def test_many_chunks_do_not_crash_and_remain_deterministic(authority_matrix):
    chunks = [
        make_single_chunk(f"Document number {i} discusses trademark policy details.", f"D-MANY-{i}", authority_matrix)
        for i in range(300)
    ]
    idx = build_index(chunks)
    resp1 = query(idx, "trademark policy", top_k=10)
    resp2 = query(idx, "trademark policy", top_k=10)
    assert [r.chunk_id for r in resp1.results] == [r.chunk_id for r in resp2.results]
    assert len(resp1.results) == 10


# ---------------------------------------------------------------------------
# 26. Repeated identical chunks (distinct chunk_id, identical text)
# ---------------------------------------------------------------------------


def test_repeated_identical_text_across_distinct_chunks_all_retrievable(authority_matrix):
    chunks = [
        make_single_chunk("Repeated boilerplate clause about jurisdiction.", f"D-REPEAT-{i}", authority_matrix)
        for i in range(10)
    ]
    idx = build_index(chunks)
    resp = query(idx, "repeated boilerplate jurisdiction", top_k=10)
    assert len(resp.results) == 10
    ids = [r.chunk_id for r in resp.results]
    assert len(ids) == len(set(ids))
    scores = {r.score for r in resp.results}
    assert len(scores) == 1  # identical text -> identical score


# ---------------------------------------------------------------------------
# Unusual Unicode / malformed metadata safety net
# ---------------------------------------------------------------------------


def test_unusual_unicode_in_query_does_not_crash(authority_matrix):
    chunk = make_single_chunk("Normal English content about patents.", "D-UNICODE-Q", authority_matrix)
    idx = build_index([chunk])
    resp = query(idx, "emoji test \U0001F600 आयुर्वेद 📄", top_k=5)
    assert resp.results == []  # none of those terms are in the corpus - must not crash
