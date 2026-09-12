# MASTER REFERENCE LOCK

Status: INITIALIZATION CONTROL DOCUMENT
Last synced against source: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf` (36 pages, read in full on 2026-09-10)

---

## A. Project Identity

- **Project:** PS 26045 — IP-SAKTI Sahayak
- **Nature:** Multilingual RAG-based IP / Regulatory Assistant for Ayurveda
- **Final framing [ENGINEERING RECOMMENDATION]:** A policy-governed, evidence-first regulatory intelligence system — not a generic chatbot. The LLM is one component inside a pipeline that performs classification, jurisdiction control, retrieval, evidence binding, citation validation, confidence/safety evaluation, and abstention/escalation.
- **Final engineering principle [OFFICIAL SOURCE — from Master Reference cover]:** "The project moat is not the LLM. It is authoritative corpus provenance + regulatory classification + jurisdiction isolation + evidence-grounded retrieval + citation verification + safe abstention."

## B. Authoritative Reference

- The single authoritative document for this project is `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`, located at the repository root.
- This PDF consolidates two artifacts: the **Deep Technical Research & Roadmap** (14 pages) and the **28-Part Research Compendium** (which restates the roadmap and adds the **Final Architecture Decision Lock** and **Final Decision Lock**).
- Where the compendium's later, corrected/locked decisions differ from earlier exploratory material in the roadmap section, **the later locked decision (Final Architecture Decision Lock / Final Decision Lock) takes precedence.**
- **This control document, and its siblings (`PHASE_TRACKER.md`, `DEVELOPMENT_RULES.md`), are implementation controls derived from the PDF. They do not replace it. The PDF remains authoritative. See Section L.**

## C. Source-Discipline Rules

Every non-trivial claim, decision, or capability statement in project documentation must carry exactly one of the seven approved labels:

`[OFFICIAL PS]` · `[OFFICIAL SOURCE]` · `[EXTERNAL RESEARCH]` · `[ENGINEERING RECOMMENDATION]` · `[OUR ENHANCEMENT]` · `[ASSUMPTION]` · `[DEFERRED]`

Rules:
- No invented legal/regulatory facts. No invented citations.
- No unsupported capability claims (e.g., claiming a language or source is "supported" before it has been evaluated).
- Assumptions must be explicitly marked `[ASSUMPTION]` and are candidates for benchmarking/confirmation, not treated as fact.
- Deferred technologies are marked `[DEFERRED]` and are not to be implemented until explicitly promoted by later instruction.

## D. Architecture Principle

`[ENGINEERING RECOMMENDATION]` Core engineering principle from the Master Reference: the system is **classification-first, jurisdiction-aware, evidence-grounded regulatory decision-support**. The correct starting point is corpus and retrieval validation — not UI, agents, voice, a knowledge graph, or fine-tuning.

Explicit anti-patterns from the Master Reference ("What You Should NOT Do First"):
- Do not start with React UI.
- Do not start with a large local 7B/14B model on 4 GB VRAM.
- Do not scrape the whole internet or all patent databases.
- Do not make the LLM decide the legal category without a deterministic classification layer.
- Do not let the LLM invent citations.
- Do not mix India and international evidence in one unrestricted retrieval index.
- Do not claim languages or sources that have not been evaluated.
- Do not call the system legal advice; make it evidence-grounded decision support with escalation.

## E. Target Architecture

`[ENGINEERING RECOMMENDATION]` Final Core Pipeline (from Final Architecture Decision Lock):

```
User → Language Detection/Canonicalization → Formulation Classification → Jurisdiction Firewall
 → Hybrid Retrieval (BM25 + BGE-M3/FAISS) → RRF Fusion → Cross-Encoder Reranker → Evidence Pack
 → Generation (Gemini / Local Qwen) → Claim/Evidence Binding → Citation Validation
 → Confidence + Safety → Answer OR Abstain/Human Escalation
```

Final Core Stack `[ENGINEERING RECOMMENDATION]`:
- Backend: FastAPI (Python orchestration)
- Frontend: React + Vite
- Retrieval: BM25 (lexical) + multilingual dense retrieval; FAISS for laptop-oriented dense indexing
- Embeddings: BGE-M3 (CPU candidate)
- Reranker: bge-reranker-v2-m3 (CPU candidate)
- Generation: Gemini Flash API (primary candidate) + Qwen2.5-3B 4-bit (local fallback candidate)
- Translation: Bhashini adapter
- Database: SQLite (early dev) → PostgreSQL (production target)
- Packaging: Docker / Docker Compose (initial deployment)
- Testing: pytest + integration/adversarial tests

Key architectural locks:
- **Jurisdiction Firewall** `[ENGINEERING RECOMMENDATION]`: India and international corpora are separated at retrieval time (separate indices/collections), not merely mentioned in the prompt.
- **Evidence and Citation** `[ENGINEERING RECOMMENDATION]`: Evidence IDs are backend-owned records. The model never invents source identifiers. Invalid/unsupported citations are rejected.
- **Classification** `[ENGINEERING RECOMMENDATION]`: Deterministic, explainable formulation-classification flow with structured questions; output includes provisional classification, basis, missing information, and human-review status.
- **Multilingual** `[ENGINEERING RECOMMENDATION]`: Preserve original query + canonical representation; translate final answers without translating away exact section/article identifiers.
- **Agents and Knowledge Graph** `[DEFERRED]`: Not core dependencies. Introduced only when benchmarked use cases demonstrate measurable value.
- **Regulatory Safety** `[ENGINEERING RECOMMENDATION]`: Answers must be grounded in authoritative evidence, respect jurisdiction/document version, and must never be presented as legal determinations. Missing/conflicting evidence triggers transparent uncertainty and human escalation.

## F. Hardware Constraints

`[OFFICIAL SOURCE — stated development hardware]`

| Component | Constraint | Engineering implication |
|---|---|---|
| GPU | NVIDIA RTX 3050 / 4 GB VRAM | Do not make a large local LLM the primary dependency; reserve GPU for one local generation model when needed. |
| RAM | 16 GB | Keep the service stack lightweight; run embeddings/reranking on CPU where practical. |
| Storage | 512 GB SSD | Use a curated authoritative corpus and avoid mass scraping; keep raw/normalized/indexed data separated. |

`[ENGINEERING RECOMMENDATION]` Practical GPU rule: **one major local model at a time.** Do not keep multiple large models resident simultaneously. FastAPI, React, SQLite, FAISS, BM25, BGE-M3 embeddings, and the cross-encoder reranker all run locally/CPU. A large 7B/14B local model is explicitly **not** a sensible primary dependency on this hardware.

## G. Complete Phase 0–23 Roadmap

See `PHASE_TRACKER.md` for the per-phase tracking table. Summary (`[OFFICIAL SOURCE]` from Master Reference "Full Engineering Roadmap — Foundation to Production"):

0. Problem, Scope & Acceptance Contract
1. Domain Taxonomy & Regulatory Decision Tree
2. Authority Matrix & Corpus Lock
3. Document Ingestion & Legal Structure Extraction
4. Legal-Aware Chunking
5. BM25 Baseline
6. Multilingual Dense Retrieval
7. Hybrid Fusion + Reranking
8. Evidence Object & Citation Architecture
9. Citation Validation
10. Grounded Generation
11. Formulation Classification Engine
12. Jurisdiction Firewall
13. Confidence, Safety & Abstention
14. Multilingual Delivery
15. Human-in-the-Loop
16. Evaluation & Red-Team Benchmark
17. Backend Productization
18. Frontend
19. Security & Adversarial Hardening
20. Deployment Engineering
21. Observability, Backup & Corpus Refresh
22. CI/CD & Production Release
23. Production Validation

Each phase in the source document carries a **Goal**, **Build** scope, **Deliverables**, and **Acceptance gate** — reproduced per-phase in `PHASE_TRACKER.md`.

## H. Testing Rule

`[ENGINEERING RECOMMENDATION]` **IMPLEMENTATION + TESTS + VALIDATION = ONE PHASE.** No phase is complete without meaningful automated tests. Tests must cover, where applicable: happy paths, edge cases, negative cases, adversarial cases, schema/contract behavior, deterministic behavior, regression behavior, safety boundaries, and provenance/source behavior. No tests written merely for coverage numbers. Default framework: `pytest`.

## I. Phase Isolation Rule

`[ENGINEERING RECOMMENDATION]` Implement one phase at a time, in the Final Build Order (Section G). Do not implement functionality belonging to a later phase while working on an earlier one. Do not bypass acceptance gates. Documentation describing future architecture is allowed; actual implementation of future-phase capability is not.

## J. Deferred Technologies

`[DEFERRED]` — not to be implemented until a later phase explicitly calls for them and/or a benchmark justifies them:

- Single/multi-agent tool orchestration (registry/TKDL/ABS research workflows)
- Knowledge graph (formulations, ingredients, laws, authorities, jurisdictions)
- Graph + RAG multi-hop evidence retrieval
- Additional live registry/search connectors beyond the locked source strategy
- Expanded language coverage beyond natively-evaluated languages
- Enterprise authentication/RBAC and advanced multi-user isolation
- Advanced observability/analytics beyond Phase 21 scope
- Large local 7B/14B LLM as a primary dependency
- Kubernetes / cloud infrastructure

`[ENGINEERING RECOMMENDATION]` Final Decision Lock governs all of these: *"New technologies must earn their place through measurable evidence; they should not be added simply because they sound advanced."*

## K. Final Production Acceptance Principles

`[ENGINEERING RECOMMENDATION]` Final Production Gate (all must pass before production release):

- Authoritative corpus and provenance validated
- Legal-aware document structure and versioning implemented
- Retrieval benchmark completed
- Classification benchmark completed
- Jurisdiction leakage tests pass
- Citation validation tests pass
- Unsupported-claim / abstention tests pass
- Multilingual quality tested for every advertised language
- Security and prompt-injection tests pass
- Backup and restore verified
- Monitoring and health checks operational
- Corpus refresh workflow tested
- Rollback procedure tested
- Production deployment reproducible from a clean environment

`[ENGINEERING RECOMMENDATION]` Production means reproducible deployment, controlled corpus updates, evaluation gates, monitoring, backups/restores, security controls, and rollback — **not merely "Dockerized."**

## L. Authority Statement

**The Master Reference PDF (`PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`) is the single source of truth for this project.** This document (`MASTER_REFERENCE_LOCK.md`) and its sibling control documents (`PHASE_TRACKER.md`, `DEVELOPMENT_RULES.md`) are derived summaries and implementation controls only. If any conflict is discovered between these control documents and the PDF, **the PDF governs**, and the control documents must be corrected to match — never the reverse. Government/regulatory source URLs listed in the PDF must be re-verified for currency before legal/production release (Master Reference, "How to Use This Reference," item 4).
