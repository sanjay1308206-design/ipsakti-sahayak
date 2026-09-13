"""
Phase 19 tests: source-discipline, phase-boundary, and dependency/
configuration-review audit (docs/PHASE_19_SECURITY_ADVERSARIAL_HARDENING.md)
for Phase 19's own additions - mirrors the audit convention established by
tests/test_phase_17_regression.py, scoped to what Phase 19 itself touched:
src/api/errors.py's new StarletteHTTPException handler, src/evaluation/
redteam.py's additive PHASE19_REDTEAM_CASES, config/phase19_redteam_cases.yaml,
and this phase's three new test files. No Phase 20+ (deployment/
observability/CI) functionality is implemented anywhere in this phase.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
CONFIG_DIR = REPO_ROOT / "config"
SRC_DIR = REPO_ROOT / "src"
FRONTEND_DIR = REPO_ROOT / "frontend"

MASTER_REFERENCE_PDF = REPO_ROOT / "PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf"
MASTER_REFERENCE_HASH_FILE = DOCS_DIR / "_master_reference.sha256"

EXPECTED_PY_DEPENDENCIES = {
    "pytest", "pyyaml", "pypdf", "sentence-transformers", "faiss-cpu", "numpy", "fastapi", "pydantic", "uvicorn", "httpx",
}
EXPECTED_FRONTEND_RUNTIME_DEPENDENCIES = {"react", "react-dom"}

# Same literal-assignment pattern used by test_phase_17_regression.py -
# detects an actual hard-coded secret VALUE, never the English word
# appearing in a docstring/comment.
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r'(api[_-]?key|password|access[_-]?token|auth[_-]?token|secret[_-]?key)\s*[=:]\s*["\'][^"\']{4,}["\']', re.IGNORECASE
)

PHASE_00_THROUGH_18_DOCS = [
    "PHASE_00_SCOPE_AND_ACCEPTANCE.md", "PHASE_01_DOMAIN_TAXONOMY.md", "PHASE_01_REGULATORY_DECISION_TREE.md",
    "PHASE_02_AUTHORITY_MATRIX.md", "PHASE_02_CORPUS_ADMISSION_POLICY.md", "PHASE_02_SOURCE_CONFLICT_POLICY.md",
    "PHASE_03_DOCUMENT_INGESTION.md", "PHASE_03_LEGAL_STRUCTURE_EXTRACTION.md", "PHASE_04_LEGAL_AWARE_CHUNKING.md",
    "PHASE_05_BM25_BASELINE.md", "PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md", "PHASE_07_HYBRID_FUSION_AND_RERANKING.md",
    "PHASE_08_EVIDENCE_OBJECT_AND_CITATION_ARCHITECTURE.md", "PHASE_09_CITATION_VALIDATION.md",
    "PHASE_10_GROUNDED_GENERATION.md", "PHASE_11_FORMULATION_CLASSIFICATION.md", "PHASE_12_JURISDICTION_FIREWALL.md",
    "PHASE_13_CONFIDENCE_SAFETY_ABSTENTION.md", "PHASE_14_MULTILINGUAL_DELIVERY.md", "PHASE_15_HUMAN_IN_THE_LOOP.md",
    "PHASE_16_EVALUATION_AND_RED_TEAM.md", "PHASE_17_BACKEND_PRODUCTIZATION.md", "PHASE_18_FRONTEND_PRODUCTIZATION.md",
]


def test_master_reference_pdf_still_byte_for_byte_unchanged():
    assert MASTER_REFERENCE_PDF.is_file()
    assert MASTER_REFERENCE_HASH_FILE.is_file()
    recorded_hash = MASTER_REFERENCE_HASH_FILE.read_text(encoding="utf-8").strip().split()[0]
    actual_hash = hashlib.sha256(MASTER_REFERENCE_PDF.read_bytes()).hexdigest()
    assert actual_hash == recorded_hash


def test_phase_00_through_18_docs_still_present_and_intact():
    for name in PHASE_00_THROUGH_18_DOCS:
        doc = DOCS_DIR / name
        assert doc.is_file() and doc.stat().st_size > 0, f"missing or empty: {name}"


def test_phase_19_doc_exists_and_nonempty():
    doc = DOCS_DIR / "PHASE_19_SECURITY_ADVERSARIAL_HARDENING.md"
    assert doc.is_file()
    assert doc.stat().st_size > 0


def test_phase_19_redteam_config_file_exists():
    assert (CONFIG_DIR / "phase19_redteam_cases.yaml").is_file()


def test_api_source_directory_unchanged_file_set():
    # Phase 19 modifies src/api/errors.py's contents but adds no new module
    # to the package - the file set itself must stay exactly what Phase 17
    # established.
    assert {p.name for p in (SRC_DIR / "api").glob("*.py")} == {
        "__init__.py", "app.py", "routes.py", "schemas.py", "errors.py", "dependencies.py",
    }


def test_evaluation_source_directory_unchanged_file_set():
    # Phase 19 adds cases to the existing src/evaluation/redteam.py module,
    # never a new module.
    assert {p.name for p in (SRC_DIR / "evaluation").glob("*.py")} == {
        "__init__.py", "models.py", "metrics.py", "benchmark.py", "redteam.py", "runner.py", "serialize.py",
    }


def test_no_new_python_dependency_declared_beyond_phase_17_baseline():
    req_dev_raw = (REPO_ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    assert not (REPO_ROOT / "requirements.txt").exists()
    declared_packages = set()
    for line in req_dev_raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name = re.split(r"[><=!~\[]", stripped, maxsplit=1)[0].strip().lower()
        if name:
            declared_packages.add(name)
    assert declared_packages == EXPECTED_PY_DEPENDENCIES, f"unexpected Python dependency set for Phase 19: {declared_packages}"


def test_no_new_frontend_runtime_dependency_declared():
    package_json = json.loads((FRONTEND_DIR / "package.json").read_text(encoding="utf-8"))
    assert set(package_json.get("dependencies", {}).keys()) == EXPECTED_FRONTEND_RUNTIME_DEPENDENCIES


def test_no_wildcard_cors_configured_anywhere():
    for py_file in (SRC_DIR / "api").glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        assert 'allow_origins=["*"]' not in text
        assert "allow_origins=['*']" not in text


def test_no_debug_or_autoreload_flag_enabled_anywhere_in_api_source():
    for py_file in (SRC_DIR / "api").glob("*.py"):
        text = py_file.read_text(encoding="utf-8").lower().replace(" ", "")
        assert "debug=true" not in text
        assert "reload=true" not in text


def test_no_hardcoded_secret_anywhere_in_phase_19_touched_source():
    for py_file in [SRC_DIR / "api" / "errors.py", SRC_DIR / "evaluation" / "redteam.py"]:
        text = py_file.read_text(encoding="utf-8")
        assert not SECRET_ASSIGNMENT_PATTERN.search(text), f"possible hardcoded secret in {py_file}"


def test_no_phase_20_or_later_directories_exist_yet():
    # [ENGINEERING RECOMMENDATION] ".github" removed from this list: Phase
    # 22 (CI/CD & Production Release) legitimately introduces
    # .github/workflows/ci.yml (docs/PHASE_22_CICD_PRODUCTION_RELEASE.md),
    # the same disclosed pattern already used when Phase 20/21 arrived
    # (e.g. Phase 6 relaxing Phase 4/5's dependency checks, Phase 17
    # dropping fastapi from ten earlier forbidden-dependency lists) -
    # never a silent removal, and every other forbidden name here is
    # unchanged and still enforced.
    for forbidden in ("deployment", "observability", "k8s", "kubernetes", "reviewers", "data", "corpus", "indexes", "index"):
        assert not (REPO_ROOT / forbidden).exists(), f"'{forbidden}/' would imply Phase 20+ functionality, which Phase 19 must not create"


def test_phase19_redteam_cases_are_additive_not_a_replacement_of_phase16():
    from evaluation.redteam import PHASE19_REDTEAM_CASES, REDTEAM_CASES

    assert len(REDTEAM_CASES) == 21, "Phase 16's original 21 cases must remain untouched"
    assert len(PHASE19_REDTEAM_CASES) == 15
    phase16_ids = {c.case_id for c in REDTEAM_CASES}
    phase19_ids = {c.case_id for c in PHASE19_REDTEAM_CASES}
    assert phase16_ids.isdisjoint(phase19_ids)
    assert phase19_ids == {f"P19-{i:02d}" for i in range(1, 16)}


def test_starlette_http_exception_handler_never_returns_200():
    # The Phase 19 fix in src/api/errors.py: this handler exists specifically
    # for framework-level rejections, never a success path.
    text = (SRC_DIR / "api" / "errors.py").read_text(encoding="utf-8")
    assert "StarletteHTTPException" in text
    assert "status_code=exc.status_code" in text
