# PHASE 3 — LEGAL STRUCTURE EXTRACTION

Status: CONTRACT + IMPLEMENTATION DOCUMENT (Phase 3 deliverable)
Authoritative source: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`
Companion: `docs\PHASE_03_DOCUMENT_INGESTION.md`
Machine-readable counterpart: `config\document_structure_schema.yaml`
Implementation: `src\ingestion\extractors.py`

**Terminology note `[ENGINEERING RECOMMENDATION]`:** "Legal structure" here means *document* structure useful for later retrieval and evidence preservation (headings, sections, paragraphs, tables). It does **not** mean legal interpretation. Detecting that a line of text looks like a heading is a typographic/structural observation, never a claim about that heading's legal force or authority.

---

## 1. Structural Elements In Scope

`[OFFICIAL SOURCE]` Master Reference Phase 3 Build text names: *"headings, sections, subsections, clauses, tables, page numbers... and provenance."* Phase 3 detects, per document type, exactly what its input signal actually supports — never more:

| Element | TEXT | HTML | PDF |
|---|---|---|---|
| Document title | `NOT_DETECTED` (no reliable signal) | `DETECTED` via `<title>` when present, else `NOT_DETECTED` | `NOT_DETECTED` |
| Headings | Heuristic (`ENGINEERING RECOMMENDATION`), see Section 3 | `DETECTED` via `<h1>`–`<h6>` | Same heuristic as TEXT, applied per extracted page text |
| Sections/subsections | Derived from heading levels 1/2 where detected | Derived from `<h1>`/`<h2>` nesting | Derived from heuristic heading levels |
| Paragraphs | Blank-line-delimited blocks | `<p>` tags | Blank-line-delimited blocks per page |
| Lists | `NOT_DETECTED` (heuristic list detection deferred, see Section 6) | `DETECTED` via `<ul>`/`<ol>`/`<li>` | `NOT_DETECTED` |
| Tables | `NOT_APPLICABLE` | `DETECTED` via `<table>`/`<tr>`/`<td>`/`<th>` | `NOT_ATTEMPTED_FOR_PDF` (Section 5) |
| Page boundaries | Single page (no native concept) | Single page | Real, from `pypdf` |
| Footnotes | `NOT_DETECTED` (`[DEFERRED]`) | `NOT_DETECTED` (`[DEFERRED]`) | `NOT_DETECTED` (`[DEFERRED]`) |
| Headers/footers | `NOT_DETECTED` (`[DEFERRED]`) | `NOT_DETECTED` (`[DEFERRED]`) | `NOT_DETECTED` (`[DEFERRED]`) |
| Appendices/schedules | `NOT_DETECTED` (`[DEFERRED]`) | `NOT_DETECTED` (`[DEFERRED]`) | `NOT_DETECTED` (`[DEFERRED]`) |

Every cell above is a real implementation behavior, tested in `tests\test_phase_03_structure.py` — not an aspiration.

## 2. Detection States

`[ENGINEERING RECOMMENDATION]` Exactly three states for any structural feature, per this phase's instructions:

- `DETECTED` — the feature was found by an unambiguous signal (real markup) or a documented heuristic matched.
- `NOT_DETECTED` — the feature was actively checked for and not found (or is not implemented for this document type).
- `UNKNOWN` — reserved for cases where detection was attempted but confidence is insufficient to assert either `DETECTED` or `NOT_DETECTED` (e.g., a heading-like line whose heading *level* cannot be determined even though the line itself is flagged as a probable heading).

## 3. Heading Heuristic (TEXT / PDF-extracted text)

`[ENGINEERING RECOMMENDATION]` — a documented heuristic, never described as legal interpretation. A non-empty line is classified `DETECTED` as a heading candidate when **both**:

1. It is short: at most 120 characters, and does not end in typical sentence-ending punctuation (`.`, `,`, `;`, `:`).
2. It matches **either**:
   - a numbered-heading pattern: `^\d+(\.\d+)*[.)]?\s+\S` (e.g., `"1. Definitions"`, `"2.1 Scope"`) — `heading_level` is set to the numbering depth (`"1."` → 1, `"2.1"` → 2), capped at 6; **or**
   - an all-uppercase-letters short line (e.g., `"SCOPE"`) — `heading_level` is `UNKNOWN` (state, not a number), since caps alone give no depth signal.

Anything else is a `PARAGRAPH` block, not a heading. This heuristic is intentionally conservative: it is tested only for **determinism** (same input → same classification) and for the **specific patterns it claims to recognize** — it is never validated against real regulatory text, because none exists in this repository (`docs\PHASE_03_DOCUMENT_INGESTION.md` Section Q).

## 4. Heading Detection (HTML)

`[OFFICIAL SOURCE — HTML is explicit markup, not a heuristic]` `<h1>`–`<h6>` tags map directly and confidently to `heading_level` 1–6, `DETECTED`. `<title>` maps to the document title, `DETECTED` when present. No ambiguity exists here because the signal is unambiguous markup, not inferred text shape.

## 5. Table Handling

`[ENGINEERING RECOMMENDATION]` Per the explicit instruction *"Where tables are extracted, preserve enough structure to avoid silently converting a table into misleading prose... If reliable table extraction is not available: preserve a controlled warning/status; do not invent table content"*:

- **HTML:** `<table>` markup is unambiguous. Each `<tr>` becomes a row; each `<td>`/`<th>` becomes a cell (its inner text, whitespace-normalized). The result is a `Table` block with `rows: list[list[str]]`, `detection_status: DETECTED`. **Known limitation `[ENGINEERING RECOMMENDATION]`:** `colspan`/`rowspan` and nested tables are not reconciled into a normalized grid — cells are captured in document order with a `TABLE_STRUCTURE_SIMPLIFIED` warning whenever a `colspan`/`rowspan` attribute is observed, so a consumer knows the row/column alignment may not be a perfect grid.
- **PDF:** Table extraction is **not attempted**. `pypdf`'s plain-text extraction does not preserve column alignment reliably enough to reconstruct a table without a real risk of silently mangling it into misleading prose (exactly the failure mode this phase's instructions warn against). Every PDF document's structural summary carries `table_extraction_status: NOT_ATTEMPTED_FOR_PDF` — a fixed, explicit, always-present status, not a per-instance guess about whether a given page "looks like" it has a table.
- **TEXT:** Plain text has no table markup at all; `table_extraction_status: NOT_APPLICABLE`.

## 6. Lists

`[ENGINEERING RECOMMENDATION]` HTML `<ul>`/`<ol>`/`<li>` are unambiguous markup and are detected (`LIST` block containing ordered `LIST_ITEM` children). TEXT/PDF list detection (e.g., recognizing `"- item"` or `"(a) item"` bullet patterns) is **not implemented** in Phase 3 — `[DEFERRED]`. Rationale: a bullet/numbering heuristic for plain text is easy to write but easy to get subtly wrong in ways that silently misrepresent document structure (e.g., confusing a numbered heading with a numbered list item); rather than ship an unvalidated heuristic for a structural feature with no real corpus to test it against, Phase 3 reports `NOT_DETECTED` and leaves list detection to a later, better-informed phase.

## 7. Page Numbers

`[OFFICIAL SOURCE]` Explicitly required by the Master Reference's Phase 3 Build scope ("page numbers"). PDF pages carry their real 1-indexed page number from `pypdf`. TEXT/HTML documents, having no native page concept, are assigned `page_number = 1` uniformly (Section H of `docs\PHASE_03_DOCUMENT_INGESTION.md`) rather than an invented page count.

## 8. Ordering

`[ENGINEERING RECOMMENDATION]` Every `Block` carries a monotonically increasing `sequence` integer, assigned in document reading order (top-to-bottom for TEXT/PDF-page text; DOM traversal order for HTML). This ordering is deterministic and tested directly (`tests\test_phase_03_structure.py`).

## 9. Non-Goals

`[OFFICIAL SOURCE]` / `[ENGINEERING RECOMMENDATION]`

- No structural detector in this phase performs legal interpretation, classification, or citation generation.
- A detected heading is never asserted to be "the" legally authoritative section heading of a regulation — it is a structural/navigational artifact for Phase 4's chunker to consume.
- No confidence score is invented for heuristic detections; only the three-state `DETECTED`/`NOT_DETECTED`/`UNKNOWN` vocabulary is used.
