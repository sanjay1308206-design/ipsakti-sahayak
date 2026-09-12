# PHASE 9 — CITATION VALIDATION

Status: CONTRACT + IMPLEMENTATION DOCUMENT (Phase 9 deliverable)
Authoritative source: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`
Governed by: `docs\MASTER_REFERENCE_LOCK.md`, `docs\DEVELOPMENT_RULES.md`, `docs\PHASE_08_EVIDENCE_OBJECT_AND_CITATION_ARCHITECTURE.md`
Machine-readable counterparts: `config\citation_validation_contract.yaml`, `config\citation_validation_schema.yaml`
Implementation: `src\citation\models.py`, `validator.py`, `metrics.py`, `serialize.py`

**Citation validation is the second half of the trust boundary Phase 8 opened.** Phase 8 said *"this is a real Evidence object with real provenance."* Phase 9 says *"this citation reference, wherever it came from, actually points to that real Evidence object — or it does not, and here is exactly why."* Everything in this phase is deterministic; nothing here requires, calls, or depends on an LLM.

---

## A. Purpose

`[OFFICIAL SOURCE]` Master Reference Final Architecture Decision Lock names *"Citation Validation"* as the pipeline stage immediately after generation and claim/evidence binding, before confidence/safety (`docs\MASTER_REFERENCE_LOCK.md` Section E: *"...→ Generation → Claim/Evidence Binding → Citation Validation → Confidence + Safety..."*). `docs\PHASE_TRACKER.md`'s own Phase 9 entry states the goal plainly: *"Prevent invented or mismatched legal citations."* Phase 9 implements exactly the citation-integrity half of that: given a citation reference (an `evidence_id`, however it arrived) and a Phase 8 `EvidencePack`, deterministically answer **VALID**, **INVALID**, or **UNRESOLVED** — never whether the underlying legal claim is correct.

## B. Scope

In scope: the `CitationReference` model (the untrusted-input shape), the `CitationValidationResult` model (the trusted-output shape), a closed status vocabulary, a closed reason-code vocabulary, `EvidencePack` validation before any resolution is attempted, exact-match-only evidence-ID resolution reusing Phase 8's own lookup, per-citation Evidence integrity/provenance verification reusing Phase 8's own tamper-detection functions, deterministic duplicate-occurrence tracking, citation-coverage metrics, deterministic serialization, and a synthetic validation benchmark.

Out of scope (no code for any of these exists anywhere in `src\citation\`): LLM generation, Gemini, Qwen, prompt engineering for answering, answer generation, legal reasoning or legal interpretation, semantic claim/evidence entailment, formulation classification, the jurisdiction firewall, the confidence/abstention engine, human escalation, a frontend, FastAPI, authentication/authorization, agents, a knowledge graph, production deployment, monitoring, automatic source downloading, or corpus crawling.

## C. Source Classification

Every non-trivial claim below carries one of the seven approved labels (`docs\DEVELOPMENT_RULES.md` Rule 1). No regulation, legal fact, source document, source URL, document identifier, page number, section number, legal conclusion, citation, dataset, API, or benchmark result is invented anywhere in this document or its implementation.

## D. Relationship to Phase 8

`[ENGINEERING RECOMMENDATION]` Phase 9 **consumes** Phase 8's `Evidence`/`EvidencePack`/`CitationTarget` exactly as produced — `src\evidence\*.py` is not modified by this phase (`tests\test_phase_09_regression.py` asserts this by file-content check). Phase 9 deliberately **reuses, rather than duplicates**, three specific pieces of Phase 8 logic:

1. Exact-match evidence-ID resolution: `evidence.builder.resolve_citation_target` (wrapped in a `evidence.models.CitationTarget`), used verbatim.
2. Evidence text/identity integrity: `evidence.validation.verify_evidence_text_integrity` / `verify_evidence_identity`, used verbatim.
3. EvidencePack identity verification: `evidence.validation.verify_pack_identity`, used verbatim.

Phase 8 built the Evidence objects and the resolution primitive; Phase 9 builds the layer that decides, for an arbitrary (possibly untrusted, possibly malformed) citation reference, whether that primitive actually succeeds — and if not, exactly why.

## E. Relationship to Phase 10

`[ENGINEERING RECOMMENDATION]` Phase 10 owns grounded generation: producing an actual answer from validated evidence, with wording, structure, uncertainty disclosure, and disclaimers. Phase 9 produces **only** a citation-integrity verdict — no answer, explanation, legal recommendation, or natural-language response is generated anywhere in `src\citation\` (verified by the phase-boundary audit, `tests\test_phase_09_regression.py`). A future Phase 10 will presumably call `citation.validator.validate_citations` on the citations a generated answer claims to use, but no such call site exists in this repository yet, and building one is explicitly Phase 10's job, not this phase's.

## F. CitationReference

`[ENGINEERING RECOMMENDATION]` (`src\citation\models.CitationReference`) Fields: `evidence_id` (`Optional[str]`), `schema_version` (`str`, default `"1.0.0"`), `citation_ref_id` (`Optional[str]`, inert caller-assigned display identifier), `display_order` (`Optional[int]`, inert display/ordering metadata). **Deliberately unvalidated at construction** — this is the single largest deliberate deviation from Phase 8's own conventions, and it is intentional: `CitationReference` represents *"a citation reference as it arrives before validation"* (conceptually, from an LLM-generated claim per the Trust Boundary in Section below) — constructing one with `evidence_id=None`, an empty string, or even a non-string value must succeed, because *classifying* that value (`MALFORMED_REFERENCE`, `EVIDENCE_ID_MISSING`, etc.) is `validator.py`'s job, never the container's. It never duplicates the full `Evidence` object — no `evidence_text`, `document_id`, `page_numbers`, or any other provenance field lives on this model; it only ever *points to* an `evidence_id`.

## G. ValidationResult

`[ENGINEERING RECOMMENDATION]` (`src\citation\models.CitationValidationResult`) Fields: `citation_reference` (the original reference that was validated), `status` (one of the closed vocabulary, Section H), `reason_code` (one of the closed vocabulary or `None`, Section I), `requested_evidence_id` (the evidence_id that was actually requested, or `None`, kept even when malformed for explainability), `resolved_evidence` (an optional `ResolvedEvidenceSummary` — `evidence_id`, `chunk_id`, `document_id`, `source_family_id`, `jurisdiction`, `synthetic` — **populated if and only if `status == "VALID"`**, i.e. evidence identity information is only ever exposed *after* it has been verified, never speculatively), `occurrence_index` (0-based position in the batch that was validated, Section O/CITATION ORDERING), `is_duplicate_occurrence` (bool, Section O), `detail` (a human-readable, never-fabricated explanation string), `validator_schema_version`. Unlike `CitationReference`, this model **is** fully validated at construction — every invariant (`status` closed, `reason_code`/`resolved_evidence` presence rules) is enforced every time a `CitationValidationResult` is built, exactly like Phase 8's `Evidence`. No field on this dataclass could hold a generated legal conclusion, answer, or claim — there simply is no such field.

## H. Status Vocabulary

`[ENGINEERING RECOMMENDATION]` Exactly three values, a closed `frozenset` (`citation.models.CITATION_STATUSES`): **`VALID`** (the reference resolves, by exact match, to real Evidence in the given `EvidencePack`, and that Evidence passes integrity/provenance verification), **`INVALID`** (the reference itself is malformed, the `EvidencePack` failed its own validation, or the resolved Evidence failed integrity/provenance verification), **`UNRESOLVED`** (the reference is structurally well-formed but its `evidence_id` does not exist in the given `EvidencePack`). No fourth status is ever introduced ad hoc elsewhere in the codebase — this is the entire vocabulary.

## I. Reason Codes

`[ENGINEERING RECOMMENDATION]` A closed, documented `frozenset` (`citation.models.CITATION_REASON_CODES`) of exactly seven values, each reachable and independently meaningful (verified directly by tests, Section AA):

| Reason code | Status | Meaning |
|---|---|---|
| `EVIDENCE_ID_MISSING` | INVALID | The reference has no `evidence_id` at all (`None`). |
| `MALFORMED_REFERENCE` | INVALID | `evidence_id` is present but not a well-formed non-empty string (empty, whitespace-only, or a non-string value). |
| `SCHEMA_MISMATCH` | INVALID | The reference's `schema_version` is not one this validator supports. |
| `EVIDENCE_NOT_FOUND` | UNRESOLVED | A well-formed `evidence_id` does not exist in the given `EvidencePack`. |
| `INVALID_PACK` | INVALID | The `EvidencePack` itself failed pack-identity validation (Section J) — every citation checked against it in that call is reported this way. |
| `EVIDENCE_PROVENANCE_FAILURE` | INVALID | The resolved Evidence's own provenance fields are structurally malformed (empty/wrong-shaped `document_id`/`source_family_id`/`jurisdiction`/`content_hash`/`page_numbers`/`block_ids`). |
| `EVIDENCE_INTEGRITY_FAILURE` | INVALID | The resolved Evidence is well-shaped but fails Phase 8's cryptographic text/identity re-verification (a forged `evidence_id` or a tampered `evidence_text`/`evidence_text_hash`). |

Two codes deliberately do **not** exist, per the explicit instruction to introduce only reason codes that are actually needed:

- **`duplicate_reference`** is absent — a duplicate citation is never, by itself, a validation failure (Section O). It is tracked as `is_duplicate_occurrence` on the result, not as a reason for `INVALID`/`UNRESOLVED`.
- **`synthetic_evidence`** is absent — `synthetic=True` evidence is never, by itself, a validation failure (Section S). It is preserved as `resolved_evidence.synthetic` on a `VALID` result.
- **`unsupported_reference_type`** is absent — Phase 8/9 currently define exactly one evidence type (`"CHUNK"`) and exactly one reference mechanism (`evidence_id`), so there is no second "type" that could be unsupported yet.

## J. EvidencePack Validation

`[ENGINEERING RECOMMENDATION]` (`src\citation\validator.check_evidence_pack_validity`) Runs **before** any citation in a batch is resolved against a pack, exactly once per `validate_citations()` call (never re-derived per-reference, so every reference in one batch sees an identical verdict). Checks, in order: (1) the pack's `schema_version` is one this validator supports; (2) no duplicate `evidence_id`/`chunk_id` values exist (structurally impossible through normal `EvidencePack` construction — `EvidencePack.__post_init__` already guarantees it — but re-checked here as defense-in-depth against an object that reached this function via a path that bypassed its own constructor); (3) `evidence.validation.verify_pack_identity` — Phase 8's own `pack_id` recomputation-and-compare, which also requires `construction_metadata["config_signature"]` to be present. If any of these fail, **every** citation validated against that pack in the same call is reported `INVALID`/`INVALID_PACK` — the pack is never partially trusted.

**Deliberately not included here:** a full per-evidence-item text/identity integrity walk (Phase 8's `verify_pack_integrity`, which Phase 9's earlier draft used and then replaced — see Section X for why). Using the heavier check here would make `EVIDENCE_INTEGRITY_FAILURE` permanently unreachable dead code, since it would always be shadowed by `INVALID_PACK` first for any pack containing so much as one tampered evidence item. Per-evidence integrity is instead checked in Section N, scoped to the *specific* Evidence object a citation resolves to — so one tampered item in an otherwise-intact ten-item pack invalidates only citations pointing at that item, not the other nine (`tests\test_phase_09_integrity.py::test_one_tampered_item_does_not_invalidate_citations_to_other_items`).

## K. Evidence ID Resolution

`[ENGINEERING RECOMMENDATION]` (`src\citation\validator._validate_single`) After the pack passes Section J and the reference passes its own structural checks (Section F/I), resolution is a single call: wrap the requested `evidence_id` in a Phase 8 `evidence.models.CitationTarget` (whose own `__post_init__` rejects a non-string/empty value — caught here and reported `MALFORMED_REFERENCE`) and call `evidence.builder.resolve_citation_target(target, pack)`. A `EvidenceNotFoundError` becomes `UNRESOLVED`/`EVIDENCE_NOT_FOUND`; success returns the real `Evidence` object for further verification (Sections M/N).

## L. Exact Matching

`[OFFICIAL SOURCE]` `resolve_citation_target` (Phase 8) performs exactly one comparison: `evidence.evidence_id == citation_target.evidence_id` — Python string equality, nothing else. Phase 9 never re-implements this lookup with different semantics; it is used verbatim. Consequences, all directly tested (`tests\test_phase_09_validator.py`):

- A truncated ID does not resolve.
- An ID with one extra trailing character does not resolve.
- An uppercased/case-folded ID does not resolve (SHA-256 hex digests are lowercase; Phase 8's identity contract does not define case-insensitive IDs).
- An ID wrapped in leading/trailing whitespace does not resolve (no trimming is ever applied).
- No partial-ID, source-name, page-number, or text-similarity fallback exists anywhere in this module.

## M. Provenance Validation

`[ENGINEERING RECOMMENDATION]` (`src\citation\validator._check_evidence_provenance_shape`) A defensive structural re-check of the *specific* resolved Evidence object's provenance fields — non-empty `document_id`/`source_family_id`/`jurisdiction`, a well-formed 64-character `content_hash`, non-empty `page_numbers`/`block_ids`. In practice unreachable for any `Evidence` built through its own real constructor (`Evidence.__post_init__` already enforces every one of these invariants) — it exists for the same reason Phase 8's own `verify_pack_integrity` re-checks things after deserialization: not every `Evidence` object handed to this function is guaranteed to have come through that constructor (e.g. a hand-corrupted in-memory object; `tests\test_phase_09_provenance.py` constructs exactly this scenario via `object.__new__` to prove the check fires).

**Critically, this check runs *before* Section N's cryptographic integrity check**, not after. Every field this check inspects (`document_id`, `source_family_id`, `jurisdiction`, `content_hash`, `page_numbers`, `block_ids`) is *also* a direct input to Phase 8's `evidence_id` hash (`evidence.identity.compute_evidence_id`) — so a structural violation in any of them would *also* make the identity re-check in Section N fail. Checking shape first is what keeps `EVIDENCE_PROVENANCE_FAILURE` independently reachable rather than permanently shadowed by `EVIDENCE_INTEGRITY_FAILURE`; the two reason codes describe genuinely different failures (structurally malformed vs. well-shaped-but-forged) precisely because of this ordering.

## N. Evidence Integrity

`[ENGINEERING RECOMMENDATION]` (`src\citation\validator._validate_single`, step 6) `evidence.validation.verify_evidence_text_integrity` and `verify_evidence_identity` are called, verbatim, on the specific resolved Evidence object. A mismatch (tampered `evidence_text` without a recomputed `evidence_text_hash`, or a forged `evidence_id` inconsistent with the Evidence's own other fields) is reported `INVALID`/`EVIDENCE_INTEGRITY_FAILURE` — the citation is **never** marked `VALID` when this fails, with no exception.

## O. Duplicate Citation Behavior

`[ENGINEERING RECOMMENDATION]` `validate_citations()` tracks, across one call, the first `occurrence_index` at which each distinct, well-formed `evidence_id` string appears. Every later occurrence of that same string sets `is_duplicate_occurrence=True` on its own independent result — **duplicates are never merged into a single result, and duplication is never, by itself, a reason for `INVALID`/`UNRESOLVED`** (there is no `duplicate_reference` reason code, Section I). Two malformed references (e.g. both `evidence_id=None`) are **not** considered duplicates of each other — `None`/empty values carry no identity to be duplicated. Citing the same fabricated (non-existent) ID twice still marks the second occurrence as a duplicate — duplicate tracking is about the *requested string*, independent of whether it resolves.

**Terminology, precisely:** *citation occurrence* = one `CitationReference` in the input list (`total_references` in the coverage metrics, Section P). *Unique cited evidence* = the count of distinct real `evidence_id` values actually resolved across all `VALID` results (`unique_valid_evidence_id_count`) — these are deliberately different numbers, and the coverage metrics report both.

## P. Citation Coverage Metrics

`[ENGINEERING RECOMMENDATION]` (`src\citation\metrics.compute_citation_coverage`) `CitationCoverageMetrics` fields: `total_references`, `valid_count`, `invalid_count`, `unresolved_count` (these three always sum to `total_references`), `unique_valid_evidence_id_count` (distinct `evidence_id` values among `VALID` results **only** — an `INVALID`/`UNRESOLVED` reference cites no real evidence, so it never contributes here, Section O), `duplicate_occurrence_count`, `citation_integrity_validation_rate` (`valid_count / total_references`, `0.0` when `total_references == 0`, always within `[0.0, 1.0]`). **This is a citation-integrity measurement only.** It is never called, documented, or usable as "legal correctness," "answer factual accuracy," or "how many claims are legally supported" — see the explicit boundary in Section Q.

## Q. Semantic Claim-Support Boundary

`[OFFICIAL SOURCE]` This is the single most important boundary in this phase. Given a claim *"X is legally permitted"* and evidence *"Y is described,"* Phase 9 **never** decides whether Y proves X. It only ever decides: *"does this citation reference resolve to real, valid Evidence?"* Semantic claim/evidence entailment — actually checking whether a piece of evidence text supports a specific generated claim — is `[DEFERRED]`: it requires natural-language understanding of the claim and evidence text together, which is explicitly out of scope for a deterministic, LLM-free citation-integrity layer. No code anywhere in `src\citation\` reads `evidence_text` for any purpose other than its SHA-256 hash comparison (Section N) — no keyword matching, no embedding similarity, no entailment model, nothing that could be mistaken for "does this evidence support this claim."

## R. Multilingual Behavior

`[ENGINEERING RECOMMENDATION]` Citation validation is language-neutral by construction: resolution is exact-string-equality on `evidence_id` (a SHA-256 hex digest, never derived from evidence text — Phase 8 Section AA already established this), so the underlying evidence text's script never affects whether a citation resolves. `tests\test_phase_09_multilingual.py` validates citations against English, Devanagari, Tamil, and mixed-script `EvidencePack`s and asserts identical resolution behavior, plus that `evidence_text` is never touched, normalized, or rewritten by validation.

## S. Synthetic-Data Behavior

`[OFFICIAL SOURCE]` `synthetic=True` on the resolved Evidence is preserved, verbatim, onto `resolved_evidence.synthetic` on a `VALID` result — and a `VALID` status is reached identically whether the underlying evidence is synthetic or not (`tests\test_phase_09_validator.py`, `test_phase_09_evaluation.py`). There is no `synthetic_evidence` reason code (Section I) precisely because synthetic status is never, by itself, a validation failure. Conversely, no numeric result from the synthetic benchmark (Section AA) is ever represented as proof of real regulatory citation correctness.

## T. Serialization

`[ENGINEERING RECOMMENDATION]` (`src\citation\serialize.py`) Deterministic JSON (`sort_keys=True`, fixed separators, UTF-8) for `CitationReference`, `CitationValidationResult`, and `CitationCoverageMetrics`. **No `pickle`, no arbitrary/executable deserialization anywhere** — every payload is plain data. Two distinct strictness postures, matching Section F/G's two trust postures:

- `citation_reference_from_dict`: validates only the **envelope** (is this a dict? does the required `schema_version` key exist at all?) — rejects a non-dict payload or a missing `schema_version` key, but passes a malformed *value* (e.g. `evidence_id: 12345`) through unchanged, because classifying that value is `validator.py`'s job, never the parser's.
- `citation_validation_result_from_dict` / `citation_coverage_metrics_from_dict`: full explicit field reconstruction with every dataclass invariant re-enforced (status/reason_code/resolved_evidence consistency, count invariants) — any missing/malformed field or inconsistent pairing raises `CitationSchemaError`, never a silently-repaired partial object. This mirrors Phase 8's `evidence_from_dict` exactly, because these are trusted validator OUTPUT shapes, not untrusted input.

## U. Security

`[ENGINEERING RECOMMENDATION]` (`tests\test_phase_09_security.py`) Tested: fake/partial/truncated/case-folded/whitespace-wrapped evidence IDs, extremely long (1,000,000-character) evidence IDs, Unicode/emoji/mixed-script evidence IDs, SQL-like and `<script>`-like evidence IDs, path-traversal-like evidence IDs, prompt-injection-shaped evidence IDs and evidence text, fake URLs and fake document identifiers used as evidence IDs, a missing (`None`) or wrong-typed `EvidencePack`, malformed serialized JSON (non-dict payloads, missing keys), an inconsistent status/reason_code pairing in a hand-crafted result dict, and many (50) duplicate citation references in one call. **Citation reference content and evidence text are always treated strictly as data** — nothing in `src\citation\` executes them, interprets them as configuration, or lets them alter validator behavior, evidence selection, schema, or filesystem paths. No claim of comprehensive security coverage.

## V. URL Handling

`[OFFICIAL SOURCE]` Phase 8 already disclosed (`docs\PHASE_08_EVIDENCE_OBJECT_AND_CITATION_ARCHITECTURE.md` Section U) that no `Evidence` object carries a document-level `source_url` field, since no upstream Phase 2-7 contract propagates one forward. Phase 9 inherits this limitation unchanged: **no URL field exists anywhere in `src\citation\`, no URL is ever constructed, guessed, inferred from a source name, or resolved against the internet.** If a future phase adds a real, non-fabricated URL field to `Evidence`, Phase 9's `ResolvedEvidenceSummary` could be extended to surface it — but only once it genuinely exists upstream, never invented here to make citations "look complete."

## W. Authority/Currentness Boundary

`[OFFICIAL SOURCE]` Citation validation never decides whether a source is legally authoritative, whether a regulation applies, whether a legal interpretation is correct, or whether a document is current. `source_family_id` and `jurisdiction` are preserved on `resolved_evidence` unchanged from whatever Phase 2's authority matrix / Phase 8's Evidence already established — Phase 9 creates no second, competing authority hierarchy and makes no currentness claim. Phase 8's `VersionInfo` (Section T of the Phase 8 doc) remains "not available" for every Evidence object either phase can currently produce, since no upstream phase propagates version/effective-date fields forward; Phase 9 does not, and cannot, fabricate one. **No result from this phase should ever be read as "this citation is current" or "this source is legally authoritative."**

## X. Limitations

`[ENGINEERING RECOMMENDATION]`

- `EVIDENCE_PROVENANCE_FAILURE` is, in practice, unreachable through any `Evidence` object built via its own real constructor — it exists purely as a defense-in-depth guard against a hand-corrupted in-memory object, and every test that reaches it deliberately bypasses normal construction (`object.__new__`) to prove the guard fires. This is disclosed, not hidden: it is not a claim that real pipeline data commonly needs this check.
- `check_evidence_pack_validity` does not perform a full per-evidence-item integrity walk (Section J) — this is a deliberate trade-off (independently reachable, correctly-scoped reason codes) rather than an oversight, but it does mean a caller relying solely on `check_evidence_pack_validity()` returning `None` should not conclude every evidence item in the pack is individually untampered — only that the pack's own identity/shape is intact. Per-citation resolution (Section N) is what actually verifies the specific evidence being cited.
- No `source_url` or `VersionInfo` field exists anywhere in this phase — inherited limitations from Phase 8 (Sections V/W above), not new gaps introduced here.
- Semantic claim-support validation does not exist (Section Q) — by design, not as an oversight.
- No production-scale performance characteristics are measured (the benchmark corpus, Section AA, is small and synthetic).

## Y. Deferred Decisions

`[DEFERRED]`

- Semantic claim/evidence entailment (does evidence Y actually support claim X) — requires natural-language understanding beyond this phase's deterministic, LLM-free scope.
- Surfacing `resolved_evidence.source_url` / `resolved_evidence.version_info`, once (and only once) Phase 8's own upstream gaps (Sections V/W) are resolved by an explicitly authorized future amendment.
- Any additional citation `reference_type` beyond "an `evidence_id` pointing at a Phase 8 CHUNK Evidence object," if a concrete need arises.
- Everything Phase 10 owns: grounded generation, evidence-only prompting, answer structure, uncertainty wording, disclaimers — explicitly not this phase's job.
- Everything Phases 11-13 own: formulation classification, the jurisdiction firewall, confidence/abstention.

## Z. Acceptance Gate

`[ENGINEERING RECOMMENDATION]` (restated per `docs\PHASE_TRACKER.md`'s one-line text — *"Fake evidence IDs and unsupported claims are rejected"* — narrowed to this phase's actual, disclosed scope, since "unsupported claims" as literally written presupposes semantic claim-support validation, which Phase 9 explicitly does not implement, Section Q): a `CitationReference` model exists and is deliberately permissive of malformed input; a `CitationValidationResult` model exists and is strictly validated; the status vocabulary is closed and exactly `{VALID, INVALID, UNRESOLVED}`; the reason-code vocabulary is closed, documented, and every code is independently reachable; an `EvidencePack` is validated before any citation is resolved against it, and a failing pack invalidates every citation checked against it in that call; evidence-ID resolution is exact-string-match only, reusing Phase 8's own lookup, with zero fuzzy/partial/case-insensitive matching; a fabricated evidence ID is reported `UNRESOLVED`, never silently repaired; a malformed reference is reported `INVALID`, never silently repaired; a tampered/forged Evidence object is detected and reported `INVALID`, reusing Phase 8's own integrity functions; duplicate citations are tracked deterministically and are never automatically invalid; citation coverage metrics are explicitly scoped to citation integrity, never legal correctness; multilingual evidence resolves identically regardless of script; the `synthetic` flag survives unchanged; serialization is deterministic, round-trip safe, and rejects malformed envelopes/inconsistent trusted-output data; no LLM is required anywhere; no Phase 10 generation exists anywhere in this phase. **MET** — see Section AA for exact evidence.

## AA. Validation Results

`[ENGINEERING RECOMMENDATION]` All Phase 9 automated tests pass — model, validator, integrity, provenance, duplicate, metrics, determinism, multilingual, security, serialization, and evaluation tests, plus the synthetic citation-validation benchmark (exact counts in the Phase 9 implementation report). The benchmark (`tests\test_phase_09_evaluation.py`, fully synthetic fixtures marked `synthetic=true`, `SYNTHETIC-BENCH-09-*` document IDs) measures **implementation properties**, not legal-answer quality: valid-citation detection, invalid-citation detection, unresolved-citation detection, tamper detection, duplicate handling, deterministic results across repeated runs, multilingual resolution, and serialization round-trip correctness. **This does not measure regulatory correctness and is not a legal-answer benchmark** — no real regulatory corpus, no generation model, and no claim of legal correctness is involved anywhere in this phase. No real-model dependency exists in Phase 9 either (100% deterministic, stdlib-plus-Phase-8-only), so there is no "NOT VALIDATED — model unavailable" disclosure needed here, unlike Phase 6/7 — every gap this phase discloses (Sections V/W/X) is an upstream-data-availability or by-design-scope gap, not a validation gap in Phase 9's own code.
