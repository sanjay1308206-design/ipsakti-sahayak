# PHASE 4 — LEGAL-AWARE CHUNKING

Status: CONTRACT + IMPLEMENTATION DOCUMENT (Phase 4 deliverable)
Authoritative source: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`
Governed by: `docs\MASTER_REFERENCE_LOCK.md`, `docs\DEVELOPMENT_RULES.md`, `docs\PHASE_03_DOCUMENT_INGESTION.md`, `docs\PHASE_03_LEGAL_STRUCTURE_EXTRACTION.md`
Machine-readable counterparts: `config\chunking_contract.yaml`, `config\chunk_schema.yaml`
Implementation: `src\chunking\`

**Terminology note `[ENGINEERING RECOMMENDATION]`:** "Legal-aware" here means the chunker respects the *document* structure Phase 3 already detected (headings, sections, paragraphs, lists, tables) when deciding chunk boundaries. It does **not** mean the chunker performs legal interpretation, and a chunk's structural metadata is never asserted to be legally authoritative — the same non-goal Phase 3 states for headings (`docs\PHASE_03_LEGAL_STRUCTURE_EXTRACTION.md` Section 9) applies here unchanged.

---

## A. Purpose

`[OFFICIAL SOURCE]` Master Reference Phase 4 goal: *"Create retrieval units that preserve legal meaning."* Build scope: *"Section/subsection/article-aware chunking, overlap only where needed, metadata propagation."* Acceptance gate: *"Retrieved chunks retain jurisdiction, section, version, and effective-date context."*

`[ENGINEERING RECOMMENDATION]` Phase 4 transforms a Phase 3 `ExtractedDocument` into a deterministic sequence of `Chunk` records — retrieval-ready units that never lose the provenance chain back to their source blocks. It performs no retrieval, no indexing, no embedding, and no generation; it produces the units later phases will retrieve over.

**On "overlap only where needed" `[ENGINEERING RECOMMENDATION]`:** this phase does not implement sliding-window overlap between chunks. Overlap exists in the Master Reference roadmap as a technique for recovering context lost at an arbitrary character-count boundary; because this chunker splits *only* at structural boundaries (or, when a single block is oversized, at the block's own text) rather than at arbitrary offsets, the specific problem overlap solves does not arise here — every chunk already carries its section-heading context as metadata (Section F), and a split block's siblings are exactly reconstructable (Section H). Overlap is therefore `[DEFERRED]`: revisit only if Phase 16 benchmarking shows retrieval quality actually suffers from its absence.

## B. Input Contract

`[ENGINEERING RECOMMENDATION]` The single entry point, `src\chunking\chunker.chunk_document(document, config=None)`, accepts exactly:

1. **`document`** — an actual `ingestion.models.ExtractedDocument` instance (the real in-memory return value of `ingestion.pipeline.ingest_document`/`ingest_bytes`), never a serialized JSON dict, a file path, or raw bytes. Passing anything else raises `TypeError` immediately (Section O).
2. **`config`** — an optional `chunking.models.ChunkingConfig`; defaults to `ChunkingConfig()` (1000 Unicode code points per chunk) when omitted.

No third input is accepted. Phase 4 never re-parses source bytes, never re-derives structure Phase 3 did not already detect, and never reads Phase 2's authority matrix or admission policy directly — a document reaching `chunk_document` has, by construction, already passed Phase 3's own admission boundary.

## C. Output Contract

`[ENGINEERING RECOMMENDATION]` `chunk_document` returns a `chunking.models.ChunkingResult`:

- `document_id`, `config_signature`, `chunking_status` (one of `CHUNKING_SUCCESS` / `CHUNKING_PARTIAL` / `CHUNKING_SKIPPED` — engineering pipeline states, not legal classifications, exactly the same vocabulary discipline as `docs\PHASE_03_DOCUMENT_INGESTION.md` Section M).
- `chunks: list[Chunk]`, `warnings: list[str]` (document-level, de-duplicated union of every chunk's own warnings).

`src\chunking\serialize.to_json` produces deterministic JSON (`sort_keys=True`, fixed separators, UTF-8) matching `config\chunk_schema.yaml`, with any wall-clock chunking timestamp kept in a separate `chunking_metadata` block outside `content` (mirroring `docs\PHASE_03_DOCUMENT_INGESTION.md` Section O.2). No database, vector index, or retrieval index is created — this is a single-document JSON artifact for Phase 5+ to consume.

## D. Chunk Identity

`[ENGINEERING RECOMMENDATION]` `chunk_id` is a SHA-256 hex digest of canonical identity fields (`src\chunking\identity.compute_chunk_id`): a fixed version tag, `document_id`, `content_hash`, the `ChunkingConfig` signature, the ordered list of contributing `block_id`s, and `split_index`. It is never a random UUID, timestamp, or process/machine-derived value (Section 7 of the originating instruction; tested directly in `tests\test_phase_04_determinism.py`).

**This is an engineering identifier only.** `chunk_id` MUST NOT be presented as, treated as, or accepted in place of a legal citation. Phase 8 (Evidence Object & Citation Architecture) owns citation identity; a future citation record MAY reference a `chunk_id` as one of several supporting fields, but `chunk_id` itself carries no claim of legal authority, source authenticity beyond Phase 3's own integrity check, or citation validity.

`chunk_sequence` is a separate, simple monotonically increasing integer (starting at 1) recording document reading order — a position, not an identity.

## E. Structural Boundary Rules

`[ENGINEERING RECOMMENDATION]` (`src\chunking\rules.py`, `src\chunking\chunker._pack_section`):

1. All blocks across all pages are flattened into one reading-order list, trusting (and verifying — Section P) Phase 3's own monotonically increasing `sequence` invariant (`docs\PHASE_03_LEGAL_STRUCTURE_EXTRACTION.md` Section 8).
2. The flattened list is partitioned into **section groups**: a new group starts at every `HEADING` block; blocks appearing before the first heading (if any) form a leading group with no heading (Section F). No boundary is invented beyond what Phase 3 already detected as a heading.
3. Within a section group, blocks are packed into one or more chunks by **greedy accumulation**: blocks are added to a chunk-in-progress, joined by a fixed separator (`"\n\n"`), until the next block would push the joined text past `max_chunk_size_chars` — at which point the current chunk is emitted and a new one starts with that block.
4. A `TABLE` block always flushes any in-progress chunk and becomes its own chunk (or row-group of chunks if oversized — Section I). It is never merged with surrounding paragraph text.
5. `LIST`/`LIST_ITEM` blocks are **not** given special boundary treatment beyond the derived `list_group_id` (Section I) — they participate in ordinary greedy accumulation, so a heading + its list normally end up in one chunk unless size forces a split.

## F. Section/Context Preservation

`[ENGINEERING RECOMMENDATION]` Every chunk carries `section_heading_block_id`, `section_heading_text`, and `section_heading_level` — copied from the section's governing `HEADING` block (or `null`/`null`/`null` when no heading precedes this content; Phase 4 never fabricates a heading to fill this gap — `CHUNK-SAFE-04`, `config\chunking_contract.yaml`).

**This is metadata, not a second copy of extracted content for retrieval purposes.** The heading block's own text appears in a chunk's `text` field exactly once — in whichever chunk actually contains that block (normally the section's first chunk). `section_heading_text` on every *other* chunk in that section is a read-only navigational pointer, clearly a distinct field from `text`, never concatenated into it.

## G. Maximum Chunk-Size Policy

`[ENGINEERING RECOMMENDATION]` `ChunkingConfig.max_chunk_size_chars` (default 1000) is measured in **Unicode code points** (Python `len(str)`) — not bytes, not tokens. A tokenizer dependency was deliberately not added: no phase before Phase 6/7 (embeddings/reranking) has an actual token-budget requirement, and adding one here would be exactly the kind of premature dependency `docs\DEVELOPMENT_RULES.md` Rule 6 forbids. `size_unit` is recorded on every chunk (`"UNICODE_CODE_POINTS"`) so a later phase can convert if it ever needs to.

`max_chunk_size_chars` is fully configurable per call (`ChunkingConfig(max_chunk_size_chars=...)`), never hard-coded inside the packing logic itself. `ChunkingConfig.__post_init__` rejects a non-positive or non-integer value (including `bool`, which is an `int` subclass in Python) with `ValueError` — an invalid configuration is refused immediately, not silently coerced (Section P).

**What could invalidate this choice `[ASSUMPTION]`:** a code-point budget is a reasonable proxy for "retrieval unit size" but is not proportional to embedding-model token count across scripts (e.g., Devanagari text tokenizes differently from ASCII). If Phase 6/7 benchmarking shows this materially skews retrieval unit sizing across the evaluated languages, revisit with an actual tokenizer at that phase — not here.

## H. Oversized-Block Handling

`[ENGINEERING RECOMMENDATION]` (`src\chunking\rules.split_text_preserving_all_characters`) When a single block's text exceeds `max_chunk_size_chars`:

1. Any chunk-in-progress for the section is flushed first (the oversized block never merges with unrelated neighbors).
2. The block's original `block_id` is preserved unchanged across every resulting chunk (`block_ids == [original_block_id]` on each piece).
3. The text is split into contiguous, non-overlapping slices, each at most `max_chunk_size_chars` code points, preferring to break at the last whitespace character within the size window (kept with the earlier piece) and falling back to a hard slice only when no whitespace exists in the window (guaranteeing forward progress on pathological input — Section Q).
4. Ordering is preserved via `split_index`/`split_count` (0-based / total), and `is_split=True` is set — never silently indistinguishable from a normal chunk.
5. **No text is ever lost or duplicated**: `"".join(pieces) == original_text` exactly, always — because pieces are pure contiguous slices with no rewriting. This is the literal invariant `tests\test_phase_04_edge_cases.py` and `tests\test_phase_04_boundaries.py` assert.
6. A `BLOCK_SPLIT_DUE_TO_SIZE` warning is attached to every resulting piece — a split is always visible, never silent.

## I. Tables and Lists

`[ENGINEERING RECOMMENDATION]`

**Tables:** A Phase 3 `TABLE` block's structured `rows` are preserved unchanged in the chunk's `table_rows` field. `text` carries a deterministic flattened rendering (`" | "`-joined cells, newline-joined rows — `src\chunking\rules.render_table_rows`) purely for lexical-retrieval usefulness; this is the *only* normalization Phase 4 performs beyond joining separate blocks' verbatim text with a fixed separator (Section 15 of the originating instruction), and it is fully reversible from `table_rows` alone. A `colspan`/`rowspan` warning already raised by Phase 3 (`TABLE_STRUCTURE_SIMPLIFIED`) is propagated unchanged, never re-derived.

If a table's flattened rendering exceeds `max_chunk_size_chars`, it is split at **whole-row boundaries only** (`src\chunking\rules.split_table_rows`) — never inside a row, so row/column meaning is never mangled. If a single row's own rendering exceeds the limit, that row becomes its own chunk unsplit (a documented size exception — `TABLE_ROW_EXCEEDS_MAX_SIZE`), because splitting inside a row cannot preserve column meaning and Phase 4 will not attempt it. No new PDF/TEXT table-extraction capability is added here; Phase 3's `NOT_ATTEMPTED_FOR_PDF` / `NOT_APPLICABLE` statuses are simply respected (there is nothing to chunk).

**Lists:** `LIST`/`LIST_ITEM` blocks are not forced into their own chunk the way tables are — they flow through ordinary greedy accumulation, normally keeping a list together with its heading and marker. To satisfy "preserve list identity if available" where Phase 3 itself does not assign one, Phase 4 derives `list_group_id`: the `block_id` of the nearest preceding `LIST` marker among a chunk's contributing blocks (reset at the next `HEADING`, `TABLE`, or non-`LIST_ITEM` block — mirroring the exact adjacency pattern Phase 3 already uses for `parent_section`). List text is never rewritten, reordered, or had items separated from earlier siblings within a size-forced split — order and `list_group_id` continuity are preserved (`tests\test_phase_04_boundaries.py`, `tests\test_phase_04_chunking.py`).

## J. Page Boundaries

`[OFFICIAL SOURCE]` A chunk records **every** page number its contributing blocks touch (`page_numbers`, sorted, de-duplicated) — never just the first or last. This is possible because Phase 3 already assigns a single, document-wide monotonically increasing `sequence` to blocks across page boundaries (PDF included), so a chunk may legitimately span two pages when the size budget allows a heading on page N and its continuation on page N+1 to share one chunk (`tests\test_phase_04_boundaries.py::test_pdf_multi_page_document_produces_page_spanning_chunk`). Page boundaries are never themselves used as a forced chunk boundary — only the structural rules in Section E and the size limit in Section G ever force a split, so a heading/paragraph pair separated only by a PDF page break stays together whenever it fits.

## K. Heading Hierarchy

`[ENGINEERING RECOMMENDATION]` `section_heading_level` is copied verbatim from Phase 3's `heading_level` (an integer 1–6, the string `"UNKNOWN"`, or `null`) — Phase 4 never infers or upgrades a level Phase 3 could not confidently assign, and never reorders sections by inferred nesting depth. A subsection (e.g. `heading_level=2`) simply starts its own section group like any other heading (Section E); Phase 4 does not attempt to nest child sections inside a parent section's chunk, since Phase 3 provides no reliable "this heading closes at this later heading" signal beyond flat reading order.

## L. Provenance Preservation

`[OFFICIAL SOURCE — Phase 4 build scope]` The required chain — *chunk → block(s) → page(s) → document → source family → jurisdiction → content hash* — is asserted directly by `tests\test_phase_04_provenance.py`'s dedicated traceability test (Phase 4's critical invariant, mirroring Phase 3's own Section O). Every `Chunk` carries `document_id`, `source_family_id`, `jurisdiction`, `content_hash` (the document's own `integrity.claimed_content_hash` — Phase 3 already guarantees `claimed == computed` before a document can exist at all, per `docs\PHASE_03_DOCUMENT_INGESTION.md` Section E), `synthetic`, `page_numbers`, and a non-empty `block_ids`. A chunk can never become an orphaned text fragment (`CHUNK-SAFE-01`).

**Disclosed gap against the Master Reference's one-line Phase 4 acceptance text `[ASSUMPTION]`:** `docs\PHASE_TRACKER.md`'s original one-line acceptance gate for Phase 4 (quoting the Master Reference roadmap) reads *"Retrieved chunks retain jurisdiction, section, version, and effective-date context."* Jurisdiction and section context are fully retained (this section). **Version and effective-date context are not currently retained**, because `ingestion.models.ExtractedDocument` itself does not carry `version`/`effective_date` forward from the Phase 2 provenance record — a Phase 3 design decision, proven intentional by `tests\test_phase_03_provenance.py::test_missing_version_is_not_silently_treated_as_current` (which asserts `"version" not in` Phase 3's own output). Phase 4 cannot preserve what Phase 3 never carries to it; propagating a fabricated or re-derived version/effective-date here would itself violate `docs\DEVELOPMENT_RULES.md` Rule 7 (no invented facts). This gap is not silently absorbed: the acceptance-gate wording actually being validated for Phase 4's completion is the fuller, restated version given directly for this implementation (block/page/document/source-family/jurisdiction/content-hash chain + deterministic identity — Section L, tested in full), matching the same restatement pattern Phase 3's own tracker entry already uses relative to its one-line Master Reference source text. **What would resolve this:** a future, explicitly-authorized Phase 3 amendment adding `version_known`/`effective_date_known` (and the values, when known) as verbatim passthrough fields on `ExtractedDocument` — the same treatment already given to `document_id`/`source_family_id`/`jurisdiction`/`synthetic` — would let Phase 4 carry them onto `Chunk` with no further design change needed here.

## M. Determinism Requirements

`[ENGINEERING RECOMMENDATION]` Running `chunk_document` twice on the same `ExtractedDocument` with the same `ChunkingConfig` produces identical chunk count, ordering, `chunk_id`s, text, metadata, and serialized JSON — asserted directly (`tests\test_phase_04_determinism.py`, including a 10-repetition byte-identical-JSON check). No randomness, no wall-clock read, no environment-dependent ordering, and no reliance on Python set/dict iteration order for anything that reaches output (block/chunk ordering is always list-based, not set-based).

## N. Synthetic Fixture Policy

`[ENGINEERING RECOMMENDATION]` All Phase 4 test documents are synthetic, built via `tests\_provenance_fixtures.make_provenance` (always `synthetic=True`) and the existing `tests\_pdf_fixtures.py` generators — no government document is downloaded or committed. `Chunk.synthetic` is propagated verbatim from `ExtractedDocument.synthetic` (`CHUNK-SAFE-02`) — never dropped, never defaulted, never flipped — the same safety property Phase 3 guarantees for its own output (`PROV-SAFE-01`/`05`, `config\corpus_provenance_schema.yaml`).

## O. Failure Behavior

`[ENGINEERING RECOMMENDATION]` Phase 4 distinguishes a **programming-contract violation** from a **legitimate empty-content case**:

- `TypeError` — `document` is not an `ingestion.models.ExtractedDocument`. A caller error, not a data-quality state.
- `ValueError` — an invalid `ChunkingConfig` (Section G), or a source `ExtractedDocument` whose blocks violate an invariant Phase 4 depends on and will not silently guess around (non-string `text`, non-integer `page_number`, an unrecognized `block_type`, or blocks not in monotonically increasing `sequence` order — Section P). These fail loudly and immediately, before any chunk is produced.
- `CHUNKING_SKIPPED` — a well-formed document with **zero blocks to chunk** (e.g. Phase 3 reported `OCR_REQUIRED`/`EXTRACTION_FAILED` with empty pages). This is not an error: nothing was lost, there was simply nothing to chunk.
- `CHUNKING_PARTIAL` — at least one chunk was produced, but some warning fired (a block or table was split, or a chunk ended up text-empty).
- `CHUNKING_SUCCESS` — at least one chunk, no warnings.

`chunk_document` never raises an uncaught exception for a well-formed document and valid config (`CHUNK-SAFE-05`).

## P. Security Considerations

`[ENGINEERING RECOMMENDATION]` Practical Phase 4 safeguards only — **no claim of comprehensive security** (`tests\test_phase_04_edge_cases.py`):

- **Malformed structural objects:** every block's `text` (must be `str`), `block_id` (non-empty `str`), `page_number` (`int`), and `block_type` (a recognized value) is validated before chunking begins; a violation raises `ValueError` rather than crashing obscurely mid-run or silently producing corrupt output.
- **Adversarial ordering:** `flatten_blocks` verifies Phase 3's own monotonic-`sequence` invariant and refuses (`ValueError`) to guess a plausible-looking ordering for out-of-sequence input rather than silently producing a wrong-but-confident answer.
- **Extremely long single blocks / pathological runs with no whitespace:** handled by Section H's slice-based splitter, which always guarantees forward progress (a hard cut at exactly `max_chunk_size_chars` when no whitespace boundary exists) — tested up to 200,000 characters.
- **Huge block counts:** tested to 3,000 blocks in one document without error; chunk-ID uniqueness is verified to still hold.
- **Repeated/duplicate content:** identical paragraph text repeated many times still yields as many distinct, uniquely-identified chunks as expected — content-hash-derived identity does not collapse legitimately distinct chunks because `block_ids`/`split_index` (not raw text) participate in `chunk_id`.
- **Unusual Unicode** (combining scripts, emoji): preserved byte-for-byte through code-point-based sizing; no ASCII-only assumption anywhere in the splitting logic.
- **Invalid configuration:** rejected immediately and loudly (Section G/O), never silently clamped to a default.

**What Phase 4 does *not* protect against `[ENGINEERING RECOMMENDATION]`:** it inherits whatever Phase 3 already extracted; it performs no content sanitization, no prompt-injection defense (that is Phase 19's concern once generation exists), and no defense against a maliciously constructed `ExtractedDocument` beyond the type/shape checks above — a caller supplying a well-typed but semantically nonsensical document will get well-typed but semantically nonsensical chunks.

## Q. Explicit Non-Goals

`[OFFICIAL SOURCE]` / `[ENGINEERING RECOMMENDATION]` Phase 4 does not implement, and this repository contains no code for: BM25/TF-IDF/dense/hybrid retrieval, embeddings, FAISS or any vector database, RRF fusion, cross-encoder reranking, citation validation, LLM generation, multilingual translation, the jurisdiction firewall, the confidence engine, human escalation, a backend API, a frontend, agents, or a knowledge graph. Those belong to Phases 5–19 respectively (`docs\MASTER_REFERENCE_LOCK.md` Section G) and are verified absent by `tests\test_phase_04_regression.py`'s phase-boundary audit.

Phase 4 also does not: invent a heading/section Phase 3 did not detect; perform sliding-window overlap (Section A); reorder content by inferred semantic relevance; summarize, paraphrase, translate, or otherwise rewrite extracted text (Section I's table-flattening is the one narrow, fully-reversible exception); or persist chunks to any index/database (none exists yet).

## R. Source/Evidence Audit (self-check for this document)

`[ENGINEERING RECOMMENDATION]`

- Every design choice above carries a source label; chunking-strategy claims are hedged as engineering choices, never legal interpretation (Section A note, Section K).
- No legal interpretation is claimed anywhere — section/heading context is a navigational aid, not a legal fact, exactly matching Phase 3's own non-goal.
- No fabricated regulatory fact, government document, or metadata value appears in this document.
- The one normalization performed (table flattening, Section I) is disclosed with its rationale and reversibility, not silently applied.
- The one deliberately deferred technique (chunk overlap, Section A) is labeled `[DEFERRED]` with an explicit revisit condition, per `docs\DEVELOPMENT_RULES.md` Rule 9.
- Every heuristic/engineering choice is labeled `[ENGINEERING RECOMMENDATION]` or `[ASSUMPTION]`; none is labeled as if it were `[OFFICIAL SOURCE]` unless it is a direct quote or restatement of the Master Reference's own Phase 4 text.
