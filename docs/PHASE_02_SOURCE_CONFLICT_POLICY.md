# PHASE 2 — SOURCE / PRIORITY CONFLICT POLICY

Status: CONTRACT DOCUMENT (Phase 2 deliverable)
Authoritative source: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`
Companion: `docs\PHASE_02_AUTHORITY_MATRIX.md`, `docs\PHASE_02_CORPUS_ADMISSION_POLICY.md`

**Scope note `[ENGINEERING RECOMMENDATION]`:** This document defines how the system is required to *behave* when evidence conflicts — not how to actually resolve any real conflict, since no evidence exists yet. It is a safety policy for later phases (9, 10, 13) to implement against.

---

## 1. The Core Rule

`[OFFICIAL SOURCE]` The Master Reference is explicit that the system must never resolve uncertainty by guessing: *"Missing or conflicting evidence should trigger transparent uncertainty and human escalation"* (Final Architecture Decision Lock, Regulatory Safety). This phase's instruction sharpens that into an engineering rule this project treats as absolute: **the system must never resolve a legal or factual conflict by letting a generation model choose whichever document sounds more convincing.** Conflict resolution, where it exists at all, is a deterministic, auditable, human-reviewable process — never a model's stylistic judgment call.

## 2. No Invented Legal Hierarchy

`[OFFICIAL SOURCE]` / `[ENGINEERING RECOMMENDATION]` The Master Reference names eight source families side by side (`docs\PHASE_02_AUTHORITY_MATRIX.md` Section 0) without ever stating that one family legally outranks another (e.g., it never says an India Code Act outranks a CDSCO rule, or that a Ministry of Ayush programme document outranks an FSSAI advisory). This project therefore **does not invent such a hierarchy.** Where two authoritative sources appear to conflict, the engineering system returns a controlled uncertainty state (`HOLD_FOR_VALIDATION` in the admission policy, or `AMBIGUOUS`/`NEEDS_EVIDENCE` in the Phase 1 classification/decision-tree contract) and requires human validation — it does not pick a "winner."

`[DEFERRED]` If a genuine, sourceable legal hierarchy is later identified (e.g., a specific statute stating that one instrument prevails over another in a named circumstance), it may be added to this policy *only* as an explicitly cited `[OFFICIAL SOURCE]`-labeled rule, never as an engineering guess.

## 3. Conflict Categories

`[ENGINEERING RECOMMENDATION]` — distinguishing conflict *types* so each can be handled by the correct later-phase mechanism, without collapsing them into one generic "conflict" bucket:

| Category | Description | Handling |
|---|---|---|
| **Authority conflict** | Two different source families make apparently inconsistent statements about the same question. | No hierarchy is assumed (Section 2). Both are surfaced; classification/generation phases must present both or abstain, never silently prefer one. |
| **Version conflict** | Two versions of the *same* logical document (`document_id`) appear simultaneously admissible. | Resolved via `supersession_status` (`docs\PHASE_02_CORPUS_ADMISSION_POLICY.md` Section 4) — the older version must be marked `SUPERSEDED` before the newer is treated as current; until confirmed, both are `ADMIT_WITH_RESTRICTION` at most. |
| **Jurisdiction conflict** | A question's jurisdiction is ambiguous (e.g., spans both India and international regimes) or a document's declared jurisdiction doesn't match its source family. | Document-level mismatches are rejected outright at admission (`docs\PHASE_02_CORPUS_ADMISSION_POLICY.md` rule A3). Question-level jurisdiction ambiguity is handled by Phase 1's `JX-03 BOTH` / `JX-04 UNSPECIFIED` inputs and, eventually, Phase 12's firewall — not resolved here. |
| **Document supersession** | A document is known to have been replaced. | `supersession_status == SUPERSEDED` is terminal in the admission policy (rule A7) — never re-surfaced as current evidence. |
| **Incomplete evidence** | Relevant evidence likely exists but has not been retrieved/confirmed. | Routes to `NEEDS_EVIDENCE` in the Phase 1 classification contract, or `HOLD_FOR_VALIDATION` in the admission policy — never treated as "no conflict." |
| **Ambiguous evidence** | Retrieved evidence does not clearly support one conclusion. | Routes to `AMBIGUOUS` in the Phase 1 classification contract (`docs\PHASE_01_REGULATORY_DECISION_TREE.md` rule R4/R5) — requires escalation, per that contract's `requires_escalation` flag. |

## 4. Safety Invariant

`[OFFICIAL SOURCE]` / `[ENGINEERING RECOMMENDATION]` Carried forward from Phase 1's classification-contract safety invariants (`config\classification_contract.yaml`): no automated component may convert a conflict into a confident, unqualified answer. Every conflict category above terminates in a state that either (a) blocks admission (`HOLD_FOR_VALIDATION`/`REJECT`), or (b) is explicitly represented downstream as `AMBIGUOUS`/`NEEDS_EVIDENCE` with `requires_escalation`/`requires_evidence` set. There is no code path, in this policy, that lets a conflict silently resolve to `ADMIT` or `KNOWN`.

## 5. What This Phase Does Not Do

`[ENGINEERING RECOMMENDATION]` No actual conflict is detected or resolved by Phase 2 — there is no evidence corpus yet to conflict. This document only fixes the *policy* that later phases (9 Citation Validation, 10 Grounded Generation, 13 Confidence/Safety) must implement against, and gives Phase 2's own admission-policy reference evaluator (`tests\_admission_policy_reference_impl.py`) a documented, testable specification for its conflict-related rules (A8, A9 in `docs\PHASE_02_CORPUS_ADMISSION_POLICY.md` Section 3).
