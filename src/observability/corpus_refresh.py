"""
Phase 21 corpus-refresh orchestration: VALIDATE -> RE-INDEX -> EVALUATE ->
RELEASE (docs/PHASE_21_OBSERVABILITY_BACKUP_CORPUS_REFRESH.md Sections
17-23, config/phase_21_observability.yaml `corpus_refresh`/`release_gate`/
`dry_run`).

`[ENGINEERING RECOMMENDATION]` This module is an ORCHESTRATION layer only
- composing existing, unmodified Phase 3/4/5/6/16/21 functions in the
exact sequence CAP-21 names, never reimplementing any of them:

- VALIDATE: `ingestion.pipeline.ingest_bytes` (Phase 3), which itself
  calls `ingestion.admission.check_admission_boundary` against
  `config/authority_matrix.yaml` - the same admission boundary every
  other document in this repository already goes through. `[ENGINEERING
  RECOMMENDATION]` corpus governance (`config/corpus_lock.yaml`) is
  respected THROUGH this existing, unmodified boundary - this module
  never re-parses `corpus_lock.yaml` to build a second, competing
  authority check (that would be exactly the "second corpus-authority
  system" Rule 2 / docs Section 4 forbid). `corpus_lock_version` is
  recorded in the release snapshot's manifest (the same field
  `observability.backup.create_snapshot` already requires) as the
  caller-declared lock version in effect at capture time - never
  re-derived here. `[ASSUMPTION]` (docs Section 22 names "the offending
  document(s) are rejected... the refresh does not proceed to
  re-indexing" without disambiguating whether other, non-offending
  candidate documents in the SAME batch may still proceed): this
  implementation is ALL-OR-NOTHING per refresh call - one invalid
  candidate document rejects the entire batch, never a partial
  admit-some/reject-some outcome. This is the stricter, fail-closed
  reading, consistent with Section 18's "the gate is a single explicit
  precondition" framing applied uniformly; a future instruction could
  legitimately choose per-document partial admission instead, but that
  would be a disclosed behavior change, not a bug fix.
- RE-INDEX: `chunking.chunker.chunk_document` (Phase 4) +
  `retrieval.index.build_index` (Phase 5, mandatory baseline) +
  optionally `retrieval.faiss_index.build_dense_index` (Phase 6, only
  when the caller supplies a loaded `EmbeddingModel` - dense retrieval
  remains additive, never required, matching Phase 7's own
  BM25-baseline-plus-optional-dense framing).
- EVALUATE: `evaluation.benchmark.score_retrieval_condition` (Phase 16),
  which itself wraps `retrieval.evaluation.precision_at_k`/`recall_at_k`/
  `mean_reciprocal_rank` (Phase 5/6) - never a second benchmark
  framework. `[ASSUMPTION]` (docs Section 6 instruction: "use the
  contract's defined evaluation pass/fail semantics rather than
  inventing a new threshold"): CAP-21 names no numeric release
  threshold, so the release gate is REGRESSION-based, exactly as docs
  Section 22 names it ("a measured regression against the
  previously-active snapshot's own scores") - the candidate must not
  score strictly worse than the currently-active release on the same
  synthetic query set, on any of Precision@K/Recall@K/MRR. When there is
  no active release yet (bootstrap) or the query set is empty, there is
  nothing to regress against and evaluation passes trivially (the same
  zero-denominator honesty every other Phase 16/21 metric already
  applies - "nothing measured" is never conflated with "measured and
  passed by a fabricated default"). `[DEFERRED]`: extending this
  regression gate to the optional dense/hybrid index - only the
  mandatory BM25 baseline gates release in this step.
  `[DEFERRED]`/`[ASSUMPTION]`: `citation.metrics` is not exercised here
  - corpus-refresh evaluation operates at the retrieval-index level
  (no `GroundedResponse`/citation data exists at this stage; citation
  validation remains Phase 9/10's own downstream concern, out of this
  orchestration's scope).
- BACKUP/RELEASE: `observability.backup.create_snapshot`/
  `verify_snapshot_integrity` (Step 5A, reused verbatim - never
  duplicated hashing/manifest logic). "Release" IS writing the
  candidate's verified snapshot into the release workspace and then
  atomically repointing `pointer.json` at it - there is no separate,
  second release mechanism.

RELEASE POINTER (docs Section 23, `[ASSUMPTION]`): the smallest
deterministic local-filesystem mechanism - one JSON file
(`release_dir/pointer.json`) naming the active snapshot directory under
`release_dir/snapshots/`, written via write-temp-file-then-`os.replace`
(atomic on POSIX and Windows) so a crash mid-write can never corrupt or
partially update it - the previous pointer is left completely untouched
until the moment a fully verified new one is ready to replace it.

FAIL-CLOSED (docs Section 17/18/22): `run_corpus_refresh` returns a
`RefreshResult` whose `status` is `"REJECTED"` (naming exactly which
stage failed) the instant any stage fails - it never proceeds to a later
stage, and the release pointer is only ever touched by the RELEASE
stage's own atomic write, so a rejected refresh can only ever leave the
pointer exactly as it already was.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from chunking.chunker import chunk_document
from chunking.models import ChunkingConfig
from evaluation.benchmark import score_retrieval_condition
from evaluation.models import EvaluationConfig
from ingestion.pipeline import ingest_bytes
from observability.backup import create_snapshot, verify_snapshot_integrity
from observability.backup_models import REQUIRED_PROVENANCE_FIELDS, AdmittedDocument, SnapshotError
from observability.logging import build_structured_log_event, emit_structured_log_event, get_logger
from retrieval.faiss_index import build_dense_index
from retrieval.index import build_index, query
from retrieval.models import Bm25Config, DenseIndexConfig

from .refresh_models import REFRESH_SCHEMA_VERSION, CandidateDocumentInput, ReleasePointer, RefreshResult, StageOutcome

_POINTER_FILENAME = "pointer.json"
_SNAPSHOTS_DIRNAME = "snapshots"
_STAGING_DIRNAME = "_staging"

_LOGGER_COMPONENT = "corpus_refresh"

# [ENGINEERING RECOMMENDATION] docs Section 17.1 folds Phase 3 admission
# AND extraction into one "validate" concept - a document that admission
# accepts but Phase 3 could not usefully extract (EXTRACTION_FAILED,
# OCR_REQUIRED) is rejected here too, never silently carried forward as
# an "admitted" document with unusable content.
_ACCEPTABLE_EXTRACTION_STATES = frozenset({"EXTRACTION_SUCCESS", "EXTRACTION_PARTIAL"})


class CorpusRefreshError(Exception):
    """Raised for a structural/programming-contract problem in the refresh workspace itself (e.g. a malformed pointer.json) - never for an ordinary candidate rejection, which is reported via `RefreshResult` instead."""


def _log(logger, event_name: str, *, level: str = "INFO", outcome: Optional[str] = None, metadata: Optional[dict] = None) -> None:
    event = build_structured_log_event(
        event_name=event_name, component=_LOGGER_COMPONENT, level=level, outcome=outcome, metadata=metadata or {}
    )
    emit_structured_log_event(logger, event)


def read_release_pointer(release_dir) -> Optional[ReleasePointer]:
    """Returns the currently-active `ReleasePointer`, or `None` if no release has ever succeeded in this workspace (bootstrap)."""
    pointer_path = Path(release_dir) / _POINTER_FILENAME
    if not pointer_path.is_file():
        return None
    try:
        raw = json.loads(pointer_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CorpusRefreshError(f"{_POINTER_FILENAME} is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise CorpusRefreshError(f"{_POINTER_FILENAME} must contain a JSON object")
    try:
        return ReleasePointer(**raw)
    except (TypeError, ValueError) as exc:
        raise CorpusRefreshError(f"{_POINTER_FILENAME} is malformed: {exc}") from exc


def _write_release_pointer_atomic(release_dir: Path, pointer: ReleasePointer) -> None:
    """Write-temp-then-`os.replace` - atomic on both POSIX and Windows, so `pointer.json` is either fully the old value or fully the new one, never a partial write."""
    payload = asdict(pointer)
    tmp_path = release_dir / f"{_POINTER_FILENAME}.tmp"
    tmp_path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp_path, release_dir / _POINTER_FILENAME)


def _metric_value(report, metric_name: str) -> Optional[float]:
    for result in report.results:
        if result.metric_name == metric_name:
            return result.value if result.applicable else None
    return None


def _bm25_per_query_results(bm25_index, evaluation_query_set: list) -> list:
    results = []
    for eq in evaluation_query_set:
        response = query(bm25_index, eq.query_text, eq.k)
        retrieved = [r.chunk_id for r in response.results]
        results.append((eq.query_id, retrieved, set(eq.relevant_chunk_ids)))
    return results


def run_corpus_refresh(
    candidate_documents: list,
    *,
    release_dir,
    corpus_lock_version: str,
    authority_matrix: Optional[dict] = None,
    chunking_config: Optional[ChunkingConfig] = None,
    bm25_config: Optional[Bm25Config] = None,
    embedding_model=None,
    dense_index_config: Optional[DenseIndexConfig] = None,
    evaluation_query_set: Optional[list] = None,
    dry_run: bool = False,
    logger=None,
) -> RefreshResult:
    """
    Runs one VALIDATE -> RE-INDEX -> EVALUATE -> (BACKUP -> RELEASE)
    corpus-refresh cycle over `candidate_documents` (a list of
    `CandidateDocumentInput` - raw bytes + provenance, never a
    pre-ingested object) against the release workspace rooted at
    `release_dir`.

    `dry_run=True` (docs Section 19) executes VALIDATE/RE-INDEX/EVALUATE
    in full and reports the real result, but never writes a snapshot or
    touches `pointer.json` - the active release is left completely
    untouched regardless of outcome, and `RefreshResult.status` is always
    `"DRY_RUN_COMPLETE"`, never `"RELEASED"`.

    Raises nothing for an ordinary candidate failure - that is reported
    via `RefreshResult.status == "REJECTED"`. Raises `CorpusRefreshError`
    only for a structural problem with the release workspace itself (a
    malformed `pointer.json`), which is not a candidate-data problem this
    function can safely paper over.
    """
    if logger is None:
        logger = get_logger(_LOGGER_COMPONENT)

    if not isinstance(candidate_documents, list) or any(not isinstance(c, CandidateDocumentInput) for c in candidate_documents):
        raise TypeError("candidate_documents must be a list of CandidateDocumentInput")
    if not isinstance(corpus_lock_version, str) or not corpus_lock_version.strip():
        raise ValueError("corpus_lock_version must be a non-empty string")
    evaluation_query_set = list(evaluation_query_set) if evaluation_query_set is not None else []

    if evaluation_query_set:
        k_values = {eq.k for eq in evaluation_query_set}
        if len(k_values) != 1:
            raise ValueError("evaluation_query_set: every EvaluationQuery must share the same k value")
        evaluation_k = next(iter(k_values))
    else:
        evaluation_k = 0  # never used for a metric computation when the query set is empty

    release_dir = Path(release_dir)
    release_dir.mkdir(parents=True, exist_ok=True)
    previous_pointer = read_release_pointer(release_dir)
    previous_active_snapshot_id = previous_pointer.active_snapshot_id if previous_pointer else None

    stages: list = []

    def _reject(reason: str, detail: str, *, candidate_snapshot_id: Optional[str] = None) -> RefreshResult:
        # candidate_snapshot_id is set ONLY for RELEASE_POINTER_FAILED - the
        # one rejection path reached after a candidate snapshot was already
        # written and verified (docs Section 9); it names a snapshot that
        # exists on disk but was never activated (`active_snapshot_id`
        # below still names the OLD, unchanged active release).
        _log(logger, "corpus_refresh.rejected", level="WARNING", outcome="failure", metadata={"reason": reason, "detail": detail})
        return RefreshResult(
            schema_version=REFRESH_SCHEMA_VERSION,
            status="REJECTED",
            rejection_reason=reason,
            dry_run=dry_run,
            candidate_document_count=len(candidate_documents),
            stages=stages,
            previous_active_snapshot_id=previous_active_snapshot_id,
            active_snapshot_id=previous_active_snapshot_id,
            candidate_snapshot_id=candidate_snapshot_id,
            candidate_evaluation_report=None,
            active_evaluation_report=None,
        )

    _log(
        logger,
        "corpus_refresh.started",
        outcome="in_progress",
        metadata={"candidate_document_count": len(candidate_documents), "dry_run": dry_run},
    )

    # -----------------------------------------------------------------
    # 1. VALIDATE (docs Section 17.1)
    # -----------------------------------------------------------------
    admitted_documents: list = []
    for candidate in candidate_documents:
        try:
            result = ingest_bytes(candidate.data, candidate.provenance, candidate.file_extension, authority_matrix=authority_matrix)
        except (TypeError, AttributeError, KeyError) as exc:
            stages.append(StageOutcome("VALIDATE", False, f"malformed candidate metadata: {exc}"))
            return _reject("VALIDATION_FAILED", f"malformed candidate metadata: {exc}")

        if result.document is None or result.pipeline_state not in _ACCEPTABLE_EXTRACTION_STATES:
            detail = f"candidate rejected by admission/extraction: pipeline_state={result.pipeline_state} reason_codes={result.reason_codes}"
            stages.append(StageOutcome("VALIDATE", False, detail))
            return _reject("VALIDATION_FAILED", detail)

        missing_backup_fields = [f for f in REQUIRED_PROVENANCE_FIELDS if f not in candidate.provenance]
        if missing_backup_fields:
            detail = f"candidate provenance is missing fields required to back up a release: {missing_backup_fields}"
            stages.append(StageOutcome("VALIDATE", False, detail))
            return _reject("VALIDATION_FAILED", detail)

        admitted_documents.append(AdmittedDocument(provenance=candidate.provenance, extracted_document=result.document))

    document_ids = [ad.extracted_document.document_id for ad in admitted_documents]
    if len(document_ids) != len(set(document_ids)):
        detail = "candidate contains duplicate document_id values"
        stages.append(StageOutcome("VALIDATE", False, detail))
        return _reject("VALIDATION_FAILED", detail)

    stages.append(StageOutcome("VALIDATE", True, f"{len(admitted_documents)} candidate document(s) admitted"))
    _log(logger, "corpus_refresh.validate", outcome="success", metadata={"admitted_count": len(admitted_documents)})

    # -----------------------------------------------------------------
    # 2. RE-INDEX (docs Section 17.2)
    # -----------------------------------------------------------------
    chunking_results: list = []
    for admitted in admitted_documents:
        try:
            chunking_result = chunk_document(admitted.extracted_document, chunking_config)
        except (TypeError, ValueError) as exc:
            detail = f"chunking failed for document {admitted.extracted_document.document_id!r}: {exc}"
            stages.append(StageOutcome("REINDEX", False, detail))
            return _reject("INDEXING_FAILED", detail)

        if chunking_result.chunking_status == "CHUNKING_SKIPPED":
            # [ENGINEERING RECOMMENDATION]: an admitted document that yields
            # zero indexable chunks would silently shrink the corpus below
            # what validation admitted - fail-closed rather than release a
            # candidate with less content than it claimed to add.
            detail = f"document {admitted.extracted_document.document_id!r} produced no chunks (CHUNKING_SKIPPED: {chunking_result.warnings})"
            stages.append(StageOutcome("REINDEX", False, detail))
            return _reject("INDEXING_FAILED", detail)

        chunking_results.append(chunking_result)

    all_chunks = [chunk for cr in chunking_results for chunk in cr.chunks]

    try:
        bm25_index = build_index(all_chunks, bm25_config)
    except (TypeError, ValueError) as exc:
        detail = f"BM25 indexing failed: {exc}"
        stages.append(StageOutcome("REINDEX", False, detail))
        return _reject("INDEXING_FAILED", detail)

    dense_index = None
    if embedding_model is not None:
        try:
            dense_index = build_dense_index(all_chunks, embedding_model, dense_index_config)
        except (TypeError, ValueError, RuntimeError) as exc:
            detail = f"dense indexing failed: {exc}"
            stages.append(StageOutcome("REINDEX", False, detail))
            return _reject("INDEXING_FAILED", detail)

    stages.append(StageOutcome("REINDEX", True, f"{len(all_chunks)} chunk(s) indexed (dense={'yes' if dense_index else 'no'})"))
    _log(
        logger,
        "corpus_refresh.reindex",
        outcome="success",
        metadata={"chunk_count": len(all_chunks), "dense_index_built": dense_index is not None},
    )

    # -----------------------------------------------------------------
    # 3. EVALUATE (docs Section 17.3)
    # -----------------------------------------------------------------
    eval_config = EvaluationConfig()
    try:
        candidate_per_query = _bm25_per_query_results(bm25_index, evaluation_query_set)
        candidate_report = score_retrieval_condition("BM25_RETRIEVAL", candidate_per_query, evaluation_k, config=eval_config)
    except (TypeError, ValueError) as exc:
        detail = f"evaluation failed to run against the candidate index: {exc}"
        stages.append(StageOutcome("EVALUATE", False, detail))
        return _reject("EVALUATION_FAILED", detail)

    active_report = None
    if previous_pointer is not None and evaluation_query_set:
        active_snapshot_dir = release_dir / _SNAPSHOTS_DIRNAME / previous_pointer.active_snapshot_relative_dir
        with tempfile.TemporaryDirectory(prefix="active-restore-") as scratch_dir:
            from observability.backup import restore_snapshot

            try:
                active_restored = restore_snapshot(active_snapshot_dir, Path(scratch_dir) / "restored")
            except SnapshotError as exc:
                detail = f"could not restore the active release for evaluation comparison: {exc}"
                stages.append(StageOutcome("EVALUATE", False, detail))
                return _reject("EVALUATION_FAILED", detail)

            if active_restored.bm25_index is not None:
                try:
                    active_per_query = _bm25_per_query_results(active_restored.bm25_index, evaluation_query_set)
                    active_report = score_retrieval_condition("BM25_RETRIEVAL", active_per_query, evaluation_k, config=eval_config)
                except (TypeError, ValueError) as exc:
                    detail = f"evaluation failed to run against the active index: {exc}"
                    stages.append(StageOutcome("EVALUATE", False, detail))
                    return _reject("EVALUATION_FAILED", detail)

    regressions = []
    if active_report is not None:
        for metric_name in (f"PRECISION_AT_{evaluation_k}", f"RECALL_AT_{evaluation_k}", "MEAN_RECIPROCAL_RANK"):
            active_value = _metric_value(active_report, metric_name)
            candidate_value = _metric_value(candidate_report, metric_name)
            if active_value is not None and candidate_value is not None and candidate_value < active_value:
                regressions.append(f"{metric_name} regressed ({candidate_value} < {active_value})")

    if regressions:
        detail = "candidate regressed against the active release: " + "; ".join(regressions)
        stages.append(StageOutcome("EVALUATE", False, detail))
        return _reject("EVALUATION_FAILED", detail)

    stages.append(StageOutcome("EVALUATE", True, "no regression detected against the active release (or nothing to compare against)"))
    _log(logger, "corpus_refresh.evaluate", outcome="success", metadata={"compared_against_active": active_report is not None})

    if dry_run:
        _log(logger, "corpus_refresh.dry_run_complete", outcome="success", metadata={"candidate_document_count": len(candidate_documents)})
        return RefreshResult(
            schema_version=REFRESH_SCHEMA_VERSION,
            status="DRY_RUN_COMPLETE",
            rejection_reason=None,
            dry_run=True,
            candidate_document_count=len(candidate_documents),
            stages=stages,
            previous_active_snapshot_id=previous_active_snapshot_id,
            active_snapshot_id=previous_active_snapshot_id,
            candidate_snapshot_id=None,
            candidate_evaluation_report=candidate_report,
            active_evaluation_report=active_report,
        )

    # -----------------------------------------------------------------
    # 4a. BACKUP (docs Section 9/12-16, Step 5A reused verbatim)
    # -----------------------------------------------------------------
    staging_root = release_dir / _STAGING_DIRNAME
    staging_root.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix="candidate-", dir=str(staging_root)))
    # create_snapshot refuses a non-empty/pre-existing target - mkdtemp's
    # own directory must be removed first so create_snapshot's own
    # "never silently overwrite" check creates a genuinely fresh one.
    staging_dir.rmdir()

    try:
        manifest = create_snapshot(
            staging_dir,
            documents=admitted_documents,
            chunking_results=chunking_results,
            bm25_index=bm25_index,
            dense_index=dense_index,
            corpus_lock_version=corpus_lock_version,
        )
    except (SnapshotError, TypeError, ValueError, OSError) as exc:
        shutil.rmtree(staging_dir, ignore_errors=True)
        detail = f"backup/snapshot creation failed: {exc}"
        stages.append(StageOutcome("BACKUP", False, detail))
        return _reject("BACKUP_FAILED", detail)

    final_snapshot_dir = release_dir / _SNAPSHOTS_DIRNAME / manifest.snapshot_id
    try:
        if final_snapshot_dir.exists():
            # docs Section 21 determinism: an identical candidate produces
            # the identical snapshot_id - re-releasing it is idempotent,
            # never a second write; the existing snapshot must still verify.
            verify_snapshot_integrity(final_snapshot_dir)
            shutil.rmtree(staging_dir, ignore_errors=True)
        else:
            final_snapshot_dir.parent.mkdir(parents=True, exist_ok=True)
            staging_dir.rename(final_snapshot_dir)
            verify_snapshot_integrity(final_snapshot_dir)
    except (SnapshotError, OSError) as exc:
        shutil.rmtree(staging_dir, ignore_errors=True)
        detail = f"backup/snapshot safety verification failed: {exc}"
        stages.append(StageOutcome("BACKUP", False, detail))
        return _reject("BACKUP_FAILED", detail)

    stages.append(StageOutcome("BACKUP", True, f"candidate snapshot {manifest.snapshot_id} written and verified"))
    _log(logger, "corpus_refresh.backup", outcome="success", metadata={"snapshot_id": manifest.snapshot_id})

    # -----------------------------------------------------------------
    # 4b. RELEASE (docs Section 17.4/23)
    # -----------------------------------------------------------------
    new_pointer = ReleasePointer(
        schema_version=REFRESH_SCHEMA_VERSION,
        active_snapshot_id=manifest.snapshot_id,
        active_snapshot_relative_dir=manifest.snapshot_id,
        corpus_lock_version=corpus_lock_version,
    )
    try:
        _write_release_pointer_atomic(release_dir, new_pointer)
    except OSError as exc:
        tmp_path = release_dir / f"{_POINTER_FILENAME}.tmp"
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        detail = f"release pointer update failed: {exc}"
        stages.append(StageOutcome("RELEASE", False, detail))
        return _reject("RELEASE_POINTER_FAILED", detail, candidate_snapshot_id=manifest.snapshot_id)

    stages.append(StageOutcome("RELEASE", True, f"pointer.json now points at snapshot {manifest.snapshot_id}"))
    _log(logger, "corpus_refresh.released", outcome="success", metadata={"snapshot_id": manifest.snapshot_id})

    return RefreshResult(
        schema_version=REFRESH_SCHEMA_VERSION,
        status="RELEASED",
        rejection_reason=None,
        dry_run=False,
        candidate_document_count=len(candidate_documents),
        stages=stages,
        previous_active_snapshot_id=previous_active_snapshot_id,
        active_snapshot_id=manifest.snapshot_id,
        candidate_snapshot_id=manifest.snapshot_id,
        candidate_evaluation_report=candidate_report,
        active_evaluation_report=active_report,
    )
