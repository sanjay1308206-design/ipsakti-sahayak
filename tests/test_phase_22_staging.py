"""
Phase 22 Step 22.5 tests: staging release + smoke tests
(docs/PHASE_22_CICD_PRODUCTION_RELEASE.md Section 7;
.github/workflows/ci.yml `staging` job; scripts/staging_smoke_test.py).

Two layers, matching this project's own established Phase 22 convention
(tests/test_phase_22_release_artifact.py):
  1. Behavior-based tests against the real `scripts/staging_smoke_test.py`
     module (imported directly, never re-implemented/mocked), including
     one test that feeds it the REAL, current `/health` payload produced
     by `api.app.create_app()` (Phase 17, unchanged) via FastAPI's own
     TestClient - proving the smoke test validates today's actual
     contract, not a stale assumption about it.
  2. Structural checks against `.github/workflows/ci.yml`'s own committed
     shape for the CI-integration requirements that cannot be proven any
     other way. No live GitHub Actions run and no real Render deployment
     is triggered, simulated, or assumed anywhere in this file.
"""

from __future__ import annotations

import http.server
import json
import sys
import threading
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
SCRIPTS_DIR = REPO_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import staging_smoke_test as smoke  # noqa: E402

from api.app import create_app  # noqa: E402


def _load_workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _staging_job() -> dict:
    return _load_workflow()["jobs"]["staging"]


class _JSONHandler(http.server.BaseHTTPRequestHandler):
    """Minimal, deterministic local HTTP server for exercising the real network/retry code path - localhost only, no external egress."""

    payload: dict = {}
    status_code: int = 200

    def do_GET(self):  # noqa: N802 - stdlib-mandated method name
        self.send_response(self.status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(self.payload).encode("utf-8"))

    def log_message(self, format, *args):  # noqa: A002 - silence stdlib default logging
        pass


@pytest.fixture
def local_json_server():
    """Starts a background HTTP server on an ephemeral localhost port serving a configurable JSON payload."""

    class Handler(_JSONHandler):
        pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        yield f"http://127.0.0.1:{port}", Handler
    finally:
        server.shutdown()
        thread.join(timeout=5)


# ---------------------------------------------------------------------------
# 1. /health contract validation - behavior, not string matching
# ---------------------------------------------------------------------------

VALID_HEALTH_PAYLOAD = {
    "status": "alive",
    "api_version": "v1",
    "corpus_status": "NOT_VALIDATED",
    "generation_provider_configured": False,
    "translation_provider_configured": False,
}


def test_verify_health_contract_accepts_a_well_formed_payload():
    smoke.verify_health_contract(dict(VALID_HEALTH_PAYLOAD))  # must not raise


def test_verify_health_contract_does_not_misclassify_not_validated_corpus_as_a_failure():
    # Explicit requirement: NOT_VALIDATED corpus_status must never be
    # treated as a smoke-test failure - it is this project's own honest,
    # current state (no corpus ingested anywhere in this repository).
    payload = dict(VALID_HEALTH_PAYLOAD, corpus_status="NOT_VALIDATED")
    smoke.verify_health_contract(payload)  # must not raise


def test_verify_health_contract_does_not_misclassify_missing_generation_provider_as_a_failure():
    payload = dict(VALID_HEALTH_PAYLOAD, generation_provider_configured=False)
    smoke.verify_health_contract(payload)  # must not raise


@pytest.mark.parametrize("missing_key", sorted(smoke.EXPECTED_HEALTH_KEYS))
def test_verify_health_contract_rejects_a_payload_missing_any_expected_key(missing_key):
    payload = dict(VALID_HEALTH_PAYLOAD)
    del payload[missing_key]
    with pytest.raises(smoke.SmokeTestError):
        smoke.verify_health_contract(payload)


def test_verify_health_contract_rejects_wrong_status_value():
    with pytest.raises(smoke.SmokeTestError):
        smoke.verify_health_contract(dict(VALID_HEALTH_PAYLOAD, status="dead"))


def test_verify_health_contract_rejects_non_boolean_provider_flags():
    with pytest.raises(smoke.SmokeTestError):
        smoke.verify_health_contract(dict(VALID_HEALTH_PAYLOAD, generation_provider_configured="false"))


def test_verify_health_contract_rejects_empty_api_version():
    with pytest.raises(smoke.SmokeTestError):
        smoke.verify_health_contract(dict(VALID_HEALTH_PAYLOAD, api_version=""))


def test_verify_health_contract_validates_the_real_current_health_endpoint_payload():
    # Proves this smoke test validates the ACTUAL, current contract
    # (src/api/schemas.py::HealthResponse via api.app.create_app()) -
    # never a fabricated or stale assumption about its shape.
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    smoke.verify_health_contract(response.json())  # must not raise


# ---------------------------------------------------------------------------
# 2. Real network/retry behavior (localhost only, deterministic)
# ---------------------------------------------------------------------------


def test_wait_for_health_succeeds_against_a_real_local_server(local_json_server):
    base_url, handler_cls = local_json_server
    handler_cls.payload = dict(VALID_HEALTH_PAYLOAD)
    payload = smoke.wait_for_health(base_url, attempts=3, delay_seconds=0.05)
    assert payload == VALID_HEALTH_PAYLOAD


def test_run_backend_smoke_test_passes_end_to_end_against_a_real_local_server(local_json_server):
    base_url, handler_cls = local_json_server
    handler_cls.payload = dict(VALID_HEALTH_PAYLOAD)
    payload = smoke.run_backend_smoke_test(base_url, attempts=3, delay_seconds=0.05)
    assert payload["status"] == "alive"


def test_run_backend_smoke_test_fails_closed_when_server_returns_a_broken_contract(local_json_server):
    base_url, handler_cls = local_json_server
    handler_cls.payload = {"status": "alive"}  # missing every other required key
    with pytest.raises(smoke.SmokeTestError):
        smoke.run_backend_smoke_test(base_url, attempts=1, delay_seconds=0.01)


def test_wait_for_health_fails_closed_when_nothing_is_listening():
    # Deliberately unused local port - never a real/external network call.
    with pytest.raises(smoke.SmokeTestError):
        smoke.wait_for_health("http://127.0.0.1:1", attempts=1, delay_seconds=0.01, timeout=0.5)


# ---------------------------------------------------------------------------
# 3. Frontend reachability + API-base-URL verification
# ---------------------------------------------------------------------------


def _serve_directory(tmp_path: Path):
    handler = http.server.SimpleHTTPRequestHandler
    import functools

    handler = functools.partial(handler, directory=str(tmp_path))
    server = http.server.HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_run_frontend_smoke_test_passes_when_bundle_contains_expected_api_base(tmp_path):
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "app.js").write_text("const API='http://127.0.0.1:8000';", encoding="utf-8")

    server, thread = _serve_directory(tmp_path)
    try:
        port = server.server_address[1]
        smoke.run_frontend_smoke_test(
            f"http://127.0.0.1:{port}/index.html",
            expected_api_base="http://127.0.0.1:8000",
            dist_dir=tmp_path,
            attempts=3,
            delay_seconds=0.05,
        )  # must not raise
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_run_frontend_smoke_test_fails_closed_when_api_base_is_not_baked_in(tmp_path):
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "app.js").write_text("const API='http://wrong-host:9999';", encoding="utf-8")

    server, thread = _serve_directory(tmp_path)
    try:
        port = server.server_address[1]
        with pytest.raises(smoke.SmokeTestError):
            smoke.run_frontend_smoke_test(
                f"http://127.0.0.1:{port}/index.html",
                expected_api_base="http://127.0.0.1:8000",
                dist_dir=tmp_path,
                attempts=1,
                delay_seconds=0.01,
            )
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_run_frontend_smoke_test_fails_closed_when_no_js_bundle_exists(tmp_path):
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    server, thread = _serve_directory(tmp_path)
    try:
        port = server.server_address[1]
        with pytest.raises(smoke.SmokeTestError):
            smoke.run_frontend_smoke_test(
                f"http://127.0.0.1:{port}/index.html",
                expected_api_base="http://127.0.0.1:8000",
                dist_dir=tmp_path,
                attempts=1,
                delay_seconds=0.01,
            )
    finally:
        server.shutdown()
        thread.join(timeout=5)


# ---------------------------------------------------------------------------
# 4. CLI behavior + honest, non-fabricating output
# ---------------------------------------------------------------------------


def test_cli_main_backend_returns_zero_and_never_claims_production_readiness(local_json_server, capsys):
    base_url, handler_cls = local_json_server
    handler_cls.payload = dict(VALID_HEALTH_PAYLOAD)
    exit_code = smoke.main(["backend", "--url", base_url, "--attempts", "3", "--delay-seconds", "0.05"])
    assert exit_code == 0
    out = capsys.readouterr().out.lower()
    assert "production ready" not in out
    assert "not asserted 'ready'" in out or "honestly reported" in out


def test_cli_main_backend_returns_nonzero_on_failure_and_prints_to_stderr(capsys):
    exit_code = smoke.main(["backend", "--url", "http://127.0.0.1:1", "--attempts", "1", "--delay-seconds", "0.01"])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "FAILED" in err


def test_smoke_test_module_is_standard_library_only():
    # Matches scripts/build_release_manifest.py's own precedent: this
    # script must run inside the `staging` CI job, which installs only
    # requirements-render.txt - never httpx/requests.
    source = Path(smoke.__file__).read_text(encoding="utf-8")
    for forbidden_import in ("import requests", "import httpx", "from requests", "from httpx"):
        assert forbidden_import not in source


def test_smoke_test_module_never_reads_or_prints_environment_secrets():
    source = Path(smoke.__file__).read_text(encoding="utf-8")
    assert "os.environ" not in source
    assert "getenv" not in source


# ---------------------------------------------------------------------------
# 5. CI workflow structural checks
# ---------------------------------------------------------------------------


def test_staging_job_exists_as_a_distinct_named_job():
    jobs = _load_workflow()["jobs"]
    assert "staging" in jobs


def test_staging_job_depends_on_every_earlier_gate():
    job = _staging_job()
    assert set(job.get("needs", [])) == {"backend", "frontend", "evaluation", "release-artifact"}


def test_staging_job_records_release_identity_via_git_sha_never_a_new_scheme():
    job = _staging_job()
    run_commands = " ".join(s.get("run", "") for s in job["steps"])
    assert "git rev-parse HEAD" in run_commands
    for forbidden_identity_source in ("uuid", "github.run_id", "date +", "timestamp"):
        assert forbidden_identity_source not in run_commands.lower()


def test_staging_job_installs_the_real_production_dependency_closure():
    job = _staging_job()
    run_commands = " ".join(s.get("run", "") for s in job["steps"])
    assert "requirements-render.txt" in run_commands
    assert "requirements-dev.txt" not in run_commands


def test_staging_job_starts_backend_with_the_same_command_render_yaml_uses():
    job = _staging_job()
    run_commands = " ".join(s.get("run", "") for s in job["steps"])
    assert "uvicorn api.app:app" in run_commands
    assert "--app-dir src" in run_commands


def test_staging_job_targets_localhost_only_never_a_real_render_or_production_url():
    job = _staging_job()
    executable_text = " ".join(f"{s.get('uses', '')} {s.get('run', '')} {json.dumps(s.get('env', {}))}".lower() for s in job["steps"])
    assert "127.0.0.1" in executable_text
    for forbidden in ("onrender.com", "render.com"):
        assert forbidden not in executable_text


def test_staging_job_runs_both_backend_and_frontend_smoke_tests():
    job = _staging_job()
    run_commands = " ".join(s.get("run", "") for s in job["steps"])
    assert "scripts/staging_smoke_test.py backend" in run_commands
    assert "scripts/staging_smoke_test.py frontend" in run_commands


def test_staging_job_never_touches_render_or_production():
    job = _staging_job()
    executable_text = " ".join(f"{s.get('uses', '')} {s.get('run', '')}".lower() for s in job["steps"])
    for forbidden in ("docker", "onrender.com", "render.com", "rollback"):
        assert forbidden not in executable_text


def test_staging_job_uses_no_secrets_and_prints_none():
    job = _staging_job()
    job_text = yaml.safe_dump(job)
    assert "secrets." not in job_text


def test_staging_job_itself_is_not_named_or_shaped_like_a_deployment_job():
    # [ENGINEERING RECOMMENDATION] narrowed to the staging job's own
    # identity: Step 22.6 legitimately adds a separate, real "production"
    # job elsewhere in this same workflow (tests/test_phase_22_production.py
    # covers its own full contract) - what this test still proves is that
    # the STAGING job specifically never mutated into a deployment job.
    job = _staging_job()
    job_name = job.get("name", "").lower()
    for forbidden_job_name_fragment in ("production", "rollback", "promote", "release-tag", "publish"):
        assert forbidden_job_name_fragment not in job_name


def test_no_rollback_promote_or_publish_job_introduced_anywhere():
    # Rollback/promotion/publishing remain out of scope through Step 22.6
    # (Step 22.7's own future scope) - checked across the WHOLE workflow,
    # unlike the staging-job-only check above.
    jobs = _load_workflow()["jobs"]
    for forbidden_job_name_fragment in ("rollback", "promote", "release-tag", "publish"):
        for job_id, job in jobs.items():
            assert forbidden_job_name_fragment not in job_id.lower()
            assert forbidden_job_name_fragment not in job.get("name", "").lower()


def test_staging_job_has_a_failure_diagnostics_step_that_does_not_swallow_the_real_failure():
    job = _staging_job()
    for step in job["steps"]:
        assert step.get("continue-on-error") is not True
    run_commands = " ".join(s.get("run", "") for s in job["steps"])
    assert "|| true" not in run_commands or "cat staging_backend.log" in run_commands  # diagnostics step may tolerate a missing log file only


def test_workflow_still_has_no_workflow_dispatch_schedule_or_deployment_trigger():
    workflow = _load_workflow()
    triggers = workflow.get("on") if "on" in workflow else workflow.get(True)
    for forbidden in ("schedule", "release", "deployment", "workflow_dispatch"):
        assert forbidden not in triggers


def test_workflow_triggers_and_permissions_unchanged_by_this_step():
    workflow = _load_workflow()
    triggers = workflow.get("on") if "on" in workflow else workflow.get(True)
    assert set(triggers.keys()) == {"push", "pull_request"}
    assert workflow.get("permissions") == {"contents": "read"}
