# PHASE 0 — PROBLEM, SCOPE & ACCEPTANCE CONTRACT

Status: CONTRACT DOCUMENT (Phase 0 deliverable)
Authoritative source: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf` (36 pages, read in full)
Governed by: `docs\MASTER_REFERENCE_LOCK.md`, `docs\DEVELOPMENT_RULES.md`

**Provenance note `[ASSUMPTION]`:** The Master Reference PDF references an original SIH problem-statement artifact (`PS_26045_IP_SAKTI_Sahayak.pdf`) as its `[OFFICIAL PS]`-tier basis, but that original PS document has not itself been supplied to or reviewed in this workspace — only the Master Reference (which consolidates and interprets it) is available. Consequently, this document treats the **Master Reference PDF itself as `[OFFICIAL SOURCE]`** (per the label definition in `MASTER_REFERENCE_LOCK.md` Section C: "a government/WIPO/regulatory source, or the Master Reference PDF itself"), and does **not** fabricate direct `[OFFICIAL PS]` quotations that cannot be traced to a reviewed document. Where the Master Reference explicitly attributes a statement to the PS, that attribution is preserved as `[OFFICIAL PS]`; everything else derived from the Master Reference's own engineering judgment is labeled `[ENGINEERING RECOMMENDATION]`, `[OUR ENHANCEMENT]`, or `[DEFERRED]` as the source itself tags it.

---

## 1. Project Identity

- **Project:** PS 26045 — IP-SAKTI Sahayak `[OFFICIAL SOURCE]`
- **Purpose:** Multilingual RAG-based IP / Regulatory Assistant for Ayurveda `[OFFICIAL SOURCE]`
- **Development hardware:** NVIDIA RTX 3050 · 4 GB VRAM · 16 GB RAM · 512 GB SSD `[OFFICIAL SOURCE]`
- **Source discipline set:** `[OFFICIAL PS]` `[OFFICIAL SOURCE]` `[EXTERNAL RESEARCH]` `[ENGINEERING RECOMMENDATION]` `[OUR ENHANCEMENT]` `[ASSUMPTION]` `[DEFERRED]` — mandatory on every claim in this and all future project documents `[OFFICIAL SOURCE]`.

## 2. Problem Definition

`[OFFICIAL SOURCE]` The Master Reference frames the problem as follows: Ayurveda practitioners, formulators, and researchers must navigate a fragmented landscape of Indian and international regulatory and intellectual-property authorities — India Code, IP India, Ministry of Ayush, CDSCO (traditional drugs and Drugs & Cosmetics Rules), FSSAI (Ayurveda Aahara / food law), WIPO/WIPO Lex (international IP, traditional knowledge, genetic resources), and TKDL — without a single trustworthy, evidence-grounded tool to answer IP and regulatory questions about their formulations.

`[OFFICIAL SOURCE]` A specific, named complication is that Ayurveda Aahara has its own FSSAI regulatory framework, while CDSCO separately publishes traditional-drug rules — meaning a correct system **must distinguish food/Ayurveda-Aahara from Ayurvedic drugs** rather than treating every Ayurvedic ingestible as one category. This is called out explicitly in the Master Reference's Authoritative Source Strategy and directly shapes the classification requirement in Section 4 below.

`[ENGINEERING RECOMMENDATION]` The engineering interpretation of this problem (Master Reference, "Core engineering principle" / "Final engineering principle"): this is not a generic Ayurveda chatbot problem. It is a **classification-first, jurisdiction-aware, evidence-grounded regulatory decision-support** problem, where the differentiator ("moat") is *"authoritative corpus provenance + regulatory classification + jurisdiction isolation + evidence-grounded retrieval + citation verification + safe abstention"* — not the language model.

## 3. System Purpose

`[ENGINEERING RECOMMENDATION]` IP-SAKTI Sahayak is a **policy-governed, evidence-first regulatory intelligence system**. The LLM is one component inside a larger pipeline that performs classification, jurisdiction control, retrieval, evidence binding, citation validation, confidence/safety evaluation, and abstention/escalation (Final Architecture Decision Lock, "Final Architecture Principle").

`[ENGINEERING RECOMMENDATION]` The system's answers must be:
- Grounded in retrieved, authoritative evidence (not model-internal knowledge).
- Jurisdiction-respecting (India vs. international evidence kept separate).
- Version/date-aware where the underlying source material provides that context.
- Explicit about uncertainty, and willing to abstain or escalate rather than guess.

`[OFFICIAL SOURCE]` **Explicit non-claim:** The system does **not** provide legal advice or authoritative legal determinations. The Master Reference is direct on this point: *"Do not call the system legal advice; make it evidence-grounded decision support with escalation."* This non-claim is a permanent constraint on every future phase, not a Phase 0-only note.

## 4. MVP Scope

`[OFFICIAL SOURCE]` Capabilities that the Master Reference's roadmap establishes as part of the intended system (each to be implemented in its own later, dedicated phase — **none implemented in Phase 0**):

| Capability | Description | Source basis |
|---|---|---|
| Regulatory & IP intelligence | Answer IP and regulatory questions about Ayurveda formulations, grounded in the authoritative source strategy (India Code, IP India, Ministry of Ayush, CDSCO, FSSAI, WIPO/WIPO Lex, TKDL). | `[OFFICIAL SOURCE]` |
| Formulation/product classification | Deterministic, explainable classification (classical/proprietary/new-drug, food/cosmetic/phytopharma, IP protection categories, ABS/TK concepts) that runs *before* retrieval and does not let the LLM decide the legal category. | `[OFFICIAL SOURCE]` |
| Jurisdiction-aware handling | India and international evidence are kept separate at retrieval time via a jurisdiction firewall, not merely mentioned in a prompt. | `[OFFICIAL SOURCE]` |
| Authoritative evidence retrieval | Hybrid retrieval (BM25 lexical + multilingual dense/BGE-M3+FAISS) with RRF fusion and cross-encoder reranking over a curated, provenance-tracked corpus. | `[OFFICIAL SOURCE]` |
| Evidence-grounded responses | Generation is evidence-only; every claim binds to a concrete, backend-owned evidence ID; invalid/unsupported citations are rejected. | `[OFFICIAL SOURCE]` |
| Multilingual delivery | Language detection/canonicalization plus a Bhashini adapter; only languages actually evaluated are advertised as supported. | `[OFFICIAL SOURCE]` |
| Uncertainty / abstention | Evidence-derived confidence scoring; low-confidence or high-stakes cases abstain rather than guess. | `[OFFICIAL SOURCE]` |
| Human escalation | A defined hand-off path (escalation reason, evidence pack, confidence, unresolved questions, facilitator) for cases the system cannot safely resolve. | `[OFFICIAL SOURCE]` |

`[ENGINEERING RECOMMENDATION]` Phase 0 itself delivers none of the above as working software. It defines the **contract** — problem, scope, boundaries, and per-capability ownership/test/acceptance mapping — that later phases (1 through 23, per the Final Build Order) are individually responsible for implementing, testing, and validating.

## 5. Out of Scope

`[DEFERRED]` The following are explicitly excluded from MVP scope per the Final Architecture Decision Lock ("Agents and Knowledge Graph") and the roadmap's "Future Evolution — Only After SIH-Ready Core" section. They are not silently promoted into current scope by this or any future phase without an explicit benchmarked justification and instruction:

- Multi-agent / single-agent tool orchestration (e.g., for registry/TKDL/ABS research workflows)
- Knowledge graph (entities: formulations, ingredients, laws, authorities, jurisdictions)
- Graph + RAG multi-hop evidence retrieval
- Additional live registry/search connectors beyond the locked Authoritative Source Strategy
- Expanded language coverage beyond natively-evaluated languages
- Enterprise authentication / RBAC and advanced multi-user isolation
- Advanced observability and analytics beyond Phase 21's operational scope
- A large local 7B/14B LLM as a **primary** dependency (a small local fallback model is in scope for later phases, per Section 11, but never as primary)
- Kubernetes / cloud infrastructure

`[OFFICIAL SOURCE]` Also explicitly out of scope for the system's behavior, permanently (not merely deferred): presenting the system's output as authoritative legal advice or a legal determination.

## 6. Core User Workflows

`[ENGINEERING RECOMMENDATION]` This is a **conceptual contract/workflow description only** — none of these stages are implemented in Phase 0. It documents the target shape for later phases to build against (per the Final Core Pipeline in `MASTER_REFERENCE_LOCK.md` Section E):

```
User question
  → Language detection / canonicalization            (Phase 14)
  → Formulation classification                        (Phase 11, schema in Phase 1)
  → Jurisdiction firewall                              (Phase 12)
  → Hybrid evidence retrieval (BM25 + dense, RRF)      (Phases 5, 6, 7)
  → Evidence pack construction                         (Phase 8)
  → Grounded generation                                (Phase 10)
  → Claim ↔ evidence binding / citation validation     (Phases 8, 9)
  → Confidence + safety evaluation                     (Phase 13)
  → Answer  OR  Abstain / Human escalation              (Phases 13, 15)
```

`[ENGINEERING RECOMMENDATION]` Every workflow stage above has exactly one owning phase, listed in Section 13's Acceptance Contract table.

## 7. System Boundaries

`[ENGINEERING RECOMMENDATION]`, derived from the Master Reference's architecture and source strategy:

- **Input boundary:** The system accepts natural-language questions about Ayurveda-related IP/regulatory matters. Inputs outside this domain (per the classification layer, once built) are out of scope and must not receive a confident answer.
- **Knowledge/source boundary:** Only the locked Authoritative Source Strategy families are in scope as evidence sources — India Code, IP India, Ministry of Ayush, CDSCO (Traditional Drugs, Drugs & Cosmetics Rules), FSSAI (Ayurveda Aahara & advisories), WIPO/WIPO Lex, TKDL (authorized/public material only, never assumed protected full-database access), and Bhashini (as a translation adapter, not a knowledge source). No source outside this registry may be treated as authoritative without a documented Phase 2 addition.
- **Regulatory/IP domain boundary:** The system distinguishes food/Ayurveda-Aahara (FSSAI) from Ayurvedic drugs (CDSCO) as separate regulatory tracks — it must not collapse them into one category.
- **Jurisdiction boundary:** India and international evidence are never merged in a single unrestricted retrieval index or answer without explicit jurisdiction labeling.
- **Evidence boundary:** No answer content may originate outside retrieved, evidence-store-backed material once the evidence/citation phases (8–10) exist. The model does not invent source identifiers.
- **Output boundary:** Outputs are evidence-grounded decision support, never presented as a legal determination or final legal advice.
- **Human escalation boundary:** Ambiguous, out-of-scope, low-confidence, or high-stakes cases must have a defined escalation path (Phase 15) rather than a confident guess.

## 8. Safety Boundary

`[OFFICIAL SOURCE]` / `[ENGINEERING RECOMMENDATION]` The system must **not**:

- Invent legal rules, regulations, or regulatory classifications `[OFFICIAL SOURCE — "Do not let the LLM invent citations" / "Do not make the LLM decide the legal category without a deterministic classification layer"]`
- Invent sources, authorities, or document identities `[ENGINEERING RECOMMENDATION — Evidence and Citation lock: "Evidence IDs are backend-owned records. The model does not invent source identifiers."]`
- Invent citations `[OFFICIAL SOURCE]`
- Silently guess when evidence is insufficient or conflicting — it must produce transparent uncertainty and escalate `[ENGINEERING RECOMMENDATION — Regulatory Safety lock]`
- Present unsupported conclusions as authoritative legal determinations `[OFFICIAL SOURCE]`
- Mix India and international evidence in one unrestricted retrieval index `[OFFICIAL SOURCE]`
- Claim languages or sources that have not actually been evaluated `[OFFICIAL SOURCE]`

These safety boundaries are permanent constraints that apply to every future phase's design, not just Phase 0's documentation.

## 9. Evidence & Provenance Contract

`[ENGINEERING RECOMMENDATION]` These are **future requirements being contracted now**, not implemented in Phase 0. They bind the design of Phases 2, 3, 4, 8, and 9:

- **Authoritative source provenance** (Phase 2): every source recorded with authority tier, jurisdiction, document type, URL, version, effective date, retrieval date, checksum, and refresh status.
- **Document identity** (Phase 3): every ingested document retains a traceable identity back to its exact source and location (heading/section/subsection/page).
- **Jurisdiction** (Phase 2, 4, 12): every evidence unit carries jurisdiction metadata that survives chunking and retrieval.
- **Version / effective-date context** (Phase 2, 4): captured where the source material provides it; absence of this context is itself a signal the confidence engine (Phase 13) must account for.
- **Evidence traceability** (Phase 8): evidence is a first-class backend object (Evidence ID + metadata), not text pasted into a prompt.
- **Citation integrity** (Phase 9): claims that cite a non-existent or mismatched evidence ID are rejected, not silently passed through.
- **Claim-to-evidence relationships** (Phase 8, 10): every generated claim must be traceable to the specific evidence ID(s) that support it.

## 10. Non-Functional Requirements

`[ENGINEERING RECOMMENDATION]`, restricted to what the Master Reference actually supports — no invented numeric SLAs:

- **Reproducibility:** A fresh environment must be provisionable and startable without source edits (roadmap Phase 20 acceptance gate); corpus updates must be validated, re-indexed, evaluated, and released safely (Phase 21).
- **Testability:** Every phase carries automated tests; a regression suite runs automatically and produces reproducible results (Phase 16 acceptance gate). This is the Phase 0-onward project rule: implementation + tests + validation = one phase.
- **Maintainability:** Research modules become a maintainable service via stable APIs, configuration, and interfaces (Phase 17), not notebook/manual steps.
- **Security:** Known attack cases (prompt injection, poisoned sources, citation manipulation, unsafe inputs) must fail safely (Phase 19).
- **Provenance:** Every source section must be traceable to its exact document and location (Phase 3 acceptance gate).
- **Controlled corpus updates:** Source change → verification → versioning → re-ingestion → re-indexing → impact analysis → evaluation → approval → production release `[OUR ENHANCEMENT — Regulatory Freshness, Final Architecture Decision Lock]`.
- **Monitoring:** Metrics, logs, latency tracking, retrieval diagnostics, citation rejection rate, and abstention rate are operational requirements owned by Phase 21.
- **Backup/restore:** Database backups and restore tests are owned by Phase 21 and re-verified in Phase 23.
- **Rollback:** Every production release must be reproducible, tested, and rollback-capable (Phase 22 acceptance gate).
- **Scalability path:** Interfaces are designed so storage, model, and deployment tiers can change (e.g., SQLite → PostgreSQL, FAISS on a laptop → a larger vector store) without rewriting the core pipeline — an explicit engineering target stated in the Master Reference's hardware section, not a numeric SLA.

`[ENGINEERING RECOMMENDATION]` No latency, throughput, or accuracy numeric targets are locked in Phase 0. The Master Reference specifies *metrics* to track per area (Recall@K/MRR/nDCG, classification F1, citation precision/recall, p50/p95 latency — see its Evaluation Plan) but explicitly defers concrete numeric thresholds to benchmarking within the owning phases (5, 7, 9, 11, 13, 16), consistent with "Set threshold before SIH" language rather than a pre-set number. Inventing a number here would violate the no-fabrication rule.

## 11. Hardware Constraints

`[OFFICIAL SOURCE]`

| Component | Constraint | Engineering implication |
|---|---|---|
| GPU | NVIDIA RTX 3050 / 4 GB VRAM | No large local LLM as primary dependency; GPU reserved for one local generation model when needed. |
| RAM | 16 GB | Lightweight service stack; embeddings/reranking run on CPU where practical. |
| Storage | 512 GB SSD | Curated authoritative corpus, not mass scraping; raw/normalized/indexed data kept separated. |

`[ENGINEERING RECOMMENDATION]` Practical GPU rule carried forward into every future phase: **one major local model at a time**; never keep multiple large models resident simultaneously. This constrains the design of Phases 6, 7, and 10 specifically, but is recorded here in Phase 0 as a binding contract term.

## 12. Deferred Technologies

`[DEFERRED]` (identical set to Section 5, restated here per the requested document structure — see `MASTER_REFERENCE_LOCK.md` Section J for the canonical list):

- Multi-agent / single-agent tool orchestration
- Knowledge graph
- Graph-RAG (multi-hop evidence retrieval)
- Expanded registry/search connectors beyond the locked source strategy
- Expanded language coverage beyond natively-evaluated languages
- Enterprise authentication / RBAC
- Advanced observability/analytics beyond Phase 21 scope
- Large local 7B/14B LLM as a primary dependency
- Kubernetes / cloud infrastructure

`[ENGINEERING RECOMMENDATION]` Per the Final Decision Lock: *"New technologies must earn their place through measurable evidence; they should not be added simply because they sound advanced."* None of the above are implemented until a specific phase's benchmark justifies promotion, and only by explicit instruction.

`[ENGINEERING RECOMMENDATION]` The same list is represented machine-readably as `deferred_technologies` (`DEF-01` through `DEF-09`) in `config\acceptance_contract.yaml`.

## 13. Acceptance Contract

`[OFFICIAL SOURCE]` The Master Reference's Phase 0 acceptance gate: *"Every mandatory PS capability has an owner, test and acceptance criterion."*

The table below maps every phase of the Final Build Order (which collectively constitute the mandatory capabilities of the system) to an owner phase, required behavior, test requirement, and acceptance criterion. This table is reproduced machine-readably in `config\acceptance_contract.yaml`. **Status values describe contract-definition status only** (i.e., "has this capability been given an owner/test-requirement/acceptance-criterion by Phase 0?"), never implementation status. No entry is marked as implemented.

| Capability ID | Mandatory Capability | Owner Phase | Required Behavior | Test Requirement | Acceptance Criterion | Status |
|---|---|---|---|---|---|---|
| CAP-00 | Problem, Scope & Acceptance Contract | 0 | Produce an explicit, testable engineering contract translating the Master Reference into defined scope, boundaries, and per-capability ownership. | Automated tests validating the contract document and YAML schema, field completeness, ID uniqueness, and internal consistency. | Every mandatory PS capability has an owner, test, and acceptance criterion. | DEFINED |
| CAP-01 | Domain Taxonomy & Regulatory Decision Tree | 1 | Turn the domain into a structured classification problem: formulation categories, intended-use questions, claims, classical/proprietary/new-drug branches, food/cosmetic/phytopharma branches, IP protection categories, ABS/TK concepts. | Classification schema + decision tree + labeled seed examples, tested against a held-out labeled set. | A test set can be classified without an LLM deciding everything. | DEFINED |
| CAP-02 | Authority Matrix & Corpus Lock | 2 | Build a source registry with authority tier, jurisdiction, document type, URL, version, effective date, retrieval date, checksum, refresh status. | Tests verifying every target question category resolves to at least one registered authoritative source. | Every target question category has at least one authoritative evidence path. | DEFINED |
| CAP-03 | Document Ingestion & Legal Structure Extraction | 3 | Convert source documents into structured records (headings, sections, subsections, clauses, tables, page numbers, dates, provenance) without destroying legal hierarchy. | Tests tracing a structured section back to its exact source document and location. | A source section can be traced back to the exact document and location. | DEFINED |
| CAP-04 | Legal-Aware Chunking | 4 | Create retrieval units via section/subsection/article-aware chunking with metadata propagation. | Tests asserting retrieved chunks retain jurisdiction, section, version, and effective-date metadata. | Retrieved chunks retain jurisdiction, section, version, and effective-date context. | DEFINED |
| CAP-05 | BM25 Baseline | 5 | Build a BM25 index and query API as the measurable lexical retrieval baseline. | Retrieval benchmark producing Recall@K, MRR, nDCG on a curated query set. | Every retrieval improvement is measured against this baseline. | DEFINED |
| CAP-06 | Multilingual Dense Retrieval | 6 | Add BGE-M3 CPU embeddings + FAISS index + embedding cache for semantic/multilingual retrieval. | Benchmark comparison against the BM25 baseline, run within hardware constraints. | Dense retrieval adds measurable recall without exhausting the laptop. | DEFINED |
| CAP-07 | Hybrid Fusion + Reranking | 7 | Combine BM25 + dense top-K via RRF, then apply a cross-encoder reranker. | Reranker benchmark comparing Precision@K / nDCG before and after reranking. | Reranking measurably improves Precision@K / nDCG. | DEFINED |
| CAP-08 | Evidence Object & Citation Architecture | 8 | Represent evidence as a first-class backend object: evidence IDs, source metadata, section/page, version, effective date, authority tier, URL. | Tests asserting every generated claim resolves to a concrete evidence ID. | Every generated claim can point to a concrete evidence ID. | DEFINED |
| CAP-09 | Citation Validation | 9 | Extract claims, validate evidence IDs, and check source/version/jurisdiction/support consistency. | Rejection tests using fabricated/mismatched evidence IDs. | Fake evidence IDs and unsupported claims are rejected. | DEFINED |
| CAP-10 | Grounded Generation | 10 | Generate answers only from validated evidence, with uncertainty wording and disclaimer, with a local fallback model. | Tests verifying unsupported claims are detected/rejected and grounded answers pass citation tests. | Unsupported claims are detected/rejected; grounded answers pass citation tests. | DEFINED |
| CAP-11 | Formulation Classification Engine | 11 | Deterministic rule engine + minimal clarifying questions producing a structured classification result. | Classification API tested against a labeled test set with an agreed F1/accuracy threshold. | Classification meets agreed F1/accuracy threshold and ambiguous cases escalate. | DEFINED |
| CAP-12 | Jurisdiction Firewall | 12 | Separate India/international evidence via distinct indices/collections, typed retrieval requests, jurisdiction metadata, and final validation. | Cross-jurisdiction leakage test suite. | Cross-jurisdiction leakage test returns zero leakage. | DEFINED |
| CAP-13 | Confidence, Safety & Abstention | 13 | Compute evidence-derived confidence (retrieval, authority, coverage, classification, version signals) with abstention thresholds. | Tests over low-confidence/high-stakes synthetic cases. | Low-confidence/high-stakes cases abstain or escalate instead of guessing. | DEFINED |
| CAP-14 | Multilingual Delivery | 14 | Language detection, canonicalization, Bhashini adapter, answer translation preserving evidence identity. | Citation-preservation tests per evaluated language. | Meaning and evidence references survive translation; only evaluated languages are advertised. | DEFINED |
| CAP-15 | Human-in-the-Loop | 15 | Escalation reason, evidence pack, confidence, unresolved questions, facilitator handoff. | Tests over ambiguous/out-of-scope/high-stakes synthetic cases. | Ambiguous/out-of-scope/high-stakes cases reliably escalate. | DEFINED |
| CAP-16 | Evaluation & Red-Team Benchmark | 16 | Build retrieval, classification, generation, citation, safety, multilingual, and adversarial benchmark sets. | Automated, reproducible regression suite execution. | Regression suite runs automatically and results are reproducible. | DEFINED |
| CAP-17 | Backend Productization | 17 | FastAPI service interfaces, configuration, persistence, audit logs, error handling, health endpoints. | Integration tests exercising core workflows via API only. | Core workflows run through stable APIs without notebook/manual steps. | DEFINED |
| CAP-18 | Frontend | 18 | React/Vite interface for chat, classification, jurisdiction, evidence, citations, confidence, escalation. | UI/e2e tests covering every core workflow. | All core workflows can be completed through UI only. | DEFINED |
| CAP-19 | Security & Adversarial Hardening | 19 | Input validation, document-as-data policy, path/file limits, prompt-injection tests, access controls, audit logs. | Security test suite covering known attack classes. | Known attack cases fail safely. | DEFINED |
| CAP-20 | Deployment Engineering | 20 | Docker/Compose profiles, environment configuration, DB migration, startup checks, model provisioning, offline/local fallback. | Fresh-environment provisioning test. | Fresh environment can be provisioned and started without source edits. | DEFINED |
| CAP-21 | Observability, Backup & Corpus Refresh | 21 | Metrics, logs, latency tracking, retrieval diagnostics, citation rejection rate, abstention rate, backups, restore tests, corpus refresh pipeline. | Backup/restore test + corpus refresh dry run. | A corpus update can be validated, re-indexed, evaluated, and released safely. | DEFINED |
| CAP-22 | CI/CD & Production Release | 22 | Automated tests → evaluation gates → container build → staging smoke tests → release artifact → production deployment. | CI pipeline run producing a versioned, rollback-tested release. | A release is reproducible, tested, and rollback-capable. | DEFINED |
| CAP-23 | Production Validation | 23 | Load tests, failure recovery, multilingual regression, citation tests, jurisdiction isolation, backup/restore, deployment rehearsal. | Full production-readiness test battery against the Final Production Gate. | All critical gates pass; unsupported capabilities remain explicitly out of scope. | DEFINED |

`[ENGINEERING RECOMMENDATION]` Allowed `status` vocabulary for this and future contract revisions: `DEFINED` (contract row exists and is internally consistent — the only value used in this Phase 0 pass), `IN_PROGRESS`, `IMPLEMENTED`, `VALIDATED`. A capability only moves past `DEFINED` when its owning phase is explicitly started and completes its own implementation + tests + validation.

## 14. Phase Boundary

`[ENGINEERING RECOMMENDATION]`

**Phase 0 defines the contract.** It produces:
- This document (`docs\PHASE_00_SCOPE_AND_ACCEPTANCE.md`)
- The machine-readable contract (`config\acceptance_contract.yaml`)
- Automated tests validating both

**Phase 0 implements no application functionality.** No retrieval, classification, embeddings, generation, jurisdiction handling, citation validation, confidence/safety logic, multilingual delivery, human escalation, backend, frontend, agents, knowledge graph, or OCR code exists as a result of this phase.

**Phase 1 — Domain Taxonomy & Regulatory Decision Tree** is the next phase in the Final Build Order. It will turn the domain into a structured classification problem (formulation categories, decision tree, labeled seed examples) per CAP-01 above. No Phase 1 implementation is included in this Phase 0 delivery.
