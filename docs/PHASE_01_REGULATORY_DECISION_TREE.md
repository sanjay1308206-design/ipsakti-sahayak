# PHASE 1 — REGULATORY DECISION TREE

Status: CONTRACT DOCUMENT (Phase 1 deliverable)
Authoritative source: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`
Companion: `docs\PHASE_01_DOMAIN_TAXONOMY.md` (defines every enum value referenced below)
Machine-readable counterpart: `config\regulatory_decision_tree.yaml`

---

## 1. Purpose

`[ENGINEERING RECOMMENDATION]` This document defines the deterministic, ordered rule set that combines the taxonomy dimensions defined in `docs\PHASE_01_DOMAIN_TAXONOMY.md` into one of the four classification states (`KNOWN`, `UNKNOWN`, `AMBIGUOUS`, `NEEDS_EVIDENCE`). It operationalizes the Final Architecture Decision Lock's Classification principle: *"Use a deterministic, explainable formulation-classification flow with structured questions. Output should be provisional classification, basis, missing information and human-review status."*

**This tree does not infer taxonomy values from free text.** It assumes each input field has already been supplied as a clean enum value (by a caller, or in later phases, by Phase 11's classification engine). Phase 1 defines *how those values combine*, not how they are extracted from raw language.

## 2. Design Requirements

`[ENGINEERING RECOMMENDATION]` Per the instruction to keep the tree:

- **Deterministic:** the same input always produces the same output; no randomness, no model inference, no external calls.
- **Explainable:** every result carries the specific rule ID and reason code that produced it.
- **Ordered:** rules are evaluated in a fixed priority order; the first matching rule wins (a strict decision list, not an unordered rule set with conflict resolution).
- **Testable:** every rule has at least one positive test (the rule fires as designed) and the tree as a whole has negative tests (see `tests\test_phase_01_decision_tree.py`).
- **Conservative under uncertainty:** any missing, conflicting, or unverified input routes to `UNKNOWN`, `AMBIGUOUS`, or `NEEDS_EVIDENCE` — never guessed into `KNOWN`.

## 3. Input Fields

`[ENGINEERING RECOMMENDATION]` All values are drawn from the enums fixed in `docs\PHASE_01_DOMAIN_TAXONOMY.md`:

| Field | Domain | Section |
|---|---|---|
| `user_intent` | UI-01..UI-08 | Taxonomy §E |
| `formulation_regulatory_track` | RT-01..RT-08 | Taxonomy §C.1 |
| `jurisdiction` | JX-01..JX-04 | Taxonomy §F |
| `regulatory_question_type` | RQ-01..RQ-08 | Taxonomy §D |
| `evidence_state` | EV-01..EV-04 | Taxonomy §G |

`[ENGINEERING RECOMMENDATION]` **Evidence-requiring intents** (must be evidence-backed to reach `KNOWN`): `DETERMINE_REGULATORY_CLASSIFICATION`, `DETERMINE_IP_PROTECTION_PATHWAY`, `CHECK_COMPLIANCE_REQUIREMENT`, `LOOKUP_AUTHORITATIVE_SOURCE` (i.e., `UI-01`–`UI-04`).

## 4. Branches (Conceptual)

`[ENGINEERING RECOMMENDATION]` The seven requested branch families map onto the rule stages below:

1. **User intent** → Rules R1, R5.
2. **Product/formulation information** → Rules R3, R4.
3. **Jurisdiction** → Rule R2.
4. **Regulatory-question type** → Rule R6.
5. **Evidence availability** → Rule R7.
6. **Classification result** → Rule R8 (`KNOWN`) or the terminal state of whichever rule fired first.
7. **Escalation/uncertainty result** → derived from the terminal `classification_state` (Section 6).

## 5. Ordered Deterministic Rules

`[ENGINEERING RECOMMENDATION]` Evaluated **in this exact order**; the first matching rule is terminal (short-circuit — later rules are not evaluated once one matches). This ordering is itself part of the contract and is tested (`docs` §5 rule order = `config\regulatory_decision_tree.yaml` `stages[].rule_id` order = `tests\_decision_tree_reference_impl.py` evaluation order).

| Order | Rule ID | Name | Fires when | Result state | Reason code |
|---|---|---|---|---|---|
| 1 | R1 | `MISSING_USER_INTENT` | `user_intent == UNDETERMINED` | `UNKNOWN` | `MISSING_USER_INTENT` |
| 2 | R2 | `MISSING_JURISDICTION` | `jurisdiction == UNSPECIFIED` | `UNKNOWN` | `MISSING_JURISDICTION` |
| 3 | R3 | `MISSING_FORMULATION_INFO` | `user_intent` is evidence-requiring AND `formulation_regulatory_track == UNDETERMINED` | `UNKNOWN` | `MISSING_FORMULATION_INFO` |
| 4 | R4 | `CONFLICTING_FORMULATION_SIGNALS` | `formulation_regulatory_track == CONFLICTING` | `AMBIGUOUS` | `CONFLICTING_FORMULATION_SIGNALS` |
| 5 | R5 | `AMBIGUOUS_USER_INTENT` | `user_intent == AMBIGUOUS_INTENT` | `AMBIGUOUS` | `AMBIGUOUS_USER_INTENT` |
| 6 | R6 | `UNRECOGNIZED_REGULATORY_QUESTION_TYPE` | `regulatory_question_type == UNDETERMINED` (or not a member of RQ-01..RQ-08) | `UNKNOWN` | `UNRECOGNIZED_REGULATORY_QUESTION_TYPE` |
| 7 | R7 | `EVIDENCE_NOT_AVAILABLE` | `user_intent` is evidence-requiring AND `evidence_state != SUFFICIENT_EVIDENCE` | `NEEDS_EVIDENCE` | `EVIDENCE_NOT_AVAILABLE` |
| 8 | R8 | `DEFAULT_KNOWN` | none of the above fired | `KNOWN` | *(none)* |

`[ENGINEERING RECOMMENDATION]` Rule R6 additionally covers "unsupported/unknown category" by rejecting any `regulatory_question_type` value outside the fixed RQ-01..RQ-08 vocabulary — this is enforced both here (as an explicit rule) and structurally in `config\classification_contract.yaml` (closed enum, no free text).

## 6. Escalation / Uncertainty Derivation

`[ENGINEERING RECOMMENDATION]`, applied after a terminal state is reached (not a separate rule stage — a direct function of the terminal state, per the Final Architecture Decision Lock's "human-review status" requirement):

- `requires_evidence = True` **iff** `classification_state == NEEDS_EVIDENCE`.
- `requires_escalation = True` **iff** `classification_state == AMBIGUOUS`.
- `UNKNOWN` sets neither flag — it signals the caller should supply the missing input, not that a human must intervene. (Phase 15's actual human-in-the-loop workflow will refine this distinction; Phase 1 only fixes the flag semantics.)
- `KNOWN` sets neither flag, but **always** carries the fixed `disclaimer` field (Section 7) — `KNOWN` is never escalation-free because it is "legally settled"; it is escalation-free only because the *engineering routing* step found no missing/conflicting/unverified input.

## 7. Safety Boundary (binding on every rule)

`[OFFICIAL SOURCE]` / `[ENGINEERING RECOMMENDATION]`, carried forward from `docs\PHASE_00_SCOPE_AND_ACCEPTANCE.md` Section 8:

- No rule may output a state implying legal certainty. `KNOWN` means "the engineering taxonomy routing was unambiguous," never "the legal answer is settled."
- Every classification result — including `KNOWN` — carries a non-empty `disclaimer` field (fixed text, defined in `config\classification_contract.yaml`) stating the result is not legal advice or a legal determination.
- No rule fabricates a regulation, citation, or authority name to justify a result; every reason code traces to an input-completeness or input-consistency check only.
- Where evidence is required and not confirmed sufficient, the tree **always** returns `NEEDS_EVIDENCE` rather than guessing — this cannot be bypassed by any rule ordering, since R7 is evaluated before the default `KNOWN` rule (R8).

## 8. Terminal States

`[OFFICIAL SOURCE — required by this Phase 1 instruction]` Exactly four terminal states exist, no others: `KNOWN`, `UNKNOWN`, `AMBIGUOUS`, `NEEDS_EVIDENCE` (Taxonomy §H, CS-01..CS-04). Every rule maps to exactly one of these four; the tree cannot produce any other output value (enforced structurally and by test).

## 9. Non-Goals

`[ENGINEERING RECOMMENDATION]`

- No LLM call, no external API call, no model inference of any kind occurs in this decision tree — it is pure, deterministic, input-to-output mapping over already-supplied enum values.
- No retrieval, embedding, or evidence-store lookup happens here — `evidence_state` is treated as an opaque input value, not computed by this tree.
- No jurisdiction firewall enforcement (index separation) happens here — `jurisdiction` is treated as an opaque input value.
