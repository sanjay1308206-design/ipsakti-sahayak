"""
Deterministic JSON serialization matching config/chunk_schema.yaml
(docs/PHASE_04_LEGAL_AWARE_CHUNKING.md Section C/M), mirroring the
src/ingestion/serialize.py convention.

Wall-clock chunking time (if wanted at all) is kept strictly outside the
deterministic `content` payload, in a separate `chunking_metadata` block, so
identical Phase 3 input + identical ChunkingConfig always produce
byte-identical `content` JSON.
"""

from __future__ import annotations

import dataclasses
import json

from .models import ChunkingResult


def result_to_dict(result: ChunkingResult) -> dict:
    return dataclasses.asdict(result)


def to_json(result: ChunkingResult, chunked_at: str = None) -> str:
    payload = {"content": result_to_dict(result)}
    if chunked_at is not None:
        payload["chunking_metadata"] = {"chunked_at": chunked_at}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
