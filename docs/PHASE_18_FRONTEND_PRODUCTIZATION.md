# PHASE 18 — FRONTEND PRODUCTIZATION

Status: CONTRACT + IMPLEMENTATION DOCUMENT (Phase 18 deliverable)
Authoritative source: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`
Governed by: `docs\MASTER_REFERENCE_LOCK.md`, `docs\DEVELOPMENT_RULES.md`, `docs\PHASE_17_BACKEND_PRODUCTIZATION.md`, `config\backend_contract.yaml`
Implementation: `frontend/src/{api,components,hooks}/*`, `frontend/src/App.tsx`

**The frontend is a window, not a judge.** Every regulatory decision a user sees was already made by Phases 8-15 and reported honestly by Phase 17. This phase adds exactly one thing: a faithful, evidence-first presentation of that report over HTTP — it never re-decides, never infers, and never fabricates what it cannot see.

---

## A. Objective

`[OFFICIAL SOURCE]` `docs\PHASE_TRACKER.md`'s Phase 18 entry: *"Expose the trustworthy artifacts clearly... All core workflows can be completed through UI only."* Phase 18 builds a React/Vite/TypeScript client that consumes the real, unmodified Phase 17 `POST /api/v1/query` and `GET /health` endpoints and presents their output faithfully.

## B. Scope

In scope: a typed API client (`frontend/src/api/client.ts`, `types.ts`) mirroring the ACTUAL, live-inspected Phase 17 wire schema; a small set of presentation components (query form, status banner, answer, classification/jurisdiction, citations, evidence, human-review, query metadata, error); an explicit request-lifecycle state machine (`IDLE/LOADING/SUCCESS/ABSTAINED/ESCALATED/ERROR`); deterministic, mocked component/unit tests; basic accessibility and responsive layout.

Out of scope (no code for any of these exists anywhere in `frontend/`): re-implementing any Phase 8-15 decision; authentication/authorization; a reviewer workflow UI (Phase 15's `review.workflow.apply_action` is not exposed by any Phase 17 endpoint, so there is nothing to call); state-management libraries (no demonstrated need beyond plain React hooks for one primary screen); a build/deploy pipeline (Phase 20); CI/CD (Phase 22); production security hardening beyond basic client-side input usability checks (Phase 19); observability (Phase 21).

## C. Architecture

`[ENGINEERING RECOMMENDATION]`

```
Browser
  → App.tsx (composition only)
  → hooks/useQueryLifecycle.ts (request-lifecycle state machine)
  → api/client.ts (typed fetch wrapper) → api/outcome.ts (presentation-only status bucketing)
  → components/* (pure presentation - one component per UI area, each reading only backend-returned fields)
```

No component, hook, or client function contains a conditional that DECIDES a domain outcome - `api/outcome.classifyOutcome` is the one function that branches on `safety_status`/`delivery_status`, and it only chooses which UI layout bucket to use (never overrides, recomputes, or contradicts the value it read).

## D. Frontend/Backend Boundary

`[OFFICIAL SOURCE]` Verified by direct, live inspection of the running Phase 17 app (not from memory) before any frontend code was written: `GET /health` and `POST /api/v1/query` are the only two endpoints; the response schema was copied field-for-field from `src/api/schemas.py`/`src/application/models.py`. The frontend never calls, imports, or embeds any Phase 8-15 Python module - it only ever calls the two HTTP endpoints.

## E. API Contract Consumption

`[OFFICIAL SOURCE]` `frontend/src/api/types.ts` is a hand-written TypeScript mirror of `QueryRequest`/`QueryResponse`/`HealthResponse`/`ErrorResponse` (`[ENGINEERING RECOMMENDATION]` - hand-written rather than OpenAPI-codegenerated, to avoid an extra devDependency for a schema this small; see Section N for the trade-off this implies). `frontend/src/api/client.ts` centralizes the base URL (`VITE_API_BASE_URL`, empty by default for same-origin/proxy setups), performs no business logic, and translates every failure mode (HTTP error with a parsed `{detail, error_type}` body, malformed/non-JSON response, network failure) into one typed `ApiError`.

## F. UI Information Architecture

`[ENGINEERING RECOMMENDATION]` One primary screen, matching the ten minimum UI areas: `Header` (identity + non-legal-advice disclaimer), `QueryForm` (multilingual textarea + optional language/jurisdiction pickers mirroring Phase 12/14's own existing vocabularies + submit/clear), `StatusBanner` (safety/grounding/delivery status), `ClassificationJurisdictionPanel`, `AnswerPanel`, `CitationsPanel`, `EvidencePanel`, `ReviewPanel` (rendered only when `review` is non-null), `QueryMetaPanel` (multilingual preservation fields), `ErrorPanel`. Presentation order follows the evidence-first hierarchy from the instructions: query → classification/jurisdiction → answer → citations → evidence → safety/review status.

## G. Evidence/Citation Presentation

`[OFFICIAL SOURCE]` / **DISCLOSED CONTRACT GAP** `[DEFERRED]`

Live inspection of the actual Phase 17 response contract found that it exposes **only**:
- `cited_evidence_ids: string[]` (Phase 10's own already-validated evidence-ID list), and
- `citation_summary` (Phase 9's own aggregate `CitationCoverageMetrics`: `total_references`/`valid_count`/`invalid_count`/`unresolved_count`/`citation_integrity_validation_rate`).

**It does not return, for any individual evidence item: evidence text, source family, jurisdiction tag, or document/chunk/page/block provenance.** This is a genuine backend-contract gap relative to the Phase 18 "Evidence area" wish-list (evidence text/source family/jurisdiction/provenance) - per explicit instruction, Phase 17 (already accepted DONE) was **not** modified to add these fields. `EvidencePanel` renders exactly what is available (the evidence identifier, as an opaque backend-owned string) and displays an explicit, visible notice that further detail is not currently exposed - it never invents evidence text, a source family, or provenance to fill the gap. `CitationsPanel` renders the real aggregate counts and, when `invalid_count + unresolved_count > 0`, states honestly that some citation attempts could not be resolved - **without inventing which specific reference failed**, since the backend does not return that identifier either (docs "CITATION DISPLAY RULES": *"If a citation cannot be resolved to displayed evidence, clearly show it as unresolved rather than inventing information"*). No evidence ID is ever generated, guessed, or mutated by the frontend (`frontend/src/App.test.tsx::"shows no evidence identifiers beyond what the backend returned"`).

## H. Safety-State Presentation

`[OFFICIAL SOURCE]` `api/outcome.classifyOutcome` reads `safety_status`/`delivery_status` (already-decided by Phase 13/14) and buckets the response into `SUCCESS`/`ABSTAINED`/`ESCALATED` for layout purposes only - `ESCALATE` always wins regardless of `delivery_status`; `DELIVERED` + `SAFE_TO_PRESENT` is the only path to `SUCCESS`; everything else (`ABSTAIN`, `UPSTREAM_BLOCKED`, `TRANSLATION_FAILED`, `UNSUPPORTED_LANGUAGE`, `GENERATION_FAILED`, or a missing status) is honestly grouped as "no normal grounded answer" (`ABSTAINED`). `StatusBanner` never presents an abstained/escalated case as a normal successful answer, and `AnswerPanel` never fabricates helpful-looking text when `answer_text` is `null` - it states plainly that no grounded answer was produced.

## I. Multilingual Handling

`[OFFICIAL SOURCE]` The query textarea accepts arbitrary Unicode text (no client-side script/language restriction); the optional "preferred answer language" picker offers exactly Phase 14's own scoped `{en, hi, ta}` vocabulary plus "not specified" - `[ENGINEERING RECOMMENDATION]`, a UI convenience mirroring an already-fixed backend contract, never a new language claim. An unsupported/malformed selection is not blocked client-side - it round-trips through the real backend and is reported however Phase 14 actually reports it (e.g. `UNSUPPORTED_LANGUAGE`). `original_query`/`canonical_query`/`detected_script`/`requested_language`/`answer_language`/`translation_applied` are all rendered verbatim in `QueryMetaPanel`/`AnswerPanel`. **No translation-quality claim is made anywhere in the UI** - this is Phase 14's own disclosed limitation, unchanged. `[DEFERRED]` additional language coverage beyond `{en, hi, ta}` and any live-translation-quality validation remain deferred, exactly as instructed.

## J. Accessibility

`[ENGINEERING RECOMMENDATION]` Semantic HTML throughout (`<header>`, `<main>`, `<section>`, `<form>`, `<dl>`); every form control has an associated `<label htmlFor>`; the submit button exposes `aria-busy` while loading and is `disabled` during the request; the loading indicator uses `role="status" aria-live="polite"`; the error panel uses `role="alert"`; validation errors are associated to the textarea via `aria-describedby`/`aria-invalid`; focus is visible (`:focus-visible` outline in `index.css`). No dedicated accessibility-testing infrastructure (axe-core, automated WCAG scanning) was added - not demonstrated as needed for this phase's scope, and not claimed as a complete accessibility audit.

## K. Testing

`[ENGINEERING RECOMMENDATION]` Vitest + `@testing-library/react` + `@testing-library/user-event` (the standard, Vite-native minimal testing stack - `[ENGINEERING RECOMMENDATION]`, chosen because it needs no separate test runner/config beyond Vite's own `test` block). **30 tests**, all using deterministic, hand-written fixtures shaped exactly like real Phase 17 responses (`frontend/src/test/fixtures.ts`) and a mocked `global.fetch` - no live Gemini/Qwen/Bhashini provider, no real regulatory corpus, no network call anywhere in the suite. Covers, at minimum, every scenario named in the instructions: render, submission invokes the client, loading state, successful/ABSTAIN/ESCALATE rendering, evidence/citation rendering, unresolved-citation honesty, network/HTTP failure rendering, empty-input rejection, English/Hindi/Tamil Unicode round-trip, no-fabrication proof, faithful field rendering, and reset behavior.

## L. Manual Validation

`[ASSUMPTION]` / **NOT VALIDATED**

A real, unmodified Phase 17 backend instance was started and live-verified via HTTP (not mocked) during this phase's implementation: `GET /health` and `POST /api/v1/query` were exercised directly with `curl`/`urllib` against a running `uvicorn` process (with the officially-supported `app.dependency_overrides` mechanism used to inject the existing `FakeGenerationProvider`/`FakeTranslationProvider` test doubles - the same mechanism `tests/test_phase_17_api.py` already uses - never a modification to Phase 17 source), confirming the real response shape matches `frontend/src/api/types.ts` exactly.

**Interactive, in-browser visual verification of the rendered UI was NOT performed in this session** - no browser-automation tool was available/authorized in this environment, and the backgrounded Vite dev server was not reliably reachable across sandboxed tool-call boundaries in this session's shell environment. This is disclosed honestly rather than fabricated: functional correctness (rendering, state transitions, faithful field display, no-fabrication) is instead verified by the 30 automated `jsdom`-based component tests (Section K), which do perform real DOM rendering and CSS-class assertion, plus a successful production build (`vite build`) and lint pass. **Real-browser visual/UX polish (font rendering of Devanagari/Tamil glyphs, responsive breakpoints on an actual device, click-through usability) remains NOT VALIDATED** and should be performed manually by a human before any demo.

## M. Known Limitations

`[ENGINEERING RECOMMENDATION]`, disclosed, not hidden:
1. Per-evidence detail (text/source family/jurisdiction/provenance) is not shown because it is not returned by the current Phase 17 contract (Section G) - a disclosed backend-contract gap, not a frontend defect.
2. The specific unresolved/invalid citation reference cannot be shown (only the aggregate count) for the same reason.
3. Interactive browser-based visual validation was not performed in this session (Section L) - `NOT VALIDATED`.
4. Hand-written TypeScript types (Section E) can drift from the backend schema if Phase 17 changes without a corresponding frontend update - no automated schema-drift check (e.g. OpenAPI-diff) exists in this phase.
5. Against the unmodified backend (no live `GenerationProvider`, no ingested corpus - Phase 17's own disclosed state), every real query currently returns either HTTP 503 or an `ABSTAIN`/`UPSTREAM_BLOCKED` result - this is expected and was not worked around by fabricating a fake success path in the frontend.

## N. Deferred Items

`[DEFERRED]`: exposing per-evidence detail/provenance and per-citation unresolved identifiers (requires a Phase 17 contract amendment, out of this phase's scope); a reviewer-action UI (requires a Phase 17 endpoint that does not exist); authentication; additional language coverage beyond `{en, hi, ta}`; live-translation-quality UX; OpenAPI-schema-driven type generation; automated accessibility scanning; automated visual regression testing; real-browser interactive QA (Section L).

## O. Source/Evidence Audit

`[OFFICIAL SOURCE]` Every field name in `frontend/src/api/types.ts` was verified against the ACTUAL contents of `src/api/schemas.py` and `src/application/models.py` at inspection time (Step 1 of this phase's implementation), never assumed from `docs/PHASE_17_BACKEND_PRODUCTIZATION.md` prose alone or from memory. The frontend never fabricates an Evidence ID, a source URL, a citation, or a jurisdiction/classification/safety value anywhere - verified directly by `frontend/src/App.test.tsx`'s no-fabrication tests (Section G).

## P. Phase-Boundary Audit

`[ENGINEERING RECOMMENDATION]` No authentication/authorization code, no rate limiting, no prompt-injection defense, no deployment configuration (Docker/Kubernetes), no observability (Prometheus/Grafana), no CI/CD pipeline, no database/persistence, no Redis/Celery, no live Gemini/Qwen/Bhashini integration, no new retrieval/classification/jurisdiction/citation/safety logic, no agent framework, no knowledge graph, and no semantic-entailment code exists anywhere in `frontend/`. `frontend/` contains zero Python imports and zero references to any `src/` module - confirmed by direct inspection.

## Q. Acceptance Criteria

`[OFFICIAL SOURCE, as restated for this implementation]` The frontend consumes the real Phase 17 API without modifying it; it never becomes the authority for classification/jurisdiction/evidence selection/citation validation/confidence/safety/abstention/legal conclusions (every such value is read-only, sourced from the API response); ABSTAIN/ESCALATE are never presented as a normal successful answer; citation/evidence identifiers are never fabricated, and an unresolved citation is shown honestly rather than invented; Unicode (English/Hindi/Tamil) round-trips correctly; the request lifecycle is explicit (`IDLE/LOADING/SUCCESS/ABSTAINED/ESCALATED/ERROR`) and never silently upgrades a backend abstention/escalation to success; basic accessibility and responsive layout are implemented; the frontend test suite (30 tests), production build, and lint all pass; the full backend/repository test suite (2868 tests) remains unaffected and passing; source-discipline and phase-boundary audits pass. **MET**, with the disclosed exceptions in Section M (a backend contract gap and an un-performed interactive browser check), neither of which is a Phase 18 implementation defect.
