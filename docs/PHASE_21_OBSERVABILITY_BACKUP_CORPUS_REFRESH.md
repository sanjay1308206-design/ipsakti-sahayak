# PHASE 21 — OBSERVABILITY, BACKUP & CORPUS REFRESH

Status: CONTRACT DOCUMENT ONLY (no Phase 21 implementation, test, or dependency exists yet)
Authoritative source: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`
Governed by: `docs\MASTER_REFERENCE_LOCK.md`, `docs\DEVELOPMENT_RULES.md`, `docs\PHASE_TRACKER.md` (`CAP-21`), `config\acceptance_contract.yaml`
Reuses (never redefines ownership of): `src\api\errors.py`, `src\citation\metrics.py`, `src\safety\evaluator.py`, `src\generation\models.py` (`ABSTENTION_REASONS`), `src\evaluation\benchmark.py`, `src\evaluation\metrics.py`, `src\retrieval\evaluation.py`, `src\ingestion\pipeline.py`, `src\ingestion\admission.py`, `config\corpus_lock.yaml`
Implementation: none yet — this document is Step 1 only.

**This is a contract, not an implementation.** No Python/TypeScript code, no test, no dependency, no deployment change accompanies this document. It exists so that Phase 21's actual build (a later, separate step) has an explicit, source-grounded scope to build against, matching the pattern every completed phase already used (contract document before code).

---

## 1. Phase 21 objective

`[OFFICIAL SOURCE]` `docs\PHASE_TRACKER.md` / `config\acceptance_contract.yaml` `CAP-21` ("Observability, Backup & Corpus Refresh"): goal *"Operate the system after deployment."* Required behavior: metrics, logs, latency tracking, retrieval diagnostics, citation rejection rate, abstention rate, backups, restore tests, corpus refresh pipeline. Required test: backup/restore test + corpus refresh dry run. Acceptance criterion: *"A corpus update can be validated, re-indexed, evaluated, and released safely."*

## 2. Scope

`[ENGINEERING RECOMMENDATION]` Phase 21 adds exactly two capabilities to the existing, unmodified Phase 0–20 system: (a) a way to observe what the deployed app already does (metrics/logs/latency/diagnostics, computed from data Phases 9/13/16 already produce), and (b) a way to safely change what corpus the system serves (backup → refresh → validate → evaluate → release), without ever regressing Phase 0–20 behavior. It is an operational layer over the existing system, not a new domain capability.

## 3. In-scope capabilities

`[OFFICIAL SOURCE, from CAP-21]`
- Structured metrics: latency, retrieval diagnostics, citation rejection rate, abstention rate (Sections 6–11).
- Structured logging convention (Section 7).
- A defined backup target, format, and integrity-verified restore procedure (Sections 12–16).
- A corpus-refresh workflow with an explicit validate→index→evaluate→release gate and a dry-run mode (Sections 17–19).

## 4. Explicit non-goals

`[ENGINEERING RECOMMENDATION]` Phase 21 does **not**: reimplement any Phase 3–16 domain logic (ingestion, chunking, retrieval, evidence, citation, generation, classification, jurisdiction, safety, multilingual, review) — it only observes and orchestrates what those phases already do; introduce a database, ORM, or persistence layer (Section 12 explains why); introduce authentication/authorization, rate limiting, or a reviewer UI (unchanged Phase 17/19 boundaries); modify `render.yaml`, `requirements-render.txt`, or any Phase 20 file; promote Gemini or any other `[DEFERRED]` technology out of its deferred status; implement CI/CD pipeline automation (Phase 22) or production validation against the Final Production Gate (Phase 23) — Phase 21 may define an interface a later phase calls, but never that phase's own implementation (`docs\MASTER_REFERENCE_LOCK.md` Section I, Phase Isolation Rule).

## 5. Existing capabilities that must be reused, not duplicated

`[OFFICIAL SOURCE]` Per `docs\DEVELOPMENT_RULES.md` Rule 2 (Clean Implementation) and the readiness inspection already completed:
- `src\api\errors.py` — existing server-side exception logging (`logger.exception`, Phase 17 Section Y). Phase 21 extends the logging *convention* around this, never replaces or relocates it.
- `src\citation\metrics.py` — `CitationCoverageMetrics` (Phase 9): `total_references`, `valid_count`, `invalid_count`, `unresolved_count`, `unique_valid_evidence_id_count`, `citation_integrity_validation_rate`. Citation rejection rate (Section 10) is derived from these fields, never recomputed independently.
- `src\generation\models.py` — `ABSTENTION_REASONS` (`REASON_NO_EVIDENCE_AVAILABLE`, `REASON_NO_VALID_CITATIONS_PRODUCED`) and `GroundedResponse.abstention_reason` (Phase 10). `src\safety\evaluator.py` — `SafetyDecision.safety_status` (`SAFE_TO_PRESENT` / `ABSTAIN` / `ESCALATE`, Phase 13). Abstention rate (Section 11) is derived from these two closed vocabularies together, never a third, independently-invented status field.
- `src\evaluation\benchmark.py` / `src\evaluation\metrics.py` — the existing `safe_rate`/`build_rate_result`/`build_not_run_result`/`compute_report_id` pattern (Phase 16), including its zero-denominator policy (`None`, never fabricated `0.0`). Phase 21 metrics/evaluation reporting must follow this same pattern, not a second one.
- `src\retrieval\evaluation.py` — `precision_at_k`/`recall_at_k`/`reciprocal_rank`/`mean_reciprocal_rank` (Phase 5/6, standard IR definitions). Retrieval diagnostics (Section 9) reuse these verbatim.
- `src\ingestion\pipeline.py` (`ingest_bytes`/`ingest_document`) and `src\ingestion\admission.py` (`check_admission_boundary`, `load_authority_matrix`) — the real admission→extraction pipeline (Phase 3). The corpus-refresh workflow (Section 17) composes these, never reimplements admission or extraction.
- `config\corpus_lock.yaml` — binding corpus governance (Phase 2). A refresh can never admit a source family, jurisdiction, or document this file does not already permit; Phase 21 does not modify it.

## 6. Metrics architecture

`[ENGINEERING RECOMMENDATION]` A metrics-aggregation module (not yet created) that computes structured, deterministic reports from already-real Phase 9/13/16 objects — mirroring `evaluation.benchmark`'s own "accepts already-computed real objects, never builds its own" convention (`docs\PHASE_16_EVALUATION_AND_RED_TEAM.md`, `benchmark.py` module docstring). It must never call a decision-making function itself (no re-classification, re-grounding, or re-safety-evaluation for measurement purposes) — it only reads results Phases 8–16 already produced. `[DEFERRED]` beyond Phase 21: any external metrics-export protocol (Prometheus exposition format, OpenTelemetry, a hosted dashboard) — see Section 24.

## 7. Structured logging convention

`[ENGINEERING RECOMMENDATION]` Extends, not replaces, `src\api\errors.py`'s existing Python stdlib `logging` usage: a consistent, structured (but still stdlib-only) log record shape for operational events (request outcome, corpus-refresh stage transitions, backup/restore events) — server-side only, never returned to a client (unchanged Phase 17 Section M/Y invariant). No secret, credential, or full raw query/evidence payload is logged beyond what Phase 17 already logs today. `[DEFERRED]`: any log-aggregation service (ELK, Loki, a hosted log drain) — Section 24.

## 8. Latency tracking

`[ENGINEERING RECOMMENDATION]` Timing wraps the existing `application.service.ApplicationService.query` call from the outside (an instrumentation layer calling the unmodified Phase 17 orchestrator), never edits inside it — consistent with "do not modify Phase 0–20 implementation." Records wall-clock duration per request as a structured log/metric field. `[ASSUMPTION]`: per-stage latency (classification vs. retrieval vs. generation, individually) is out of scope unless `ApplicationService` already exposes stage boundaries without modification — to be confirmed at implementation time, not assumed here. This assumption is invalidated if a future inspection finds `ApplicationService` already exposes per-stage timing hooks; if so, per-stage latency becomes in-scope without a contract change.

## 9. Retrieval diagnostics

`[OFFICIAL SOURCE]` Reuses `retrieval.evaluation.precision_at_k`/`recall_at_k`/`reciprocal_rank`/`mean_reciprocal_rank` verbatim (Section 5) against whatever synthetic/real query set is available at measurement time (Section 20). Phase 21 does not define new IR metrics.

## 10. Citation rejection-rate definition

`[ENGINEERING RECOMMENDATION]` `citation_rejection_rate = (invalid_count + unresolved_count) / total_references`, applying `evaluation.metrics.safe_rate`'s zero-denominator policy (Section 5) — `None`/not-applicable when `total_references == 0`, never a fabricated `0.0`. Sourced directly from `citation.metrics.CitationCoverageMetrics`, never recomputed by re-reading raw citation references.

## 11. Abstention-rate definition

`[ENGINEERING RECOMMENDATION]` `abstention_rate = count(safety_status == "ABSTAIN") / total_requests_evaluated`, again via `safe_rate`. Optionally broken down by `GroundedResponse.abstention_reason` (`generation.models.ABSTENTION_REASONS`) when that information is available to the aggregator, never a new abstention taxonomy invented in this phase.

## 12. Backup target

`[ENGINEERING RECOMMENDATION]`/`[ASSUMPTION]` **The repository currently has no database, no ORM, no persistence layer, and no persisted production corpus/index anywhere** — confirmed by the Phase 21 readiness inspection and unchanged by Phase 17 Section W (`[DEFERRED]`, fully stateless) and `docs\MASTER_REFERENCE_LOCK.md` Section E (SQLite→PostgreSQL is listed only as an eventual *production target*, never built in Phase 0–20). Therefore **Phase 21 does not define a database backup** — inventing one would violate Rule 6 (No Premature Dependencies) and would have nothing real to back up.

`[ASSUMPTION]` The Phase 21 backup target is instead **a corpus/index snapshot artifact**: the output of a corpus-refresh run — the admitted document set (Phase 3 `IngestionResult`s), the derived chunk set (Phase 4), and the built retrieval index state (Phase 5 BM25 state / Phase 6 FAISS index, when either exists) — packaged together as one versioned, content-hashed directory or archive on the local filesystem of whatever environment runs the refresh. This is an assumption, not an official requirement, because CAP-21 names "backups" without specifying the artifact.

**What would invalidate this assumption:** (a) a future phase introduces a real database or managed persistence layer to hold corpus/index state instead of filesystem artifacts — this contract would then need revising, not silently reinterpreted; (b) explicit instruction promotes cloud object storage (S3-compatible or otherwise) into scope — Section 24 keeps this `[DEFERRED]` until that happens.

## 13. Backup format/contents

`[ASSUMPTION]` A backup unit contains: (1) the set of admitted source documents' provenance records (Phase 2/3 schema fields — `document_id`, `source_family_id`, `content_hash`, `provenance_status`, `validation_status`, etc., per `config\corpus_provenance_schema.yaml`, unchanged); (2) the derived chunk set (Phase 4, content-addressed per its own existing identity scheme); (3) the built retrieval index artifacts (Phase 5/6, whichever exist); (4) one manifest file recording a snapshot ID, creation timestamp, the `config\corpus_lock.yaml` `lock_version` in effect at capture time, and a content hash of the whole snapshot. No document's raw bytes are duplicated beyond what ingestion already retains; no credential or secret is ever included (unchanged Phase 17/19/20 invariant, restated here rather than re-litigated).

## 14. Backup integrity verification

`[ENGINEERING RECOMMENDATION]` Reuses `ingestion.hashing.compute_content_hash` (Phase 3) for per-document integrity, extended by one snapshot-level manifest hash (SHA-256 over the manifest's own canonical fields, following every other phase's own deterministic-identity convention — e.g. `generation.generator.compute_response_id`, Phase 10). A backup is "valid" only if every per-document hash and the manifest hash re-verify; any mismatch is a hard failure (Section 22), never a silent partial-restore.

## 15. Restore procedure

`[ENGINEERING RECOMMENDATION]` Unpack the snapshot; re-verify every hash in Section 14 before anything is loaded; reject the entire snapshot (not a partial subset) on any mismatch; reconstruct the admitted document set, chunk set, and index state from the verified artifacts using the same, unmodified Phase 3–6 loaders — never a second, parallel deserialization path.

## 16. Restore success criteria

`[ENGINEERING RECOMMENDATION]` A restore is proven successful only when: (a) every integrity hash re-verifies (Section 14); (b) the restored corpus/index, when run through the same synthetic evaluation query set used at backup time (Section 9/20), reproduces byte-identical `precision_at_k`/`recall_at_k`/`reciprocal_rank` results — equivalence is proven by deterministic re-measurement, never assumed from a successful unpack alone.

## 17. Corpus-refresh workflow

`[OFFICIAL SOURCE, restated from CAP-21's acceptance criterion]` **validate → re-index → evaluate → release** — composed entirely from existing, unmodified stages:
1. **Validate:** `ingestion.admission.check_admission_boundary` + `ingestion.pipeline.ingest_bytes`/`ingest_document` (Phase 3) against the unmodified `config\corpus_lock.yaml`/`config\authority_matrix.yaml` (Phase 2) — a document that fails admission never proceeds.
2. **Re-index:** the existing, unmodified Phase 4 (chunking) → Phase 5/6 (BM25/dense index build) stages, run against the newly-admitted document set plus whatever the previous release already contained.
3. **Evaluate:** the existing, unmodified `evaluation.benchmark`/`retrieval.evaluation`/`citation.metrics` machinery (Phase 9/16), run against the candidate new index — never skipped, never replaced by a weaker check.
4. **Release:** only after validate, re-index, and evaluate all succeed (Section 18) does the candidate snapshot (Section 12) become the active one.

## 18. Validate → re-index → evaluate → release gate

`[ENGINEERING RECOMMENDATION]` **The safe rule is validate → index → evaluate → release, never update → release → discover problems.** The gate is a single explicit precondition: a candidate corpus/index snapshot may become "active" only if every one of Sections 17's four stages reports success; a failure at any stage halts the workflow before release and leaves the previously-active, already-evaluated snapshot serving unchanged (Section 22/23). This is a fail-closed gate, not a best-effort one — an invalid or partially-evaluated update can never become the active release.

## 19. Dry-run behavior

`[ENGINEERING RECOMMENDATION]` A dry run executes validate → re-index → evaluate in full, against real (or, today, synthetic — Section 20) inputs, and reports the result exactly as a real run would, but never performs the release step (Section 17.4) — the currently-active snapshot is left untouched regardless of the dry run's outcome. This is CAP-21's own named test requirement ("corpus refresh dry run") and is the primary mechanism for proving the gate works before it is ever exercised against real production data.

## 20. Synthetic-fixture requirements

`[OFFICIAL SOURCE, consistent with every Phase 8–16 test]` **No real corpus is ingested anywhere in this repository today** (confirmed repeatedly by Phase 10/17's own regression checks). Phase 21's backup/restore and corpus-refresh tests therefore exercise the workflow exclusively against small, synthetic fixtures (reusing `tests\_pdf_fixtures.py`/`_provenance_fixtures.py`/`_chunk_fixtures.py`/etc. where they already fit, following the same `synthetic=True`, `SYNTHETIC-*`-ID convention Phase 16 already established), never a real regulatory document. This is not a Phase 21 limitation invented here — it is the honest, pre-existing state of the whole repository, restated for this phase.

## 21. Determinism requirements

`[ENGINEERING RECOMMENDATION]` Snapshot IDs, manifest hashes, and evaluation report IDs must be deterministic functions of their own canonical inputs (Section 14), never a random UUID or wall-clock timestamp used as identity — matching every prior phase's own identity convention (Phase 8 `evidence_id`, Phase 10 `response_id`, Phase 16 `compute_report_id`, Phase 17 `compute_request_id`). Given identical inputs, a dry run and a real run of the same candidate corpus must produce identical evaluation results.

## 22. Failure handling

`[ENGINEERING RECOMMENDATION]`, fail-closed at every stage:
- **Restore failure** (integrity mismatch, Section 14/16): the restore is rejected in full; the environment continues serving whatever was active before the restore attempt; the failure is logged (Section 7), never silently retried with a different snapshot.
- **Corpus validation failure** (Section 17.1): the offending document(s) are rejected with the same `IngestionResult`/admission reason codes Phase 3 already produces; the refresh does not proceed to re-indexing.
- **Retrieval/indexing failure** (Section 17.2): the refresh halts before evaluation; the previously-active index remains active and serving.
- **Evaluation failure** (Section 17.3 — e.g., a measured regression against the previously-active snapshot's own scores): the candidate snapshot is never released; this is treated identically to a validation or indexing failure for gating purposes (Section 18).
- **In every case above, an invalid or failed update can never become the active corpus/index** — this is the literal safety property CAP-21's acceptance criterion requires.

## 23. Release/rollback behavior

`[ENGINEERING RECOMMENDATION]` "Release" is a pointer/reference switch to a fully-verified snapshot (Section 12–16), never an in-place mutation of the previously-active snapshot — the prior snapshot remains intact and immediately restorable (Section 15) after a new release, giving rollback as "restore the previous snapshot ID" rather than a separately-invented rollback mechanism. `[ASSUMPTION]`: the exact release-pointer mechanism (a file, an environment variable, a manifest entry) is an implementation detail deferred to Step 2+, not fixed here — this contract only requires that whatever mechanism is chosen preserves the previous snapshot untouched until an operator (or a later Phase 22 pipeline) explicitly discards it.

## 24. Dependency constraints

`[OFFICIAL SOURCE]` Per `docs\DEVELOPMENT_RULES.md` Rule 6 (No Premature Dependencies): Phase 21 introduces **no new dependency** unless a specific requirement above cannot be met with the Python standard library plus what Phase 0–20 already installed. Explicitly `[DEFERRED]`, not to be introduced by this phase: PostgreSQL, SQLite, Redis, S3 or any cloud object storage, any paid monitoring service, OpenTelemetry, Prometheus, Grafana, any external APM, or any external analytics platform. None of these is named by CAP-21's own required-behavior text; none may be added speculatively. If a future, explicit instruction determines one of these is actually necessary, that promotion must be recorded the same way Rule 9 already requires for any other deferred technology (explicit instruction + measurable benchmarked evidence) — never assumed here.

## 25. Render Free constraints

`[EXTERNAL RESEARCH]`/`[ENGINEERING RECOMMENDATION]` Phase 20's deployment target (`docs\PHASE_20_DEPLOYMENT_ENGINEERING.md`) is Render Free, which this contract does not claim provides persistent backup storage or production-grade persistence of any kind — no such claim is made anywhere in Phase 20's own documentation, and none is invented here. Phase 21's backup/restore mechanism (Section 12–16) must remain compatible with Render Free's actual constraints (no guaranteed persistent disk across deploys) by design — its target artifact is a self-contained, content-hashed snapshot that can be produced, verified, and restored from any environment (a developer's machine, CI, or a Render instance with attached storage, if one is ever provisioned), never assuming Render Free itself durably retains it between deploys. This section does not modify `render.yaml` or any other Phase 20 file, and none is required for Phase 21's own scope to be defined.

## 26. Security/adversarial considerations

`[ENGINEERING RECOMMENDATION]` A corpus-refresh workflow is a new trust boundary (untrusted or malformed candidate documents reaching the admission boundary) and must inherit, not weaken, Phase 3's existing admission/integrity checks (Section 17.1) and Phase 19's existing adversarial-input discipline (malformed input rejected explicitly, never a silent crash or a fabricated success). A backup/restore path must never become a mechanism for smuggling an unvalidated document past `config\corpus_lock.yaml`'s governance (Section 5) — restore always re-runs the same integrity/admission checks a fresh ingestion would, never a trusted-by-default fast path.

## 27. Test strategy

`[OFFICIAL SOURCE]` Per `docs\MASTER_REFERENCE_LOCK.md` Section H (Testing Rule): `pytest`, covering — where applicable — happy path (a valid synthetic corpus update refreshes, evaluates, and releases successfully), edge cases (an empty candidate set, a candidate identical to the current active snapshot), negative cases (a document that fails admission), adversarial cases (a malformed/oversized/adversarially-crafted candidate document, a tampered snapshot manifest), schema/contract behavior (manifest shape, metrics report shape), deterministic behavior (Section 21), regression behavior (a `tests\test_phase_21_regression.py` asserting Phase 0–20 behavior/dependency sets/source-discipline remain unchanged, following every prior phase's own regression-file convention), and the two CAP-21-named tests explicitly: a backup/restore round-trip test (Section 16) and a corpus-refresh dry run (Section 19).

## 28. Acceptance criteria

`[OFFICIAL SOURCE, CAP-21]` Phase 21 is acceptance-ready only when all of the following hold, each traced to a specific test:
1. A backup/restore test exists and passes (Section 16's equivalence proof).
2. A corpus-refresh dry run exists and passes (Section 19).
3. A corpus update can be validated → re-indexed → evaluated → safely released end-to-end (Section 17/18), proven for at least one synthetic candidate (Section 20).
4. An invalid or failed update can never become the active corpus/index (Section 22) — proven adversarially, not merely asserted.
5. Full Phase 0–20 regression suite remains passing, unweakened (currently 2920/2920) — Phase 21 adds tests, never relaxes an existing one.

## 29. Deferred items

`[DEFERRED]`
- Any external metrics/log/monitoring service (Section 6/7/24).
- A real database or managed persistence layer for corpus/index state (Section 12).
- Cloud object storage for backups (Section 12/24).
- Per-stage (as opposed to per-request) latency breakdown, pending confirmation it's obtainable without modifying `ApplicationService` (Section 8).
- Advanced observability/analytics beyond this phase's own operational scope (`MASTER_REFERENCE_LOCK.md` Section J, `acceptance_contract.yaml` `DEF-07`) — unchanged and not promoted by this document.
- CI/CD automation of the refresh workflow (Phase 22's own scope) and production-validation sign-off against the Final Production Gate (Phase 23's own scope, `MASTER_REFERENCE_LOCK.md` Section K) — this contract may define the interface a later phase calls but implements neither.
- A live Gemini/Qwen/Bhashini provider — remains Phase 10/14's own `[DEFERRED]` boundary; Phase 21 is purely operational and does not touch it.

## 30. Phase exit criteria

`[ENGINEERING RECOMMENDATION]` Phase 21 may be marked DONE only when: implementation exists for Sections 6–19 exactly as scoped here (no more, no less); every test in Section 27 exists and passes; Section 28's five acceptance criteria are each demonstrated, not merely claimed; the full repository regression suite passes at a count no lower than today's 2920 (new tests only added, none removed or weakened); no Phase 0–20 file was modified to accommodate Phase 21 except through an explicitly-disclosed, reviewed change following the same pattern already used when a later phase legitimately extended an earlier phase's own regression guard (e.g., Phase 6 relaxing Phase 4/5's dependency checks, Phase 17 dropping `fastapi` from ten earlier forbidden-dependency lists) — never a silent edit; and `docs\PHASE_TRACKER.md`'s Phase 21 row is updated to reflect the real, validated implementation status, exactly as every prior completed phase's row already does.
