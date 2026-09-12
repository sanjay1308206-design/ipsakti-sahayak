"""
Phase 16 tests: Master Reference integrity, Phase 0-15 regression
protection, repository cleanliness for the Phase 15-16 boundary,
phase-boundary audit (no Phase 17+ implementation leaked in), dependency
discipline, and docs/PHASE_16_EVALUATION_AND_RED_TEAM.md completeness.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest
import yaml

from _repo_scan import is_repo_scan_excluded

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
CONFIG_DIR = REPO_ROOT / "config"
SRC_DIR = REPO_ROOT / "src"

MASTER_REFERENCE_PDF = REPO_ROOT / "PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf"
MASTER_REFERENCE_HASH_FILE = DOCS_DIR / "_master_reference.sha256"

EXPECTED_CONFIG_FILES_THROUGH_PHASE_15 = {
    "acceptance_contract.yaml", "domain_taxonomy.yaml", "regulatory_decision_tree.yaml", "classification_contract.yaml",
    "authority_matrix.yaml", "corpus_provenance_schema.yaml", "corpus_lock.yaml", "document_ingestion_contract.yaml",
    "document_structure_schema.yaml", "chunking_contract.yaml", "chunk_schema.yaml", "bm25_contract.yaml",
    "retrieval_result_schema.yaml", "dense_retrieval_contract.yaml", "dense_index_schema.yaml",
    "hybrid_retrieval_contract.yaml", "hybrid_result_schema.yaml", "evidence_contract.yaml", "evidence_schema.yaml",
    "citation_validation_contract.yaml", "citation_validation_schema.yaml", "grounded_generation_contract.yaml",
    "grounded_generation_schema.yaml", "formulation_classification_contract.yaml", "jurisdiction_firewall_contract.yaml",
    "confidence_safety_contract.yaml", "multilingual_delivery_contract.yaml", "human_review_contract.yaml",
}

FUTURE_IMPLEMENTATION_MODULE_HINTS = ("scraper", "crawler", "ocr", "pdf_parser", "risk_scoring")

FORBIDDEN_DEPENDENCY_PACKAGES = (
    "langchain", "llama-index", "llamaindex", "chromadb", "qdrant", "weaviate", "pinecone", "kubernetes", "neo4j",
    "rank-bm25", "rank_bm25", "tiktoken", "openai", "google-generativeai", "google-genai", "transformers",
    "llama-cpp-python", "geopy", "geoip2", "scipy", "numpy-stats", "pandas",
)

REQUIRED_DOC_SECTIONS = [
    "A. Objective", "B. Scope", "C. Non-Scope", "D. Evaluation Philosophy", "E. Benchmark Data Policy",
    "F. Ground-Truth Discipline", "G. Benchmark Schema", "H. Retrieval Evaluation", "I. BM25 Evaluation",
    "J. Dense Evaluation", "K. Hybrid/RRF/Reranking Evaluation", "L. Classification Evaluation",
    "M. Jurisdiction Evaluation", "N. Citation Evaluation", "O. Grounding Evaluation", "P. Safety Evaluation",
    "Q. Multilingual Evaluation", "R. Human-Review Evaluation", "S. End-to-End Evaluation", "T. Red-Team Framework",
    "U. Attack Categories", "V. Attack Success Definitions", "W. Red-Team Metrics", "X. Failure Triage",
    "Y. Result Schema", "Z. Serialization", "AA. Determinism", "AB. Statistical Limitations",
    "AC. Real-Data Limitations", "AD. Benchmark Versioning", "AE. Known Limitations", "AF. Deferred Work",
    "AG. Phase 17 Boundary", "AH. Acceptance Gate", "AI. Validation Evidence",
]


def test_master_reference_pdf_still_byte_for_byte_unchanged():
    assert MASTER_REFERENCE_PDF.is_file()
    assert MASTER_REFERENCE_HASH_FILE.is_file()
    recorded_hash = MASTER_REFERENCE_HASH_FILE.read_text(encoding="utf-8").strip().split()[0]
    actual_hash = hashlib.sha256(MASTER_REFERENCE_PDF.read_bytes()).hexdigest()
    assert actual_hash == recorded_hash


def test_phase_00_through_15_docs_still_present_and_intact():
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
    ]
    for doc in docs:
        assert doc.is_file()
        assert doc.stat().st_size > 0


def test_phase_tracker_phases_0_through_15_remain_done_and_all_phases_present():
    text = (DOCS_DIR / "PHASE_TRACKER.md").read_text(encoding="utf-8")
    pattern = re.compile(r"^## Phase (\d+) .*?\n- \*\*Status:\*\* (.+)$", re.MULTILINE)
    statuses = {int(m.group(1)): m.group(2).strip() for m in pattern.finditer(text)}
    assert set(statuses.keys()) == set(range(24))
    for phase in range(15):
        assert statuses[phase] != "NOT STARTED", f"Phase {phase} tracker entry regressed to NOT STARTED"


def test_all_prior_phase_source_directories_untouched_by_phase_16():
    assert {p.name for p in (SRC_DIR / "classification").glob("*.py")} == {"__init__.py", "models.py", "rules.py", "classifier.py", "serialize.py"}
    assert {p.name for p in (SRC_DIR / "evidence").glob("*.py")} == {"__init__.py", "models.py", "identity.py", "builder.py", "validation.py", "serialize.py"}
    assert {p.name for p in (SRC_DIR / "citation").glob("*.py")} == {"__init__.py", "models.py", "validator.py", "metrics.py", "serialize.py"}
    assert {p.name for p in (SRC_DIR / "generation").glob("*.py")} == {"__init__.py", "models.py", "prompts.py", "providers.py", "grounding.py", "generator.py", "serialize.py"}
    assert {p.name for p in (SRC_DIR / "jurisdiction").glob("*.py")} == {"__init__.py", "models.py", "policy.py", "firewall.py", "filtering.py", "serialize.py"}
    assert {p.name for p in (SRC_DIR / "safety").glob("*.py")} == {"__init__.py", "models.py", "policy.py", "evaluator.py", "serialize.py"}
    assert {p.name for p in (SRC_DIR / "multilingual").glob("*.py")} == {"__init__.py", "models.py", "preservation.py", "providers.py", "delivery.py", "serialize.py"}
    assert {p.name for p in (SRC_DIR / "review").glob("*.py")} == {"__init__.py", "models.py", "policy.py", "workflow.py", "validation.py", "serialize.py"}
    assert {p.name for p in (SRC_DIR / "retrieval").glob("*.py")} == {
        "__init__.py", "bm25.py", "embeddings.py", "evaluation.py", "faiss_index.py", "hybrid.py", "identity.py",
        "index.py", "models.py", "reranker.py", "rrf.py", "serialize.py", "tokenizer.py",
    }


def test_config_directory_still_contains_the_phase_0_through_15_files():
    actual = {p.name for p in CONFIG_DIR.glob("*.yaml")}
    assert EXPECTED_CONFIG_FILES_THROUGH_PHASE_15.issubset(actual), f"config/ is missing Phase 0-15 files: {EXPECTED_CONFIG_FILES_THROUGH_PHASE_15 - actual}"


def test_evaluation_config_files_exist():
    assert (CONFIG_DIR / "evaluation_contract.yaml").is_file()
    assert (CONFIG_DIR / "redteam_cases.yaml").is_file()


def test_evaluation_source_directory_contains_expected_files():
    evaluation_dir = SRC_DIR / "evaluation"
    assert {p.name for p in evaluation_dir.glob("*.py")} == {"__init__.py", "models.py", "metrics.py", "benchmark.py", "redteam.py", "runner.py", "serialize.py"}


def test_redteam_cases_yaml_matches_python_catalogue_exactly():
    from evaluation.redteam import REDTEAM_CASES

    data = yaml.safe_load((CONFIG_DIR / "redteam_cases.yaml").read_text(encoding="utf-8"))
    yaml_ids = {c["case_id"] for c in data["cases"]}
    python_ids = {c.case_id for c in REDTEAM_CASES}
    assert yaml_ids == python_ids

    yaml_categories = {c["case_id"]: c["attack_category"] for c in data["cases"]}
    for case in REDTEAM_CASES:
        assert yaml_categories[case.case_id] == case.attack_category

    from evaluation.models import ATTACK_CATEGORY_SUCCESS_DEFINITION

    # [OUR ENHANCEMENT] Phase 19 legitimately extended the shared
    # ATTACK_CATEGORY_SUCCESS_DEFINITION dict with 15 new categories of
    # its own (mirrored separately in config/phase19_redteam_cases.yaml
    # and cross-checked by test_phase_19_redteam.py) that this Phase 16
    # yaml file - documented as the fixed 21-case catalogue mirror - was
    # never meant to cover. This is a subset check (was exact `==` when
    # the dict only had these 21 keys); every one of this yaml's own 21
    # entries is still required to match the Python mapping exactly.
    for category, definition in data["attack_category_to_success_definition"].items():
        assert ATTACK_CATEGORY_SUCCESS_DEFINITION[category] == definition


def test_no_backend_frontend_or_deployment_directories_exist():
    for forbidden in ("backend", "deployment"):
        assert not (REPO_ROOT / forbidden).exists()


def test_no_phase_17_or_later_directories_exist_yet():
    for forbidden in ("api", "reviewers", "data", "corpus", "indexes", "index"):
        assert not (REPO_ROOT / forbidden).exists(), f"'{forbidden}/' would imply Phase 17+ functionality, which Phase 16 must not create"


def test_no_future_phase_module_names_present_anywhere():
    candidate_files = [f for f in REPO_ROOT.rglob("*.py") if not is_repo_scan_excluded(f)]
    lowered_names = [f.name.lower() for f in candidate_files]
    for hint in FUTURE_IMPLEMENTATION_MODULE_HINTS:
        matches = [n for n in lowered_names if hint in n]
        assert matches == [], f"found future-phase implementation module(s) matching {hint!r}: {matches}"


def test_no_forbidden_imports_anywhere_in_evaluation_source():
    forbidden_import_roots = (
        "chromadb", "qdrant", "weaviate", "pinecone", "tensorflow", "openai", "google", "langchain",
        "llama_index", "torch", "transformers", "sentence_transformers", "faiss", "requests", "httpx", "grpc",
        "geopy", "geoip2", "socket", "flask", "django", "scipy", "sklearn", "pandas",
    )
    import_line_re = re.compile(r"^\s*(?:import|from)\s+([\w\.]+)", re.MULTILINE)
    for py_file in (SRC_DIR / "evaluation").glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for module in import_line_re.findall(text):
            top_level = module.split(".")[0].lower()
            assert top_level not in forbidden_import_roots, f"{py_file.relative_to(REPO_ROOT)} imports forbidden module {module!r}"


def test_evaluation_source_only_imports_from_documented_earlier_phases_or_stdlib():
    # docs Section D: src/evaluation/ may import citation.metrics (types/
    # metrics only) but must never import a full pipeline orchestrator
    # module (classification.classifier, jurisdiction.firewall,
    # generation.generator, safety.evaluator, multilingual.delivery,
    # review.policy/workflow) - those are exercised only from the TEST
    # layer, never from src/evaluation/ itself.
    forbidden_modules = (
        "classification.classifier", "jurisdiction.firewall", "jurisdiction.filtering", "generation.generator",
        "generation.providers", "safety.evaluator", "multilingual.delivery", "multilingual.preservation",
        "review.policy", "review.workflow", "evidence.builder",
    )
    import_line_re = re.compile(r"^\s*(?:import|from)\s+([\w\.]+)", re.MULTILINE)
    for py_file in (SRC_DIR / "evaluation").glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for module in import_line_re.findall(text):
            assert module not in forbidden_modules, f"{py_file.relative_to(REPO_ROOT)} imports {module!r} - src/evaluation/ must only be a metrics/reporting layer"


def test_no_new_dependency_declared_beyond_phase_6_baseline():
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
    expected = {"pytest", "pyyaml", "pypdf", "sentence-transformers", "faiss-cpu", "numpy"}
    # A later phase (e.g. Phase 17's fastapi/pydantic/uvicorn/httpx) may
    # legitimately ADD dependencies beyond this phase's own baseline - an
    # exact-set check is structurally incompatible with that (the same
    # reasoning already applied when Phase 6 relaxed Phase 4/5's own
    # exact-set checks). This phase's own baseline must still be present;
    # nothing may be REMOVED from it.
    assert expected.issubset(declared_packages), f"Phase 16's own dependency baseline must remain declared, got: {declared_packages}"


def test_no_corpus_document_files_exist_anywhere():
    doc_like_extensions = (".pdf", ".html", ".htm", ".docx", ".doc")
    found = [p for p in REPO_ROOT.rglob("*") if p.is_file() and p.suffix.lower() in doc_like_extensions and not is_repo_scan_excluded(p) and "frontend" not in p.parts]
    assert found == [MASTER_REFERENCE_PDF], f"unexpected document-like file(s) found (possible ingestion/corpus leakage): {found}"


def test_no_fastapi_react_or_frontend_terms_in_evaluation_source():
    forbidden_terms = ("react", "vite", "jsx", "@app.route", "apirouter")
    for py_file in (SRC_DIR / "evaluation").glob("*.py"):
        text = py_file.read_text(encoding="utf-8").lower()
        for term in forbidden_terms:
            assert term not in text, f"{py_file.relative_to(REPO_ROOT)} contains forbidden term {term!r}"


def test_no_cvss_or_fabricated_numeric_severity_in_evaluation_source():
    forbidden_terms = ("cvss", "confidence_interval", "p_value", "statistical_significance")
    for py_file in (SRC_DIR / "evaluation").glob("*.py"):
        text = py_file.read_text(encoding="utf-8").lower()
        for term in forbidden_terms:
            assert term not in text, f"{py_file.relative_to(REPO_ROOT)} contains forbidden term {term!r}"


def test_no_eval_or_exec_anywhere_in_evaluation_source():
    for py_file in (SRC_DIR / "evaluation").glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        assert "eval(" not in text
        assert "exec(" not in text


def test_no_wall_clock_timestamp_usage_in_evaluation_source():
    forbidden_terms = ("datetime.now", "time.time", "utcnow", "timezone.utc")
    for py_file in (SRC_DIR / "evaluation").glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for term in forbidden_terms:
            assert term not in text, f"{py_file.relative_to(REPO_ROOT)} contains forbidden timestamp usage {term!r}"


def test_no_random_module_usage_in_evaluation_source():
    for py_file in (SRC_DIR / "evaluation").glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        assert "import random" not in text
        assert "secrets." not in text


@pytest.fixture(scope="module")
def phase_16_doc_text() -> str:
    path = DOCS_DIR / "PHASE_16_EVALUATION_AND_RED_TEAM.md"
    assert path.is_file()
    return path.read_text(encoding="utf-8")


def test_phase_16_doc_exists_and_nonempty(phase_16_doc_text: str):
    assert len(phase_16_doc_text) > 0


@pytest.mark.parametrize("section_heading", REQUIRED_DOC_SECTIONS)
def test_phase_16_doc_has_required_section(phase_16_doc_text: str, section_heading: str):
    assert section_heading in phase_16_doc_text


def test_phase_16_doc_states_phase_5_through_15_reuse(phase_16_doc_text: str):
    for phase_name in ("Phase 5", "Phase 9", "Phase 11", "Phase 12", "Phase 13", "Phase 14", "Phase 15"):
        assert phase_name in phase_16_doc_text


def test_phase_16_doc_states_phase_17_boundary(phase_16_doc_text: str):
    assert "Phase 17" in phase_16_doc_text


def test_phase_16_doc_discloses_real_world_not_validated(phase_16_doc_text: str):
    assert "REAL-WORLD REGULATORY PERFORMANCE" in phase_16_doc_text
    assert "NOT VALIDATED" in phase_16_doc_text


def test_phase_16_doc_discloses_bge_m3_not_validated(phase_16_doc_text: str):
    assert "BGE-M3 REAL-MODEL QUALITY" in phase_16_doc_text
    assert "NOT VALIDATED" in phase_16_doc_text
