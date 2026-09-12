"""
Phase 17 tests: Master Reference integrity, Phase 0-16 regression
protection, repository cleanliness for the Phase 16-17 boundary,
phase-boundary audit (no Phase 18+ implementation leaked in), dependency
discipline, and docs/PHASE_17_BACKEND_PRODUCTIZATION.md completeness.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from _repo_scan import is_repo_scan_excluded

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
CONFIG_DIR = REPO_ROOT / "config"
SRC_DIR = REPO_ROOT / "src"

MASTER_REFERENCE_PDF = REPO_ROOT / "PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf"
MASTER_REFERENCE_HASH_FILE = DOCS_DIR / "_master_reference.sha256"

EXPECTED_CONFIG_FILES_THROUGH_PHASE_16 = {
    "acceptance_contract.yaml", "domain_taxonomy.yaml", "regulatory_decision_tree.yaml", "classification_contract.yaml",
    "authority_matrix.yaml", "corpus_provenance_schema.yaml", "corpus_lock.yaml", "document_ingestion_contract.yaml",
    "document_structure_schema.yaml", "chunking_contract.yaml", "chunk_schema.yaml", "bm25_contract.yaml",
    "retrieval_result_schema.yaml", "dense_retrieval_contract.yaml", "dense_index_schema.yaml",
    "hybrid_retrieval_contract.yaml", "hybrid_result_schema.yaml", "evidence_contract.yaml", "evidence_schema.yaml",
    "citation_validation_contract.yaml", "citation_validation_schema.yaml", "grounded_generation_contract.yaml",
    "grounded_generation_schema.yaml", "formulation_classification_contract.yaml", "jurisdiction_firewall_contract.yaml",
    "confidence_safety_contract.yaml", "multilingual_delivery_contract.yaml", "human_review_contract.yaml",
    "evaluation_contract.yaml", "redteam_cases.yaml",
}

FUTURE_IMPLEMENTATION_MODULE_HINTS = ("scraper", "crawler", "ocr", "pdf_parser", "risk_scoring")

FORBIDDEN_DEPENDENCY_PACKAGES = (
    "langchain", "llama-index", "llamaindex", "chromadb", "qdrant", "weaviate", "pinecone", "kubernetes", "neo4j",
    "rank-bm25", "rank_bm25", "tiktoken", "openai", "google-generativeai", "google-genai", "transformers",
    "llama-cpp-python", "geopy", "geoip2", "sqlalchemy", "psycopg2", "celery", "redis", "django",
)

# Literal-assignment patterns - detects an actual hard-coded secret VALUE,
# never merely the English word appearing in a docstring/comment (which
# would be a false positive against this phase's own honest disclosures
# about NOT having credentials, matching the pattern already fixed in
# Phase 10/12/15/16's own regression files).
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r'(api[_-]?key|password|access[_-]?token|auth[_-]?token|secret[_-]?key)\s*[=:]\s*["\'][^"\']{4,}["\']', re.IGNORECASE
)

REQUIRED_DOC_SECTIONS = [
    "A. Objective", "B. Scope", "C. Non-Scope", "D. Architecture", "E. FastAPI Boundary", "F. Application Service",
    "G. Domain/API Separation", "H. API Versioning", "I. Health Endpoint", "J. Query Endpoint", "K. Request Contract",
    "L. Response Contract", "M. Error Handling", "N. Safety Semantics", "O. Citation Handling", "P. Evidence Handling",
    "Q. Jurisdiction Handling", "R. Classification Handling", "S. Multilingual Handling", "T. Human-Review Handling",
    "U. Configuration", "V. Provider Boundaries", "W. Persistence Status", "X. Request Identity", "Y. Logging",
    "Z. Input Limits", "AA. CORS", "AB. Security Boundary", "AC. OpenAPI", "AD. Testing", "AE. Dependency Policy",
    "AF. Known Limitations", "AG. Deferred Work", "AH. Phase 18 Boundary", "AI. Acceptance Gate", "AJ. Validation Evidence",
]


def test_master_reference_pdf_still_byte_for_byte_unchanged():
    assert MASTER_REFERENCE_PDF.is_file()
    assert MASTER_REFERENCE_HASH_FILE.is_file()
    recorded_hash = MASTER_REFERENCE_HASH_FILE.read_text(encoding="utf-8").strip().split()[0]
    actual_hash = hashlib.sha256(MASTER_REFERENCE_PDF.read_bytes()).hexdigest()
    assert actual_hash == recorded_hash


def test_phase_00_through_16_docs_still_present_and_intact():
    docs = [
        DOCS_DIR / "PHASE_00_SCOPE_AND_ACCEPTANCE.md", DOCS_DIR / "PHASE_01_DOMAIN_TAXONOMY.md",
        DOCS_DIR / "PHASE_01_REGULATORY_DECISION_TREE.md", DOCS_DIR / "PHASE_02_AUTHORITY_MATRIX.md",
        DOCS_DIR / "PHASE_02_CORPUS_ADMISSION_POLICY.md", DOCS_DIR / "PHASE_02_SOURCE_CONFLICT_POLICY.md",
        DOCS_DIR / "PHASE_03_DOCUMENT_INGESTION.md", DOCS_DIR / "PHASE_03_LEGAL_STRUCTURE_EXTRACTION.md",
        DOCS_DIR / "PHASE_04_LEGAL_AWARE_CHUNKING.md", DOCS_DIR / "PHASE_05_BM25_BASELINE.md",
        DOCS_DIR / "PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md", DOCS_DIR / "PHASE_07_HYBRID_FUSION_AND_RERANKING.md",
        DOCS_DIR / "PHASE_08_EVIDENCE_OBJECT_AND_CITATION_ARCHITECTURE.md", DOCS_DIR / "PHASE_09_CITATION_VALIDATION.md",
        DOCS_DIR / "PHASE_10_GROUNDED_GENERATION.md", DOCS_DIR / "PHASE_11_FORMULATION_CLASSIFICATION.md",
        DOCS_DIR / "PHASE_12_JURISDICTION_FIREWALL.md", DOCS_DIR / "PHASE_13_CONFIDENCE_SAFETY_ABSTENTION.md",
        DOCS_DIR / "PHASE_14_MULTILINGUAL_DELIVERY.md", DOCS_DIR / "PHASE_15_HUMAN_IN_THE_LOOP.md",
        DOCS_DIR / "PHASE_16_EVALUATION_AND_RED_TEAM.md",
    ]
    for doc in docs:
        assert doc.is_file()
        assert doc.stat().st_size > 0


def test_phase_tracker_phases_0_through_16_remain_done_and_all_phases_present():
    text = (DOCS_DIR / "PHASE_TRACKER.md").read_text(encoding="utf-8")
    pattern = re.compile(r"^## Phase (\d+) .*?\n- \*\*Status:\*\* (.+)$", re.MULTILINE)
    statuses = {int(m.group(1)): m.group(2).strip() for m in pattern.finditer(text)}
    assert set(statuses.keys()) == set(range(24))
    for phase in range(17):
        assert statuses[phase] != "NOT STARTED", f"Phase {phase} tracker entry regressed to NOT STARTED"


def test_all_prior_phase_source_directories_untouched_by_phase_17():
    assert {p.name for p in (SRC_DIR / "classification").glob("*.py")} == {"__init__.py", "models.py", "rules.py", "classifier.py", "serialize.py"}
    assert {p.name for p in (SRC_DIR / "evidence").glob("*.py")} == {"__init__.py", "models.py", "identity.py", "builder.py", "validation.py", "serialize.py"}
    assert {p.name for p in (SRC_DIR / "citation").glob("*.py")} == {"__init__.py", "models.py", "validator.py", "metrics.py", "serialize.py"}
    assert {p.name for p in (SRC_DIR / "generation").glob("*.py")} == {"__init__.py", "models.py", "prompts.py", "providers.py", "grounding.py", "generator.py", "serialize.py"}
    assert {p.name for p in (SRC_DIR / "jurisdiction").glob("*.py")} == {"__init__.py", "models.py", "policy.py", "firewall.py", "filtering.py", "serialize.py"}
    assert {p.name for p in (SRC_DIR / "safety").glob("*.py")} == {"__init__.py", "models.py", "policy.py", "evaluator.py", "serialize.py"}
    assert {p.name for p in (SRC_DIR / "multilingual").glob("*.py")} == {"__init__.py", "models.py", "preservation.py", "providers.py", "delivery.py", "serialize.py"}
    assert {p.name for p in (SRC_DIR / "review").glob("*.py")} == {"__init__.py", "models.py", "policy.py", "workflow.py", "validation.py", "serialize.py"}
    assert {p.name for p in (SRC_DIR / "evaluation").glob("*.py")} == {"__init__.py", "models.py", "metrics.py", "benchmark.py", "redteam.py", "runner.py", "serialize.py"}


def test_config_directory_still_contains_the_phase_0_through_16_files():
    actual = {p.name for p in CONFIG_DIR.glob("*.yaml")}
    assert EXPECTED_CONFIG_FILES_THROUGH_PHASE_16.issubset(actual), f"config/ is missing Phase 0-16 files: {EXPECTED_CONFIG_FILES_THROUGH_PHASE_16 - actual}"


def test_backend_config_file_exists():
    assert (CONFIG_DIR / "backend_contract.yaml").is_file()


def test_api_and_application_source_directories_contain_expected_files():
    assert {p.name for p in (SRC_DIR / "api").glob("*.py")} == {"__init__.py", "app.py", "routes.py", "schemas.py", "errors.py", "dependencies.py"}
    assert {p.name for p in (SRC_DIR / "application").glob("*.py")} == {"__init__.py", "config.py", "models.py", "service.py"}


def test_no_frontend_deployment_or_observability_directories_exist():
    for forbidden in ("deployment", "observability", "k8s", "kubernetes", ".github/workflows"):
        assert not (REPO_ROOT / forbidden).exists()


def test_no_phase_18_or_later_directories_exist_yet():
    for forbidden in ("reviewers", "data", "corpus", "indexes", "index"):
        assert not (REPO_ROOT / forbidden).exists(), f"'{forbidden}/' would imply Phase 18+ functionality, which Phase 17 must not create"


def test_no_future_phase_module_names_present_anywhere():
    candidate_files = [f for f in REPO_ROOT.rglob("*.py") if not is_repo_scan_excluded(f)]
    lowered_names = [f.name.lower() for f in candidate_files]
    for hint in FUTURE_IMPLEMENTATION_MODULE_HINTS:
        matches = [n for n in lowered_names if hint in n]
        assert matches == [], f"found future-phase implementation module(s) matching {hint!r}: {matches}"


def test_no_forbidden_imports_anywhere_in_api_or_application_source():
    forbidden_import_roots = (
        "chromadb", "qdrant", "weaviate", "pinecone", "tensorflow", "openai", "google", "langchain", "llama_index",
        "torch", "sentence_transformers", "faiss", "grpc", "geopy", "geoip2", "flask", "django", "sqlalchemy",
        "psycopg2", "celery", "redis", "boto3", "kubernetes",
    )
    import_line_re = re.compile(r"^\s*(?:import|from)\s+([\w\.]+)", re.MULTILINE)
    for src_dir in (SRC_DIR / "api", SRC_DIR / "application"):
        for py_file in src_dir.glob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            for module in import_line_re.findall(text):
                top_level = module.split(".")[0].lower()
                assert top_level not in forbidden_import_roots, f"{py_file.relative_to(REPO_ROOT)} imports forbidden module {module!r}"


def test_api_source_never_imports_decision_making_functions_from_domain_modules():
    # docs Section E/G: FastAPI must never decide jurisdiction, classification,
    # evidence validity, citation validity, safety, or grounding - only
    # application.service may call the real decision-making entry points.
    forbidden_symbols = (
        "classify(", "resolve_jurisdiction(", "generate_grounded_response(", "evaluate_safety(",
        "validate_citations(", "build_evidence_pack(", "apply_action(",
    )
    for py_file in (SRC_DIR / "api").glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for symbol in forbidden_symbols:
            assert symbol not in text, f"{py_file.relative_to(REPO_ROOT)} references forbidden decision-making symbol {symbol!r}"


def test_api_source_contains_no_domain_conditional_business_rules():
    # docs "DOMAIN / API SEPARATION" - a literal string scan for the exact
    # anti-pattern examples named in the instructions.
    forbidden_snippets = ('jurisdiction ==', 'confidence <', 'evidence_id.startswith', 'safety_status ==', 'classification_state ==')
    for py_file in (SRC_DIR / "api").glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for snippet in forbidden_snippets:
            assert snippet not in text, f"{py_file.relative_to(REPO_ROOT)} contains a domain conditional {snippet!r} - business rules belong in the domain modules"


def test_application_source_only_imports_real_phase_8_through_15_entry_points():
    import_line_re = re.compile(r"^\s*(?:import|from)\s+([\w\.]+)", re.MULTILINE)
    allowed_top_levels = {
        "classification", "jurisdiction", "evidence", "generation", "safety", "multilingual", "review",
        "dataclasses", "typing", "hashlib", "os", "functools",
    }
    for py_file in (SRC_DIR / "application").glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for module in import_line_re.findall(text):
            top_level = module.split(".")[0]
            if top_level == "__future__":
                continue
            assert top_level in allowed_top_levels or (SRC_DIR / (top_level + ".py")).exists() is False, (
                f"{py_file.relative_to(REPO_ROOT)} imports unexpected module {module!r}"
            )


def test_no_hardcoded_secret_assignment_anywhere_in_new_source():
    for src_dir in (SRC_DIR / "api", SRC_DIR / "application"):
        for py_file in src_dir.glob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            match = SECRET_ASSIGNMENT_PATTERN.search(text)
            assert match is None, f"{py_file.relative_to(REPO_ROOT)} appears to hard-code a secret-shaped value: {match.group(0)!r}"


def test_no_wildcard_cors_configured_anywhere():
    for py_file in (SRC_DIR / "api").glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        assert 'allow_origins=["*"]' not in text
        assert "allow_origins=['*']" not in text


def test_no_new_dependency_declared_beyond_phase_6_plus_phase_17_baseline():
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
    for pkg in FORBIDDEN_DEPENDENCY_PACKAGES:
        assert pkg.lower() not in declared_packages, f"forbidden dependency actually declared: {pkg}"
    expected = {"pytest", "pyyaml", "pypdf", "sentence-transformers", "faiss-cpu", "numpy", "fastapi", "pydantic", "uvicorn", "httpx"}
    assert declared_packages == expected, f"unexpected dependency set: {declared_packages}"


def test_no_corpus_document_files_exist_anywhere():
    doc_like_extensions = (".pdf", ".html", ".htm", ".docx", ".doc")
    found = [p for p in REPO_ROOT.rglob("*") if p.is_file() and p.suffix.lower() in doc_like_extensions and not is_repo_scan_excluded(p) and "frontend" not in p.parts]
    assert found == [MASTER_REFERENCE_PDF], f"unexpected document-like file(s) found (possible ingestion/corpus leakage): {found}"


def test_no_eval_or_exec_anywhere_in_new_source():
    for src_dir in (SRC_DIR / "api", SRC_DIR / "application"):
        for py_file in src_dir.glob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            assert "eval(" not in text
            assert "exec(" not in text


def test_no_wall_clock_timestamp_usage_in_new_source():
    forbidden_terms = ("datetime.now", "time.time", "utcnow", "timezone.utc")
    for src_dir in (SRC_DIR / "api", SRC_DIR / "application"):
        for py_file in src_dir.glob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            for term in forbidden_terms:
                assert term not in text, f"{py_file.relative_to(REPO_ROOT)} contains forbidden timestamp usage {term!r}"


def test_full_pipeline_through_the_api_is_importable_and_functional():
    from fastapi.testclient import TestClient

    from api.app import create_app
    from api.dependencies import get_application_service
    from application.service import ApplicationService
    from generation.providers import FakeGenerationProvider

    app = create_app()
    service = ApplicationService(generation_provider=FakeGenerationProvider(response_text="uncited"))
    app.dependency_overrides[get_application_service] = lambda: service
    client = TestClient(app, raise_server_exceptions=False)

    health = client.get("/health")
    assert health.status_code == 200

    response = client.post("/api/v1/query", json={"query": "Tell me about Ministry of Ayush policy in India."})
    assert response.status_code == 200
    body = response.json()
    assert body["safety_status"] == "ABSTAIN"
    assert body["classification"]["classification_state"] == "KNOWN"


@pytest.fixture(scope="module")
def phase_17_doc_text() -> str:
    path = DOCS_DIR / "PHASE_17_BACKEND_PRODUCTIZATION.md"
    assert path.is_file()
    return path.read_text(encoding="utf-8")


def test_phase_17_doc_exists_and_nonempty(phase_17_doc_text: str):
    assert len(phase_17_doc_text) > 0


@pytest.mark.parametrize("section_heading", REQUIRED_DOC_SECTIONS)
def test_phase_17_doc_has_required_section(phase_17_doc_text: str, section_heading: str):
    assert section_heading in phase_17_doc_text


def test_phase_17_doc_states_phase_11_through_15_reuse(phase_17_doc_text: str):
    for phase_name in ("Phase 11", "Phase 12", "Phase 13", "Phase 14", "Phase 15"):
        assert phase_name in phase_17_doc_text


def test_phase_17_doc_states_phase_18_boundary(phase_17_doc_text: str):
    assert "Phase 18" in phase_17_doc_text


def test_phase_17_doc_discloses_deferred_live_provider(phase_17_doc_text: str):
    assert "[DEFERRED]" in phase_17_doc_text
    assert "GenerationProviderNotConfiguredError" in phase_17_doc_text


def test_phase_17_doc_discloses_not_validated_items(phase_17_doc_text: str):
    assert "NOT VALIDATED" in phase_17_doc_text
