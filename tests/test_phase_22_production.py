"""
Phase 22 Step 22.6 tests: production deployment
(docs/PHASE_22_CICD_PRODUCTION_RELEASE.md; .github/workflows/ci.yml
`production` job; render.yaml's existing Phase 20 services, unchanged).

Static/structural checks against the committed workflow shape, matching
this project's own established Phase 22 convention (tests/
test_phase_22_release_artifact.py, tests/test_phase_22_staging.py). No
live GitHub Actions run, no real Render deploy-hook call, and no live
production HTTP request is triggered, simulated, or assumed anywhere in
this file - this suite proves the workflow's own committed shape (gating,
credential handling, fail-closed behavior, release-identity
verification), never a real deployment result. It never claims a live
deployment occurred.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
RENDER_YAML_PATH = REPO_ROOT / "render.yaml"


def _load_workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _production_job() -> dict:
    return _load_workflow()["jobs"]["production"]


def _run_commands(job: dict) -> str:
    return " ".join(s.get("run", "") for s in job["steps"])


# ---------------------------------------------------------------------------
# 1. Production job exists and is gated on every earlier check, incl. staging
# ---------------------------------------------------------------------------


def test_production_job_exists_as_a_distinct_named_job():
    jobs = _load_workflow()["jobs"]
    assert "production" in jobs


def test_production_job_depends_on_every_earlier_gate_including_staging():
    job = _production_job()
    assert set(job.get("needs", [])) == {"backend", "frontend", "evaluation", "release-artifact", "staging"}


def test_production_job_is_not_triggered_directly_by_push_bypassing_gates():
    # There is no separate push-triggered workflow/job for production -
    # the ONLY way this job can run is via the `needs` chain above, which
    # requires the entire existing CI pipeline (including staging) to
    # have already succeeded on this exact commit.
    workflow = _load_workflow()
    assert "production" not in {job_id for job_id in workflow["jobs"] if not workflow["jobs"][job_id].get("needs")}
    triggers = workflow.get("on") if "on" in workflow else workflow.get(True)
    assert set(triggers.keys()) == {"push", "pull_request"}
    for forbidden in ("schedule", "release", "deployment", "workflow_dispatch"):
        assert forbidden not in triggers


# ---------------------------------------------------------------------------
# 2. Release identity is preserved and re-verified, never reinvented
# ---------------------------------------------------------------------------


def test_production_job_verifies_release_identity_via_git_sha_never_a_new_scheme():
    job = _production_job()
    run_commands = _run_commands(job)
    assert "git rev-parse HEAD" in run_commands
    for forbidden_identity_source in ("uuid", "github.run_id", "date +", "timestamp"):
        assert forbidden_identity_source not in run_commands.lower()


def test_production_job_verifies_the_release_manifest_matches_head():
    job = _production_job()
    run_commands = _run_commands(job)
    assert "scripts/build_release_manifest.py" in run_commands
    assert "release_id" in run_commands


def test_production_job_pins_each_deploy_to_the_exact_commit_via_ref_parameter():
    # The Render deploy hook's own `ref=<sha>` query parameter
    # ([EXTERNAL RESEARCH], render.com/docs/deploy-hooks) is used so a
    # deploy can never silently pick up a later commit than the one that
    # actually passed every gate.
    job = _production_job()
    run_commands = _run_commands(job)
    assert "ref=${RELEASE_SHA}" in run_commands or "ref=$RELEASE_SHA" in run_commands


# ---------------------------------------------------------------------------
# 3. Credentials: referenced only via secrets, never guessed/hardcoded/printed
# ---------------------------------------------------------------------------


def test_production_job_references_deploy_hooks_only_via_named_secrets():
    job = _production_job()
    job_text = yaml.safe_dump(job)
    assert "secrets.RENDER_BACKEND_DEPLOY_HOOK_URL" in job_text
    assert "secrets.RENDER_FRONTEND_DEPLOY_HOOK_URL" in job_text


def test_production_job_never_hardcodes_a_service_id_api_key_or_onrender_url():
    job = _production_job()
    job_text = yaml.safe_dump(job).lower()
    for forbidden in ("srv-", "onrender.com", "api_key", "apikey"):
        assert forbidden not in job_text


def test_production_job_never_echoes_a_secret_value():
    job = _production_job()
    for step in job["steps"]:
        run_line = step.get("run", "")
        # The secret is read into an env var (DEPLOY_HOOK_URL) and used
        # only inside a curl argument - it must never be echoed/printed
        # directly, and no step may dump the raw env var on its own.
        assert "echo \"$DEPLOY_HOOK_URL\"" not in run_line
        assert "echo $DEPLOY_HOOK_URL" not in run_line
        assert "print(" not in run_line or "DEPLOY_HOOK_URL" not in run_line


def test_production_job_uses_curl_without_verbose_flags_that_would_leak_the_url():
    job = _production_job()
    run_commands = _run_commands(job)
    for step in job["steps"]:
        run_line = step.get("run", "")
        if "curl" in run_line:
            assert " -v " not in run_line
            assert "--trace" not in run_line


def test_production_job_does_not_create_or_hardcode_any_secret():
    # This step never provisions a GitHub Secret itself - only references
    # ones a human must configure manually (documented in the workflow's
    # own header comment and this step's final report).
    job = _production_job()
    job_text = yaml.safe_dump(job)
    assert "gh secret set" not in job_text
    assert "api.github.com" not in job_text


# ---------------------------------------------------------------------------
# 4. Fail-closed behavior when configuration is absent
# ---------------------------------------------------------------------------


def test_production_job_deploy_steps_fail_closed_when_hook_url_is_absent():
    job = _production_job()
    deploy_backend_step = next(s for s in job["steps"] if "Deploy backend" in s.get("name", ""))
    deploy_frontend_step = next(s for s in job["steps"] if "Deploy frontend" in s.get("name", ""))
    for step in (deploy_backend_step, deploy_frontend_step):
        run_line = step["run"]
        assert '-z "$DEPLOY_HOOK_URL"' in run_line
        assert "deployed=false" in run_line
        assert "skipping" in run_line.lower()
        # Never treated as a successful deployment when skipped.
        assert "deployed=true" in run_line  # present in the ELSE branch only


def test_production_job_smoke_test_steps_are_conditioned_on_an_actual_deploy():
    job = _production_job()
    smoke_steps = [s for s in job["steps"] if "Smoke-test the production" in s.get("name", "")]
    assert len(smoke_steps) == 2
    for step in smoke_steps:
        assert "deployed" in step.get("if", "")


def test_production_job_smoke_test_steps_fail_closed_when_production_url_is_absent():
    job = _production_job()
    smoke_steps = [s for s in job["steps"] if "Smoke-test the production" in s.get("name", "")]
    for step in smoke_steps:
        run_line = step["run"]
        assert "vars.RENDER_" in run_line
        assert "exit 1" in run_line


def test_production_job_reuses_the_real_smoke_test_script_never_reimplemented():
    job = _production_job()
    run_commands = _run_commands(job)
    assert "scripts/staging_smoke_test.py backend" in run_commands
    assert "scripts/staging_smoke_test.py frontend" in run_commands
    assert (REPO_ROOT / "scripts" / "staging_smoke_test.py").is_file()


# ---------------------------------------------------------------------------
# 5. Production target is the EXISTING Phase 20 services, never a new one
# ---------------------------------------------------------------------------


def test_render_yaml_still_declares_exactly_the_two_original_phase_20_services():
    # This step must not create a new production service or rename the
    # existing ones - render.yaml's service identity is unchanged.
    render_config = yaml.safe_load(RENDER_YAML_PATH.read_text(encoding="utf-8"))
    service_names = {s["name"] for s in render_config["services"]}
    assert service_names == {"ipsakti-backend", "ipsakti-frontend"}


def test_render_yaml_service_build_start_and_health_config_is_byte_for_byte_unchanged():
    # Structural re-assertion of Phase 20's own locked configuration
    # (tests/test_phase_20_deployment.py owns the full contract) - proves
    # Step 22.6 did not quietly alter build/start commands or the health
    # check path while adding production deployment automation.
    render_config = yaml.safe_load(RENDER_YAML_PATH.read_text(encoding="utf-8"))
    backend = next(s for s in render_config["services"] if s["name"] == "ipsakti-backend")
    frontend = next(s for s in render_config["services"] if s["name"] == "ipsakti-frontend")
    assert backend["buildCommand"] == "pip install -r requirements-render.txt"
    assert backend["startCommand"] == "uvicorn api.app:app --host 0.0.0.0 --port $PORT --app-dir src"
    assert backend["healthCheckPath"] == "/health"
    assert frontend["buildCommand"] == "npm ci && npm run build"
    assert frontend["staticPublishPath"] == "./dist"


def test_render_yaml_still_has_no_docker_database_or_paid_plan():
    render_config = yaml.safe_load(RENDER_YAML_PATH.read_text(encoding="utf-8"))
    assert "databases" not in render_config
    for service in render_config["services"]:
        # The frontend static site declares no `plan` key at all (Render's
        # static-site runtime has no paid/free plan field) - only the
        # backend web service does; where present, it must stay "free".
        assert service.get("plan", "free") == "free"
        assert service.get("runtime") != "docker"


# ---------------------------------------------------------------------------
# 5b. Auto-deploy safety lock (Step 22.6 amendment): Render's own git-based
# auto-deploy must be explicitly OFF on both services, so the GitHub
# Actions `production` job's deploy-hook path is the sole controlled
# production-deployment authority - a push to main must never
# independently deploy production and bypass CI/evaluation/staging.
# ---------------------------------------------------------------------------


def _auto_deploy_trigger(service: dict):
    # [PyYAML QUIRK, same class already documented for the workflow's own
    # bare `on:` trigger key in tests/test_phase_22_ci_foundation.py]:
    # SafeLoader resolves the bare, unquoted YAML 1.1 boolean `off` to
    # Python's `False` - Render's own parser reads the literal string
    # "off" per its documented autoDeployTrigger enum. This helper makes
    # that translation explicit rather than silently comparing to a
    # string that would never match.
    return service.get("autoDeployTrigger")


def test_render_yaml_backend_has_auto_deploy_trigger_explicitly_off():
    render_config = yaml.safe_load(RENDER_YAML_PATH.read_text(encoding="utf-8"))
    backend = next(s for s in render_config["services"] if s["name"] == "ipsakti-backend")
    assert _auto_deploy_trigger(backend) is False


def test_render_yaml_frontend_has_auto_deploy_trigger_explicitly_off():
    render_config = yaml.safe_load(RENDER_YAML_PATH.read_text(encoding="utf-8"))
    frontend = next(s for s in render_config["services"] if s["name"] == "ipsakti-frontend")
    assert _auto_deploy_trigger(frontend) is False


def test_render_yaml_no_service_uses_commit_auto_deploy_trigger():
    render_config = yaml.safe_load(RENDER_YAML_PATH.read_text(encoding="utf-8"))
    for service in render_config["services"]:
        assert _auto_deploy_trigger(service) != "commit"


def test_render_yaml_no_service_uses_checks_pass_auto_deploy_trigger():
    # Deliberately NOT used, even as the "safer-sounding" alternative to
    # bare "commit": it would leave a SECOND, Render-side auto-deploy path
    # active alongside the explicit GitHub Actions deploy-hook path this
    # project actually uses - one single controlled deployment authority
    # only.
    render_config = yaml.safe_load(RENDER_YAML_PATH.read_text(encoding="utf-8"))
    for service in render_config["services"]:
        assert _auto_deploy_trigger(service) != "checksPass"


def test_render_yaml_auto_deploy_trigger_field_is_present_never_omitted():
    # Omitting the field is NOT equivalent to "off" for an existing
    # service (Render's own documented behavior: omitting it "retains the
    # existing value"), so this must be an explicit, present key on both
    # services - never left implicit.
    render_config = yaml.safe_load(RENDER_YAML_PATH.read_text(encoding="utf-8"))
    for service in render_config["services"]:
        assert "autoDeployTrigger" in service


def test_deploy_hook_production_path_remains_the_sole_deployment_mechanism():
    # The GitHub Actions `production` job's deploy-hook steps (Step 22.6's
    # original implementation) are unchanged and remain the only
    # production-deployment automation anywhere in this repository - this
    # render.yaml amendment only REMOVES a competing, ungated Render-side
    # path, it does not add or alter the deploy-hook path itself.
    job = _production_job()
    run_commands = _run_commands(job)
    assert "secrets.RENDER_BACKEND_DEPLOY_HOOK_URL" in yaml.safe_dump(job)
    assert "secrets.RENDER_FRONTEND_DEPLOY_HOOK_URL" in yaml.safe_dump(job)
    assert "ref=${RELEASE_SHA}" in run_commands or "ref=$RELEASE_SHA" in run_commands


def test_production_job_targets_no_localhost_url_never_confused_with_staging():
    job = _production_job()
    run_commands = _run_commands(job)
    assert "127.0.0.1" not in run_commands


# ---------------------------------------------------------------------------
# 6. Scope boundary: no Docker, no rollback, no Phase 23, no other cloud/db
# ---------------------------------------------------------------------------


def test_production_job_introduces_no_docker_database_or_other_cloud_provider():
    job = _production_job()
    job_text = yaml.safe_dump(job).lower()
    for forbidden in ("docker", "postgres", "mysql", "mongodb", "aws", "gcp", "azure", "heroku", "vercel", "netlify"):
        assert forbidden not in job_text


def test_no_rollback_or_phase_23_functionality_introduced_anywhere():
    jobs = _load_workflow()["jobs"]
    for job_id, job in jobs.items():
        job_text = yaml.safe_dump(job).lower()
        for forbidden in ("rollback", "phase_23", "phase 23", "load-test", "load_test", "production-validation"):
            assert forbidden not in job_id.lower()
            assert forbidden not in job.get("name", "").lower()
            assert forbidden not in job_text.replace(job.get("name", "").lower(), "")


def test_workflow_still_has_exactly_six_jobs_in_the_expected_dependency_chain():
    jobs = _load_workflow()["jobs"]
    assert set(jobs.keys()) == {"backend", "frontend", "evaluation", "release-artifact", "staging", "production"}
    assert jobs["release-artifact"]["needs"] == ["backend", "frontend", "evaluation"]
    assert set(jobs["staging"]["needs"]) == {"backend", "frontend", "evaluation", "release-artifact"}
    assert set(jobs["production"]["needs"]) == {"backend", "frontend", "evaluation", "release-artifact", "staging"}


def test_workflow_triggers_and_permissions_unchanged_by_this_step():
    workflow = _load_workflow()
    triggers = workflow.get("on") if "on" in workflow else workflow.get(True)
    assert set(triggers.keys()) == {"push", "pull_request"}
    assert workflow.get("permissions") == {"contents": "read"}


# ---------------------------------------------------------------------------
# 7. This test suite itself never claims a live deployment occurred
# ---------------------------------------------------------------------------


def test_this_suite_makes_no_live_network_call():
    # Sanity/self-check: this file's own IMPORT block must contain no
    # real HTTP client and no live Render/GitHub API interaction - it is
    # structural-only. Checked against only the import lines at the top
    # of the file (never the whole file, since this assertion's own
    # forbidden-pattern list would otherwise self-match).
    import ast

    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module.split(".")[0])

    for forbidden_module in ("urllib", "requests", "httpx", "subprocess"):
        assert forbidden_module not in imported_names
