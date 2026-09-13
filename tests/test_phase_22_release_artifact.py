"""
Phase 22 Step 22.4 tests: release identity + reproducible release-artifact
manifest (docs/PHASE_22_CICD_PRODUCTION_RELEASE.md;
scripts/build_release_manifest.py; .github/workflows/ci.yml
`release-artifact` job).

Behavior-based tests against the real script (imported directly, not
re-implemented/mocked) wherever practical, plus structural checks against
the workflow's own committed shape for the CI-integration requirements
that cannot be proven any other way (no live GitHub Actions run is
triggered here).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
SCRIPTS_DIR = REPO_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import build_release_manifest as release_module  # noqa: E402


def _load_workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _release_artifact_job() -> dict:
    return _load_workflow()["jobs"]["release-artifact"]


# ---------------------------------------------------------------------------
# 1. Release identity is deterministic, git-derived, never invented
# ---------------------------------------------------------------------------


def test_release_id_matches_real_git_head_sha():
    identity = release_module.compute_release_identity()
    ground_truth = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert identity["release_id"] == ground_truth


def test_release_id_is_a_full_length_hex_commit_sha_not_uuid_or_timestamp():
    identity = release_module.compute_release_identity()
    assert re.fullmatch(r"[0-9a-f]{40}", identity["release_id"])
    # Not an ISO timestamp, not a UUID4 (which has fixed dashes/version nibble).
    assert "-" not in identity["release_id"]
    assert "T" not in identity["release_id"]


def test_source_tree_clean_flag_matches_real_git_status():
    identity = release_module.compute_release_identity()
    ground_truth = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout
    assert identity["source_tree_clean"] == (ground_truth == "")


# ---------------------------------------------------------------------------
# 2. API_VERSION is never mistaken for, or used to compute, the release id
# ---------------------------------------------------------------------------


def test_release_id_is_independent_of_api_contract_version():
    content = release_module.build_manifest_content(release_id="f" * 40, source_tree_clean=True)
    assert content["release_id"] == "f" * 40
    assert content["api_contract_version_reference"] == "v1"
    assert content["release_id"] != content["api_contract_version_reference"]
    # Changing the (informational) API version reference must never be
    # able to change the release identity - proven by construction: the
    # function that extracts it is never called by compute_release_identity.
    import inspect

    identity_source = inspect.getsource(release_module.compute_release_identity)
    assert "_extract_api_contract_version" not in identity_source


# ---------------------------------------------------------------------------
# 3. Artifact generation succeeds and produces valid, well-shaped JSON
# ---------------------------------------------------------------------------


def test_manifest_generation_succeeds_and_has_expected_shape():
    manifest = release_module.build_release_manifest(release_id="a" * 40, source_tree_clean=True, created_at="2026-01-01T00:00:00+00:00")
    assert set(manifest.keys()) == {"content", "manifest_hash", "manifest_metadata"}
    content = manifest["content"]
    for key in (
        "schema_version", "artifact_schema", "release_id", "source_tree_clean",
        "api_contract_version_reference", "deployment_config_files",
        "backend_app_content_hash", "backend_app_file_count",
        "frontend_app_content_hash", "frontend_app_file_count",
    ):
        assert key in content
    assert manifest["manifest_metadata"] == {"created_at": "2026-01-01T00:00:00+00:00"}


def test_write_manifest_produces_valid_json_on_disk(tmp_path):
    manifest = release_module.build_release_manifest(release_id="b" * 40, source_tree_clean=True)
    output_path = tmp_path / "release_manifest.json"
    release_module.write_manifest(manifest, output_path)
    reloaded = json.loads(output_path.read_text(encoding="utf-8"))
    assert reloaded == manifest


def test_cli_main_generates_a_manifest_file(tmp_path):
    output_path = tmp_path / "cli_release_manifest.json"
    exit_code = release_module.main(["--output", str(output_path), "--created-at", "2026-01-01T00:00:00+00:00"])
    assert exit_code == 0
    assert output_path.is_file()
    reloaded = json.loads(output_path.read_text(encoding="utf-8"))
    assert re.fullmatch(r"[0-9a-f]{64}", reloaded["manifest_hash"])


# ---------------------------------------------------------------------------
# 4. Determinism / reproducibility
# ---------------------------------------------------------------------------


def test_manifest_hash_is_identical_across_repeated_builds_of_the_same_state():
    manifest_a = release_module.build_release_manifest(release_id="c" * 40, source_tree_clean=True, created_at="2026-01-01T00:00:00+00:00")
    manifest_b = release_module.build_release_manifest(release_id="c" * 40, source_tree_clean=True, created_at="2026-01-01T00:00:00+00:00")
    assert manifest_a == manifest_b
    assert manifest_a["manifest_hash"] == manifest_b["manifest_hash"]


def test_manifest_hash_is_unaffected_by_created_at_but_content_is_reused():
    manifest_a = release_module.build_release_manifest(release_id="d" * 40, source_tree_clean=True, created_at="2026-01-01T00:00:00+00:00")
    manifest_b = release_module.build_release_manifest(release_id="d" * 40, source_tree_clean=True, created_at="2099-12-31T23:59:59+00:00")
    assert manifest_a["manifest_hash"] == manifest_b["manifest_hash"]
    assert manifest_a["content"] == manifest_b["content"]
    assert manifest_a["manifest_metadata"] != manifest_b["manifest_metadata"]


def test_app_content_hash_changes_when_a_source_file_actually_changes(tmp_path):
    scratch = tmp_path / "app"
    scratch.mkdir()
    (scratch / "module_a.py").write_text("value = 1\n", encoding="utf-8")
    (scratch / "module_b.py").write_text("value = 2\n", encoding="utf-8")

    before = release_module.collect_app_content_hash(scratch)
    (scratch / "module_a.py").write_text("value = 999\n", encoding="utf-8")
    after = release_module.collect_app_content_hash(scratch)

    assert before["content_hash"] != after["content_hash"]
    assert before["file_count"] == after["file_count"] == 2


def test_app_content_hash_is_independent_of_file_visit_order(tmp_path):
    scratch_a = tmp_path / "order_a"
    scratch_b = tmp_path / "order_b"
    scratch_a.mkdir()
    scratch_b.mkdir()
    # Create the same two files in reverse order between the two directories.
    (scratch_a / "aaa.py").write_text("1\n", encoding="utf-8")
    (scratch_a / "zzz.py").write_text("2\n", encoding="utf-8")
    (scratch_b / "zzz.py").write_text("2\n", encoding="utf-8")
    (scratch_b / "aaa.py").write_text("1\n", encoding="utf-8")

    result_a = release_module.collect_app_content_hash(scratch_a)
    result_b = release_module.collect_app_content_hash(scratch_b)
    assert result_a["content_hash"] == result_b["content_hash"]


def test_app_content_hash_ignores_pycache_and_compiled_artifacts(tmp_path):
    scratch = tmp_path / "app_with_cache"
    scratch.mkdir()
    (scratch / "module.py").write_text("value = 1\n", encoding="utf-8")
    before = release_module.collect_app_content_hash(scratch)

    cache_dir = scratch / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "module.cpython-310.pyc").write_bytes(b"\x00\x01\x02fake-bytecode")
    (scratch / "module.pyc").write_bytes(b"more-fake-bytecode")

    after = release_module.collect_app_content_hash(scratch)
    assert before["content_hash"] == after["content_hash"]
    assert before["file_count"] == after["file_count"] == 1


def test_app_content_hash_is_none_for_empty_or_missing_directory(tmp_path):
    missing = tmp_path / "does-not-exist"
    assert release_module.collect_app_content_hash(missing) == {"content_hash": None, "file_count": 0}

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    assert release_module.collect_app_content_hash(empty_dir) == {"content_hash": None, "file_count": 0}


# ---------------------------------------------------------------------------
# 5. Integrity metadata is correct
# ---------------------------------------------------------------------------


def test_deployment_config_file_hashes_match_real_files_on_disk():
    records = release_module.hash_deployment_config_files()
    assert len(records) == len(release_module.DEPLOYMENT_CONFIG_FILES)
    for record in records:
        real_path = REPO_ROOT / record["relative_path"]
        assert release_module.hash_file(real_path) == record["content_hash"]
        assert real_path.stat().st_size == record["size_bytes"]


def test_missing_deployment_config_file_raises_rather_than_silently_skipping(monkeypatch):
    monkeypatch.setattr(release_module, "DEPLOYMENT_CONFIG_FILES", ("this/file/does/not/exist.txt",))
    with pytest.raises(release_module.ReleaseManifestError):
        release_module.hash_deployment_config_files()


def test_manifest_hash_recomputation_matches_stored_hash():
    manifest = release_module.build_release_manifest(release_id="e" * 40, source_tree_clean=True)
    recomputed = release_module.compute_manifest_hash(manifest["content"])
    assert recomputed == manifest["manifest_hash"]


# ---------------------------------------------------------------------------
# 6. Excluded content
# ---------------------------------------------------------------------------


def test_manifest_never_references_venv_node_modules_or_env_files():
    manifest = release_module.build_release_manifest(release_id="1" * 40, source_tree_clean=True)
    raw = json.dumps(manifest)
    for forbidden in (".venv", "node_modules", ".env", "secret", "password", "api_key", "credential"):
        assert forbidden not in raw.lower()


def test_manifest_does_not_reference_docker_or_container():
    manifest = release_module.build_release_manifest(release_id="2" * 40, source_tree_clean=True)
    raw = json.dumps(manifest).lower()
    assert "docker" not in raw
    assert "container" not in raw


def test_only_named_deployment_config_files_are_hashed_never_arbitrary_root_files():
    assert set(release_module.DEPLOYMENT_CONFIG_FILES) == {
        "render.yaml",
        "requirements-render.txt",
        ".python-version",
        "frontend/.node-version",
        "frontend/package.json",
        "frontend/package-lock.json",
    }


# ---------------------------------------------------------------------------
# 7. CI integration: generated only after quality/evaluation gates, never deploys
# ---------------------------------------------------------------------------


def test_release_artifact_job_exists_and_depends_on_all_quality_gates():
    job = _release_artifact_job()
    assert set(job.get("needs", [])) == {"backend", "frontend", "evaluation"}


def test_release_artifact_job_runs_the_real_script():
    job = _release_artifact_job()
    run_commands = " ".join(s.get("run", "") for s in job["steps"])
    assert "scripts/build_release_manifest.py" in run_commands
    assert (REPO_ROOT / "scripts" / "build_release_manifest.py").is_file()


def test_release_artifact_job_uses_ci_native_upload_not_external_service():
    job = _release_artifact_job()
    upload_step = next(s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/upload-artifact"))
    assert upload_step["with"]["path"] == "release_manifest.json"


def test_release_artifact_job_installs_no_new_dependencies():
    job = _release_artifact_job()
    run_commands = " ".join(s.get("run", "") for s in job["steps"])
    assert "pip install" not in run_commands
    assert "npm" not in run_commands


def test_release_artifact_job_does_not_deploy_or_use_secrets():
    job = _release_artifact_job()
    job_text = yaml.safe_dump(job)
    assert "secrets." not in job_text
    executable_text = " ".join(f"{s.get('uses', '')} {s.get('run', '')}".lower() for s in job["steps"])
    for forbidden in ("render.com", "onrender.com", "deploy", "docker"):
        assert forbidden not in executable_text


def test_no_rollback_tag_or_publish_job_introduced():
    # [ENGINEERING RECOMMENDATION] "staging" removed from this list: Step
    # 22.5 (docs/PHASE_22_CICD_PRODUCTION_RELEASE.md) legitimately
    # introduces a job literally named "staging" that only runs an
    # ephemeral, local-to-the-runner smoke test (never a live Render
    # deployment, never production) gated on this release-artifact job -
    # its own full contract is covered by tests/test_phase_22_staging.py.
    # [ENGINEERING RECOMMENDATION] "production" also removed from this
    # list: Step 22.6 legitimately introduces a job literally named
    # "production" that deploys to the existing Phase 20 Render services,
    # gated on backend+frontend+evaluation+release-artifact+staging all
    # passing - its own full contract is covered by
    # tests/test_phase_22_production.py. Every other forbidden fragment
    # here is unchanged and still enforced.
    jobs = _load_workflow()["jobs"]
    for forbidden_fragment in ("rollback", "release-tag", "publish"):
        for job_id, job in jobs.items():
            assert forbidden_fragment not in job_id.lower()
            assert forbidden_fragment not in job.get("name", "").lower()


def test_workflow_triggers_and_permissions_still_unchanged():
    workflow = _load_workflow()
    triggers = workflow.get("on") if "on" in workflow else workflow.get(True)
    assert set(triggers.keys()) == {"push", "pull_request"}
    assert workflow.get("permissions") == {"contents": "read"}
