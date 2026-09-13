#!/usr/bin/env python3
"""
Phase 22 Step 22.5 - staging smoke tests
(docs/PHASE_22_CICD_PRODUCTION_RELEASE.md Section 7 "Impact on staging").

`[ENGINEERING RECOMMENDATION]` REUSED, NOT REIMPLEMENTED, by Step 22.6's
`production` CI job (docs/DEVELOPMENT_RULES.md Rule 6 - prefer existing
tooling): the same `/health`-contract validation this module already
performs against an ephemeral local staging instance is the correct,
identical check to run against the real, deployed production backend -
the contract (`src/api/schemas.py::HealthResponse`) does not change
between environments. `run_frontend_smoke_test`'s `expected_api_base`/
`dist_dir` arguments are OPTIONAL for exactly this reason: Step 22.5's
local staging run has the just-built `dist/` directory on disk to
inspect for the baked-in API base URL, but Step 22.6's production job
never has a local build artifact to inspect (Render builds the frontend
itself, remotely) - when both are omitted, this function performs a
pure reachability check only, never fabricating an API-base-URL
assertion it has no artifact to support.

`[ENGINEERING RECOMMENDATION]` Standalone, Python-standard-library-only
(no `requests`/`httpx` - matches `scripts/build_release_manifest.py`'s own
precedent) so this script runs unmodified in the `staging` CI job, which
installs only `requirements-render.txt` (the real production dependency
closure), never `requirements-dev.txt`. It imports nothing from `src/`,
for the same reason `build_release_manifest.py` does not: importing
anything from `retrieval` cascades into `numpy`/`faiss`/`PyYAML`
(`requirements-render.txt`'s own header). This script only ever talks to
a running process over HTTP - it never imports the application directly.

STAGING DEFINITION (`[ENGINEERING RECOMMENDATION]`, docs/
PHASE_22_CICD_PRODUCTION_RELEASE.md Section 7, `[DEFERRED]`-resolved
here): "staging" for this project, today, is an ephemeral instance of the
candidate release's backend (started with the exact same
`requirements-render.txt` dependency closure and the exact same
`uvicorn api.app:app --app-dir src` start command `render.yaml` uses -
Phase 20, unchanged) and frontend (built with the exact same
`npm ci && npm run build` command, Phase 20 unchanged, only pointed at
the staging backend's URL via `VITE_API_BASE_URL`), both run on the
disposable GitHub Actions runner and torn down when the job ends. This is
deliberately NOT a second Render service: no live account/plan
verification of Render's current free-tier service-count limits is
possible from within this repository (`[ASSUMPTION]`, unresolved -
docs/PHASE_20_DEPLOYMENT_ENGINEERING.md Section 11's own disclosed
boundary), so provisioning one is `[DEFERRED]` rather than assumed safe.
This local mechanism is named explicitly as one of the options the
Step 22.1 document already anticipated ("a local smoke-test run against
a preview build"), needs no credential, cannot touch Render's account,
and structurally cannot ever replace production (it never calls Render's
API).

TRACEABILITY TO release_id: the staging job checks out the SAME commit
`backend`/`evaluation`/`release-artifact` already validated in the same
CI run (`needs: [backend, frontend, evaluation, release-artifact]`) - the
running process under test IS that exact `release_id` by construction,
never re-derived or invented here. This script never asserts a specific
`release_id` value itself because `GET /health` (Phase 17, unchanged)
carries no git-identity field - inventing one here (e.g. by adding a
field to `HealthResponse`) would be Phase 17 application-source change,
explicitly out of this step's scope.

CONTRACT HONESTY (docs "Do NOT falsely classify a NOT_VALIDATED corpus or
missing generation provider as production-ready"): this script validates
that `/health` returns the CONTRACT it actually promises
(`src/api/schemas.py::HealthResponse`) - never that the system is
"production ready". `corpus_status == "NOT_VALIDATED"` and
`generation_provider_configured is False` are today's honestly-reported,
expected values (no corpus is ingested anywhere in this repository; a
live generation provider remains Phase 10's own `[DEFERRED]` boundary) -
this script asserts their PRESENCE and TYPE, never a specific "ready"
value, and never fabricates end-to-end RAG functionality.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

DEFAULT_ATTEMPTS = 10
DEFAULT_DELAY_SECONDS = 1.0
DEFAULT_TIMEOUT_SECONDS = 5.0

EXPECTED_HEALTH_KEYS = {
    "status",
    "api_version",
    "corpus_status",
    "generation_provider_configured",
    "translation_provider_configured",
}


class SmokeTestError(Exception):
    """Raised for a genuine smoke-test failure - never swallowed, never retried silently past the caller's own retry budget."""


def _get_json(url: str, timeout: float) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed localhost/staging URL, never user input
        status = getattr(response, "status", response.getcode())
        if status != 200:
            raise SmokeTestError(f"GET {url} returned HTTP {status}, expected 200")
        body = response.read()

    try:
        return json.loads(body.decode("utf-8"))
    except ValueError as exc:
        raise SmokeTestError(f"GET {url} did not return valid JSON: {exc}") from exc


def wait_for_health(base_url: str, attempts: int = DEFAULT_ATTEMPTS, delay_seconds: float = DEFAULT_DELAY_SECONDS, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> dict:
    """Polls `{base_url}/health` with retries - a freshly started uvicorn process needs a moment to bind its port."""
    last_error: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            return _get_json(f"{base_url.rstrip('/')}/health", timeout=timeout)
        except (urllib.error.URLError, OSError, SmokeTestError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(delay_seconds)
    raise SmokeTestError(f"backend never became healthy at {base_url}/health after {attempts} attempt(s): {last_error}")


def verify_health_contract(payload: dict) -> None:
    """
    Validates the ACTUAL `/health` contract (`src/api/schemas.py::HealthResponse`)
    - presence and type only, never a specific "readiness" value for the
    two fields this project's own current phase honestly reports as not
    yet available (see module docstring "CONTRACT HONESTY").
    """
    missing = EXPECTED_HEALTH_KEYS - payload.keys()
    if missing:
        raise SmokeTestError(f"/health response missing expected keys: {sorted(missing)}")

    if payload["status"] != "alive":
        raise SmokeTestError(f"/health status={payload['status']!r}, expected 'alive'")
    if not isinstance(payload["api_version"], str) or not payload["api_version"]:
        raise SmokeTestError(f"/health api_version is not a non-empty string: {payload['api_version']!r}")
    if not isinstance(payload["corpus_status"], str) or not payload["corpus_status"]:
        raise SmokeTestError(f"/health corpus_status is not a non-empty string: {payload['corpus_status']!r}")
    if not isinstance(payload["generation_provider_configured"], bool):
        raise SmokeTestError("/health generation_provider_configured is not a boolean")
    if not isinstance(payload["translation_provider_configured"], bool):
        raise SmokeTestError("/health translation_provider_configured is not a boolean")


def run_backend_smoke_test(base_url: str, attempts: int = DEFAULT_ATTEMPTS, delay_seconds: float = DEFAULT_DELAY_SECONDS) -> dict:
    payload = wait_for_health(base_url, attempts=attempts, delay_seconds=delay_seconds)
    verify_health_contract(payload)
    return payload


def _wait_for_reachable(url: str, attempts: int, delay_seconds: float, timeout: float) -> None:
    last_error: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers={"Accept": "text/html"})
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                status = getattr(response, "status", response.getcode())
                if status != 200:
                    raise SmokeTestError(f"GET {url} returned HTTP {status}, expected 200")
            return
        except (urllib.error.URLError, OSError, SmokeTestError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(delay_seconds)
    raise SmokeTestError(f"staging frontend never became reachable at {url} after {attempts} attempt(s): {last_error}")


def run_frontend_smoke_test(
    base_url: str,
    expected_api_base: Optional[str] = None,
    dist_dir: Optional[Path] = None,
    attempts: int = DEFAULT_ATTEMPTS,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> None:
    """
    Verifies the deployed static frontend is reachable and, when a local
    build artifact is available (`dist_dir` given), that its BUILD-TIME-
    baked `VITE_API_BASE_URL` (Vite bakes it in at build time, never read
    at runtime - docs/PHASE_20_DEPLOYMENT_ENGINEERING.md Section 8)
    points at the intended backend. When `dist_dir` is omitted (Step
    22.6's production job - see module docstring), this performs
    reachability only - it never fabricates an API-base-URL assertion it
    has no local artifact to support. Never claims end-to-end RAG
    functionality - that depends on the backend's own, separately-checked
    generation-provider configuration.
    """
    _wait_for_reachable(base_url, attempts=attempts, delay_seconds=delay_seconds, timeout=timeout)

    if dist_dir is None:
        return

    if not expected_api_base:
        raise SmokeTestError("expected_api_base must be provided whenever dist_dir is provided")

    dist_dir = Path(dist_dir)
    js_bundles = sorted(p for p in dist_dir.rglob("*.js") if p.is_file())
    if not js_bundles:
        raise SmokeTestError(f"no built JS bundle found under {dist_dir} - frontend build did not run")

    if not any(expected_api_base in bundle.read_text(encoding="utf-8", errors="ignore") for bundle in js_bundles):
        raise SmokeTestError(
            f"expected staging API base URL {expected_api_base!r} was not baked into any built JS bundle under {dist_dir}"
        )


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 22 Step 22.5/22.6 staging and production smoke tests.")
    subparsers = parser.add_subparsers(dest="target", required=True)

    backend_parser = subparsers.add_parser("backend", help="Smoke-test a backend's /health contract (staging or production).")
    backend_parser.add_argument("--url", required=True, help="Backend base URL, e.g. http://127.0.0.1:8000 or a real production URL")
    backend_parser.add_argument("--attempts", type=int, default=DEFAULT_ATTEMPTS)
    backend_parser.add_argument("--delay-seconds", type=float, default=DEFAULT_DELAY_SECONDS)

    frontend_parser = subparsers.add_parser("frontend", help="Smoke-test a frontend's reachability, and its API base URL when a local build is available.")
    frontend_parser.add_argument("--url", required=True, help="Frontend base URL, e.g. http://127.0.0.1:4173 or a real production URL")
    frontend_parser.add_argument("--expected-api-base", default=None, help="The VITE_API_BASE_URL the build was built with (requires --dist-dir; omit both for a production reachability-only check).")
    frontend_parser.add_argument("--dist-dir", default=None, help="Path to the built frontend dist/ directory, if locally available (omit for a production reachability-only check).")
    frontend_parser.add_argument("--attempts", type=int, default=DEFAULT_ATTEMPTS)
    frontend_parser.add_argument("--delay-seconds", type=float, default=DEFAULT_DELAY_SECONDS)

    args = parser.parse_args(argv)

    if args.target == "frontend" and bool(args.dist_dir) != bool(args.expected_api_base):
        parser.error("--dist-dir and --expected-api-base must be provided together (or both omitted)")

    try:
        if args.target == "backend":
            payload = run_backend_smoke_test(args.url, attempts=args.attempts, delay_seconds=args.delay_seconds)
            print(f"backend smoke test PASSED: {args.url}/health")
            print(f"  api_version={payload['api_version']!r}")
            print(f"  corpus_status={payload['corpus_status']!r} (honestly reported, not asserted 'ready')")
            print(f"  generation_provider_configured={payload['generation_provider_configured']!r}")
            print(f"  translation_provider_configured={payload['translation_provider_configured']!r}")
        else:
            run_frontend_smoke_test(
                args.url,
                expected_api_base=args.expected_api_base,
                dist_dir=Path(args.dist_dir) if args.dist_dir else None,
                attempts=args.attempts,
                delay_seconds=args.delay_seconds,
            )
            if args.dist_dir:
                print(f"frontend smoke test PASSED: {args.url} (API base {args.expected_api_base!r} confirmed baked into build)")
            else:
                print(f"frontend smoke test PASSED: {args.url} (reachability only - no local build artifact to verify API base URL against)")
    except SmokeTestError as exc:
        print(f"smoke test FAILED: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
