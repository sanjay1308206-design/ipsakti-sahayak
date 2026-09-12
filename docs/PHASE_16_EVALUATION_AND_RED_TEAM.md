# PHASE 16 — EVALUATION + RED-TEAM BENCHMARK

Status: CONTRACT + IMPLEMENTATION DOCUMENT (Phase 16 deliverable)
Authoritative source: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`
Governed by: `docs\MASTER_REFERENCE_LOCK.md`, `docs\DEVELOPMENT_RULES.md`, `docs\PHASE_05_BM25_BASELINE.md`, `docs\PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md`, `docs\PHASE_07_HYBRID_FUSION_AND_RERANKING.md`, `docs\PHASE_09_CITATION_VALIDATION.md`, `docs\PHASE_13_CONFIDENCE_SAFETY_ABSTENTION.md`
Machine-readable counterparts: `config\evaluation_contract.yaml`, `config\redteam_cases.yaml`
Implementation: `src\evaluation\models.py`, `metrics.py`, `benchmark.py`, `redteam.py`, `runner.py`, `serialize.py`

**This phase measures the system as it actually is.** It answers "how do we know it works?" — it never changes retrieval algorithms, classifier rules, jurisdiction logic, citation validation, grounding logic, safety thresholds, multilingual logic, or human-review semantics to make a number look better. Where a benchmark fails, this phase reports the failure and identifies the responsible component; it never hides a failure or auto-fixes it inside the evaluator.

---

## A. Objective

`[OFFICIAL SOURCE]` `docs\PHASE_TRACKER.md`'s Phase 16 entry: *"Prove the system works instead of relying on demo impressions... Regression suite runs automatically and results are reproducible."* This phase builds the reusable metrics/comparison/reporting layer that turns Phase 0-15's own real behavior into structured, deterministic, versioned evidence — component by component and end-to-end — plus a fixed, deterministic red-team benchmark.

## B. Scope

In scope: a structured `BenchmarkCase`/`RedTeamCase` schema; deterministic scoring/reporting (`EvaluationResult`, `ComponentBenchmarkReport`, `RedTeamResult`, `RedTeamSummary`, `FailureTriageEntry`, `EvaluationReport`); a unified wrapper over Phase 5/6/7's retrieval metrics and Phase 9's citation-coverage metrics; fresh (never-before-existing) benchmark scoring for classification (Phase 11), jurisdiction (Phase 12), grounding (Phase 10), safety (Phase 13), multilingual (Phase 14), and human-review (Phase 15), since none of those phases exposed a reusable `src/` evaluation API of their own (Section D); ten controlled end-to-end cases (A-J); a fixed, 21-category red-team catalogue with precise attack-success definitions; deterministic serialization.

Out of scope (no code for any of these exists anywhere in `src\evaluation\`): changing retrieval/classification/jurisdiction/citation/grounding/safety/multilingual/human-review behavior; a large, authoritative, human-validated real-regulatory benchmark (`[DEFERRED]`, Section AC); semantic claim/evidence entailment (remains Phase 9's own `[DEFERRED]` boundary); FastAPI productization or API endpoints (Phase 17); a React frontend (Phase 18); project-wide adversarial security hardening (Phase 19); deployment engineering (Phase 20); observability, backup, or corpus refresh (Phase 21); CI/CD (Phase 22); production validation (Phase 23).

## C. Non-Scope

`[ENGINEERING RECOMMENDATION]` Explicitly, Phase 16 is not a new retrieval/generation/classification feature, not a database, not a persistent benchmark-history store, and not a statistics library. It performs zero write operations against any earlier phase's objects — every function in `src\evaluation\` reads already-computed real objects and returns a new, independent Phase-16-owned result.

## D. Evaluation Philosophy

`[ENGINEERING RECOMMENDATION]` **`src/evaluation/` is a metrics/comparison/reporting layer, not a duplicate pipeline orchestrator.** Inspection of every earlier phase (Section B) found exactly one genuine reusable production evaluation module, `retrieval.evaluation` (Phase 5/6, `precision_at_k`/`recall_at_k`/`mean_reciprocal_rank`) — its own docstring explicitly assigns Phase 16 the job of owning "the full evaluation harness." `citation.metrics.compute_citation_coverage` (Phase 9) is the second. Classification (11), jurisdiction (12), grounding (10), safety (13), multilingual (14), and human-review (15) each had their own **ad hoc, test-only** benchmark (`tests/test_phase_XX_evaluation.py`), never a reusable `src/` API. Phase 16 therefore: (1) wraps the two existing production metric modules unchanged, and (2) builds fresh scoring/reporting for the rest — but the actual REAL-OBJECT CONSTRUCTION (building an `EvidencePack`, calling `classify()`, `resolve_jurisdiction()`, `evaluate_safety()`, `deliver_response()`, `review.workflow.apply_action()`) happens in `tests/test_phase_16_*.py`, reusing the project's existing `tests/_*_fixtures.py` modules exactly like every earlier phase's own evaluation test already did. This keeps `src/evaluation/` free of duplicated pipeline-construction logic and free of any mutating import.

## E. Benchmark Data Policy

`[OFFICIAL SOURCE]`/`[DEFERRED]` No internet scraping, no fabricated "official" legal answers, no fake regulatory claims presented as ground truth anywhere in this phase. Every benchmark case in this repository is one of: (1) an existing synthetic fixture already used by Phase 5-15's own tests (`tests/_*_fixtures.py`), (2) a small, additional synthetic corpus/query set following the exact same `SYNTHETIC-BENCH-*` naming convention Phase 5-9 already established, or (3) a controlled, hand-constructed synthetic adversarial case (the 21-category red-team catalogue). **A large, authoritative, human-validated real-regulatory benchmark is `[DEFERRED]`** — this repository does not contain one, and none is fabricated here.

## F. Ground-Truth Discipline

`[ENGINEERING RECOMMENDATION]` Every `BenchmarkCase.ground_truth_origin` is exactly one of `SYNTHETIC_EXPECTATION` (a hand-constructed synthetic case with a known, deterministic correct answer — e.g. an empty query must classify `UNKNOWN`), `STRUCTURAL_EXPECTATION` (a property the pipeline's own contracts already guarantee — e.g. a `SAFE_TO_PRESENT` decision must have a non-`NOT_APPLICABLE` engineering signal), `AUTHORITATIVE_EXPECTATION` (would require a real, human-verified regulatory answer — **no case in this repository currently uses this value**, since no authoritative benchmark exists yet, Section E), or `SECURITY_EXPECTATION` (an adversarial case whose correct outcome is "the attack must not succeed"). A model-generated expectation is never silently treated as authoritative — there is no code path anywhere that infers `ground_truth_origin` from model output.

## G. Benchmark Schema

`[ENGINEERING RECOMMENDATION]` `evaluation.models.BenchmarkCase`: `case_id`, `category` (one of `COMPONENT_NAMES`), `ground_truth_origin`, `input_summary`, `expected_behavior` (all required), plus optional `expected_evidence_ids`/`expected_jurisdiction`/`expected_classification_state`/`expected_safety_status`/`expected_review_status`/`expected_language` (never forced onto a case where irrelevant — e.g. a classification case carries no `expected_jurisdiction`), `adversarial`/`synthetic` (bools), `notes`. `evaluation.models.RedTeamCase` is the adversarial counterpart: `attack_category` (one of 21 closed values), `attack_input_summary`, `target_component`, `expected_security_property`, `expected_result` (`BLOCKED`/`REJECTED`/`INERT`), `severity`/`severity_rationale` (categorical, never a CVSS score, and required together).

## H. Retrieval Evaluation

`[OFFICIAL SOURCE — Manning/Raghavan/Schütze, standard IR literature, reused via Phase 5/6's own docstring attribution]` `evaluation.benchmark.score_retrieval_condition` wraps Phase 5/6's own `precision_at_k`/`recall_at_k`/`mean_reciprocal_rank` (never reimplemented) over caller-supplied `(query_id, retrieved_chunk_ids, relevant_chunk_ids)` tuples, produced by a REAL BM25/dense/RRF/reranked call (`tests/test_phase_16_retrieval.py`, reusing the exact same synthetic corpus/query/relevance protocol as `tests/test_phase_07_evaluation.py` for comparison fairness). Report fields (docs "RETRIEVAL EVALUATION"): dataset size (6 synthetic chunks), query count (3), K (3), relevant-document/chunk definition (an exact set of `chunk_id`s per query, hand-declared), metric, result, limitations (fully disclosed below).

## I. BM25 Evaluation

`[ENGINEERING RECOMMENDATION]` Phase 5's own BM25 implementation and benchmark are completely untouched — `score_retrieval_condition("BM25_RETRIEVAL", ...)` is a unified reporting interface OVER it, never a replacement. No BM25 parameter (`k1`, `b`) is changed anywhere in this phase.

## J. Dense Evaluation

`[OFFICIAL SOURCE]` Phase 6's own dense-retrieval implementation and benchmark are completely untouched. **BGE-M3 REAL-MODEL QUALITY — NOT VALIDATED.** Every dense-retrieval report in this phase carries an explicit `REAL_MODEL_RETRIEVAL_QUALITY` result with `applicable=False` and an explanation naming exactly this gap — `FakeEmbeddingModel` is used throughout, exactly like Phase 6's own disclosed limitation. The already-cached MiniLM sanity check Phase 6 ran as a one-off plumbing verification is never cited here as evidence of BGE-M3 quality (per explicit instruction).

## K. Hybrid/RRF/Reranking Evaluation

`[OFFICIAL SOURCE]` `tests/test_phase_16_retrieval.py::test_four_way_comparison_does_not_claim_unmeasured_improvement` measures BM25/dense/RRF/RRF+reranker over the identical query set, relevance judgments, and cutoff — exactly Phase 7's own comparison-fairness protocol. **No assertion claims RRF or reranking improves over BM25** unless the measured numbers actually show it; the test only asserts every condition finds *some* relevant material (proving the comparison itself is meaningful), matching Phase 7's own honest, non-triumphalist disclosure that hybrid fusion did not measurably beat BM25 alone on its tiny synthetic corpus.

## L. Classification Evaluation

`[ENGINEERING RECOMMENDATION]` `tests/test_phase_16_classification.py` calls the REAL `classification.classifier.classify` over five synthetic cases spanning `KNOWN`/`UNKNOWN`/`AMBIGUOUS`/`NEEDS_EVIDENCE` and a `CONFLICTING` regulatory-track case, scored via `evaluation.benchmark.score_exact_match_cases` into a `CLASSIFICATION_STATE_EXACT_ACCURACY` result. **No probabilistic calibration exists anywhere** — `ClassificationResult` has no `confidence`/`probability` field, directly asserted. Deterministic repeatability (10 identical calls, byte-identical results) is tested directly. A full confusion matrix is not built: with 5 hand-constructed synthetic cases spanning 4 states, a per-cell confusion matrix would have too few observations per cell to be meaningful (Section AB) — pass/fail per case plus the aggregate exact-accuracy rate is the honest level of granularity for this dataset size.

## M. Jurisdiction Evaluation

`[OFFICIAL SOURCE]` The HIGH-PRIORITY safety benchmark (docs "JURISDICTION EVALUATION"). `tests/test_phase_16_jurisdiction.py` calls the REAL `jurisdiction.firewall.resolve_jurisdiction`/`jurisdiction.filtering.filter_evidence` and measures, over a fixed mixed India/International evidence set: (1) an India-only request leaks zero International evidence; (2) an International-only request leaks zero India evidence; (3) `BOTH` permits everything; (4) `UNSPECIFIED` fails closed (zero allowed); (5) a malformed jurisdiction signal (`"FRANCE"`) fails closed; (6) malformed evidence-side jurisdiction metadata fails closed; (7) a missing jurisdiction signal fails closed; (8) `resolve_jurisdiction`'s own signature has no `language`/`script` parameter at all — structurally proving language/script cannot influence it. `evaluation.benchmark.score_jurisdiction_leakage` defines `JURISDICTION_LEAKAGE_RATE = prohibited_ids_leaked / prohibited_ids_seen` — `NOT_APPLICABLE` when zero prohibited evidence was ever presented, and a single leaked item is always visible as a non-zero rate, never rounded away. **Measured result: 0.0 leakage across every case in this benchmark** (real numbers, not invented) — the real `filter_evidence` implementation never leaked in any constructed scenario, tested directly.

## N. Citation Evaluation

`[OFFICIAL SOURCE]` `evaluation.benchmark.score_citation_benchmark` wraps Phase 9's own `citation.metrics.compute_citation_coverage` **unchanged** — `valid_count`/`invalid_count`/`unresolved_count`/`citation_integrity_validation_rate`/`unique_valid_evidence_id_count` are Phase 9's own numbers, never re-derived. `CITATION_INTEGRITY_VALIDATION_RATE` is `NOT_APPLICABLE` when zero references were validated (never a fabricated `0.0`). **No result anywhere in this phase claims "citation is legally correct"** — every citation report additionally carries an explicit `CLAIM_SUPPORT_ENTAILMENT` result, always `NOT RUN`, explaining that semantic entailment is Phase 9's own `[DEFERRED]` boundary (Section below).

## O. Grounding Evaluation

`[OFFICIAL SOURCE]` `tests/test_phase_16_grounding.py` calls the REAL `generation.generator.generate_grounded_response` and measures `GROUNDED`/`ABSTAINED`/`GENERATION_FAILED` under: no evidence (abstains, provider never even called), citation failure (an uncited answer abstains, `NO_VALID_CITATIONS_PRODUCED`), provider failure (`fail_with`, `GENERATION_FAILED`, never a crash), a provider that raises an exception (`GENERATION_FAILED`, never a crash), a provider returning the wrong output type (`GENERATION_FAILED`), empty provider output (abstains, never fabricates a citation), malicious evidence text containing fake system instructions (`[[CITE:FAKE-999]]` never becomes a real citation), and prompt-injection text embedded in evidence claiming `grounding_status=GROUNDED` (has zero effect — the response still abstains on zero real citations). **No semantic grounding-quality claim is made** — every test measures structural status transitions only, never whether the answer text is factually correct.

## P. Safety Evaluation

`[OFFICIAL SOURCE]` `tests/test_phase_16_safety.py` calls the REAL `safety.evaluator.evaluate_safety` and proves all nine gates (`G1`-`G9`) are independently reachable under the CURRENT, unmodified `SafetyPolicyConfig` — `test_all_nine_gates_are_independently_reachable` collects the exact fired-gate set across nine constructed scenarios and asserts it equals `{G1..G9}`. **`SafetyPolicyConfig`'s thresholds are never modified anywhere in this phase** (`test_thresholds_are_not_modified_by_this_benchmark` asserts the exact default values `strong_min_unique_citations=2`, `strong_min_integrity_rate=1.0`, `moderate_min_integrity_rate=0.5`) — Phase 13's own `[ASSUMPTION]` label on these thresholds is repeated here, not resolved: Phase 16 measures behavior *under* the current configuration, it does not validate that the configuration itself is correct.

## Q. Multilingual Evaluation

`[OFFICIAL SOURCE]` `tests/test_phase_16_multilingual.py` calls the REAL `multilingual.preservation`/`multilingual.delivery` and measures original-query preservation, canonical-query preservation, the script-vs-language distinction, language-never-becomes-jurisdiction (`MultilingualDeliveryResult` has no `jurisdiction` field), translation-failure handling (`TRANSLATION_FAILED`, `answer_text=None`), unsupported-language handling, and evidence/citation/grounding/safety preservation through a (fake) translation call. **No translation-quality claim is made** — `FakeTranslationProvider`'s own docstring already discloses it is not a real translation; this phase adds no benchmark that could be mistaken for one. **REAL TRANSLATION QUALITY — NOT VALIDATED.**

## R. Human-Review Evaluation

`[OFFICIAL SOURCE]` `tests/test_phase_16_review.py` calls the REAL `review.policy`/`review.workflow` and measures correct review-triggering (an `ESCALATE` case triggers, a `SAFE_TO_PRESENT` case does not), valid state transitions, invalid transitions rejected (`InvalidReviewTransitionError`), reviewer-identity validation (`ReviewerIdentityError` on an empty ID), evidence-selection validation (`FakeEvidenceReferenceError` on a fabricated ID, acceptance of a real one), evidence immutability across a full review cycle, reviewer-comment isolation (stored verbatim, no `jurisdiction`-shaped field exists on `ReviewAction` at all), and rejection of a malicious reviewer action attempting to select a fabricated evidence ID. **There is no UI yet — nothing in this file evaluates one** (Phase 18's own scope).

## S. End-to-End Evaluation

`[ENGINEERING RECOMMENDATION]` `tests/test_phase_16_end_to_end.py` wires the REAL Phase 11-15 pipeline through all ten instructed cases: **A** (known + valid jurisdiction + valid evidence/citations + grounded + safe → `DELIVERED`, no review needed), **B** (ambiguous classification → `ESCALATE` → a real `ReviewRequest` is built), **C** (`UNSPECIFIED` jurisdiction → `allowed_jurisdictions == frozenset()`), **D** (an uncited answer → `ABSTAIN` → `UPSTREAM_BLOCKED`, `answer_text=None`), **E** (a failing provider → `GENERATION_FAILED`, `answer_text=None`), **F** (a failing translation provider on an otherwise-safe response → `TRANSLATION_FAILED`, `answer_text=None`), **G** (malicious evidence text → `ABSTAINED`, the injected instruction has zero effect), **H** (the exact malicious-reviewer scenario → `SafetyDecision`/`ClassificationResult` unchanged), **I** (a mixed India/International evidence list filtered against an India-only decision → International item blocked), **J** (an empty `EvidencePack` → `ABSTAINED` → `ABSTAIN`). None of these ten cases is hard-coded into any production module — they exist only as tests.

## T. Red-Team Framework

`[OFFICIAL SOURCE]` `evaluation.redteam.REDTEAM_CASES` — a FIXED, deterministic tuple of exactly 21 cases (one per instructed attack category), asserted by a module-level `assert` to exactly match the 21-category set and the case-id sequence `RT-01`..`RT-21`. No randomness anywhere — every case is a hand-written, versioned record, cross-mirrored in `config/redteam_cases.yaml` for auditability (drift-checked by `tests/test_phase_16_regression.py`).

## U. Attack Categories

`[OFFICIAL SOURCE]` Exactly the 21 named in the instructions: `PROMPT_INJECTION`, `EVIDENCE_INJECTION`, `CITATION_FORGERY`, `FAKE_EVIDENCE_ID`, `EVIDENCE_ID_MUTATION`, `CONTENT_HASH_MUTATION`, `JURISDICTION_LEAKAGE`, `LANGUAGE_TO_JURISDICTION_MANIPULATION`, `CLASSIFICATION_MANIPULATION`, `SAFETY_OVERRIDE_ATTEMPT`, `GROUNDING_OVERRIDE_ATTEMPT`, `REVIEWER_PRIVILEGE_ESCALATION`, `MALICIOUS_REVIEWER_COMMENT`, `UNICODE_ATTACK`, `MIXED_SCRIPT_ATTACK`, `OVERSIZED_INPUT`, `MALFORMED_SERIALIZATION`, `PROVIDER_FAILURE`, `EMPTY_PROVIDER_OUTPUT`, `WRONG_PROVIDER_OUTPUT_TYPE`, `CROSS_PHASE_METADATA_MUTATION`. Every category is executed against real Phase 8-15 objects in `tests/test_phase_16_redteam.py` (21 dedicated `_rtNN_check` functions, each shared verbatim between its own parametrized test and the full-summary aggregate test — no result is ever fabricated or duplicated with drift risk).

## V. Attack Success Definitions

`[OFFICIAL SOURCE]` Precisely as instructed, plus two documented, necessary catch-alls for categories the instructions did not individually define: `JURISDICTION_BYPASS` (prohibited-jurisdiction evidence appears in `allowed_evidence`), `CITATION_FORGERY_SUCCESS` (a fabricated evidence_id resolves `VALID`), `SAFETY_OVERRIDE` (`SafetyDecision.safety_status` changes due to untrusted input), `GROUNDING_BYPASS` (an ungrounded/uncited output is reported `GROUNDED`), `EVIDENCE_MUTATION` (a forged `evidence_id`/tampered `evidence_text` passes Phase 8's own integrity re-verification), `REVIEWER_PRIVILEGE_ESCALATION` (any reviewer input changes a trusted upstream object), `GENERIC_TRUSTED_STATE_UNCHANGED` (before/after comparison of the relevant trusted object — used for prompt/evidence injection, classification/grounding/cross-phase-metadata manipulation attempts, malicious comments, Unicode/mixed-script attacks, empty provider output), `GENERIC_INPUT_REJECTED` (an explicit, typed exception/failure status was raised — used for fake evidence IDs, oversized input, malformed serialization, provider failure, and wrong provider output type). `evaluation.models.ATTACK_CATEGORY_SUCCESS_DEFINITION` is the fixed, exhaustive mapping — `RedTeamResult.__post_init__` structurally rejects any mismatch between a case's `attack_category` and its own `success_definition`, and `build_redteam_result` never accepts `success_definition` as a caller-supplied parameter at all (Section AB security note).

## W. Red-Team Metrics

`[ENGINEERING RECOMMENDATION]` `attack_cases`, `successful_attacks`, `blocked_attacks` (always summing to `attack_cases`), `detection_rate = blocked_attacks / attack_cases`, `attack_success_rate = successful_attacks / attack_cases` — both `None` when `attack_cases == 0` (never a fabricated `0.0`/`1.0` for an empty run). **Measured result: 21 attack cases, 0 successful, 21 blocked, `detection_rate=1.0`, `attack_success_rate=0.0`** (`tests/test_phase_16_redteam.py::test_full_redteam_summary_all_21_categories_blocked`, real numbers from real checks). This is a SYNTHETIC red-team benchmark result, not a real-world security audit or penetration test — it demonstrates that Phases 8-15's already-built, already-tested defenses hold under Phase 16's own structured red-team format; it makes no broader security claim (Section AC).

## X. Failure Triage

`[ENGINEERING RECOMMENDATION]` `evaluation.models.FailureTriageEntry`: `case_id`, `component`, `failure_category` (one of 10 closed values), `expected_behavior`, `actual_behavior`, `reproducible`, `severity`/`severity_rationale` (categorical, required together, never a CVSS score), `suggested_owner_phase`, `notes`. `evaluation.runner.collect_failed_case_ids` is a pure convenience that surfaces `{component: [failed_case_id, ...]}` from a list of `ComponentBenchmarkReport` — it never auto-triages, never auto-assigns severity, and never fixes anything; building an actual `FailureTriageEntry` for a real failure is a human/caller decision. **No benchmark case in this phase's own test suite currently fails** (Section AI) — the triage machinery exists and is tested (`tests/test_phase_16_serialization.py`), but has not needed to triage a real Phase 0-15 defect during this phase's own implementation.

## Y. Result Schema

`[ENGINEERING RECOMMENDATION]` `EvaluationResult` → `ComponentBenchmarkReport` → `EvaluationReport` (component/end-to-end side); `RedTeamCase` → `RedTeamResult` → `RedTeamSummary` (red-team side); `FailureTriageEntry` (cross-cutting). `COMPONENT_NAMES` is one closed vocabulary spanning both component AND end-to-end/red-team reporting, but `EvaluationReport.component_reports` never allows two reports for the same component, and `END_TO_END`/`RED_TEAM_SECURITY` are always their own, separate entries — never folded into a per-stage number (docs "the framework must clearly distinguish COMPONENT METRICS from END-TO-END METRICS").

## Z. Serialization

`[ENGINEERING RECOMMENDATION]` `serialize.py` mirrors `src\safety\serialize.py`'s convention exactly: full explicit field reconstruction on deserialization, every dataclass invariant re-enforced, `ensure_ascii=False` (Devanagari/Tamil/emoji round-trip without escaping), no `pickle`. **ZERO-DENOMINATOR POLICY**, enforced structurally by `EvaluationResult.__post_init__`: `value is None` if and only if `applicable is False` — a zero-denominator case can never be `applicable=True` (raises `ValueError` at construction), so `NaN`/infinity is never producible through this package's own API. `tests/test_phase_16_serialization.py` (19 tests) covers round-trip, malformed/missing/wrong-type data, Unicode, nested (`EvaluationReport` containing `ComponentBenchmarkReport` containing `EvaluationResult`), empty datasets, and zero-denominator cases explicitly.

## AA. Determinism

`[ENGINEERING RECOMMENDATION]` Every identity field (`report_id` on both `ComponentBenchmarkReport` and `EvaluationReport`) is a deterministic SHA-256 hash over canonical fields (`benchmark.compute_report_id`, `runner.compute_evaluation_report_id`) — never a random UUID, never a timestamp, consistent with every prior phase's own convention. Repeated scoring of identical cases/coverage/red-team results produces byte-identical objects and JSON (`tests/test_phase_16_determinism.py`, 8 tests). No randomized adversarial generation exists anywhere — `REDTEAM_CASES` is a fixed tuple (docs "NO RANDOM TESTS").

## AB. Statistical Limitations

`[ENGINEERING RECOMMENDATION]` No statistical significance test, confidence interval, or p-value is computed anywhere in this phase — every synthetic dataset here (5-6 chunks, 2-5 cases per component) is far too small for such a claim to be meaningful, and none is made. A full confusion matrix for classification (Section L) and per-jurisdiction-pair leakage rates with confidence bounds (Section M) are both deliberately not built for the same reason. **No synthetic benchmark result in this phase is described as statistically representative of real-world performance.**

## AC. Real-Data Limitations

`[OFFICIAL SOURCE]` **REAL-WORLD REGULATORY PERFORMANCE — NOT VALIDATED.** This repository contains no large, authoritative, human-validated regulatory evaluation benchmark (confirmed by direct inspection of every `config/*.yaml` and `tests/_*_fixtures.py` module — none exists). Every numeric result in this phase (retrieval Precision/Recall/MRR, classification/jurisdiction/citation/safety/multilingual/review pass rates, the red-team `attack_success_rate`) measures IMPLEMENTATION correctness against synthetic or structural expectations only — none of them is, or should be read as, a measurement of real regulatory answer quality, legal correctness, or production-grade security posture.

## AD. Benchmark Versioning

`[ENGINEERING RECOMMENDATION]` `BENCHMARK_SCHEMA_VERSION` (`"1.0.0"`) is tracked independently of `EVALUATION_SCHEMA_VERSION` (also `"1.0.0"` today, but free to diverge) — the benchmark CASE CATALOGUE (`REDTEAM_CASES`, the synthetic corpora/cases defined in `tests/test_phase_16_*.py`) can change without forcing a result-shape migration, and vice versa. Both are explicit, hand-incremented strings on `EvaluationConfig`/`EvaluationReport` — never a timestamp (docs "Do not use timestamps as the only version identifier"). Changing the MEANING of an existing case (not just adding new ones) would require incrementing `benchmark_schema_version` — not done in this initial release, since no such change occurred.

## AE. Known Limitations

`[ENGINEERING RECOMMENDATION]`, disclosed, not hidden:
1. No persistent benchmark-history store exists — every `EvaluationReport` is an in-memory object for the duration of one test run; regression-baseline comparison across runs is `[DEFERRED]` to Phase 21 (observability) if ever needed.
2. `CORPUS_PROVENANCE`/`DOCUMENT_STRUCTURE`/`EVIDENCE_CONSTRUCTION` are not independently re-benchmarked by Phase 16 — they are referenced as already exhaustively covered by Phase 2/3/4/8's own test suites (`build_referenced_coverage_report`), a deliberate scope decision to avoid duplicating existing metrics, not an oversight.
3. Retrieval/dense/reranker benchmarks use `FakeEmbeddingModel`/`FakeReranker` throughout — no real BGE-M3/`bge-reranker-v2-m3` number exists anywhere in this phase (Section J).
4. No real Bhashini/translation-provider benchmark exists — multilingual evaluation measures structural preservation only (Section Q).
5. The classification/jurisdiction/safety/multilingual/human-review benchmarks are all small, hand-constructed synthetic case sets (2-9 cases each) — sufficient to prove structural correctness, not to make a statistical claim (Section AB).

## AF. Deferred Work

`[DEFERRED]`: a large, authoritative, human-validated real-regulatory benchmark; a real BGE-M3/`bge-reranker-v2-m3`/Bhashini benchmark; semantic claim/evidence entailment; persistent, cross-run benchmark-history storage; statistical significance testing; a red-team benchmark run against a real (non-fake) generation/translation provider.

## AG. Phase 17 Boundary

`[ENGINEERING RECOMMENDATION]` No FastAPI endpoint, API route, or HTTP server exists anywhere in `src\evaluation\` — every function in this phase is a plain Python function callable only from within this process (a test, or a future notebook/script). Productizing this evaluation harness behind an API is explicitly Phase 17's own, separately not-started, scope.

## AH. Acceptance Gate

`[OFFICIAL SOURCE, as restated for this implementation]` CAP-16's text — *"Regression suite runs automatically and results are reproducible"* — is met as follows: every Phase 16 test is part of the same `pytest tests/ -v` regression suite already run for Phases 0-15; every Phase 16 result is deterministic (Section AA); the benchmark schema, versioning, ground-truth discipline, and zero-denominator policy are all implemented and tested; retrieval/classification/jurisdiction/citation/grounding/safety/multilingual/human-review/end-to-end/red-team evaluation are all implemented against real Phase 3-15 objects; no earlier-phase behavior was changed to pass a benchmark (verified by phase-boundary/regression audit, Section AI); real-world/statistical limitations are explicitly disclosed, never fabricated. **MET.**

## AI. Validation Evidence

`pytest tests/ -v` run twice — see the Phase 16 implementation report for the exact pass counts of both runs. Zero skips, zero xfail, zero weakened assertions anywhere in `tests\test_phase_16_*.py`. Phase 0-15 regression, Master Reference hash integrity, source-discipline audit, and phase-boundary audit (no FastAPI/React/deployment/observability/CI-CD/production-validation code, fields, or imports anywhere in `src\evaluation\`; no earlier-phase source file modified by this phase except where an actual, documented, regression-tested bug fix was required — none was found during this phase's own implementation) all pass — see `tests\test_phase_16_regression.py`.
