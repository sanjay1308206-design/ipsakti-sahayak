# PHASE 2 — CORPUS ADMISSION POLICY

Status: CONTRACT DOCUMENT (Phase 2 deliverable)
Authoritative source: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`
Companion: `docs\PHASE_02_AUTHORITY_MATRIX.md`
Machine-readable counterparts: `config\corpus_provenance_schema.yaml`, `config\corpus_lock.yaml`

**Scope note `[ENGINEERING RECOMMENDATION]`:** This is a policy and a deterministic checklist for how a document *would* be evaluated once ingestion exists (Phase 3+). It does not ingest anything. No real document is evaluated by this phase. The reference evaluator described in Section 3 operates only on synthetic, clearly-marked test fixtures (`tests\_admission_policy_reference_impl.py`), never on real files.

---

## 1. Admission States

`[ENGINEERING RECOMMENDATION]` — engineering corpus-governance states, not legal categories, per this phase's explicit instruction. Exactly five states exist:

| State | Meaning |
|---|---|
| `ADMIT` | All provenance, identity, jurisdiction, validation, and version conditions are satisfied without restriction. |
| `ADMIT_WITH_RESTRICTION` | Admitted, but a known limitation must travel with the document (e.g., version/effective-date unknown, or supersession status unknown) — never presented as unrestricted current evidence. |
| `HOLD_FOR_VALIDATION` | A required condition is missing or unconfirmed; not yet admissible; not rejected either. |
| `REJECT` | A hard integrity failure (unknown source family, unknown/mismatched jurisdiction) — never admissible as-is. |
| `SUPERSEDED` | Known to have been replaced by a newer version; retained for audit/history but never served as current evidence. |

No other admission state may be produced. No admission state implies a legal conclusion — `ADMIT` means "meets this project's provenance/governance bar," never "is legally correct" or "is currently in force" in a legal sense.

## 2. The Twelve-Point Admission Checklist

`[ENGINEERING RECOMMENDATION]`, operationalizing the Master Reference's Phase 2 acceptance gate ("Every target question category has at least one authoritative evidence path") into a per-document contract:

1. **Source identity** — `source_family_id` must be a member of `config\authority_matrix.yaml`'s registered families. Unregistered family → `REJECT`.
2. **Authority classification** — the document inherits its family's `authority_tier`/`authority_role`; no per-document override exists in Phase 2.
3. **Jurisdiction** — `jurisdiction` must equal the source family's fixed jurisdiction (`docs\PHASE_02_AUTHORITY_MATRIX.md` Section 7). Mismatch → `REJECT`.
4. **Document identity** — `document_id` must be present and non-empty. Missing → `HOLD_FOR_VALIDATION`.
5. **Version / effective date if available** — `version_known` and `effective_date_known` are recorded explicitly as booleans. If both are `false`, the document may reach at best `ADMIT_WITH_RESTRICTION` — **never** silently treated as current (see Section 4, negative case).
6. **Acquisition metadata** — `retrieved_at` must be recorded (not evaluated further in Phase 2, since no acquisition occurs).
7. **Integrity / hash** — `content_hash` must be present and non-empty. Missing → `HOLD_FOR_VALIDATION`.
8. **Provenance record** — the full shape defined in `config\corpus_provenance_schema.yaml` must be populated; unknown fields are represented explicitly (e.g., `null`/an explicit "unknown" marker), never omitted silently.
9. **Validation status** — `validation_status` must equal `VALIDATED` (independently confirmed against the live/official source, per `docs\PHASE_02_AUTHORITY_MATRIX.md` Section 4) to reach `ADMIT`. Anything else → `HOLD_FOR_VALIDATION`.
10. **Supersession/replacement status** — `supersession_status` of `SUPERSEDED` → terminal `SUPERSEDED` state, never re-admitted as current. `UNKNOWN` → at best `ADMIT_WITH_RESTRICTION`.
11. **Conflict status** — `conflict_status` of `CONFLICTING`, or a non-empty `known_conflicting_with` list without a recorded `conflict_status`, → `HOLD_FOR_VALIDATION` and routes to `docs\PHASE_02_SOURCE_CONFLICT_POLICY.md`. The system never silently picks a winner.
12. **Admission decision** — the deterministic combination of 1–11, evaluated in a fixed priority order (Section 3), yielding exactly one of the five states in Section 1.

## 3. Deterministic Evaluation Order

`[ENGINEERING RECOMMENDATION]` Ordered, first-match-wins, mirroring the style of `docs\PHASE_01_REGULATORY_DECISION_TREE.md`. Implemented for test purposes only in `tests\_admission_policy_reference_impl.py`:

| Order | Rule | Fires when | Result |
|---|---|---|---|
| A1 | `UNKNOWN_SOURCE_FAMILY` | `source_family_id` not registered | `REJECT` |
| A2 | `UNKNOWN_JURISDICTION` | `jurisdiction` not a recognized value | `REJECT` |
| A3 | `JURISDICTION_MISMATCH` | `jurisdiction` ≠ source family's fixed jurisdiction | `REJECT` |
| A4 | `MISSING_DOCUMENT_IDENTITY` | `document_id` empty/missing | `HOLD_FOR_VALIDATION` |
| A5 | `MISSING_CONTENT_HASH` | `content_hash` empty/missing | `HOLD_FOR_VALIDATION` |
| A6 | `VALIDATION_NOT_CONFIRMED` | `validation_status` ≠ `VALIDATED` | `HOLD_FOR_VALIDATION` |
| A7 | `DOCUMENT_SUPERSEDED` | `supersession_status == SUPERSEDED` | `SUPERSEDED` |
| A8 | `UNRESOLVED_CONFLICT` | `conflict_status == CONFLICTING` | `HOLD_FOR_VALIDATION` |
| A9 | `MISSING_CONFLICT_STATUS_DESPITE_KNOWN_CONFLICT` | `known_conflicting_with` non-empty AND `conflict_status` not set | `HOLD_FOR_VALIDATION` |
| A10 | `VERSION_UNKNOWN_RESTRICTED` | `version_known == false` AND `effective_date_known == false` | `ADMIT_WITH_RESTRICTION` |
| A11 | `SUPERSESSION_STATUS_UNKNOWN` | `supersession_status == UNKNOWN` | `ADMIT_WITH_RESTRICTION` |
| A12 | `DEFAULT_ADMIT` | none of the above fired | `ADMIT` |

This evaluator never reads a real file, never downloads anything, and never performs OCR/PDF parsing — it only evaluates an already-supplied, fully-specified provenance record (real or, in Phase 2's tests, synthetic).

## 4. Document Identity & Versioning

`[ENGINEERING RECOMMENDATION]` — an engineering identity strategy, not a legal versioning rule:

- **`document_id`** is the logical identity of a document across versions (e.g., a stable handle for "the Ayurveda Aahara Regulations"), assigned by the (future) ingestion process, never invented in Phase 2.
- **`version`** distinguishes different points in time of the same logical document. `(document_id, version)` must be unique.
- **`content_hash`** (SHA-256 of the normalized source bytes, `[ENGINEERING RECOMMENDATION]`) distinguishes byte-identical duplicates from genuinely different content. Two records with the same `content_hash` but different `document_id`/`version` are flagged `DUPLICATE_CONTENT_SUSPECTED` for manual review — never silently auto-merged or auto-deduplicated.
- **Amended/revised material** is a new `version` of the same `document_id`, with `supersession_status` on the older version updated to `SUPERSEDED` — this update itself requires validation (Section 2, item 10); Phase 2 does not implement the update mechanism, only the field contract.
- **Missing version information is never silently treated as current.** This is enforced structurally: `version_known: false` forces, at best, `ADMIT_WITH_RESTRICTION` (rule A10) — there is no code path that defaults an unknown version to "current."

## 5. What Phase 2 Explicitly Does Not Do

`[OFFICIAL SOURCE]` / `[ENGINEERING RECOMMENDATION]` — restating the phase boundary for this document specifically: no document is downloaded, scraped, crawled, OCR'd, parsed, normalized, chunked, indexed, embedded, or otherwise acquired. The checklist and evaluator above exist solely so that Phase 3+ has an unambiguous, pre-agreed contract to implement against, and so this phase's own test suite can prove the *policy* behaves safely under adversarial synthetic input before any real ingestion code is written.
