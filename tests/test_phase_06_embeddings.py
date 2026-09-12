"""
Phase 6 tests: EmbeddingConfig validation, EmbeddingModel lifecycle
(load/dimension/embed_*), l2_normalize, and SentenceTransformerEmbeddingModel's
construction/error-path behavior (never a full real-model download - see
docs/PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md Section R).
"""

from __future__ import annotations

import numpy as np
import pytest

from retrieval.embeddings import (
    DEFAULT_MODEL_NAME,
    EmbeddingConfig,
    EmbeddingModelLoadError,
    EmbeddingModelNotLoadedError,
    FakeEmbeddingModel,
    SentenceTransformerEmbeddingModel,
    l2_normalize,
)


# ---------------------------------------------------------------------------
# EmbeddingConfig
# ---------------------------------------------------------------------------


def test_embedding_config_defaults_to_bge_m3():
    config = EmbeddingConfig()
    assert config.model_name == "BAAI/bge-m3" == DEFAULT_MODEL_NAME
    assert config.device == "cpu"
    assert config.normalize is True


def test_embedding_config_rejects_empty_model_name():
    with pytest.raises(ValueError):
        EmbeddingConfig(model_name="")
    with pytest.raises(ValueError):
        EmbeddingConfig(model_name="   ")


def test_embedding_config_rejects_empty_device():
    with pytest.raises(ValueError):
        EmbeddingConfig(device="")


def test_embedding_config_rejects_non_bool_normalize():
    with pytest.raises(ValueError):
        EmbeddingConfig(normalize="true")


def test_embedding_config_rejects_non_positive_batch_size():
    with pytest.raises(ValueError):
        EmbeddingConfig(batch_size=0)
    with pytest.raises(ValueError):
        EmbeddingConfig(batch_size=-5)


def test_embedding_config_signature_excludes_device():
    cpu_config = EmbeddingConfig(model_name="fake-x", device="cpu")
    gpu_config = EmbeddingConfig(model_name="fake-x", device="cuda")
    assert cpu_config.signature == gpu_config.signature


def test_embedding_config_signature_changes_with_model_or_normalize():
    base = EmbeddingConfig(model_name="fake-x", normalize=True)
    other_model = EmbeddingConfig(model_name="fake-y", normalize=True)
    other_normalize = EmbeddingConfig(model_name="fake-x", normalize=False)
    assert base.signature != other_model.signature
    assert base.signature != other_normalize.signature


# ---------------------------------------------------------------------------
# l2_normalize
# ---------------------------------------------------------------------------


def test_l2_normalize_produces_unit_vectors():
    vectors = np.array([[3.0, 4.0], [1.0, 0.0]], dtype=np.float32)
    normalized = l2_normalize(vectors)
    norms = np.linalg.norm(normalized, axis=1)
    assert np.allclose(norms, 1.0)


def test_l2_normalize_1d_vector():
    vector = np.array([3.0, 4.0], dtype=np.float32)
    normalized = l2_normalize(vector)
    assert normalized.shape == (2,)
    assert np.isclose(np.linalg.norm(normalized), 1.0)


def test_l2_normalize_zero_vector_stays_zero_not_nan():
    vectors = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)
    normalized = l2_normalize(vectors)
    assert np.all(normalized == 0.0)
    assert np.isfinite(normalized).all()


def test_l2_normalize_is_deterministic():
    vectors = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
    assert np.array_equal(l2_normalize(vectors), l2_normalize(vectors))


# ---------------------------------------------------------------------------
# EmbeddingModel lifecycle (using FakeEmbeddingModel as a concrete instance)
# ---------------------------------------------------------------------------


def test_embed_before_load_raises_not_loaded_error():
    model = FakeEmbeddingModel(dimension=8)
    with pytest.raises(EmbeddingModelNotLoadedError):
        _ = model.dimension
    with pytest.raises(EmbeddingModelNotLoadedError):
        model.embed_query("text")
    with pytest.raises(EmbeddingModelNotLoadedError):
        model.embed_documents(["text"])


def test_model_is_loaded_flag():
    model = FakeEmbeddingModel(dimension=8)
    assert model.is_loaded is False
    model.load()
    assert model.is_loaded is True


def test_fake_embedding_model_rejects_non_positive_dimension():
    with pytest.raises(ValueError):
        FakeEmbeddingModel(dimension=0)
    with pytest.raises(ValueError):
        FakeEmbeddingModel(dimension=-1)


def test_fake_embedding_model_produces_correct_shapes():
    model = FakeEmbeddingModel(dimension=12)
    model.load()
    docs = model.embed_documents(["hello world", "trademark registration"])
    assert docs.shape == (2, 12)
    query = model.embed_query("hello")
    assert query.shape == (12,)


def test_fake_embedding_model_empty_documents_list():
    model = FakeEmbeddingModel(dimension=12)
    model.load()
    docs = model.embed_documents([])
    assert docs.shape == (0, 12)


def test_fake_embedding_model_is_deterministic():
    model_a = FakeEmbeddingModel(dimension=12)
    model_a.load()
    model_b = FakeEmbeddingModel(dimension=12)
    model_b.load()
    assert np.array_equal(model_a.embed_query("consistent text"), model_b.embed_query("consistent text"))


def test_fake_embedding_model_similar_text_more_similar_than_dissimilar_text():
    model = FakeEmbeddingModel(dimension=64)
    model.load()
    from retrieval.embeddings import l2_normalize

    a = l2_normalize(model.embed_query("trademark registration application"))
    b = l2_normalize(model.embed_query("trademark registration process"))
    c = l2_normalize(model.embed_query("weather rainfall agriculture"))
    assert np.dot(a, b) > np.dot(a, c)


def test_fake_embedding_model_raw_output_is_not_pre_normalized():
    model = FakeEmbeddingModel(dimension=8)
    model.load()
    vector = model.embed_query("some words here")
    # raw embedding is a sum of token vectors - not expected to already be unit norm
    assert not np.isclose(np.linalg.norm(vector), 1.0)


# ---------------------------------------------------------------------------
# SentenceTransformerEmbeddingModel - construction/error paths only
# ---------------------------------------------------------------------------


def test_sentence_transformer_model_not_loaded_by_default():
    model = SentenceTransformerEmbeddingModel(EmbeddingConfig(model_name="BAAI/bge-m3"))
    assert model.is_loaded is False
    assert model.model_identity == "BAAI/bge-m3"


def test_sentence_transformer_model_load_failure_raises_clear_error_not_silent_fallback(monkeypatch):
    # An invalid/unresolvable model name must never silently fall back to a
    # different (e.g. smaller/cached) model - it must raise clearly. The
    # underlying SentenceTransformer construction is monkeypatched to fail
    # deterministically and offline (no network round-trip to Hugging Face
    # Hub is needed to prove this error path - manually verified once,
    # separately, against the real library: see
    # docs/PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md Section X).
    import sentence_transformers

    def fake_constructor(*args, **kwargs):
        raise OSError("simulated: model 'this-model-does-not-exist-xyz123' not found")

    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", fake_constructor)
    model = SentenceTransformerEmbeddingModel(
        EmbeddingConfig(model_name="this-model-definitely-does-not-exist-xyz123")
    )
    with pytest.raises(EmbeddingModelLoadError):
        model.load()
    assert model.is_loaded is False


def test_sentence_transformer_model_missing_dependency_raises_clear_error(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "sentence_transformers":
            raise ImportError("simulated: sentence_transformers not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    model = SentenceTransformerEmbeddingModel(EmbeddingConfig())
    with pytest.raises(EmbeddingModelLoadError):
        model.load()
