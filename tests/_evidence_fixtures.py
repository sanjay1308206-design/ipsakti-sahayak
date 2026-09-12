"""
Phase 8 test-support module: builds real Phase 4 chunks (reusing
tests/_bm25_fixtures.py / tests/_dense_fixtures.py) and real Phase 5/6/7
retrieval candidates, for use by tests/test_phase_08_*.py.

SYNTHETIC TEST FIXTURE GENERATOR ONLY. Not a test module itself (no test_
prefix) - pytest will not collect it.
"""

from __future__ import annotations

from _bm25_fixtures import make_chunks, make_single_chunk
from _dense_fixtures import make_fake_model
from _hybrid_fixtures import make_fake_reranker

from retrieval.faiss_index import build_dense_index, dense_query
from retrieval.hybrid import rerank_candidates
from retrieval.index import build_index
from retrieval.index import query as bm25_query
from retrieval.rrf import fuse_rrf

__all__ = [
    "make_chunks",
    "make_single_chunk",
    "make_fake_model",
    "make_fake_reranker",
    "make_bm25_response",
    "make_dense_response",
    "make_rrf_response",
    "make_hybrid_response",
]


def make_bm25_response(chunks, query_text: str, top_k: int = 10):
    index = build_index(chunks)
    return bm25_query(index, query_text, top_k=top_k)


def make_dense_response(chunks, query_text: str, top_k: int = 10, dimension: int = 32):
    model = make_fake_model(dimension=dimension)
    index = build_dense_index(chunks, model)
    return dense_query(index, model, query_text, top_k=top_k)


def make_rrf_response(chunks, query_text: str, top_k: int = 10, candidate_k: int = 10):
    bm25_resp = make_bm25_response(chunks, query_text, top_k=top_k)
    dense_resp = make_dense_response(chunks, query_text, top_k=top_k)
    return fuse_rrf(bm25_resp, dense_resp, candidate_k=candidate_k)


def make_hybrid_response(chunks, query_text: str, top_k: int = 10, candidate_k: int = 10):
    rrf_resp = make_rrf_response(chunks, query_text, top_k=top_k, candidate_k=candidate_k)
    reranker = make_fake_reranker()
    return rerank_candidates(rrf_resp, reranker, top_k=top_k)
