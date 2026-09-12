"""
Phase 6 tests: FAISS-specific mechanics - vector dimensions, ID mapping
integrity, duplicate chunk_id rejection, NaN/invalid embedding rejection,
DenseIndexConfig validation.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml
from _dense_fixtures import make_fake_model, make_single_chunk

from chunking.models import Chunk
from retrieval.embeddings import EmbeddingModel
from retrieval.faiss_index import build_dense_index, dense_query
from retrieval.models import DenseIndexConfig

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


class _BadDimensionModel(EmbeddingModel):
    """Deliberately returns the wrong shape - for dimension-mismatch tests."""

    def load(self):
        self._loaded = True

    @property
    def dimension(self):
        return 8

    def embed_documents(self, texts):
        return np.zeros((len(texts), 4), dtype=np.float32)  # wrong! declared dim is 8

    def embed_query(self, text):
        return np.zeros(4, dtype=np.float32)  # wrong! declared dim is 8


class _NaNModel(EmbeddingModel):
    """Deliberately returns non-finite values - for NaN/Inf rejection tests."""

    def load(self):
        self._loaded = True

    @property
    def dimension(self):
        return 4

    def embed_documents(self, texts):
        arr = np.zeros((len(texts), 4), dtype=np.float32)
        arr[0][0] = np.nan
        return arr

    def embed_query(self, text):
        return np.array([np.inf, 0.0, 0.0, 0.0], dtype=np.float32)


# ---------------------------------------------------------------------------
# ID mapping integrity
# ---------------------------------------------------------------------------


def test_faiss_internal_position_never_substitutes_for_chunk_id(authority_matrix):
    chunks = [
        make_single_chunk(f"Document number {i} about licensing.", f"D-POS-{i}", authority_matrix) for i in range(5)
    ]
    model = make_fake_model()
    idx = build_dense_index(chunks, model)
    resp = dense_query(idx, model, "licensing", top_k=5)
    real_chunk_ids = {c.chunk_id for c in chunks}
    for result in resp.results:
        assert result.chunk_id in real_chunk_ids
        # never an integer-looking position/index string standing in for identity
        assert not result.chunk_id.isdigit()


def test_chunk_ids_list_preserves_build_order(authority_matrix):
    chunks = [make_single_chunk(f"Item {i} text.", f"D-ORDER-{i}", authority_matrix) for i in range(4)]
    model = make_fake_model()
    idx = build_dense_index(chunks, model)
    assert idx.chunk_ids == [c.chunk_id for c in chunks]


def test_build_dense_index_rejects_duplicate_chunk_ids():
    a = _fake_chunk(chunk_id="DUP:p1:b1", text="first version")
    b = _fake_chunk(chunk_id="DUP:p1:b1", text="second version")
    model = make_fake_model()
    with pytest.raises(ValueError):
        build_dense_index([a, b], model)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_build_dense_index_rejects_non_list_input():
    model = make_fake_model()
    with pytest.raises(TypeError):
        build_dense_index("not a list", model)


def test_build_dense_index_rejects_non_chunk_elements():
    model = make_fake_model()
    with pytest.raises(TypeError):
        build_dense_index([{"chunk_id": "fake"}], model)


def test_build_dense_index_rejects_unloaded_embedding_model():
    model = make_fake_model()
    model._loaded = False  # simulate not having called load()
    with pytest.raises(RuntimeError):
        build_dense_index([], model)


def test_build_dense_index_rejects_non_embedding_model():
    with pytest.raises(TypeError):
        build_dense_index([], "not a model")


# ---------------------------------------------------------------------------
# Dimension mismatch / NaN rejection
# ---------------------------------------------------------------------------


def test_build_dense_index_rejects_mismatched_embedding_dimension():
    model = _BadDimensionModel()
    model.load()
    chunk = _fake_chunk()
    with pytest.raises(ValueError):
        build_dense_index([chunk], model)


def test_build_dense_index_rejects_nan_embeddings():
    model = _NaNModel()
    model.load()
    chunk = _fake_chunk()
    with pytest.raises(ValueError):
        build_dense_index([chunk], model)


def test_dense_query_rejects_nan_query_embedding():
    model = make_fake_model(dimension=4)
    chunk = _fake_chunk()
    idx = build_dense_index([chunk], model)

    # Same model_identity/dimension as `model` (via matching EmbeddingConfig)
    # so the identity/dimension compatibility checks pass and the NaN check
    # specifically is what must fire.
    from retrieval.embeddings import EmbeddingConfig

    bad_model = _NaNModel(config=EmbeddingConfig(model_name=model.model_identity))
    bad_model.load()
    with pytest.raises(ValueError):
        dense_query(idx, bad_model, "text", top_k=1)


# ---------------------------------------------------------------------------
# DenseIndexConfig validation
# ---------------------------------------------------------------------------


def test_dense_index_config_defaults_to_flat_ip():
    config = DenseIndexConfig()
    assert config.index_type == "FLAT_IP"


def test_dense_index_config_rejects_unsupported_index_type():
    with pytest.raises(ValueError):
        DenseIndexConfig(index_type="IVF")
    with pytest.raises(ValueError):
        DenseIndexConfig(index_type="HNSW")
    with pytest.raises(ValueError):
        DenseIndexConfig(index_type="NOT_A_REAL_TYPE")
