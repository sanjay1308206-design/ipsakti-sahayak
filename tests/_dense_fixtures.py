"""
Phase 6 test-support module: builds real Phase 4 chunking.models.Chunk
objects (reusing tests/_bm25_fixtures.py, which reuses tests/_chunk_fixtures.py)
plus a loaded, deterministic retrieval.embeddings.FakeEmbeddingModel, for
use by tests/test_phase_06_*.py.

SYNTHETIC TEST FIXTURE GENERATOR ONLY. Not a test module itself (no test_
prefix) - pytest will not collect it.
"""

from __future__ import annotations

from _bm25_fixtures import make_chunks, make_single_chunk

from retrieval.embeddings import EmbeddingConfig, FakeEmbeddingModel

__all__ = ["make_chunks", "make_single_chunk", "make_fake_model"]


def make_fake_model(dimension: int = 16, **config_overrides) -> FakeEmbeddingModel:
    """A loaded, ready-to-use FakeEmbeddingModel - never downloads anything."""
    config = EmbeddingConfig(model_name="fake-embedding-v1", device="cpu", **config_overrides)
    model = FakeEmbeddingModel(config=config, dimension=dimension)
    model.load()
    return model
