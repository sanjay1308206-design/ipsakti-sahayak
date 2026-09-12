# PHASE 11 — FORMULATION CLASSIFICATION ENGINE

Status: CONTRACT + IMPLEMENTATION DOCUMENT (Phase 11 deliverable)
Authoritative source: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`
Governed by: `docs\MASTER_REFERENCE_LOCK.md`, `docs\DEVELOPMENT_RULES.md`, `docs\PHASE_01_DOMAIN_TAXONOMY.md`, `docs\PHASE_01_REGULATORY_DECISION_TREE.md`
Machine-readable counterpart: `config\formulation_classification_contract.yaml`
Implementation: `src\classification\models.py`, `rules.py`, `classifier.py`, `serialize.py`

**Phase 1 fixed the vocabulary and the combination rules. Phase 11 is the missing piece between them and raw text.** Phase 1's own documentation states this explicitly: *"Phase 1 does not implement the logic that reads free-text user input and assigns taxonomy values — that is Phase 11."* This phase implements exactly that piece, and nothing else — it never redefines a category, never changes a rule's meaning, and never makes the jurisdiction, evidence-retrieval, or legal-conclusion decisions that belong to later phases.

---

## A. Phase Objective

`[OFFICIAL SOURCE]` The Master Reference's Final Architecture Decision Lock names the Classification principle: *"Use a deterministic, explainable formulation-classification flow with structured questions. Output should be provisional classification, basis, missing information and human-review status."* `docs\PHASE_TRACKER.md`'s CAP-11 entry states the goal: *"Deterministic rule engine + minimal clarifying questions producing a structured classification result."* Phase 11 implements the deterministic rule engine that reads raw/structured caller input and produces that structured result, by combining Phase 1's already-fixed taxonomy and decision tree — never by inventing a second one.

## B. Scope

In scope: a minimal `ClassificationInput` model; deterministic, literal keyword-based extraction of every Phase 1 taxonomy dimension from that input; a production-facing, documented duplicate of Phase 1's decision-tree evaluator; a `ClassificationResult` that exactly satisfies `config\classification_contract.yaml` plus an additional, Phase-11-owned `dimension_details` explainability structure; deterministic serialization.

Out of scope (no code for any of these exists anywhere in `src\classification\`): jurisdiction firewall routing/enforcement, evidence retrieval of any kind, confidence scoring beyond Phase 1's own boolean escalation flags, translation, human-escalation workflow, a red-team/evaluation framework beyond this phase's own tests, backend productization, a frontend, project-wide security hardening, deployment, observability, CI/CD, or production validation.

## C. Non-Scope

`[ENGINEERING RECOMMENDATION]` Explicitly, Phase 11 does not: select the India vs. international corpus; allow or block a jurisdiction; decide governing law; declare a regulatory authority applicable; determine current legal status or legal compliance; issue legal advice; or perform final regulatory interpretation. `jurisdiction_input` is produced exactly as Phase 1's taxonomy already treats it — an opaque routing value, never a firewall decision (Phase 12's exclusive scope, `docs\PHASE_01_DOMAIN_TAXONOMY.md` Section F).

## D. Existing Phase 1 Contracts Reused

`[OFFICIAL SOURCE]` Three files, reused verbatim, never redesigned:

1. `config\domain_taxonomy.yaml` (`taxonomy_version: "1.0.0"`) — every enum value for `regulatory_track`, `ip_protection_category`, `abs_tk_relation`, `regulatory_question_categories`, `user_intent_categories`, `jurisdiction_inputs`, `evidence_states`, `classification_states`.
2. `config\regulatory_decision_tree.yaml` (`tree_version: "1.0.0"`) — the exact 8 ordered rules (R1–R8) that combine already-supplied enum values into a terminal `classification_state`.
3. `config\classification_contract.yaml` (`contract_version: "1.0.0"`) — the output schema Phase 11's result must conform to.

Phase 1's own test-only reference tree evaluator, `tests\_decision_tree_reference_impl.py`, is explicitly *not* production code (its own docstring: *"This is NOT the Phase 11 'Formulation Classification Engine'"*). Per the explicit instruction to reuse its semantics while documenting any necessary duplication, `src\classification\rules.evaluate_tree` is a production-facing, line-for-line semantic duplicate of it — `tests\test_phase_11_rules.py` cross-checks the two directly, on a large synthetic input grid, to guarantee they never drift apart.

## E. Classification Dimensions

`[OFFICIAL SOURCE]` Exactly the dimensions Phase 1 already established — no dimension is added:

| Dimension | Taxonomy source | Feeds the decision tree? |
|---|---|---|
| `user_intent` | `domain_taxonomy.yaml` §user_intent_categories | Yes (R1, R3, R5, R7) |
| `regulatory_track` | §regulatory_track | Yes, as `formulation_regulatory_track` (R3, R4) |
| `ip_protection_category` | §ip_protection_category | **No** — output-only enrichment |
| `abs_tk_relation` | §abs_tk_relation | **No** — output-only enrichment |
| `regulatory_question_type` | §regulatory_question_categories | Yes (R6) |
| `jurisdiction_input` | §jurisdiction_inputs | Yes, as `jurisdiction` (R2) |
| `evidence_state` | §evidence_states | Yes (R7) — opaque passthrough, never computed here (Section N) |

`ip_protection_category` and `abs_tk_relation` are classified independently and included in the output, but — per Phase 1's own decision-tree contract, left completely unmodified — do **not** themselves gate `classification_state`; only the five tree-input fields above do. This is a deliberate, pre-existing Phase 1 design choice, not something Phase 11 introduces or "fixes."

## F. Classification States

`[OFFICIAL SOURCE]` Exactly Phase 1's four closed terminal states — `KNOWN`, `UNKNOWN`, `AMBIGUOUS`, `NEEDS_EVIDENCE` (`classification.models.CLASSIFICATION_STATES`) — no fifth value is ever introduced. `[OUR ENHANCEMENT]` Phase 11 additionally reuses this SAME vocabulary, minus `NEEDS_EVIDENCE`, as the **per-dimension** explainability state (`classification.models.DIMENSION_STATES = {KNOWN, UNKNOWN, AMBIGUOUS}`) — see Section K for why `NEEDS_EVIDENCE` is deliberately excluded at that level.

## G. Input Contract

`[ENGINEERING RECOMMENDATION]` `classification.models.ClassificationInput`: `input_id` (str, required), `raw_query` (str, required — may be empty), `formulation_description` (`Optional[str]`), `evidence_state` (`Optional[str]`, opaque passthrough, Section N). Deliberately minimal: only the two free-text fields explicitly named in the Phase 11 instructions' own "Possible Inputs" list are implemented — no speculative `ingredients`/`dosage_form`/`manufacturing_context`/`market_context` schema, since Phase 1's contract does not require them and the instructions explicitly warn against "a giant speculative schema." Both dimensions are extracted from the *combination* of `raw_query` and `formulation_description` (concatenated, lowercased) — never from one exclusively.

## H. Output Contract

`[OFFICIAL SOURCE]`/`[ENGINEERING RECOMMENDATION]` `classification.models.ClassificationResult` carries every field `config\classification_contract.yaml` requires — `schema_version`, `input_id`, `user_intent`, `formulation_classification` (`regulatory_track`/`ip_protection_category`/`abs_tk_relation`), `regulatory_question_type`, `jurisdiction_input`, `evidence_state`, `classification_state`, `reason_codes`, `explanation`, `requires_evidence`, `requires_escalation`, `basis`, `disclaimer`, `provenance` — with every enum value a genuine member of its Phase 1 vocabulary (SAFE-06) and every derived-flag invariant enforced at construction (SAFE-04/05). Additionally, `dimension_details: dict[str, DimensionResult]` — a Phase-11-owned addition, never a replacement for the flat contract fields — carries the value/state/reason/matched-rule breakdown per dimension (Section K).

## I. Rule Engine

`[ENGINEERING RECOMMENDATION]` Two layers (`src\classification\rules.py`):

1. **Extraction rules** (`REGULATORY_TRACK_KEYWORDS`, `IP_PROTECTION_KEYWORDS`, `ABS_TK_KEYWORDS`, `REGULATORY_QUESTION_TYPE_KEYWORDS`, `USER_INTENT_KEYWORDS`, plus dedicated jurisdiction logic) — ordered, inspectable Python tuples of `(taxonomy_id, category_name, keyword_phrases)`. Deliberately literal and narrow (Section P) — a caller must name the category itself (or an exact Master-Reference synonym, e.g. "Aahara") for a match; nothing is inferred from a product name, ingredient list, or general knowledge.
2. **The decision tree** (`evaluate_tree`) — the exact, ordered R1→R8 evaluation from Section D, first-match-wins, ordered/deterministic/inspectable/testable per Phase 1's own design requirements (`docs\PHASE_01_REGULATORY_DECISION_TREE.md` Section 2), never silently re-ordered or re-weighted.

## J. Deterministic Behavior

`[ENGINEERING RECOMMENDATION]` No LLM, no embeddings, no FAISS, no external API, no network access, and no randomness exist anywhere in `src\classification\`. Given identical `(ClassificationInput, ClassificationConfig)`, `classify()` always returns an identical `ClassificationResult` (`tests\test_phase_11_determinism.py`, 10 repetitions per case). An LLM-assisted classifier was considered and explicitly **not** built: the instructions require stopping and documenting the reason if one seems necessary, and no such necessity was found — literal keyword matching plus Phase 1's own fixed rule tree is sufficient to satisfy CAP-11's acceptance criterion (a test set can be classified without an LLM deciding everything) and keeps the whole engine auditable end to end. `[DEFERRED]` An LLM-assisted extraction layer remains a possible future enhancement, but only if evidence-based evaluation against this deterministic baseline someday justifies it (per the Final Decision Lock's own "new technologies must earn their place" principle) — not built here.

## K. Explainability / Reason Codes

`[ENGINEERING RECOMMENDATION]` Two levels, never conflated:

- **Tree-level** `reason_codes` (Section H) — exactly Phase 1's own rule-derived codes (e.g. `["MISSING_JURISDICTION"]`), empty only when `classification_state == KNOWN`, per `config\classification_contract.yaml`'s own description.
- **Dimension-level** `DimensionResult` (`dimension`, `value`, `state`, `matched_rule_ids`, `reason`) — one per classified dimension, in `ClassificationResult.dimension_details`. `matched_rule_ids` names the specific taxonomy/keyword-rule IDs consulted (e.g. `["RT-01"]`, or `["RT-01", "RT-06"]` for a conflict) — an observable, rule-level fact, never a hidden chain-of-thought. `NEEDS_EVIDENCE` is structurally excluded from `DIMENSION_STATES` (Section F) because no single text-extraction step can independently know "evidence is needed" — that is purely an emergent property of the overall tree (R7, driven by `user_intent` + `evidence_state` together), never of one dimension's own keyword match.

`explanation` (a required top-level string) is assembled purely from these same observable facts — the fired rule, its reason code(s), and every dimension's own value/state/reason — never from anything not already present in `dimension_details`/`reason_codes`.

## L. Ambiguity Handling

`[OFFICIAL SOURCE]`/`[ENGINEERING RECOMMENDATION]` The classifier never forces a value when input supports multiple plausible categories. Three distinct resolutions, depending on what Phase 1's own taxonomy defines for that dimension:

- `regulatory_track`: zero matches → `UNDETERMINED` (RT-07); exactly one → that value; two or more → `CONFLICTING` (RT-08, feeds tree rule R4 → `AMBIGUOUS`).
- `user_intent`: zero matches on a non-empty query → `GENERAL_INFORMATION_REQUEST` (UI-05, the taxonomy's own non-evidence-requiring default, Section M); zero matches on an empty query → `UNDETERMINED` (UI-08); exactly one → that value; two or more → `AMBIGUOUS_INTENT` (UI-07, feeds tree rule R5 → `AMBIGUOUS`).
- `ip_protection_category` / `abs_tk_relation` / `regulatory_question_type`: these have **no** conflicting/ambiguous member in Phase 1's taxonomy at all — two or more matches fall back to that dimension's own `UNDETERMINED` value, never an arbitrarily-chosen match and never an invented new state (`tests\test_phase_11_ambiguity.py::test_dimension_without_own_conflicting_state_falls_back_to_undetermined_not_a_guess`).
- `jurisdiction_input`: matching both India and international signals resolves to `BOTH` (JX-03) — this is a legitimate, already-defined *resolved* value in Phase 1's own taxonomy, not an unresolved conflict.

Every ambiguity resolution records the specific conflicting rule IDs in `matched_rule_ids`, never silently.

## M. Unknown vs. Needs Evidence

`[OFFICIAL SOURCE]` Preserved exactly as Phase 1 defines it (`docs\PHASE_01_DOMAIN_TAXONOMY.md` Section H, `docs\PHASE_01_REGULATORY_DECISION_TREE.md` Section 7): `UNKNOWN` means a required input dimension is missing or unrecognized — the tree could not even proceed to the evidence question. `NEEDS_EVIDENCE` means every input dimension is complete and unambiguous, and *only* evidence remains outstanding. These are never collapsed into each other — `tests\test_phase_11_ambiguity.py` tests both directions explicitly (missing jurisdiction with an otherwise-complete evidence-requiring query stays `UNKNOWN`, never `NEEDS_EVIDENCE`; a fully complete but evidence-unconfirmed query reaches `NEEDS_EVIDENCE`, never `UNKNOWN`).

## N. Evidence Boundary

`[ENGINEERING RECOMMENDATION]` Phase 11 never retrieves evidence itself — no corpus query, no call into `src\retrieval\`/`src\evidence\`/`src\citation\`/`src\generation\`, no web search, no query to India Code, IP India, WIPO, CDSCO, FSSAI, Ministry of Ayush, or TKDL exists anywhere in `src\classification\` (verified by import-audit in `tests\test_phase_11_regression.py`). `evidence_state`, if supplied on `ClassificationInput`, is treated as a **pure opaque passthrough** — validated against Phase 1's own closed vocabulary and, if absent or unrecognized, defaulted to `NOT_YET_EVALUATED` (the only truthful value obtainable without an upstream evidence check, per Phase 1's own philosophy). It is assumed to have been determined by some future orchestrator that already ran the Phase 5–9 evidence pipeline — no such orchestrator is built in this phase.

## O. IP Classification Boundary

`[ENGINEERING RECOMMENDATION]` `ip_protection_category` and `abs_tk_relation` reuse Phase 1's existing IP/ABS-TK taxonomy exactly (`PATENT`/`TRADEMARK`/`DESIGN`/`GEOGRAPHICAL_INDICATION`/`TRADITIONAL_KNOWLEDGE_RELATED`/`ACCESS_AND_BENEFIT_SHARING_RELATED`). Phase 11 never determines whether a particular invention is legally patentable, never determines infringement, and never issues a legal conclusion of any kind — classification here is a routing label only (Section F/H), consistent with Phase 1's own "engineering categories are never legal categories" design principle.

## P. Ayurveda Formulation Boundary

`[OFFICIAL SOURCE]`/`[ENGINEERING RECOMMENDATION]` Uses only the distinctions Phase 1 already established (the Ayurveda Aahara/food vs. Ayurvedic-drug branches named directly in the Master Reference's Authoritative Source Strategy, `docs\PHASE_01_DOMAIN_TAXONOMY.md` Section C.1). No legal conclusion is hard-coded from a product name — the extractor only recognizes explicit branch-naming text (e.g. "classical ayurvedic," "Aahara") in the supplied `formulation_description`/`raw_query`, never a guess derived from an ingredient list or a product's commercial name. If the available input cannot establish the distinction, the result is `UNDETERMINED` — never guessed.

## Q. Multilingual Behavior

`[ENGINEERING RECOMMENDATION]` Extraction operates on Unicode text via ordinary Python substring matching — no translation exists anywhere in `src\classification\`, and `raw_query`/`formulation_description` are never rewritten or normalized. `tests\test_phase_11_multilingual.py` exercises Devanagari, Tamil, and mixed-script/emoji input end-to-end: the classifier never crashes, never silently translates, and correctly finds an English-language keyword signal even when it is embedded inside a mixed-script string. Devanagari/Tamil-only text with no recognized keyword correctly resolves to that dimension's `UNDETERMINED` — the classifier never guesses a category merely because *some* text was present.

## R. Security

`[ENGINEERING RECOMMENDATION]` (`tests\test_phase_11_security.py`) User-provided text is always inert data, matched only against the fixed keyword tables in Section I — never executed, never `eval`'d (`test_classifier_never_uses_eval_or_exec` asserts this by source inspection). Tested: prompt-injection-shaped query text, instruction-like formulation-description text, SQL-like text, script-like text, path-traversal-like text, extremely long (5000×-repeated) query/formulation text, `None`/empty values, unexpected input types (list, int, `None` for `raw_query`; int for `evidence_state`), a taxonomy-mismatched (fabricated) `evidence_state` value, Unicode/emoji flooding, and malformed/tampered serialized JSON. No claim of comprehensive security coverage.

## S. Serialization

`[ENGINEERING RECOMMENDATION]` (`src\classification\serialize.py`) Deterministic JSON (`sort_keys=True`, fixed separators, UTF-8) for `ClassificationInput` and `ClassificationResult`, mirroring `src\citation\serialize.py`'s/`src\generation\serialize.py`'s convention exactly. Both are trusted shapes here (unlike Phase 9's deliberately-permissive `CitationReference`) — full explicit field reconstruction, with every dataclass invariant (including the nested `formulation_classification`, `provenance`, and every `dimension_details` entry) re-enforced on deserialization. No pickle, no arbitrary/executable deserialization anywhere.

## T. Determinism

`[ENGINEERING RECOMMENDATION]` `classify()` is a pure function of `(ClassificationInput, ClassificationConfig)` — no result identity/hash field is introduced (`config\classification_contract.yaml` defines none, and `input_id` already serves as the caller's own traceability key), so determinism is verified directly via equality across repeated calls and byte-identical serialized JSON (`tests\test_phase_11_determinism.py`), rather than via a manufactured hash field.

## U. Synthetic Evaluation

`[ENGINEERING RECOMMENDATION]` (`tests\test_phase_11_evaluation.py`) A hand-authored table of 8 synthetic cases, each with an explicitly pre-defined expected `classification_state` (2 `KNOWN`, 2 `UNKNOWN`, 2 `AMBIGUOUS`, 2 `NEEDS_EVIDENCE`), plus dedicated tests for deterministic repeated classification, rule ordering (R1 before R2; R4 firing ahead of a later rule when both conditions are present), missing-field handling, multilingual/mixed-script/adversarial input, serialization round-trip, taxonomy/config mismatch handling (a fabricated `evidence_state` value), and direct regression against Phase 1's own four worked examples.

## V. Evaluation Interpretation

`[OFFICIAL SOURCE]` **This benchmark does not measure real-world classification accuracy and reports no accuracy percentage.** Every fixture is hand-authored and synthetic; no real user query, real formulation, or real regulatory fact is involved anywhere in it. A pass/fail result here demonstrates that Phase 11's own deterministic extraction-plus-tree logic behaves exactly as specified on these hand-picked cases — it says nothing about how reliably the literal keyword-matching heuristic would classify real-world free text, which has not been evaluated and is not claimed to be evaluated.

## W. Known Limitations

`[ENGINEERING RECOMMENDATION]`

- The extraction heuristic is **literal keyword matching only** — it will not recognize a formulation described without using one of the fixed phrases (e.g. a product described purely by ingredient list, with no explicit branch name, always resolves to `UNDETERMINED`). This is a disclosed conservative trade-off, not a defect: the alternative (inferring legal criteria from ingredients/product names) is exactly what the instructions explicitly forbid.
- `IP-05 NONE`, `ATK-03 NOT_RELATED`, and `UI-06 OUT_OF_SCOPE_OR_UNSUPPORTED` are structurally unreachable by this extractor (Section I/L) — asserting any of these negative/exclusionary values from the mere absence of a positive keyword would itself be an unjustified inference this heuristic deliberately does not make.
- Keyword tables are necessarily `[OUR ENHANCEMENT]`, not `[OFFICIAL SOURCE]` — the Master Reference names the taxonomy categories but never the text signals that should trigger them; this is a genuinely open gap Phase 1's own documentation already discloses (`docs\PHASE_01_DOMAIN_TAXONOMY.md` Section C.1's `[ASSUMPTION]`/`[DEFERRED]` note), which Phase 11 fills with an honestly-labeled heuristic rather than leaving unfilled or silently treating as authoritative.
- No production-scale or real-user-query evaluation has been performed (Section V).

## X. Deferred Items

`[DEFERRED]`

- An LLM-assisted or ML-based extraction layer, evaluated against this deterministic baseline, if a concrete future need is demonstrated (Section J).
- Recognizing `IP-05`/`ATK-03`/`UI-06` via some future, more carefully justified negative-signal heuristic.
- Any additional `ClassificationInput` field (ingredients, dosage form, manufacturing/market context) beyond `raw_query`/`formulation_description`, if a concrete future need is demonstrated and justified against Phase 1's own contract.
- Everything Phase 12 (jurisdiction firewall), Phase 13 (confidence/safety framework beyond the boolean escalation flags already in Phase 1's contract), Phase 14 (translation/multilingual delivery), and Phase 15 (human-in-the-loop escalation) own.

## Y. Phase 12 Boundary

`[OFFICIAL SOURCE]` Phase 11 answers *"what formulation/category does the available information indicate?"*; Phase 12 answers *"which jurisdiction/regulatory boundary applies?"* — two deliberately separate questions. `jurisdiction_input` is produced by Phase 11 as an opaque routing value (`INDIA`/`INTERNATIONAL`/`BOTH`/`UNSPECIFIED`), exactly as Phase 1's own taxonomy already defines it (`docs\PHASE_01_DOMAIN_TAXONOMY.md` Section F: *"Phase 1 defines only the input values this dimension can take; the actual firewall... is Phase 12's responsibility, not implemented here"*) — Phase 11 inherits that exact same boundary unchanged. No index selection, no corpus routing, no allow/block decision, and no governing-law determination exists anywhere in `src\classification\`.

## Z. Acceptance Gate

`[ENGINEERING RECOMMENDATION]` A deterministic, explainable formulation-classification engine exists; Phase 1's taxonomy and decision-tree semantics are both reused unchanged, with no independent conflicting taxonomy created; a structured `ClassificationResult` exists that exactly satisfies `config\classification_contract.yaml`, plus Phase-11-owned per-dimension explainability; the `KNOWN`/`UNKNOWN`/`AMBIGUOUS`/`NEEDS_EVIDENCE` semantics are preserved exactly, cross-checked against Phase 1's own reference implementation; every classification result is explainable through observable rules/keyword matches, never a hidden reasoning trace; no legal conclusion, jurisdiction decision, or external retrieval occurs anywhere in `src\classification\`; no LLM dependency is required; Unicode/ambiguity/unknown/needs-evidence/security/serialization/determinism/synthetic-evaluation tests all pass; no Phase 12+ functionality exists anywhere in this phase. **MET** — see Section AA for exact evidence.

## AA. Validation Evidence

`[ENGINEERING RECOMMENDATION]` All Phase 11 automated tests pass — model, rule-engine (cross-checked exhaustively against Phase 1's own reference tree evaluator), ambiguity, multilingual, security, determinism, serialization, and evaluation tests (exact counts in the Phase 11 implementation report). The synthetic evaluation suite (Section U/V) measures implementation correctness against hand-authored, explicitly-labeled synthetic cases only and reports no fabricated real-world accuracy figure. No real-model dependency exists anywhere in Phase 11 (100% deterministic, stdlib-only), so there is no "NOT VALIDATED — model unavailable" disclosure needed here — every gap this phase discloses (Section W) is a deliberate, honestly-labeled scope boundary, not a validation gap in Phase 11's own code.
