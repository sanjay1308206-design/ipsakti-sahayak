"""
Phase 21 backup/restore: corpus/index snapshot creation and safe restore
(docs/PHASE_21_OBSERVABILITY_BACKUP_CORPUS_REFRESH.md Sections 12-16,
config/phase_21_observability.yaml `backup`).

`[ENGINEERING RECOMMENDATION]` This module is an AGGREGATION/PACKAGING
layer only, mirroring `observability.metrics`'s own "accepts already-real
objects, never builds its own" convention. It never re-implements:

- admission/extraction (`ingestion.pipeline.ingest_bytes`/`ingest_document`,
  Phase 3) - a caller supplies already-ingested `ExtractedDocument`s;
- chunking (`chunking.chunker.chunk_document`, Phase 4) - a caller
  supplies already-built `ChunkingResult`s;
- BM25/dense index building (`retrieval.index.build_index`/
  `retrieval.faiss_index.build_dense_index`, Phase 5/6) - a caller
  supplies an already-built `Bm25Index`/`DenseIndex`;
- any serialization shape - every artifact is written using the SAME
  deterministic serializer its own owning phase already provides
  (`ingestion.serialize.document_to_dict`, `chunking.serialize.result_to_dict`,
  `retrieval.serialize.index_to_dict`, `retrieval.serialize.save_dense_index`/
  `load_dense_index`) - never a second, competing serialization format.

`[ASSUMPTION]` (docs Section 15, restated): Phase 3/4 provide a one-way
dict/JSON SERIALIZER for `ExtractedDocument`/`ChunkingResult` but no
dict-to-dataclass LOADER. Rather than inventing one here (which would be
exactly the "second, parallel deserialization path" docs Section 15
forbids), `restore_snapshot` returns those two artifact kinds as their
already-verified canonical dict payload - the identical shape
`document_to_dict`/`result_to_dict` produce - never a reconstructed
frozen dataclass instance. `Bm25Index` (a single flat dataclass plus one
nested config) IS reconstructed, mirroring `retrieval.serialize.
load_dense_index`'s own established "rebuild a nested dataclass from its
own dict shape" pattern; `DenseIndex`/FAISS restoration calls that real,
existing loader unmodified - the one artifact kind Phase 6 already knows
how to load.

SNAPSHOT FORMAT: a plain directory tree (`[ENGINEERING RECOMMENDATION]`,
docs Section 15 "prefer a simple deterministic filesystem snapshot
representation... unless the contract explicitly requires" an archive
format - it does not) - `manifest.json` at the root, plus
`documents/<document_id>.json`, `chunks/<document_id>.json`,
`bm25_index.json`, and `dense_index.faiss`/`dense_index_metadata.json`
when present. No tar/zip archive is used, so classic archive-extraction
path attacks (e.g. "zip slip") do not apply directly - the equivalent
risk here is a manifest that names an escaping or symlinked path, which
`_safe_join` and the symlink checks below defend against on every read.

SECURITY: every path recorded in a manifest is treated as UNTRUSTED input
when a snapshot is verified or restored (docs Section 26) - it is never
trusted merely because it came from "our own" `manifest.json`, since a
tampered or hand-edited manifest is exactly the failure mode integrity
verification exists to catch.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import asdict
from pathlib import Path, PurePosixPath
from typing import Optional

from chunking.models import ChunkingResult
from chunking.serialize import result_to_dict as chunk_result_to_dict
from ingestion.serialize import document_to_dict
from observability.logging import redact_metadata
from retrieval.identity import compute_index_signature
from retrieval.models import Bm25Config, Bm25Index, DenseIndex
from retrieval.serialize import index_to_dict as bm25_index_to_dict
from retrieval.serialize import load_dense_index, save_dense_index

from .backup_models import (
    BACKUP_SCHEMA_VERSION,
    AdmittedDocument,
    ArtifactRecord,
    RestoreResult,
    SnapshotError,
    SnapshotIntegrityError,
    SnapshotManifest,
    SnapshotSchemaError,
)

# [ENGINEERING RECOMMENDATION] a conservative allow-list for any value used
# as a filename component (document_id) - rejects anything that could not
# possibly be a safe path segment, before it is ever joined onto a real
# filesystem path.
import re

_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

_MANIFEST_FILENAME = "manifest.json"


def _check_non_empty_string(name: str, value) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _sanitize_id_component(name: str, value: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID_PATTERN.match(value):
        raise ValueError(f"{name} must match {_SAFE_ID_PATTERN.pattern!r} to be used as a snapshot filename, got {value!r}")
    return value


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json_artifact(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _require_empty_dir(target_dir: Path, purpose: str) -> None:
    """
    Refuses to write into a directory that already contains something -
    the ONLY way this module guarantees it "never silently overwrites
    unrelated files" (docs restore requirement 7). Creating a brand-new,
    currently-empty-or-absent directory is always safe; anything else is
    the caller's own data and is left untouched.
    """
    if target_dir.exists():
        if not target_dir.is_dir():
            raise SnapshotError(f"{purpose} path exists and is not a directory: {target_dir}")
        if any(target_dir.iterdir()):
            raise SnapshotError(f"{purpose} directory already exists and is not empty, refusing to overwrite: {target_dir}")
    target_dir.mkdir(parents=True, exist_ok=True)


def _safe_join(root: Path, relative_path: str) -> Path:
    """
    Resolves `relative_path` against `root`, rejecting anything that is
    not a plain, contained, non-symlinked path - the untrusted-manifest
    counterpart of `ingestion.pipeline.ingest_document`'s own
    resolve-then-`relative_to` path-traversal guard (docs Section 26,
    reused pattern, never a second competing one).

    Rejects: absolute POSIX paths, drive-letter/UNC-style paths, any `..`
    or empty/`.` path component, backslash-separated paths (Windows
    traversal spelled with `\\`), and any path that resolves outside
    `root` once symlinks are followed.
    """
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise SnapshotIntegrityError("artifact relative_path must be a non-empty string")
    if "\\" in relative_path or re.match(r"^[A-Za-z]:", relative_path):
        raise SnapshotIntegrityError(f"unsafe artifact path rejected: {relative_path!r}")

    candidate = PurePosixPath(relative_path)
    if candidate.is_absolute() or any(part in ("", ".", "..") for part in candidate.parts):
        raise SnapshotIntegrityError(f"unsafe artifact path rejected: {relative_path!r}")

    root = Path(root).resolve()
    try:
        resolved = (root / relative_path).resolve()
    except (OSError, RuntimeError) as exc:
        raise SnapshotIntegrityError(f"unresolvable artifact path: {relative_path!r}") from exc
    try:
        resolved.relative_to(root)
    except ValueError:
        raise SnapshotIntegrityError(f"artifact path escapes snapshot root: {relative_path!r}")
    return resolved


def _reject_symlink(root: Path, relative_path: str) -> None:
    """Defense in depth alongside `_safe_join`: refuses to treat ANY symlinked artifact path as safe, even one that (if followed) would stay inside `root`."""
    candidate = root / relative_path
    if candidate.is_symlink():
        raise SnapshotIntegrityError(f"artifact path is a symlink, refusing to follow it: {relative_path!r}")


# ---------------------------------------------------------------------------
# Snapshot creation
# ---------------------------------------------------------------------------


def create_snapshot(
    target_dir,
    *,
    documents: list,
    chunking_results: Optional[list] = None,
    bm25_index: Optional[Bm25Index] = None,
    dense_index: Optional[DenseIndex] = None,
    corpus_lock_version: str,
    created_at: Optional[str] = None,
) -> SnapshotManifest:
    """
    Writes one versioned, content-hashed corpus/index snapshot into
    `target_dir` (docs Section 12/13) from already-real Phase 3/4/5/6
    output the caller supplies - never builds any of it itself.

    `target_dir` must not already exist as a non-empty directory (docs
    "never silently overwrite unrelated files"). `corpus_lock_version`
    must be the `config/corpus_lock.yaml` `lock_version` in effect at
    capture time (docs Section 13) - passed explicitly by the caller,
    never read from disk here (this module does not own corpus_lock.yaml).

    `created_at`, if given, is recorded in a separate, non-hashed
    `manifest_metadata` block (mirroring the `chunking_metadata`/
    `ingestion_metadata` convention already used by
    `chunking.serialize`/`ingestion.serialize`) - wall-clock capture time
    is real operational metadata, but it is never part of the
    deterministic `snapshot_id`/`manifest_hash` identity (docs Section 21).
    """
    target_dir = Path(target_dir)
    _require_empty_dir(target_dir, "snapshot target")

    if not isinstance(documents, list) or any(not isinstance(d, AdmittedDocument) for d in documents):
        raise TypeError("documents must be a list of AdmittedDocument")
    chunking_results = list(chunking_results) if chunking_results is not None else []
    for cr in chunking_results:
        if not isinstance(cr, ChunkingResult):
            raise TypeError(f"chunking_results items must be chunking.models.ChunkingResult, got {type(cr).__name__}")
    if bm25_index is not None and not isinstance(bm25_index, Bm25Index):
        raise TypeError("bm25_index must be a retrieval.models.Bm25Index or None")
    if dense_index is not None and not isinstance(dense_index, DenseIndex):
        raise TypeError("dense_index must be a retrieval.models.DenseIndex or None")
    _check_non_empty_string("corpus_lock_version", corpus_lock_version)

    document_ids = [ad.extracted_document.document_id for ad in documents]
    if len(document_ids) != len(set(document_ids)):
        raise ValueError("documents must not contain duplicate document_id values")
    chunk_result_ids = [cr.document_id for cr in chunking_results]
    if len(chunk_result_ids) != len(set(chunk_result_ids)):
        raise ValueError("chunking_results must not contain duplicate document_id values")

    artifacts: list = []
    identity_parts = ["corpus-snapshot-v1", corpus_lock_version]

    for admitted in sorted(documents, key=lambda ad: ad.extracted_document.document_id):
        doc_id = _sanitize_id_component("document_id", admitted.extracted_document.document_id)
        relative_path = f"documents/{doc_id}.json"
        payload = {
            "content": {
                # [ENGINEERING RECOMMENDATION] reuses observability.logging's
                # own field-name redaction (Phase 21 Step 4), never a second,
                # competing redaction mechanism - the flat provenance dict is
                # exactly the shape that utility is designed for; the nested
                # ExtractedDocument payload below is left untouched (it is
                # real document CONTENT, not caller-supplied metadata, and a
                # blanket redaction there would risk corrupting legitimate
                # document text that happens to contain a matched substring).
                "provenance": redact_metadata(admitted.provenance),
                "document": document_to_dict(admitted.extracted_document),
            }
        }
        file_path = target_dir / relative_path
        _write_json_artifact(file_path, payload)
        content_hash = _hash_file(file_path)
        artifacts.append(ArtifactRecord(relative_path, "DOCUMENT", content_hash, file_path.stat().st_size))
        identity_parts.append(f"doc:{doc_id}:{admitted.extracted_document.integrity.computed_content_hash}")

    for cr in sorted(chunking_results, key=lambda c: c.document_id):
        doc_id = _sanitize_id_component("document_id", cr.document_id)
        relative_path = f"chunks/{doc_id}.json"
        payload = {"content": chunk_result_to_dict(cr)}
        file_path = target_dir / relative_path
        _write_json_artifact(file_path, payload)
        content_hash = _hash_file(file_path)
        artifacts.append(ArtifactRecord(relative_path, "CHUNK_SET", content_hash, file_path.stat().st_size))
        chunk_hashes = ",".join(sorted(c.content_hash for c in cr.chunks))
        identity_parts.append(f"chunks:{doc_id}:{chunk_hashes}")

    if bm25_index is not None:
        relative_path = "bm25_index.json"
        payload = {"content": bm25_index_to_dict(bm25_index)}
        file_path = target_dir / relative_path
        _write_json_artifact(file_path, payload)
        content_hash = _hash_file(file_path)
        artifacts.append(ArtifactRecord(relative_path, "BM25_INDEX", content_hash, file_path.stat().st_size))
        identity_parts.append(f"bm25:{bm25_index.signature}")

    if dense_index is not None:
        faiss_relative = "dense_index.faiss"
        metadata_relative = "dense_index_metadata.json"
        faiss_path = target_dir / faiss_relative
        metadata_path = target_dir / metadata_relative
        save_dense_index(dense_index, faiss_path, metadata_path)
        artifacts.append(ArtifactRecord(faiss_relative, "DENSE_INDEX_FAISS", _hash_file(faiss_path), faiss_path.stat().st_size))
        artifacts.append(
            ArtifactRecord(metadata_relative, "DENSE_INDEX_METADATA", _hash_file(metadata_path), metadata_path.stat().st_size)
        )
        identity_parts.append(f"dense:{dense_index.signature}")

    # docs Section 21: deterministic function of canonical inputs only -
    # never a random UUID or wall-clock timestamp used as identity.
    snapshot_id = hashlib.sha256("|".join(identity_parts).encode("utf-8")).hexdigest()

    sorted_artifacts = sorted(artifacts, key=lambda a: a.relative_path)
    manifest_content = {
        "schema_version": BACKUP_SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        "corpus_lock_version": corpus_lock_version,
        "artifacts": [asdict(a) for a in sorted_artifacts],
    }
    canonical_manifest_json = json.dumps(manifest_content, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    manifest_hash = hashlib.sha256(canonical_manifest_json.encode("utf-8")).hexdigest()

    manifest_payload = {"content": manifest_content, "manifest_hash": manifest_hash}
    if created_at is not None:
        _check_non_empty_string("created_at", created_at)
        manifest_payload["manifest_metadata"] = {"created_at": created_at}

    (target_dir / _MANIFEST_FILENAME).write_text(
        json.dumps(manifest_payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )

    return SnapshotManifest(
        schema_version=BACKUP_SCHEMA_VERSION,
        snapshot_id=snapshot_id,
        corpus_lock_version=corpus_lock_version,
        artifacts=sorted_artifacts,
        manifest_hash=manifest_hash,
    )


# ---------------------------------------------------------------------------
# Integrity verification
# ---------------------------------------------------------------------------


def _read_manifest_content(snapshot_dir: Path) -> tuple:
    manifest_path = snapshot_dir / _MANIFEST_FILENAME
    if manifest_path.is_symlink():
        raise SnapshotIntegrityError(f"{_MANIFEST_FILENAME} is a symlink, refusing to follow it")
    if not manifest_path.is_file():
        raise SnapshotSchemaError(f"{_MANIFEST_FILENAME} not found in snapshot: {snapshot_dir}")

    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SnapshotSchemaError(f"{_MANIFEST_FILENAME} is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict) or "content" not in raw or "manifest_hash" not in raw:
        raise SnapshotSchemaError(f"{_MANIFEST_FILENAME} is missing required top-level keys: content, manifest_hash")

    content = raw["content"]
    manifest_hash = raw["manifest_hash"]
    if not isinstance(content, dict):
        raise SnapshotSchemaError(f"{_MANIFEST_FILENAME} 'content' must be an object")
    if not isinstance(manifest_hash, str) or not manifest_hash.strip():
        raise SnapshotSchemaError(f"{_MANIFEST_FILENAME} 'manifest_hash' must be a non-empty string")

    required_keys = ("schema_version", "snapshot_id", "corpus_lock_version", "artifacts")
    missing = [k for k in required_keys if k not in content]
    if missing:
        raise SnapshotSchemaError(f"{_MANIFEST_FILENAME} content is missing required keys: {missing}")
    if not isinstance(content["artifacts"], list):
        raise SnapshotSchemaError(f"{_MANIFEST_FILENAME} content.artifacts must be a list")

    return content, manifest_hash


def verify_snapshot_integrity(snapshot_dir) -> SnapshotManifest:
    """
    Full integrity verification of a snapshot directory (docs Section
    14/16): recomputes the manifest hash, then every declared artifact's
    hash/size, then cross-checks the manifest's declared file set against
    what is ACTUALLY on disk in both directions (missing AND unexpected
    files). Raises `SnapshotSchemaError`/`SnapshotIntegrityError` on the
    first problem found - never returns a partially-verified manifest.
    """
    snapshot_dir = Path(snapshot_dir).resolve()
    if not snapshot_dir.is_dir():
        raise SnapshotSchemaError(f"snapshot directory not found: {snapshot_dir}")

    content, stored_manifest_hash = _read_manifest_content(snapshot_dir)

    recomputed_manifest_hash = hashlib.sha256(
        json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if recomputed_manifest_hash != stored_manifest_hash:
        raise SnapshotIntegrityError(
            "manifest_hash does not match the recomputed hash of the manifest content - "
            "the manifest has been tampered with or corrupted"
        )

    try:
        artifacts = [
            ArtifactRecord(
                relative_path=a["relative_path"],
                artifact_type=a["artifact_type"],
                content_hash=a["content_hash"],
                size_bytes=a["size_bytes"],
            )
            for a in content["artifacts"]
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise SnapshotSchemaError(f"manifest artifact entries are malformed: {exc}") from exc

    declared_paths: set = set()
    for artifact in artifacts:
        if artifact.relative_path in declared_paths:
            raise SnapshotSchemaError(f"duplicate artifact path in manifest: {artifact.relative_path}")
        declared_paths.add(artifact.relative_path)

        _reject_symlink(snapshot_dir, artifact.relative_path)
        resolved_path = _safe_join(snapshot_dir, artifact.relative_path)

        if not resolved_path.is_file():
            raise SnapshotIntegrityError(f"artifact declared in manifest is missing: {artifact.relative_path}")

        actual_size = resolved_path.stat().st_size
        if actual_size != artifact.size_bytes:
            raise SnapshotIntegrityError(
                f"artifact size mismatch for {artifact.relative_path}: expected {artifact.size_bytes}, found {actual_size}"
            )
        actual_hash = _hash_file(resolved_path)
        if actual_hash != artifact.content_hash:
            raise SnapshotIntegrityError(
                f"artifact content hash mismatch for {artifact.relative_path} - the file was modified or corrupted"
            )

    # Detect unexpected artifacts (files present but not declared) AND
    # missing ones (declared but absent) by walking the real tree once,
    # never trusting filesystem enumeration order for anything but this
    # existence cross-check (docs "avoid nondeterministic dictionary/
    # filesystem-enumeration-order dependence").
    actual_files: set = set()
    for root, dirnames, filenames in os.walk(snapshot_dir, followlinks=False):
        root_path = Path(root)
        dirnames[:] = [d for d in dirnames if not (root_path / d).is_symlink()]
        for filename in filenames:
            file_path = root_path / filename
            if file_path.is_symlink():
                raise SnapshotIntegrityError(f"unexpected symlink found in snapshot: {file_path.relative_to(snapshot_dir)}")
            rel = file_path.relative_to(snapshot_dir).as_posix()
            if rel == _MANIFEST_FILENAME:
                continue
            actual_files.add(rel)

    unexpected = actual_files - declared_paths
    if unexpected:
        raise SnapshotIntegrityError(f"unexpected artifact(s) present in snapshot, not declared in manifest: {sorted(unexpected)}")

    missing = declared_paths - actual_files
    if missing:
        raise SnapshotIntegrityError(f"artifact(s) declared in manifest but missing from snapshot: {sorted(missing)}")

    return SnapshotManifest(
        schema_version=content["schema_version"],
        snapshot_id=content["snapshot_id"],
        corpus_lock_version=content["corpus_lock_version"],
        artifacts=sorted(artifacts, key=lambda a: a.relative_path),
        manifest_hash=stored_manifest_hash,
    )


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------


def _bm25_index_from_dict(data: dict) -> Bm25Index:
    """
    Reconstructs a `Bm25Index` from its own canonical dict shape
    (`retrieval.serialize.index_to_dict`'s output), mirroring
    `retrieval.serialize.load_dense_index`'s own "rebuild a nested
    dataclass from its own dict shape" pattern (there: `EmbeddingConfig`/
    `DenseIndexConfig`; here: `Bm25Config`) - never a new, independently
    invented BM25 deserializer. The index signature is recomputed and
    cross-checked exactly like `load_dense_index` already does for
    `DenseIndex` - a hand-edited/corrupted payload that still happens to
    parse as JSON is still caught.
    """
    try:
        config = Bm25Config(**data["config"])
        index = Bm25Index(
            config=config,
            chunk_count=data["chunk_count"],
            average_document_length=data["average_document_length"],
            chunk_ids=data["chunk_ids"],
            document_lengths=data["document_lengths"],
            term_document_frequency=data["term_document_frequency"],
            term_frequencies=data["term_frequencies"],
            chunk_provenance=data["chunk_provenance"],
            signature=data["signature"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SnapshotSchemaError(f"bm25 index payload is malformed: {exc}") from exc

    recomputed_signature = compute_index_signature(
        config.signature, index.chunk_ids, [p["content_hash"] for p in index.chunk_provenance]
    )
    if recomputed_signature != index.signature:
        raise SnapshotIntegrityError(
            "bm25 index signature does not match the signature recomputed from its own restored content - "
            "the payload may be corrupted or hand-edited"
        )
    return index


def restore_snapshot(snapshot_dir, restore_target_dir) -> RestoreResult:
    """
    Verifies `snapshot_dir` in full (`verify_snapshot_integrity`), then
    copies every declared artifact into `restore_target_dir` - a fresh,
    caller-controlled location that must not already contain anything
    (docs restore requirement 1/7) and must not be the snapshot directory
    itself - and re-verifies each COPIED file's hash before returning
    (docs restore requirement 4).

    FAIL-CLOSED (docs Section 15/16/22): raises `SnapshotError` (or a
    subclass) on the first problem found, at any stage - a corrupted or
    tampered snapshot, or a copy that does not match its recorded hash,
    is never partially activated. There is no in-place mutation of
    `snapshot_dir` and no release/activation mechanism here at all (that
    remains later Phase 21 work - docs Section 23, out of scope for this
    step).
    """
    manifest = verify_snapshot_integrity(snapshot_dir)
    snapshot_dir = Path(snapshot_dir).resolve()

    restore_target_dir = Path(restore_target_dir)
    if restore_target_dir.exists() and restore_target_dir.resolve() == snapshot_dir:
        raise SnapshotError("restore_target_dir must not be the snapshot directory itself")
    _require_empty_dir(restore_target_dir, "restore target")
    restore_target_dir = restore_target_dir.resolve()

    for artifact in manifest.artifacts:
        source_path = _safe_join(snapshot_dir, artifact.relative_path)
        dest_path = _safe_join(restore_target_dir, artifact.relative_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, dest_path)

        restored_hash = _hash_file(dest_path)
        if restored_hash != artifact.content_hash:
            raise SnapshotIntegrityError(
                f"restored artifact hash mismatch for {artifact.relative_path} - restore is unsafe and was aborted"
            )

    by_type: dict = {}
    for artifact in manifest.artifacts:
        by_type.setdefault(artifact.artifact_type, []).append(artifact)

    documents = [
        json.loads((restore_target_dir / a.relative_path).read_text(encoding="utf-8"))["content"]
        for a in by_type.get("DOCUMENT", [])
    ]
    chunking_results = [
        json.loads((restore_target_dir / a.relative_path).read_text(encoding="utf-8"))["content"]
        for a in by_type.get("CHUNK_SET", [])
    ]

    bm25_index = None
    bm25_artifacts = by_type.get("BM25_INDEX", [])
    if bm25_artifacts:
        payload = json.loads((restore_target_dir / bm25_artifacts[0].relative_path).read_text(encoding="utf-8"))
        bm25_index = _bm25_index_from_dict(payload["content"])

    dense_index = None
    dense_faiss_artifacts = by_type.get("DENSE_INDEX_FAISS", [])
    dense_metadata_artifacts = by_type.get("DENSE_INDEX_METADATA", [])
    if dense_faiss_artifacts and dense_metadata_artifacts:
        dense_index = load_dense_index(
            restore_target_dir / dense_faiss_artifacts[0].relative_path,
            restore_target_dir / dense_metadata_artifacts[0].relative_path,
        )

    return RestoreResult(
        manifest=manifest,
        restored_dir=str(restore_target_dir),
        documents=documents,
        chunking_results=chunking_results,
        bm25_index=bm25_index,
        dense_index=dense_index,
    )
