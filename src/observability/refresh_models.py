"""
Phase 21 corpus-refresh orchestration data shapes
(docs/PHASE_21_OBSERVABILITY_BACKUP_CORPUS_REFRESH.md Sections 17-23,
config/phase_21_observability.yaml `corpus_refresh`/`release_gate`/`dry_run`).

Plain data holders only - no ingestion/chunking/indexing/evaluation logic
here (that lives in `corpus_refresh.py`, and is otherwise entirely reused,
never reimplemented, from `ingestion`/`chunking`/`retrieval`/`evaluation`/
`observability.backup`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

REFRESH_SCHEMA_VERSION = "1.0.0"

# docs Section 17/18: the workflow is a single, fail-closed gate - a
# refresh either RELEASES (every stage passed) or is REJECTED (the first
# stage that failed says why); a dry run stops one step earlier, at
# DRY_RUN_COMPLETE, deliberately never reaching RELEASED (docs Section 19).
REFRESH_STATUSES = frozenset({"RELEASED", "REJECTED", "DRY_RUN_COMPLETE"})

# docs Section 22: one closed vocabulary naming exactly which stage a
# rejected refresh failed at - never a free-text reason used as the only
# signal for something callers may need to branch on.
REJECTION_REASONS = frozenset(
    {
        "VALIDATION_FAILED",
        "INDEXING_FAILED",
        "EVALUATION_FAILED",
        "BACKUP_FAILED",
        "RELEASE_POINTER_FAILED",
    }
)

STAGE_NAMES = frozenset({"VALIDATE", "REINDEX", "EVALUATE", "BACKUP", "RELEASE"})


def _check_non_empty_string(name: str, value) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _check_non_negative_int(name: str, value) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer, got {value!r}")


@dataclass(frozen=True)
class CandidateDocumentInput:
    """
    One raw candidate document to be admitted (docs Section 17.1) - the
    orchestrator runs the REAL Phase 3 pipeline
    (`ingestion.pipeline.ingest_bytes`) over this, never a pre-ingested
    object; that is what distinguishes this stage from
    `observability.backup`'s own `AdmittedDocument` (which packages an
    ALREADY-ingested result).
    """

    data: bytes
    provenance: dict
    file_extension: str

    def __post_init__(self):
        if not isinstance(self.data, bytes):
            raise ValueError("data must be bytes")
        if not isinstance(self.provenance, dict):
            raise ValueError("provenance must be a dict")
        _check_non_empty_string("file_extension", self.file_extension)


@dataclass(frozen=True)
class EvaluationQuery:
    """
    One synthetic evaluation query (docs Section 20) - `relevant_chunk_ids`
    is the query-set author's own STRUCTURAL expectation, exactly like
    Phase 16's `BenchmarkCase.ground_truth_origin` discipline: a
    synthetic fixture's declared expectation, never a model-generated or
    inferred one.
    """

    query_id: str
    query_text: str
    relevant_chunk_ids: frozenset
    k: int

    def __post_init__(self):
        _check_non_empty_string("query_id", self.query_id)
        _check_non_empty_string("query_text", self.query_text)
        if not isinstance(self.relevant_chunk_ids, (frozenset, set)) or any(
            not isinstance(x, str) for x in self.relevant_chunk_ids
        ):
            raise ValueError("relevant_chunk_ids must be a set/frozenset of strings")
        if isinstance(self.k, bool) or not isinstance(self.k, int) or self.k <= 0:
            raise ValueError(f"k must be a positive integer, got {self.k!r}")


@dataclass(frozen=True)
class ReleasePointer:
    """
    `[ASSUMPTION]` (docs Section 23): the smallest deterministic
    local-filesystem release-pointer mechanism compatible with the
    contract - a single JSON file naming which snapshot directory (under
    `release_dir/snapshots/`) is currently active. Never a database,
    never an external service.
    """

    schema_version: str
    active_snapshot_id: str
    active_snapshot_relative_dir: str
    corpus_lock_version: str

    def __post_init__(self):
        _check_non_empty_string("schema_version", self.schema_version)
        _check_non_empty_string("active_snapshot_id", self.active_snapshot_id)
        _check_non_empty_string("active_snapshot_relative_dir", self.active_snapshot_relative_dir)
        _check_non_empty_string("corpus_lock_version", self.corpus_lock_version)


@dataclass(frozen=True)
class StageOutcome:
    """One stage's pass/fail record, in the fixed VALIDATE->REINDEX->EVALUATE->BACKUP->RELEASE order (docs Section 17/18)."""

    stage: str
    passed: bool
    detail: str

    def __post_init__(self):
        if self.stage not in STAGE_NAMES:
            raise ValueError(f"stage must be one of {sorted(STAGE_NAMES)}, got {self.stage!r}")
        if not isinstance(self.passed, bool):
            raise ValueError("passed must be a bool")
        _check_non_empty_string("detail", self.detail)


@dataclass(frozen=True)
class RefreshResult:
    """
    The top-level result of one `corpus_refresh.run_corpus_refresh` call
    (docs Section 17/18/19/22). `status == "REJECTED"` if and only if
    `rejection_reason` is set - the only representation of "which gate
    failed" this dataclass carries (mirrors Phase 16's own
    `applicable`/`value` zero-denominator discipline: one boolean, one
    optional companion field, never a free-text-only signal).
    """

    schema_version: str
    status: str
    rejection_reason: Optional[str]
    dry_run: bool
    candidate_document_count: int
    stages: list  # list[StageOutcome], in stage order, stopping at the first failure
    previous_active_snapshot_id: Optional[str]
    active_snapshot_id: Optional[str]  # the snapshot id that IS active after this call returns
    candidate_snapshot_id: Optional[str]  # set only once a candidate snapshot was actually written to disk (BACKUP stage reached)
    candidate_evaluation_report: Optional[object]  # evaluation.models.ComponentBenchmarkReport, when the EVALUATE stage ran
    active_evaluation_report: Optional[object]  # evaluation.models.ComponentBenchmarkReport, when a prior active release existed and was measured for comparison

    def __post_init__(self):
        _check_non_empty_string("schema_version", self.schema_version)
        if self.status not in REFRESH_STATUSES:
            raise ValueError(f"status must be one of {sorted(REFRESH_STATUSES)}, got {self.status!r}")
        if self.rejection_reason is not None and self.rejection_reason not in REJECTION_REASONS:
            raise ValueError(f"rejection_reason must be one of {sorted(REJECTION_REASONS)} or None, got {self.rejection_reason!r}")
        if (self.status == "REJECTED") != (self.rejection_reason is not None):
            raise ValueError("rejection_reason must be set if and only if status == 'REJECTED'")
        if not isinstance(self.dry_run, bool):
            raise ValueError("dry_run must be a bool")
        if self.status == "RELEASED" and self.dry_run:
            raise ValueError("a dry run must never report status == 'RELEASED' (docs Section 19)")
        _check_non_negative_int("candidate_document_count", self.candidate_document_count)
        if not isinstance(self.stages, list) or any(not isinstance(s, StageOutcome) for s in self.stages):
            raise ValueError("stages must be a list of StageOutcome")
        if self.status == "RELEASED" and self.candidate_snapshot_id != self.active_snapshot_id:
            raise ValueError("a RELEASED refresh must have candidate_snapshot_id == active_snapshot_id")
