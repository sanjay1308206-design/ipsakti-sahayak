"""
Cross-encoder reranking abstraction
(docs/PHASE_07_HYBRID_FUSION_AND_RERANKING.md Section L/M/N).

Reranker is a small, explicit interface: load() -> score(query,
candidate_texts). Two implementations exist, mirroring
src/retrieval/embeddings.py's EmbeddingModel pattern exactly:

- CrossEncoderReranker: the real, production-shaped path, backed by
  `sentence_transformers.CrossEncoder`. Default model identity is
  "BAAI/bge-reranker-v2-m3" (the Master Reference's named reranker
  candidate) - but the model name is fully explicit/configurable via
  RerankerConfig, never silently substituted.
- FakeReranker: a deterministic, dependency-light stand-in used ONLY by
  this project's own automated tests. It downloads nothing, needs no
  GPU/heavy-CPU inference, and is NEVER used to produce a result presented
  as real reranking quality - see its own docstring for the full safety
  rationale.

The reranker only scores/reorders candidates. It never modifies candidate
chunk text, never modifies provenance, never generates evidence, never
summarizes or rewrites chunks - it receives (query, chunk_text) pairs as
DATA and returns a float per pair, nothing else.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass

import numpy as np

from .tokenizer import tokenize

DEFAULT_RERANKER_MODEL_NAME = "BAAI/bge-reranker-v2-m3"  # [OFFICIAL SOURCE] docs/MASTER_REFERENCE_LOCK.md Section E
FAKE_RERANKER_MODEL_NAME = "fake-reranker-v1"


class RerankerLoadError(RuntimeError):
    """Raised when a reranker model fails to load (missing dependency, missing/uncached model, device error)."""


class RerankerNotLoadedError(RuntimeError):
    """Raised when score()/dimension-like properties are used before load()."""


@dataclass(frozen=True)
class RerankerConfig:
    """
    Explicit reranker configuration (docs Section L). `device` is excluded
    from `signature` for the same reason as `EmbeddingConfig.device`
    (docs/PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md Section H) - a
    runtime/hardware execution choice, not part of the reranker's logical
    identity.
    """

    model_name: str = DEFAULT_RERANKER_MODEL_NAME
    device: str = "cpu"
    batch_size: int = 32
    contract_version: str = "1.0.0"

    def __post_init__(self):
        if not isinstance(self.model_name, str) or not self.model_name.strip():
            raise ValueError(f"model_name must be a non-empty string, got {self.model_name!r}")
        if not isinstance(self.device, str) or not self.device.strip():
            raise ValueError(f"device must be a non-empty string, got {self.device!r}")
        if isinstance(self.batch_size, bool) or not isinstance(self.batch_size, int) or self.batch_size <= 0:
            raise ValueError(f"batch_size must be a positive integer, got {self.batch_size!r}")
        if not isinstance(self.contract_version, str) or not self.contract_version.strip():
            raise ValueError("contract_version must be a non-empty string")

    @property
    def signature(self) -> str:
        return f"reranker-config:v{self.contract_version}:model={self.model_name}"


class Reranker(abc.ABC):
    """
    Interface every Phase 7 reranker backend implements. `load()` must be
    called before `score()` - calling it first raises
    RerankerNotLoadedError, never a silent/partial result.
    """

    def __init__(self, config: RerankerConfig = None):
        self.config = config or RerankerConfig()
        self._loaded = False

    @abc.abstractmethod
    def load(self) -> None:
        """Load model weights/resources. Must raise RerankerLoadError on any failure."""

    @abc.abstractmethod
    def score(self, query: str, candidate_texts: list) -> np.ndarray:
        """Score `query` against each of `candidate_texts`. Returns shape (len(candidate_texts),)."""

    @property
    def model_identity(self) -> str:
        return self.config.model_name

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def _require_loaded(self) -> None:
        if not self._loaded:
            raise RerankerNotLoadedError(f"{type(self).__name__} has not been loaded - call load() before scoring")


class CrossEncoderReranker(Reranker):
    """
    Real reranker backend, backed by `sentence_transformers.CrossEncoder`.
    Default model identity: "BAAI/bge-reranker-v2-m3" (docs Section M). No
    silent model substitution: if `config.model_name` cannot be loaded
    (missing dependency, model not cached and no/failed download, invalid
    name, device error), load() raises RerankerLoadError - it never falls
    back to a different model.
    """

    def __init__(self, config: RerankerConfig = None):
        super().__init__(config)
        self._model = None

    def load(self) -> None:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RerankerLoadError(
                "the 'sentence-transformers' package is not installed - cannot load a real reranker model"
            ) from exc

        try:
            model = CrossEncoder(self.config.model_name, device=self.config.device)
        except Exception as exc:  # noqa: BLE001 - re-raised as a typed, documented error
            raise RerankerLoadError(
                f"failed to load reranker model {self.config.model_name!r} on device "
                f"{self.config.device!r}: {exc}"
            ) from exc

        self._model = model
        self._loaded = True

    def score(self, query: str, candidate_texts: list) -> np.ndarray:
        self._require_loaded()
        if not candidate_texts:
            return np.zeros((0,), dtype=np.float32)
        pairs = [(query, text) for text in candidate_texts]
        scores = self._model.predict(pairs, batch_size=self.config.batch_size, convert_to_numpy=True)
        return np.asarray(scores, dtype=np.float32)


class FakeReranker(Reranker):
    """
    Deterministic, dependency-light reranker for THIS PROJECT'S OWN TESTS
    ONLY. Never downloads anything, needs no GPU/heavy-CPU inference, and
    must never be used to produce a result presented as real
    bge-reranker-v2-m3 reranking quality (docs Section V). Its score is a
    simple, deterministic query-term-overlap count against the candidate
    text (via the same retrieval.tokenizer.tokenize used elsewhere in this
    project, so English/Devanagari/Tamil/mixed text all tokenize
    identically) - useful for testing reranker *plumbing* (batching,
    ordering, tie-breaking, score propagation, error handling) - it makes
    no claim whatsoever about real cross-encoder relevance quality.
    """

    def __init__(self, config: RerankerConfig = None):
        config = config or RerankerConfig(model_name=FAKE_RERANKER_MODEL_NAME, device="cpu")
        super().__init__(config)

    def load(self) -> None:
        self._loaded = True  # nothing to load - deterministic, in-process only

    def score(self, query: str, candidate_texts: list) -> np.ndarray:
        self._require_loaded()
        if not candidate_texts:
            return np.zeros((0,), dtype=np.float32)
        query_tokens = set(tokenize(query))
        scores = []
        for text in candidate_texts:
            text_tokens = tokenize(text)
            overlap = sum(1 for token in text_tokens if token in query_tokens)
            scores.append(float(overlap))
        return np.array(scores, dtype=np.float32)
