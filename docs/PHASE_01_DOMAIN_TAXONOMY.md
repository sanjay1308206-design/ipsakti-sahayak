# PHASE 1 — DOMAIN TAXONOMY

Status: CONTRACT DOCUMENT (Phase 1 deliverable)
Authoritative source: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`
Governed by: `docs\MASTER_REFERENCE_LOCK.md`, `docs\DEVELOPMENT_RULES.md`, `docs\PHASE_00_SCOPE_AND_ACCEPTANCE.md`
Machine-readable counterpart: `config\domain_taxonomy.yaml`

**Scope note `[ENGINEERING RECOMMENDATION]`:** This document defines the taxonomy *vocabulary* — the fixed set of category names a later classification engine (Phase 11) will assign to a question, and the fixed set of question/intent categories the system recognizes. It does **not** implement logic that reads free text and assigns these categories; that inference logic is explicitly Phase 11's "Formulation Classification Engine" (rule engine + minimal clarifying questions). Phase 1 only fixes the vocabulary and the deterministic combination rules over *already-supplied* category values (see `docs\PHASE_01_REGULATORY_DECISION_TREE.md`).

---

## A. Purpose

`[OFFICIAL SOURCE]` Phase 1's goal, per the Master Reference roadmap: *"Turn the domain into a structured classification problem."* Its Build scope is: *"Formulation categories, intended-use questions, claims, classical/proprietary/new-drug branches, food/cosmetic/phytopharma branches, IP protection categories and ABS/TK concepts."* Its acceptance gate: *"A test set can be classified without an LLM deciding everything."*

`[ENGINEERING RECOMMENDATION]` This taxonomy exists so that later phases — jurisdiction firewall (12), evidence retrieval (5–7), citation validation (8–9), grounded generation (10), the classification engine itself (11), confidence/safety (13) — all consume the *same* fixed vocabulary rather than each phase inventing its own category names.

## B. Taxonomy Design Principles

`[ENGINEERING RECOMMENDATION]`

1. **Preserve, don't refine.** Where the Master Reference names a category at a given granularity (e.g., "classical/proprietary/new-drug", "food/cosmetic/phytopharma"), this taxonomy uses exactly that granularity. No finer legal subcategory is invented.
2. **Every category is traceable.** Every category carries one source-discipline label (Section M).
3. **Every dimension has an explicit "undetermined" state.** No dimension forces a value when the input doesn't support one.
4. **Every dimension has an explicit "conflicting" state where relevant.** Multiple simultaneous matches are a distinct, named state — not silently resolved by picking one.
5. **The vocabulary is closed and testable.** Test suites enforce that no category outside the fixed enum can enter a classification result (Phase 1's answer to "no unsupported regulatory terminology").
6. **Engineering categories are never legal categories.** A category name here is a routing/workflow label, not a claim about what the law says. See Section L and `docs\PHASE_01_REGULATORY_DECISION_TREE.md` for the safety boundary this implies.

## C. Product/Formulation Classification Dimensions

`[OFFICIAL SOURCE]` Three dimensions, each derived from a specific Master Reference phrase — no finer subcategories added:

### C.1 Regulatory Track

Source phrase: *"classical/proprietary/new-drug branches, food/cosmetic/phytopharma branches"* (Phase 1 Build) and *"Ayurveda Aahara has its own FSSAI regulatory framework, while CDSCO separately publishes traditional-drug rules/material. The classifier must therefore distinguish food/Ayurveda-Aahara from Ayurvedic drugs"* (Authoritative Source Strategy).

| ID | Category | Source |
|---|---|---|
| RT-01 | `CLASSICAL_AYURVEDIC_DRUG` | `[OFFICIAL SOURCE]` — named branch |
| RT-02 | `PROPRIETARY_AYURVEDIC_DRUG` | `[OFFICIAL SOURCE]` — named branch |
| RT-03 | `NEW_AYURVEDIC_DRUG` | `[OFFICIAL SOURCE]` — named branch |
| RT-04 | `AYURVEDA_AAHARA_FOOD` | `[OFFICIAL SOURCE]` — named branch + explicit food/drug distinction |
| RT-05 | `COSMETIC` | `[OFFICIAL SOURCE]` — named branch |
| RT-06 | `PHYTOPHARMACEUTICAL` | `[OFFICIAL SOURCE]` — named branch |
| RT-07 | `UNDETERMINED` | `[ENGINEERING RECOMMENDATION]` — no branch signaled by input |
| RT-08 | `CONFLICTING` | `[ENGINEERING RECOMMENDATION]` — more than one branch signaled, no deterministic tiebreak |

`[ASSUMPTION]` The Master Reference names these six branches but does not define the *legal criteria* that distinguish one from another (e.g., what exactly makes a formulation "proprietary" vs. "classical"). Those criteria are not invented here; they are `[DEFERRED]` to Phase 2 (Authority Matrix & Corpus Lock, which will register the actual CDSCO/FSSAI source texts) and Phase 11 (the classification engine that applies them). Phase 1 fixes only the *names*.

### C.2 IP Protection Category

Source phrase: IP India row of the Authoritative Source Strategy — *"Patents, trademarks, designs, GI and related public search/e-services"* — plus Phase 1 Build's *"IP protection categories."*

| ID | Category | Source |
|---|---|---|
| IP-01 | `PATENT` | `[OFFICIAL SOURCE]` |
| IP-02 | `TRADEMARK` | `[OFFICIAL SOURCE]` |
| IP-03 | `DESIGN` | `[OFFICIAL SOURCE]` |
| IP-04 | `GEOGRAPHICAL_INDICATION` | `[OFFICIAL SOURCE]` — "GI" expanded to its standard full term |
| IP-05 | `NONE` | `[ENGINEERING RECOMMENDATION]` — question is not IP-protection-related |
| IP-06 | `UNDETERMINED` | `[ENGINEERING RECOMMENDATION]` — insufficient input to tell |

### C.3 ABS/TK Relation

Source phrase: Phase 1 Build's *"ABS/TK concepts"*, and the WIPO GRATK reference: *"WIPO resource center for the 2024 treaty on IP, genetic resources and associated traditional knowledge."*

| ID | Category | Source |
|---|---|---|
| ATK-01 | `TRADITIONAL_KNOWLEDGE_RELATED` | `[OFFICIAL SOURCE]` |
| ATK-02 | `ACCESS_AND_BENEFIT_SHARING_RELATED` | `[OFFICIAL SOURCE]` |
| ATK-03 | `NOT_RELATED` | `[ENGINEERING RECOMMENDATION]` |
| ATK-04 | `UNDETERMINED` | `[ENGINEERING RECOMMENDATION]` |

## D. Regulatory Question Taxonomy

`[OFFICIAL SOURCE]` Derived 1:1 from the "Source family" column of the Master Reference's Authoritative Source Strategy table (`MASTER_REFERENCE_LOCK.md` Section B / Master Reference page 3). Each question category names the source family that would own the answer — it is a *routing* taxonomy, not a legal one.

| ID | Category | Corresponds to source family |
|---|---|---|
| RQ-01 | `INDIA_LEGISLATIVE` | India Code |
| RQ-02 | `IP_REGISTRATION_AND_SEARCH` | IP India |
| RQ-03 | `AYUSH_POLICY` | Ministry of Ayush |
| RQ-04 | `TRADITIONAL_DRUG_REGULATION` | CDSCO / Drugs & Cosmetics |
| RQ-05 | `AYURVEDA_AAHARA_FOOD_LAW` | FSSAI |
| RQ-06 | `INTERNATIONAL_IP_TREATY` | WIPO / WIPO Lex |
| RQ-07 | `TRADITIONAL_KNOWLEDGE_DATABASE` | TKDL (authorized/public material only) |
| RQ-08 | `UNDETERMINED` | `[ENGINEERING RECOMMENDATION]` — question does not map to a registered source family |

`[ENGINEERING RECOMMENDATION]` Bhashini is intentionally **excluded** from this taxonomy — it is a translation/language service adapter (Phase 14), not a source of regulatory answers, per its row in the Authoritative Source Strategy table ("Multilingual translation/language infrastructure through an adapter").

## E. User Intent Taxonomy

`[ENGINEERING RECOMMENDATION]` The Master Reference names "intended-use questions" as part of Phase 1's build scope but does not enumerate specific intent categories — this dimension is an engineering derivation from the system's stated purpose (`docs\PHASE_00_SCOPE_AND_ACCEPTANCE.md` Section 3/4), not a quotation from the source.

| ID | Category | Description |
|---|---|---|
| UI-01 | `DETERMINE_REGULATORY_CLASSIFICATION` | "What regulatory category does my formulation/product fall under?" |
| UI-02 | `DETERMINE_IP_PROTECTION_PATHWAY` | "How can this be protected as IP / what protection applies?" |
| UI-03 | `CHECK_COMPLIANCE_REQUIREMENT` | "What rules/requirements apply to me given a known category?" |
| UI-04 | `LOOKUP_AUTHORITATIVE_SOURCE` | "What does a specific law/regulation/notification say?" |
| UI-05 | `GENERAL_INFORMATION_REQUEST` | Informational question not requiring an evidence-backed regulatory conclusion. |
| UI-06 | `OUT_OF_SCOPE_OR_UNSUPPORTED` | Falls outside the locked source strategy / domain entirely. |
| UI-07 | `AMBIGUOUS_INTENT` | Input signals more than one intent with no deterministic tiebreak. |
| UI-08 | `UNDETERMINED` | No intent signal supplied. |

`[ENGINEERING RECOMMENDATION]` `UI-01`, `UI-02`, `UI-03`, `UI-04` are the "evidence-requiring" intents — a regulatory conclusion under these intents must be evidence-backed (Section G, and `docs\PHASE_01_REGULATORY_DECISION_TREE.md` Rule R7). `UI-05` and `UI-06` do not require evidence to reach a terminal state.

## F. Jurisdiction-Sensitive Dimensions

`[OFFICIAL SOURCE]` Directly tied to the Jurisdiction Firewall lock (`MASTER_REFERENCE_LOCK.md` Section E): *"India and international corpora should be separated at retrieval time, not merely mentioned in the prompt."* Phase 1 defines only the **input values** this dimension can take; the actual firewall (separate indices, leakage testing) is Phase 12's responsibility, not implemented here.

| ID | Category | Source |
|---|---|---|
| JX-01 | `INDIA` | `[OFFICIAL SOURCE]` |
| JX-02 | `INTERNATIONAL` | `[OFFICIAL SOURCE]` |
| JX-03 | `BOTH` | `[ENGINEERING RECOMMENDATION]` — question legitimately spans both |
| JX-04 | `UNSPECIFIED` | `[ENGINEERING RECOMMENDATION]` — not yet provided by the user |

## G. Evidence-Dependent Dimensions

`[ENGINEERING RECOMMENDATION]` These states describe whether authoritative evidence (Phase 2+ corpus) backs a conclusion. **Honesty note:** because Phases 2–10 have not been implemented, no real evidence corpus exists yet anywhere in this repository. Any classification produced today, for an evidence-requiring intent, is therefore always `NOT_YET_EVALUATED` in practice — this is expected and correct at this stage of the project, not a defect.

| ID | Category | Meaning |
|---|---|---|
| EV-01 | `SUFFICIENT_EVIDENCE` | Retrieved evidence (once Phases 2–9 exist) supports a defensible answer. |
| EV-02 | `INSUFFICIENT_EVIDENCE` | Evidence was checked but does not support a confident answer. |
| EV-03 | `NO_EVIDENCE_AVAILABLE` | No matching evidence exists in the corpus at all. |
| EV-04 | `NOT_YET_EVALUATED` | No evidence check has been performed (the only truthful value obtainable today, prior to Phase 2). |

## H. Unknown / Ambiguous States

`[ENGINEERING RECOMMENDATION]` Overall classification-result states (distinct from the per-dimension `UNDETERMINED`/`CONFLICTING` values above — this is the *terminal* state of the whole decision tree, see `docs\PHASE_01_REGULATORY_DECISION_TREE.md`):

| ID | State | Meaning |
|---|---|---|
| CS-01 | `KNOWN` | All required input dimensions were supplied, unambiguous, and recognized. **This is an engineering-routing conclusion, never a legal determination** (Section L). |
| CS-02 | `UNKNOWN` | A required input dimension is missing or unrecognized; the tree could not proceed. |
| CS-03 | `AMBIGUOUS` | Input dimensions conflict or map to more than one category with no deterministic tiebreak. |
| CS-04 | `NEEDS_EVIDENCE` | Inputs are complete and unambiguous, but the intent requires an evidence-backed answer and evidence has not been confirmed sufficient. |

No input is ever forced into `KNOWN`. See the decision tree's rule ordering for how each state is reached.

## I. Classification Output Model

`[ENGINEERING RECOMMENDATION]` The full output schema is defined machine-readably in `config\classification_contract.yaml` and summarized here:

`input_id`, `user_intent`, `formulation_classification` (`regulatory_track`, `ip_protection_category`, `abs_tk_relation`), `regulatory_question_type`, `jurisdiction_input`, `evidence_state`, `classification_state`, `reason_codes`, `explanation`, `requires_evidence`, `requires_escalation`, `basis`, `disclaimer`, `provenance`.

This mirrors the Final Architecture Decision Lock's Classification principle: *"Output should be provisional classification, basis, missing information and human-review status."* (`basis` + `reason_codes` = basis/missing information; `requires_escalation` = human-review status; `classification_state` is explicitly "provisional" — see Section L.)

## J. Explainability Requirements

`[ENGINEERING RECOMMENDATION]`

1. Every classification result must include `reason_codes` — the specific rule(s) that determined the outcome, not just the outcome itself.
2. Every classification result must include `basis` — the taxonomy/rule IDs consulted, for audit and traceability.
3. Every classification result must include a non-empty `explanation` string a human can read without consulting source code.
4. No classification result may be produced by an unexplainable/black-box step (e.g., no LLM call, no opaque ML model) — this is enforced by keeping the decision tree a fixed, ordered, deterministic rule list (`docs\PHASE_01_REGULATORY_DECISION_TREE.md`).

## K. Examples

`[OUR ENHANCEMENT]` — **synthetic illustrative examples only**, not real regulatory facts, not drawn from any actual user query or actual formulation:

**Example 1 — `NEEDS_EVIDENCE`:** A synthetic caller supplies `user_intent=DETERMINE_REGULATORY_CLASSIFICATION`, `jurisdiction=INDIA`, `formulation_regulatory_track=AYURVEDA_AAHARA_FOOD`, `regulatory_question_type=AYURVEDA_AAHARA_FOOD_LAW`, `evidence_state=NOT_YET_EVALUATED`. All inputs are complete and unambiguous, but the intent requires an evidence-backed answer and no evidence has been checked (expected today, pre-Phase-2) → result: `NEEDS_EVIDENCE`.

**Example 2 — `UNKNOWN`:** A synthetic caller supplies `user_intent=DETERMINE_REGULATORY_CLASSIFICATION` but no jurisdiction → result: `UNKNOWN`, `reason_codes=[MISSING_JURISDICTION]`.

**Example 3 — `AMBIGUOUS`:** A synthetic caller's formulation description matches signals for both `AYURVEDA_AAHARA_FOOD` and `PHYTOPHARMACEUTICAL` with no deterministic tiebreaker → `formulation_regulatory_track=CONFLICTING` → result: `AMBIGUOUS`, `reason_codes=[CONFLICTING_FORMULATION_SIGNALS]`.

**Example 4 — `KNOWN` (non-evidence-requiring):** A synthetic caller supplies `user_intent=GENERAL_INFORMATION_REQUEST`, `jurisdiction=INDIA`, `regulatory_question_type=AYUSH_POLICY` → all required fields present and unambiguous, intent does not require evidence → result: `KNOWN`. **Even here, the disclaimer field is always populated — `KNOWN` never means "legally certain."**

## L. Explicit Non-Goals

`[OFFICIAL SOURCE]` / `[ENGINEERING RECOMMENDATION]`

- This taxonomy is **not** a legal classification system. A `KNOWN` result is an engineering routing conclusion (which downstream pipeline branch applies), never a legal determination — consistent with the Master Reference's explicit instruction: *"Do not call the system legal advice; make it evidence-grounded decision support with escalation."*
- Phase 1 does **not** implement the logic that reads free-text user input and assigns taxonomy values — that is Phase 11.
- Phase 1 does **not** implement evidence retrieval, so `evidence_state` can only ever be truthfully reported as `NOT_YET_EVALUATED` in this repository today.
- Phase 1 does **not** implement the jurisdiction firewall (index separation, leakage testing) — only the `jurisdiction` input vocabulary.
- Phase 1 introduces **no new regulatory category names** beyond what Section C–F trace to the Master Reference or explicitly mark as engineering additions.

## M. Source/Evidence Audit

`[ENGINEERING RECOMMENDATION]` Self-audit performed for this document (see Phase 1 implementation report for the full repository-wide audit):

- Every category table above carries a per-row or per-section source label.
- No statute number, section number, government order number, or citation was introduced anywhere in this document.
- No government authority name was introduced beyond those already named in the Master Reference's Authoritative Source Strategy table (India Code, IP India, Ministry of Ayush, CDSCO, FSSAI, WIPO/WIPO Lex, TKDL).
- All `[ASSUMPTION]` and `[DEFERRED]` markers above identify genuinely open questions (legal criteria distinguishing regulatory-track branches; real evidence availability) rather than treating them as settled.
