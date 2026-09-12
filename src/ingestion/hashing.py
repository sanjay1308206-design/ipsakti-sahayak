"""
Content integrity hashing (docs/PHASE_03_DOCUMENT_INGESTION.md Section E).

The hash is an integrity/identity mechanism only - it asserts nothing
about legal authority.
"""

from __future__ import annotations

import hashlib


def compute_content_hash(data: bytes) -> str:
    """SHA-256 of the actual input bytes, lowercase hex."""
    return hashlib.sha256(data).hexdigest()


def hash_matches(data: bytes, claimed_hash: str) -> bool:
    if not claimed_hash:
        return False
    return compute_content_hash(data) == claimed_hash.strip().lower()
