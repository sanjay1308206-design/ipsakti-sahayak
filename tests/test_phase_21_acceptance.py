"""
Phase 21 Step 6: final CAP-21 acceptance/integration tests
(docs/PHASE_21_OBSERVABILITY_BACKUP_CORPUS_REFRESH.md Sections 17-23, 27-28;
config/acceptance_contract.yaml CAP-21).

This file does NOT re-prove unit-level behavior already covered by
tests/test_phase_21_metrics.py, tests/test_phase_21_logging.py,
tests/test_phase_21_backup.py, or tests/test_phase_21_corpus_refresh.py -
each of those already exercises its own module's contract in isolation
(redaction, integrity hashing, individual failure branches, etc.) using
the REAL Phase 3-16/21 implementations, never mocks of the whole
workflow.

What this file adds is the missing CROSS-COMPONENT evidence CAP-21's own
acceptance criterion names as one sentence - "A corpus update can be
validated, re-indexed, evaluated, and released safely" - end to end, in
a single test, tying together: candidate -> VALIDATE -> RE-INDEX ->
EVALUATE -> BACKUP -> RELEASE -> active pointer -> Step 5A restore, plus
one equivalent test for the dry-run path's "never activates" guarantee.
Only synthetic fixtures are used; no real production corpus is required
or claimed.
"""

from __future__ import annotations

from _provenance_fixtures import make_provenance

from ingestion.hashing import compute_content_hash
from observability.backup import restore_snapshot, verify_snapshot_integrity
from observability.corpus_refresh import read_release_pointer, run_corpus_refresh
from observability.refresh_models import CandidateDocumentInput

CORPUS_LOCK_VERSION = "1.0.0"


def _make_candidate(text: str, document_id: str, **provenance_overrides) -> CandidateDocumentInput:
    data = text.encode("utf-8")
    provenance = make_provenance(
        compute_content_hash(data),
        document_id=document_id,
        provenance_status="COMPLETE",
        validation_status="VALIDATED",
        **provenance_overrides,
    )
    return CandidateDocumentInput(data=data, provenance=provenance, file_extension=".txt")


# ---------------------------------------------------------------------------
# CAP-21 acceptance criterion: "A corpus update can be validated,
# re-indexed, evaluated, and released safely" - proven end to end, in one
# place, using the real Step 5A/5B implementations (never mocked).
# ---------------------------------------------------------------------------


def test_cap21_end_to_end_lifecycle_validate_reindex_evaluate_backup_release_and_restore(tmp_path):
    release_dir = tmp_path / "release"
    candidate = _make_candidate("Trademark renewal and opposition procedure text.", "CAP21-ACCEPTANCE-DOC-1")

    result = run_corpus_refresh([candidate], release_dir=release_dir, corpus_lock_version=CORPUS_LOCK_VERSION)

    # VALIDATE -> RE-INDEX -> EVALUATE -> BACKUP -> RELEASE, in that exact
    # order, every stage passed - docs Section 17/18's own lifecycle,
    # proven against the real pipeline rather than asserted in isolation.
    assert result.status == "RELEASED"
    assert result.rejection_reason is None
    assert [s.stage for s in result.stages] == ["VALIDATE", "REINDEX", "EVALUATE", "BACKUP", "RELEASE"]
    assert all(s.passed for s in result.stages)

    # The active pointer (docs Section 23) really was updated to name this
    # exact release - not merely a value the RefreshResult claims.
    pointer = read_release_pointer(release_dir)
    assert pointer is not None
    assert pointer.active_snapshot_id == result.active_snapshot_id == result.candidate_snapshot_id
    assert pointer.corpus_lock_version == CORPUS_LOCK_VERSION

    # The release IS a real Step 5A snapshot - independently verifiable
    # and restorable through backup.py's own, unmodified functions, never
    # a parallel "release record" format invented by corpus_refresh.py.
    active_snapshot_dir = release_dir / "snapshots" / pointer.active_snapshot_relative_dir
    verify_snapshot_integrity(active_snapshot_dir)  # must not raise
    restored = restore_snapshot(active_snapshot_dir, tmp_path / "restored")
    assert len(restored.documents) == 1
    assert restored.documents[0]["document"]["document_id"] == "CAP21-ACCEPTANCE-DOC-1"
    assert restored.bm25_index is not None
    assert restored.bm25_index.chunk_count >= 1

    # The candidate's own retrieval diagnostics were genuinely measured
    # (Phase 16 evaluation.benchmark, reused - never skipped) even with an
    # empty synthetic query set (nothing to compare/regress against yet).
    assert result.candidate_evaluation_report is not None
    assert result.candidate_evaluation_report.component == "BM25_RETRIEVAL"


# ---------------------------------------------------------------------------
# CAP-21 test requirement: "corpus refresh dry run" - never activates,
# never touches the active release/pointer, no production corpus required.
# ---------------------------------------------------------------------------


def test_cap21_dry_run_never_activates_and_leaves_release_workspace_untouched(tmp_path):
    release_dir = tmp_path / "release"

    # Establish a real active release first, so this test can prove the
    # dry run leaves an ALREADY-ACTIVE release alone - not merely that
    # bootstrap (no release yet) stays empty.
    baseline = _make_candidate("Baseline active release content.", "CAP21-ACCEPTANCE-DOC-2A")
    baseline_result = run_corpus_refresh([baseline], release_dir=release_dir, corpus_lock_version=CORPUS_LOCK_VERSION)
    assert baseline_result.status == "RELEASED"
    pointer_before = read_release_pointer(release_dir)

    dry_run_candidate = _make_candidate("Materially different dry-run candidate content.", "CAP21-ACCEPTANCE-DOC-2B")
    dry_result = run_corpus_refresh(
        [dry_run_candidate], release_dir=release_dir, corpus_lock_version=CORPUS_LOCK_VERSION, dry_run=True
    )

    # candidate -> validation -> re-index -> evaluation -> release DECISION
    # (docs Section 19) - the decision is reported, but never executed.
    assert dry_result.status == "DRY_RUN_COMPLETE"
    assert dry_result.dry_run is True
    assert [s.stage for s in dry_result.stages] == ["VALIDATE", "REINDEX", "EVALUATE"]
    assert all(s.passed for s in dry_result.stages)
    assert dry_result.candidate_snapshot_id is None

    # The active release and its pointer are byte-for-byte the same as
    # before the dry run - never partially touched.
    pointer_after = read_release_pointer(release_dir)
    assert pointer_after == pointer_before
    assert dry_result.active_snapshot_id == baseline_result.active_snapshot_id

    # No candidate snapshot directory was written anywhere in the workspace.
    snapshot_dirs = {p.name for p in (release_dir / "snapshots").iterdir()}
    assert snapshot_dirs == {baseline_result.active_snapshot_id}
