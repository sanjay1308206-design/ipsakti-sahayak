"""
Phase 21 - Observability, Backup & Corpus Refresh
(docs/PHASE_21_OBSERVABILITY_BACKUP_CORPUS_REFRESH.md,
config/phase_21_observability.yaml).

This package is the OPERATIONAL AGGREGATION/REPORTING layer only - it
never re-implements citation validation (Phase 9), safety/abstention
decisions (Phase 13), or retrieval scoring (Phase 5/6). It only reads
already-real, already-validated Phase 8-16 objects and turns them into a
structured, deterministic operational metrics report, exactly like
`evaluation.benchmark` already does for Phase 16's own benchmark scoring.

Step 3 scope: operational metrics aggregation (`metrics.py`, `models.py`).
Step 4 scope: a structured operational logging convention (`logging.py`)
that extends, never replaces, `src/api/errors.py`'s existing stdlib
`logging` usage. Step 5a scope: corpus/index backup and safe restore
(`backup.py`, `backup_models.py`) - a filesystem snapshot packaging layer
over already-real Phase 3/4/5/6 output, never a database (docs Section
12, `[ASSUMPTION]`). Step 5b scope: corpus-refresh orchestration
(`corpus_refresh.py`, `refresh_models.py`) - a fail-closed VALIDATE ->
RE-INDEX -> EVALUATE -> (BACKUP -> RELEASE) pipeline composing existing
Phase 3/4/5/6/16 functions plus this package's own Step 5a backup/restore,
with a small local-filesystem release-pointer mechanism (docs Section 23,
`[ASSUMPTION]`) - never a database or external service. This package does
not yet implement Phase 22 CI/CD or Phase 23 production validation.
"""
