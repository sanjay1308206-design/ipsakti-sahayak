# PHASE 7 — HYBRID FUSION + RERANKING

Status: CONTRACT + IMPLEMENTATION DOCUMENT (Phase 7 deliverable)
Authoritative source: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`
Governed by: `docs\MASTER_REFERENCE_LOCK.md`, `docs\DEVELOPMENT_RULES.md`, `docs\PHASE_05_BM25_BASELINE.md`, `docs\PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md`
Machine-readable counterparts: `config\hybrid_retrieval_contract.yaml`, `config\hybrid_result_schema.yaml`
Implementation: `src\retrieval\rrf.py`, `hybrid.py`, `reranker.py`, plus `models.py`/`identity.py`/`serialize.py` extended (not replaced)

**Terminology note `[ENGINEERING RECOMMENDATION]`:** "Hybrid" here means combining Phase 5's lexical ranks and Phase 6's dense-similarity ranks via Reciprocal Rank Fusion, then optionally reordering the fused candidates with a cross-encoder. Every score this phase produces or passes through — BM25, dense, RRF, reranker — is a *relevance signal*, never legal authority, citation validity, regulatory correctness, or confidence in a legal conclusion.

---

## A. Purpose

`[OFFICIAL SOURCE]` Master Reference Final Architecture Decision Lock names the retrieval stage as *"Hybrid Retrieval (BM25 + BGE-M3/FAISS) → RRF Fusion → Cross-Encoder Reranker → Evidence Pack"* (`docs\MASTER_REFERENCE_LOCK.md` Section E). Phase 7 implements exactly the RRF-fusion and reranking portion of that pipeline — establishing a deterministic hybrid retrieval layer that can be measured against, not merely assumed better than, Phases 5 and 6 individually.

## B. Scope

In scope: RRF fusion of Phase 5/6 result sets, a cross-encoder reranking abstraction (real + deterministic test double), a final hybrid retrieval result contract, a synthetic four-way benchmark (BM25 / dense / RRF / RRF+reranker), and security/defensive validation.

Out of scope (no code for any of these exists in this repository): Evidence Pack architecture, citation validation, claim↔evidence binding, grounded generation, Gemini, Qwen, formulation classification, the jurisdiction firewall, the confidence/abstention engine, human escalation, a frontend, FastAPI productization, agents, a knowledge graph, production deployment, monitoring, authentication/authorization, corpus crawling, or automatic regulatory source downloading. Phase 7 produces **ranked retrieval candidates only** — Phase 8 owns evidence-object/citation architecture.

## C. Source Classification

Every non-trivial claim below carries one of the seven approved labels (`docs\DEVELOPMENT_RULES.md` Rule 1). No regulation, legal claim, dataset, source document, API capability, benchmark result, or production-readiness claim is invented anywhere in this document or its implementation (Section Z discloses exactly what was, and was not, measured).

## D. Relationship to Phase 5

`[ENGINEERING RECOMMENDATION]` Phase 7 **consumes** Phase 5's `RetrievalResponse`/`RetrievalResult` exactly as Phase 5 produces them — `src\retrieval\bm25.py`, `index.py`, and `tokenizer.py` are untouched (`tests\test_phase_07_regression.py` asserts this by file-content check). BM25 remains independently queryable and measurable on its own; Phase 7 never redesigns or reimplements lexical scoring.

## E. Relationship to Phase 6

`[ENGINEERING RECOMMENDATION]` Phase 7 **consumes** Phase 6's `DenseRetrievalResponse`/`DenseRetrievalResult` exactly as Phase 6 produces them — `src\retrieval\faiss_index.py` and `embeddings.py`'s existing classes are untouched. Dense retrieval remains independently queryable and measurable on its own. Phase 7 reuses Phase 6's `EmbeddingModel` interface pattern verbatim for its own `Reranker` interface (Section L) rather than inventing a new abstraction style.

## F. Hybrid Retrieval Architecture

`[ENGINEERING RECOMMENDATION]` The exact target pipeline (`src\retrieval\hybrid.run_hybrid_pipeline`):

```
query → bm25_query() → RetrievalResponse ─┐
                                            ├→ fuse_rrf() → RrfResponse → rerank_candidates() → HybridRetrievalResponse
query → dense_query() → DenseRetrievalResponse ─┘
```

Every stage is **independently callable and independently measurable** — `fuse_rrf()` alone answers "how does RRF hybrid perform?" and `rerank_candidates()` alone (given an `RrfResponse`) answers "does reranking improve the RRF ordering?" (Section T, architectural principle: BM25 and dense are complementary signals, neither assumed universally superior). `run_hybrid_pipeline()` is a thin convenience composition of the four already-independent functions — it adds no logic of its own.

## G. Candidate Union

`[OFFICIAL SOURCE]` The candidate set is the union of `chunk_id`s appearing in either the BM25 or dense result list — never a new identity, never a subset chosen by one system's opinion of the other. If a `chunk_id` appears in **both** lists, both systems' ranks contribute to its RRF score and their provenance must match exactly (Section J); if it appears in **only one**, only that system's rank contributes (`RrfResult.bm25_rank`/`dense_rank` is `None` for the side that didn't retrieve it — never fabricated as `0` or any other sentinel that could be confused with a real rank).

## H. RRF Formula

`[EXTERNAL RESEARCH]` Standard Reciprocal Rank Fusion (Cormack, Clarke & Buettcher, 2009):

```
RRF_score(d) = Σ over retrieval lists L containing d of  1 / (k + rank_L(d))
```

`rank_L(d)` is always the **1-based** rank already assigned by the contributing system's own result contract (`RetrievalResult.rank` / `DenseRetrievalResult.rank`, both already 1-based per their own Phase 5/6 documentation) — RRF never re-derives, renumbers, or infers a rank. `k = 60.0` is the standard constant from the originating paper `[EXTERNAL RESEARCH]`, not tuned for this corpus — exactly the same un-tuned-default discipline already applied to Phase 5's `k1`/`b` (`docs\PHASE_05_BM25_BASELINE.md` Section G).

## I. RRF Configuration

`[ENGINEERING RECOMMENDATION]` `src\retrieval\models.RrfConfig(k: float = 60.0)` — `k` is a real, validated (`k > 0`), documented field, never a hidden magic constant inside `fuse_rrf`. `candidate_k` (how many top-RRF candidates survive into reranking) is a **required, explicit, positive-integer parameter** to `fuse_rrf()` itself — mirroring Phase 5/6's own `top_k` discipline (invalid values raise `ValueError` immediately, never silently clamped).

## J. RRF Duplicate Handling

`[ENGINEERING RECOMMENDATION]` Two distinct duplicate scenarios, handled differently and both tested:

- **A `chunk_id` appearing in both the BM25 and dense lists** is the *normal, expected* case — both ranks contribute (Section G), and `fuse_rrf` additionally validates their provenance (`document_id`, `source_family_id`, `jurisdiction`, `content_hash`, `synthetic`, `page_numbers`, `block_ids`, `chunk_text`) matches exactly; a mismatch raises `ValueError` rather than silently preferring one source (`HYBRID-SAFE-03`).
- **A duplicate `chunk_id` appearing twice within the SAME input list** (BM25 or dense) is treated as **malformed retrieval output and rejected** (`ValueError`), never silently deduplicated, summed, or double-counted. Rationale: Phase 5's `Bm25Index` and Phase 6's `DenseIndex` both already guarantee unique `chunk_id`s at build time (`tests\test_phase_05_faiss.py`/`test_phase_06_faiss.py`'s own duplicate-rejection tests), so a duplicate surviving into a `RetrievalResponse`/`DenseRetrievalResponse` can only mean the object was hand-constructed or corrupted after the fact — the originating instruction's explicit preference ("prefer rejecting malformed retrieval output rather than silently repairing it") is followed literally here.

## K. RRF Tie-Breaking

`[ENGINEERING RECOMMENDATION]` Deterministic total order: **descending RRF score, then ascending `chunk_id`** — never insertion order, `dict`/`set` iteration order, timestamps, or memory addresses. The candidate union itself is built from an order-preserving `dict.fromkeys()` pass over both input lists (not a `set`), so even the *pre-sort* candidate enumeration is reproducible, though only the final sorted order is contractually meaningful.

## L. Reranker Architecture

`[ENGINEERING RECOMMENDATION]` (`src\retrieval\reranker.py`) `Reranker` is an `abc.ABC` mirroring Phase 6's `EmbeddingModel` pattern exactly: `load()`, `score(query, candidate_texts) -> np.ndarray`, plus `model_identity`/`is_loaded`. Calling `score()` before `load()` raises `RerankerNotLoadedError`. Two implementations:

- **`CrossEncoderReranker`** — the real path, backed by `sentence_transformers.CrossEncoder`. `load()` wraps every failure (missing package, unresolvable/uncached model, device error) in `RerankerLoadError`, never a silent fallback to a different model.
- **`FakeReranker`** — a deterministic, dependency-light **test double only** (Section Q). It downloads nothing and computes a simple query-term-overlap count (via the same `retrieval.tokenizer.tokenize()` used everywhere else in this project) purely to exercise reranker *plumbing* — batching, ordering, tie-breaking, score propagation, error handling. **It never pretends to be `bge-reranker-v2-m3`** and is never used to produce a result presented as real cross-encoder relevance quality.

The reranker receives **only** `(query, chunk_text)` pairs — plain data. It never modifies candidate chunk text, never modifies provenance, never generates evidence, never summarizes or rewrites chunks (Section Q of the originating instruction). It scores and reorders; nothing else.

## M. bge-reranker-v2-m3 Decision

`[OFFICIAL SOURCE]` `docs\MASTER_REFERENCE_LOCK.md` Section E names `bge-reranker-v2-m3` as the reranker candidate in the Final Core Stack. `src\retrieval\reranker.DEFAULT_RERANKER_MODEL_NAME = "BAAI/bge-reranker-v2-m3"` is the documented default `RerankerConfig.model_name`. **Model name is never silently substituted**: `RerankerConfig.model_name` is explicit and validated; `CrossEncoderReranker.load()` either loads exactly that model or raises `RerankerLoadError` — it never falls back to a smaller/cached/different model on failure (`config\hybrid_retrieval_contract.yaml` output requirements).

## N. CPU/GPU Strategy

`[OFFICIAL SOURCE — stated development hardware]` NVIDIA RTX 3050, 4 GB VRAM (`docs\MASTER_REFERENCE_LOCK.md` Section F). `RerankerConfig.device` defaults to `"cpu"` and is never auto-detected from `torch.cuda.is_available()` — identical reasoning to Phase 6's `EmbeddingConfig.device` (`docs\PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md` Section H). GPU execution (`device="cuda"`) remains available because `sentence-transformers`/`torch` support it natively, but nothing in this repository forces, requires, or specially optimizes for it, and no out-of-memory fallback logic exists (no silent CPU downgrade). `device` is excluded from `RerankerConfig.signature` for the same reason it is excluded from `EmbeddingConfig.signature` — a runtime/hardware choice, not part of the reranker's logical identity.

## O. Candidate Depth

`[ENGINEERING RECOMMENDATION]` Every depth parameter in the pipeline is explicit and required, never a hidden default buried in a function body: `bm25_top_k` (Phase 5's own `query()` parameter), `dense_top_k` (Phase 6's own `dense_query()` parameter), `candidate_k` (`fuse_rrf()`'s RRF-stage cutoff), `reranker_top_k`/`top_k` (`rerank_candidates()`'s final cutoff). `run_hybrid_pipeline()` requires all four positionally-named — there is no version of this function with a silently-assumed depth.

## P. Final Result Contract

`[ENGINEERING RECOMMENDATION]` `HybridRetrievalResponse` (`query`, `top_k`, `rrf_k`, `reranker_model_identity`, `results`) wraps `HybridRetrievalResult`: `rank`, `chunk_id`, `reranker_score`, `rrf_score`, `bm25_rank`/`bm25_score` (nullable), `dense_rank`/`dense_score` (nullable), `reranker_model_identity`, `document_id`, `source_family_id`, `jurisdiction`, `content_hash`, `synthetic`, `page_numbers`, `block_ids`, `chunk_text`. All four scores are **distinct fields, never collapsed** (`config\hybrid_result_schema.yaml`, `tests\test_phase_07_provenance.py`).

## Q. Score Semantics

`[ENGINEERING RECOMMENDATION]` Documented once, precisely, and repeated in both YAML contracts and dedicated tests:

| Score | Meaning | Never means |
|---|---|---|
| `bm25_score` | Lexical (term-overlap) relevance signal | Legal authority, citation validity, regulatory correctness, answer confidence |
| `dense_score` | Dense semantic-similarity signal (cosine) | Same as above |
| `rrf_score` | Rank-fusion signal — how well-ranked `d` was across contributing systems | Same as above |
| `reranker_score` | Cross-encoder relevance signal | Same as above |

None of these four scores is legal authority, regulatory validity, or citation correctness at any point in this pipeline. That distinction belongs to later architecture (Phase 8 evidence objects, Phase 9 citation validation, Phase 13 confidence/abstention) and is explicitly out of scope here (Section B).

## R. Provenance

`[OFFICIAL SOURCE — Phase 7 build scope]` The required chain — *hybrid result → chunk_id → block_ids → page_numbers → document_id → source_family_id → jurisdiction → content_hash* — is asserted directly by `tests\test_phase_07_provenance.py` **after each of the four stages**: BM25 alone, dense alone, RRF, and reranking. Neither RRF nor the reranker ever replaces a `chunk_id`; FAISS internal vector positions and BM25 internal document positions never appear as business identity anywhere in this pipeline (Section G/L). `synthetic=true` on a source chunk survives unchanged through every stage.

## S. Multilingual Behavior

`[ENGINEERING RECOMMENDATION]` / `[ASSUMPTION]` `tests\test_phase_07_multilingual.py` exercises English, Devanagari, Tamil, and mixed-script queries through the full BM25 → dense → RRF → rerank pipeline using `FakeEmbeddingModel` and `FakeReranker`. This proves the *plumbing* handles multilingual Unicode correctly end-to-end — it is **not** a claim of real multilingual semantic or reranking quality (identical distinction to `docs\PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md` Section P). Whether `bge-reranker-v2-m3` itself reranks multilingual Ayurveda/IP content well is `[ASSUMPTION — NOT VALIDATED in this repository]` (Section Z).

## T. Benchmark Methodology

`[ENGINEERING RECOMMENDATION]` (`tests\test_phase_07_evaluation.py`) A small, fully synthetic benchmark (`synthetic=true`, `SYNTHETIC-BENCH-07-*` document IDs) with known-by-construction relevance labels, built once and reused identically across all four measurement conditions — **same query set, same relevance judgments, same chunk set, same evaluation protocol, same cutoff K** (Section U's fairness requirement) — comparing:

**A.** BM25 alone (Phase 5's `query()`) **B.** Dense alone (Phase 6's `dense_query()`, `FakeEmbeddingModel`) **C.** RRF hybrid (`fuse_rrf()`) **D.** RRF + reranking (`rerank_candidates()`, `FakeReranker`)

Metrics: Precision@k, Recall@k (reused from `retrieval.evaluation`, already shared by Phase 5/6) and MRR (added in Phase 6, reused here unchanged). The benchmark answers *"does hybrid fusion improve retrieval over each individual method, on this synthetic set?"* and *"does reranking improve the RRF ordering, on this synthetic set?"* **as measured** — it does not cherry-pick queries, and any observed direction (hybrid better, worse, or tied) is reported as measured, not assumed.

## U. Benchmark Results

`[ENGINEERING RECOMMENDATION]` Exact numbers are in the Phase 7 implementation report (not fabricated here as a template). This is an **implementation benchmark** (proves the four pipeline stages compute correctly against a synthetic, known-relevance set) — it is explicitly **not** a real regulatory retrieval benchmark, since no real regulatory corpus or real embedding/reranker model was used to produce it (Section Z).

## V. Security

`[ENGINEERING RECOMMENDATION]` (`tests\test_phase_07_security.py`) Tested: empty BM25/dense result lists (one or both), duplicate `chunk_id` within one list, mismatched provenance for the same `chunk_id` across lists, invalid ranks/non-finite scores (simulated malformed result objects), invalid/negative/non-integer `candidate_k`/`top_k`, a reranker returning a mismatched-length or non-finite score array, missing/unloaded reranker, incompatible reranker configuration, Unicode edge cases, extremely long candidate text, repeated identical candidates, and candidate text crafted to *look* like configuration/instructions (e.g. embedded key=value-looking strings) — **chunk content is always treated as inert data**; nothing in the reranking or fusion path parses, executes, or is influenced by candidate text beyond scoring it as a string. No claim of comprehensive security.

## W. Limitations

`[ENGINEERING RECOMMENDATION]`

- No real-model benchmark was run for either BGE-M3 (inherited limitation from Phase 6) or `bge-reranker-v2-m3` in this repository (Section Z).
- `FakeReranker`/`FakeEmbeddingModel` have no real semantic or cross-encoder understanding — multilingual/benchmark coverage proves plumbing correctness only.
- RRF's `k=60.0` and the reranker's default configuration are un-tuned defaults, not validated against any real regulatory corpus (none exists yet).
- No approximate/production-scale performance characteristics are measured for the reranking stage (candidate sets in this repository are small and synthetic).
- CPU-vs-GPU output equivalence for the reranker is unverified (`[ASSUMPTION]`, same as Phase 6 Section H).

## X. Deferred Decisions

`[DEFERRED]` — not implemented until a later phase explicitly calls for them and/or benchmarking justifies them:

- Weighted score fusion (a non-RRF alternative) — not evaluated; RRF was chosen because it is the Master-Reference-locked, parameter-light, rank-based (not raw-score-based) fusion method, avoiding the need to make BM25 and cosine-similarity scores commensurable.
- Alternative rerankers beyond `bge-reranker-v2-m3` — Section Y.
- Approximate vector retrieval / vector databases for the underlying dense stage — Phase 6's own deferred list, unchanged here.
- A real `bge-reranker-v2-m3` benchmark run (Section Z) — deferred by explicit user decision during this phase's implementation, not a technical blocker; the download is feasible whenever authorized.
- Evidence Pack construction, citation formatting, claim/evidence binding, grounded generation — explicitly Phase 8/9/10's job, not this one's.

## Y. Acceptance Gate

`[ENGINEERING RECOMMENDATION]` (no separate Master Reference one-liner exists for Phase 7 beyond the pipeline diagram itself — Section A) Phase 7 acceptance, as defined for this implementation: BM25 and dense results can both enter the hybrid pipeline; candidate union works without losing provenance or inventing identity; RRF is correctly implemented with a configurable `k` and deterministic tie-breaking; duplicate candidates are handled correctly (Section J); a cross-encoder abstraction exists with a `bge-reranker-v2-m3` integration path, a CPU-safe default, and no silent model substitution; a fake reranker exists for deterministic automated tests; reranker output preserves chunk identity; all provenance survives every stage; multilingual Unicode cases are tested; a benchmark compares BM25/dense/RRF/reranked retrieval fairly; real-model validation is honestly reported with no fabricated numbers; Phase 0–6 regression remains intact; no Phase 8+ functionality exists. **MET** — see the Phase 7 implementation report for the exact evidence and the explicit "NOT VALIDATED" disclosures.

## Z. Validation Results

`[ENGINEERING RECOMMENDATION]` Exact status, with no fabricated numbers:

- **Automated test suite (FakeEmbeddingModel + FakeReranker):** all Phase 7 tests pass (exact count in the Phase 7 implementation report) — RRF mathematics, candidate union/duplicate/tie-break behavior, reranker contract/plumbing, provenance chain after each of the four stages, determinism (repeated fusion/reranking, byte-identical JSON), security/defensive edge cases, and the synthetic four-way (BM25/dense/RRF/RRF+reranker) benchmark.
- **Real BGE-M3 dense-retrieval validation: NOT VALIDATED** — inherited from Phase 6; `BAAI/bge-m3` was not downloaded in that phase and remains not downloaded here.
- **Real bge-reranker-v2-m3 validation: NOT VALIDATED** — `BAAI/bge-reranker-v2-m3` is not cached in this environment and downloading it was explicitly declined for this session (the user was asked directly, consistent with the Phase 6 BGE-M3 decision, and chose to skip the download and rely on the fake-reranker validation path instead). Network access was available; no benchmark number is fabricated in its place.
- **Real `sentence_transformers.CrossEncoder` integration plumbing:** verified, as a one-off development sanity check (not part of the committed automated suite, and not a claim about `bge-reranker-v2-m3` itself), against `BAAI/bge-reranker-base` — a smaller cross-encoder model already cached in this environment from unrelated prior work, run fully offline. Confirmed: real model load, `predict()` returning finite numeric scores for `(query, text)` pairs in the expected shape.
- **CPU execution:** confirmed working (the sanity check above ran on `device="cpu"`). **GPU execution:** untested in this repository — no performance or correctness claim is made for the GPU reranker path.
