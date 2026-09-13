"""
Phase 21 Step 5a tests: corpus/index backup and safe restore
(docs/PHASE_21_OBSERVABILITY_BACKUP_CORPUS_REFRESH.md Sections 12-16, 27).

Reuses real Phase 3/4/5 objects (via tests/_backup_fixtures.py, exactly
like tests/test_phase_21_metrics.py already does for Phase 9/13) rather
than hand-built stand-ins, so these tests also prove the backup layer
packages real, already-validated Phase 3/4/5 output correctly - never a
second, competing ingestion/chunking/indexing computation.

Does NOT test corpus-refresh orchestration, the release pointer, or
corpus activation - those are separate, not-yet-implemented Phase 21
capabilities (docs Section 3/17-19/23).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest
import yaml
from _backup_fixtures import make_admitted_document, make_bm25_index, make_chunking_result

from observability.backup import create_snapshot, restore_snapshot, verify_snapshot_integrity
from observability.backup_models import (
    AdmittedDocument,
    ArtifactRecord,
    RestoreResult,
    SnapshotError,
    SnapshotIntegrityError,
    SnapshotManifest,
    SnapshotSchemaError,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_LOCK_VERSION = "1.0.0"


@pytest.fixture
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def _write_raw_manifest(snapshot_dir: Path, artifacts: list, corpus_lock_version: str = CORPUS_LOCK_VERSION) -> None:
    """Test-only helper: hand-crafts a manifest.json with a CORRECT manifest_hash for arbitrary (possibly malicious) artifact entries, so adversarial tests exercise the per-artifact path/hash checks rather than the manifest-hash check."""
    content = {
        "schema_version": "1.0.0",
        "snapshot_id": "test-snapshot-id",
        "corpus_lock_version": corpus_lock_version,
        "artifacts": artifacts,
    }
    manifest_hash = hashlib.sha256(
        json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    payload = {"content": content, "manifest_hash": manifest_hash}
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / "manifest.json").write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )


def _malicious_artifact(relative_path: str) -> dict:
    return {"relative_path": relative_path, "artifact_type": "DOCUMENT", "content_hash": "a" * 64, "size_bytes": 2}


# ---------------------------------------------------------------------------
# 1. Successful snapshot creation
# ---------------------------------------------------------------------------


def test_successful_snapshot_creation_writes_manifest_and_artifacts(tmp_path, authority_matrix):
    admitted = make_admitted_document("Trademark filing procedure.", "BACKUP-DOC-1", authority_matrix)
    chunking_result = make_chunking_result(admitted)
    bm25_index = make_bm25_index([chunking_result])

    target_dir = tmp_path / "snapshot"
    manifest = create_snapshot(
        target_dir,
        documents=[admitted],
        chunking_results=[chunking_result],
        bm25_index=bm25_index,
        corpus_lock_version=CORPUS_LOCK_VERSION,
    )

    assert isinstance(manifest, SnapshotManifest)
    assert (target_dir / "manifest.json").is_file()
    assert (target_dir / "documents" / "BACKUP-DOC-1.json").is_file()
    assert (target_dir / "chunks" / "BACKUP-DOC-1.json").is_file()
    assert (target_dir / "bm25_index.json").is_file()
    assert {a.artifact_type for a in manifest.artifacts} == {"DOCUMENT", "CHUNK_SET", "BM25_INDEX"}


# ---------------------------------------------------------------------------
# 2. Successful restore
# ---------------------------------------------------------------------------


def test_successful_restore(tmp_path, authority_matrix):
    admitted = make_admitted_document("Patent examination timeline.", "BACKUP-DOC-2", authority_matrix)
    chunking_result = make_chunking_result(admitted)
    bm25_index = make_bm25_index([chunking_result])

    snapshot_dir = tmp_path / "snapshot"
    create_snapshot(
        snapshot_dir,
        documents=[admitted],
        chunking_results=[chunking_result],
        bm25_index=bm25_index,
        corpus_lock_version=CORPUS_LOCK_VERSION,
    )

    restored = restore_snapshot(snapshot_dir, tmp_path / "restored")
    assert isinstance(restored, RestoreResult)
    assert len(restored.documents) == 1
    assert len(restored.chunking_results) == 1
    assert restored.bm25_index is not None


# ---------------------------------------------------------------------------
# 3. Round-trip equivalence
# ---------------------------------------------------------------------------


def test_round_trip_equivalence_of_document_and_chunk_content(tmp_path, authority_matrix):
    from chunking.serialize import result_to_dict
    from ingestion.serialize import document_to_dict

    admitted = make_admitted_document("Copyright registration form.", "BACKUP-DOC-3", authority_matrix)
    chunking_result = make_chunking_result(admitted)

    snapshot_dir = tmp_path / "snapshot"
    create_snapshot(snapshot_dir, documents=[admitted], chunking_results=[chunking_result], corpus_lock_version=CORPUS_LOCK_VERSION)

    restored = restore_snapshot(snapshot_dir, tmp_path / "restored")
    assert restored.documents[0]["document"] == document_to_dict(admitted.extracted_document)
    assert restored.chunking_results[0] == result_to_dict(chunking_result)


def test_round_trip_equivalence_of_bm25_index(tmp_path, authority_matrix):
    admitted = make_admitted_document("Design registration eligibility.", "BACKUP-DOC-4", authority_matrix)
    chunking_result = make_chunking_result(admitted)
    bm25_index = make_bm25_index([chunking_result])

    snapshot_dir = tmp_path / "snapshot"
    create_snapshot(
        snapshot_dir, documents=[admitted], chunking_results=[chunking_result], bm25_index=bm25_index, corpus_lock_version=CORPUS_LOCK_VERSION
    )

    restored = restore_snapshot(snapshot_dir, tmp_path / "restored")
    assert restored.bm25_index.signature == bm25_index.signature
    assert restored.bm25_index.chunk_ids == bm25_index.chunk_ids
    assert restored.bm25_index.term_frequencies == bm25_index.term_frequencies


# ---------------------------------------------------------------------------
# 4. Deterministic snapshot identity
# ---------------------------------------------------------------------------


def test_deterministic_snapshot_identity_for_equivalent_input(tmp_path, authority_matrix):
    admitted_a = make_admitted_document("Geographic indication basics.", "BACKUP-DOC-5", authority_matrix)
    chunking_a = make_chunking_result(admitted_a)

    admitted_b = make_admitted_document("Geographic indication basics.", "BACKUP-DOC-5", authority_matrix)
    chunking_b = make_chunking_result(admitted_b)

    manifest_a = create_snapshot(tmp_path / "snap_a", documents=[admitted_a], chunking_results=[chunking_a], corpus_lock_version=CORPUS_LOCK_VERSION)
    manifest_b = create_snapshot(tmp_path / "snap_b", documents=[admitted_b], chunking_results=[chunking_b], corpus_lock_version=CORPUS_LOCK_VERSION)

    assert manifest_a.snapshot_id == manifest_b.snapshot_id
    assert manifest_a.manifest_hash == manifest_b.manifest_hash


def test_snapshot_identity_independent_of_input_list_order(tmp_path, authority_matrix):
    doc1 = make_admitted_document("First act text.", "BACKUP-DOC-6", authority_matrix)
    doc2 = make_admitted_document("Second act text.", "BACKUP-DOC-7", authority_matrix)
    c1 = make_chunking_result(doc1)
    c2 = make_chunking_result(doc2)

    manifest_forward = create_snapshot(
        tmp_path / "snap_fwd", documents=[doc1, doc2], chunking_results=[c1, c2], corpus_lock_version=CORPUS_LOCK_VERSION
    )
    manifest_reverse = create_snapshot(
        tmp_path / "snap_rev", documents=[doc2, doc1], chunking_results=[c2, c1], corpus_lock_version=CORPUS_LOCK_VERSION
    )
    assert manifest_forward.snapshot_id == manifest_reverse.snapshot_id


# ---------------------------------------------------------------------------
# 5. Content-hash verification
# ---------------------------------------------------------------------------


def test_content_hash_verification_passes_for_untouched_snapshot(tmp_path, authority_matrix):
    admitted = make_admitted_document("Industrial design novelty.", "BACKUP-DOC-8", authority_matrix)
    snapshot_dir = tmp_path / "snapshot"
    create_snapshot(snapshot_dir, documents=[admitted], corpus_lock_version=CORPUS_LOCK_VERSION)
    verify_snapshot_integrity(snapshot_dir)  # must not raise


# ---------------------------------------------------------------------------
# 6. Missing artifact
# ---------------------------------------------------------------------------


def test_missing_artifact_is_detected(tmp_path, authority_matrix):
    admitted = make_admitted_document("Plant variety protection.", "BACKUP-DOC-9", authority_matrix)
    snapshot_dir = tmp_path / "snapshot"
    create_snapshot(snapshot_dir, documents=[admitted], corpus_lock_version=CORPUS_LOCK_VERSION)

    (snapshot_dir / "documents" / "BACKUP-DOC-9.json").unlink()

    with pytest.raises(SnapshotIntegrityError):
        verify_snapshot_integrity(snapshot_dir)


# ---------------------------------------------------------------------------
# 7. Modified artifact
# ---------------------------------------------------------------------------


def test_modified_artifact_is_detected(tmp_path, authority_matrix):
    admitted = make_admitted_document("Semiconductor layout design.", "BACKUP-DOC-10", authority_matrix)
    snapshot_dir = tmp_path / "snapshot"
    create_snapshot(snapshot_dir, documents=[admitted], corpus_lock_version=CORPUS_LOCK_VERSION)

    doc_path = snapshot_dir / "documents" / "BACKUP-DOC-10.json"
    doc_path.write_text(doc_path.read_text(encoding="utf-8") + " ", encoding="utf-8")

    with pytest.raises(SnapshotIntegrityError):
        verify_snapshot_integrity(snapshot_dir)


# ---------------------------------------------------------------------------
# 8. Corrupted manifest/metadata
# ---------------------------------------------------------------------------


def test_corrupted_manifest_json_is_rejected(tmp_path):
    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir()
    (snapshot_dir / "manifest.json").write_text("{not valid json", encoding="utf-8")

    with pytest.raises(SnapshotSchemaError):
        verify_snapshot_integrity(snapshot_dir)


def test_manifest_missing_required_keys_is_rejected(tmp_path):
    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir()
    (snapshot_dir / "manifest.json").write_text(json.dumps({"foo": "bar"}), encoding="utf-8")

    with pytest.raises(SnapshotSchemaError):
        verify_snapshot_integrity(snapshot_dir)


def test_manifest_hash_tamper_is_detected(tmp_path, authority_matrix):
    admitted = make_admitted_document("Utility model examination.", "BACKUP-DOC-11", authority_matrix)
    snapshot_dir = tmp_path / "snapshot"
    create_snapshot(snapshot_dir, documents=[admitted], corpus_lock_version=CORPUS_LOCK_VERSION)

    manifest_path = snapshot_dir / "manifest.json"
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw["content"]["corpus_lock_version"] = "9.9.9"  # tamper without recomputing manifest_hash
    manifest_path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(SnapshotIntegrityError):
        verify_snapshot_integrity(snapshot_dir)


# ---------------------------------------------------------------------------
# 9. Unexpected artifact
# ---------------------------------------------------------------------------


def test_unexpected_artifact_is_detected(tmp_path, authority_matrix):
    admitted = make_admitted_document("Well-known trademark criteria.", "BACKUP-DOC-12", authority_matrix)
    snapshot_dir = tmp_path / "snapshot"
    create_snapshot(snapshot_dir, documents=[admitted], corpus_lock_version=CORPUS_LOCK_VERSION)

    (snapshot_dir / "documents" / "STRAY-FILE.json").write_text("{}", encoding="utf-8")

    with pytest.raises(SnapshotIntegrityError):
        verify_snapshot_integrity(snapshot_dir)


# ---------------------------------------------------------------------------
# 10. Invalid snapshot
# ---------------------------------------------------------------------------


def test_missing_manifest_is_an_invalid_snapshot(tmp_path):
    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir()

    with pytest.raises(SnapshotSchemaError):
        verify_snapshot_integrity(snapshot_dir)


def test_nonexistent_snapshot_directory_is_rejected(tmp_path):
    with pytest.raises(SnapshotSchemaError):
        verify_snapshot_integrity(tmp_path / "does-not-exist")


# ---------------------------------------------------------------------------
# 11. Path traversal
# ---------------------------------------------------------------------------


def test_path_traversal_dotdot_is_rejected(tmp_path):
    snapshot_dir = tmp_path / "snapshot"
    _write_raw_manifest(snapshot_dir, [_malicious_artifact("../outside.json")])
    with pytest.raises(SnapshotIntegrityError):
        verify_snapshot_integrity(snapshot_dir)


# ---------------------------------------------------------------------------
# 12. Absolute-path attack
# ---------------------------------------------------------------------------


def test_absolute_path_is_rejected(tmp_path):
    snapshot_dir = tmp_path / "snapshot"
    _write_raw_manifest(snapshot_dir, [_malicious_artifact("/etc/passwd")])
    with pytest.raises(SnapshotIntegrityError):
        verify_snapshot_integrity(snapshot_dir)


def test_windows_drive_absolute_path_is_rejected(tmp_path):
    snapshot_dir = tmp_path / "snapshot"
    _write_raw_manifest(snapshot_dir, [_malicious_artifact("C:/Windows/win.ini")])
    with pytest.raises(SnapshotIntegrityError):
        verify_snapshot_integrity(snapshot_dir)


def test_backslash_traversal_is_rejected(tmp_path):
    snapshot_dir = tmp_path / "snapshot"
    _write_raw_manifest(snapshot_dir, [_malicious_artifact("documents\\..\\..\\evil.json")])
    with pytest.raises(SnapshotIntegrityError):
        verify_snapshot_integrity(snapshot_dir)


# ---------------------------------------------------------------------------
# 13. Nested traversal
# ---------------------------------------------------------------------------


def test_nested_traversal_is_rejected(tmp_path):
    snapshot_dir = tmp_path / "snapshot"
    _write_raw_manifest(snapshot_dir, [_malicious_artifact("documents/nested/../../../outside.json")])
    with pytest.raises(SnapshotIntegrityError):
        verify_snapshot_integrity(snapshot_dir)


# ---------------------------------------------------------------------------
# 14. Symlink/path escape
# ---------------------------------------------------------------------------


def test_symlinked_artifact_is_rejected(tmp_path, authority_matrix):
    admitted = make_admitted_document("Trade secret protection scope.", "BACKUP-DOC-13", authority_matrix)
    snapshot_dir = tmp_path / "snapshot"
    create_snapshot(snapshot_dir, documents=[admitted], corpus_lock_version=CORPUS_LOCK_VERSION)

    outside_target = tmp_path / "outside_secret.txt"
    outside_target.write_text("outside content", encoding="utf-8")
    doc_path = snapshot_dir / "documents" / "BACKUP-DOC-13.json"
    doc_path.unlink()
    try:
        os.symlink(outside_target, doc_path)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not permitted in this environment")

    with pytest.raises(SnapshotIntegrityError):
        verify_snapshot_integrity(snapshot_dir)


# ---------------------------------------------------------------------------
# 15. Partial restore failure
# ---------------------------------------------------------------------------


def test_partial_restore_failure_does_not_return_a_result(tmp_path, authority_matrix, monkeypatch):
    admitted = make_admitted_document("Compulsory licensing conditions.", "BACKUP-DOC-14", authority_matrix)
    snapshot_dir = tmp_path / "snapshot"
    create_snapshot(snapshot_dir, documents=[admitted], corpus_lock_version=CORPUS_LOCK_VERSION)

    import observability.backup as backup_module

    def _corrupting_copyfile(source, dest):
        Path(dest).write_bytes(b"corrupted-during-copy")

    monkeypatch.setattr(backup_module.shutil, "copyfile", _corrupting_copyfile)

    with pytest.raises(SnapshotIntegrityError):
        backup_module.restore_snapshot(snapshot_dir, tmp_path / "restored")


# ---------------------------------------------------------------------------
# 16. Restore verification failure
# ---------------------------------------------------------------------------


def test_restore_fails_when_source_snapshot_is_tampered(tmp_path, authority_matrix):
    admitted = make_admitted_document("Border enforcement measures.", "BACKUP-DOC-15", authority_matrix)
    snapshot_dir = tmp_path / "snapshot"
    create_snapshot(snapshot_dir, documents=[admitted], corpus_lock_version=CORPUS_LOCK_VERSION)

    doc_path = snapshot_dir / "documents" / "BACKUP-DOC-15.json"
    doc_path.write_text(doc_path.read_text(encoding="utf-8") + "tamper", encoding="utf-8")

    with pytest.raises(SnapshotIntegrityError):
        restore_snapshot(snapshot_dir, tmp_path / "restored")

    assert not (tmp_path / "restored").exists()


# ---------------------------------------------------------------------------
# 17. Empty/minimal synthetic corpus
# ---------------------------------------------------------------------------


def test_empty_corpus_snapshot_round_trips(tmp_path):
    snapshot_dir = tmp_path / "snapshot"
    manifest = create_snapshot(snapshot_dir, documents=[], corpus_lock_version=CORPUS_LOCK_VERSION)
    assert manifest.artifacts == []

    restored = restore_snapshot(snapshot_dir, tmp_path / "restored")
    assert restored.documents == []
    assert restored.chunking_results == []
    assert restored.bm25_index is None
    assert restored.dense_index is None


# ---------------------------------------------------------------------------
# 18. Repeated backup determinism
# ---------------------------------------------------------------------------


def test_repeated_backup_is_byte_identical_given_fixed_created_at(tmp_path, authority_matrix):
    admitted = make_admitted_document("Anti-competitive licensing practices.", "BACKUP-DOC-16", authority_matrix)

    create_snapshot(tmp_path / "snap_1", documents=[admitted], corpus_lock_version=CORPUS_LOCK_VERSION, created_at="2026-01-01T00:00:00+00:00")
    create_snapshot(tmp_path / "snap_2", documents=[admitted], corpus_lock_version=CORPUS_LOCK_VERSION, created_at="2026-01-01T00:00:00+00:00")

    manifest_1 = (tmp_path / "snap_1" / "manifest.json").read_text(encoding="utf-8")
    manifest_2 = (tmp_path / "snap_2" / "manifest.json").read_text(encoding="utf-8")
    assert manifest_1 == manifest_2


# ---------------------------------------------------------------------------
# 19. No unintended overwrite
# ---------------------------------------------------------------------------


def test_create_snapshot_refuses_nonempty_target_directory(tmp_path, authority_matrix):
    admitted = make_admitted_document("Franchise disclosure requirements.", "BACKUP-DOC-17", authority_matrix)
    target_dir = tmp_path / "snapshot"
    target_dir.mkdir()
    (target_dir / "keep_me.txt").write_text("do not touch", encoding="utf-8")

    with pytest.raises(SnapshotError):
        create_snapshot(target_dir, documents=[admitted], corpus_lock_version=CORPUS_LOCK_VERSION)

    assert (target_dir / "keep_me.txt").read_text(encoding="utf-8") == "do not touch"
    assert not (target_dir / "manifest.json").exists()


def test_restore_snapshot_refuses_nonempty_target_directory(tmp_path, authority_matrix):
    admitted = make_admitted_document("Standard essential patent licensing.", "BACKUP-DOC-18", authority_matrix)
    snapshot_dir = tmp_path / "snapshot"
    create_snapshot(snapshot_dir, documents=[admitted], corpus_lock_version=CORPUS_LOCK_VERSION)

    restore_dir = tmp_path / "restored"
    restore_dir.mkdir()
    (restore_dir / "keep_me.txt").write_text("do not touch", encoding="utf-8")

    with pytest.raises(SnapshotError):
        restore_snapshot(snapshot_dir, restore_dir)

    assert (restore_dir / "keep_me.txt").read_text(encoding="utf-8") == "do not touch"


# ---------------------------------------------------------------------------
# 20. No secrets exposed in backup metadata
# ---------------------------------------------------------------------------


def test_secret_looking_provenance_field_is_redacted(tmp_path, authority_matrix):
    admitted = make_admitted_document(
        "Licensing fee schedule.", "BACKUP-DOC-19", authority_matrix, api_key="sk-should-never-appear-in-backup"
    )
    snapshot_dir = tmp_path / "snapshot"
    create_snapshot(snapshot_dir, documents=[admitted], corpus_lock_version=CORPUS_LOCK_VERSION)

    raw = (snapshot_dir / "documents" / "BACKUP-DOC-19.json").read_text(encoding="utf-8")
    assert "sk-should-never-appear-in-backup" not in raw
    assert "***REDACTED***" in raw


# ---------------------------------------------------------------------------
# Additional: AdmittedDocument consistency + dense index reuse
# ---------------------------------------------------------------------------


def test_admitted_document_rejects_document_id_mismatch(authority_matrix):
    admitted = make_admitted_document("Mismatch check text.", "BACKUP-DOC-20", authority_matrix)
    bad_provenance = dict(admitted.provenance)
    bad_provenance["document_id"] = "SOME-OTHER-ID"
    with pytest.raises(ValueError):
        AdmittedDocument(provenance=bad_provenance, extracted_document=admitted.extracted_document)


def test_dense_index_round_trip_uses_existing_phase6_loader(tmp_path, authority_matrix):
    from _dense_fixtures import make_fake_model
    from retrieval.faiss_index import build_dense_index

    admitted = make_admitted_document("Dense retrieval smoke text.", "BACKUP-DOC-21", authority_matrix)
    chunking_result = make_chunking_result(admitted)
    model = make_fake_model()
    dense_index = build_dense_index(list(chunking_result.chunks), model)

    snapshot_dir = tmp_path / "snapshot"
    create_snapshot(
        snapshot_dir,
        documents=[admitted],
        chunking_results=[chunking_result],
        dense_index=dense_index,
        corpus_lock_version=CORPUS_LOCK_VERSION,
    )

    restored = restore_snapshot(snapshot_dir, tmp_path / "restored")
    assert restored.dense_index is not None
    assert restored.dense_index.signature == dense_index.signature
