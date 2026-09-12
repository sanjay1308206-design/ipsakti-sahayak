"""
Phase 7 test-support module: builds real Phase 4 chunking.models.Chunk
objects (reusing tests/_bm25_fixtures.py / tests/_dense_fixtures.py), a
loaded deterministic FakeEmbeddingModel, and a loaded deterministic
FakeReranker, for use by tests/test_phase_07_*.py.

SYNTHETIC TEST FIXTURE GENERATOR ONLY. Not a test module itself (no test_
prefix) - pytest will not collect it.
"""

from __future__ import annotations

from _bm25_fixtures import make_chunks, make_single_chunk
from _dense_fixtures import make_fake_model

from retrieval.reranker import FakeReranker, RerankerConfig

__all__ = ["make_chunks", "make_single_chunk", "make_fake_model", "make_fake_reranker"]


def make_fake_reranker(**config_overrides) -> FakeReranker:
    """A loaded, ready-to-use FakeReranker - never downloads anything."""
    config = RerankerConfig(model_name="fake-reranker-v1", device="cpu", **config_overrides)
    reranker = FakeReranker(config=config)
    reranker.load()
    return reranker
