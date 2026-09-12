"""
Phase 20 tests: deployment-configuration-only checks
(docs/PHASE_20_DEPLOYMENT_ENGINEERING.md). This phase adds no RAG/
business/security logic - these tests verify only that the Render Free
deployment configuration (render.yaml, requirements-render.txt, version
pin files) is internally consistent, ₹0-cost-safe, and does not modify
or weaken anything Phases 0-19 already established.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
FRONTEND_DIR = REPO_ROOT / "frontend"

EXPECTED_DEV_DEPENDENCIES = {
    "pytest", "pyyaml", "pypdf", "sentence-transformers", "faiss-cpu", "numpy", "fastapi", "pydantic", "uvicorn", "httpx",
}
# [OUR ENHANCEMENT] Phase 20.4-B Fix 1 + Fix 2: numpy/faiss-cpu/PyYAML
# were added, one real Render deployment failure at a time
# (ModuleNotFoundError: numpy, then faiss's own import of chunking.models
# triggering ingestion's own `import yaml`), each proving the package IS
# required at application STARTUP - see requirements-render.txt's own
# header comment for the full, corrected import-chain explanation of
# both. `pypdf` was checked the same way (a clean venv with only this
# file's packages was proven to start successfully WITHOUT pypdf
# installed) and correctly stays forbidden: `ingestion/extractors.py`
# imports it lazily, inside a function, never at module top level, and
# nothing on the deployed app's startup or default request path calls
# that function. `sentence-transformers`/`torch`/`transformers` remain
# forbidden for the same reason (lazy, inside `SentenceTransformerEmbeddingModel`/
# `CrossEncoderReranker`'s own load methods, never called by the default
# path). `pytest`/`httpx` remain forbidden - test-only, never imported by
# `src/api/`/`src/application/` or anything they call.
EXPECTED_RENDER_DEPENDENCIES = {"fastapi", "pydantic", "uvicorn", "numpy", "faiss-cpu", "pyyaml"}
FORBIDDEN_RENDER_DEPENDENCIES = {"pytest", "pypdf", "sentence-transformers", "httpx", "torch", "transformers"}

SECRET_ASSIGNMENT_PATTERN = re.compile(
    r'(api[_-]?key|password|access[_-]?token|auth[_-]?token|secret[_-]?key)\s*[=:]\s*["\']?[^"\'\s]{4,}', re.IGNORECASE
)


def _declared_package_names(requirements_text: str) -> set:
    declared = set()
    for line in requirements_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name = re.split(r"[><=!~\[]", stripped, maxsplit=1)[0].strip().lower()
        if name:
            declared.add(name)
    return declared


def test_requirements_render_file_exists():
    assert (REPO_ROOT / "requirements-render.txt").is_file()


def test_requirements_render_contains_exactly_the_runtime_deps_the_deployed_app_imports():
    text = (REPO_ROOT / "requirements-render.txt").read_text(encoding="utf-8")
    declared = _declared_package_names(text)
    assert declared == EXPECTED_RENDER_DEPENDENCIES, f"unexpected Render deployment dependency set: {declared}"
    assert declared.isdisjoint(FORBIDDEN_RENDER_DEPENDENCIES)


def test_requirements_render_pins_match_requirements_dev_pins():
    # Never a silently different/unverified version range from the one
    # already verified working in requirements-dev.txt.
    dev_text = (REPO_ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    render_text = (REPO_ROOT / "requirements-render.txt").read_text(encoding="utf-8")

    def _pin(text: str, package: str) -> str:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith(package.lower()) and not stripped.startswith("#"):
                return stripped
        raise AssertionError(f"{package} not found")

    for package in ("fastapi", "pydantic", "uvicorn", "numpy", "faiss-cpu", "pyyaml"):
        assert _pin(render_text, package) == _pin(dev_text, package)


def test_requirements_dev_txt_is_completely_unmodified_by_phase_20():
    # Phase 20 must never touch requirements-dev.txt (Phase 17/19's own
    # regression tests already assert its exact dependency set - this is
    # a Phase-20-specific restatement of the same invariant).
    declared = _declared_package_names((REPO_ROOT / "requirements-dev.txt").read_text(encoding="utf-8"))
    assert declared == EXPECTED_DEV_DEPENDENCIES


def test_python_version_pin_file_exists_and_is_a_plausible_version():
    pin = (REPO_ROOT / ".python-version").read_text(encoding="utf-8").strip()
    assert re.match(r"^3\.\d+(\.\d+)?$", pin), f"unexpected .python-version content: {pin!r}"


def test_frontend_node_version_pin_file_exists_and_is_a_plausible_version():
    pin = (FRONTEND_DIR / ".node-version").read_text(encoding="utf-8").strip()
    assert re.match(r"^\d+(\.\d+){0,2}$", pin), f"unexpected frontend/.node-version content: {pin!r}"


def test_render_yaml_exists_and_parses_as_valid_yaml():
    doc = yaml.safe_load((REPO_ROOT / "render.yaml").read_text(encoding="utf-8"))
    assert isinstance(doc, dict)
    assert "services" in doc
    assert isinstance(doc["services"], list) and len(doc["services"]) == 2


def _service(doc: dict, name: str) -> dict:
    for svc in doc["services"]:
        if svc.get("name") == name:
            return svc
    raise AssertionError(f"service {name!r} not found in render.yaml")


def test_render_yaml_declares_exactly_two_free_services_no_database_no_docker():
    doc = yaml.safe_load((REPO_ROOT / "render.yaml").read_text(encoding="utf-8"))
    assert "databases" not in doc
    for svc in doc["services"]:
        assert svc.get("runtime") != "docker"
        if svc.get("plan") is not None:
            assert svc["plan"] == "free", f"{svc.get('name')} is not on the free plan: {svc.get('plan')}"


def test_render_yaml_backend_service_uses_the_approved_start_command_and_health_path():
    doc = yaml.safe_load((REPO_ROOT / "render.yaml").read_text(encoding="utf-8"))
    backend = _service(doc, "ipsakti-backend")
    assert backend["runtime"] == "python"
    assert backend["startCommand"] == "uvicorn api.app:app --host 0.0.0.0 --port $PORT --app-dir src"
    assert backend["buildCommand"] == "pip install -r requirements-render.txt"
    assert backend["healthCheckPath"] == "/health"
    assert "requirements-dev.txt" not in backend["buildCommand"]


def test_render_yaml_frontend_service_builds_and_publishes_the_vite_dist_directory():
    doc = yaml.safe_load((REPO_ROOT / "render.yaml").read_text(encoding="utf-8"))
    frontend = _service(doc, "ipsakti-frontend")
    assert frontend["runtime"] == "static"
    assert "npm run build" in frontend["buildCommand"]
    assert frontend["staticPublishPath"] in ("./dist", "dist")


def test_render_yaml_never_hardcodes_a_backend_or_frontend_url_or_a_secret():
    # "onrender.com" appears only in this file's own explanatory comments
    # (describing what a Render URL IS) - the real invariant is that no
    # env var's actual `value:` is ever set to a live onrender.com URL or
    # a secret-shaped literal; both URL-bearing vars use `sync: false`
    # instead (asserted separately below).
    text = (REPO_ROOT / "render.yaml").read_text(encoding="utf-8")
    non_comment_lines = [line for line in text.splitlines() if not line.strip().startswith("#")]
    non_comment_text = "\n".join(non_comment_lines)
    assert "onrender.com" not in non_comment_text
    assert not SECRET_ASSIGNMENT_PATTERN.search(non_comment_text.replace("sync: false", ""))


def test_render_yaml_cors_and_api_base_url_vars_are_manually_set_not_hardcoded():
    doc = yaml.safe_load((REPO_ROOT / "render.yaml").read_text(encoding="utf-8"))
    backend_vars = {v["key"]: v for v in _service(doc, "ipsakti-backend")["envVars"]}
    frontend_vars = {v["key"]: v for v in _service(doc, "ipsakti-frontend")["envVars"]}
    assert backend_vars["IPSAKTI_CORS_ALLOWED_ORIGINS"].get("sync") is False
    assert "value" not in backend_vars["IPSAKTI_CORS_ALLOWED_ORIGINS"]
    assert frontend_vars["VITE_API_BASE_URL"].get("sync") is False
    assert "value" not in frontend_vars["VITE_API_BASE_URL"]


def test_render_yaml_never_declares_a_wildcard_cors_value():
    text = (REPO_ROOT / "render.yaml").read_text(encoding="utf-8")
    assert 'value: "*"' not in text
    assert "value: '*'" not in text


def test_src_api_app_py_was_not_modified_to_add_port_or_uvicorn_run():
    # Phase 20 instructions: configure the start command externally,
    # never by adding os.environ["PORT"]/uvicorn.run(...) to app.py itself.
    text = (SRC_DIR / "api" / "app.py").read_text(encoding="utf-8")
    assert "uvicorn.run" not in text
    assert "os.environ" not in text
    assert 'PORT' not in text


def test_no_docker_or_procfile_artifacts_were_introduced():
    for forbidden in ("Dockerfile", "docker-compose.yml", "docker-compose.yaml", "Procfile"):
        assert not (REPO_ROOT / forbidden).exists(), f"{forbidden} should not exist - Docker was not determined necessary"


def test_no_database_dependency_or_service_introduced_anywhere():
    render_text = (REPO_ROOT / "render.yaml").read_text(encoding="utf-8").lower()
    for forbidden in ("postgres", "redis", "sqlite", "mysql", "mongodb"):
        assert forbidden not in render_text
