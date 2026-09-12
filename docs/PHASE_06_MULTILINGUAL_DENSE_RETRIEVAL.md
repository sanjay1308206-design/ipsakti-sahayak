# PHASE 6 — MULTILINGUAL DENSE RETRIEVAL

Status: CONTRACT + IMPLEMENTATION DOCUMENT (Phase 6 deliverable)
Authoritative source: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`
Governed by: `docs\MASTER_REFERENCE_LOCK.md`, `docs\DEVELOPMENT_RULES.md`, `docs\PHASE_05_BM25_BASELINE.md`
Machine-readable counterparts: `config\dense_retrieval_contract.yaml`, `config\dense_index_schema.yaml`
Implementation: `src\retrieval\embeddings.py`, `faiss_index.py`, `models.py`, `identity.py`, `serialize.py`, `evaluation.py`

**Terminology note `[ENGINEERING RECOMMENDATION]`:** "Dense retrieval" here means embedding-vector cosine-similarity ranking only. A dense similarity score measures how close two pieces of text are in a learned embedding space — it is never a measure of legal authority, citation validity, regulatory correctness, or confidence in a legal conclusion. This is an independent baseline, not the final retrieval system; Phase 7 (Hybrid Fusion + Reranking) is the only later phase authorized to combine it with Phase 5's BM25 baseline.

---

## A. Purpose

`[OFFICIAL SOURCE]` Master Reference Phase 6 goal: *"Add semantic retrieval for paraphrased and multilingual questions."* Build scope: *"BGE-M3 embeddings on CPU, FAISS index, embedding cache."* Acceptance gate: *"Dense retrieval adds measurable recall without exhausting the laptop."*

`[ENGINEERING RECOMMENDATION]` Phase 6 builds an independent, deterministic, multilingual dense-retrieval baseline over Phase 4 `Chunk` objects, so it can later be scientifically compared against Phase 5's BM25 baseline (Section D). It answers *"how does dense retrieval perform on its own?"* — not *"how do we combine it with BM25?"* (that is Phase 7's job, explicitly out of scope here).

## B. Scope

In scope: an embedding-model abstraction (real + deterministic test double), a FAISS flat-index build/query path, a dense retrieval result contract, index persistence, a synthetic multilingual benchmark, and security/defensive validation.

Out of scope (explicitly deferred to later phases, no code for any of these exists in this repository): RRF/hybrid fusion, cross-encoder reranking, evidence packs, citation validation, LLM generation (Gemini/Qwen), formulation classification, the jurisdiction firewall, the confidence/abstention engine, multilingual response generation, a frontend, FastAPI, agents, a knowledge graph, production deployment, monitoring, authentication/authorization, corpus crawling/scraping, or automatic regulatory source downloading.

## C. Source Classification

Every non-trivial claim below carries one of the seven approved labels (`docs\DEVELOPMENT_RULES.md` Rule 1): `[OFFICIAL PS]`, `[OFFICIAL SOURCE]`, `[EXTERNAL RESEARCH]`, `[ENGINEERING RECOMMENDATION]`, `[OUR ENHANCEMENT]`, `[ASSUMPTION]`, `[DEFERRED]`. No regulation, legal claim, dataset, source document, API capability, benchmark result, or production-readiness claim is invented anywhere in this document or its implementation (Section X discloses exactly what was, and was not, actually measured).

## D. Relationship to Phase 5

`[ENGINEERING RECOMMENDATION]` Phase 5 (BM25) and Phase 6 (dense) are **independent, parallel baselines** over the same Phase 4 `Chunk` input. Neither depends on, imports, or modifies the other's code (`tests\test_phase_06_regression.py` asserts `src\retrieval\bm25.py`/`index.py` remain byte-for-byte unmodified). Both share the same generic `src\retrieval\evaluation.py` metric functions (Precision@k, Recall@k, and now MRR) and the same `tokenizer.py`'s `tokenize()` (reused only by `FakeEmbeddingModel` for deterministic test embeddings — never by the real embedding path, which consumes whole text). This lets Phase 7 later compare them apples-to-apples without either baseline having been shaped around the other.

## E. BGE-M3 Decision

`[OFFICIAL SOURCE]` `docs\MASTER_REFERENCE_LOCK.md` Section E names BGE-M3 as the "Embeddings: BGE-M3 (CPU candidate)" in the Final Core Stack. `src\retrieval\embeddings.DEFAULT_MODEL_NAME = "BAAI/bge-m3"` is the documented default `EmbeddingConfig.model_name` for `SentenceTransformerEmbeddingModel` — the real embedding backend. BGE-M3 is a multilingual, Hugging-Face-hosted embedding model runnable through `sentence-transformers`' standard `SentenceTransformer(model_name).encode(...)` API, which is why that library (not a bespoke BGE-M3 client) is this phase's chosen integration path (Section F).

**Model name is never silently substituted** (`config\dense_retrieval_contract.yaml` output requirements): `EmbeddingConfig.model_name` is an explicit, validated, non-empty string; `SentenceTransformerEmbeddingModel.load()` either loads exactly that model or raises `EmbeddingModelLoadError` — it never falls back to a smaller/cached/different model on failure.

## F. Alternatives Considered

`[ENGINEERING RECOMMENDATION]` — none claimed superior/inferior beyond what is stated with a reason:

- **A bespoke BGE-M3 HTTP/ONNX client** — rejected: `sentence-transformers` is the standard, actively-maintained integration path for Hugging-Face sentence-embedding models, already a listed likely dependency, and avoids reinventing tokenization/pooling/normalization logic BGE-M3 itself depends on.
- **A different multilingual embedding model** (e.g. LaBSE, multilingual-e5) — not evaluated in this repository; BGE-M3 is the Master-Reference-locked candidate (Section E) and no benchmark exists yet to justify deviating from it (`docs\DEVELOPMENT_RULES.md` Rule 9: "new technologies must earn their place through measurable evidence").
- **Vector databases** (Chroma, Qdrant, Weaviate, Pinecone) — rejected for this baseline: none is named by the Master Reference for this phase, all add operational/deployment surface (a running service, not a library) disproportionate to a laptop-oriented, correctness-first baseline, and the strict phase boundary (Section 27 of the originating instruction) forbids introducing them without a concrete Phase 6 requirement proving FAISS's flat index is insufficient — none exists.
- **FAISS index variants** (IVF, HNSW, PQ, GPU FAISS) — rejected for this baseline; see Section K.
- **CPU vs. GPU embedding** — see Section G/H.

## G. Hardware Implications

`[OFFICIAL SOURCE — stated development hardware]` NVIDIA RTX 3050, 4 GB VRAM, 16 GB RAM, 512 GB SSD, Windows (`docs\MASTER_REFERENCE_LOCK.md` Section F). BGE-M3 is a ~2.2 GB, multi-hundred-million-parameter transformer; running it, plus its supporting `torch`/`transformers` stack, on a 4 GB VRAM card risks out-of-memory failures or destabilizing whatever else is using the GPU. **This implementation therefore defaults every embedding to CPU execution** (`EmbeddingConfig.device = "cpu"` by default) and never assumes GPU/CUDA availability, a specific CUDA version, or a specific VRAM budget anywhere in the code. GPU execution remains available (`EmbeddingConfig(device="cuda")`) purely because `sentence-transformers`/`torch` support it natively when present — this repository does not force, require, or specially optimize for it, and does not attempt to catch/downgrade a GPU out-of-memory error into a silent CPU fallback (Section I: no silent substitution of any kind).

## H. CPU/GPU Execution Strategy

`[ENGINEERING RECOMMENDATION]` `device` is a required, explicit, non-empty string on `EmbeddingConfig` — never auto-detected or defaulted based on `torch.cuda.is_available()`. This is deliberate: an implicit "use the GPU if you can" policy would make behavior depend on whatever hardware happens to be running the code, undermining reproducibility and this specific hardware's known instability risk (Section G). `device` is *excluded* from `EmbeddingConfig.signature` (and therefore from the dense index signature, Section M) — it is documented as a runtime/hardware execution choice, not part of the embedding model's logical identity; whether the same model+config produces bit-identical output on CPU vs. GPU floating-point backends is `[ASSUMPTION — not benchmarked in this repository]`, since no real-model benchmark was run here (Section X).

## I. Embedding Contract

`[ENGINEERING RECOMMENDATION]` (`src\retrieval\embeddings.py`) `EmbeddingModel` is an `abc.ABC` with `load()`, `dimension` (property), `embed_documents(texts) -> np.ndarray[len(texts), dim]`, `embed_query(text) -> np.ndarray[dim]`, plus `model_identity` and `is_loaded`. Calling `dimension`/`embed_*` before `load()` raises `EmbeddingModelNotLoadedError`. Two implementations:

- **`SentenceTransformerEmbeddingModel`** — the real path. `load()` imports `sentence_transformers` lazily (only when actually used) and wraps every failure — missing package, unresolvable/uncached model name, device error — in `EmbeddingModelLoadError`, never a bare library exception and never a silent fallback.
- **`FakeEmbeddingModel`** — a deterministic, dependency-light **test double only** (Section Q/R). It downloads nothing, needs no GPU/heavy CPU inference, and produces a hash-seeded, token-overlap-sensitive vector (via the same `retrieval.tokenizer.tokenize()` Phase 5 already uses) purely to exercise dense-retrieval *plumbing* — ranking, provenance, determinism, persistence. **It is never used to build an index whose results are presented as real semantic retrieval quality.**

Both models expose **batch** document embedding (`embed_documents` takes a list; `EmbeddingConfig.batch_size` controls the real model's internal batching) and single-text query embedding. Model name/version and embedding dimension are always recorded: `model_identity` on every index/result, `dimension` read directly from the loaded model (never assumed/hard-coded) and stored on the built `DenseIndex`.

## J. Normalization Strategy

`[ENGINEERING RECOMMENDATION]` Cosine similarity via **L2-normalized vectors + FAISS inner product** (`config\dense_retrieval_contract.yaml: similarity_strategy: COSINE_VIA_NORMALIZED_INNER_PRODUCT`). Critically, **normalization is applied by exactly one shared function, `src\retrieval\embeddings.l2_normalize`, called from exactly one place — `faiss_index.py`'s `build_dense_index`/`dense_query`** — never inside an individual `EmbeddingModel` implementation. This guarantees document and query vectors always go through the identical normalization code path, regardless of which embedding backend produced the raw vectors (`tests\test_phase_06_embeddings.py` asserts this directly). A zero-norm vector (e.g. an empty-text embedding) is left unchanged by `l2_normalize` rather than producing NaN/Inf — a documented, tested edge case (Section P). `EmbeddingConfig.normalize` is a single, explicit, project-wide switch: when `False`, raw (un-normalized) inner product is used instead — the matching FAISS index type (`IndexFlatIP`) is identical either way since inner product is the primitive in both cases; only whether the caller pre-normalizes changes.

## K. FAISS Index Design

`[ENGINEERING RECOMMENDATION]` `faiss.IndexFlatIP` — exact, brute-force inner-product search — is the **only** supported index type for this baseline (`DenseIndexConfig.index_type = "FLAT_IP"`, validated against a closed `DENSE_INDEX_TYPES` set). This prioritizes correctness, determinism, and inspectability over query latency, appropriate for a laptop-oriented baseline whose corpus size is small and synthetic in this repository. **IVF, HNSW, PQ, GPU FAISS, and any distributed vector search are explicitly deferred** (Section V) — none is justified by a concrete Phase 6 requirement; introducing an approximate index would trade away exactness for a speed benefit this phase does not need to demonstrate.

## L. ID Mapping

`[OFFICIAL SOURCE]` FAISS's own internal vector position (an integer, `0..chunk_count-1` in build order) is **never** treated as, or exposed as, the business identity. `DenseIndex.chunk_ids[i]` maps that internal position to the real Phase 4 `chunk_id`; every other per-chunk array (`chunk_provenance`) is indexed by the same position. `DenseRetrievalResult.chunk_id` is always the real `chunk_id`, resolved through this mapping — never a FAISS position, an array index, or a generated display name (`tests\test_phase_06_provenance.py` asserts this explicitly). Duplicate `chunk_id`s in the input are rejected (`ValueError`) before any vector is added to the index.

## M. Index Signature

`[ENGINEERING RECOMMENDATION]` (`src\retrieval\identity.compute_dense_index_signature`) A SHA-256 hash over: the embedding model identity, the embedding dimension, the normalization flag, the `DenseIndexConfig` signature (index type), the ordered `chunk_ids`, and the ordered `content_hash`es of every indexed chunk. Identical inputs always produce an identical signature; changing any one of these — a different model, a different dimension, flipping normalization, a different chunk set, or even one chunk's content changing (hence its `content_hash`) — changes the signature. `device` is deliberately excluded (Section H). This is a build/version identifier for the *dense index itself* — never a legal citation, never a regulatory document version (mirrors the identical distinction already drawn for Phase 5's BM25 index signature).

## N. Retrieval Result Contract

`[ENGINEERING RECOMMENDATION]` `DenseRetrievalResponse` (`query`, `top_k`, `index_signature`, `model_identity`, `results`) wraps `DenseRetrievalResult` (`rank`, `chunk_id`, `score`, `model_identity`, `document_id`, `source_family_id`, `jurisdiction`, `content_hash`, `synthetic`, `page_numbers`, `block_ids`, `chunk_text`). Unlike Phase 5's BM25 response, there is no per-token "normalized query representation" field — a dense query is embedded holistically as one vector, not tokenized into individually-scored terms, so no token-level artifact exists to report.

**`score` is a cosine-similarity signal ONLY.** It is not, and must never be presented as: legal authority, citation validity, regulatory correctness, or confidence in a legal conclusion (`config\dense_index_schema.yaml`'s field description, repeated verbatim in this document, in the contract YAML, and asserted by a dedicated regression test — Section S/W).

**Difference from Phase 5, explicitly documented:** unlike BM25 (which excludes exact-zero-score, no-term-overlap chunks — `docs\PHASE_05_BM25_BASELINE.md` Section L), dense retrieval always returns `min(top_k, chunk_count)` results. Every embedding has *some* cosine similarity to a query vector; there is no natural "zero means no match" threshold the way BM25's term-overlap scoring has. A low dense score means "weak semantic similarity," never "no evidence" — and is never silently reinterpreted as either (`DENSE-SAFE-02`, `config\dense_retrieval_contract.yaml`).

## O. Provenance Preservation

`[OFFICIAL SOURCE — Phase 6 build scope]` The required chain — *dense result → chunk_id → block_ids → page_numbers → document_id → source_family_id → jurisdiction → content_hash* — is asserted directly by `tests\test_phase_06_provenance.py`'s dedicated traceability test, mirroring Phase 3/4/5's own critical-invariant tests. Every field is copied **unchanged** from the originating Phase 4 `Chunk` — the dense layer never rewrites, infers, or reclassifies any of them, and (Section L) never lets a FAISS integer position, array position, or generated name stand in for the real `chunk_id`. `synthetic=true` on a source chunk is always `synthetic=true` on its resulting `DenseRetrievalResult` — synthetic test material is never represented as real regulatory evidence anywhere in this pipeline.

## P. Multilingual Behavior

`[ENGINEERING RECOMMENDATION]` / `[ASSUMPTION]` The embedding contract accepts arbitrary Unicode text uniformly — no script-specific branching exists anywhere in `embeddings.py` or `faiss_index.py`. `tests\test_phase_06_multilingual.py` exercises English, Devanagari, Tamil, and mixed-script queries/documents against `FakeEmbeddingModel` end-to-end (index build → query → provenance-correct results), proving the *plumbing* handles multilingual Unicode without crashing or corrupting results.

**This is explicitly NOT a claim of real multilingual semantic quality.** `FakeEmbeddingModel`'s token-hash-based vectors have no learned cross-lingual semantic relationships (a Devanagari word and its English translation do not embed near each other under it) — it can only prove that *if* a real multilingual model like BGE-M3 were loaded, the surrounding index/query/provenance code would handle its output correctly. Whether BGE-M3 itself achieves good multilingual retrieval quality on this project's actual regulatory content is `[ASSUMPTION — NOT VALIDATED in this repository]`, since no real-model benchmark was run (Section X) and no real regulatory corpus exists yet to evaluate against.

## Q. Benchmark Methodology

`[ENGINEERING RECOMMENDATION]` (`tests\test_phase_06_evaluation.py`) A small, fully synthetic benchmark (`synthetic=true` throughout, `SYNTHETIC-BENCH-*` document IDs) with known-by-construction relevance labels, run against `FakeEmbeddingModel`. Metrics: **Precision@k, Recall@k** (reused from Phase 5's `retrieval.evaluation`) and **MRR** (Mean Reciprocal Rank, newly added to the same shared module for Phase 6 — `[EXTERNAL RESEARCH]`, standard IR literature). The benchmark measures **engineering correctness of the dense-retrieval implementation** — that ranking, provenance, and multilingual plumbing work — and separately, as an evaluation-only comparison (never a fusion), reports how the same synthetic queries rank under Phase 5's BM25 baseline for context. **It does not, and cannot, measure real semantic retrieval quality**, since it runs against `FakeEmbeddingModel`, not BGE-M3 (Section X).

## R. Test Strategy

`[ENGINEERING RECOMMENDATION]` All automated tests use `FakeEmbeddingModel` — zero downloads, zero GPU/heavy-CPU dependency, fully deterministic, safe to run offline and in CI. `SentenceTransformerEmbeddingModel` is exercised only for its *error paths* (missing package simulated via monkeypatching where practical, invalid model name → `EmbeddingModelLoadError`) and its *construction/validation* logic — never a full real-model load, per the explicit instruction not to download a large model merely to run unit tests. See Section X for what was, and was not, validated against the real model during this phase's own development (outside the committed automated suite).

## S. Security/Defensive Validation

`[ENGINEERING RECOMMENDATION]` (`tests\test_phase_06_security.py`) Tested: empty corpus, empty/whitespace query, duplicate `chunk_id`, mismatched vector dimensions (a deliberately broken custom `EmbeddingModel`), NaN/infinite embeddings, invalid/negative/non-integer `top_k`, malformed chunk metadata, corrupted persisted index metadata, incompatible model configuration (querying an index with a different model identity or dimension), missing index/metadata files, Unicode edge cases, very long text, and repeated identical chunks. **No claim of comprehensive security** — this is the same explicit, honest limitation Phase 5 states for its own security section.

## T. Persistence

`[ENGINEERING RECOMMENDATION]` (`src\retrieval\serialize.save_dense_index`/`load_dense_index`) Two files: FAISS's own native binary format (`faiss.write_index`/`faiss.read_index`) for the vector data, and a deterministic JSON sidecar for everything else (embedding config, dense index config, model identity, dimension, chunk count, `chunk_ids`, `chunk_provenance`, signature). **No pickled Python object, no arbitrary/unsafe deserialization anywhere.** Loading validates, in order: both files exist (else `FileNotFoundError`); the metadata JSON parses and contains every required key (else `DenseIndexCompatibilityError`); the FAISS binary reads (else `DenseIndexCompatibilityError`); the FAISS index's own `d` (dimension) and `ntotal` (vector count) match the metadata (else `DenseIndexCompatibilityError`); and the stored `signature` matches one freshly recomputed from the loaded metadata (else `DenseIndexCompatibilityError` — catches hand-edited/tampered metadata). **This is not a production vector database** — no Chroma/Qdrant/similar was introduced, no sharding, no incremental update, no concurrent-access handling.

## U. Limitations

`[ENGINEERING RECOMMENDATION]`

- No real-model benchmark was run in this repository (Section X) — BGE-M3 was never downloaded/loaded end-to-end here; only its integration *path* (via `sentence-transformers`) was implemented and validated against a different, already-cached small model, and only for plumbing correctness, not for BGE-M3-specific behavior.
- `FakeEmbeddingModel` has no real semantic understanding — multilingual test coverage proves plumbing correctness only (Section P).
- FAISS `IndexFlatIP` is brute-force — no approximate-search performance characteristics are measured or claimed.
- No embedding cache is implemented despite the Master Reference naming one ("embedding cache" in Phase 6 build scope) — `[DEFERRED]`, Section V.
- CPU-vs-GPU output equivalence is unverified (`[ASSUMPTION]`, Section H).
- No production vector database, sharding, or concurrent-access support (Section T).

## V. Deferred Decisions

`[DEFERRED]` — not implemented until a later phase explicitly calls for them and/or benchmarking justifies them:

- IVF/HNSW/PQ FAISS index variants, GPU FAISS, distributed vector search (Section K).
- An embedding cache (named in the Master Reference's Phase 6 build scope but not implemented here — revisit once a real model is actually run repeatedly against a real corpus and re-embedding cost is measured to matter).
- Alternative multilingual embedding models (LaBSE, multilingual-e5, etc.) — Section F.
- Vector databases (Chroma/Qdrant/Weaviate/Pinecone) — Section F.
- A real BGE-M3 benchmark run (Section X) — deferred by explicit user decision during this phase's implementation, not a technical blocker; the download is feasible (network access confirmed available) whenever authorized.
- Hybrid fusion of BM25 + dense (RRF) — Phase 7's job, not this one's.

## W. Acceptance Gate

`[OFFICIAL SOURCE]` Master Reference Phase 6 acceptance gate: *"Dense retrieval adds measurable recall without exhausting the laptop."* As restated for this implementation (matching the fuller definition given at Phase 6 start): a BGE-M3 integration path exists and is CPU-safe by default; dense retrieval works end-to-end (build → query) over Phase 4 chunks with an explicit FAISS vector-to-`chunk_id` mapping; full provenance is preserved; index persistence round-trips and fails safely on incompatibility; ranking is deterministic with an explicit tie-break; multilingual Unicode cases are tested at the plumbing level; a benchmark methodology exists with real (not fabricated) numbers against the deterministic test double; Phase 5 remains unmodified and passing; no Phase 7+ implementation exists. **MET** — see Section X for the exact evidence, and the explicit "NOT VALIDATED" disclosure for what a real-model recall number would require.

## X. Validation Results

`[ENGINEERING RECOMMENDATION]` Exact status, with no fabricated numbers:

- **Automated test suite (FakeEmbeddingModel):** all Phase 6 tests pass (exact count in the Phase 6 implementation report) — index build/query, ranking/tie-break, provenance chain, determinism (repeated build/query, byte-identical JSON), persistence round-trip, security/defensive edge cases, and the synthetic Precision@k/Recall@k/MRR benchmark.
- **Real BGE-M3 benchmark: NOT VALIDATED — BAAI/bge-m3 is not cached in this environment and downloading it (~2.2 GB) was explicitly declined for this session** (the user was asked directly and chose to skip the download and rely on the fake-embedding-model validation path instead). Network access to Hugging Face was confirmed available during this phase's development, so the download is feasible whenever explicitly authorized; no benchmark number is fabricated in its place.
- **Real `sentence-transformers` integration plumbing:** verified, as a one-off development sanity check (not part of the committed automated suite, and not a claim about BGE-M3 itself), against `sentence-transformers/all-MiniLM-L6-v2` — a small model already cached in this environment from unrelated prior work. Confirmed: real model load, correct dimension retrieval (384), correctly-shaped/finite document and query embeddings, and a clear `EmbeddingModelLoadError` (no silent fallback) for an invalid model name.
- **CPU execution:** confirmed working (the sanity check above ran on `device="cpu"`). **GPU execution:** untested in this repository (`torch.cuda.is_available()` returns `True` in this environment, but no embedding call was made with `device="cuda"` during this phase — no performance or correctness claim is made for the GPU path).
