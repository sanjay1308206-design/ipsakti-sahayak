"""
Deterministic JSON serialization for Evidence/EvidencePack
(docs/PHASE_08_EVIDENCE_OBJECT_AND_CITATION_ARCHITECTURE.md Section W),
mirroring the src/chunking/serialize.py and src/retrieval/serialize.py
convention.

No arbitrary/executable Python object deserialization anywhere - every
payload here is plain JSON data (str/int/float/bool/list/dict). Loading
NEVER silently discards a provenance field: `*_from_dict` reconstructs
every dataclass field explicitly and raises EvidenceIntegrityError on any
missing/malformed field or any identity/hash mismatch (tampering) -
never a partial, silently-repaired object.

`Evidence.source_location` is a computed property, not a stored field, so
it is intentionally NOT duplicated into the serialized payload - it is
always trivially reconstructable from the flat fields that ARE persisted
(no redundant on-disk representation of the same data).
"""

from __future__ import annotations

import dataclasses
import json

from .models import CitationTarget, Evidence, EvidenceIntegrityError, EvidencePack, RetrievalMetadata, VersionInfo
from .validation import verify_evidence_identity, verify_evidence_text_integrity, verify_pack_integrity


def evidence_to_dict(evidence: Evidence) -> dict:
    return dataclasses.asdict(evidence)


def evidence_to_json(evidence: Evidence) -> str:
    payload = {"content": evidence_to_dict(evidence)}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def evidence_from_dict(data: dict) -> Evidence:
    """Reconstructs and integrity-verifies one Evidence object. Raises EvidenceIntegrityError on any tampering."""
    try:
        retrieval_metadata = RetrievalMetadata(**data["retrieval_metadata"])
        version_info = VersionInfo(**data["version_info"])
        evidence = Evidence(
            evidence_id=data["evidence_id"],
            evidence_schema_version=data["evidence_schema_version"],
            evidence_type=data["evidence_type"],
            evidence_text=data["evidence_text"],
            evidence_text_hash=data["evidence_text_hash"],
            chunk_id=data["chunk_id"],
            document_id=data["document_id"],
            source_family_id=data["source_family_id"],
            jurisdiction=data["jurisdiction"],
            content_hash=data["content_hash"],
            synthetic=data["synthetic"],
            page_numbers=data["page_numbers"],
            block_ids=data["block_ids"],
            retrieval_metadata=retrieval_metadata,
            version_info=version_info,
            section_heading_text=data.get("section_heading_text"),
            section_heading_level=data.get("section_heading_level"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise EvidenceIntegrityError(f"malformed evidence data: {exc}") from exc

    verify_evidence_text_integrity(evidence)
    verify_evidence_identity(evidence)
    return evidence


def evidence_pack_to_dict(pack: EvidencePack) -> dict:
    return dataclasses.asdict(pack)


def evidence_pack_to_json(pack: EvidencePack) -> str:
    payload = {"content": evidence_pack_to_dict(pack)}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def evidence_pack_from_dict(data: dict) -> EvidencePack:
    """Reconstructs and integrity-verifies a full EvidencePack. Raises EvidenceIntegrityError on any tampering."""
    try:
        evidence_items = [evidence_from_dict(item) for item in data["evidence_items"]]
        pack = EvidencePack(
            pack_id=data["pack_id"],
            schema_version=data["schema_version"],
            query=data["query"],
            evidence_items=evidence_items,
            construction_metadata=data["construction_metadata"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise EvidenceIntegrityError(f"malformed evidence pack data: {exc}") from exc

    verify_pack_integrity(pack)
    return pack


def citation_target_to_dict(citation_target: CitationTarget) -> dict:
    return dataclasses.asdict(citation_target)


def citation_target_from_dict(data: dict) -> CitationTarget:
    try:
        return CitationTarget(evidence_id=data["evidence_id"], schema_version=data["schema_version"])
    except (KeyError, TypeError, ValueError) as exc:
        raise EvidenceIntegrityError(f"malformed citation target data: {exc}") from exc
