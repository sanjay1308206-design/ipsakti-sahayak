"""
FAISS dense index build/query orchestration
(docs/PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md Sections K, L, M, N).

build_dense_index(): the only way to construct a DenseIndex. Consumes a
list of real chunking.models.Chunk objects (the actual in-memory Phase 4
output) and a loaded EmbeddingModel - never a serialized JSON dict, never
raw text passed directly.

dense_query(): the only way to retrieve. Never mutates the index; running
it repeatedly against the same index/embedding_model/query is guaranteed
to produce identical DenseRetrievalResponse objects (docs Section M).

Never downloads anything. Never reranks. Never fuses with BM25 (Phase 7).
Never generates.
"""

from __future__ import annotations

import faiss
import numpy as np

from chunking.models import Chunk

from .embeddings import EmbeddingModel, l2_normalize
from .identity import compute_dense_index_signature
from .models import DenseIndex, DenseIndexConfig, DenseRetrievalResponse, DenseRetrievalResult


def _validate_chunks(chunks: list) -> None:
    if not isinstance(chunks, list):
        raise TypeError(f"build_dense_index expects a list of Chunk objects, got {type(chunks).__name__}")
    for chunk in chunks:
        if not isinstance(chunk, Chunk):
            raise TypeError(f"build_dense_index expects chunking.models.Chunk objects, got {type(chunk).__name__}")


def _validate_embedding_matrix(vectors: np.ndarray, expected_rows: int, expected_dimension: int, source: str) -> np.ndarray:
    vectors = np.asarray(vectors, dtype=np.float32)
    if vectors.ndim != 2 or vectors.shape != (expected_rows, expected_dimension):
        raise ValueError(
            f"{source} returned an array of shape {vectors.shape}, expected ({expected_rows}, {expected_dimension})"
        )
    if not np.isfinite(vectors).all():
        raise ValueError(f"{source} produced non-finite (NaN/Inf) values")
    return vectors


def build_dense_index(
    chunks: list,
    embedding_model: EmbeddingModel,
    dense_index_config: DenseIndexConfig = None,
) -> DenseIndex:
    _validate_chunks(chunks)
    if not isinstance(embedding_model, EmbeddingModel):
        raise TypeError(f"build_dense_index expects an EmbeddingModel, got {type(embedding_model).__name__}")
    if not embedding_model.is_loaded:
        raise RuntimeError("embedding_model must be loaded (call embedding_model.load()) before build_dense_index")
    if dense_index_config is None:
        dense_index_config = DenseIndexConfig()

    chunk_ids = [c.chunk_id for c in chunks]
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("build_dense_index requires unique chunk_id values - found a duplicate")

    dimension = embedding_model.dimension
    faiss_index = faiss.IndexFlatIP(dimension)
    chunk_provenance = []

    if chunks:
        texts = [c.text for c in chunks]
        raw_vectors = embedding_model.embed_documents(texts)
        raw_vectors = _validate_embedding_matrix(raw_vectors, len(chunks), dimension, "embed_documents")
        vectors = l2_normalize(raw_vectors) if embedding_model.config.normalize else raw_vectors
        faiss_index.add(np.ascontiguousarray(vectors, dtype=np.float32))
        chunk_provenance = [
            {
                "document_id": c.document_id,
                "source_family_id": c.source_family_id,
                "jurisdiction": c.jurisdiction,
                "content_hash": c.content_hash,
                "synthetic": c.synthetic,
                "page_numbers": list(c.page_numbers),
                "block_ids": list(c.block_ids),
                "text": c.text,
            }
            for c in chunks
        ]

    signature = compute_dense_index_signature(
        model_identity=embedding_model.model_identity,
        dimension=dimension,
        normalize=embedding_model.config.normalize,
        dense_index_config_signature=dense_index_config.signature,
        chunk_ids=chunk_ids,
        content_hashes=[c.content_hash for c in chunks],
    )

    return DenseIndex(
        embedding_config=embedding_model.config,
        dense_index_config=dense_index_config,
        model_identity=embedding_model.model_identity,
        dimension=dimension,
        chunk_count=len(chunks),
        chunk_ids=chunk_ids,
        chunk_provenance=chunk_provenance,
        signature=signature,
        faiss_index=faiss_index,
    )


def dense_query(
    index: DenseIndex,
    embedding_model: EmbeddingModel,
    query_text: str,
    top_k: int,
) -> DenseRetrievalResponse:
    if not isinstance(index, DenseIndex):
        raise TypeError(f"dense_query expects a retrieval.models.DenseIndex, got {type(index).__name__}")
    if not isinstance(embedding_model, EmbeddingModel):
        raise TypeError(f"dense_query expects an EmbeddingModel, got {type(embedding_model).__name__}")
    if not embedding_model.is_loaded:
        raise RuntimeError("embedding_model must be loaded (call embedding_model.load()) before dense_query")
    if not isinstance(query_text, str):
        raise TypeError(f"dense_query expects query_text to be str, got {type(query_text).__name__}")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
        raise ValueError(f"top_k must be a positive integer, got {top_k!r}")

    # Reject querying an index with an incompatible embedding model/config -
    # matching vector dimension by coincidence would otherwise produce
    # meaningless similarity scores (docs Section H/security).
    if embedding_model.model_identity != index.model_identity:
        raise ValueError(
            f"embedding_model identity {embedding_model.model_identity!r} does not match "
            f"the index's model identity {index.model_identity!r} - refusing to query with "
            f"an incompatible embedding model"
        )
    if embedding_model.dimension != index.dimension:
        raise ValueError(
            f"embedding_model dimension {embedding_model.dimension} does not match "
            f"the index's dimension {index.dimension}"
        )

    if index.chunk_count == 0:
        return DenseRetrievalResponse(
            query=query_text,
            top_k=top_k,
            index_signature=index.signature,
            model_identity=index.model_identity,
            results=[],
        )

    raw_query_vector = embedding_model.embed_query(query_text)
    raw_query_vector = _validate_embedding_matrix(
        np.asarray(raw_query_vector, dtype=np.float32).reshape(1, -1), 1, index.dimension, "embed_query"
    )
    query_vector = l2_normalize(raw_query_vector) if index.embedding_config.normalize else raw_query_vector

    k = min(top_k, index.chunk_count)
    scores, positions = index.faiss_index.search(np.ascontiguousarray(query_vector, dtype=np.float32), k)

    candidates = []
    for position, score in zip(positions[0], scores[0]):
        if position < 0:  # FAISS pads with -1 if it cannot fill k results (should not happen given k <= ntotal)
            continue
        candidates.append((float(score), index.chunk_ids[int(position)], int(position)))

    # Deterministic tie-break (docs Section N), matching Phase 5's rule:
    # descending score, then ascending chunk_id - never FAISS's raw
    # implementation-defined tie order.
    candidates.sort(key=lambda item: (-item[0], item[1]))

    results = []
    for rank, (score, chunk_id, position) in enumerate(candidates, start=1):
        prov = index.chunk_provenance[position]
        results.append(
            DenseRetrievalResult(
                rank=rank,
                chunk_id=chunk_id,
                score=score,
                model_identity=index.model_identity,
                document_id=prov["document_id"],
                source_family_id=prov["source_family_id"],
                jurisdiction=prov["jurisdiction"],
                content_hash=prov["content_hash"],
                synthetic=prov["synthetic"],
                page_numbers=prov["page_numbers"],
                block_ids=prov["block_ids"],
                chunk_text=prov["text"],
            )
        )

    return DenseRetrievalResponse(
        query=query_text,
        top_k=top_k,
        index_signature=index.signature,
        model_identity=index.model_identity,
        results=results,
    )
