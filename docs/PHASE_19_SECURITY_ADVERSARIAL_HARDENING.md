# PHASE 19 — Security & Adversarial Hardening

Derived from `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf` (`[OFFICIAL SOURCE]`) and `docs/PHASE_TRACKER.md`'s own one-line Phase 19 definition: "Defend against prompt injection, poisoned sources, citation manipulation, unsafe inputs." Rule (`docs/DEVELOPMENT_RULES.md`): IMPLEMENTATION + TESTS + VALIDATION = ONE PHASE.

## A. Objective

Phase 19 does not build new domain functionality. It adversarially probes every trust boundary introduced by Phases 8–18 (evidence identity, citation resolution, jurisdiction firewall, safety/abstention, human review, multilingual delivery, the Phase 17 API, and the Phase 18 frontend) and either (1) proves the existing defense already holds, or (2) fixes the smallest justified defect and then proves the fix holds — never by weakening or deleting a test to make it pass.

## B. Scope

- One real implementation defect found and fixed: `src/api/errors.py` gained an explicit `StarletteHTTPException` handler (see Section E).
- Fifteen additive red-team categories (`P19-01`..`P19-15`) in `src/evaluation/redteam.py`'s `PHASE19_REDTEAM_CASES`, mirrored in `config/phase19_redteam_cases.yaml`, exercised against real Phase 8–18 objects (never mocked/stubbed logic) by `tests/test_phase_19_redteam.py`.
- Six additional API-layer adversarial-payload tests in `tests/test_phase_19_api_security.py` (deeply-nested JSON, invalid UTF-8, repeated malformed requests, unknown-route error-shape parity) that Phase 17's own test suite did not cover.
- A dependency/configuration review and phase-boundary/source-discipline audit (`tests/test_phase_19_regression.py`), the same category of check every prior phase performs for its own additions.

## C. Non-Scope

No new domain capability, no new dependency (Python or frontend), no authentication/authorization system, no rate limiting, no WAF/network-layer control, no Phase 20 deployment/CI artifact. Those remain Phase 20–22's own scope. Phase 19 is a hardening/verification pass over what Phases 0–18 already built, not a new feature phase.

## D. The Genuine Defect Found And Fixed

Starlette (FastAPI's ASGI framework) raises its own `starlette.exceptions.HTTPException` for framework-level body-parsing failures — invalid UTF-8 in the request body, or a JSON structure nested deep enough to exhaust the JSON parser's recursion limit — **before** this application's own `RequestValidationError` handler (registered in `src/api/errors.py` since Phase 17) ever runs, and FastAPI installs a default handler for Starlette's own exception type ahead of the generic `Exception` catch-all. Prior to this phase, that default handler returned a bare `{"detail": ...}` body with no `error_type` key, silently violating this API's one documented `ErrorResponse` contract (`docs/PHASE_17_BACKEND_PRODUCTIZATION.md` Section L, tested by `test_phase_17_errors.py::test_error_response_always_matches_error_schema`) for this one class of request. The response was never a 500, never leaked a traceback, and never leaked internal detail — the defect was a schema-shape inconsistency, not an information-disclosure or crash bug.

**Fix:** `src/api/errors.py` now registers an explicit `@app.exception_handler(StarletteHTTPException)` handler that reuses Starlette's own (already-safe, already-generic) `exc.detail` and `exc.status_code` verbatim, and normalizes the body to this API's `{"detail": ..., "error_type": "MALFORMED_REQUEST"}` shape. This runs strictly *before* FastAPI's default handler for the same exception type (explicit registration takes precedence), and does not change status codes, does not change FastAPI's own 404-for-unknown-route behavior (verified directly by `test_unknown_route_error_body_also_matches_error_schema`), and adds no new information to the response.

## E. Category Coverage Map

Phase 19 was scoped against exactly **16** named threat categories. Two distinct, non-overlapping test mechanisms prove them:

1. **The formal Phase 19 red-team benchmark** — the 15 cases `P19-01`..`P19-15` in `src/evaluation/redteam.py`'s `PHASE19_REDTEAM_CASES`, each with an executable `_p19NN_check` and a pass/fail verdict, aggregated by `tests/test_phase_19_redteam.py::test_full_phase19_redteam_summary_all_15_categories_blocked` into `attack_cases=15, successful_attacks=0, blocked_attacks=15, detection_rate=1.0`. This is a fixed-size artifact (mirroring Phase 16's own 21-case `REDTEAM_CASES`) and is **not** itself sized to 16 — several of the 16 threat categories below are proven by *more than one* of its 15 cases, and two of the 16 categories fall outside what a "red-team case" can even measure (a dependency audit and a meta-fact about the benchmark's own additivity are not adversarial inputs with a blocked/succeeded verdict).
2. **Everything else** — `tests/test_phase_19_api_security.py`, `tests/test_phase_19_regression.py`, and tests reused unchanged from Phases 8, 9, 16, 17, and 18.

The "15/15 blocked" figure in Section H refers **only** to mechanism 1 above (the formal benchmark), not to "15 of the 16 categories" — do not read the two numbers (15 and 16) as the same count measured two ways.

| # | Category | Red-team case ID(s) | Additional covering test(s) | Result |
|---|---|---|---|---|
| 1 | User-query prompt injection | P19-01 | — | INERT |
| 2 | Retrieved-document prompt injection | P19-02 | — | INERT |
| 3 | Evidence forgery/mutation | P19-04 | reused from Phase 8 (`test_phase_08_integrity.py`, `test_phase_08_security.py`) and Phase 9 (`test_phase_09_integrity.py`) | REJECTED |
| 4 | Citation forgery | P19-11 | reused from Phase 17 (`test_phase_17_security.py::test_fake_citation_in_provider_output_never_becomes_a_cited_evidence_id`) | REJECTED |
| 5 | Jurisdiction override | P19-03, P19-13 | — | BLOCKED |
| 6 | Classification override | P19-01 *(same case as #1 — one check asserts `classification_state`, `jurisdiction.state`, and `safety_status` are all unchanged together)* | — | INERT |
| 7 | Safety override | P19-02 *(same case as #2, for the identical reason)* | — | INERT |
| 8 | Serialization mutation | P19-10, P19-15 | — | INERT / REJECTED |
| 9 | Unicode adversarial inputs | P19-03, P19-13 *(same cases as #5)* | reused from Phase 17 (`test_phase_17_unicode.py`) | BLOCKED |
| 10 | Frontend XSS/rendering | P19-06 | reused from Phase 18's own frontend test suite (React's default text-interpolation escaping) | INERT |
| 11 | Human-review manipulation | P19-05, P19-14 | — | REJECTED / INERT |
| 12 | Malformed API inputs | P19-08, P19-09 | `test_phase_19_api_security.py` (invalid UTF-8, syntactically invalid JSON, repeated malformed requests); reused from Phase 17 (`test_phase_17_errors.py`, `test_phase_17_security.py::test_malformed_json_rejected`) | REJECTED (422/400), never 500 |
| 13 | Oversized input | P19-07 | `test_phase_19_api_security.py` (20,000-deep nested JSON rejected, not 500); reused from Phase 17 (`test_phase_17_api.py::test_oversized_query_rejected`) | REJECTED |
| 14 | Error-information leakage | P19-12 | `test_phase_19_api_security.py` (no `RecursionError`/`Traceback`/`site-packages` in any response body); reused from Phase 17 (`test_phase_17_errors.py`) | INERT |
| 15 | Dependency/configuration review | *(none — not a red-team case)* | `test_phase_19_regression.py` (exact Python dependency set unchanged from the Phase 17 baseline; exact frontend runtime dependency set is `{react, react-dom}` only; no wildcard CORS; no `debug=True`/`reload=True` in API source; no hardcoded secret pattern in any Phase-19-touched file) | See Section F |
| 16 | Extension of Phase 16 red-team coverage | *(none — this category describes the benchmark itself, not a case within it)* | `test_phase_19_regression.py::test_phase19_redteam_cases_are_additive_not_a_replacement_of_phase16` (Phase 16's 21 cases byte-for-byte untouched; 15 new, disjoint `P19-` case IDs) | 15 new, 0 removed/modified |

All 15 case IDs (`P19-01`..`P19-15`) are used above; none is orphaned, and the double-use of `P19-01`/`P19-02` (categories 1/6 and 2/7) and `P19-03`/`P19-13` (categories 5/9) reflects that a single check's assertion genuinely covers two named claims at once — it is not double-counted toward the 15-case total.

`test_phase_19_redteam.py::test_repeated_deeply_nested_requests_remain_stable`-style repeated-request stability is exercised as part of category 12 (malformed API inputs) via `P19-09` and `test_phase_19_api_security.py::test_repeated_deeply_nested_requests_remain_stable` — it is not a 17th category.

## F. Dependency/Configuration Review Findings

- **Python dependencies:** `requirements-dev.txt` declares exactly the same 10 packages as the Phase 17 baseline (`pytest`, `PyYAML`, `pypdf`, `sentence-transformers`, `faiss-cpu`, `numpy`, `fastapi`, `pydantic`, `uvicorn`, `httpx`). Phase 19 added zero new packages — asserted by `test_phase_19_regression.py::test_no_new_python_dependency_declared_beyond_phase_17_baseline`.
- **Frontend dependencies:** `frontend/package.json`'s `dependencies` block is exactly `{react, react-dom}`; all dev tooling (`vite`, `vitest`, `oxlint`, `typescript`, testing-library) is dev-only, none is shipped to production output. No new runtime dependency was added.
- **CORS:** `src/api/app.py` adds `CORSMiddleware` only when `IPSAKTI_CORS_ALLOWED_ORIGINS` is explicitly set; no code path anywhere in `src/api/` sets `allow_origins=["*"]`.
- **Debug/reload flags:** no `debug=True` or `reload=True` literal exists anywhere in `src/api/`.
- **Secrets:** no hard-coded API key/password/token/secret-key value exists anywhere in the files this phase touched (`src/api/errors.py`, `src/evaluation/redteam.py`), checked with the same literal-assignment regex Phase 17's own regression file uses (never a false positive against a docstring's prose).
- **Corpus/data leakage:** no new `data/`, `corpus/`, `index(es)/`, `reviewers/` directory exists; the only document-like file in the repository remains the locked Master Reference PDF.

## G. Known Limitations / Disclosed Gaps (not fabricated)

- Phase 19's threat model is limited to the trust boundaries that exist in this codebase today (Phases 8–18). It does not cover authentication/authorization (no such system exists yet — Phase 20+), network-layer denial-of-service (no rate limiter exists yet), or dependency CVE scanning against a live vulnerability database (no network access is assumed available in this environment; the review above is manual/structural, not a `pip-audit`/`npm audit` run against a live feed).
- The frontend XSS defense (category 10) is proven two ways — a static sink scan and a backend-verbatim-preservation proof — but the actual browser-rendered escaping behavior is exercised by Phase 18's own Vitest suite, not re-executed here; Phase 19 does not duplicate that DOM-level assertion.
- `EVIDENCE_PROVENANCE_FAILURE`'s disclosed Phase 9 limitation (reachable only via a deliberately bypassed constructor, documented in `docs/PHASE_09_CITATION_VALIDATION.md` Section X) is unchanged by Phase 19 and is not re-litigated here.

## H. Acceptance Gate

"Known attack cases fail safely" (`docs/PHASE_TRACKER.md`). **MET** for all 16 categories in Section E, via two distinct mechanisms:

- The formal 15-case red-team benchmark (`P19-01`..`P19-15`, covering 14 of the 16 categories — see Section E for which): `tests/test_phase_19_redteam.py::test_full_phase19_redteam_summary_all_15_categories_blocked` asserts `attack_cases == 15`, `successful_attacks == 0`, `blocked_attacks == 15`, `detection_rate == 1.0`, `attack_success_rate == 0.0`. This "15/15" is a statement about the benchmark's own 15 cases, not about 15 of the 16 named categories.
- The remaining 2 categories (dependency/configuration review; extension of Phase 16 red-team coverage) are not expressible as red-team cases and are instead proven directly by `tests/test_phase_19_regression.py`'s assertions (Section F).

All contributing test files pass in full: `tests/test_phase_19_api_security.py` (6/6), `tests/test_phase_19_redteam.py` (16/16), `tests/test_phase_19_regression.py` (14/14); Phase 16's original 21 red-team categories (`tests/test_phase_16_redteam.py`, 22 tests including its own aggregate summary) remain independently passing and untouched.

## I. Validation Evidence

- `tests/test_phase_19_api_security.py`: 6/6 passing.
- `tests/test_phase_19_redteam.py`: 16/16 passing (15 per-category parametrized tests, split across 3 fixture-shape groups — 11 no-client, 3 client-only, 1 app-and-client — plus 1 aggregate 15-category summary).
- `tests/test_phase_19_regression.py`: 14/14 passing.
- `tests/test_phase_16_redteam.py`: 22/22 passing, unchanged.
- `tests/test_phase_17_*.py` (10 files): 156/156 passing, unchanged.
- Combined (`tests/test_phase_17_*.py` + `tests/test_phase_19_*.py` + `tests/test_phase_16_redteam.py`): 214/214 passing (156 + 6 + 16 + 14 + 22 = 214), verified by `pytest --collect-only` against the actual runner, not by summing remembered per-phase figures.
- Full repository suite (`pytest tests/ -v`): 2904/2904 passing, run twice for reproducibility; identical pass count both times.
- Frontend suite (`npm run test -- --run` in `frontend/`): passing, unchanged from Phase 18.
- Frontend build (`npm run build`) and lint (`npm run lint`): clean.

## J. Phase 20 Boundary

Phase 19 implements no deployment configuration, no container/Compose profile, no CI/CD pipeline, no observability/metrics/logging infrastructure beyond what Phase 17 already logs server-side, and no database/migration/backup logic. Those remain Phase 20's (Deployment Engineering), Phase 21's (Observability, Backup & Corpus Refresh), and Phase 22's (CI/CD & Production Release) own, separately-scoped work.
