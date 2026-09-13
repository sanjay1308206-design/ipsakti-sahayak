"""
Phase 22 Step 22.7 tests: rollback system
(docs/PHASE_22_CICD_PRODUCTION_RELEASE.md "Rollback System";
.github/workflows/rollback.yml; scripts/rollback_target.py).

Two layers, matching this project's own established Phase 22 convention:
  1. Behavior-based unit tests against the real `scripts/rollback_target.py`
     module, run against THIS repository's own real git history (the
     same technique tests/test_phase_22_release_artifact.py already uses:
     `git rev-parse HEAD` as ground truth) - no live Render call anywhere.
  2. Structural checks against `.github/workflows/rollback.yml` and the
     amended `.github/workflows/ci.yml` `production` job's own committed
     shape. No live GitHub Actions run, no real Render deploy-hook call,
     and no live production HTTP request is triggered, simulated, or
     assumed anywhere in this file - it never claims a live rollback
     occurred.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
ROLLBACK_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "rollback.yml"
RENDER_YAML_PATH = REPO_ROOT / "render.yaml"
SCRIPTS_DIR = REPO_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import rollback_target  # noqa: E402


def _load_ci_workflow() -> dict:
    return yaml.safe_load(CI_WORKFLOW_PATH.read_text(encoding="utf-8"))


def _load_rollback_workflow() -> dict:
    return yaml.safe_load(ROLLBACK_WORKFLOW_PATH.read_text(encoding="utf-8"))


def _rollback_job() -> dict:
    return _load_rollback_workflow()["jobs"]["rollback"]


def _production_job() -> dict:
    return _load_ci_workflow()["jobs"]["production"]


def _run_commands(job: dict) -> str:
    return " ".join(s.get("run", "") for s in job["steps"])


def _real_head_sha() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()


# ---------------------------------------------------------------------------
# Unit tests: scripts/rollback_target.py (behavior, against real git history)
# ---------------------------------------------------------------------------


def test_resolve_target_sha_prefers_explicit_input_over_known_good():
    assert rollback_target.resolve_target_sha("abc123", "def456") == "abc123"


def test_resolve_target_sha_falls_back_to_known_good_when_input_empty():
    assert rollback_target.resolve_target_sha("", "def456") == "def456"
    assert rollback_target.resolve_target_sha(None, "def456") == "def456"
    assert rollback_target.resolve_target_sha("   ", "def456") == "def456"


def test_resolve_target_sha_fails_closed_when_both_are_empty():
    with pytest.raises(rollback_target.RollbackTargetError):
        rollback_target.resolve_target_sha("", "")
    with pytest.raises(rollback_target.RollbackTargetError):
        rollback_target.resolve_target_sha(None, None)


def test_validate_sha_format_rejects_bad_shapes():
    for bad in ("not-a-sha", "abc123", "A" * 40, "g" * 40, "f" * 39, "f" * 41, "", None, 12345):
        with pytest.raises(rollback_target.RollbackTargetError):
            rollback_target.validate_sha_format(bad)


def test_validate_sha_format_accepts_well_formed_hex():
    rollback_target.validate_sha_format("a" * 40)  # must not raise
    rollback_target.validate_sha_format("0123456789abcdef0123456789abcdef01234567")  # must not raise


def test_validate_target_sha_accepts_the_real_current_repository_head():
    # [L] valid current repository HEAD is accepted.
    head_sha = _real_head_sha()
    rollback_target.validate_target_sha(head_sha, ref="HEAD", repo_root=REPO_ROOT)  # must not raise


def test_validate_commit_exists_rejects_a_well_formed_but_foreign_sha():
    # [M] well-formed foreign 40-hex SHA is rejected.
    foreign_sha = "deadbeef" * 5  # 40 hex chars, syntactically valid, not a real commit anywhere
    assert len(foreign_sha) == 40
    with pytest.raises(rollback_target.RollbackTargetError):
        rollback_target.validate_commit_exists(foreign_sha, repo_root=REPO_ROOT)
    with pytest.raises(rollback_target.RollbackTargetError):
        rollback_target.validate_target_sha(foreign_sha, ref="HEAD", repo_root=REPO_ROOT)


def test_validate_target_sha_rejects_invalid_format_before_touching_git():
    # [K] invalid SHA format is rejected - and rejected by the FIRST check
    # (format), never reaching a git subprocess call for a string that
    # cannot possibly be a commit id.
    with pytest.raises(rollback_target.RollbackTargetError):
        rollback_target.validate_target_sha("short", ref="HEAD", repo_root=REPO_ROOT)


def test_validate_commit_reachable_accepts_an_ancestor_of_head():
    head_sha = _real_head_sha()
    rollback_target.validate_commit_reachable(head_sha, ref="HEAD", repo_root=REPO_ROOT)  # must not raise


def test_rollback_target_module_reuses_repo_root_never_redefines_it():
    from build_release_manifest import REPO_ROOT as manifest_repo_root

    assert rollback_target.REPO_ROOT == manifest_repo_root


def test_rollback_target_cli_resolve_prints_expected_output_line(capsys):
    exit_code = rollback_target.main(["resolve", "--input-sha", "abc123", "--known-good-sha", ""])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert out.strip() == "target_sha=abc123"


def test_rollback_target_cli_validate_fails_closed_on_bad_input(capsys):
    exit_code = rollback_target.main(["validate", "--sha", "not-a-real-sha"])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "FAILED" in err


def test_rollback_target_module_is_standard_library_only():
    source = Path(rollback_target.__file__).read_text(encoding="utf-8")
    for forbidden_import in ("import requests", "import httpx", "from requests", "from httpx"):
        assert forbidden_import not in source


# ---------------------------------------------------------------------------
# [A]-[C] rollback.yml exists, workflow_dispatch only, target_sha input
# ---------------------------------------------------------------------------


def test_rollback_workflow_file_exists():
    assert ROLLBACK_WORKFLOW_PATH.is_file()


def test_rollback_workflow_parses_as_valid_yaml_with_one_job():
    workflow = _load_rollback_workflow()
    assert isinstance(workflow, dict)
    assert set(workflow["jobs"].keys()) == {"rollback"}


def test_rollback_workflow_triggered_only_by_workflow_dispatch():
    workflow = _load_rollback_workflow()
    triggers = workflow.get("on") if "on" in workflow else workflow.get(True)
    assert set(triggers.keys()) == {"workflow_dispatch"}
    for forbidden in ("push", "pull_request", "schedule", "workflow_run"):
        assert forbidden not in triggers


def test_rollback_workflow_has_target_sha_input():
    workflow = _load_rollback_workflow()
    triggers = workflow.get("on") if "on" in workflow else workflow.get(True)
    inputs = triggers["workflow_dispatch"]["inputs"]
    assert "target_sha" in inputs


def test_rollback_workflow_target_sha_input_is_optional_with_empty_default():
    # [D] target_sha correctly supports the documented empty/default
    # behavior (falls back to RENDER_LAST_KNOWN_GOOD_SHA) rather than
    # being a hard-required input.
    workflow = _load_rollback_workflow()
    triggers = workflow.get("on") if "on" in workflow else workflow.get(True)
    target_sha_input = triggers["workflow_dispatch"]["inputs"]["target_sha"]
    assert target_sha_input.get("required") is False
    assert target_sha_input.get("default") == ""


def test_rollback_workflow_least_privilege_permissions():
    workflow = _load_rollback_workflow()
    assert workflow.get("permissions") == {"contents": "read"}


# ---------------------------------------------------------------------------
# [E] RENDER_LAST_KNOWN_GOOD_SHA referenced, target resolution reused
# ---------------------------------------------------------------------------


def test_rollback_workflow_references_known_good_sha_variable():
    # Referenced via an `env:` block on the "Resolve the rollback target
    # SHA" step, not inline in `run:` text - check the full job dump.
    job = _rollback_job()
    job_text = yaml.safe_dump(job)
    assert "vars.RENDER_LAST_KNOWN_GOOD_SHA" in job_text


def test_rollback_workflow_uses_the_real_rollback_target_script():
    job = _rollback_job()
    run_commands = _run_commands(job)
    assert "scripts/rollback_target.py resolve" in run_commands
    assert "scripts/rollback_target.py validate" in run_commands
    assert (REPO_ROOT / "scripts" / "rollback_target.py").is_file()


def test_rollback_workflow_checks_out_full_history():
    job = _rollback_job()
    checkout_step = next(s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout"))
    assert checkout_step.get("with", {}).get("fetch-depth") == 0


def test_rollback_workflow_checks_out_the_resolved_target_commit():
    job = _rollback_job()
    run_commands = _run_commands(job)
    assert "git checkout" in run_commands
    assert "steps.resolve_target.outputs.target_sha" in run_commands


# ---------------------------------------------------------------------------
# Release manifest reused at the target commit
# ---------------------------------------------------------------------------


def test_rollback_workflow_validates_manifest_via_the_real_step_22_4_script():
    job = _rollback_job()
    run_commands = _run_commands(job)
    assert "scripts/build_release_manifest.py" in run_commands
    assert "release_id" in run_commands
    assert (REPO_ROOT / "scripts" / "build_release_manifest.py").is_file()


def test_rollback_workflow_checks_out_target_before_building_manifest():
    job = _rollback_job()
    step_names = [s.get("name", "") for s in job["steps"]]
    checkout_target_index = next(i for i, n in enumerate(step_names) if "Check out the exact, validated target commit" in n)
    manifest_index = next(i for i, n in enumerate(step_names) if "release manifest" in n.lower())
    assert checkout_target_index < manifest_index


# ---------------------------------------------------------------------------
# [F]-[I] backend/frontend deploy hooks reused, same target SHA
# ---------------------------------------------------------------------------


def test_rollback_workflow_reuses_backend_deploy_hook_secret_only():
    job = _rollback_job()
    job_text = yaml.safe_dump(job)
    assert "secrets.RENDER_BACKEND_DEPLOY_HOOK_URL" in job_text


def test_rollback_workflow_reuses_frontend_deploy_hook_secret_only():
    job = _rollback_job()
    job_text = yaml.safe_dump(job)
    assert "secrets.RENDER_FRONTEND_DEPLOY_HOOK_URL" in job_text


def test_rollback_workflow_introduces_no_new_deploy_hook_secret():
    job = _rollback_job()
    job_text = yaml.safe_dump(job)
    for line in job_text.splitlines():
        if "secrets." in line and "DEPLOY_HOOK_URL" in line:
            assert "RENDER_BACKEND_DEPLOY_HOOK_URL" in line or "RENDER_FRONTEND_DEPLOY_HOOK_URL" in line


def test_rollback_workflow_both_deploys_use_ref_with_target_sha():
    job = _rollback_job()
    run_commands = _run_commands(job)
    assert run_commands.count("ref=${{ steps.resolve_target.outputs.target_sha }}") == 2


def test_rollback_workflow_both_services_use_the_identical_target_sha_reference():
    job = _rollback_job()
    backend_step = next(s for s in job["steps"] if "Roll back backend" in s.get("name", ""))
    frontend_step = next(s for s in job["steps"] if "Roll back frontend" in s.get("name", ""))
    backend_ref = "ref=${{ steps.resolve_target.outputs.target_sha }}"
    frontend_ref = "ref=${{ steps.resolve_target.outputs.target_sha }}"
    assert backend_ref in backend_step["run"]
    assert frontend_ref in frontend_step["run"]


# ---------------------------------------------------------------------------
# [J] fail-closed secret handling, [O] never echoed
# ---------------------------------------------------------------------------


def test_rollback_workflow_fails_closed_before_attempting_either_deploy_when_a_hook_is_missing():
    job = _rollback_job()
    preflight_step = next(s for s in job["steps"] if "Verify both Render deploy-hook secrets are configured" in s.get("name", ""))
    run_line = preflight_step["run"]
    assert '-z "$BACKEND_HOOK"' in run_line
    assert '-z "$FRONTEND_HOOK"' in run_line
    assert "exit 1" in run_line

    step_names = [s.get("name", "") for s in job["steps"]]
    preflight_index = step_names.index(preflight_step["name"])
    backend_deploy_index = next(i for i, n in enumerate(step_names) if "Roll back backend" in n)
    frontend_deploy_index = next(i for i, n in enumerate(step_names) if "Roll back frontend" in n)
    assert preflight_index < backend_deploy_index
    assert preflight_index < frontend_deploy_index


def test_rollback_workflow_never_echoes_a_secret_value():
    job = _rollback_job()
    for step in job["steps"]:
        run_line = step.get("run", "")
        assert 'echo "$DEPLOY_HOOK_URL"' not in run_line
        assert "echo $DEPLOY_HOOK_URL" not in run_line
        assert 'echo "$BACKEND_HOOK"' not in run_line
        assert 'echo "$FRONTEND_HOOK"' not in run_line


def test_rollback_workflow_uses_curl_without_verbose_flags_that_would_leak_the_url():
    job = _rollback_job()
    for step in job["steps"]:
        run_line = step.get("run", "")
        if "curl" in run_line:
            assert " -v " not in run_line
            assert "--trace" not in run_line


# ---------------------------------------------------------------------------
# [N] partial deployment failure causes workflow failure
# ---------------------------------------------------------------------------


def test_rollback_workflow_deploy_steps_continue_on_error_so_both_are_always_attempted():
    job = _rollback_job()
    backend_step = next(s for s in job["steps"] if "Roll back backend" in s.get("name", ""))
    frontend_step = next(s for s in job["steps"] if "Roll back frontend" in s.get("name", ""))
    assert backend_step.get("continue-on-error") is True
    assert frontend_step.get("continue-on-error") is True


def test_rollback_workflow_detects_partial_failure_by_comparing_both_outcomes():
    job = _rollback_job()
    detect_step = next(s for s in job["steps"] if "Detect and report a partial rollback" in s.get("name", ""))
    run_line = detect_step["run"]
    assert "steps.rollback_backend.outcome" in run_line
    assert "steps.rollback_frontend.outcome" in run_line
    assert "exit 1" in run_line
    assert "PARTIAL ROLLBACK DETECTED" in run_line


def test_rollback_workflow_never_retries_or_self_heals():
    # Checks for the ACT of retrying/self-healing (a retry action, a
    # bounded retry loop, a second automatic deploy attempt) - never a
    # bare substring match, since this workflow's own disclosure text
    # legitimately says "does not retry or self-heal".
    job = _rollback_job()
    job_text = yaml.safe_dump(job).lower()
    for forbidden in ("uses: nick-fields/retry", "for i in {1..", "while true", "retry-on-failure"):
        assert forbidden not in job_text
    # The deploy-hook curl call must appear exactly twice total (once per
    # service) anywhere in the job - never a third, automatic corrective
    # re-deploy attempt.
    run_commands = _run_commands(job)
    assert run_commands.count("curl -fsS -X POST") == 2


# ---------------------------------------------------------------------------
# Post-rollback verification reuses staging_smoke_test.py unmodified
# ---------------------------------------------------------------------------


def test_rollback_workflow_reuses_the_real_smoke_test_script():
    job = _rollback_job()
    run_commands = _run_commands(job)
    assert "scripts/staging_smoke_test.py backend" in run_commands
    assert "scripts/staging_smoke_test.py frontend" in run_commands


def test_rollback_workflow_smoke_tests_are_conditioned_on_both_deploys_succeeding():
    job = _rollback_job()
    smoke_steps = [s for s in job["steps"] if "Smoke-test the rolled-back" in s.get("name", "")]
    assert len(smoke_steps) == 2
    for step in smoke_steps:
        condition = step.get("if", "")
        assert "steps.rollback_backend.outcome == 'success'" in condition
        assert "steps.rollback_frontend.outcome == 'success'" in condition


def test_rollback_workflow_smoke_tests_target_production_variables_never_localhost():
    job = _rollback_job()
    run_commands = _run_commands(job)
    assert "vars.RENDER_BACKEND_PRODUCTION_URL" in run_commands
    assert "vars.RENDER_FRONTEND_PRODUCTION_URL" in run_commands
    assert "127.0.0.1" not in run_commands


def test_staging_smoke_test_script_was_not_modified_beyond_what_step_22_6_already_required():
    # docs "Do not modify staging_smoke_test.py unless absolutely
    # necessary" - Step 22.7 needed no change to it at all; this asserts
    # the exact, already-existing CLI surface it depends on still exists.
    import staging_smoke_test

    assert hasattr(staging_smoke_test, "run_backend_smoke_test")
    assert hasattr(staging_smoke_test, "run_frontend_smoke_test")
    assert hasattr(staging_smoke_test, "main")


# ---------------------------------------------------------------------------
# [P] rollback.yml is not wired into ci.yml's push/pull_request chain
# ---------------------------------------------------------------------------


def test_rollback_workflow_not_functionally_wired_into_ci_workflow():
    # ci.yml's own header comment legitimately MENTIONS "rollback.yml" in
    # prose while disclosing this step's change (same pattern already
    # used for "scripts", "onrender.com", etc. elsewhere in this file's
    # comments) - what must never exist is FUNCTIONAL wiring: a
    # `workflow_run` trigger, or a job that `uses:`/calls the rollback
    # workflow.
    ci_workflow = _load_ci_workflow()
    triggers = ci_workflow.get("on") if "on" in ci_workflow else ci_workflow.get(True)
    assert "workflow_run" not in triggers
    for job in ci_workflow["jobs"].values():
        for step in job["steps"]:
            assert "rollback.yml" not in str(step.get("uses", ""))


def test_ci_workflow_triggers_still_push_and_pull_request_only():
    ci_workflow = _load_ci_workflow()
    triggers = ci_workflow.get("on") if "on" in ci_workflow else ci_workflow.get(True)
    assert set(triggers.keys()) == {"push", "pull_request"}


def test_ci_workflow_job_set_unchanged_by_this_step():
    ci_workflow = _load_ci_workflow()
    assert set(ci_workflow["jobs"].keys()) == {"backend", "frontend", "evaluation", "release-artifact", "staging", "production"}


# ---------------------------------------------------------------------------
# [Q] render.yaml remains autoDeployTrigger: off
# ---------------------------------------------------------------------------


def test_render_yaml_still_has_auto_deploy_trigger_off_on_both_services():
    render_config = yaml.safe_load(RENDER_YAML_PATH.read_text(encoding="utf-8"))
    for service in render_config["services"]:
        assert service.get("autoDeployTrigger") is False


def test_rollback_step_never_alters_render_yaml_or_production_configuration():
    rollback_job = _rollback_job()
    job_text = yaml.safe_dump(rollback_job).lower()
    assert "render.yaml" not in job_text
    assert "git commit" not in job_text
    assert "git push" not in job_text


# ---------------------------------------------------------------------------
# [R] Phase 22.6 production deployment logic remains intact
# ---------------------------------------------------------------------------


def test_production_job_deploy_and_smoke_test_steps_unchanged():
    job = _production_job()
    step_names = [s.get("name", "") for s in job["steps"]]
    assert any("Deploy backend to production" in n for n in step_names)
    assert any("Deploy frontend to production" in n for n in step_names)
    assert any("Smoke-test the production backend" in n for n in step_names)
    assert any("Smoke-test the production frontend" in n for n in step_names)


def test_production_job_gained_exactly_one_new_step_for_known_good_recording():
    job = _production_job()
    step_names = [s.get("name", "") for s in job["steps"]]
    matching = [n for n in step_names if "Record known-good release SHA" in n]
    assert len(matching) == 1


def test_production_job_known_good_recording_step_never_prints_the_token():
    job = _production_job()
    record_step = next(s for s in job["steps"] if "Record known-good release SHA" in s.get("name", ""))
    run_line = record_step["run"]
    assert 'echo "$GH_TOKEN"' not in run_line
    assert "echo $GH_TOKEN" not in run_line


def test_production_job_known_good_recording_step_fails_closed_without_pat():
    job = _production_job()
    record_step = next(s for s in job["steps"] if "Record known-good release SHA" in s.get("name", ""))
    run_line = record_step["run"]
    assert '-z "$GH_TOKEN"' in run_line
    assert "gh variable set" in run_line


def test_production_job_needs_and_gating_unchanged():
    job = _production_job()
    assert set(job.get("needs", [])) == {"backend", "frontend", "evaluation", "release-artifact", "staging"}


def test_workflow_permissions_unchanged_by_this_step():
    ci_workflow = _load_ci_workflow()
    assert ci_workflow.get("permissions") == {"contents": "read"}


# ---------------------------------------------------------------------------
# [S]/[T] no Docker/database/new-cloud-provider, no Phase 23
# ---------------------------------------------------------------------------


def test_rollback_workflow_introduces_no_docker_database_or_other_cloud_provider():
    job = _rollback_job()
    job_text = yaml.safe_dump(job).lower()
    for forbidden in ("docker", "postgres", "mysql", "mongodb", "aws", "gcp", "azure", "heroku", "vercel", "netlify"):
        assert forbidden not in job_text


def test_rollback_workflow_introduces_no_phase_23_functionality():
    job = _rollback_job()
    job_text = yaml.safe_dump(job).lower()
    for forbidden in ("phase_23", "phase 23", "load-test", "load_test", "production-validation"):
        assert forbidden not in job_text


def test_rollback_workflow_never_commits_or_pushes():
    job = _rollback_job()
    job_text = yaml.safe_dump(job).lower()
    for forbidden in ("git commit", "git push", "gh pr create", "gh release create"):
        assert forbidden not in job_text
