# PHASE 17 — BACKEND PRODUCTIZATION

Status: CONTRACT + IMPLEMENTATION DOCUMENT (Phase 17 deliverable)
Authoritative source: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`
Governed by: `docs\MASTER_REFERENCE_LOCK.md`, `docs\DEVELOPMENT_RULES.md`, `docs\PHASE_10_GROUNDED_GENERATION.md`, `docs\PHASE_11_FORMULATION_CLASSIFICATION.md`, `docs\PHASE_12_JURISDICTION_FIREWALL.md`, `docs\PHASE_13_CONFIDENCE_SAFETY_ABSTENTION.md`, `docs\PHASE_14_MULTILINGUAL_DELIVERY.md`, `docs\PHASE_15_HUMAN_IN_THE_LOOP.md`
Machine-readable counterpart: `config\backend_contract.yaml`
Implementation: `src\api\{app,routes,schemas,errors,dependencies}.py`, `src\application\{config,models,service}.py`

**FastAPI is a boundary, not a brain.** Every regulatory decision in this system was already made by Phases 8-15 before Phase 17 existed. This phase adds exactly one thing: a way to reach that existing decision-making machinery over HTTP, and to report its real, honest output back to a caller — without ever re-deciding, faking, or silently overriding anything it reports.

---

## A. Objective

`[OFFICIAL SOURCE]` `docs\PHASE_TRACKER.md`'s Phase 17 entry: *"Turn research modules into a maintainable service... Core workflows run through stable APIs without notebook/manual steps."* Phase 17 converts the validated Phase 0-16 domain components into a coherent backend application boundary — an orchestration layer, never a reimplementation.

## B. Scope

In scope: a FastAPI transport boundary (`GET /health`, `POST /api/v1/query`); Pydantic request/response wire schemas; an `ApplicationService` orchestrator that calls the real Phase 11/12/(retrieval+evidence)/10/13/14/15 APIs in sequence; explicit error mapping; an explicit configuration boundary (environment/application, provider objects kept separate); a deterministic, non-Evidence-ID application request identity.

Out of scope (no code for any of these exists anywhere in `src\api\`/`src\application\`): re-implementing any Phase 8-15 decision; a live Gemini/Qwen/Bhashini adapter (Phase 10/14's own `[DEFERRED]` boundary, unchanged); authentication/authorization; persistence of any kind; a reviewer UI, corpus administration, retraining, or analytics endpoints; a React/Vite frontend (Phase 18); Docker/Kubernetes/cloud deployment (Phase 20); Prometheus/Grafana/tracing (Phase 21); CI/CD (Phase 22); full project-wide adversarial hardening (Phase 19); production validation (Phase 23).

## C. Non-Scope

`[ENGINEERING RECOMMENDATION]` Explicitly, Phase 17 does not make the system production-ready. It does not claim authentication, authorization, persistence, throughput, latency, uptime, scalability, cloud infrastructure, legal authority, or regulatory correctness — none of these is implemented, measured, or claimed anywhere in this phase.

## D. Architecture

`[ENGINEERING RECOMMENDATION]` Four layers, matching the target diagram exactly:

```
HTTP → src/api/routes.py (FastAPI) → src/api/schemas.py (Pydantic)
     → src/application/service.ApplicationService (orchestrator)
     → real Phase 8-15 modules (unmodified) → src/application/models (result dataclasses)
     → src/api/schemas.py (response conversion) → HTTP response
```

`src/application/` contains **zero** FastAPI/Pydantic imports — it is plain-dataclass Python, fully testable without HTTP (Section AD). `src/api/` contains **zero** business rules — every `if` statement touching a domain value (`jurisdiction`, `classification_state`, `safety_status`, an evidence_id) lives inside the Phase 8-15 modules it calls, never in a route handler.

## E. FastAPI Boundary

`[OFFICIAL SOURCE]` FastAPI handles exactly what the instructions name: HTTP request parsing, Pydantic schema validation, response serialization, HTTP status mapping (`src/api/errors.py`), dependency wiring (`src/api/dependencies.py`), exception translation, and OpenAPI documentation (generated automatically, verified in Section AC). It never decides jurisdiction, regulatory category, evidence validity, citation validity, safety, grounding, or reviewer authorization — `tests/test_phase_17_regression.py` asserts structurally that `src/api/` never imports a decision-making function from `classification`/`jurisdiction`/`citation`/`safety`/`generation`, only `application.service`.

## F. Application Service

`[ENGINEERING RECOMMENDATION]` `application.service.ApplicationService.query(request)` is the sole orchestrator: `multilingual.preservation.build_input_context` → `classification.classifier.classify` → `jurisdiction.firewall.resolve_jurisdiction` → an injected `evidence_pack_builder` (retrieval + `evidence.builder.build_evidence_pack`) → `generation.generator.generate_grounded_response` (itself calling Phase 9 citation validation internally) → `safety.evaluator.evaluate_safety` → `multilingual.delivery.deliver_response` → `review.policy.build_review_request`. Every call uses the real, unmodified Phase function — none is re-implemented, none is skipped.

**Honesty about what is actually executable (docs "APPLICATION ORCHESTRATOR"):** this repository has no ingested authoritative corpus (confirmed by every prior phase's own regression check — no corpus document files exist anywhere except the Master Reference PDF itself). `default_evidence_pack_builder` therefore returns a REAL, honestly EMPTY Phase 8 `EvidencePack` for every query — this is not a fake pipeline, it is the real "no evidence" path Phase 10/13/16 already tested exhaustively, driving a real `ABSTAIN`. A real retrieval index can be wired in later by supplying a different `evidence_pack_builder` callable, with no change to this module. Similarly, no live `GenerationProvider` exists anywhere in this repository (Phase 10's own `[DEFERRED]` boundary) — `ApplicationService.query` raises `GenerationProviderNotConfiguredError` (mapped to HTTP 503) immediately if none is configured, rather than silently substituting a provider or fabricating an answer.

## G. Domain/API Separation

`[OFFICIAL SOURCE]` No route handler, schema, or error mapper anywhere in `src\api\` contains a conditional on a domain value (`if jurisdiction == "INDIA"`, `if safety_status == ...`, `if evidence_id.startswith(...)`) — verified structurally by `tests\test_phase_17_regression.py`. Every such rule lives inside its owning Phase 8-15 module.

## H. API Versioning

`[ENGINEERING RECOMMENDATION]` A single explicit version, `v1` (`application.config.API_VERSION`), used as the `/api/v1/...` path prefix. No API stability guarantee is made — this is an internal-development boundary, not a versioned public contract. A second version is not introduced because nothing yet requires one.

## I. Health Endpoint

`[ENGINEERING RECOMMENDATION]` `GET /health` verifies only that the process is alive and reports two STATIC facts: whether a `GenerationProvider`/`TranslationProvider` is configured (a cheap attribute check, never a live call to either), and `corpus_status`, which is **always** `"NOT_VALIDATED"` — no corpus is ingested anywhere in this repository, and this endpoint never claims otherwise. No retrieval, model, or network call is performed by this endpoint.

## J. Query Endpoint

`[ENGINEERING RECOMMENDATION]` `POST /api/v1/query` is the single primary product endpoint (docs "CORE ENDPOINTS" — the minimum product boundary). No authentication, user-management, reviewer-dashboard, corpus-administration, ingestion, retraining, analytics, or benchmark endpoint exists anywhere in `src\api\` — each would require a capability explicitly deferred (Section B).

## K. Request Contract

`[ENGINEERING RECOMMENDATION]` `api.schemas.QueryRequest`: `query` (required, 1-20,000 characters at the wire level), `requested_language`/`jurisdiction`/`source_language` (optional, untrusted passthrough strings — validity is decided downstream by Phase 12/14's own real logic, never re-validated or re-encoded here), `formulation_description` (optional, passed to Phase 11). No field duplicates Phase 11/12 logic (no `jurisdiction_input` re-derivation, no classification-state field a client could set).

## L. Response Contract

`[ENGINEERING RECOMMENDATION]` `api.schemas.QueryResponse` exposes: `answer_text`/`answer_language`/`translation_applied`/`delivery_status` (Phase 14), `grounding_status`/`cited_evidence_ids`/`citation_summary` (Phase 10/9), `safety_status` (Phase 13), `classification`/`jurisdiction` summaries (Phase 11/12), `review` (Phase 15, `None` when no trigger fired), `original_query`/`canonical_query`/`detected_script` (Phase 14 preservation). Every field is a **direct passthrough** from `application.models.ApplicationQueryResult`, itself a direct passthrough from the real upstream objects — there is no code path anywhere that derives a response field from client input or from `answer_text` itself. No internal implementation class (`ReviewAction`, `EvidencePack`, `GroundedResponse`, ...), filesystem path, or credential is ever exposed (verified directly against the generated OpenAPI schema, `tests\test_phase_17_serialization.py`/`test_phase_17_security.py`). The response is a plain JSON object with no framework-specific shape — designed to be consumed by any client, never around React specifically (Phase 18's own concern).

## M. Error Handling

`[ENGINEERING RECOMMENDATION]` `src/api/errors.py` registers four handlers, each returning a safe `{"detail": ..., "error_type": ...}` body: `RequestValidationError`/`InvalidQueryError`/`ApplicationSchemaError` → HTTP 422 (client/input problem); `GenerationProviderNotConfiguredError` → HTTP 503 (an explicit, named application/domain failure — never a silent 200); any other `Exception` → HTTP 500 with a **generic, sanitized** message (`"internal server error"`) — the real exception is logged server-side only (Python `logging`, never returned to the client) and no Python traceback, exception message, or filesystem path ever reaches the response body (`tests\test_phase_17_errors.py` proves this directly with adversarial exception messages containing fake credentials/paths).

## N. Safety Semantics

`[OFFICIAL SOURCE]` The HTTP status and the domain status never contradict each other. HTTP 200 means *"the pipeline ran to completion and produced a well-defined outcome"* — `delivery_status` in the body (`DELIVERED`/`UPSTREAM_BLOCKED`/`TRANSLATION_FAILED`/`UNSUPPORTED_LANGUAGE`, Phase 14's own closed vocabulary) is always the honest, direct report of what actually happened. An `ABSTAIN`/`ESCALATE` `SafetyDecision` is never presented as `DELIVERED`; `UPSTREAM_BLOCKED` always carries `answer_text=None`. HTTP 4xx/5xx are reserved for actual request/server failures, never for a legitimate domain outcome. No "legal advice" status exists anywhere in this vocabulary.

## O. Citation Handling

`[OFFICIAL SOURCE]` `citation_summary` is `Phase 9`'s own `CitationCoverageMetrics`, reached through `GroundedResponse.citation_validation_summary`, reused verbatim (`application.service._citation_summary`) — never recomputed, never generated inside FastAPI. `cited_evidence_ids` is `MultilingualDeliveryResult.cited_evidence_ids`, itself Phase 10's own already-validated list — a fabricated evidence ID embedded in provider output can never appear in it (`tests\test_phase_17_security.py::test_fake_citation_in_provider_output_never_becomes_a_cited_evidence_id`).

## P. Evidence Handling

`[OFFICIAL SOURCE]` No endpoint accepts a client-supplied Evidence ID as trusted (`QueryRequest` has no such field, asserted directly). No endpoint can mutate an `EvidencePack` — there is no `POST /evidence/edit` or equivalent anywhere in `src\api\` (`tests\test_phase_17_security.py::test_no_evidence_mutation_endpoint_exists`). Corpus management is entirely out of this phase's scope.

## Q. Jurisdiction Handling

`[OFFICIAL SOURCE]` The client may supply `jurisdiction` per Phase 12's own `explicit_jurisdiction` contract, but `src/api/` contains no jurisdiction logic of any kind — every request calls `jurisdiction.firewall.resolve_jurisdiction` unchanged. A malformed value (`"totally-fake-value"`) fails closed to `UNKNOWN`, exactly like Phase 12's own real behavior — never rejected as a 4xx, never silently trusted. Jurisdiction is never inferred from IP address, browser locale, language, physical location, or timezone — no code path in this phase reads any of those signals at all.

## R. Classification Handling

`[OFFICIAL SOURCE]` FastAPI never classifies formulations — every request calls `classification.classifier.classify` unchanged, and the result is summarized (`application.models.ClassificationSummary`) never re-derived. No second, API-specific classifier exists anywhere in `src\api\`/`src\application\`.

## S. Multilingual Handling

`[OFFICIAL SOURCE]` The response exposes `original_query`, `canonical_query`, `detected_script`, `requested_language`, `answer_language`, `translation_applied`, and `delivery_status` — all Phase 14's own fields, verbatim. No translation-quality claim is made anywhere (Phase 14's own `FakeTranslationProvider`-only limitation, unchanged). No silent language fallback exists — an unsupported language is reported `UNSUPPORTED_LANGUAGE`, never silently served in English or any other language.

## T. Human-Review Handling

`[OFFICIAL SOURCE]` The response exposes a `review` object (`review_request_id`/`trigger_reasons`/`priority`/`review_status`) only when Phase 15's own `build_review_request` actually fires — `None` otherwise, never fabricated. No reviewer UI, authentication, or persistence exists anywhere in `src\api\`/`src\application\` — a reviewer acting on this `review_request_id` remains entirely out of this phase's scope (Phase 15's own workflow, `review.workflow.apply_action`, is not exposed through any endpoint here).

## U. Configuration

`[ENGINEERING RECOMMENDATION]` Three explicitly separate concerns (`application/config.py`): `EnvironmentConfig` (environment-variable-derived only — currently just `IPSAKTI_CORS_ALLOWED_ORIGINS`), `ApplicationConfig` (explicit knobs: `api_version`, `max_query_length`, `max_formulation_description_length`), and provider objects (`GenerationProvider`/`TranslationProvider`/`evidence_pack_builder`), which are **not** configuration at all — they are explicit Python objects constructed by the caller and passed directly to `ApplicationService`, never resolved "by magic" from an environment value. No secret, API key, token, password, or credential is read, stored, or exposed anywhere in this module — none is needed, since no live provider adapter exists (Section F).

## V. Provider Boundaries

`[OFFICIAL SOURCE]` `generation_provider`/`translation_provider` are explicit constructor arguments on `ApplicationService` — never silently chosen, guessed, or substituted. The real, running app (`api/dependencies.get_application_service`) constructs an `ApplicationService` with `generation_provider=None` by default (the honest current state of this repository); a caller wanting a different provider passes one in explicitly (production wiring) or overrides the FastAPI dependency (tests). If a required provider is absent, the API returns an explicit HTTP 503 — never a fabricated answer.

## W. Persistence Status

`[DEFERRED]` No database, ORM, or persistent storage exists anywhere in this phase. The Master Reference's own SQLite → PostgreSQL direction (`docs\MASTER_REFERENCE_LOCK.md` Section E) remains an eventual product/deployment concern — Phase 17 is fully stateless: every `ApplicationService.query` call is independent, with no shared mutable state across requests beyond the (also stateless) `lru_cache`-memoized `BackendConfig`.

## X. Request Identity

`[ENGINEERING RECOMMENDATION]` `application.service.compute_request_id` is a deterministic SHA-256 hash over the request's own canonical fields (`query`, `requested_language`, `jurisdiction`, `formulation_description`, `source_language`), namespaced `"api-query-request-v1"` — never a random UUID, never a timestamp, and (CRITICAL, verified structurally) never equal to, derived from, or usable as an Evidence ID (Phase 8), a Document ID (Phase 3), a Review Request ID (Phase 15), or a `GroundedResponse.response_id` (Phase 10) — each of those five identity domains uses a completely separate canonical-string namespace in its own phase's own identity function, and this module never imports another phase's identity-computation function.

## Y. Logging

`[ENGINEERING RECOMMENDATION]` `src/api/errors.py` logs unhandled exceptions server-side via Python's standard `logging` module (`logger.exception(...)`) — for debugging only, never returned to a client. No user input, secret, or full request payload is logged unnecessarily. This is not Phase 21's observability stack (no metrics backend, no log aggregation, no distributed tracing) and makes no claim of complete audit logging.

## Z. Input Limits

`[OUR ENHANCEMENT]` Two explicit, documented tiers (Section K): a coarse wire-level bound (`_WIRE_MAX_LENGTH = 20,000` characters, Pydantic `Field(max_length=...)`) rejects obviously oversized payloads before they reach the application layer; the real, configurable business limit (`ApplicationConfig.max_query_length`, default 4,000) is enforced once, inside `ApplicationService.query`. Neither claims complete DoS protection — Phase 19 owns broader security hardening.

## AA. CORS

`[ENGINEERING RECOMMENDATION]` CORS middleware is added **only** when `IPSAKTI_CORS_ALLOWED_ORIGINS` is explicitly set (a comma-separated origin list) — the default app has no CORS middleware at all, never an unrestricted wildcard (`allow_origins=["*"]` is never used anywhere in this codebase). This is a local-development convenience, not a production security posture.

## AB. Security Boundary

`[ENGINEERING RECOMMENDATION]` `tests/test_phase_17_security.py` (14 tests) verifies: no client field can set `safety_status`/`grounding_status`/`cited_evidence_ids`/`delivery_status`/`review_status` directly (no such request field exists); a malformed/fake jurisdiction value fails closed rather than being trusted; a fabricated evidence ID in provider output never becomes a cited ID; no evidence- or reviewer-mutation endpoint exists anywhere; malformed JSON and oversized payloads are rejected (422); prompt-injection text in the query is preserved as inert data, never interpreted; the OpenAPI schema exposes no credential-shaped text and no internal filesystem path. This is a workflow-level boundary, not Phase 19's complete adversarial hardening — no claim of complete application security is made.

## AC. OpenAPI

`[OFFICIAL SOURCE]` FastAPI generates the OpenAPI schema automatically — nothing in this phase hand-duplicates it. `tests/test_phase_17_serialization.py` verifies directly: both endpoints are present, `QueryRequest`/`QueryResponse`/`HealthResponse` appear in `components.schemas`, the query endpoint documents a request body and a `200` response, and no internal domain class (`ReviewAction`, `EvidencePack`, `GroundedResponse`, `SafetyDecision`, `ClassificationResult`, `JurisdictionDecision`) is exposed as a schema component.

## AD. Testing

`[ENGINEERING RECOMMENDATION]` `ApplicationService` is fully testable without a network server — every `tests/test_phase_17_application.py` test constructs it directly with `FakeGenerationProvider`/`FakeTranslationProvider` (Phase 10/14's own deterministic, offline test doubles) and a plain Python `evidence_pack_builder` callable. HTTP-level tests use FastAPI's own `TestClient` (in-process ASGI calls, no real socket) with `app.dependency_overrides` to inject the same fakes. No test anywhere in `tests/test_phase_17_*.py` touches the internet, a GPU, or a real API key.

## AE. Dependency Policy

`[ENGINEERING RECOMMENDATION]` Inspection found `fastapi` (0.136.0), `pydantic` (2.13.2), `uvicorn` (0.42.0), and `httpx` (0.28.1, transitively required by FastAPI's own `TestClient`) already installed and working in this environment — none was blindly upgraded to a newer release; each is pinned to its actually-verified-working version range in `requirements-dev.txt` (`fastapi>=0.136,<0.137` by minor, since FastAPI is still pre-1.0; `pydantic>=2,<3` by major, matching this project's own numpy/faiss-cpu convention; `uvicorn>=0.42,<0.43`; `httpx>=0.28,<0.29`, test-only). No ORM, database driver, authentication framework, task queue, Redis, Celery, message broker, or monitoring stack was added — none is required by any existing contract.

## AF. Known Limitations

`[ENGINEERING RECOMMENDATION]`, disclosed, not hidden:
1. `default_evidence_pack_builder` always returns an empty `EvidencePack` — every real query against the unmodified app currently reaches `ABSTAIN`/`UPSTREAM_BLOCKED`, honestly, since no corpus is ingested (Section F).
2. `ApplicationService.query()` always raises `GenerationProviderNotConfiguredError` against the unmodified app — a real deployment needs a real `GenerationProvider` wired in via `api/dependencies.py`, which does not exist in this repository (Phase 10's own `[DEFERRED]` boundary).
3. No load, latency, throughput, or concurrency characteristic is measured anywhere in this phase — `NOT VALIDATED`.
4. `ApplicationConfig`'s knobs (`max_query_length`, etc.) are `[OUR ENHANCEMENT]` defaults, not derived from any upstream contract or real capacity measurement.

## AG. Deferred Work

`[DEFERRED]`: a live Gemini/Qwen/Bhashini adapter and its FastAPI dependency wiring; a real retrieval-backed `evidence_pack_builder`; authentication/authorization; persistence; a reviewer workflow endpoint (`review.workflow.apply_action` remains unexposed); rate limiting beyond the simple input-size guard; complete adversarial security hardening (Phase 19); deployment packaging (Phase 20); observability (Phase 21); CI/CD (Phase 22); production validation (Phase 23).

## AH. Phase 18 Boundary

`[ENGINEERING RECOMMENDATION]` No React/Vite code, no frontend component, and no UI-specific response shaping exists anywhere in `src\api\`/`src\application\` — the response schema is deliberately client-agnostic (Section L). Phase 18 consumes this API; it does not extend or modify it as part of this phase.

## AI. Acceptance Gate

`[OFFICIAL SOURCE, as restated for this implementation]` CAP-17's text — *"Core workflows run through stable APIs without notebook/manual steps"* — is met as follows: `GET /health` and `POST /api/v1/query` are both implemented, tested, and documented via OpenAPI; every domain decision is delegated to the real, unmodified Phase 8-15 modules; the application service is testable without HTTP; error handling distinguishes 422/503/500 and never leaks internal detail; safety/grounding/citation/evidence identity are all preserved end-to-end, proven adversarially; no secret is committed; no unnecessary persistence, frontend, deployment, observability, or CI/CD exists anywhere in this phase. **MET.**

## AJ. Validation Evidence

`pytest tests/ -v` run twice — see the Phase 17 implementation report for the exact pass counts of both runs. Zero skips, zero xfail, zero weakened assertions anywhere in `tests\test_phase_17_*.py`. Phase 0-16 regression, Master Reference hash integrity, source-discipline audit, and phase-boundary audit (no React/Vite/Docker/Kubernetes/Prometheus/CI-CD/production-validation code, fields, or imports anywhere in `src\api\`/`src\application\`) all pass — see `tests\test_phase_17_regression.py`.
