"""
Phase 21 Step 5b tests: corpus-refresh orchestration
(docs/PHASE_21_OBSERVABILITY_BACKUP_CORPUS_REFRESH.md Sections 17-23, 27).

Exercises the real VALIDATE -> RE-INDEX -> EVALUATE -> (BACKUP -> RELEASE)
pipeline over small synthetic documents (via _provenance_fixtures.py,
exactly like every earlier Phase 3/4/5 test already does) - never a real
production corpus (docs Section 20). Does NOT test Phase 22/23, Gemini,
or any deployment/persistence mechanism.
"""

from __future__ import annotations

import logging
import os

import pytest
from _provenance_fixtures import make_provenance

from ingestion.hashing import compute_content_hash
from observability.backup import restore_snapshot, verify_snapshot_integrity
from observability.backup_models import SnapshotError
from observability.corpus_refresh import CorpusRefreshError, read_release_pointer, run_corpus_refresh
from observability.refresh_models import CandidateDocumentInput, EvaluationQuery, RefreshResult

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
# 1-4. Successful validation / indexing / evaluation / release
# ---------------------------------------------------------------------------


def test_successful_refresh_passes_every_stage_and_releases(tmp_path):
    candidate = _make_candidate("Trademark opposition procedure.", "REFRESH-DOC-1")
    result = run_corpus_refresh([candidate], release_dir=tmp_path / "release", corpus_lock_version=CORPUS_LOCK_VERSION)

    assert isinstance(result, RefreshResult)
    assert result.status == "RELEASED"
    assert result.rejection_reason is None
    stage_names = [s.stage for s in result.stages]
    assert stage_names == ["VALIDATE", "REINDEX", "EVALUATE", "BACKUP", "RELEASE"]
    assert all(s.passed for s in result.stages)
    assert result.active_snapshot_id == result.candidate_snapshot_id
    assert result.candidate_evaluation_report is not None


# ---------------------------------------------------------------------------
# 5. Complete dry run
# ---------------------------------------------------------------------------


def test_complete_dry_run_never_writes_a_pointer(tmp_path):
    release_dir = tmp_path / "release"
    candidate = _make_candidate("Patent working requirement.", "REFRESH-DOC-2")
    result = run_corpus_refresh([candidate], release_dir=release_dir, corpus_lock_version=CORPUS_LOCK_VERSION, dry_run=True)

    assert result.status == "DRY_RUN_COMPLETE"
    assert result.dry_run is True
    assert result.candidate_snapshot_id is None
    assert [s.stage for s in result.stages] == ["VALIDATE", "REINDEX", "EVALUATE"]
    assert not (release_dir / "pointer.json").exists()
    assert read_release_pointer(release_dir) is None


# ---------------------------------------------------------------------------
# 6/7. Validation / admission failure
# ---------------------------------------------------------------------------


def test_validation_failure_unknown_source_family(tmp_path):
    candidate = _make_candidate("Unknown family text.", "REFRESH-DOC-3", source_family_id="SF-DOES-NOT-EXIST")
    result = run_corpus_refresh([candidate], release_dir=tmp_path / "release", corpus_lock_version=CORPUS_LOCK_VERSION)

    assert result.status == "REJECTED"
    assert result.rejection_reason == "VALIDATION_FAILED"
    assert result.stages[0].stage == "VALIDATE" and not result.stages[0].passed
    assert "UNKNOWN_SOURCE_FAMILY" in result.stages[0].detail


def test_admission_failure_unknown_jurisdiction(tmp_path):
    candidate = _make_candidate("Unknown jurisdiction text.", "REFRESH-DOC-4", jurisdiction="ATLANTIS")
    result = run_corpus_refresh([candidate], release_dir=tmp_path / "release", corpus_lock_version=CORPUS_LOCK_VERSION)

    assert result.status == "REJECTED"
    assert result.rejection_reason == "VALIDATION_FAILED"
    assert "UNKNOWN_JURISDICTION" in result.stages[0].detail


# ---------------------------------------------------------------------------
# 8. Extraction failure
# ---------------------------------------------------------------------------


def test_extraction_failure_whitespace_only_document(tmp_path):
    candidate = _make_candidate("   \n\n   ", "REFRESH-DOC-5")
    result = run_corpus_refresh([candidate], release_dir=tmp_path / "release", corpus_lock_version=CORPUS_LOCK_VERSION)

    assert result.status == "REJECTED"
    assert result.rejection_reason == "VALIDATION_FAILED"
    assert "EXTRACTION_FAILED" in result.stages[0].detail


# ---------------------------------------------------------------------------
# 9. Chunking failure
# ---------------------------------------------------------------------------


def test_chunking_failure_is_rejected(tmp_path, monkeypatch):
    import observability.corpus_refresh as cr_module
    from chunking.models import ChunkingResult

    def fake_chunk_document(document, config=None):
        return ChunkingResult(document_id=document.document_id, chunking_status="CHUNKING_SKIPPED", config_signature="fake-sig", chunks=[], warnings=["NO_BLOCKS_TO_CHUNK"])

    monkeypatch.setattr(cr_module, "chunk_document", fake_chunk_document)

    candidate = _make_candidate("Real content that would normally chunk fine.", "REFRESH-DOC-6")
    result = run_corpus_refresh([candidate], release_dir=tmp_path / "release", corpus_lock_version=CORPUS_LOCK_VERSION)

    assert result.status == "REJECTED"
    assert result.rejection_reason == "INDEXING_FAILED"
    assert result.stages[-1].stage == "REINDEX"
    assert "CHUNKING_SKIPPED" in result.stages[-1].detail


# ---------------------------------------------------------------------------
# 10. BM25 indexing failure
# ---------------------------------------------------------------------------


def test_bm25_indexing_failure_is_rejected(tmp_path, monkeypatch):
    import observability.corpus_refresh as cr_module

    def fake_build_index(chunks, config=None):
        raise ValueError("simulated BM25 build failure")

    monkeypatch.setattr(cr_module, "build_index", fake_build_index)

    candidate = _make_candidate("Design registration process.", "REFRESH-DOC-7")
    result = run_corpus_refresh([candidate], release_dir=tmp_path / "release", corpus_lock_version=CORPUS_LOCK_VERSION)

    assert result.status == "REJECTED"
    assert result.rejection_reason == "INDEXING_FAILED"
    assert "simulated BM25 build failure" in result.stages[-1].detail


# ---------------------------------------------------------------------------
# 11. Dense indexing failure
# ---------------------------------------------------------------------------


def test_dense_indexing_failure_is_rejected(tmp_path, monkeypatch):
    from _dense_fixtures import make_fake_model

    import observability.corpus_refresh as cr_module

    def fake_build_dense_index(chunks, embedding_model, dense_index_config=None):
        raise RuntimeError("simulated dense build failure")

    monkeypatch.setattr(cr_module, "build_dense_index", fake_build_dense_index)

    candidate = _make_candidate("Geographical indication procedure.", "REFRESH-DOC-8")
    result = run_corpus_refresh(
        [candidate], release_dir=tmp_path / "release", corpus_lock_version=CORPUS_LOCK_VERSION, embedding_model=make_fake_model()
    )

    assert result.status == "REJECTED"
    assert result.rejection_reason == "INDEXING_FAILED"
    assert "simulated dense build failure" in result.stages[-1].detail


# ---------------------------------------------------------------------------
# 12. Evaluation failure (regression against active release)
# ---------------------------------------------------------------------------


def test_evaluation_failure_on_regression_against_active_release(tmp_path, monkeypatch):
    release_dir = tmp_path / "release"
    candidate1 = _make_candidate("Baseline provisions text.", "REFRESH-DOC-9A")
    result1 = run_corpus_refresh([candidate1], release_dir=release_dir, corpus_lock_version=CORPUS_LOCK_VERSION)
    assert result1.status == "RELEASED"

    import observability.corpus_refresh as cr_module
    from evaluation.models import ComponentBenchmarkReport, EvaluationResult

    call_count = {"n": 0}

    def fake_score(component, per_query_results, k, *, real_model_validated=False, not_validated_reason=None, config=None):
        call_count["n"] += 1
        value = 0.1 if call_count["n"] == 1 else 0.9  # candidate (1st call) scores worse than active (2nd call)
        schema_version = config.schema_version if config else "1.0.0"
        result = EvaluationResult(
            schema_version=schema_version, metric_name=f"PRECISION_AT_{k}", component=component,
            applicable=True, value=value, numerator=None, denominator=1,
            explanation="synthetic", ground_truth_origin="STRUCTURAL_EXPECTATION",
        )
        return ComponentBenchmarkReport(
            schema_version=schema_version, report_id=f"fixed-report-id-{call_count['n']}", component=component,
            case_count=1, results=[result], passed_case_ids=["q1"], failed_case_ids=[], notes=None, config_signature="sig",
        )

    monkeypatch.setattr(cr_module, "score_retrieval_condition", fake_score)

    candidate2 = _make_candidate("Updated provisions text.", "REFRESH-DOC-9B")
    query_set = [EvaluationQuery(query_id="q1", query_text="provisions", relevant_chunk_ids=frozenset({"whatever"}), k=5)]
    result2 = run_corpus_refresh(
        [candidate2], release_dir=release_dir, corpus_lock_version=CORPUS_LOCK_VERSION, evaluation_query_set=query_set
    )

    assert result2.status == "REJECTED"
    assert result2.rejection_reason == "EVALUATION_FAILED"
    assert "regressed" in result2.stages[-1].detail

    pointer = read_release_pointer(release_dir)
    assert pointer.active_snapshot_id == result1.active_snapshot_id


# ---------------------------------------------------------------------------
# 13. Backup failure
# ---------------------------------------------------------------------------


def test_backup_failure_is_rejected_and_preserves_active_release(tmp_path, monkeypatch):
    release_dir = tmp_path / "release"
    candidate1 = _make_candidate("First real release text.", "REFRESH-DOC-10A")
    result1 = run_corpus_refresh([candidate1], release_dir=release_dir, corpus_lock_version=CORPUS_LOCK_VERSION)
    assert result1.status == "RELEASED"

    import observability.corpus_refresh as cr_module

    def fake_create_snapshot(*args, **kwargs):
        raise SnapshotError("simulated backup failure")

    monkeypatch.setattr(cr_module, "create_snapshot", fake_create_snapshot)

    candidate2 = _make_candidate("Second candidate text.", "REFRESH-DOC-10B")
    result2 = run_corpus_refresh([candidate2], release_dir=release_dir, corpus_lock_version=CORPUS_LOCK_VERSION)

    assert result2.status == "REJECTED"
    assert result2.rejection_reason == "BACKUP_FAILED"
    assert result2.candidate_snapshot_id is None

    pointer = read_release_pointer(release_dir)
    assert pointer.active_snapshot_id == result1.active_snapshot_id


# ---------------------------------------------------------------------------
# 14. Release-pointer failure
# ---------------------------------------------------------------------------


def test_release_pointer_failure_preserves_previous_pointer(tmp_path, monkeypatch):
    release_dir = tmp_path / "release"
    candidate1 = _make_candidate("First real release text v2.", "REFRESH-DOC-11A")
    result1 = run_corpus_refresh([candidate1], release_dir=release_dir, corpus_lock_version=CORPUS_LOCK_VERSION)
    assert result1.status == "RELEASED"

    def raising_replace(*args, **kwargs):
        raise OSError("simulated release-pointer write failure")

    monkeypatch.setattr(os, "replace", raising_replace)

    candidate2 = _make_candidate("Second candidate text v2.", "REFRESH-DOC-11B")
    result2 = run_corpus_refresh([candidate2], release_dir=release_dir, corpus_lock_version=CORPUS_LOCK_VERSION)

    assert result2.status == "REJECTED"
    assert result2.rejection_reason == "RELEASE_POINTER_FAILED"
    # the candidate snapshot WAS written and verified (BACKUP succeeded) but never activated
    assert result2.candidate_snapshot_id is not None
    assert result2.candidate_snapshot_id != result1.active_snapshot_id

    pointer = read_release_pointer(release_dir)
    assert pointer.active_snapshot_id == result1.active_snapshot_id


# ---------------------------------------------------------------------------
# 15. Malformed candidate metadata
# ---------------------------------------------------------------------------


def test_malformed_candidate_metadata_is_rejected(tmp_path):
    candidate = _make_candidate("Text with malformed provenance field.", "REFRESH-DOC-12", source_family_id=["not", "a", "string"])
    result = run_corpus_refresh([candidate], release_dir=tmp_path / "release", corpus_lock_version=CORPUS_LOCK_VERSION)

    assert result.status == "REJECTED"
    assert result.rejection_reason == "VALIDATION_FAILED"
    assert "malformed candidate metadata" in result.stages[-1].detail


# ---------------------------------------------------------------------------
# 16. Corrupted candidate artifact
# ---------------------------------------------------------------------------


def test_corrupted_candidate_artifact_content_hash_mismatch(tmp_path):
    wrong_hash = compute_content_hash(b"totally different bytes")
    provenance = make_provenance(wrong_hash, document_id="REFRESH-DOC-13", provenance_status="COMPLETE", validation_status="VALIDATED")
    candidate = CandidateDocumentInput(data=b"the real candidate bytes", provenance=provenance, file_extension=".txt")

    result = run_corpus_refresh([candidate], release_dir=tmp_path / "release", corpus_lock_version=CORPUS_LOCK_VERSION)

    assert result.status == "REJECTED"
    assert result.rejection_reason == "VALIDATION_FAILED"
    assert "CONTENT_HASH_MISMATCH" in result.stages[-1].detail


# ---------------------------------------------------------------------------
# 17/18. Failed candidate cannot become active / active release survives failure
# ---------------------------------------------------------------------------


def test_failed_candidate_never_becomes_active(tmp_path):
    release_dir = tmp_path / "release"
    good = _make_candidate("Good baseline release.", "REFRESH-DOC-14A")
    result1 = run_corpus_refresh([good], release_dir=release_dir, corpus_lock_version=CORPUS_LOCK_VERSION)
    assert result1.status == "RELEASED"

    bad = _make_candidate("Bad candidate.", "REFRESH-DOC-14B", jurisdiction="NOWHERE")
    result2 = run_corpus_refresh([bad], release_dir=release_dir, corpus_lock_version=CORPUS_LOCK_VERSION)
    assert result2.status == "REJECTED"

    pointer = read_release_pointer(release_dir)
    assert pointer.active_snapshot_id == result1.active_snapshot_id
    verify_snapshot_integrity(release_dir / "snapshots" / pointer.active_snapshot_id)  # still usable


# ---------------------------------------------------------------------------
# 19. Successful release changes the active pointer correctly
# ---------------------------------------------------------------------------


def test_successful_release_changes_active_pointer(tmp_path):
    release_dir = tmp_path / "release"
    first = _make_candidate("First release content.", "REFRESH-DOC-15A")
    result1 = run_corpus_refresh([first], release_dir=release_dir, corpus_lock_version=CORPUS_LOCK_VERSION)
    assert result1.status == "RELEASED"

    second = _make_candidate("Second release content, materially different.", "REFRESH-DOC-15B")
    result2 = run_corpus_refresh([second], release_dir=release_dir, corpus_lock_version=CORPUS_LOCK_VERSION)
    assert result2.status == "RELEASED"
    assert result2.previous_active_snapshot_id == result1.active_snapshot_id
    assert result2.active_snapshot_id != result1.active_snapshot_id

    pointer = read_release_pointer(release_dir)
    assert pointer.active_snapshot_id == result2.active_snapshot_id


# ---------------------------------------------------------------------------
# 20. Deterministic repeated dry run
# ---------------------------------------------------------------------------


def test_repeated_dry_run_is_deterministic(tmp_path):
    candidate_a = _make_candidate("Deterministic dry run content.", "REFRESH-DOC-16")
    candidate_b = _make_candidate("Deterministic dry run content.", "REFRESH-DOC-16")

    result_a = run_corpus_refresh([candidate_a], release_dir=tmp_path / "release_a", corpus_lock_version=CORPUS_LOCK_VERSION, dry_run=True)
    result_b = run_corpus_refresh([candidate_b], release_dir=tmp_path / "release_b", corpus_lock_version=CORPUS_LOCK_VERSION, dry_run=True)

    assert [s.detail for s in result_a.stages] == [s.detail for s in result_b.stages]
    values_a = [r.value for r in result_a.candidate_evaluation_report.results]
    values_b = [r.value for r in result_b.candidate_evaluation_report.results]
    assert values_a == values_b


# ---------------------------------------------------------------------------
# 23. Existing Phase 21 backup/restore integration
# ---------------------------------------------------------------------------


def test_released_snapshot_round_trips_through_step_5a_restore(tmp_path):
    release_dir = tmp_path / "release"
    candidate = _make_candidate("Content that must round-trip through restore.", "REFRESH-DOC-17")
    result = run_corpus_refresh([candidate], release_dir=release_dir, corpus_lock_version=CORPUS_LOCK_VERSION)
    assert result.status == "RELEASED"

    snapshot_dir = release_dir / "snapshots" / result.active_snapshot_id
    restored = restore_snapshot(snapshot_dir, tmp_path / "restored")
    assert len(restored.documents) == 1
    assert restored.bm25_index is not None


# ---------------------------------------------------------------------------
# 24. Structured operational logging integration
# ---------------------------------------------------------------------------


def test_structured_logging_events_are_emitted(tmp_path, caplog):
    candidate = _make_candidate("Logging integration content.", "REFRESH-DOC-18")
    with caplog.at_level(logging.INFO, logger="ipsakti.corpus_refresh"):
        result = run_corpus_refresh([candidate], release_dir=tmp_path / "release", corpus_lock_version=CORPUS_LOCK_VERSION)

    assert result.status == "RELEASED"
    messages = " ".join(r.message for r in caplog.records)
    for expected_event in ("corpus_refresh.started", "corpus_refresh.validate", "corpus_refresh.reindex", "corpus_refresh.evaluate", "corpus_refresh.backup", "corpus_refresh.released"):
        assert expected_event in messages


# ---------------------------------------------------------------------------
# Additional: malformed pointer.json is a structural error, not a silent pass
# ---------------------------------------------------------------------------


def test_malformed_pointer_file_raises_corpus_refresh_error(tmp_path):
    release_dir = tmp_path / "release"
    release_dir.mkdir()
    (release_dir / "pointer.json").write_text("{not valid json", encoding="utf-8")

    with pytest.raises(CorpusRefreshError):
        read_release_pointer(release_dir)
