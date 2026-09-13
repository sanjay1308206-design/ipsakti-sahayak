"""
Phase 22 Step 22.3 tests: automated quality + evaluation gate
(docs/PHASE_22_CICD_PRODUCTION_RELEASE.md; .github/workflows/ci.yml
`evaluation` job).

Static/structural checks against the committed workflow, PLUS one
stronger check that actually resolves the evaluation job's own glob
patterns against the real filesystem (not just a substring match) to
prove the job would genuinely invoke real, existing test files - never
an evaluation job that "looks right" as a string but silently matches
nothing.

This suite does not modify, and does not re-validate, the `backend`/
`frontend` jobs already covered by tests/test_phase_22_ci_foundation.py
(Step 22.2) - that file is left completely untouched by this step.
"""

from __future__ import annotations

import glob
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _load_workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _evaluation_job() -> dict:
    return _load_workflow()["jobs"]["evaluation"]


def _run_commands(job: dict) -> str:
    return " ".join(s.get("run", "") for s in job["steps"])


def _pytest_run_step(job: dict) -> dict:
    return next(s for s in job["steps"] if "pytest" in s.get("run", ""))


# ---------------------------------------------------------------------------
# 1. Evaluation gate exists, distinct from the backend/frontend test jobs
# ---------------------------------------------------------------------------


def test_evaluation_job_exists_as_a_distinct_named_job():
    # [ENGINEERING RECOMMENDATION] "release-artifact" added to the expected
    # set: Step 22.4 legitimately adds a fourth job (release manifest
    # generation, gated on this evaluation job passing) - see
    # tests/test_phase_22_release_artifact.py for its own full contract.
    # [ENGINEERING RECOMMENDATION] "staging" added: Step 22.5 legitimately
    # adds a fifth job (ephemeral, local-to-the-runner smoke test, gated
    # on this evaluation job plus release-artifact passing) - see
    # tests/test_phase_22_staging.py for its own full contract.
    # [ENGINEERING RECOMMENDATION] "production" added: Step 22.6
    # legitimately adds a sixth job (gated production deployment to the
    # existing Phase 20 Render services, only after staging passes) - see
    # tests/test_phase_22_production.py for its own full contract.
    jobs = _load_workflow()["jobs"]
    assert "evaluation" in jobs
    assert set(jobs.keys()) == {"backend", "frontend", "evaluation", "release-artifact", "staging", "production"}


def test_evaluation_job_is_not_hidden_inside_backend_or_frontend_jobs():
    workflow = _load_workflow()
    backend_commands = _run_commands(workflow["jobs"]["backend"])
    frontend_commands = _run_commands(workflow["jobs"]["frontend"])
    # The backend job's own full-suite run legitimately also exercises the
    # Phase 16/21 evaluation tests (they are part of the repository's one
    # test suite) - what must NOT happen is the evaluation job being
    # merged away/removed as a separately-reportable check.
    assert "evaluation" not in workflow["jobs"]["backend"].get("name", "").lower()
    assert backend_commands != frontend_commands  # sanity: genuinely different jobs


# ---------------------------------------------------------------------------
# 2. Evaluation is ACTUALLY invoked by CI - resolved against real files,
# not merely a plausible-looking string.
# ---------------------------------------------------------------------------


def test_evaluation_command_glob_patterns_resolve_to_real_existing_test_files():
    job = _evaluation_job()
    run_line = _pytest_run_step(job)["run"]
    # Extract the path/glob arguments that follow "pytest -q".
    args = run_line.split("pytest -q", 1)[1].split()
    assert args, "evaluation command must pass at least one path/glob to pytest"

    matched_files: set[str] = set()
    for pattern in args:
        matches = glob.glob(str(REPO_ROOT / pattern))
        assert matches, f"evaluation command pattern {pattern!r} matched no real file on disk"
        matched_files.update(matches)

    assert len(matched_files) >= 15, "evaluation gate should cover the full Phase 16 benchmark suite plus Phase 21 corpus-refresh evaluation"


def test_evaluation_command_covers_every_current_phase_16_test_file():
    job = _evaluation_job()
    run_line = _pytest_run_step(job)["run"]
    args = run_line.split("pytest -q", 1)[1].split()

    phase_16_pattern = next((a for a in args if "phase_16" in a), None)
    assert phase_16_pattern is not None, "evaluation command must reference the Phase 16 evaluation/benchmark suite"

    pattern_matches = {Path(p).name for p in glob.glob(str(REPO_ROOT / phase_16_pattern))}
    actual_phase_16_files = {p.name for p in REPO_ROOT.glob("tests/test_phase_16_*.py")}
    assert pattern_matches == actual_phase_16_files


def test_evaluation_command_covers_phase_21_corpus_refresh_evaluation_gate():
    job = _evaluation_job()
    run_line = _pytest_run_step(job)["run"]
    assert "tests/test_phase_21_corpus_refresh.py" in run_line
    assert "tests/test_phase_21_acceptance.py" in run_line
    assert (REPO_ROOT / "tests" / "test_phase_21_corpus_refresh.py").is_file()
    assert (REPO_ROOT / "tests" / "test_phase_21_acceptance.py").is_file()


# ---------------------------------------------------------------------------
# 3. Evaluation failure must cause CI failure - no error-swallowing.
# ---------------------------------------------------------------------------


def test_evaluation_step_does_not_swallow_failures():
    job = _evaluation_job()
    for step in job["steps"]:
        assert step.get("continue-on-error") is not True
    assert "|| true" not in _run_commands(job)
    assert "|| exit 0" not in _run_commands(job)


# ---------------------------------------------------------------------------
# 4. No secrets, no deployment, no Docker in the evaluation job.
# ---------------------------------------------------------------------------


def test_evaluation_job_uses_no_secrets():
    job = _evaluation_job()
    job_text = yaml.safe_dump(job)
    assert "secrets." not in job_text


def test_evaluation_job_does_not_invoke_deployment():
    job = _evaluation_job()
    executable_text = " ".join(f"{s.get('uses', '')} {s.get('run', '')}".lower() for s in job["steps"])
    for forbidden in ("render.com", "onrender.com", "deploy", "docker"):
        assert forbidden not in executable_text


def test_evaluation_job_installs_only_from_requirements_dev_txt():
    job = _evaluation_job()
    run_commands = _run_commands(job)
    assert "requirements-dev.txt" in run_commands
    assert "requirements-render.txt" not in run_commands
    assert "npm" not in run_commands  # no Node/frontend tooling needed for this job


# ---------------------------------------------------------------------------
# 5. No release/rollback/staging functionality introduced prematurely.
# ---------------------------------------------------------------------------


def test_no_release_rollback_tag_or_publish_job_introduced():
    # [ENGINEERING RECOMMENDATION] bare "release" removed from this list:
    # Step 22.4 legitimately introduces a job literally named
    # "release-artifact" that only GENERATES a manifest (never deploys/
    # publishes/promotes it - proven separately by
    # tests/test_phase_22_release_artifact.py::test_release_artifact_job_does_not_deploy_or_use_secrets
    # and ::test_no_rollback_tag_or_publish_job_introduced). Every
    # other forbidden fragment here - actual deployment/promotion
    # vocabulary - is unchanged and still enforced.
    # [ENGINEERING RECOMMENDATION] "staging" also removed from this list:
    # Step 22.5 legitimately introduces a job literally named "staging"
    # that only runs an ephemeral, local-to-the-runner smoke test (never
    # a live Render deployment, never production - proven separately by
    # tests/test_phase_22_staging.py::test_staging_job_never_touches_render_or_production).
    # [ENGINEERING RECOMMENDATION] bare "tag" narrowed to "release-tag":
    # bare "tag" is a false-positive substring of the now-legitimate
    # "staging" job name (s-TAG-ing) - "release-tag" is the actual
    # forbidden concept (a git-tag-based release/versioning job) and is
    # unambiguous.
    # [ENGINEERING RECOMMENDATION] "production" also removed from this
    # list: Step 22.6 legitimately introduces a job literally named
    # "production" that deploys to the existing Phase 20 Render services
    # only after every earlier gate (including staging) passes - its own
    # full contract, including that it never deploys prematurely and
    # never bypasses staging, is covered by
    # tests/test_phase_22_production.py. "rollback" remains forbidden
    # here unchanged: this step does not introduce it (Step 22.7's scope).
    jobs = _load_workflow()["jobs"]
    for forbidden_job_name_fragment in ("rollback", "release-tag", "publish"):
        for job_id, job in jobs.items():
            assert forbidden_job_name_fragment not in job_id.lower()
            assert forbidden_job_name_fragment not in job.get("name", "").lower()


def test_workflow_triggers_and_permissions_unchanged_by_this_step():
    workflow = _load_workflow()
    triggers = workflow.get("on") if "on" in workflow else workflow.get(True)
    assert set(triggers.keys()) == {"push", "pull_request"}
    assert workflow.get("permissions") == {"contents": "read"}
