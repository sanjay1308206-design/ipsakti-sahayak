"""
Deterministic evidence/pack identity (docs/PHASE_08_EVIDENCE_OBJECT_AND_CITATION_ARCHITECTURE.md
Section H/X).

evidence_id is derived from: the evidence schema version, chunk_id,
content_hash, document_id, source_family_id, jurisdiction, block_ids, and
page_numbers - never from a FAISS/BM25 array position, a random UUID, or
anything derived from LLM output. It is a distinct, evidence-layer-scoped
identity: chunk_id remains the underlying Phase 4 retrieval identity;
evidence_id changes if the evidence schema itself changes, even when
chunk_id does not.

pack_id is derived from: the pack schema version, the query, the ordered
list of evidence IDs actually included, and the evidence-selection
config's own signature.

These are engineering identifiers/hashes only - never a cryptographic
legal signature, never a citation, never evidence of legal authority.
"""

from __future__ import annotations

import hashlib


def compute_evidence_id(
    schema_version: str,
    chunk_id: str,
    content_hash: str,
    document_id: str,
    source_family_id: str,
    jurisdiction: str,
    block_ids: list,
    page_numbers: list,
) -> str:
    canonical = "|".join(
        [
            "evidence-id-v1",
            schema_version,
            chunk_id,
            content_hash,
            document_id,
            source_family_id,
            jurisdiction,
            ",".join(block_ids),
            ",".join(str(p) for p in page_numbers),
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_pack_id(schema_version: str, query: str, evidence_ids: list, config_signature: str) -> str:
    canonical = "|".join(
        [
            "evidence-pack-v1",
            schema_version,
            query,
            ",".join(evidence_ids),
            config_signature,
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
