# PHASE 3 — DOCUMENT INGESTION

Status: CONTRACT + IMPLEMENTATION DOCUMENT (Phase 3 deliverable)
Authoritative source: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`
Governed by: `docs\MASTER_REFERENCE_LOCK.md`, `docs\DEVELOPMENT_RULES.md`, `docs\PHASE_02_AUTHORITY_MATRIX.md`, `docs\PHASE_02_CORPUS_ADMISSION_POLICY.md`
Machine-readable counterparts: `config\document_ingestion_contract.yaml`, `config\document_structure_schema.yaml`
Implementation: `src\ingestion\`

---

## A. Purpose

`[OFFICIAL SOURCE]` Phase 3's goal, per the Master Reference roadmap: *"Convert source documents into structured records without destroying legal hierarchy."* Its Build scope: *"PDF/HTML parsing, headings, sections, subsections, clauses, tables, page numbers, dates and provenance."* Its acceptance gate: *"A source section can be traced back to the exact document and location."*

`[ENGINEERING RECOMMENDATION]` Phase 3 builds the pipeline that converts a document already admitted under Phase 2's policy into a deterministic, provenance-preserving normalized structural representation, ready for Phase 4's legal-aware chunking. It does not itself retrieve, chunk, embed, or generate anything.

## B. Input Contract

`[ENGINEERING RECOMMENDATION]` The pipeline's entry point (`src\ingestion\pipeline.ingest_document`) accepts exactly two things:

1. **Raw file bytes** (or a path to a local file the caller has already placed on disk — never a URL; Phase 3 never downloads anything).
2. **A provenance record** conforming to `config\corpus_provenance_schema.yaml` — the same shape Phase 2 defined, supplied by the caller (in production, this would come from a Phase-2-governed admission process that does not yet exist as running code; in this repository, only synthetic fixtures exist).

No third input is accepted. The pipeline never infers `source_family_id` or `jurisdiction` from file content — those are provenance facts, not something to be guessed from text.

## C. Admission Preconditions

`[OFFICIAL SOURCE]` / `[ENGINEERING RECOMMENDATION]` Before any byte of the document is parsed, `src\ingestion\admission.check_admission_boundary` evaluates the supplied provenance record against `config\authority_matrix.yaml` and `config\corpus_lock.yaml`, in this fixed order (first failure wins):

| Order | Check | Failure state |
|---|---|---|
| 1 | `document_id` present and non-empty | `REJECTED_INPUT` (`MISSING_DOCUMENT_IDENTITY`) |
| 2 | `source_family_id` present | `REJECTED_INPUT` (`MISSING_SOURCE_FAMILY`) |
| 3 | `source_family_id` registered in `config\authority_matrix.yaml` | `REJECTED_INPUT` (`UNKNOWN_SOURCE_FAMILY`) |
| 4 | source family's `corpus_role == EVIDENCE_SOURCE` (not a service adapter, e.g. Bhashini) | `REJECTED_INPUT` (`SOURCE_FAMILY_NOT_EVIDENCE_SOURCE`) |
| 5 | `jurisdiction` present and a recognized value | `REJECTED_INPUT` (`UNKNOWN_JURISDICTION`) |
| 6 | `jurisdiction` matches the source family's fixed `jurisdiction_scope` | `REJECTED_INPUT` (`JURISDICTION_MISMATCH`) |
| 7 | `content_hash` (claimed) present and non-empty | `REJECTED_INPUT` (`MISSING_CONTENT_HASH`) |
| 8 | `admission_status` present and one of `{ADMIT, ADMIT_WITH_RESTRICTION}` | `REJECTED_INPUT` (`INVALID_ADMISSION_STATE`) |

Any document whose `admission_status` is `REJECT`, `HOLD_FOR_VALIDATION`, or `SUPERSEDED` fails check 8 and never reaches extraction — this is how Phase 3 honors "superseded documents when policy prohibits current ingestion" and "rejected documents" without inventing a new legal meaning for those states (they retain exactly the engineering meaning locked in `docs\PHASE_02_CORPUS_ADMISSION_POLICY.md`).

**On synthetic fixtures `[ENGINEERING RECOMMENDATION]`:** `config\corpus_provenance_schema.yaml`'s `synthetic` field and `PROV-SAFE-01`/`PROV-SAFE-05` were refined in this phase (schema_version 1.0.0 → 1.1.0) to resolve a genuine tension: the original PROV-SAFE-01 wording ("must be rejected by real ingestion code") would have made Phase 3's own pipeline untestable, since no real Phase-2-admitted document exists anywhere in this repository and every Phase 3 test fixture is therefore required to set `synthetic=true`. The admission boundary above does **not** reject `synthetic=true` records — it lets them through so the pipeline can be tested — but the pipeline (Section N) always propagates `synthetic` unchanged into its output, and never writes to any persistent corpus store (none exists yet). This is a disclosed refinement of a previous phase's safety wording, not a silent weakening: the underlying safety intent (a synthetic record must never be mistaken for real evidence) is fully preserved and is itself tested (Section R / `tests\test_phase_03_provenance.py`).

## D. Supported Document Types

`[ENGINEERING RECOMMENDATION]`, validated by actual implementation, not assumed:

| Type | Extension | Extractor | Dependency |
|---|---|---|---|
| `TEXT` | `.txt` | `src\ingestion\extractors.extract_text` | none (stdlib) |
| `HTML` | `.html`, `.htm` | `src\ingestion\extractors.extract_html` | none (stdlib `html.parser`) |
| `PDF` | `.pdf` | `src\ingestion\extractors.extract_pdf` | `pypdf` (see `requirements-dev.txt` for justification) |

Any other extension → `REJECTED_INPUT` (`UNSUPPORTED_DOCUMENT_TYPE`). Type is determined from the file extension only; Phase 3 does not perform content-sniffing/magic-byte detection (`[DEFERRED]` — not required for the synthetic/local fixtures this phase handles, and adding it would be premature without real heterogeneous input).

## E. Integrity Verification

`[ENGINEERING RECOMMENDATION]` `src\ingestion\hashing.compute_content_hash` computes SHA-256 over the *actual input bytes* (not the Master Reference's own hash mechanism, and not any prior claimed value). The pipeline compares this computed hash against the provenance record's claimed `content_hash`. A mismatch → `REJECTED_INPUT` (`CONTENT_HASH_MISMATCH`) — the document is never extracted on a false integrity premise. This hash is an integrity/identity mechanism only; it asserts nothing about legal authority (`docs\PHASE_02_CORPUS_ADMISSION_POLICY.md` Section 4).

## F. Document Identity Handling

`[ENGINEERING RECOMMENDATION]` Identity is never derived from a display name or file name alone. `document_id` and `content_hash` together (per Phase 2's provenance contract) distinguish: different documents (different `document_id`), different versions of the same document (same `document_id`, different `content_hash`/`version`), and byte-identical duplicates (identical `content_hash`) — see `tests\test_phase_03_ingestion.py` duplicate-detection tests. Missing `version` is preserved as missing (`version_known: false` passed through from the provenance record), never defaulted to "current."

## G. Text Extraction Behavior

`[ENGINEERING RECOMMENDATION]` Extraction is deterministic for identical input bytes. Decoding failures (TEXT: invalid UTF-8; PDF: parser exceptions) never fabricate replacement text — they produce an explicit warning and downgrade `extraction_status` (Section M). No extractor in this phase performs OCR; a PDF page whose extracted text is empty/whitespace-only is marked `OCR_REQUIRED` at the page level (a heuristic signal that the page is likely a scanned image), never silently treated as "no content."

## H. Page Preservation

`[ENGINEERING RECOMMENDATION]` `PDF` documents preserve real page boundaries (one `Page` per `pypdf` page, 1-indexed). `HTML` and `TEXT` documents have no native page concept; Phase 3 represents them as a single page (`page_number = 1`) rather than inventing arbitrary pagination. This is documented, not hidden.

## I. Structural Extraction

See `docs\PHASE_03_LEGAL_STRUCTURE_EXTRACTION.md` for the full structural-detection design (headings, tables, lists, etc.).

## J. Heading/Section Handling

`[ENGINEERING RECOMMENDATION]` HTML heading tags (`<h1>`–`<h6>`) are unambiguous markup and are detected with `DETECTED` status and a confident `heading_level`. TEXT/PDF heading detection is a documented heuristic (`docs\PHASE_03_LEGAL_STRUCTURE_EXTRACTION.md` Section 3) and is never claimed to be legally authoritative — a detected heading is a retrieval/navigation aid, not a legal fact.

## K. Table Handling

`[ENGINEERING RECOMMENDATION]` HTML `<table>`/`<tr>`/`<td>`/`<th>` markup is unambiguous and is extracted as a real row/cell structure (`DETECTED`). PDF and TEXT table extraction is **not attempted** in Phase 3 (`table_extraction_status: NOT_ATTEMPTED_FOR_PDF` / `NOT_APPLICABLE` for TEXT) rather than risk silently converting tabular content into misleading prose — see `docs\PHASE_03_LEGAL_STRUCTURE_EXTRACTION.md` Section 5 for the full rationale.

## L. Extraction Warnings

`[ENGINEERING RECOMMENDATION]` Every extractor accumulates a list of warning codes (e.g., `DECODE_ERROR_REPLACED_CHARACTERS`, `EMPTY_PAGE`, `PARSER_EXCEPTION`, `ENCRYPTED_PDF_UNSUPPORTED`, `PDF_TABLE_EXTRACTION_NOT_IMPLEMENTED`) at document, page, and block level as applicable. Warnings are never dropped silently; they travel into the serialized output (Section N).

## M. Failure/Quarantine Behavior

`[ENGINEERING RECOMMENDATION]` Terminal pipeline states, exactly as required (`config\document_ingestion_contract.yaml`):

- `READY_FOR_INGESTION` — passed the admission boundary (Section C); extraction is about to run. Not a final state of `ingest_document` — an internal checkpoint exposed for testability.
- `REJECTED_INPUT` — failed an admission-boundary or file-level precondition (Sections C, P). No extraction attempted.
- `EXTRACTION_SUCCESS` — every page extracted with non-trivial text and no warnings that reduce confidence.
- `EXTRACTION_PARTIAL` — some but not all pages/blocks extracted successfully, or extraction succeeded with warnings.
- `EXTRACTION_FAILED` — the extractor could not produce any usable structure (e.g., parser exception on every page, or a completely empty file after admission passed).
- `OCR_REQUIRED` — every page's extracted text is empty/whitespace-only (all-scanned-pages signal); no OCR is performed, per this phase's explicit boundary.
- `QUARANTINED` — reserved for a document that passed the admission boundary but whose file-level integrity/safety checks failed after that point (e.g., hash mismatch, oversized file, path-traversal attempt). Distinct from `REJECTED_INPUT` in that the provenance record itself was valid; it is the *file* that could not be trusted.

## N. Output Contract

`[ENGINEERING RECOMMENDATION]` `src\ingestion\serialize.to_json` produces deterministic JSON (`sort_keys=True`, fixed separators, UTF-8, no embedded ingestion timestamp inside the content payload — see Section O.2) matching `config\document_structure_schema.yaml`. No database, vector index, or retrieval index is created — this is a single-document, single-file JSON artifact intended for Phase 4 to consume.

## O. Provenance Preservation

`[OFFICIAL SOURCE — Phase 3 build scope]` Every `Block` carries an unbroken chain back to its source: `block → page_number → document_id → source_family_id → jurisdiction → content_hash`. This chain is asserted directly by `tests\test_phase_03_provenance.py`'s dedicated traceability test (Phase 3's "critical invariant").

**O.2 — Determinism vs. operational metadata `[ENGINEERING RECOMMENDATION]`:** `ingest_document` never reads the wall clock internally. If an ingestion timestamp is wanted, the caller supplies it explicitly as a separate parameter, which the serializer places in a distinct `ingestion_metadata` block outside `content` — so two calls with identical bytes/provenance produce byte-identical `content` JSON regardless of when they ran.

## P. Security Considerations

`[ENGINEERING RECOMMENDATION]` Practical Phase 3 safeguards only — **no claim of complete security**:

- **Path traversal:** when a file path (not raw bytes) is supplied, it is resolved and must remain within an explicit caller-supplied root directory; a path escaping that root (e.g., via `..`) is rejected before any read occurs (`QUARANTINED`, `PATH_TRAVERSAL_ATTEMPT`).
- **Unsupported extensions:** rejected before parsing (Section D).
- **Empty files:** rejected (`QUARANTINED`, `EMPTY_FILE`) before extraction.
- **Oversized files:** a fixed, documented size ceiling (`MAX_INPUT_BYTES = 50_000_000`, `[ENGINEERING RECOMMENDATION]` — an arbitrary but explicit and testable bound, not derived from the Master Reference) is enforced; larger inputs are `QUARANTINED` (`OVERSIZED_INPUT`) rather than processed.
- **Malformed files / parser exceptions:** every extractor call is wrapped; a parser exception becomes `EXTRACTION_FAILED` with a `PARSER_EXCEPTION` warning, never an uncaught crash.
- **Binary/non-text content presented as TEXT:** decode failures are caught and downgrade the result (Section G); they never crash the pipeline.
- **Maliciously crafted structures:** Phase 3 relies on `pypdf`'s and the standard library's own parsing robustness; it adds no additional PDF-bomb/zip-bomb defenses beyond the size ceiling above. This is an explicit, documented limitation (Section Q), not a claim of hardened parsing.

## Q. Limitations

`[ENGINEERING RECOMMENDATION]`

- No OCR — scanned/image-only PDF pages are reported as `OCR_REQUIRED`, never fabricated.
- No layout/font-based heading detection for PDF (only the same conservative text heuristic used for TEXT) — `pypdf`'s basic API does not reliably expose font/position metadata, and a heavier dependency (e.g. `pdfplumber`) is not justified for Phase 3.
- No table extraction for PDF/TEXT — HTML only (Section K).
- No footnote, header/footer, or appendix/schedule detection — `[DEFERRED]`; no reliable stdlib/`pypdf` signal exists without substantially more engineering than Phase 3 warrants.
- No content-type sniffing beyond file extension (Section D).
- No hardened defense against adversarially crafted PDFs beyond a size ceiling and exception handling (Section P).
- Heading/list/table detection heuristics are unvalidated against any real regulatory corpus (none exists yet) — they are tested only for determinism and for the specific documented patterns they claim to recognize, not for real-world accuracy.

## R. Source/Evidence Audit (self-check for this document)

`[ENGINEERING RECOMMENDATION]`

- Every design choice above carries a source label; extraction-capability claims are hedged as implementation-dependent where relevant (Section G, Q).
- No legal interpretation is claimed anywhere — headings/sections are retrieval aids, not legal facts (Section J).
- No fabricated regulatory fact, government document, or metadata value appears in this document.
- The `synthetic` field refinement (Section C) is disclosed with its rationale, not silently applied.
- Every heuristic is explicitly labeled `[ENGINEERING RECOMMENDATION]`; none is labeled as if it were `[OFFICIAL SOURCE]`.
