"""
Deterministic chunk identity (docs/PHASE_04_LEGAL_AWARE_CHUNKING.md Section D/Section 7).

chunk_id is derived by hashing canonical identity fields - never a random
UUID, timestamp, or process/machine state. Identical document_id +
content_hash + chunking config + contributing block_ids + split_index
always produces the same chunk_id.

This hash is an engineering identity/deduplication mechanism only. It
asserts nothing about legal authority and must never be presented as a
citation (Phase 8 owns citation architecture).
"""

from __future__ import annotations

import hashlib


def compute_chunk_id(
    document_id: str,
    content_hash: str,
    config_signature: str,
    block_ids: list,
    split_index: int,
) -> str:
    canonical = "|".join(
        [
            "chunk-id-v1",
            document_id,
            content_hash,
            config_signature,
            ",".join(block_ids),
            str(split_index),
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
