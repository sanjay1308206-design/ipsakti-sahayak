"""
Phase 21 backup/restore data shapes
(docs/PHASE_21_OBSERVABILITY_BACKUP_CORPUS_REFRESH.md Sections 12-16,
config/phase_21_observability.yaml `backup`).

`[ASSUMPTION]` (docs Section 12): the Phase 21 backup target is a
filesystem corpus/index SNAPSHOT, never a database backup - no database,
ORM, or persistence layer exists anywhere in this repository (Phase 17
Section W, unchanged), and inventing one here would violate Rule 6 (No
Premature Dependencies).

Every dataclass here is a plain data holder only - no filesystem I/O, no
hashing, no admission/extraction/chunking/indexing logic (that lives in
`backup.py`, and is otherwise entirely reused, never reimplemented, from
`ingestion`/`chunking`/`retrieval`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ingestion.models import ExtractedDocument

BACKUP_SCHEMA_VERSION = "1.0.0"

# docs Section 13: "admitted documents + chunk set + retrieval index
# artifacts (Phase 5/6, whichever exist)" - never an arbitrary artifact
# added merely because something else exists in the repository.
ARTIFACT_TYPES = frozenset(
    {
        "DOCUMENT",
        "CHUNK_SET",
        "BM25_INDEX",
        "DENSE_INDEX_METADATA",
        "DENSE_INDEX_FAISS",
    }
)

# docs Section 13: the specific corpus_provenance_schema.yaml fields a
# backup's provenance record must carry - reused as a presence check
# only (the schema itself remains Phase 2's own, never re-validated in
# full here).
REQUIRED_PROVENANCE_FIELDS = (
    "document_id",
    "source_family_id",
    "content_hash",
    "provenance_status",
    "validation_status",
    "synthetic",
)


class SnapshotError(Exception):
    """Base class for every Phase 21 backup/restore failure."""


class SnapshotSchemaError(SnapshotError):
    """A snapshot's manifest, or one of its artifact files, is malformed or missing required structure."""


class SnapshotIntegrityError(SnapshotError):
    """A snapshot failed integrity verification - hash mismatch, missing/unexpected artifact, or an unsafe path."""


def _check_non_empty_string(name: str, value) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _check_non_negative_int(name: str, value) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer, got {value!r}")


@dataclass(frozen=True)
class AdmittedDocument:
    """
    Pairs one Phase 2 provenance record with the Phase 3 extraction result
    it produced - the two pieces of already-real output docs Section 13
    asks a backup to package together. Neither is derived from the other;
    both must be supplied by the caller exactly as Phase 2/3 already
    produced them - this dataclass only cross-checks their consistency.
    """

    provenance: dict
    extracted_document: ExtractedDocument

    def __post_init__(self):
        if not isinstance(self.provenance, dict):
            raise ValueError("provenance must be a dict")
        if not isinstance(self.extracted_document, ExtractedDocument):
            raise ValueError("extracted_document must be an ingestion.models.ExtractedDocument")
        missing = [k for k in REQUIRED_PROVENANCE_FIELDS if k not in self.provenance]
        if missing:
            raise ValueError(f"provenance is missing required fields (config/corpus_provenance_schema.yaml): {missing}")
        if str(self.provenance["document_id"]) != self.extracted_document.document_id:
            raise ValueError("provenance.document_id does not match extracted_document.document_id")
        if str(self.provenance["source_family_id"]) != self.extracted_document.source_family_id:
            raise ValueError("provenance.source_family_id does not match extracted_document.source_family_id")
        if bool(self.provenance["synthetic"]) != self.extracted_document.synthetic:
            raise ValueError("provenance.synthetic does not match extracted_document.synthetic")


@dataclass(frozen=True)
class ArtifactRecord:
    """
    One file inside a snapshot. `relative_path` is always POSIX-style
    (forward slashes) and relative - never absolute, never containing a
    `..` component - validated structurally here; actual filesystem-escape
    protection happens where the path is resolved against a real root
    (`backup._safe_join`), since a hostile value can only be detected by
    resolving it, not by shape alone.
    """

    relative_path: str
    artifact_type: str
    content_hash: str
    size_bytes: int

    def __post_init__(self):
        _check_non_empty_string("relative_path", self.relative_path)
        if self.artifact_type not in ARTIFACT_TYPES:
            raise ValueError(f"artifact_type must be one of {sorted(ARTIFACT_TYPES)}, got {self.artifact_type!r}")
        _check_non_empty_string("content_hash", self.content_hash)
        _check_non_negative_int("size_bytes", self.size_bytes)


@dataclass(frozen=True)
class SnapshotManifest:
    """The top-level, deterministic manifest for one Phase 21 corpus/index snapshot (docs Section 13/14)."""

    schema_version: str
    snapshot_id: str
    corpus_lock_version: str
    artifacts: list  # list[ArtifactRecord]
    manifest_hash: str

    def __post_init__(self):
        _check_non_empty_string("schema_version", self.schema_version)
        _check_non_empty_string("snapshot_id", self.snapshot_id)
        _check_non_empty_string("corpus_lock_version", self.corpus_lock_version)
        if not isinstance(self.artifacts, list) or any(not isinstance(a, ArtifactRecord) for a in self.artifacts):
            raise ValueError("artifacts must be a list of ArtifactRecord")
        paths = [a.relative_path for a in self.artifacts]
        if len(paths) != len(set(paths)):
            raise ValueError("artifacts must not contain duplicate relative_path values")
        _check_non_empty_string("manifest_hash", self.manifest_hash)


@dataclass(frozen=True)
class RestoreResult:
    """
    The result of a SUCCESSFUL restore (docs Section 15/16).
    `backup.restore_snapshot` raises `SnapshotError` on any failure
    instead of returning a partial result, so an instance of this
    dataclass is only ever produced for a fully verified restore
    (fail-closed, docs Section 22).

    `documents`/`chunking_results` are the verified, already-canonical
    dict payloads `ingestion.serialize.document_to_dict`/
    `chunking.serialize.result_to_dict` themselves produce - Phase 3/4
    provide a one-way `to_json`/`*_to_dict` SERIALIZER only, no
    dict-to-dataclass loader, so restoring to that same verified dict
    shape is the honest boundary: never a second, independently-invented
    ExtractedDocument/ChunkingResult deserializer (docs Section 15,
    `[ASSUMPTION]`, see `backup.py` module docstring).

    `bm25_index`/`dense_index` ARE reconstructed as real
    `retrieval.models.Bm25Index`/`DenseIndex` objects, since Phase 6
    already provides `retrieval.serialize.load_dense_index` (reused
    verbatim) and `Bm25Index`'s own shape is a single flat dataclass +
    one nested config, mirroring `load_dense_index`'s own "rebuild a
    nested dataclass from its own dict shape" pattern rather than adding
    a new one.
    """

    manifest: SnapshotManifest
    restored_dir: str
    documents: list  # list[dict]
    chunking_results: list  # list[dict]
    bm25_index: Optional[object]
    dense_index: Optional[object]
