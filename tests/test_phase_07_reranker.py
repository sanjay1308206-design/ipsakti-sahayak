"""
Phase 7 tests: Reranker/RerankerConfig contract, lifecycle, and
CrossEncoderReranker construction/error paths - never a full real-model
download (docs/PHASE_07_HYBRID_FUSION_AND_RERANKING.md Sections L/M/N).
"""

from __future__ import annotations

import numpy as np
import pytest

from retrieval.reranker import (
    DEFAULT_RERANKER_MODEL_NAME,
    CrossEncoderReranker,
    FakeReranker,
    RerankerConfig,
    RerankerLoadError,
    RerankerNotLoadedError,
)


# ---------------------------------------------------------------------------
# RerankerConfig
# ---------------------------------------------------------------------------


def test_reranker_config_defaults_to_bge_reranker_v2_m3():
    config = RerankerConfig()
    assert config.model_name == "BAAI/bge-reranker-v2-m3" == DEFAULT_RERANKER_MODEL_NAME
    assert config.device == "cpu"


def test_reranker_config_rejects_empty_model_name():
    with pytest.raises(ValueError):
        RerankerConfig(model_name="")
    with pytest.raises(ValueError):
        RerankerConfig(model_name="   ")


def test_reranker_config_rejects_empty_device():
    with pytest.raises(ValueError):
        RerankerConfig(device="")


def test_reranker_config_rejects_non_positive_batch_size():
    with pytest.raises(ValueError):
        RerankerConfig(batch_size=0)
    with pytest.raises(ValueError):
        RerankerConfig(batch_size=-1)


def test_reranker_config_signature_excludes_device():
    cpu_config = RerankerConfig(model_name="fake-x", device="cpu")
    gpu_config = RerankerConfig(model_name="fake-x", device="cuda")
    assert cpu_config.signature == gpu_config.signature


def test_reranker_config_signature_changes_with_model():
    a = RerankerConfig(model_name="fake-x")
    b = RerankerConfig(model_name="fake-y")
    assert a.signature != b.signature


# ---------------------------------------------------------------------------
# Reranker lifecycle
# ---------------------------------------------------------------------------


def test_score_before_load_raises_not_loaded_error():
    reranker = FakeReranker()
    with pytest.raises(RerankerNotLoadedError):
        reranker.score("query", ["text"])


def test_reranker_is_loaded_flag():
    reranker = FakeReranker()
    assert reranker.is_loaded is False
    reranker.load()
    assert reranker.is_loaded is True


def test_model_identity_reflects_config():
    reranker = FakeReranker(RerankerConfig(model_name="custom-fake"))
    assert reranker.model_identity == "custom-fake"


# ---------------------------------------------------------------------------
# FakeReranker - deterministic term-overlap scoring
# ---------------------------------------------------------------------------


def test_fake_reranker_scores_higher_overlap_higher():
    reranker = FakeReranker()
    reranker.load()
    scores = reranker.score("trademark registration", ["trademark registration application", "unrelated text about weather"])
    assert scores[0] > scores[1]


def test_fake_reranker_empty_candidate_list_returns_empty_array():
    reranker = FakeReranker()
    reranker.load()
    scores = reranker.score("query", [])
    assert len(scores) == 0
    assert isinstance(scores, np.ndarray)


def test_fake_reranker_is_deterministic():
    reranker_a = FakeReranker()
    reranker_a.load()
    reranker_b = FakeReranker()
    reranker_b.load()
    texts = ["trademark application", "patent filing", "ayurveda formulation"]
    assert np.array_equal(reranker_a.score("trademark", texts), reranker_b.score("trademark", texts))


def test_fake_reranker_never_claims_to_be_real_model():
    reranker = FakeReranker()
    assert "bge-reranker" not in reranker.model_identity.lower()
    assert reranker.model_identity == "fake-reranker-v1"


def test_fake_reranker_does_not_modify_candidate_texts():
    reranker = FakeReranker()
    reranker.load()
    texts = ["Original text one.", "Original text two."]
    original = list(texts)
    reranker.score("query", texts)
    assert texts == original


def test_fake_reranker_returns_one_score_per_candidate():
    reranker = FakeReranker()
    reranker.load()
    texts = [f"Document {i}" for i in range(7)]
    scores = reranker.score("document", texts)
    assert len(scores) == 7


def test_fake_reranker_handles_multilingual_text_without_crashing():
    reranker = FakeReranker()
    reranker.load()
    scores = reranker.score("पंजीकरण", ["आयुर्वेद पंजीकरण नियम", "unrelated english text", "மருந்து பதிவு"])
    assert len(scores) == 3
    assert all(np.isfinite(s) for s in scores)


# ---------------------------------------------------------------------------
# CrossEncoderReranker - construction/error paths only
# ---------------------------------------------------------------------------


def test_cross_encoder_reranker_not_loaded_by_default():
    reranker = CrossEncoderReranker(RerankerConfig(model_name="BAAI/bge-reranker-v2-m3"))
    assert reranker.is_loaded is False
    assert reranker.model_identity == "BAAI/bge-reranker-v2-m3"


def test_cross_encoder_reranker_load_failure_raises_clear_error_not_silent_fallback(monkeypatch):
    # Monkeypatched to fail deterministically and offline - no network
    # round-trip needed to prove this error path (manually verified once,
    # separately, against the real library with an already-cached smaller
    # cross-encoder model: see docs/PHASE_07_HYBRID_FUSION_AND_RERANKING.md
    # Section Z).
    import sentence_transformers

    def fake_constructor(*args, **kwargs):
        raise OSError("simulated: model 'this-model-does-not-exist-xyz123' not found")

    monkeypatch.setattr(sentence_transformers, "CrossEncoder", fake_constructor)
    reranker = CrossEncoderReranker(RerankerConfig(model_name="this-model-definitely-does-not-exist-xyz123"))
    with pytest.raises(RerankerLoadError):
        reranker.load()
    assert reranker.is_loaded is False


def test_cross_encoder_reranker_missing_dependency_raises_clear_error(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "sentence_transformers":
            raise ImportError("simulated: sentence_transformers not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    reranker = CrossEncoderReranker(RerankerConfig())
    with pytest.raises(RerankerLoadError):
        reranker.load()
