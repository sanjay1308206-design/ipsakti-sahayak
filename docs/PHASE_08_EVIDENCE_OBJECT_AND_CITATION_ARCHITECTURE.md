# PHASE 8 — EVIDENCE OBJECT + CITATION ARCHITECTURE

Status: CONTRACT + IMPLEMENTATION DOCUMENT (Phase 8 deliverable)
Authoritative source: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`
Governed by: `docs\MASTER_REFERENCE_LOCK.md`, `docs\DEVELOPMENT_RULES.md`, `docs\PHASE_07_HYBRID_FUSION_AND_RERANKING.md`
Machine-readable counterparts: `config\evidence_contract.yaml`, `config\evidence_schema.yaml`
Implementation: `src\evidence\models.py`, `identity.py`, `builder.py`, `validation.py`, `serialize.py`

**The Evidence layer is the trust boundary.** Retrieval says *"this chunk may be relevant."* Evidence says *"this exact chunk, with this exact provenance and source location, is the evidence object available to downstream systems."* Everything in this phase is deterministic; nothing here requires, calls, or depends on an LLM.

---

## A. Purpose

`[OFFICIAL SOURCE]` Master Reference Final Architecture Decision Lock names the pipeline stage *"Evidence Pack"* immediately after retrieval/reranking and before generation (`docs\MASTER_REFERENCE_LOCK.md` Section E: *"...→ Cross-Encoder Reranker → Evidence Pack → Generation..."*). Phase 8 implements exactly that stage: converting Phase 7's ranked candidates into backend-owned, deterministic Evidence objects and an EvidencePack, without generating any answer, claim, or citation validation.

## B. Scope

In scope: the canonical `Evidence` object, deterministic evidence/pack identity, verbatim-text integrity, the full provenance chain, an explicit `SourceLocation` view, a minimal `CitationTarget`, `EvidencePack` construction from Phase 7 candidates (selection, deduplication, ordering), serialization with tamper detection, and a synthetic construction-property benchmark.

Out of scope (no code for any of these exists in this repository): LLM answer generation, Gemini, Qwen, prompt templates for answering users, generated-claim construction, claim↔evidence binding from generated answers, citation validation of generated answers, formulation classification, the jurisdiction firewall, the confidence/abstention engine, human escalation, multilingual answer generation, a frontend, FastAPI, authentication/authorization, agents, a knowledge graph, production deployment, monitoring, corpus crawling, or automatic source downloading.

## C. Source Classification

Every non-trivial claim below carries one of the seven approved labels (`docs\DEVELOPMENT_RULES.md` Rule 1). No regulation, legal fact, source document, source URL, document identifier, page number, section number, legal conclusion, citation, dataset, API, or benchmark result is invented anywhere in this document or its implementation. Where upstream provenance genuinely lacks a field (version/effective-date, source URL), the gap is disclosed as `[DEFERRED]`/`[ASSUMPTION]`, never filled in (Section T/U).

## D. Relationship to Phase 7

`[ENGINEERING RECOMMENDATION]` Phase 8 **consumes** Phase 5/6/7's result objects (`RetrievalResult`, `DenseRetrievalResult`, `RrfResult`, `HybridRetrievalResult`) exactly as produced — none of `src\retrieval\*.py` is modified (`tests\test_phase_08_regression.py` asserts this by file-content check). Phase 8 is deliberately **not coupled to Phase 7 specifically**: `build_evidence_from_candidate` accepts *any* ranked candidate object exposing the standard provenance attribute names (`chunk_id`, `chunk_text`, `document_id`, `source_family_id`, `jurisdiction`, `content_hash`, `synthetic`, `page_numbers`, `block_ids`, `rank`), type-discriminating only for the retrieval-score fields that are inherently retrieval-specific (Section Q). This satisfies the explicit instruction to *"design the evidence layer around stable provenance and source location rather than retrieval-specific implementation details."*

## E. Relationship to Phase 9

`[ENGINEERING RECOMMENDATION]` Phase 9 owns **generated-answer citation validation**: *generated claim → citation reference → validation against an actual Evidence ID/source → PASS/FAIL*. Phase 8 builds the Evidence objects and `CitationTarget`s that pipeline will validate against — it does not run that pipeline itself. `resolve_citation_target` (Section L) only checks *"does this evidence_id exist in this EvidencePack"* — never *"does a generated claim correctly cite this evidence."* No generated-answer object of any kind exists anywhere in `src\evidence\`.

## F. Relationship to Phase 10

`[ENGINEERING RECOMMENDATION]` Phase 10 will eventually consume `EvidencePack` to ground its generation. Phase 8 produces **only structured evidence** — no answer, explanation, legal recommendation, regulatory interpretation, or natural-language response is generated anywhere in this phase (verified by the phase-boundary audit, `tests\test_phase_08_regression.py`).

## G. Evidence Object

`[ENGINEERING RECOMMENDATION]` (`src\evidence\models.Evidence`) Fields: `evidence_id`, `evidence_schema_version`, `evidence_type` (currently only `"CHUNK"` — a closed, versioned vocabulary), `evidence_text` (verbatim), `evidence_text_hash`, `chunk_id`, `document_id`, `source_family_id`, `jurisdiction`, `content_hash`, `synthetic`, `page_numbers`, `block_ids`, `retrieval_metadata`, `version_info`, and optional `section_heading_text`/`section_heading_level`. **No legal conclusion is ever stored on this object** — every field is either verbatim source text, a provenance identifier, or a documented retrieval signal. `evidence_text` is never paraphrased, summarized, or rewritten (`tests\test_phase_08_integrity.py` asserts exact text equality against the originating candidate).

## H. Evidence Identity

`[ENGINEERING RECOMMENDATION]` (`src\evidence\identity.compute_evidence_id`) A SHA-256 hash over: `evidence_schema_version`, `chunk_id`, `content_hash`, `document_id`, `source_family_id`, `jurisdiction`, `block_ids`, and `page_numbers`. **Backend-generated, deterministic, collision-resistant, reproducible, and entirely independent of any LLM output.** Never a FAISS/BM25 array position, a random UUID, or a generated display name (`EVIDENCE-SAFE-02`, `config\evidence_contract.yaml`).

**`evidence_id` is distinct from, and never substitutes for, `chunk_id`.** `chunk_id` remains the underlying Phase 4 retrieval identity everywhere in this codebase; `evidence_id` is a separate, evidence-layer-scoped identity, versioned by `evidence_schema_version` — if the evidence schema itself changes, `evidence_id` changes even though the same chunk's `chunk_id` does not. This is the literal implementation of the instruction *"Do NOT replace chunk_id with evidence_id internally."*

## I. Evidence Text Integrity

`[ENGINEERING RECOMMENDATION]` `evidence_text` is copied directly from `candidate.chunk_text` with no transformation (`build_evidence_from_candidate`, Section D). `evidence_text_hash = SHA256(evidence_text)` is computed once, at construction time, from the same text — making tampering **architecturally impossible** through the normal construction path. Tampering becomes *detectable* specifically when an `Evidence` object is deserialized or otherwise re-verified: `validation.verify_evidence_text_integrity` recomputes the hash from the loaded `evidence_text` and compares it to the loaded `evidence_text_hash`, raising `EvidenceIntegrityError` on any mismatch (mirrors Phase 6's dense-index signature re-verification pattern exactly).

## J. Provenance Chain

`[OFFICIAL SOURCE — Phase 8 build scope]` The full, unshortened chain is preserved on every `Evidence` object and asserted directly by `tests\test_phase_08_provenance.py`:

```
evidence_id → chunk_id → block_id(s) → page(s) → document_id → source_family_id → jurisdiction → content_hash
```

Never shortened for convenience, never replaced by a display title, never collapsed into `evidence_id` alone.

## K. Source Location

`[ENGINEERING RECOMMENDATION]` `Evidence.source_location` is a **computed property** (`models.SourceLocation`), not a second stored copy of the same fields — Development Rules forbid redundant duplication, and a property is always trivially reconstructable from `Evidence`'s own flat fields. It carries `document_id`, `source_family_id`, `jurisdiction`, `content_hash`, `page_numbers`, `block_ids`, and `section_heading_text`/`section_heading_level` **when actually present on the originating candidate** — which, as of Phase 5/6/7's current result contracts, is *never* (none of `RetrievalResult`/`DenseRetrievalResult`/`RrfResult`/`HybridRetrievalResult` propagate Phase 4's heading metadata forward). This is a disclosed, honest gap, not a fabrication: no fake section numbers, paragraph numbers, or URLs are ever created (`config\evidence_contract.yaml` output requirements).

## L. Citation Target

`[ENGINEERING RECOMMENDATION]` `models.CitationTarget(evidence_id, schema_version)` — the minimal object the instructions call for: *CitationTarget → Evidence ID → Authoritative Evidence Object → exact source location.* `builder.resolve_citation_target(citation_target, pack)` performs exactly that lookup, raising `EvidenceNotFoundError` if the referenced `evidence_id` is not present in the given `EvidencePack` (`EVIDENCE-SAFE-06`) — directly testing the "EvidencePack containing fabricated evidence IDs" validation category (Section Y) without touching generated-answer validation (Phase 9's boundary, Section E).

## M. EvidencePack

`[ENGINEERING RECOMMENDATION]` `models.EvidencePack(pack_id, schema_version, query, evidence_items, construction_metadata)`. `pack_id` **is** the deterministic identity/signature the instructions ask for — computed from `pack_schema_version` + `query` + the ordered evidence IDs actually included + the selection config's own signature (`identity.compute_pack_id`). A single field satisfies both the "pack_id" and "deterministic signature" requirements rather than two redundant ones. `jurisdictions`/`source_family_ids` are computed properties (derived summaries, Section S), never separately stored. `EvidencePack` contains **only** real `Evidence` objects — never a generated answer, claim, LLM reasoning, or hallucinated citation (enforced structurally: there is no field on this dataclass that could hold one).

## N. Candidate-to-Evidence Selection

`[ENGINEERING RECOMMENDATION]` `models.EvidenceSelectionConfig(max_evidence_items=10, max_rank=None, min_score=None)` — every parameter explicit, validated, and documented; no hidden default buried in a function body. `min_score`, when set, filters on the *most-refined-available* score per candidate (`reranker_score` → `rrf_score` → raw `score`, in that priority order — `builder._primary_score`), explicitly documented as a pure retrieval-signal filter, **never a legal relevance threshold** (the instruction's own phrasing, repeated verbatim in `config\evidence_contract.yaml`). Selection is 100% deterministic candidate-list processing — no LLM-based evidence selector exists anywhere.

## O. Deduplication

`[ENGINEERING RECOMMENDATION]` The same underlying `chunk_id` retrieved through BM25, dense, RRF, or reranking always maps to **exactly one** Evidence identity within one `build_evidence_pack` call. Policy: **first occurrence, by input list order, wins**; later occurrences of the same `chunk_id` are dropped (counted in `construction_metadata["dropped_duplicate_chunk_id_count"]`, never silently discarded without a trace). This is deliberately simple rather than merging retrieval metadata across occurrences — a documented, defensible choice (Section X, alternatives). In the normal pipeline (a single `HybridRetrievalResponse.results` list), this is a no-op: Phase 7's own RRF fusion already guarantees one candidate per `chunk_id` before Phase 8 ever sees it. The dedup logic exists for robustness against a caller merging candidate lists from multiple retrieval stages directly (`tests\test_phase_08_deduplication.py`).

**Similar-looking text is never merged.** Only an *identical* `chunk_id` triggers deduplication — two different chunks with coincidentally similar text remain two separate Evidence objects, exactly as the instruction requires ("do not merge different chunks merely because their text looks similar").

## P. Ordering

`[ENGINEERING RECOMMENDATION]` Deterministic total order: **ascending rank, then ascending `chunk_id`** (`build_evidence_pack`'s explicit `sort()` call) — never `set`/`dict` iteration order, insertion order alone, or randomness. Applied *after* deduplication and filtering, *before* the `max_evidence_items` truncation, so the retained evidence is always the best-ranked surviving candidates. Repeated construction with identical inputs is asserted to be byte-identical (`tests\test_phase_08_determinism.py`).

## Q. Retrieval Metadata

`[ENGINEERING RECOMMENDATION]` `models.RetrievalMetadata` cleanly separates `rank`/`bm25_rank`/`bm25_score`/`dense_rank`/`dense_score`/`dense_model_identity`/`rrf_score`/`reranker_score`/`reranker_model_identity` from `Evidence`'s own identity/provenance fields — a structurally distinct nested object, never intermixed. `builder._extract_retrieval_metadata` is type-aware for the four known Phase 5/6/7 result types (populating exactly the fields each one actually carries) and falls back to generic attribute lookup for any future/unknown candidate type, fabricating nothing. **None of these scores is ever legal confidence** — repeated verbatim from Phase 5/6/7's own score-semantics discipline.

## R. Authoritativeness

`[OFFICIAL SOURCE]` Phase 8 does not independently decide that any document is legally authoritative. `source_family_id` is preserved **unchanged** from whatever Phase 2's authority matrix / Phase 3 admission boundary already established — Phase 8 reuses this field, never creates a second competing authority hierarchy, and never guesses a value when this metadata is (hypothetically) missing (`Evidence.__post_init__` requires `source_family_id` to be a non-empty string, but does not itself validate it against `config\authority_matrix.yaml` — that validation is Phase 2/3's own boundary, already enforced before any chunk exists).

## S. Jurisdiction Metadata

`[ENGINEERING RECOMMENDATION]` `jurisdiction` is preserved unchanged as passthrough metadata (`EvidencePack.jurisdictions` is a derived, read-only summary property). Phase 8 does **not** implement the Phase 12 jurisdiction firewall — no filtering, routing, or India/international policy decision is made anywhere in `src\evidence\`.

## T. Version/Effective-Date Limitations

`[DEFERRED]` / `[ASSUMPTION]` Phase 2's `config\corpus_provenance_schema.yaml` defines `version`, `version_known`, `effective_date`, `effective_date_known`, `publication_date`, and `supersession_status` — but **none of these fields are currently carried forward** by Phase 3's `ExtractedDocument`, Phase 4's `Chunk`, or any Phase 5/6/7 retrieval result (this exact gap was already disclosed in `docs\PHASE_04_LEGAL_AWARE_CHUNKING.md`'s own acceptance-gate note and re-confirmed here by direct inspection of every intervening contract). `models.VersionInfo` therefore always holds `version=None, version_known=False, effective_date=None, effective_date_known=False, publication_date=None, supersession_status=None` for every Evidence object this phase can currently produce — a structurally visible, honestly-disclosed gap, not a fabrication. **What would resolve this:** a future, explicitly-authorized Phase 3/4 amendment propagating these fields forward (the same kind of amendment already named as the resolution path in Phase 4's own tracker entry) would let Phase 8 populate `VersionInfo` with no schema change here.

## U. Source URL Policy

`[DEFERRED]` / `[ASSUMPTION]` Phase 2's provenance schema has a per-document `source_reference` field (a URL/official reference, distinct from the source family's portal URL) — but it is likewise **not propagated** past Phase 2's own admission-policy layer into anything Phase 8 can access. `config\authority_matrix.yaml` *does* carry a per-source-family portal `url` (e.g. `https://www.indiacode.nic.in/`) — a real, non-fabricated, already-existing configuration value — but Phase 8 deliberately does **not** surface it as a document-level `source_url` on `Evidence`, since conflating a general source-family portal link with a specific document citation target would itself be misleading. No `Evidence` object in this phase carries a `source_url` field at all; it is simply absent rather than set to a guessed or constructed value. **Never constructed from a document name. Never guessed.**

## V. Synthetic Evidence Safety

`[ENGINEERING RECOMMENDATION]` `synthetic` is copied verbatim from the originating candidate at every step — `synthetic=true` on a source chunk survives unchanged through retrieval → Evidence → EvidencePack (`tests\test_phase_08_multilingual.py` and `test_phase_08_evidence.py` assert this explicitly for both `True` and `False`). Synthetic test material is never represented as real regulatory evidence anywhere in this pipeline.

## W. Serialization

`[ENGINEERING RECOMMENDATION]` (`src\evidence\serialize.py`) Deterministic JSON (`sort_keys=True`, fixed separators, UTF-8) for `Evidence`, `EvidencePack`, and `CitationTarget`. **No arbitrary/executable deserialization anywhere** — every payload is plain data (str/int/float/bool/list/dict); `pickle` is never used. `evidence_from_dict`/`evidence_pack_from_dict` reconstruct every field explicitly and immediately re-verify integrity (Section X) — a missing key, wrong type, tampered hash, or forged ID raises `EvidenceIntegrityError`, never a silently-repaired partial object. `Evidence.source_location` (a computed property) is intentionally **not** duplicated into the serialized payload — it is always reconstructable from the flat fields that are persisted.

## X. Evidence Signatures

`[ENGINEERING RECOMMENDATION]` Exactly documented in Section H (evidence) and Section M (pack). **These are engineering hashes only — never a cryptographic legal signature, never a citation, never evidence of legal authority.** `validation.verify_evidence_identity`/`verify_pack_identity` recompute each signature from the object's own other fields and compare, catching a hand-forged ID that happens to be well-typed but inconsistent with its claimed provenance.

## Y. Validation

`[ENGINEERING RECOMMENDATION]` Two layers, matching the project's established pattern: **structural** validation (missing evidence ID, empty evidence text, malformed page numbers/block IDs, invalid synthetic flag, invalid content-hash shape, invalid schema version) happens in each dataclass's own `__post_init__` (`models.py`) — fails immediately at construction, always. **Identity/consistency** validation (mismatched evidence text/hash, duplicate evidence IDs, duplicate underlying chunk IDs, forged evidence/pack IDs, malformed `EvidencePack` referencing fabricated evidence) happens in `validation.py`'s dedicated functions, since these require comparing an object's fields *against each other* or *against a recomputed value* — impossible to catch at construction time alone for a hand-crafted or post-hoc-corrupted object. **Validation fails closed**: every integrity violation raises `EvidenceIntegrityError` (a `ValueError` subclass), never a silent repair (`tests\test_phase_08_integrity.py`).

## Z. Security

`[ENGINEERING RECOMMENDATION]` (`tests\test_phase_08_security.py`) Tested: prompt-injection-like text inside `evidence_text`, HTML/script-like text, SQL-like text, extremely long evidence text, Unicode/mixed-script text, null/empty required fields, malformed serialized JSON, tampered `evidence_text_hash`/`evidence_id`/`pack_id`, duplicate evidence/chunk IDs, path-like strings inside text, fake URLs/document identifiers embedded in text. **Evidence text is always treated strictly as data** — `build_evidence_from_candidate` never executes it, never parses it as configuration, and nothing in `src\evidence\` lets candidate text alter evidence-ID generation, selection limits, schema version, or filesystem paths. No claim of comprehensive security.

## AA. Multilingual Preservation

`[ENGINEERING RECOMMENDATION]` `tests\test_phase_08_multilingual.py` exercises English, Devanagari, Tamil, and mixed-script `evidence_text` through the full candidate → Evidence → EvidencePack path, asserting **byte-for-byte** preservation (no normalization, no rewriting of the verbatim representation). Where identity computation needs a canonical form (it does not, here — `compute_evidence_id` never touches `evidence_text` at all, only structural provenance fields), it would remain strictly separate from the verbatim `evidence_text` field; this phase's identity hash is already text-independent by design; the separate `evidence_text_hash` field is what changes if the text itself changes.

## AB. Benchmark Methodology

`[ENGINEERING RECOMMENDATION]` (`tests\test_phase_08_evaluation.py`) A small, fully synthetic benchmark (`synthetic=true`, `SYNTHETIC-BENCH-08-*` document IDs) measuring **implementation properties**, not legal-answer quality: candidate-to-evidence traceability (every evidence item's `chunk_id` matches a real input candidate), deduplication correctness (a mixed BM25+dense candidate list for overlapping chunks collapses to the expected evidence count), deterministic pack identity (repeated construction is byte-identical), exact evidence-text preservation, and serialization round-trip correctness. **This is not a legal-answer benchmark and does not measure regulatory correctness** — no real regulatory corpus or real embedding/reranker model is involved.

## AC. Limitations

`[ENGINEERING RECOMMENDATION]`

- `VersionInfo` is always "not available" — a real gap in the current pipeline, not a Phase 8 defect (Section T).
- `source_url` does not exist on `Evidence` at all — the per-document URL is not available anywhere upstream (Section U).
- `section_heading_text`/`section_heading_level` are always `None` in practice today, since no Phase 5/6/7 result type currently carries them.
- Deduplication is "first occurrence wins," not a merge of retrieval metadata across occurrences — simple and deterministic, but discards the *other* occurrence's scores (documented trade-off, Section O/X).
- No production-scale performance characteristics are measured (benchmark corpora here are small and synthetic).

## AD. Deferred Items

`[DEFERRED]`

- Populating `VersionInfo` once Phase 3/4 propagate version/effective-date fields forward.
- Surfacing a document-level `source_url` once Phase 2/3 propagate `source_reference` forward.
- A merged (rather than first-wins) deduplication strategy, if a concrete downstream need for combined retrieval metadata is demonstrated.
- Any additional `evidence_type` beyond `"CHUNK"` (e.g. a structured table-row evidence type), if a concrete need arises.
- Everything Phase 9/10 own (generated-answer citation validation, claim/evidence binding, grounded generation) — explicitly not this phase's job.

## AE. Acceptance Gate

`[ENGINEERING RECOMMENDATION]` (no separate Master Reference one-liner exists for Phase 8 beyond the pipeline diagram itself — Section A) As defined for this implementation: a canonical `Evidence` object exists; evidence identity is backend-owned, deterministic, and independent of LLM output; evidence text is verbatim and its integrity is validated; the full provenance chain is preserved; source location is explicit (and honest about what is unavailable); a `CitationTarget` can reference real Evidence IDs and resolve against a real `EvidencePack`; candidate-to-evidence construction is deterministic; duplicate retrieval occurrences do not create duplicate evidence; retrieval scores remain separate from evidence identity; the synthetic flag survives the full pipeline; serialization is deterministic and round-trip safe with tamper detection; multilingual evidence text is preserved; no LLM is required anywhere; no generated answer, Phase 9 validation, or Phase 10 generation exists. **MET** — see the Phase 8 implementation report for exact evidence.

## AF. Validation Results

`[ENGINEERING RECOMMENDATION]` Exact status, with no fabricated numbers: all Phase 8 automated tests pass (exact count in the Phase 8 implementation report) — evidence/identity/provenance/integrity/deduplication/determinism/serialization/multilingual/security tests and the synthetic construction-property benchmark. No real-model dependency exists anywhere in Phase 8 (it is 100% deterministic, stdlib-only), so there is no "NOT VALIDATED — model unavailable" disclosure needed here, unlike Phase 6/7 — the one honest gap in this phase is upstream-data availability (`VersionInfo`, `source_url`), disclosed in Sections T/U, not a validation gap in Phase 8's own code.
