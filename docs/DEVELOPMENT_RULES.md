# DEVELOPMENT RULES — PS 26045 IP-SAKTI Sahayak

These rules are implementation controls derived from `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`. They govern *how* work proceeds, phase to phase. See `MASTER_REFERENCE_LOCK.md` for the authoritative architecture/scope summary and `PHASE_TRACKER.md` for per-phase status. **The PDF remains authoritative over all three control documents.**

---

## 1. Source Discipline

Every non-trivial claim, decision, or capability statement must carry exactly one of these seven labels:

- `[OFFICIAL PS]` — directly supported by the SIH problem statement.
- `[OFFICIAL SOURCE]` — a government/WIPO/regulatory source, or the Master Reference PDF itself.
- `[EXTERNAL RESEARCH]` — external research material informing a decision.
- `[ENGINEERING RECOMMENDATION]` — our chosen implementation approach.
- `[OUR ENHANCEMENT]` — a deliberate addition beyond the source material.
- `[ASSUMPTION]` — not yet confirmed; must be benchmarked or validated before being relied upon.
- `[DEFERRED]` — acknowledged but intentionally not built yet.

Rules:
- No fabricated legal or regulatory facts, ever.
- No invented citations, URLs, section numbers, or authority names.
- No claiming a capability (a supported language, a supported source, a working integration) before it has actually been implemented and evaluated.
- Government/regulatory source URLs must be re-verified for currency before any legal/production release.

## 2. Clean Implementation

- Build only what the current phase requires. No speculative abstractions for hypothetical future phases.
- No half-finished implementations. A phase's implementation is either done (with tests and validation) or not started.
- Prefer the simplest approach that satisfies the phase's acceptance gate.

## 3. Phase Isolation

- Work proceeds one phase at a time, in the Final Build Order locked in the Master Reference (see `MASTER_REFERENCE_LOCK.md` Section G).
- Do not implement a later phase's functionality while an earlier phase is in progress, even if it looks convenient (e.g., do not add embeddings/FAISS while still on the BM25 baseline phase).
- Documentation describing future architecture is fine. Actual code for future-phase capability is not, until that phase is explicitly started.
- Do not bypass a phase's acceptance gate to move to the next phase.

## 4. Implementation + Tests + Validation = One Phase

- A phase is not complete until it has: working implementation, automated tests, and validation against its acceptance gate.
- Default test framework: `pytest`.
- Tests must cover, where applicable to the phase: happy paths, edge cases, negative cases, adversarial cases, schema/contract behavior, deterministic behavior, regression behavior, safety boundaries, and provenance/source behavior.
- No tests written merely to inflate coverage numbers — every test must assert something meaningful about correctness or safety.

## 5. Regression Testing

- New phases must not silently break the acceptance gates of previously completed phases.
- As the evaluation harness (Phase 16) comes online, the regression suite should run automatically and reproducibly.
- Before a phase is marked complete, previously passing tests for earlier phases must still pass.

## 6. No Premature Dependencies

- No dependency is added because it "may be useful later." Every dependency must be justified by the needs of the current phase.
- Heavyweight AI/ML dependencies (LangChain, LlamaIndex, FAISS, sentence-transformers, BGE-M3, rerankers, vector databases, OCR engines, large local LLMs, agent frameworks, graph databases, Kubernetes, cloud infrastructure) are not installed until the phase that actually requires them is explicitly started, and even then only per the locked stack in `MASTER_REFERENCE_LOCK.md` Section E.
- Project-control/testing infrastructure dependencies (e.g., `pytest`) are the only exception, and only when directly justified.

## 7. No Fabricated Legal Facts / No Invented Citations

- Regulatory, legal, and IP claims must trace to an `[OFFICIAL SOURCE]` or `[OFFICIAL PS]`-labeled reference.
- If a fact cannot be sourced, it must be marked `[ASSUMPTION]` and flagged for confirmation — never asserted as settled fact.
- This rule applies to project documentation now and to the system's runtime citation behavior once generation/citation phases (8–10) begin.

## 8. Explicit Assumptions

- Any unconfirmed belief used to make a decision is written down and labeled `[ASSUMPTION]`.
- Assumptions are tracked, not buried — they should be visible in the relevant phase's documentation until resolved.

## 9. Explicit Deferred Decisions

- Anything intentionally postponed is labeled `[DEFERRED]` and listed in `MASTER_REFERENCE_LOCK.md` Section J (or a phase-specific doc once that phase starts).
- A deferred technology is only promoted out of deferred status by explicit instruction plus (per the Final Decision Lock) measurable benchmarked evidence that it earns its place.

## 10. Acceptance Gate Requirement

- Every phase has a specific acceptance gate defined in `PHASE_TRACKER.md`, sourced from the Master Reference.
- A phase cannot be marked complete without its acceptance gate demonstrably passing.
- Acceptance gates are not negotiable shortcuts — if a gate cannot be met, the phase is not done, regardless of time pressure.

## 11. Hardware Discipline

- Development hardware is fixed: NVIDIA RTX 3050 (4 GB VRAM), 16 GB RAM, 512 GB SSD.
- One major local GPU model at a time. Never keep multiple large models resident simultaneously.
- Embeddings and reranking run on CPU where practical, reserving the GPU for local generation fallback only.
- A large 7B/14B local model is never the primary dependency.

## 12. Production Meaning

- "Production" means reproducible deployment, controlled corpus updates, evaluation gates, monitoring, backup/restore, security controls, and rollback — not merely "Dockerized."
- The Final Production Gate (`MASTER_REFERENCE_LOCK.md` Section K) must fully pass before any production release.
