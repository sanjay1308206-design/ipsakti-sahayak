"""
Phase 22 Step 22.2 tests: CI pipeline foundation
(docs/PHASE_22_CICD_PRODUCTION_RELEASE.md; .github/workflows/ci.yml).

Static/structural checks only, mirroring tests/test_phase_20_deployment.py's
own convention for render.yaml - file existence, YAML shape, string/set
assertions against the workflow file. No live GitHub Actions run is
triggered, simulated, or assumed here; this suite proves the workflow's
own committed shape, never its actual remote execution result.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _load_workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _triggers(workflow: dict) -> dict:
    # PyYAML's SafeLoader resolves the bare, unquoted `on:` key as the
    # boolean True per YAML 1.1 (confirmed against this project's own
    # pinned PyYAML>=6,<7) - GitHub Actions' own parser reads it as the
    # literal string "on"; this helper accounts for PyYAML's quirk so the
    # test reads the same trigger block a person editing the file sees.
    return workflow.get("on") if "on" in workflow else workflow.get(True)


def test_ci_workflow_file_exists():
    assert WORKFLOW_PATH.is_file()


def test_ci_workflow_parses_as_valid_yaml():
    workflow = _load_workflow()
    assert isinstance(workflow, dict)
    assert workflow.get("jobs")


def test_ci_workflow_triggers_on_push_to_main_and_pull_request_only():
    triggers = _triggers(_load_workflow())
    assert set(triggers.keys()) == {"push", "pull_request"}
    assert triggers["push"].get("branches") == ["main"]


def test_ci_workflow_has_no_schedule_release_or_deployment_trigger():
    triggers = _triggers(_load_workflow())
    for forbidden in ("schedule", "release", "deployment", "workflow_dispatch"):
        assert forbidden not in triggers


def test_ci_workflow_declares_least_privilege_permissions():
    workflow = _load_workflow()
    assert workflow.get("permissions") == {"contents": "read"}


def test_ci_workflow_has_backend_and_frontend_jobs_only():
    # [ENGINEERING RECOMMENDATION] "evaluation" added to the expected set:
    # Step 22.3 (docs/PHASE_22_CICD_PRODUCTION_RELEASE.md) legitimately
    # adds a third, separately-named CI job for the evaluation gate
    # (tests/test_phase_22_evaluation_gate.py covers its own contract in
    # full) - this remains an EXACT-match assertion, still failing if any
    # OTHER, unexpected job is ever added.
    # [ENGINEERING RECOMMENDATION] "staging" and "production" likewise
    # added: Step 22.5 adds an ephemeral, local smoke-test job
    # (tests/test_phase_22_staging.py) and Step 22.6 adds the actual
    # gated production-deployment job (tests/test_phase_22_production.py),
    # each depending on every job before it.
    jobs = _load_workflow()["jobs"]
    # [ENGINEERING RECOMMENDATION] "release-artifact" added: Step 22.4
    # (docs/PHASE_22_CICD_PRODUCTION_RELEASE.md) legitimately adds a
    # fourth job that only generates/uploads a release manifest, gated on
    # backend+frontend+evaluation all passing - its own full contract is
    # covered by tests/test_phase_22_release_artifact.py.
    # [ENGINEERING RECOMMENDATION] "staging" added: Step 22.5 legitimately
    # adds a fifth job that runs an ephemeral, local-to-the-runner
    # staging smoke test (never a live Render deployment, never
    # production) gated on backend+frontend+evaluation+release-artifact
    # all passing - its own full contract is covered by
    # tests/test_phase_22_staging.py. Disclosed phase-boundary amendment
    # (same pattern as the two additions above), not a weakening - this
    # remains an EXACT-match assertion, still failing if any OTHER,
    # unexpected job is ever added.
    # [ENGINEERING RECOMMENDATION] "production" added: Step 22.6
    # legitimately adds a sixth job that deploys the already-staged
    # release to the existing Phase 20 Render services via a
    # secret-gated deploy hook, never running unless every earlier gate
    # (including staging) has passed - its own full contract is covered
    # by tests/test_phase_22_production.py.
    assert set(jobs.keys()) == {"backend", "frontend", "evaluation", "release-artifact", "staging", "production"}


def test_backend_job_reads_pinned_python_version_file():
    steps = _load_workflow()["jobs"]["backend"]["steps"]
    setup_step = next(s for s in steps if str(s.get("uses", "")).startswith("actions/setup-python"))
    assert setup_step["with"]["python-version-file"] == ".python-version"


def test_backend_job_installs_only_from_requirements_dev_txt():
    steps = _load_workflow()["jobs"]["backend"]["steps"]
    run_commands = " ".join(s.get("run", "") for s in steps)
    assert "requirements-dev.txt" in run_commands
    assert "requirements-render.txt" not in run_commands


def test_backend_job_runs_pytest():
    steps = _load_workflow()["jobs"]["backend"]["steps"]
    run_commands = " ".join(s.get("run", "") for s in steps)
    assert "pytest" in run_commands


def test_frontend_job_reads_pinned_node_version_file():
    steps = _load_workflow()["jobs"]["frontend"]["steps"]
    setup_step = next(s for s in steps if str(s.get("uses", "")).startswith("actions/setup-node"))
    assert setup_step["with"]["node-version-file"] == "frontend/.node-version"


def test_frontend_job_uses_npm_ci_never_npm_install():
    steps = _load_workflow()["jobs"]["frontend"]["steps"]
    run_commands = " ".join(s.get("run", "") for s in steps)
    assert "npm ci" in run_commands
    assert "npm install" not in run_commands


def test_frontend_job_runs_lint_test_and_build():
    steps = _load_workflow()["jobs"]["frontend"]["steps"]
    run_commands = " ".join(s.get("run", "") for s in steps)
    assert "npm run lint" in run_commands
    assert "npm test" in run_commands
    assert "npm run build" in run_commands


def test_frontend_job_working_directory_is_frontend():
    frontend_job = _load_workflow()["jobs"]["frontend"]
    assert frontend_job.get("defaults", {}).get("run", {}).get("working-directory") == "frontend"


def test_no_secret_reference_outside_the_production_job():
    # [ENGINEERING RECOMMENDATION] narrowed from a whole-file check: Step
    # 22.6 legitimately introduces exactly one secret reference (the
    # Render deploy hook URLs), confined to the "production" job (its own
    # full contract, including "never printed" and "fails closed when
    # absent", is covered by tests/test_phase_22_production.py). Every
    # OTHER job must remain completely secret-free, unchanged.
    workflow = _load_workflow()
    for job_id, job in workflow["jobs"].items():
        if job_id == "production":
            continue
        job_text = yaml.safe_dump(job)
        assert "secrets." not in job_text, f"job {job_id!r} must not reference any secret"


def test_no_docker_anywhere_and_no_render_deployment_step_outside_production():
    # Checks the STRUCTURED step content (uses:/run:), never the raw file
    # text - the workflow's own explanatory comments legitimately mention
    # "Docker"/"deploy" while documenting why they are excluded (docs/
    # PHASE_22_CICD_PRODUCTION_RELEASE.md Step 22.1); what must never
    # appear is an actual executable step that builds/pushes a container
    # anywhere, or one that talks to Render OUTSIDE the "production" job.
    # [ENGINEERING RECOMMENDATION] "production" job excluded from the
    # render.com/onrender.com/deploy checks: Step 22.6 legitimately adds
    # the one job whose entire purpose is deploying to Render - its own
    # full contract (deploy-hook usage, never printing the secret, never
    # touching staging) is covered by tests/test_phase_22_production.py.
    # "docker" remains forbidden in EVERY job without exception, including
    # "production" - Step 22.6 explicitly excludes Docker.
    jobs = _load_workflow()["jobs"]
    all_executable_text = " ".join(
        f"{step.get('uses', '')} {step.get('run', '')}".lower() for job in jobs.values() for step in job["steps"]
    )
    assert "docker" not in all_executable_text

    non_production_executable_text = " ".join(
        f"{step.get('uses', '')} {step.get('run', '')}".lower()
        for job_id, job in jobs.items()
        if job_id != "production"
        for step in job["steps"]
    )
    for forbidden in ("render.com", "onrender.com", "deploy"):
        assert forbidden not in non_production_executable_text
