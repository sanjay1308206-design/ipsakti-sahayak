# PHASE 13 — CONFIDENCE + SAFETY + ABSTENTION

Status: CONTRACT + IMPLEMENTATION DOCUMENT (Phase 13 deliverable)
Authoritative source: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`
Governed by: `docs\MASTER_REFERENCE_LOCK.md`, `docs\DEVELOPMENT_RULES.md`, `docs\PHASE_09_CITATION_VALIDATION.md`, `docs\PHASE_10_GROUNDED_GENERATION.md`, `docs\PHASE_11_FORMULATION_CLASSIFICATION.md`, `docs\PHASE_12_JURISDICTION_FIREWALL.md`
Machine-readable counterpart: `config\confidence_safety_contract.yaml`
Implementation: `src\safety\models.py`, `policy.py`, `evaluator.py`, `serialize.py`

**Do not let the system sound more certain than its evidence justifies.** Every prior phase already produced its own honest uncertainty signal — Phase 11's `UNKNOWN`/`AMBIGUOUS`, Phase 12's `UNKNOWN`/`AMBIGUOUS`, Phase 10's `ABSTAINED`/`GENERATION_FAILED`, Phase 9's citation-integrity ratio. Phase 13 does not re-derive any of these. It is the final, deterministic gate that reads all of them together and decides whether the resulting answer may actually be shown.

---

## A. Phase Objective

`[OFFICIAL SOURCE]` The Master Reference's Final Architecture Decision Lock places *"Confidence + Safety"* immediately after citation validation, ending in *"Answer OR Abstain/Human Escalation"* (`docs\MASTER_REFERENCE_LOCK.md` Section E). `docs\PHASE_TRACKER.md`'s CAP-13 entry: *"Make the system safe when evidence is weak or conflicting... low-confidence/high-stakes cases abstain or escalate instead of guessing."* Phase 13 implements exactly that final boundary — a deterministic policy layer, not a new inference engine.

## B. Scope

In scope: `SafetyDecision`/`SafetyPolicyConfig` models; a fixed, ordered sequence of nine hard safety gates over Phase 11/12/10's already-produced decisions; an optional, explicitly-categorical "engineering signal" computed only after every hard gate has passed; deterministic serialization.

Out of scope (no code for any of these exists anywhere in `src\safety\`): retrieval of any kind, classification, jurisdiction routing, citation validation, evidence construction, answer generation, semantic entailment, human-in-the-loop workflow implementation, translation, an API, a frontend, deployment, or monitoring.

## C. Non-Scope

`[ENGINEERING RECOMMENDATION]` Explicitly, Phase 13 is not another retrieval engine, another classifier, another citation validator, another LLM, a legal reasoning engine, or a semantic entailment engine. It never writes a rule like *"patent applications with X are unsafe"* unless an authoritative source explicitly establishes such a rule (none does, anywhere in this project) — it only ever reads already-computed upstream signals and applies a fixed, disclosed policy over them.

## D. Existing Contracts Reused

`[OFFICIAL SOURCE]` Four objects, reused directly by type, never reconstructed or duplicated:

1. `classification.models.ClassificationResult` (Phase 11) — `classification_state`, `requires_escalation`.
2. `jurisdiction.models.JurisdictionDecision` (Phase 12) — `state`, `requires_escalation`.
3. `generation.models.GroundedResponse` (Phase 10) — `grounding_status`, `abstention_reason`, `failure_reason`, `cited_evidence_ids`, `citation_validation_summary`, `synthetic`.
4. `citation.metrics.CitationCoverageMetrics` (Phase 9) — reached *through* `GroundedResponse.citation_validation_summary`, never a separate parameter and never recomputed: `unique_valid_evidence_id_count`, `citation_integrity_validation_rate`.

**Design decision, explicitly documented:** Phase 13 does **not** accept a raw `EvidencePack` or a separate list of `CitationValidationResult` objects as input. Every signal Phase 13 needs from Phases 8/9 is already summarized and carried forward inside `GroundedResponse` (Phase 10 already does this work) — accepting the raw upstream objects directly would risk Phase 13 re-deriving conclusions Phase 9/10 already reached, which the instructions explicitly forbid ("do NOT reimplement citation validation").

## E. Safety Architecture

`[ENGINEERING RECOMMENDATION]` `evaluate_safety(input_id, classification_result, jurisdiction_decision, grounded_response, config) -> SafetyDecision`. Internally: nine ordered, deterministic, first-match-wins gates (`G1`..`G9`), mirroring the exact "ordered rule list" convention Phase 1/9/11/12 already established for their own decision trees. Every gate runs to completion in order; the optional engineering signal (Section J) is computed **only** inside `G9`, after every hard gate has already passed — there is no code path that computes a reassuring signal and then discovers a hard failure afterward (docs "HARD-GATE ORDER", directly enforced by the code's own control flow, not merely by convention).

## F. Input Contract

`[ENGINEERING RECOMMENDATION]` All three upstream objects are **optional** (`None` is a legitimate, safety-relevant input meaning "this stage was never run" or "not supplied") — `evaluate_safety` fails closed rather than raising when they are absent, since a caller invoking Phase 13 with incomplete information is exactly the scenario this phase exists to handle safely. `config: Optional[SafetyPolicyConfig]` supplies the explicit, documented policy coefficients (Section K).

## G. Output Contract

`[ENGINEERING RECOMMENDATION]` `safety.models.SafetyDecision`: `schema_version`, `decision_id` (deterministic SHA-256, Section Y), `input_id`, `safety_status`, `reason_code`, `explanation`, `engineering_signal_band`, `hard_gate_results` (the ordered `G1:PASS`/`G1:FIRED`-style audit trail), `input_status_summary` (a flat, purely informational dict of the raw upstream facts observed — `classification_state`, `jurisdiction_state`, `grounding_status`, `cited_evidence_count`, `unique_valid_evidence_id_count`, `citation_integrity_validation_rate` — **never itself consulted to make the decision**, only recorded for audit), `abstained`, `escalation_required`, `synthetic` (`Optional[bool]` — `None` when genuinely unknown, never defaulted to `False`), `config_signature`. Every invariant (status/reason-code pairing, `abstained`/`escalation_required` consistency, `engineering_signal_band` presence rule) is enforced at construction, mirroring Phase 9/11/12's own discipline.

## H. Hard Safety Gates

`[OFFICIAL SOURCE]`/`[ENGINEERING RECOMMENDATION]` Exactly nine, in this fixed order (matching the pipeline order Classification → Jurisdiction → Generation):

| Gate | Fires when | Result | Reason code |
|---|---|---|---|
| G1 | `classification_result.requires_escalation` (Phase 11's own flag) | `ESCALATE` | `CLASSIFICATION_AMBIGUOUS` |
| G2 | `classification_result` missing, or `classification_state == "UNKNOWN"` | `ABSTAIN` | `CLASSIFICATION_UNRESOLVED` |
| G3 | `jurisdiction_decision.requires_escalation` (Phase 12's own flag) | `ESCALATE` | `JURISDICTION_AMBIGUOUS` |
| G4 | `jurisdiction_decision` missing, or `state == "UNKNOWN"` | `ABSTAIN` | `JURISDICTION_UNRESOLVED` |
| G5 | `grounded_response` missing | `ABSTAIN` | `MISSING_GROUNDED_RESPONSE` |
| G6 | `grounding_status == "GENERATION_FAILED"` (Phase 10's own status) | `ABSTAIN` | `GENERATION_FAILED` |
| G7 | `grounding_status == "ABSTAINED"` (Phase 10's own status) | `ABSTAIN` | `GENERATION_ABSTAINED` |
| G8 | zero `cited_evidence_ids`, and `config.require_at_least_one_valid_citation` | `ABSTAIN` | `NO_VALID_CITATIONS` |
| G9 | none of the above fired | `SAFE_TO_PRESENT` | `SAFE_GROUNDED_RESPONSE` |

`classification_state == "NEEDS_EVIDENCE"` deliberately does **not** fire G2 — it means *"classification itself is fully resolved; only evidence is outstanding"* (Phase 1's own definition), and whether that evidence materialized is exactly what G5–G8 check next. Treating `NEEDS_EVIDENCE` the same as `UNKNOWN` would discard information Phase 11 already established (`tests\test_phase_13_integration.py::test_needs_evidence_classification_proceeds_to_grounding_check`).

## I. Soft Signals

`[ENGINEERING RECOMMENDATION]` Exactly two, both already-existing, already-bounded Phase 9 fields reached through `GroundedResponse.citation_validation_summary`: `unique_valid_evidence_id_count` and `citation_integrity_validation_rate`. Both are informational inputs to the engineering signal (Section J) **only** — they can never force `ABSTAIN`/`ESCALATE` on their own, and they are computed strictly after every hard gate has passed (G9). Retrieval-quality scores (BM25/dense/RRF/reranker) are never read, combined, or treated as a soft signal anywhere in this phase (Section T).

## J. Confidence/Trust Representation

`[OFFICIAL SOURCE]` **`engineering_signal_band` is an ENGINEERING signal about citation-integrity/grounding structure only.** It is never a probability that a legal answer is correct, a probability of regulatory approval, legal certainty, legal compliance, a patentability probability, or an infringement probability. It is **categorical**, not numeric (`STRONG`/`MODERATE`/`WEAK`/`NOT_APPLICABLE`) — per the explicit instruction to *"prefer a categorical trust/safety assessment"* when no calibration exists, which is the case here: no numeric probability, confidence percentage, or score of any kind is computed, stored, or exposed anywhere in `src\safety\`. `NOT_APPLICABLE` is the only value reachable when `safety_status != "SAFE_TO_PRESENT"` — no signal about citation structure is meaningful for a response that was never presented.

## K. Threshold Policy

`[ASSUMPTION]` **No empirically validated threshold exists anywhere in the Master Reference or any prior-phase contract** for what makes citation coverage "strong" versus "weak" — this was directly inspected and confirmed absent before any coefficient below was chosen. `safety.policy.compute_engineering_signal_band` uses exactly three configurable coefficients (`SafetyPolicyConfig.strong_min_unique_citations=2`, `strong_min_integrity_rate=1.0`, `moderate_min_integrity_rate=0.5`):

- **Why these terms exist:** more independently-corroborating real citations, and fewer failed citation attempts alongside them, is an intuitively more defensible grounding structure than the alternative — this is the entire justification.
- **Why these particular values:** arbitrary, round, conservative-leaning numbers chosen for legibility, not derived from any study.
- **What evidence does NOT support them:** no labeled dataset, no calibration exercise, no legal-outcome correlation study — none exists in this project. Changing any of these three numbers would be equally unjustified in either direction; they are defaults, not findings.
- **How they must eventually be validated:** only via a real, labeled benchmark correlating `engineering_signal_band` with an actual downstream outcome — none exists today, and none is claimed to exist (Section AB).

`STRONG`: `unique_valid_evidence_id_count >= strong_min_unique_citations` **and** `citation_integrity_validation_rate >= strong_min_integrity_rate`. `MODERATE`: at least one valid citation (already guaranteed by G8 having passed) **and** `rate >= moderate_min_integrity_rate`. `WEAK`: everything else that still reached G9. `G8`'s own boolean (`require_at_least_one_valid_citation`, default `True`) is likewise `[ASSUMPTION]`-labeled: it is Phase 13's own, deliberately-stricter-than-Phase-10 presentation-safety policy, not a value Phase 10's own (relaxable) `require_citations` config dictates.

## L. Abstention

`[OFFICIAL SOURCE]` `ABSTAIN` means *"the system lacks sufficient evidence/conditions to answer safely"* — reached by G2, G4, G5, G6, G7, G8. `abstained` is `True` if and only if `safety_status == "ABSTAIN"`, enforced at construction. An abstained decision never carries a real `engineering_signal_band` and the underlying `GroundedResponse.answer_text` (already `None` for `ABSTAINED`/`GENERATION_FAILED` per Phase 10's own invariant) is never surfaced as if it were safe.

## M. Escalation Boundary

`[OFFICIAL SOURCE]`/`[DEFERRED]` `ESCALATE` means *"an existing project policy (Phase 11's or Phase 12's own `requires_escalation` flag) flags this case for review"* — reached only by G1 and G3, both direct reuses of an upstream phase's own boolean, never a Phase-13-invented escalation condition. `escalation_required` is `True` if and only if `safety_status == "ESCALATE"`. **Phase 13 emits this flag only** — it creates no reviewer queue, no case assignment, no notification, and no approval workflow anywhere in `src\safety\` (verified structurally, `tests\test_phase_13_abstention.py`); the actual human-in-the-loop workflow is Phase 15's own, explicitly deferred, scope.

## N. Phase 10 Integration

`[OFFICIAL SOURCE]` `grounding_status` is read and branched on directly (G6/G7) — never recomputed. `GENERATION_FAILED` and `ABSTAINED` can never become `SAFE_TO_PRESENT` (`tests\test_phase_13_gates.py::test_g6_generation_failed`, `test_g7_generation_abstained_no_evidence`). `GROUNDED` does **not** automatically mean safe — it still must pass G8 and, even then, only reaches `SAFE_TO_PRESENT` via G9 after every prior gate (`tests\test_phase_13_gates.py::test_g9_default_safe_reachable`).

## O. Phase 9 Integration

`[OFFICIAL SOURCE]` Citation validation is never reimplemented — `unique_valid_evidence_id_count`/`citation_integrity_validation_rate` are read verbatim from `GroundedResponse.citation_validation_summary` (itself Phase 9's own, unmodified `CitationCoverageMetrics`). **Documented policy, explicitly not automatic:** an invalid or unresolved citation *attempt* alongside at least one surviving valid citation does **not**, by itself, force abstention — Phase 9/10 already excluded the invalid attempt from `cited_evidence_ids`; Phase 13 only additionally penalizes it *informationally* (a lower `engineering_signal_band`), never as a hard gate (`tests\test_phase_13_integration.py::test_invalid_citation_attempts_alongside_a_valid_one_do_not_force_abstention`). Only a **total absence** of any valid citation (G8) is a hard gate.

## P. Phase 12 Integration

`[OFFICIAL SOURCE]` `JurisdictionDecision.state`/`requires_escalation` are read directly (G3/G4) — jurisdiction logic is never reimplemented, and Phase 12's own firewall decision is never overridden. A jurisdiction that is `AMBIGUOUS` or `UNKNOWN` (or missing entirely) can never become `SAFE_TO_PRESENT` (`tests\test_phase_13_integration.py::test_jurisdiction_blocked_state_cannot_be_overridden`).

## Q. Phase 11 Integration

`[OFFICIAL SOURCE]` `ClassificationResult.classification_state`/`requires_escalation` are read directly (G1/G2) — classification is never reimplemented, and Phase 11's own uncertainty (`UNKNOWN`/`AMBIGUOUS`) is never silently converted to certainty. `NEEDS_EVIDENCE` is applied conservatively per its own documented semantics (Section H).

## R. Evidence Quality

`[ENGINEERING RECOMMENDATION]` *"There is evidence"* and *"the evidence is sufficient to answer"* are kept distinct throughout: G5–G7 check whether Phase 10 itself considered the evidence sufficient (`grounding_status`); the engineering signal (Section J) then separately characterizes *how many, and how cleanly cited* the surviving evidence items are — never conflating chunk *count* with answer *correctness*. Phase 8/9 provide only integrity/provenance signals here, used honestly as exactly that.

## S. Semantic-Support Limitation

`[DEFERRED]` Phase 13 does **not** implement semantic claim/evidence entailment — no NLI model, no embedding-similarity-as-entailment, no LLM-as-judge, no semantic claim verification exists anywhere in `src\safety\` (verified by source inspection, `tests\test_phase_13_security.py`-style checks mirroring Phase 9's own boundary tests). The system knows *"this citation resolves to valid evidence"* (Phase 9's own guarantee) without ever claiming to know *"this exact sentence is fully supported by that evidence"* — that second, harder claim is explicitly out of scope, inherited unchanged from Phase 9's own semantic claim-support boundary (`docs\PHASE_09_CITATION_VALIDATION.md` Section Q).

## T. Retrieval-Score Limitation

`[OFFICIAL SOURCE]` BM25, dense similarity, RRF, and reranker scores are never read, combined, or treated as legal correctness anywhere in `src\safety\` — they do not even reach `GroundedResponse` in a form Phase 13 could access (Phase 10 does not carry raw retrieval scores forward). No incompatible score scale is ever combined without documented normalization, because no retrieval score is used at all.

## U. Synthetic-Data Handling

`[OFFICIAL SOURCE]` `SafetyDecision.synthetic` is passed through from `GroundedResponse.synthetic` unchanged — `True`/`False` when a `GroundedResponse` was supplied, `None` (never defaulted to `False`) when it was not. Synthetic status never increases the engineering signal (Section J's formula reads only citation-integrity fields, never `synthetic`) and never causes a hard-gate bypass — `tests\test_phase_13_evaluation.py::test_benchmark_synthetic_evidence_preserved` proves the flag survives to the final decision unchanged.

## V. Multilingual Behavior

`[ENGINEERING RECOMMENDATION]` No translation exists anywhere in `src\safety\`. Since Phase 13 never reads raw query/evidence text directly (only already-structured upstream decisions), Unicode handling is inherited entirely from Phase 10/11/12's own already-tested behavior. `tests\test_phase_13_multilingual.py` directly regression-tests that identical semantic content in English, Hindi, and Tamil — none containing an explicit jurisdiction keyword — all abstain identically, never differently based on script.

## W. Security

`[ENGINEERING RECOMMENDATION]` (`tests\test_phase_13_security.py`) Tested: prompt-injection-shaped query/evidence text (never produces a falsely-safe decision), malicious Evidence IDs embedded in citation markers (never resolve), wrong-typed upstream objects at the Phase 13 boundary (`TypeError`, never a silent misinterpretation), extremely long strings, Unicode/emoji, deeply nested JSON in the opaque `input_status_summary`, and malformed/tampered serialized JSON. No `eval`/`exec`/dynamic execution anywhere. No claim of comprehensive security coverage.

## X. Numeric Safety

`[ENGINEERING RECOMMENDATION]` `SafetyPolicyConfig`'s three rate/count coefficients are validated at construction: `NaN`/`Infinity`/`-Infinity` and out-of-`[0.0, 1.0]` rates are rejected (`math.isfinite` plus explicit bounds checking); non-positive citation counts are rejected. `CitationCoverageMetrics.citation_integrity_validation_rate` itself is never re-validated by Phase 13 beyond a type check, since Phase 9's own `CitationCoverageMetrics.__post_init__` already guarantees it is bounded — Phase 13 trusts, but structurally verifies the *type* of, that upstream guarantee (`tests\test_phase_13_security.py::test_malformed_citation_metrics_object_rejected_by_policy_layer`).

## Y. Determinism

`[ENGINEERING RECOMMENDATION]` `evaluator.compute_decision_id` is a SHA-256 hash over the decision's own canonical fields (`schema_version`, `input_id`, `safety_status`, `reason_code`, `engineering_signal_band`, the sorted `input_status_summary`, `config_signature`) — never a random UUID, never a timestamp. Identical `(input_id, classification_result, jurisdiction_decision, grounded_response, config)` always produces an identical `SafetyDecision`, `decision_id`, and serialized JSON (`tests\test_phase_13_determinism.py`, 10 repetitions per case).

## Z. Serialization

`[ENGINEERING RECOMMENDATION]` (`src\safety\serialize.py`) Deterministic JSON (`sort_keys=True`, fixed separators, UTF-8), mirroring Phase 9/11/12's own trusted-output convention. Full explicit field reconstruction with every invariant re-enforced on deserialization; a dedicated guard rejects a bare string passed where `hard_gate_results` (a list) is expected, to prevent it silently becoming a character-split list instead of raising. No pickle, no arbitrary/executable deserialization anywhere.

## AA. Synthetic Evaluation

`[ENGINEERING RECOMMENDATION]` (`tests\test_phase_13_evaluation.py`) Exactly the 24 implementation properties named in the Phase 13 instructions: grounded-with-valid-evidence, no-evidence, invalid-evidence (a tampered pack), invalid-citation-mixed-with-valid, unresolved-citation-only, generation abstention/failure, blocked/ambiguous jurisdiction, unresolved classification, an explicit escalation condition, a hard gate overriding a high (two-citation, full-integrity) soft signal, a weak-signal-but-still-safe case, deterministic repetition, multilingual/mixed-script input, synthetic-evidence preservation, prompt injection, malformed numeric config, serialization round-trip, policy-configuration validation, exhaustive reason-code reachability (all nine codes proven reachable in one test), and Phase 10/12 integration.

## AB. Evaluation Interpretation

`[OFFICIAL SOURCE]` **This benchmark does not measure legal accuracy, calibration, or real-world correctness, and reports no F1/accuracy/calibration figure.** Every fixture is synthetic and hand-constructed; no real evidence corpus, real legal fact, or real regulatory outcome is involved anywhere in it. A pass/fail result here demonstrates that Phase 13's own deterministic gate sequence and engineering-signal formula behave exactly as specified on these cases — it says nothing about, and does not attempt to measure, whether `engineering_signal_band` correlates with anything a human reviewer would judge as "correct" or "trustworthy" in the real world, since no such correlation study has been performed.

## AC. Known Limitations

`[ENGINEERING RECOMMENDATION]`

- `engineering_signal_band`'s three coefficients are disclosed `[ASSUMPTION]`s (Section K), not calibrated values — this is the single most important limitation of this phase, repeated here for emphasis.
- `decision_id` is not cryptographically re-verified against the decision's own fields on deserialization (mirroring Phase 12's own disclosed limitation) — nothing downstream treats it as a tamper-detection boundary.
- Phase 13 cannot distinguish *why* a hard gate fired beyond the reason code and `explanation` string — it does not, and structurally cannot, expose Phase 11/12's own richer `dimension_details`/`basis` audit trails; a caller needing that detail must inspect the upstream objects directly (which remain fully available alongside the `SafetyDecision`).
- G8's `require_at_least_one_valid_citation` policy is static per call (via `SafetyPolicyConfig`) — it is not automatically conditioned on `classification_result`'s own `evidence_requiring` intent flag, to keep the policy simple and auditable (a documented simplification, not an oversight).

## AD. Deferred Items

`[DEFERRED]`

- Any empirical validation or calibration of the engineering-signal thresholds (Section K) — would require a real, labeled benchmark that does not exist today.
- Semantic claim/evidence entailment of any kind (Section S).
- The actual human-in-the-loop workflow behind `escalation_required` (Phase 15's own scope).
- Conditioning G8 on classification-derived evidence-requiring intent (Section AC).
- Everything Phase 14 (translation/multilingual delivery) owns.

## AE. Phase 14 Boundary

`[OFFICIAL SOURCE]` Phase 13 never translates, never delivers a multilingual response, and never implements a language-generation pipeline — it consumes and produces plain structured data (`SafetyDecision`), leaving presentation and delivery entirely to later phases. No translation library, adapter, or language-generation code exists anywhere in `src\safety\`.

## AF. Acceptance Gate

`[ENGINEERING RECOMMENDATION]` Existing confidence/safety-relevant contracts (Phase 9's citation metrics, Phase 10's grounding status, Phase 11's classification state, Phase 12's jurisdiction state) are inspected and reused, with no conflicting parallel taxonomy created; a deterministic safety policy exists with a structured `SafetyDecision`; nine hard gates are implemented and always override the optional engineering signal, which is computed only after every gate passes; no fake legal probability or unsupported calibration claim exists anywhere; every heuristic threshold is explicitly `[ASSUMPTION]`-labeled; abstention and escalation are both deterministic and mutually exclusive; Phase 10's `GENERATION_FAILED`/`ABSTAINED` statuses are respected exactly; Phase 9's citation validation is reused, never reimplemented; Phase 12's firewall decision cannot be overridden; Phase 11's uncertainty cannot be silently converted to certainty; semantic entailment is not implemented; retrieval scores are never misrepresented as legal correctness; synthetic evidence remains marked synthetic; multilingual/security/numeric-safety/serialization/determinism/synthetic-evaluation tests all pass; no Phase 14+ functionality exists anywhere in `src\safety\`. **MET** — see Section AG for exact evidence.

## AG. Validation Evidence

`[ENGINEERING RECOMMENDATION]` All Phase 13 automated tests pass — model, policy, gate, integration, abstention, multilingual, security, determinism, serialization, and evaluation tests (exact counts in the Phase 13 implementation report). The synthetic evaluation suite (Section AA/AB) measures implementation correctness against hand-constructed synthetic cases only and reports no fabricated legal-accuracy, F1, or calibration figure. No real-model dependency exists anywhere in Phase 13 (100% deterministic, stdlib-plus-Phase-9/10/11/12-only), so there is no "NOT VALIDATED — model unavailable" disclosure needed here — every gap this phase discloses (Section AC) is a deliberate, honestly-labeled scope boundary or disclosed `[ASSUMPTION]`, never a validation gap in Phase 13's own code.
