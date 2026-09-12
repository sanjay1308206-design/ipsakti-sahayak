# PHASE 20 — DEPLOYMENT ENGINEERING

Status: CONTRACT + IMPLEMENTATION DOCUMENT (Phase 20 deliverable, written retroactively against work already present in the repository)
Authoritative source: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`
Governed by: `docs\MASTER_REFERENCE_LOCK.md`, `docs\DEVELOPMENT_RULES.md`, `docs\PHASE_17_BACKEND_PRODUCTIZATION.md`, `docs\PHASE_18_FRONTEND_PRODUCTIZATION.md`, `docs\PHASE_19_SECURITY_ADVERSARIAL_HARDENING.md`
Implementation: `render.yaml`, `requirements-render.txt`, `.python-version`, `frontend\.node-version`
Tests: `tests\test_phase_20_deployment.py` (16 tests)

**This document describes only what Phase 20 has actually built: a version-controlled Render Free deployment configuration for the existing, unmodified Phase 17 backend and Phase 18 frontend.** It adds no new domain logic, no new dependency beyond what deployment requires, and no live external-provider integration. Where this document differs from `docs\PHASE_TRACKER.md`'s original one-line Phase 20 description, that difference is disclosed explicitly (Section 1) rather than silently overwritten.

---

## 1. Objective

`[OFFICIAL SOURCE]` `docs\PHASE_TRACKER.md`'s Phase 20 entry: goal *"Make the system reproducible across laptop, SIH, and larger environments"*; acceptance gate *"Fresh environment can be provisioned and started without source edits."*

`[ENGINEERING RECOMMENDATION]` **Disclosed deviation from the tracker's original implementation sketch:** the tracker's Phase 20 row lists "Docker/Compose profiles... database migration... model provisioning" as its implementation plan. What was actually built instead is a **Render Blueprint** (`render.yaml`) targeting Render's native Python-web-service and static-site runtimes directly — no Docker, no Compose, no database, no model-provisioning step exists anywhere in this phase. This is a deliberate substitution, not an oversight: Render Free natively builds and runs a Python `pip install` + `uvicorn` process and a static-site build without a container layer, so Docker was not determined necessary for a ₹0-cost demo target (`render.yaml`'s own header comment; enforced structurally by `tests\test_phase_20_deployment.py::test_no_docker_or_procfile_artifacts_were_introduced` and `::test_render_yaml_declares_exactly_two_free_services_no_database_no_docker`). `docs\PHASE_TRACKER.md` itself has **not** been updated to reflect this — its Phase 20 row still reads "NOT STARTED" as of this document's writing; that is a known, disclosed documentation gap, not something this document silently papers over.

The objective actually met: a reproducible, version-controlled description of how to host the real Phase 17 API and Phase 18 UI on a free hosting tier, provisionable without editing any source file — only Render-dashboard-supplied environment variable values are needed afterward (Section 8).

## 2. Scope

`[ENGINEERING RECOMMENDATION]` In scope: `render.yaml` (a two-service Render Blueprint); `requirements-render.txt` (a minimal, separately-maintained Python runtime dependency file for the backend service only); `.python-version` and `frontend\.node-version` (interpreter/runtime version pins, consumed both directly by local tooling and by `render.yaml`'s own `PYTHON_VERSION`/`NODE_VERSION` env vars); `tests\test_phase_20_deployment.py` (16 static configuration-shape tests).

Out of scope (no code or config for any of these exists anywhere introduced by this phase): Docker/Kubernetes/Compose; a database or persistence layer of any kind; CI/CD pipelines (Phase 22); observability/metrics/log-aggregation/backup-restore (Phase 21); a live Gemini/Qwen/Bhashini provider adapter or its wiring (Phase 10/14's own `[DEFERRED]` boundary — unchanged, and explicitly not promoted by this phase, see Section 13); authentication/authorization or rate limiting beyond what Phase 17/19 already built; corpus ingestion, indexing, or automatic refresh; any change to `src\api\`, `src\application\`, or any Phase 0–19 domain module.

## 3. Deployment target

`[EXTERNAL RESEARCH]` Render.com, Free tier, described declaratively via Render's own Blueprint spec (`render.yaml` at the repository root). Field names and structure were verified against Render's own documentation at implementation time (cited directly in `render.yaml`'s header): `render.com/docs/blueprint-spec`, `render.com/docs/web-services`, `render.com/docs/static-sites`, `render.com/docs/health-checks`, `render.com/docs/python-version`, `render.com/docs/node-version`.

`[ENGINEERING RECOMMENDATION]` A Blueprint is optional — Render also supports dashboard/CLI/API-only service creation — but was chosen because it gives a reproducible, version-controlled description of both services, matching this phase's objective (Section 1).

## 4. Backend deployment configuration

`[ENGINEERING RECOMMENDATION]` Service `ipsakti-backend` in `render.yaml`: `type: web`, `runtime: python`, `plan: free`, `rootDir: .`.
- **Build:** `pip install -r requirements-render.txt` — deliberately never `requirements-dev.txt` (`tests\test_phase_20_deployment.py::test_render_yaml_backend_service_uses_the_approved_start_command_and_health_path` asserts `"requirements-dev.txt" not in backend["buildCommand"]`).
- **Start:** `uvicorn api.app:app --host 0.0.0.0 --port $PORT --app-dir src` — `api.app:app` matches `src\api\app.py`'s module-level `app = create_app()` (`docs\PHASE_17_BACKEND_PRODUCTIZATION.md` Section D/E); `--app-dir src` makes `src\` the import root, the same mechanism `tests\conftest.py` already uses for local test collection; `--host 0.0.0.0 --port $PORT` is Render's own documented requirement for a web service (`[EXTERNAL RESEARCH]`, `render.com/docs/web-services`). No change was made to `src\api\app.py` to hardcode a port or call `uvicorn.run()` — the start command is configured entirely externally (`tests\test_phase_20_deployment.py::test_src_api_app_py_was_not_modified_to_add_port_or_uvicorn_run`).
- **Health check:** `healthCheckPath: /health` (Section 10).

## 5. Frontend deployment configuration

`[ENGINEERING RECOMMENDATION]` Service `ipsakti-frontend` in `render.yaml`: `type: web`, `runtime: static`, `rootDir: frontend`.
- **Build:** `npm ci && npm run build`.
- **Publish:** `staticPublishPath: ./dist` — the real Vite build output directory Phase 18 already produces, unmodified.
No frontend source file was changed by this phase; Phase 20 only describes how the existing, already-tested Phase 18 build output gets hosted.

## 6. Runtime dependency boundary

`[ENGINEERING RECOMMENDATION]` `requirements-render.txt` is deliberately separate from and smaller than `requirements-dev.txt`, and is never modified to match it exactly — it contains only what the deployed backend's actual import graph needs at startup, proven by direct inspection rather than assumption (the file's own header documents the exact import chain for each package).

Current exact declared set (`EXPECTED_RENDER_DEPENDENCIES` in `tests\test_phase_20_deployment.py`, asserted as an exact-match, not a subset):
`fastapi`, `pydantic`, `uvicorn`, `numpy`, `faiss-cpu`, `pyyaml`.

`[OUR ENHANCEMENT]` `numpy`, `faiss-cpu`, and `pyyaml` were added only after two real, observed Render deployment failures (`ModuleNotFoundError: numpy`, then `ModuleNotFoundError: yaml`) — not speculatively. The confirmed import chain: `api.app → api.routes → application.service` imports `evidence.builder` at module level, which imports `retrieval.models`; importing any name from a package always executes that package's `__init__.py` first, so importing from `retrieval` unconditionally runs `retrieval\embeddings.py`'s top-level `import numpy` and `retrieval\faiss_index.py`'s top-level `import faiss`, and `faiss_index.py`'s own `from chunking.models import Chunk` in turn cascades through `chunking\__init__.py → chunker.py → ingestion\models.py → ingestion\__init__.py → pipeline.py → admission.py`'s top-level `import yaml` — even though `evidence\builder.py` itself only ever uses the stdlib-only `retrieval.models` types and never calls anything embedding/FAISS-related. No source file was changed to make either fix; only the dependency manifest was corrected, twice, against the actual (not assumed) import graph.

Explicitly forbidden (`FORBIDDEN_RENDER_DEPENDENCIES`, asserted disjoint from the declared set): `pytest`, `pypdf`, `sentence-transformers`, `httpx`, `torch`, `transformers` — each verified test-only or lazily-imported (inside a function or a load method, never at module top level), so none is reachable from the deployed app's startup or default request path.

`[ENGINEERING RECOMMENDATION]` **No live-generation SDK is part of this dependency closure.** `google-genai` (or any other LLM-provider SDK) is not declared in `requirements-render.txt`. This is consistent with, not a change to, Phase 10's own `[DEFERRED]` live-provider boundary (`docs\PHASE_10_GROUNDED_GENERATION.md` Section M) — the deployed backend's own `api\dependencies.get_application_service` constructs its `ApplicationService` with `generation_provider=None` (`docs\PHASE_17_BACKEND_PRODUCTIZATION.md` Section V, unchanged), so `POST /api/v1/query` on this deployment returns HTTP 503 rather than a generated answer, exactly as Phase 17 already documented. Phase 20 does not promote, wire in, or otherwise change this.

`[ENGINEERING RECOMMENDATION]` Where a package is shared between `requirements-dev.txt` and `requirements-render.txt` (all six of the above), its version-range pin must be byte-identical in both files — never a silently different, unverified range (`tests\test_phase_20_deployment.py::test_requirements_render_pins_match_requirements_dev_pins`). `requirements-dev.txt` itself is asserted completely unmodified by this phase (`::test_requirements_dev_txt_is_completely_unmodified_by_phase_20`).

## 7. Python and Node version pins

`[ENGINEERING RECOMMENDATION]` `.python-version` (repository root) pins `3.10.11`; `frontend\.node-version` pins `24.14.0`. Both are consumed twice: locally by any version-manager tooling that reads these conventional files, and explicitly inside `render.yaml` as the `PYTHON_VERSION`/`NODE_VERSION` environment variables on each respective service — `[EXTERNAL RESEARCH]`, the mechanism Render's own documentation names (`render.com/docs/python-version`, `render.com/docs/node-version`) for pinning a Render build's language runtime version. `tests\test_phase_20_deployment.py` asserts both pin files exist and match a plausible version-string shape (`test_python_version_pin_file_exists_and_is_a_plausible_version`, `test_frontend_node_version_pin_file_exists_and_is_a_plausible_version`) — it does not assert the pin files and `render.yaml`'s literal `PYTHON_VERSION`/`NODE_VERSION` values stay byte-identical to each other; that consistency is currently maintained by hand, not test-enforced.

## 8. Environment-variable/secrets handling

`[ENGINEERING RECOMMENDATION]` Exactly two environment variables are declared across both services, and both use Render's `sync: false` mechanism (`[EXTERNAL RESEARCH]`, Blueprint spec) — meaning no `value:` is set in `render.yaml` at all; each must be filled in manually via the Render dashboard/CLI **after** both services exist and their real `*.onrender.com` URLs are known:
- Backend `IPSAKTI_CORS_ALLOWED_ORIGINS` (Section 9).
- Frontend `VITE_API_BASE_URL` — `frontend\src\api\client.ts` already reads this (Phase 18); Vite bakes `VITE_`-prefixed variables into the static build at **build time**, not read at runtime (`[EXTERNAL RESEARCH]`, `vite.dev/guide/env-and-mode`), so the frontend's first real build must happen (or be re-triggered) only after the backend service's URL is known — documented directly in `render.yaml`'s own "ORDERING NOTE".

`tests\test_phase_20_deployment.py::test_render_yaml_cors_and_api_base_url_vars_are_manually_set_not_hardcoded` asserts both vars carry `sync: false` and no `value` key. `::test_render_yaml_never_hardcodes_a_backend_or_frontend_url_or_a_secret` asserts no `onrender.com` URL and no secret-shaped literal (`api_key=`, `password:`, etc.) appears anywhere in `render.yaml` outside its own explanatory comments.

`[ENGINEERING RECOMMENDATION]` No credential, API key, or token is declared anywhere in `render.yaml` or `requirements-render.txt` — none is needed, since no live external provider is wired into the deployed app (Section 6).

## 9. CORS configuration

`[OFFICIAL SOURCE]` Unchanged from Phase 17 (`docs\PHASE_17_BACKEND_PRODUCTIZATION.md` Section AA): `CORSMiddleware` is added only when `IPSAKTI_CORS_ALLOWED_ORIGINS` is explicitly set; the default app has no CORS middleware and never uses an unrestricted wildcard. `render.yaml` declares this variable `sync: false` (manual entry, real frontend origin only) and `tests\test_phase_20_deployment.py::test_render_yaml_never_declares_a_wildcard_cors_value` asserts no `value: "*"` literal (either quote style) exists anywhere in the file.

## 10. Health check

`[OFFICIAL SOURCE]` `GET /health`, unchanged from Phase 17 (`docs\PHASE_17_BACKEND_PRODUCTIZATION.md` Section I): a static liveness/config check only — it verifies the process is alive and reports two static facts (whether a `GenerationProvider`/`TranslationProvider` is configured, and `corpus_status`, which is **always** `"NOT_VALIDATED"`, since no corpus is ingested anywhere in this repository). It never performs a live retrieval, model, or network call. `render.yaml`'s `healthCheckPath: /health` wires this endpoint into Render's own health-check polling (`[EXTERNAL RESEARCH]`, `render.com/docs/health-checks`); Phase 20 adds no new health semantics beyond pointing Render at what already exists.

## 11. Free-tier / ₹0 demo constraints

`[ENGINEERING RECOMMENDATION]` Both services are pinned `plan: free`; no database, Docker runtime, paid add-on, or custom domain is declared anywhere in `render.yaml` (its own "COST LOCK" header comment states this explicitly and instructs that the file must never be silently changed to a paid plan). Enforced structurally: `tests\test_phase_20_deployment.py::test_render_yaml_declares_exactly_two_free_services_no_database_no_docker` and `::test_no_database_dependency_or_service_introduced_anywhere`.

`[ASSUMPTION]` Render Free's actual runtime behavior (cold starts after a period of inactivity, a monthly free-hours cap, no persistent disk) is documented by Render itself (`[EXTERNAL RESEARCH]`, cited in Section 3) but has **not** been benchmarked or observed live from within this repository or its test suite — `tests\test_phase_20_deployment.py` checks only the static shape of `render.yaml`/`requirements-render.txt`, never a live Render process. No claim of measured cold-start latency, uptime, or throughput is made anywhere in this phase.

## 12. Security constraints

`[ENGINEERING RECOMMENDATION]` Phase 20 adds no new security control of its own — it deploys the app Phase 17/19 already hardened, unchanged. What Phase 20 specifically verifies at the deployment-configuration level: no secret/credential/URL literal is committed anywhere in `render.yaml` (Section 8); CORS stays closed by default and is never set to a wildcard (Section 9); `requirements-render.txt` excludes every test-only and heavy-ML package (`pytest`, `httpx`, `sentence-transformers`, `torch`, `transformers`, `pypdf`) from the production install, narrowing what actually ships to a live Render process versus what exists for local development; no `Dockerfile`/`docker-compose.yml`/`Procfile` artifact was introduced. This is a deployment-configuration-boundary check, not a restatement or extension of Phase 19's adversarial hardening — Phase 19's own scope (`docs\PHASE_19_SECURITY_ADVERSARIAL_HARDENING.md` Section J) explicitly names Phase 20 deployment artifacts as outside what it covers.

## 13. What Phase 20 explicitly does NOT provide

`[ENGINEERING RECOMMENDATION]`, none of the following is implemented, measured, or claimed anywhere in this phase — each remains exactly the pre-existing, disclosed limitation of the phase that actually owns it:
- **Production readiness** — per `docs\DEVELOPMENT_RULES.md` Rule 12's own definition, *"'Production' means reproducible deployment, controlled corpus updates, evaluation gates, monitoring, backup/restore, security controls, and rollback."* Phase 20 provides only the first of these (a reproducible deployment description); controlled corpus updates, evaluation gates in a pipeline, monitoring, backup/restore, and rollback automation do not exist anywhere in this repository. This is explicitly a demo/free-tier deployment configuration, **not** a production deployment by the project's own stated definition.
- **Scalability** — no load, latency, throughput, or concurrency characteristic is measured (Phase 17's own disclosed `NOT VALIDATED`, `docs\PHASE_17_BACKEND_PRODUCTIZATION.md` Section AF, unchanged).
- **GPU deployment** — Render's free web-service runtime used here is CPU-only; no GPU is configured, requested, or available anywhere in `render.yaml`.
- **Database availability** — no database, ORM, or persistent storage exists anywhere (Phase 17 Section W `[DEFERRED]`, unchanged; structurally reasserted by `test_no_database_dependency_or_service_introduced_anywhere`).
- **Authentication/authorization** — none exists anywhere in `src\api\` (Phase 17 Section B, unchanged).
- **Rate limiting** — only Phase 17's simple input-size guard exists (Section Z); Phase 19 itself explicitly named rate limiting out of its own scope (Section C). Nothing in Phase 20 adds one.
- **Observability** — no metrics backend, log aggregation, or distributed tracing exists; that is explicitly Phase 21's own future scope.
- **Automatic corpus refresh** — no corpus is ingested anywhere in this repository at all (Phase 17 Section F); refresh automation is explicitly Phase 21's own future scope.
- **Live Gemini generation** — `generation_provider=None` is the deployed app's own default (Section 6); no live provider SDK is declared or wired in. This remains Phase 10's own `[DEFERRED]` boundary, unchanged and unpromoted by this document.
- **Live multilingual translation** — only Phase 14's own deterministic `FakeTranslationProvider` exists anywhere in this repository (Phase 17 Section S, unchanged); no live translation adapter is deployed.

## 14. Test strategy and acceptance criteria

`[ENGINEERING RECOMMENDATION]` `tests\test_phase_20_deployment.py` — 16 tests, all static/structural (file existence, YAML shape, string/set assertions against `render.yaml` and `requirements-render.txt`; no live network call, no live Render deployment, no subprocess launch of `uvicorn`):
1. `requirements-render.txt` exists.
2. Its declared package set is exactly `{fastapi, pydantic, uvicorn, numpy, faiss-cpu, pyyaml}` and disjoint from the forbidden set (Section 6).
3. Every shared package's pin matches `requirements-dev.txt` byte-for-byte.
4. `requirements-dev.txt` remains completely unmodified.
5–6. `.python-version` / `frontend\.node-version` exist and match a plausible version-string shape.
7. `render.yaml` exists and parses as valid YAML with exactly 2 services.
8. Exactly two free-plan services, no `databases` key, no `runtime: docker`.
9. Backend service's start/build command and health path match exactly what Section 4 documents.
10. Frontend service's build command and publish path match exactly what Section 5 documents.
11. No `onrender.com` URL or secret-shaped literal anywhere in `render.yaml`.
12. CORS/API-base-URL vars are `sync: false` with no `value`, never hardcoded.
13. No wildcard (`"*"`) CORS value anywhere.
14. `src\api\app.py` was not modified to add a port or `uvicorn.run()` call.
15. No `Dockerfile`/`docker-compose.yml`/`docker-compose.yaml`/`Procfile` exists.
16. No database-related term (`postgres`, `redis`, `sqlite`, `mysql`, `mongodb`) appears in `render.yaml`.

`[OFFICIAL SOURCE, as restated for this implementation]` `docs\PHASE_TRACKER.md`'s Phase 20 acceptance gate — *"Fresh environment can be provisioned and started without source edits"* — is met in the narrow, disclosed sense that: a single Blueprint file (`render.yaml`) fully describes both services from source, requires editing zero application source files to provision (only Render-dashboard-entered environment variable *values*, never code, are needed — Section 8), and this shape is proven by the 16 tests above plus the full repository regression suite remaining green (2920/2920, see Section 15). It is **not** verified by an actual, live, end-to-end Render provisioning run performed from within this repository or its test suite — no network access to Render is assumed available in this development environment, and no test here launches a real Render build. This is disclosed as the honest boundary of what "MET" means for this phase, not claimed as a live-verified fact.

## 15. Current deployment status

`[OUR ENHANCEMENT]`/`[ASSUMPTION]` **Not currently verifiable as live from within this repository.** No `*.onrender.com` URL, deployment log, or credential is stored anywhere in this repository (by design — Section 8), so this document makes no claim about whether a live Render service is currently running, healthy, or reachable.

What *is* evidenced in the repository: `requirements-render.txt`'s own header comments describe at least two real, prior Render deployment attempts that failed with genuine `ModuleNotFoundError`s (`numpy`, then `yaml`), each subsequently diagnosed by direct import-chain inspection and fixed by adding the missing package to `requirements-render.txt` (Section 6) — meaning a live Render build was actually attempted and observed to fail at least twice, and the dependency manifest was corrected against that real, observed failure rather than by speculation. Whether a live deployment currently succeeds end-to-end (i.e., the backend boots and serves `GET /health` on Render itself) has not been re-verified inside this repository or documented here with a timestamp/URL, and this document does not claim it has.

## 16. Deferred items / next work

`[DEFERRED]`
- Docker/Compose packaging, if ever needed beyond Render's native runtimes (superseded for the current free-tier target per Section 1's disclosed deviation, not ruled out permanently).
- A database/persistence layer and its migration tooling.
- Observability, metrics, log aggregation, backup/restore, and corpus-refresh automation (Phase 21's own scope).
- CI/CD pipeline automation (Phase 22's own scope).
- Production validation against the Master Reference's full "Production Meaning" bar (Rule 12) — evaluation gates, monitoring, rollback (Phase 23's own scope).
- A live Gemini/Qwen/Bhashini provider adapter and its `api\dependencies.py` wiring — remains Phase 10/14's own `[DEFERRED]` boundary; **explicitly not addressed, promoted, or changed by this document or this phase.**
- Authentication/authorization, rate limiting beyond the existing input-size guard, and any GPU-backed deployment target.
- A test that launches an actual live Render (or equivalent) process end-to-end and asserts on its real, running behavior — today's 16 tests are static/structural only (Section 14).
- Reconciling `docs\PHASE_TRACKER.md`'s Phase 20 row (currently "NOT STARTED", describing a Docker/Compose plan) with the Render-Blueprint approach this document actually describes (Section 1) — left for a separate, explicit update rather than done silently as part of writing this document.
