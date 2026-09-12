"""
Deterministic JSON serialization for Phase 5 (Bm25Index/RetrievalResponse,
docs/PHASE_05_BM25_BASELINE.md Section 23), Phase 6 (DenseIndex/
DenseRetrievalResponse, docs/PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md
Section T), and Phase 7 (RrfResponse/HybridRetrievalResponse,
docs/PHASE_07_HYBRID_FUSION_AND_RERANKING.md), mirroring the
src/chunking/serialize.py convention.

No arbitrary/executable Python object deserialization anywhere - every
JSON payload here is plain data (str/int/float/list/dict); reading it back
never reconstructs a live index or executes code. The one exception is the
FAISS index's own binary file (Phase 6 only), which uses FAISS's native,
documented (de)serialization (faiss.write_index/faiss.read_index) - never
Python `pickle` or another generic/unsafe deserializer. Phase 7 introduces
no new persistence of its own (docs Section T of PHASE_07) - RRF/reranking
results are ephemeral computations over already-persisted Phase 5/6
indexes, so only JSON serialization (for determinism testing/inspection)
is provided here, not a save/load pair.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import faiss

from .embeddings import EmbeddingConfig
from .models import (
    Bm25Index,
    DenseIndex,
    DenseIndexCompatibilityError,
    DenseIndexConfig,
    DenseRetrievalResponse,
    HybridRetrievalResponse,
    RetrievalResponse,
    RrfResponse,
)


def index_to_dict(index: Bm25Index) -> dict:
    return dataclasses.asdict(index)


def index_to_json(index: Bm25Index) -> str:
    payload = {"content": index_to_dict(index)}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def response_to_dict(response: RetrievalResponse) -> dict:
    return dataclasses.asdict(response)


def response_to_json(response: RetrievalResponse, retrieved_at: str = None) -> str:
    payload = {"content": response_to_dict(response)}
    if retrieved_at is not None:
        payload["retrieval_metadata"] = {"retrieved_at": retrieved_at}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Phase 6 - dense index metadata + FAISS binary persistence
# ---------------------------------------------------------------------------


def dense_index_metadata_to_dict(index: DenseIndex) -> dict:
    """Everything about a DenseIndex EXCEPT the opaque `faiss_index` object itself."""
    return {
        "embedding_config": dataclasses.asdict(index.embedding_config),
        "dense_index_config": dataclasses.asdict(index.dense_index_config),
        "model_identity": index.model_identity,
        "dimension": index.dimension,
        "chunk_count": index.chunk_count,
        "chunk_ids": index.chunk_ids,
        "chunk_provenance": index.chunk_provenance,
        "signature": index.signature,
    }


def dense_index_metadata_to_json(index: DenseIndex) -> str:
    payload = {"content": dense_index_metadata_to_dict(index)}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def dense_response_to_dict(response: DenseRetrievalResponse) -> dict:
    return dataclasses.asdict(response)


def dense_response_to_json(response: DenseRetrievalResponse, retrieved_at: str = None) -> str:
    payload = {"content": dense_response_to_dict(response)}
    if retrieved_at is not None:
        payload["retrieval_metadata"] = {"retrieved_at": retrieved_at}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def save_dense_index(index: DenseIndex, faiss_path, metadata_path) -> None:
    """
    Persist a DenseIndex as two files: FAISS's own native binary format for
    the vectors (`faiss_path`) and a deterministic JSON sidecar for
    everything else (`metadata_path`). Never a single pickled blob.
    """
    faiss.write_index(index.faiss_index, str(faiss_path))
    Path(metadata_path).write_text(dense_index_metadata_to_json(index), encoding="utf-8")


def load_dense_index(faiss_path, metadata_path) -> DenseIndex:
    """
    Load a persisted DenseIndex, failing safely (DenseIndexCompatibilityError
    or FileNotFoundError) on any missing file, corrupted content, or
    internal inconsistency - never silently producing a usable-looking but
    misleading index (docs Section T).
    """
    faiss_path = Path(faiss_path)
    metadata_path = Path(metadata_path)

    if not faiss_path.is_file():
        raise FileNotFoundError(f"FAISS index file not found: {faiss_path}")
    if not metadata_path.is_file():
        raise FileNotFoundError(f"dense index metadata file not found: {metadata_path}")

    try:
        raw = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata = raw["content"]
    except (json.JSONDecodeError, KeyError, UnicodeDecodeError) as exc:
        raise DenseIndexCompatibilityError(f"corrupted dense index metadata file: {metadata_path}") from exc

    try:
        faiss_index = faiss.read_index(str(faiss_path))
    except Exception as exc:  # noqa: BLE001 - re-raised as a typed, documented error
        raise DenseIndexCompatibilityError(f"corrupted or unreadable FAISS index file: {faiss_path}") from exc

    required_keys = (
        "embedding_config",
        "dense_index_config",
        "model_identity",
        "dimension",
        "chunk_count",
        "chunk_ids",
        "chunk_provenance",
        "signature",
    )
    missing = [k for k in required_keys if k not in metadata]
    if missing:
        raise DenseIndexCompatibilityError(f"dense index metadata is missing required keys: {missing}")

    try:
        embedding_config = EmbeddingConfig(**metadata["embedding_config"])
        dense_index_config = DenseIndexConfig(**metadata["dense_index_config"])
    except (TypeError, ValueError) as exc:
        raise DenseIndexCompatibilityError(f"dense index metadata config is invalid: {exc}") from exc

    dimension = metadata["dimension"]
    if faiss_index.d != dimension:
        raise DenseIndexCompatibilityError(
            f"FAISS index dimension {faiss_index.d} does not match metadata dimension {dimension}"
        )
    if faiss_index.ntotal != metadata["chunk_count"]:
        raise DenseIndexCompatibilityError(
            f"FAISS index vector count {faiss_index.ntotal} does not match "
            f"metadata chunk_count {metadata['chunk_count']}"
        )

    index = DenseIndex(
        embedding_config=embedding_config,
        dense_index_config=dense_index_config,
        model_identity=metadata["model_identity"],
        dimension=dimension,
        chunk_count=metadata["chunk_count"],
        chunk_ids=metadata["chunk_ids"],
        chunk_provenance=metadata["chunk_provenance"],
        signature=metadata["signature"],
        faiss_index=faiss_index,
    )

    from .identity import compute_dense_index_signature

    recomputed_signature = compute_dense_index_signature(
        model_identity=index.model_identity,
        dimension=index.dimension,
        normalize=embedding_config.normalize,
        dense_index_config_signature=dense_index_config.signature,
        chunk_ids=index.chunk_ids,
        content_hashes=[p["content_hash"] for p in index.chunk_provenance],
    )
    if recomputed_signature != index.signature:
        raise DenseIndexCompatibilityError(
            "stored signature does not match the signature recomputed from loaded metadata - "
            "the metadata file may be corrupted or hand-edited"
        )

    return index


# ---------------------------------------------------------------------------
# Phase 7 - RRF / hybrid result serialization (no index persistence - see
# module docstring)
# ---------------------------------------------------------------------------


def rrf_response_to_dict(response: RrfResponse) -> dict:
    return dataclasses.asdict(response)


def rrf_response_to_json(response: RrfResponse) -> str:
    payload = {"content": rrf_response_to_dict(response)}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def hybrid_response_to_dict(response: HybridRetrievalResponse) -> dict:
    return dataclasses.asdict(response)


def hybrid_response_to_json(response: HybridRetrievalResponse, retrieved_at: str = None) -> str:
    payload = {"content": hybrid_response_to_dict(response)}
    if retrieved_at is not None:
        payload["retrieval_metadata"] = {"retrieved_at": retrieved_at}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
