# PHASE 5 — BM25 RETRIEVAL BASELINE

Status: CONTRACT + IMPLEMENTATION DOCUMENT (Phase 5 deliverable)
Authoritative source: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`
Governed by: `docs\MASTER_REFERENCE_LOCK.md`, `docs\DEVELOPMENT_RULES.md`, `docs\PHASE_04_LEGAL_AWARE_CHUNKING.md`
Machine-readable counterparts: `config\bm25_contract.yaml`, `config\retrieval_result_schema.yaml`
Implementation: `src\retrieval\`

**Terminology note `[ENGINEERING RECOMMENDATION]`:** "Retrieval" here means lexical (term-overlap) ranking only. A BM25 score is a measure of textual term overlap between a query and a chunk — it is never a measure of legal authority, correctness, or citation validity. This is not a final retrieval system; it is the measurable baseline Phase 6 (dense retrieval) and Phase 7 (hybrid fusion + reranking) will be compared against.

---

## A. Objective

`[OFFICIAL SOURCE]` Master Reference Phase 5 goal: *"Establish a measurable lexical retrieval baseline."* Build scope: *"BM25 index and query API."* Acceptance gate: *"Every retrieval improvement is measured against this baseline."*

`[ENGINEERING RECOMMENDATION]` Phase 5 builds a simple, reproducible, explainable, CPU-friendly, measurable lexical retrieval baseline over Phase 4's `Chunk` objects. It is deliberately not the final retrieval architecture — no dense retrieval, no fusion, no reranking, no generation. Its purpose is to exist as a fixed comparison point.

## B. Input Contract

`[ENGINEERING RECOMMENDATION]` The two entry points, `src\retrieval\index.build_index(chunks, config=None)` and `src\retrieval\index.query(index, query_text, top_k)`, accept exactly:

- `build_index`: a Python `list` of actual `chunking.models.Chunk` instances (the real in-memory Phase 4 output) — never a serialized JSON dict, never raw chunk text, never a file path. An optional `Bm25Config` (Section G); defaults to the standard parameters when omitted.
- `query`: a built `Bm25Index`, a raw `str` query, and a positive integer `top_k`.

No third input is accepted. Phase 5 never re-reads Phase 3/4 config files at query time, never re-derives chunk structure, and never reaches into Phase 2's authority matrix directly — a `Chunk` reaching `build_index` has, by construction, already passed every earlier phase's admission/extraction/chunking boundary.

## C. Tokenization Policy

`[ENGINEERING RECOMMENDATION]` (`src\retrieval\tokenizer.tokenize`) Tokenization is deliberately simple and script-agnostic: Python's `\w+` regular expression under Unicode mode, which matches a run of Unicode letters/digits/underscore in **any** script (Latin, Devanagari, Tamil, etc.) with no per-script special-casing. Punctuation, hyphens, and whitespace are treated purely as separators — `"well-known"` tokenizes as `["well", "known"]`. This is a documented simplification, not a claim of linguistically correct word-boundary detection for every language; script-specific segmentation (e.g. proper compound-word handling, agglutinative-morphology-aware splitting for Dravidian languages) is `[DEFERRED]` (Section R) — establishing a reproducible cross-language baseline is this phase's job, not solving multilingual morphology.

No heavyweight NLP tokenizer dependency (spaCy, a language model, ICU segmentation) was added: the standard library's Unicode-aware `re` module is sufficient for a lexical baseline and keeps the dependency surface at zero (`docs\DEVELOPMENT_RULES.md` Rule 6).

## D. Text Normalization Policy

`[ENGINEERING RECOMMENDATION]` Before tokenization, text is normalized via `unicodedata.normalize("NFKC", text)` (compatibility decomposition + canonical composition — collapses visually/semantically equivalent Unicode representations of the same character, e.g. combining-character sequences vs. precomposed forms) and then `.lower()` (a no-op for scripts without case, e.g. Devanagari/Tamil; standard case-folding for Latin/Cyrillic/etc.).

**Critical distinction (Section 9 of the originating instruction):** this normalization applies **only** to the token stream used internally for indexing/scoring. `Chunk.text` — the original evidence text — is read but never mutated, and `RetrievalResult.chunk_text` is always a verbatim, unnormalized copy of the source chunk's text. The BM25 index never replaces or shadows the original evidence text.

## E. Stopword Policy

`[ENGINEERING RECOMMENDATION]` **Chosen: Option A — no stopword removal in this baseline** (`config\bm25_contract.yaml: stopword_policy: "NONE"`). Rationale: this corpus is multilingual (English, Hindi, Tamil, and others per the evaluated-language list); importing a single English stopword list and applying it uniformly would silently bias the baseline against every non-English chunk (removing zero stopwords for scripts it doesn't cover, while distorting English scoring) — exactly the "claiming languages that have not been evaluated" anti-pattern `docs\MASTER_REFERENCE_LOCK.md` Section D warns against. A precisely versioned, per-language stopword policy is a measurable, revisitable improvement to weigh in Phase 16 evaluation against this no-removal baseline — not an arbitrary addition here.

## F. Unicode Handling

`[OFFICIAL SOURCE — tested directly]` per Section 8 of the originating instruction, the tokenizer is exercised directly against: English, Devanagari, Tamil, mixed-script text, punctuation, numbers, hyphenated text, repeated whitespace, and empty text (`tests\test_phase_05_tokenization.py`). No script is special-cased or privileged; the same `\w+`-over-NFKC-lowercased pipeline runs uniformly for every script. `unicodedata.normalize` and Python's Unicode-aware `str.lower()`/`re` module are used exactly as the standard library implements them — no custom Unicode table or script-detection logic exists in this repository.

## G. BM25 Formula/Parameters

`[ENGINEERING RECOMMENDATION]` (`src\retrieval\bm25.py`) Standard Okapi BM25:

```
score(D, Q) = Σ over query terms t of:
    idf(t) * (tf(t, D) * (k1 + 1)) / (tf(t, D) + k1 * (1 - b + b * |D| / avgdl))

idf(t) = ln(1 + (N - df(t) + 0.5) / (df(t) + 0.5))
```

Where `tf(t, D)` = raw term frequency of `t` in chunk `D`, `df(t)` = number of chunks containing `t` at least once, `N` = total chunk count, `|D|` = token count of `D`, `avgdl` = mean token count across all indexed chunks.

**Parameters (`src\retrieval\models.Bm25Config`): `k1 = 1.5`, `b = 0.75`** — the standard textbook defaults from the original Okapi BM25 formulation (Robertson & Zaragoza) `[ENGINEERING RECOMMENDATION]`, explicitly not tuned for this corpus. Both are named `Bm25Config` fields, never hard-coded magic numbers inside the scoring function, and both are validated (`k1 ≥ 0`, `0.0 ≤ b ≤ 1.0`) at construction time. **Parameter tuning belongs to Phase 16 evaluation, never to arbitrary assumption in this baseline** (per the originating instruction Section 7 and `docs\DEVELOPMENT_RULES.md` Rule 10).

**IDF variant note `[ENGINEERING RECOMMENDATION]`:** the classic Robertson–Sparck-Jones IDF, `ln((N-df+0.5)/(df+0.5))`, can go negative for terms appearing in more than half the corpus, which then *subtracts* from a document's score in a way that is easy to misread as "this term counts against relevance." This implementation uses the "+1 inside the log" variant, which is always non-negative, at the documented cost of compressing the discriminating power of extremely common terms. This is a common, well-known variant (used by, e.g., `rank_bm25`'s default implementation) — not a novel invention — and is stated here so the exact formula being tested is never ambiguous.

## H. Index Representation

`[ENGINEERING RECOMMENDATION]` (`src\retrieval\models.Bm25Index`) A single internal integer position (`0..chunk_count-1`, matching input list order — never a hash, never derived from dict/set iteration) maps to a Phase 4 `chunk_id` via the parallel list `chunk_ids`. Every other per-chunk array (`document_lengths`, `term_frequencies`, `chunk_provenance`) is indexed by that same position. The internal position is **never** exposed in any output (`RetrievalResult` carries only the real `chunk_id`) — it is a pure implementation detail, not a second identity system. The whole index is plain data (`str`/`int`/`float`/`list`/`dict`), directly JSON-serializable with no custom encoder (Section 23 of the originating instruction; `src\retrieval\serialize.index_to_json`).

## I. Query Processing

`[ENGINEERING RECOMMENDATION]` `query_text` is tokenized with the exact same policy used at index-build time (Sections C/D) — there is no separate, divergent "query-time" tokenizer. Query terms with zero corpus document frequency (`df(t) == 0`, i.e. absent from every indexed chunk) contribute nothing and are simply skipped in scoring, rather than raising an error or attempting an undefined IDF.

## J. Ranking/Tie-Breaking

`[ENGINEERING RECOMMENDATION]` Results are sorted by **descending BM25 score, then ascending `chunk_id`** (`src\retrieval\index.query`, the exact sort key `(-score, chunk_id)`) — a fully deterministic total order with no dependency on insertion order, dictionary/set iteration, timestamps, process IDs, or memory addresses. Two chunks with identical scores always resolve to the same relative order on every run (`tests\test_phase_05_ranking.py`).

## K. Top-k Behavior

`[ENGINEERING RECOMMENDATION]` `top_k` must be a positive integer; a non-positive or non-integer value (including `bool`, an `int` subclass) raises `ValueError` immediately — an invalid usage, not a data-quality state (mirroring `docs\PHASE_04_LEGAL_AWARE_CHUNKING.md`'s treatment of `max_chunk_size_chars`). `top_k` larger than the number of chunks that actually scored above zero simply returns however many matched — never padded with zero-score results, never an error (`tests\test_phase_05_edge_cases.py`).

## L. Empty/Unknown Queries

`[ENGINEERING RECOMMENDATION]` An empty string or whitespace-only query tokenizes to zero terms; `query()` returns a `RetrievalResponse` with `results=[]` immediately (not an error — Section O's failure-behavior discipline mirrors Phase 4's `CHUNKING_SKIPPED` vs. exception distinction). A query composed entirely of terms absent from the corpus (`df(t) == 0` for every term) also returns `results=[]`, for the same reason: no chunk scores above zero, and **zero-score chunks are never returned** (`BM25-SAFE-02`, `config\bm25_contract.yaml`) — a score of exactly 0.0 means no lexical evidence connects the chunk to the query, and returning it would misrepresent an absence of match as a ranked result.

## M. Provenance Preservation

`[OFFICIAL SOURCE — Phase 5 build scope]` The required chain — *retrieval result → chunk_id → block_ids → page_numbers → document_id → source_family_id → jurisdiction → content_hash* — is asserted directly by `tests\test_phase_05_provenance.py`'s dedicated traceability test (mirroring Phase 3's and Phase 4's own critical-invariant tests). Every `RetrievalResult` carries these fields **unchanged** from the originating `Chunk` — BM25 never rewrites, infers, or reclassifies any of them. `score` is documented, in both the doc and the schema, as a lexical relevance signal only — never legal authority, never a citation (Phase 8/9 own that architecture).

## N. Determinism

`[ENGINEERING RECOMMENDATION]` Identical `chunks` + identical `Bm25Config` produce identical index statistics (`document_lengths`, `term_document_frequency`, `average_document_length`, `signature`); identical `(index, query_text, top_k)` produce identical `RetrievalResponse` (score, ordering, `chunk_id`s, serialized JSON) on every run (`tests\test_phase_05_determinism.py`, including a repeated-run byte-identical-JSON check). No randomness, no wall-clock read, no reliance on set/dict iteration order anywhere output-visible.

**Index identity (`src\retrieval\identity.compute_index_signature`):** a SHA-256 hash of the `Bm25Config` signature (which itself encodes `k1`, `b`, and the tokenizer policy version) plus the ordered `chunk_ids` and `content_hash`es of every indexed chunk. Changing any of `k1`/`b`/tokenizer policy/the exact chunk set changes the signature — this is the index's own version identity, and is explicitly **not** a regulatory document version (that concept, when it exists, lives in Phase 2's provenance schema, not here).

## O. Security/Resource Limits

`[ENGINEERING RECOMMENDATION]` Practical Phase 5 safeguards only — **no claim of comprehensive security** (`tests\test_phase_05_edge_cases.py`):

- **Malformed input:** `build_index` rejects non-`list` input and any element that isn't a real `chunking.models.Chunk` (`TypeError`); duplicate `chunk_id` values are rejected (`ValueError`) rather than silently corrupting the index's identity mapping.
- **Invalid configuration:** `Bm25Config` rejects a negative `k1`, a `b` outside `[0.0, 1.0]`, or an unsupported `tokenizer_version` at construction time.
- **Invalid query usage:** non-`str` query text and non-positive/non-integer `top_k` raise typed exceptions immediately, never a crash mid-scoring.
- **Extremely long chunk text / huge chunk counts / pathologically repeated tokens:** tested up to tens of thousands of tokens per chunk and thousands of chunks without error; scoring is linear in `(query terms) × (chunks)`, with no unbounded intermediate structure.
- **Unusual Unicode:** handled via the same NFKC-normalized, script-agnostic tokenizer as everything else (Section F).

**What Phase 5 does *not* protect against:** it performs no rate limiting, no query sanitization against downstream use (no HTML/SQL/prompt-injection concerns arise at this layer — those belong to whichever later phase actually executes untrusted input against a service), and builds no distributed or persisted index — this is an in-memory, single-process baseline only.

## P. Evaluation Methodology

`[ENGINEERING RECOMMENDATION]` (`src\retrieval\evaluation.py`, `tests\test_phase_05_evaluation.py`) Two standard information-retrieval metrics `[EXTERNAL RESEARCH — standard IR literature]`:

- **Precision@k** — fraction of the top-k retrieved `chunk_id`s that are in the known-relevant set.
- **Recall@k** — fraction of the known-relevant `chunk_id`s that appear within the top-k retrieved.

The benchmark itself is a small, fully synthetic fixture: a handful of synthetic chunks with deliberately engineered term overlap, and queries whose relevant `chunk_id`s are known *by construction* (not by any claim about real regulatory relevance). It exercises exact-term retrieval, partial-term retrieval, repeated-term frequency scoring, multilingual Unicode matching, irrelevant-chunk rejection, and top-k behavior. **This benchmark measures the engineering correctness of the BM25 baseline implementation — it does not, and cannot, represent real regulatory retrieval quality**, since no real regulatory corpus exists in this repository (`docs\DEVELOPMENT_RULES.md` Rule 7).

## Q. Limitations

`[ENGINEERING RECOMMENDATION]`

- Tokenization is script-agnostic but linguistically naive: no stemming, no lemmatization, no compound-word or agglutinative-morphology handling for any language.
- No stopword removal (Section E) — a deliberate, revisitable baseline choice, not an oversight.
- No spelling correction, fuzzy matching, or synonym expansion.
- BM25 parameters are textbook defaults, unvalidated against any real regulatory corpus (none exists yet).
- Index is in-memory and single-process only; no persistence, sharding, or incremental update is implemented.
- No relevance feedback or query expansion.

## R. Deferred Improvements

`[DEFERRED]` — not to be implemented until a later phase explicitly calls for them and/or Phase 16 benchmarking justifies them:

- Script-specific tokenization/segmentation (e.g. proper Tamil/Devanagari word-boundary handling beyond `\w+`).
- A versioned, per-language stopword policy.
- Stemming/lemmatization.
- BM25 parameter tuning against a real evaluation set.
- Index persistence/serialization for reuse across process restarts (a JSON serializer exists — Section H — but no on-disk index store is built here).
- rank_bm25 or any external BM25 library — the stdlib implementation here is preferred for the stated reasons (explicit parameters, deterministic testability, zero dependency surface); revisit only if a specific, measured limitation of this implementation is found.

## S. Source/Evidence Classification (self-check for this document)

`[ENGINEERING RECOMMENDATION]`

- Every design choice above carries a source label; the BM25 formula and IR metrics are labeled `[EXTERNAL RESEARCH]`/`[OFFICIAL SOURCE]` as standard-literature restatements, never presented as this project's own invention.
- No legal or regulatory claim is made anywhere in this document; `score` is explicitly and repeatedly distinguished from legal authority/citation validity (Sections A, M, and `config\retrieval_result_schema.yaml`).
- No fabricated regulatory fact, government document, or metadata value appears in this document or its fixtures — every test document is synthetic and marked `synthetic=true`.
- Parameter choices (`k1`, `b`) are explicitly disclaimed as un-tuned defaults, not claimed-optimal values.
- Every deferred technique is labeled `[DEFERRED]` with a stated revisit condition, per `docs\DEVELOPMENT_RULES.md` Rule 9.
