# PHASE 15 — HUMAN-IN-THE-LOOP

Status: CONTRACT + IMPLEMENTATION DOCUMENT (Phase 15 deliverable)
Authoritative source: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`
Governed by: `docs\MASTER_REFERENCE_LOCK.md`, `docs\DEVELOPMENT_RULES.md`, `docs\PHASE_08_EVIDENCE_OBJECT_AND_CITATION_ARCHITECTURE.md`, `docs\PHASE_09_CITATION_VALIDATION.md`, `docs\PHASE_10_GROUNDED_GENERATION.md`, `docs\PHASE_11_FORMULATION_CLASSIFICATION.md`, `docs\PHASE_12_JURISDICTION_FIREWALL.md`, `docs\PHASE_13_CONFIDENCE_SAFETY_ABSTENTION.md`, `docs\PHASE_14_MULTILINGUAL_DELIVERY.md`
Machine-readable counterpart: `config\human_review_contract.yaml`
Implementation: `src\review\models.py`, `policy.py`, `workflow.py`, `validation.py`, `serialize.py`

**A human reviewer is a safety and quality-control boundary, never a replacement authority.** By the time a case reaches Phase 15, Phase 8 has already produced real evidence, Phase 9 has already validated citations, Phase 10 has already decided grounding, Phase 11 has already classified the request, Phase 12 has already routed jurisdiction, Phase 13 has already decided safety, and Phase 14 has already handled delivery/translation. Phase 15 never re-opens any of those decisions. It only ever does three things: (1) deterministically decide whether a case needs human eyes, using signals those phases already produced; (2) give a reviewer a read-only summary of what happened, plus a small, closed set of structured decisions to record; and (3) record that decision as an independent, immutable, auditable fact that can inform delivery — without ever silently rewriting anything upstream.

---

## A. Objective

`[OFFICIAL SOURCE]` `docs\PHASE_TRACKER.md`'s Phase 15 entry: *"Give users a clear path when AI cannot safely conclude... Ambiguous/out-of-scope/high-stakes cases reliably escalate."* `docs\MASTER_REFERENCE_LOCK.md` Section E's Final Core Pipeline ends in *"Answer OR Abstain/Human Escalation"* — Phase 15 implements exactly that escalation boundary: a deterministic workflow for the cases Phase 13 already flagged as `ABSTAIN`/`ESCALATE`, plus a small set of other already-established upstream uncertainty signals (Section E below), through to a structured, auditable human decision.

## B. Scope

In scope: deterministic review-trigger evaluation over already-existing Phase 9/10/11/12/13/14 signals; a structured `ReviewRequest` (trigger reasons, categorical priority, a flat case snapshot); a smallest-justified finite-state review workflow (`PENDING → IN_REVIEW → {APPROVED, REJECTED, NEEDS_MORE_EVIDENCE, ESCALATED}`); an immutable, append-only `ReviewAction` audit trail with explicit, non-timestamp ordering; reviewer-selected-evidence validation against a real `EvidencePack`; a "human review decision → delivery control" boundary (`authorize_presentation`) that can authorize presenting a non-`SAFE_TO_PRESENT` response only via a real, recorded `APPROVE` action; deterministic serialization.

## C. Non-Scope

Out of scope (no code for any of these exists anywhere in `src\review\`): re-implementing evidence construction (Phase 8), citation validation (Phase 9), grounded generation (Phase 10), formulation classification (Phase 11), jurisdiction routing (Phase 12), safety policy (Phase 13), or translation/delivery (Phase 14); a reviewer dashboard, web page, or any frontend (Phase 18); FastAPI endpoints or any productization (Phase 17); real authentication/authorization (`[DEFERRED]`); multi-reviewer consensus semantics; a corpus-feedback loop, automatic retraining, or automatic rule modification; the complete Phase 16 evaluation/red-team benchmark framework; project-wide adversarial security hardening (Phase 19); deployment, observability, backup, corpus refresh, or CI/CD (Phases 20-22).

## D. Architecture

`[ENGINEERING RECOMMENDATION]` Three cooperating modules, none of which imports a *constructor* for any upstream Phase 8-14 object (only their already-closed vocabularies, for validation, and — for evidence — membership-only lookups):

1. **`policy.py`** — `evaluate_review_trigger(...)` (the sole trigger decision), `build_review_request(...)` (wraps a firing trigger into a structured, serializable `ReviewRequest`, or returns `None` for a safe/normal case), `authorize_presentation(...)` (the "human review decision → delivery control" boundary).
2. **`workflow.py`** — `apply_action(...)` (the sole place a new `ReviewAction` is created), `compute_current_status(...)` (folds an ordered, immutable `ReviewAction` history into a live status — `ReviewRequest` itself never stores a mutable status field).
3. **`validation.py`** — defensive checks (`validate_reviewer_id`, `validate_action_type`, `validate_selected_evidence_ids`) that `workflow.py` calls before constructing anything, mirroring Phase 9's `CitationReference`/`validator.py` split: untrusted input is permissive to *receive*, but every check deciding whether it may be *used* is explicit and fails closed.

`ReviewRequest` and `ReviewAction` are both frozen dataclasses — **nothing in this package ever mutates an existing object**. A review's "current status" is always a derived fold over its `ReviewAction` history (event-sourced), never a field flipped in place.

## E. Review Triggers

`[OFFICIAL SOURCE]`/`[ENGINEERING RECOMMENDATION]` Exactly eleven trigger reasons, each reading **one already-closed vocabulary value from an earlier phase's own contract** — no new regulatory-risk category, keyword heuristic, or numeric threshold is invented anywhere in this phase (per explicit instruction). See `config\human_review_contract.yaml`'s `trigger_reason_source_mapping` for the exact, machine-readable source of each:

| Trigger reason | Source signal | Priority |
|---|---|---|
| `SAFETY_ESCALATE` | `SafetyDecision.safety_status == ESCALATE` (Phase 13) | `CRITICAL` |
| `SAFETY_ABSTAIN` | `SafetyDecision.safety_status == ABSTAIN` (Phase 13) | `HIGH` |
| `CLASSIFICATION_AMBIGUOUS` | `ClassificationResult.classification_state == AMBIGUOUS`, or `requires_escalation` (Phase 11) | `HIGH` |
| `CLASSIFICATION_UNRESOLVED` | `classification_state == UNKNOWN` (Phase 11) | `NORMAL` |
| `CLASSIFICATION_NEEDS_EVIDENCE` | `classification_state == NEEDS_EVIDENCE` (Phase 11) | `NORMAL` |
| `REGULATORY_TRACK_CONFLICTING` | `formulation_classification.regulatory_track == CONFLICTING` (Phase 1/11's own existing taxonomy value — satisfies "conflicting evidence" without inventing a new concept) | `HIGH` |
| `JURISDICTION_AMBIGUOUS` | `JurisdictionDecision.state == AMBIGUOUS`, or `requires_escalation` (Phase 12) | `HIGH` |
| `JURISDICTION_UNRESOLVED` | `state == UNKNOWN` (Phase 12) | `NORMAL` |
| `CITATION_INTEGRITY_FAILURE` | any supplied `CitationValidationResult.status != VALID` (Phase 9) | `HIGH` |
| `GROUNDING_FAILURE` | `GroundedResponse.grounding_status != GROUNDED` (Phase 10) | `HIGH` |
| `MULTILINGUAL_DELIVERY_ISSUE` | `MultilingualDeliveryResult.delivery_status in {TRANSLATION_FAILED, UNSUPPORTED_LANGUAGE}` (Phase 14) | `NORMAL` |

`evaluate_review_trigger` accepts every upstream object as optional and independently checkable — a caller may supply just one (e.g. only a `JurisdictionDecision`, to test jurisdiction-uncertainty routing in isolation) or the full set from a real pipeline run. Multiple reasons may co-fire; `priority` is the categorical maximum across all fired reasons (`NORMAL < HIGH < CRITICAL`), never a numeric score (`[NO NUMERIC CONFIDENCE INVENTION]`, per explicit instruction). No trigger fires for a case where every supplied signal is within its own normal/non-ambiguous bounds — `build_review_request` returns `None` in that case rather than fabricating an escalation.

## F. Review Request

`[ENGINEERING RECOMMENDATION]` `ReviewRequest`: `schema_version`, `review_request_id` (deterministic SHA-256, Section W), `input_id`, `original_query`/`canonical_query` (preserved verbatim, exactly like Phase 14's `MultilingualInputContext`), `case_snapshot` (a `ReviewCaseSnapshot` — Section Q), `trigger_reasons`/`priority`/`review_reason` (from `evaluate_review_trigger`), `review_status` (always `PENDING` at construction — enforced), `config_signature`. Per explicit instruction not to duplicate upstream objects unnecessarily: **no live reference to, or copy of, the full `EvidencePack`/`GroundedResponse`/`ClassificationResult`/etc. is ever stored here** — only a flat summary of their own already-established status/state fields plus their own deterministic identity strings (`evidence_pack_id`, `response_id`, `jurisdiction_decision_id`, `safety_decision_id`, `multilingual_result_id`), so a reviewer or auditor can locate the real, authoritative object elsewhere without this request ever becoming a second, competing copy of it.

## G. Review States

`[ENGINEERING RECOMMENDATION]` The smallest state machine that is actually justified by this phase's own scope — arrived at by reasoning, not by blindly copying the instructions' example list (which happens to coincide with it once the reasoning is done): `PENDING` (initial), `IN_REVIEW` (a reviewer has explicitly claimed the case via `START_REVIEW` — optional; a decision may also be recorded directly from `PENDING`), `APPROVED`/`REJECTED`/`NEEDS_MORE_EVIDENCE`/`ESCALATED` (terminal — no further action is permitted, docs Section AC discloses why `NEEDS_MORE_EVIDENCE`/`ESCALATED` do not loop back into this same request rather than looping automatically). Every transition is looked up in one fixed, closed table (`models.ACTION_TRANSITIONS`); any `(status, action)` pair absent from it is an `InvalidReviewTransitionError`, never silently normalized to the nearest valid one.

## H. Review Decisions

`[ENGINEERING RECOMMENDATION]` Exactly five reviewer actions — `START_REVIEW` (claim, not a decision), `APPROVE`, `REJECT`, `REQUEST_MORE_EVIDENCE`, `ESCALATE` (the four actual decisions). `workflow.apply_action` is the sole constructor of a `ReviewAction`: it folds the request's action history to find the *real* current status (never a status the caller merely asserts), validates the transition, validates any `selected_evidence_ids` against a real `EvidencePack` (Section K), and returns a new, independent, immutable record. **A reviewer cannot**, anywhere in this package: edit an Evidence ID or hash, edit source provenance, edit jurisdiction metadata, fabricate or upgrade a citation, change `original_query`, change upstream classification, or turn an unsafe response `SAFE_TO_PRESENT` on the `SafetyDecision` object itself — there is no field, function, or import in `src\review\` that could do any of those things (Sections J-P, verified structurally by `tests\test_phase_15_security.py`).

## I. Reviewer Identity

`[ENGINEERING RECOMMENDATION]`/`[DEFERRED]` `reviewer_id` is a required, non-empty string on every `ReviewAction` — the only requirement this phase imposes. **No real authentication or authorization is implemented** (`validation.validate_reviewer_id` only rejects `None`/empty/non-string values) — real identity verification belongs to a later product/security phase (Phase 17+) unless existing infrastructure already supports it, which it does not in this repository. Synthetic reviewer IDs (`"synthetic-test-reviewer-001"`, etc.) are explicitly acceptable and used throughout this phase's own tests. This is the one place system-generated data (everything else on `ReviewAction`) and reviewer-generated data (`reviewer_id`, `reviewer_comment`, `selected_evidence_ids`) are structurally distinguished by field ownership, not by convention alone.

## J. Evidence Immutability

`[OFFICIAL SOURCE]` `src\review\` never imports `evidence.builder` (no construction function) and never holds a mutable reference to an `Evidence`/`EvidencePack` object beyond reading `evidence_pack.evidence_items[*].evidence_id` for one membership check (Section K). No code path anywhere in this package can change `evidence_text`, `evidence_text_hash`, `content_hash`, `document_id`, `source_family_id`, or `jurisdiction` on any `Evidence` object. `tests\test_phase_15_security.py` proves this directly: a full review cycle (`START_REVIEW` → `APPROVE`, including a malicious comment) leaves `evidence_id`/`evidence_text_hash`/`pack_id` byte-identical, and Phase 8's own `verify_pack_identity`/`verify_evidence_identity` still pass afterward.

## K. Citation Integrity

`[OFFICIAL SOURCE]` A reviewer may only ever *select* (`selected_evidence_ids` on a `ReviewAction`) evidence that already exists in a real, supplied `EvidencePack` — `validation.validate_selected_evidence_ids` performs exact-string membership only (no fuzzy/partial matching, mirroring Phase 9's own citation-resolution discipline) and raises `FakeEvidenceReferenceError` for anything else, including when no `EvidencePack` is supplied at all to validate against (fail closed, never "trusted anyway"). This is a *selection* of existing evidence for the reviewer's own reference, never the creation of a new citation, and it never revalidates or overrides a Phase 9 `CitationValidationResult`.

## L. Classification Interaction

`[OFFICIAL SOURCE]` `ClassificationResult` is read only for `classification_state`/`requires_escalation`/`formulation_classification.regulatory_track`/`evidence_state`/`input_id` — captured as flat strings on `ReviewCaseSnapshot`, never re-derived, never overwritten. A reviewer may flag disagreement only via `reviewer_comment` (untrusted free text) or by choosing `REQUEST_MORE_EVIDENCE`/`ESCALATE` as their own workflow decision — there is no field or function anywhere in `src\review\` that replaces or edits a `ClassificationResult`.

## M. Jurisdiction Interaction

`[OFFICIAL SOURCE]` `JurisdictionDecision` is read only for `state`/`requires_escalation`/`decision_id` — Phase 12's firewall decision is never rewritten. A reviewer who believes jurisdiction routing is wrong can only express that as `reviewer_comment` text or a workflow decision (`REJECT`/`ESCALATE`) — never a structural override, and `ReviewAction` has no `jurisdiction`/`jurisdiction_state` field at all (directly asserted, `tests\test_phase_15_security.py::test_fake_jurisdiction_claim_never_appears_as_a_trusted_field`).

## N. Grounding Interaction

`[OFFICIAL SOURCE]` `GroundedResponse` is read only for `grounding_status`/`cited_evidence_ids`/`response_id`/`evidence_pack_id`/`synthetic` — Phase 10's own grounding decision is never manufactured or overridden. Requesting more evidence (`REQUEST_MORE_EVIDENCE`) does not, and cannot, change the original `GroundedResponse` object — it only records the reviewer's own decision as a separate fact; producing an actual new grounded response for a corrected case would require re-running Phase 8-10, which is explicitly out of this phase's scope (Section Z).

## O. Safety Interaction

`[OFFICIAL SOURCE]` Phase 13's `SafetyDecision` remains the sole automated safety authority — nothing in `src\review\` writes a new `safety_status` onto it or anywhere else. `authorize_presentation(safety_decision, review_action=None)` is the one place this phase produces a presentation-relevant answer: if `safety_decision.safety_status == "SAFE_TO_PRESENT"`, it is authorized automatically (`source="AUTOMATED_SAFE_TO_PRESENT"`); otherwise, presentation is authorized **only** given a real `ReviewAction` with `action == "APPROVE"` (`source="HUMAN_REVIEW_APPROVED"`, always carrying `FIXED_HUMAN_REVIEW_DISCLAIMER` — never a claim of legal certainty or government authority, Section T); otherwise `source="BLOCKED"`. `safety_status` on the returned `PresentationAuthorization` is always the *original* value (`ESCALATE`/`ABSTAIN`), never silently rewritten to `SAFE_TO_PRESENT`.

## P. Multilingual Interaction

`[OFFICIAL SOURCE]` `MultilingualDeliveryResult` is read only for `delivery_status`/`requested_language`/`detected_script`/`result_id` — Phase 14's translation/delivery decision is never re-run or overridden. `ReviewCaseSnapshot` never carries the translated `answer_text` itself (only the status/language/script metadata needed to understand *what kind* of delivery issue occurred) — a reviewer who needs the actual answer text consults the real `MultilingualDeliveryResult`/`GroundedResponse` objects directly, never a duplicated copy living on the review request.

## Q. Review Snapshot

`[ENGINEERING RECOMMENDATION]` "What system state was reviewed" is answered by `ReviewCaseSnapshot` — a flat, fully-validated (Section below) summary of upstream facts, plus each upstream object's own deterministic identity string. **Disclosed limitation:** this phase has no persistence layer (Phase 17+'s own scope) — the snapshot is a value captured at `build_review_request` call time from whatever objects were in memory then; it does not, by itself, *prevent* a caller from later reconstructing a different in-memory object under the same identity elsewhere. Within this phase's own domain-logic scope, every relevant object (`Evidence`, `EvidencePack`, `ClassificationResult`, `JurisdictionDecision`, `GroundedResponse`, `SafetyDecision`, `MultilingualDeliveryResult`) is already a frozen dataclass (Phase 8-14's own discipline) — immutability during one review's lifetime is guaranteed by Python's own object model for as long as the same in-memory objects are used, which is the only guarantee a persistence-free domain layer can honestly make.

## R. Audit Trail

`[ENGINEERING RECOMMENDATION]` Every reviewer action is an independent, immutable `ReviewAction`: `review_action_id` (deterministic SHA-256), `review_request_id`, `sequence_number` (an explicit ordinal — Section W), `reviewer_id`, `action`, `previous_status`/`new_status` (cross-validated against the same closed transition table at construction — a hand-forged, internally-inconsistent record is structurally impossible), `reviewer_comment` (untrusted, bounded to `MAX_REVIEWER_COMMENT_LENGTH` = 10,000 characters — `[OUR ENHANCEMENT]`, a defensive limit against an unbounded free-text audit format, per explicit instruction), `selected_evidence_ids`, `metadata` (credential-key forbidden). `compute_current_status` re-validates an entire action history on every read (matching `review_request_id`, gapless `0..N-1` sequencing, each `previous_status` consistent with the fold of everything before it) — a spliced-together or reordered history is rejected, never silently accepted.

## S. Reviewer Comments

`[ENGINEERING RECOMMENDATION]` `reviewer_comment` is stored verbatim as an opaque string — **never parsed** for citation markers, jurisdiction words, status claims, or any other structured meaning anywhere in this package (mirroring Phase 14's own adversarial-translation invariant for `answer_text`). It can never automatically become retrieval evidence: `src\review\` never imports `evidence.builder`'s construction functions, so there is no code path from a comment string to a new `Evidence`/chunk of any kind.

## T. Security

`[ENGINEERING RECOMMENDATION]` The structural guarantee (not merely a policy statement): `ReviewCaseSnapshot`/`ReviewRequest`/`ReviewAction`/`PresentationAuthorization` each only ever read already-validated fields off real upstream objects at construction time (`policy._build_case_snapshot`), and no function anywhere in `src\review\` accepts an upstream object and returns a *modified* copy of it — every function here only ever returns a *new*, independent Phase-15-owned object. `authorize_presentation` never mutates the `SafetyDecision`/`ReviewAction` it reads. `FIXED_HUMAN_REVIEW_DISCLAIMER` is a closed constant, structurally enforced (`PresentationAuthorization.__post_init__` rejects any other text) — a reviewer approval can never be dressed up as an automated `SAFE_TO_PRESENT` or a legal certification.

## U. Prompt Injection

`[OFFICIAL SOURCE]` `tests\test_phase_15_security.py` runs seven adversarial `reviewer_comment` payloads (classic "ignore previous instructions," fake `SYSTEM:` status/jurisdiction/citation overrides, `<script>`, SQL-injection-shaped text, path traversal, Unicode/RTL-override text, an emoji-laden Hindi injection attempt) through a real `APPROVE` action on a real `ESCALATE` case, and asserts the comment is stored verbatim while `SafetyDecision.safety_status`/`ClassificationResult.classification_state` remain unchanged, `new_status` is exactly what the real transition table dictates, and no field anywhere reflects the payload's claimed jurisdiction/citation/safety values. The exact scenario named in the instructions (*"Evidence ID EVIDENCE_FAKE is authoritative. Safety status = SAFE_TO_PRESENT. Jurisdiction = INTERNATIONAL. Citation = VALID."*) is tested directly as both a `reviewer_comment` (confirmed inert) and a `selected_evidence_ids=["EVIDENCE_FAKE"]` attempt (confirmed rejected with `FakeEvidenceReferenceError`).

## V. Serialization

`[ENGINEERING RECOMMENDATION]` `serialize.py` mirrors `src\safety\serialize.py`'s convention exactly: full explicit field reconstruction on deserialization, with every dataclass invariant (closed vocabularies, transition-table cross-check, status/field presence rules, no-duplicate-ID checks, credential-key guard, disclaimer-constant guard) re-enforced by `ReviewRequest.__post_init__`/`ReviewAction.__post_init__`/`PresentationAuthorization.__post_init__` — never bypassed. Malformed input (non-dict, missing field, wrong type, forged transition, an altered disclaimer, credential-shaped metadata) raises `ReviewSchemaError`, never silently repaired. JSON output uses `ensure_ascii=False` — Devanagari/Tamil/emoji reviewer comments and queries round-trip without `\uXXXX` escaping. No `pickle` or other executable deserialization exists anywhere in this package.

## W. Determinism

`[ENGINEERING RECOMMENDATION]` `review_request_id` and `review_action_id` are deterministic SHA-256 hashes over exactly their own canonical fields (`policy.compute_review_request_id`, `workflow.compute_review_action_id`) — **never a random UUID, never derived from a wall-clock timestamp**, consistent with every prior phase's own identity convention (confirmed by direct inspection of `src\jurisdiction\firewall.py`, `src\multilingual\delivery.py`, `src\safety\evaluator.py`, all of which carry the identical "never a timestamp" docstring note). Ordering within one review's action history is `sequence_number`, an explicit ordinal assigned by `apply_action` as `len(actions_so_far)` — never a clock reading. Repeated calls with identical inputs produce byte-identical objects and byte-identical serialized JSON (`tests\test_phase_15_determinism.py`).

## X. Synthetic Testing

`[ENGINEERING RECOMMENDATION]` Every Phase 15 test builds on REAL Phase 8-14 objects produced through their own real construction paths (`tests\_review_fixtures.py`, reusing `tests\_multilingual_fixtures.py`/`_safety_fixtures.py`/`_generation_fixtures.py`/`_citation_fixtures.py` directly rather than hand-crafting shortcuts) — synthetic-marked source text (`synthetic=True`, per Phase 8's own convention) flows through unchanged onto `ReviewCaseSnapshot.synthetic`, never presented as real regulatory evidence. No fabricated numeric benchmark of "review quality" or "reviewer accuracy" is claimed anywhere in this phase — there is no labeled dataset for that, and none is invented here.

## Y. Known Limitations

`[ENGINEERING RECOMMENDATION]`, disclosed, not hidden:
1. No persistence layer exists — `ReviewRequest`/`ReviewAction` are in-memory Python objects only; a real deployment needs Phase 17+ to add storage, at which point this phase's own deterministic identities (`review_request_id`/`review_action_id`) become the natural primary keys, requiring no redesign here.
2. No real reviewer authentication exists (Section I) — `reviewer_id` is trusted as supplied by the caller.
3. `NEEDS_MORE_EVIDENCE`/`ESCALATED` are terminal for a given `ReviewRequest` — obtaining a corrected answer requires a new pipeline run (a new `EvidencePack`/`GroundedResponse`/etc.) and a new `ReviewRequest`, never an automatic re-open of this one (Section Z).
4. `IN_REVIEW` does not implement locking/assignment — two reviewers could both call `apply_action` from the same `PENDING`/`IN_REVIEW` state; both actions would be independently valid and recorded (multiple concurrent reviews remain separate records, per explicit instruction not to invent consensus semantics), but nothing here detects or resolves the resulting disagreement.
5. `ReviewCaseSnapshot`'s immutability guarantee is bounded by "the same in-memory frozen dataclass objects were used" (Section Q) — it is not a cryptographic tamper-proof snapshot of a persisted record, since no persisted record exists yet.

## Z. Deferred Items

`[DEFERRED]`: real reviewer authentication/authorization; a reviewer dashboard or any frontend; FastAPI productization of this workflow; multi-reviewer consensus semantics; reviewer-feedback-driven corpus updates, retraining, or rule modification; automatic re-opening of a `NEEDS_MORE_EVIDENCE`/`ESCALATED` request once new evidence/classification/jurisdiction/safety objects exist; persistent storage of `ReviewRequest`/`ReviewAction` records; the complete Phase 16 evaluation/red-team benchmark framework; project-wide adversarial security hardening (Phase 19).

## AA. Phase 16 Boundary

`[ENGINEERING RECOMMENDATION]` Phase 15 implements only its own workflow-level security/adversarial tests (`tests\test_phase_15_security.py`) — it does not implement Phase 16's complete evaluation/red-team benchmark framework, and no code in `src\review\` references, imports, or anticipates a Phase 16 evaluation-harness API. Reviewer decisions recorded here are exactly the kind of ground truth a *future*, separately-scoped Phase 16 benchmark might reference — but building that benchmark is explicitly not this phase's job.

## AB. Acceptance Gate

`[ENGINEERING RECOMMENDATION, as restated for this implementation, since CAP-15's text — "Ambiguous/out-of-scope/high-stakes cases reliably escalate" — is met directly]` a deterministic review-trigger boundary exists over already-established Phase 9-14 signals, with no new regulatory-risk category invented; review triggers, states, and decisions are all explicit, closed, and validated; state transitions are deterministic and invalid transitions fail explicitly; reviewer identity is a separate, non-authoritative field; evidence, citation identity, classification, jurisdiction, grounding, and safety are all structurally un-mutatable by anything in `src\review\`, proven adversarially; reviewer comments remain untrusted metadata, proven against seven prompt-injection payloads and the exact malicious-action scenario named in the instructions; serialization is deterministic, round-trip safe, and rejects malformed/forged data; determinism holds for both identity hashes and full JSON; no FastAPI/React/authentication/corpus-feedback/retraining/Phase 16+ functionality exists anywhere in this phase. **MET.**

## AC. Validation Evidence

`pytest tests/ -v` run twice — see the Phase 15 implementation report for the exact pass counts of both runs. Zero skips, zero xfail, zero weakened assertions anywhere in `tests\test_phase_15_*.py`. Phase 0-14 regression, Master Reference hash integrity, source-discipline audit, and phase-boundary audit (no FastAPI/React/reviewer-dashboard/authentication/corpus-feedback/retraining/evaluation-framework/deployment/monitoring code, fields, or imports anywhere in `src\review\`) all pass — see `tests\test_phase_15_regression.py`.
