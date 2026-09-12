"""
Dense embedding abstraction (docs/PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md
Section I).

EmbeddingModel is a small, explicit interface: load() -> embed_documents()/
embed_query(). Two implementations exist:

- SentenceTransformerEmbeddingModel: the real, production-shaped path,
  backed by the `sentence-transformers` library. Default model identity is
  "BAAI/bge-m3" (the Master Reference's named dense-retrieval candidate -
  docs Section E) - but the model name is fully explicit/configurable via
  EmbeddingConfig, never silently substituted.
- FakeEmbeddingModel: a deterministic, dependency-light stand-in used ONLY
  by this project's own automated tests. It downloads nothing, needs no
  GPU/CPU-heavy inference, and is NEVER used to build a real production
  index - see its own docstring for the full safety rationale.

Both implementations return RAW (non-normalized) embeddings from
embed_documents()/embed_query(). Normalization (Section J) is applied
uniformly by src/retrieval/faiss_index.py via the single, shared
`l2_normalize` function below - never inside an individual model
implementation - so document and query vectors are guaranteed to go
through the exact same normalization code path.
"""

from __future__ import annotations

import abc
import hashlib
from dataclasses import dataclass

import numpy as np

from .tokenizer import tokenize

DEFAULT_MODEL_NAME = "BAAI/bge-m3"  # [OFFICIAL SOURCE] docs/MASTER_REFERENCE_LOCK.md Section E
FAKE_MODEL_NAME = "fake-embedding-v1"


class EmbeddingModelLoadError(RuntimeError):
    """Raised when an embedding model fails to load (missing dependency, missing/uncached model, device error)."""


class EmbeddingModelNotLoadedError(RuntimeError):
    """Raised when embed_documents()/embed_query()/dimension is used before load()."""


def l2_normalize(vectors: np.ndarray) -> np.ndarray:
    """
    L2-normalize rows of a 2D array (or a 1D vector). A zero vector (norm
    == 0 - e.g. an empty-text embedding) is left unchanged rather than
    producing NaN/Inf - a documented, tested edge case
    (docs/PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md Section J).
    """
    squeeze = vectors.ndim == 1
    matrix = vectors.reshape(1, -1) if squeeze else vectors
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    safe_norms = np.where(norms == 0, 1.0, norms)
    normalized = matrix / safe_norms
    return normalized[0] if squeeze else normalized


@dataclass(frozen=True)
class EmbeddingConfig:
    """
    Explicit embedding configuration (docs Section I). `device` is
    deliberately excluded from `signature` - it is a runtime/hardware
    execution choice (docs Section H), not part of the embedding model's
    logical identity; the same model+normalize policy is intended to be
    logically comparable whether it ran on CPU or GPU
    `[ASSUMPTION - not benchmarked in this repository]`.
    """

    model_name: str = DEFAULT_MODEL_NAME
    device: str = "cpu"
    normalize: bool = True
    batch_size: int = 32
    contract_version: str = "1.0.0"

    def __post_init__(self):
        if not isinstance(self.model_name, str) or not self.model_name.strip():
            raise ValueError(f"model_name must be a non-empty string, got {self.model_name!r}")
        if not isinstance(self.device, str) or not self.device.strip():
            raise ValueError(f"device must be a non-empty string, got {self.device!r}")
        if not isinstance(self.normalize, bool):
            raise ValueError(f"normalize must be a bool, got {type(self.normalize).__name__}")
        if isinstance(self.batch_size, bool) or not isinstance(self.batch_size, int) or self.batch_size <= 0:
            raise ValueError(f"batch_size must be a positive integer, got {self.batch_size!r}")
        if not isinstance(self.contract_version, str) or not self.contract_version.strip():
            raise ValueError("contract_version must be a non-empty string")

    @property
    def signature(self) -> str:
        return f"embedding-config:v{self.contract_version}:model={self.model_name}:normalize={self.normalize}"


class EmbeddingModel(abc.ABC):
    """
    Interface every Phase 6 embedding backend implements. `load()` must be
    called before `dimension`/`embed_documents`/`embed_query` - calling
    them first raises EmbeddingModelNotLoadedError, never a silent/partial
    result.
    """

    def __init__(self, config: EmbeddingConfig = None):
        self.config = config or EmbeddingConfig()
        self._loaded = False

    @abc.abstractmethod
    def load(self) -> None:
        """Load model weights/resources. Must raise EmbeddingModelLoadError on any failure."""

    @property
    @abc.abstractmethod
    def dimension(self) -> int:
        """Embedding vector dimension. Only valid after load()."""

    @abc.abstractmethod
    def embed_documents(self, texts: list) -> np.ndarray:
        """Embed a batch of document texts. Returns shape (len(texts), dimension), RAW (not normalized)."""

    @abc.abstractmethod
    def embed_query(self, text: str) -> np.ndarray:
        """Embed one query string. Returns shape (dimension,), RAW (not normalized)."""

    @property
    def model_identity(self) -> str:
        return self.config.model_name

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def _require_loaded(self) -> None:
        if not self._loaded:
            raise EmbeddingModelNotLoadedError(
                f"{type(self).__name__} has not been loaded - call load() before embedding"
            )


class SentenceTransformerEmbeddingModel(EmbeddingModel):
    """
    Real embedding backend, backed by the `sentence-transformers` library.
    Default model identity: "BAAI/bge-m3" (docs Section E). No silent
    model substitution: if `config.model_name` cannot be loaded (missing
    dependency, model not cached and no/failed download, invalid name,
    device error), load() raises EmbeddingModelLoadError - it never falls
    back to a different model.
    """

    def __init__(self, config: EmbeddingConfig = None):
        super().__init__(config)
        self._model = None
        self._dimension = None

    def load(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise EmbeddingModelLoadError(
                "the 'sentence-transformers' package is not installed - "
                "cannot load a real embedding model"
            ) from exc

        try:
            model = SentenceTransformer(self.config.model_name, device=self.config.device)
        except Exception as exc:  # noqa: BLE001 - re-raised as a typed, documented error
            raise EmbeddingModelLoadError(
                f"failed to load embedding model {self.config.model_name!r} on device "
                f"{self.config.device!r}: {exc}"
            ) from exc

        self._model = model
        # sentence-transformers renamed get_sentence_embedding_dimension() to
        # get_embedding_dimension() - support both so this works across the
        # pinned version range without a deprecation warning on newer ones.
        if hasattr(model, "get_embedding_dimension"):
            self._dimension = int(model.get_embedding_dimension())
        else:
            self._dimension = int(model.get_sentence_embedding_dimension())
        self._loaded = True

    @property
    def dimension(self) -> int:
        self._require_loaded()
        return self._dimension

    def embed_documents(self, texts: list) -> np.ndarray:
        self._require_loaded()
        if not texts:
            return np.zeros((0, self._dimension), dtype=np.float32)
        embeddings = self._model.encode(
            list(texts),
            batch_size=self.config.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=False,  # normalization is applied uniformly by faiss_index.py
        )
        return np.asarray(embeddings, dtype=np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        self._require_loaded()
        embedding = self._model.encode(
            [text], convert_to_numpy=True, normalize_embeddings=False
        )[0]
        return np.asarray(embedding, dtype=np.float32)


class FakeEmbeddingModel(EmbeddingModel):
    """
    Deterministic, dependency-light embedding model for THIS PROJECT'S OWN
    TESTS ONLY. Never downloads anything, needs no GPU/heavy CPU inference,
    and must never be used to build an index presented as real semantic
    retrieval quality (docs/PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md
    Section Q). It is a hash-seeded bag-of-tokens vector: each token
    (via the same retrieval.tokenizer.tokenize used by Phase 5, so
    English/Devanagari/Tamil/mixed text all tokenize identically) is mapped
    to a fixed pseudo-random unit-scale vector via a SHA-256-seeded RNG,
    and a text's embedding is the sum of its tokens' vectors. This gives
    deterministic, token-overlap-sensitive similarity behavior useful for
    testing dense-retrieval *plumbing* (ranking, provenance, determinism) -
    it makes no claim whatsoever about real semantic embedding quality.
    """

    def __init__(self, config: EmbeddingConfig = None, dimension: int = 16):
        config = config or EmbeddingConfig(model_name=FAKE_MODEL_NAME, device="cpu", normalize=True)
        super().__init__(config)
        if not isinstance(dimension, int) or isinstance(dimension, bool) or dimension <= 0:
            raise ValueError(f"dimension must be a positive integer, got {dimension!r}")
        self._dimension = dimension

    def load(self) -> None:
        self._loaded = True  # nothing to load - deterministic, in-process only

    @property
    def dimension(self) -> int:
        self._require_loaded()
        return self._dimension

    def _embed_one(self, text: str) -> np.ndarray:
        vector = np.zeros(self._dimension, dtype=np.float32)
        for token in tokenize(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            seed = int.from_bytes(digest[:8], "big")
            rng = np.random.default_rng(seed)
            vector += rng.standard_normal(self._dimension).astype(np.float32)
        return vector

    def embed_documents(self, texts: list) -> np.ndarray:
        self._require_loaded()
        if not texts:
            return np.zeros((0, self._dimension), dtype=np.float32)
        return np.stack([self._embed_one(t) for t in texts]).astype(np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        self._require_loaded()
        return self._embed_one(text)
