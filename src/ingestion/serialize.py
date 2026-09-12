"""
Deterministic JSON serialization matching config/document_structure_schema.yaml
(docs/PHASE_03_DOCUMENT_INGESTION.md Section N/O).

Wall-clock ingestion time (if the caller wants one recorded at all) is kept
strictly outside the deterministic `content` payload, in a separate
`ingestion_metadata` block, so identical input bytes + provenance always
produce byte-identical `content` JSON.
"""

from __future__ import annotations

import dataclasses
import json

from .models import ExtractedDocument


def document_to_dict(document: ExtractedDocument) -> dict:
    return dataclasses.asdict(document)


def to_json(document: ExtractedDocument, ingested_at: str = None) -> str:
    payload = {"content": document_to_dict(document)}
    if ingested_at is not None:
        payload["ingestion_metadata"] = {"ingested_at": ingested_at}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
