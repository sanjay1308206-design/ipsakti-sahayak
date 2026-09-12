"""
Deterministic index identity for Phase 5 (BM25) and Phase 6 (dense/FAISS)
(docs/PHASE_05_BM25_BASELINE.md Section N/24, docs/PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md
Section M).

An index signature changes whenever anything that affects scoring or
ranking changes: algorithm parameters, tokenizer/embedding-model identity,
or the exact set of indexed chunks (identity + content). It is a
build/version identifier for the *retrieval index* - never a legal
citation, never a regulatory document version.
"""

from __future__ import annotations

import hashlib


def compute_index_signature(config_signature: str, chunk_ids: list, content_hashes: list) -> str:
    """Phase 5 (BM25) index signature."""
    canonical = "|".join(
        [
            "bm25-index-v1",
            config_signature,
            ",".join(chunk_ids),
            ",".join(content_hashes),
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_dense_index_signature(
    model_identity: str,
    dimension: int,
    normalize: bool,
    dense_index_config_signature: str,
    chunk_ids: list,
    content_hashes: list,
) -> str:
    """
    Phase 6 (dense/FAISS) index signature. Changes if the embedding model
    identity, dimension, normalization policy, FAISS index configuration,
    or the exact indexed chunk set (identity + content) changes.
    `device` (CPU/GPU) is deliberately excluded - see
    retrieval.embeddings.EmbeddingConfig.signature for why.
    """
    canonical = "|".join(
        [
            "dense-index-v1",
            model_identity,
            str(dimension),
            str(normalize),
            dense_index_config_signature,
            ",".join(chunk_ids),
            ",".join(content_hashes),
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
