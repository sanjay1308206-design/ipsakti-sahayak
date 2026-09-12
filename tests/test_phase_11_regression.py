"""
Phase 11 tests: Master Reference integrity, Phase 0-10 regression
protection, repository cleanliness for the Phase 10-11 boundary,
phase-boundary audit (no Phase 12+ implementation leaked in), dependency
discipline, cross-check against Phase 1's own reference implementation
and taxonomy/decision-tree/contract YAML for drift, and
docs/PHASE_11_FORMULATION_CLASSIFICATION.md completeness.
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

EXPECTED_CONFIG_FILES_THROUGH_PHASE_10 = {
    "acceptance_contract.yaml",
    "domain_taxonomy.yaml",
    "regulatory_decision_tree.yaml",
    "classification_contract.yaml",
    "authority_matrix.yaml",
    "corpus_provenance_schema.yaml",
    "corpus_lock.yaml",
    "document_ingestion_contract.yaml",
    "document_structure_schema.yaml",
    "chunking_contract.yaml",
    "chunk_schema.yaml",
    "bm25_contract.yaml",
    "retrieval_result_schema.yaml",
    "dense_retrieval_contract.yaml",
    "dense_index_schema.yaml",
    "hybrid_retrieval_contract.yaml",
    "hybrid_result_schema.yaml",
    "evidence_contract.yaml",
    "evidence_schema.yaml",
    "citation_validation_contract.yaml",
    "citation_validation_schema.yaml",
    "grounded_generation_contract.yaml",
    "grounded_generation_schema.yaml",
}

# Phases beyond the one now in progress (Phase 11). "formulation_classification_engine"
# is deliberately absent - Phase 11 IS the formulation classification
# engine, now explicitly authorized and in progress, and its modules are
# named models.py/rules.py/classifier.py/serialize.py under
# src/classification/ (never "formulation_classification_engine.py"), so
# no collision exists or is expected.
FUTURE_IMPLEMENTATION_MODULE_HINTS = (
    "jurisdiction_firewall",
    "confidence_engine",
    "scraper",
    "crawler",
    "ocr",
    "pdf_parser",
    "abstention_engine",
    "human_escalation",
    "translation_adapter",
)

FORBIDDEN_DEPENDENCY_PACKAGES = (
    "langchain",
    "llama-index",
    "llamaindex",
    "chromadb",
    "qdrant",
    "weaviate",
    "pinecone",
    "kubernetes",
    "neo4j",
    "rank-bm25",
    "rank_bm25",
    "tiktoken",
    "openai",
    "google-generativeai",
    "google-genai",
    "transformers",
    "llama-cpp-python",
)

REQUIRED_DOC_SECTIONS = [
    "A. Phase Objective",
    "B. Scope",
    "C. Non-Scope",
    "D. Existing Phase 1 Contracts Reused",
    "E. Classification Dimensions",
    "F. Classification States",
    "G. Input Contract",
    "H. Output Contract",
    "I. Rule Engine",
    "J. Deterministic Behavior",
    "K. Explainability / Reason Codes",
    "L. Ambiguity Handling",
    "M. Unknown vs. Needs Evidence",
    "N. Evidence Boundary",
    "O. IP Classification Boundary",
    "P. Ayurveda Formulation Boundary",
    "Q. Multilingual Behavior",
    "R. Security",
    "S. Serialization",
    "T. Determinism",
    "U. Synthetic Evaluation",
    "V. Evaluation Interpretation",
    "W. Known Limitations",
    "X. Deferred Items",
    "Y. Phase 12 Boundary",
    "Z. Acceptance Gate",
    "AA. Validation Evidence",
]


# ---------------------------------------------------------------------------
# Master Reference integrity
# ---------------------------------------------------------------------------


def test_master_reference_pdf_still_byte_for_byte_unchanged():
    assert MASTER_REFERENCE_PDF.is_file()
    assert MASTER_REFERENCE_HASH_FILE.is_file()
    recorded_hash = MASTER_REFERENCE_HASH_FILE.read_text(encoding="utf-8").strip().split()[0]
    actual_hash = hashlib.sha256(MASTER_REFERENCE_PDF.read_bytes()).hexdigest()
    assert actual_hash == recorded_hash


# ---------------------------------------------------------------------------
# Phase 0-10 artifacts remain intact
# ---------------------------------------------------------------------------


def test_phase_00_through_10_docs_still_present_and_intact():
    docs = [
        DOCS_DIR / "PHASE_00_SCOPE_AND_ACCEPTANCE.md",
        DOCS_DIR / "PHASE_01_DOMAIN_TAXONOMY.md",
        DOCS_DIR / "PHASE_01_REGULATORY_DECISION_TREE.md",
        DOCS_DIR / "PHASE_02_AUTHORITY_MATRIX.md",
        DOCS_DIR / "PHASE_02_CORPUS_ADMISSION_POLICY.md",
        DOCS_DIR / "PHASE_02_SOURCE_CONFLICT_POLICY.md",
        DOCS_DIR / "PHASE_03_DOCUMENT_INGESTION.md",
        DOCS_DIR / "PHASE_03_LEGAL_STRUCTURE_EXTRACTION.md",
        DOCS_DIR / "PHASE_04_LEGAL_AWARE_CHUNKING.md",
        DOCS_DIR / "PHASE_05_BM25_BASELINE.md",
        DOCS_DIR / "PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md",
        DOCS_DIR / "PHASE_07_HYBRID_FUSION_AND_RERANKING.md",
        DOCS_DIR / "PHASE_08_EVIDENCE_OBJECT_AND_CITATION_ARCHITECTURE.md",
        DOCS_DIR / "PHASE_09_CITATION_VALIDATION.md",
        DOCS_DIR / "PHASE_10_GROUNDED_GENERATION.md",
    ]
    for doc in docs:
        assert doc.is_file()
        assert doc.stat().st_size > 0


def test_phase_tracker_phases_0_through_10_remain_done_and_all_phases_present():
    text = (DOCS_DIR / "PHASE_TRACKER.md").read_text(encoding="utf-8")
    pattern = re.compile(r"^## Phase (\d+) .*?\n- \*\*Status:\*\* (.+)$", re.MULTILINE)
    statuses = {int(m.group(1)): m.group(2).strip() for m in pattern.finditer(text)}

    assert set(statuses.keys()) == set(range(24))
    for phase in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10):
        assert statuses[phase] != "NOT STARTED", f"Phase {phase} tracker entry regressed to NOT STARTED"


def test_evidence_citation_and_generation_source_files_are_untouched_by_phase_11():
    evidence_dir = SRC_DIR / "evidence"
    assert {p.name for p in evidence_dir.glob("*.py")} == {
        "__init__.py", "models.py", "identity.py", "builder.py", "validation.py", "serialize.py",
    }
    citation_dir = SRC_DIR / "citation"
    assert {p.name for p in citation_dir.glob("*.py")} == {
        "__init__.py", "models.py", "validator.py", "metrics.py", "serialize.py",
    }
    generation_dir = SRC_DIR / "generation"
    assert {p.name for p in generation_dir.glob("*.py")} == {
        "__init__.py", "models.py", "prompts.py", "providers.py", "grounding.py", "generator.py", "serialize.py",
    }


# ---------------------------------------------------------------------------
# Phase 1 vocabulary/rule/contract drift checks - Phase 11 mirrors, never
# redefines, these files.
# ---------------------------------------------------------------------------


def _load_taxonomy() -> dict:
    return yaml.safe_load((CONFIG_DIR / "domain_taxonomy.yaml").read_text(encoding="utf-8"))


def test_regulatory_track_enum_matches_domain_taxonomy_yaml():
    from classification.models import REGULATORY_TRACK_VALUES

    taxonomy = _load_taxonomy()
    names = {c["name"] for c in taxonomy["dimensions"]["regulatory_track"]["categories"]}
    assert REGULATORY_TRACK_VALUES == names


def test_ip_protection_category_enum_matches_domain_taxonomy_yaml():
    from classification.models import IP_PROTECTION_CATEGORY_VALUES

    taxonomy = _load_taxonomy()
    names = {c["name"] for c in taxonomy["dimensions"]["ip_protection_category"]["categories"]}
    assert IP_PROTECTION_CATEGORY_VALUES == names


def test_abs_tk_relation_enum_matches_domain_taxonomy_yaml():
    from classification.models import ABS_TK_RELATION_VALUES

    taxonomy = _load_taxonomy()
    names = {c["name"] for c in taxonomy["dimensions"]["abs_tk_relation"]["categories"]}
    assert ABS_TK_RELATION_VALUES == names


def test_regulatory_question_type_enum_matches_domain_taxonomy_yaml():
    from classification.models import REGULATORY_QUESTION_TYPE_VALUES

    taxonomy = _load_taxonomy()
    names = {c["name"] for c in taxonomy["regulatory_question_categories"]["categories"]}
    assert REGULATORY_QUESTION_TYPE_VALUES == names


def test_user_intent_enum_matches_domain_taxonomy_yaml():
    from classification.models import USER_INTENT_VALUES

    taxonomy = _load_taxonomy()
    names = {c["name"] for c in taxonomy["user_intent_categories"]["categories"]}
    assert USER_INTENT_VALUES == names


def test_evidence_requiring_intents_matches_domain_taxonomy_yaml():
    from classification.models import EVIDENCE_REQUIRING_INTENTS

    taxonomy = _load_taxonomy()
    names = {c["name"] for c in taxonomy["user_intent_categories"]["categories"] if c.get("evidence_requiring")}
    assert EVIDENCE_REQUIRING_INTENTS == names


def test_jurisdiction_enum_matches_domain_taxonomy_yaml():
    from classification.models import JURISDICTION_VALUES

    taxonomy = _load_taxonomy()
    names = {c["name"] for c in taxonomy["jurisdiction_inputs"]["categories"]}
    assert JURISDICTION_VALUES == names


def test_evidence_state_enum_matches_domain_taxonomy_yaml():
    from classification.models import EVIDENCE_STATE_VALUES

    taxonomy = _load_taxonomy()
    names = {c["name"] for c in taxonomy["evidence_states"]["categories"]}
    assert EVIDENCE_STATE_VALUES == names


def test_classification_states_enum_matches_domain_taxonomy_yaml():
    from classification.models import CLASSIFICATION_STATES

    taxonomy = _load_taxonomy()
    names = {c["name"] for c in taxonomy["classification_states"]["categories"]}
    assert CLASSIFICATION_STATES == names


def test_disclaimer_matches_classification_contract_yaml():
    from classification.models import FIXED_DISCLAIMER

    contract = yaml.safe_load((CONFIG_DIR / "classification_contract.yaml").read_text(encoding="utf-8"))
    disclaimer_field = next(f for f in contract["fields"] if f["name"] == "disclaimer")
    assert FIXED_DISCLAIMER == disclaimer_field["constant"].strip()


def test_taxonomy_version_matches_domain_taxonomy_yaml():
    from classification.models import TAXONOMY_VERSION

    taxonomy = _load_taxonomy()
    assert TAXONOMY_VERSION == taxonomy["taxonomy_version"]


def test_decision_tree_version_matches_regulatory_decision_tree_yaml():
    from classification.models import DECISION_TREE_VERSION

    tree = yaml.safe_load((CONFIG_DIR / "regulatory_decision_tree.yaml").read_text(encoding="utf-8"))
    assert DECISION_TREE_VERSION == tree["tree_version"]


def test_contract_version_matches_classification_contract_yaml():
    from classification.models import CLASSIFICATION_CONTRACT_VERSION

    contract = yaml.safe_load((CONFIG_DIR / "classification_contract.yaml").read_text(encoding="utf-8"))
    assert CLASSIFICATION_CONTRACT_VERSION == contract["contract_version"]


def test_full_pipeline_through_classification_is_importable_and_functional():
    import sys

    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))

    from classification.classifier import classify
    from classification.models import ClassificationInput
    from evidence.builder import build_evidence_pack  # noqa: F401 - proves Phase 8 still importable alongside Phase 11
    from citation.validator import validate_citations  # noqa: F401 - proves Phase 9 still importable alongside Phase 11
    from generation.generator import generate_grounded_response  # noqa: F401 - proves Phase 10 still importable alongside Phase 11

    result = classify(ClassificationInput(input_id="SMOKE", raw_query="Tell me about Ministry of Ayush policy in India."))
    assert result.classification_state == "KNOWN"


# ---------------------------------------------------------------------------
# Repository cleanliness for the Phase-10-through-Phase-11 boundary
# ---------------------------------------------------------------------------


def test_config_directory_still_contains_the_phase_0_through_10_files():
    actual = {p.name for p in CONFIG_DIR.glob("*.yaml")}
    assert EXPECTED_CONFIG_FILES_THROUGH_PHASE_10.issubset(actual), (
        f"config/ is missing Phase 0-10 files: {EXPECTED_CONFIG_FILES_THROUGH_PHASE_10 - actual}"
    )


def test_classification_config_file_exists():
    assert (CONFIG_DIR / "formulation_classification_contract.yaml").is_file()


def test_classification_source_directory_contains_expected_files():
    classification_dir = SRC_DIR / "classification"
    assert {p.name for p in classification_dir.glob("*.py")} == {
        "__init__.py", "models.py", "rules.py", "classifier.py", "serialize.py",
    }


def test_no_backend_frontend_or_deployment_directories_exist():
    for forbidden in ("backend", "evaluation", "scripts", "deployment"):
        assert not (REPO_ROOT / forbidden).exists()


def test_no_phase_12_or_later_directories_exist_yet():
    for forbidden in ("jurisdiction", "confidence", "escalation", "translation", "data", "corpus", "indexes", "index"):
        assert not (REPO_ROOT / forbidden).exists(), (
            f"'{forbidden}/' would imply Phase 12+ functionality, which Phase 11 must not create"
        )


def test_no_future_phase_module_names_present_anywhere():
    candidate_files = [f for f in REPO_ROOT.rglob("*.py") if not is_repo_scan_excluded(f)]
    lowered_names = [f.name.lower() for f in candidate_files]
    for hint in FUTURE_IMPLEMENTATION_MODULE_HINTS:
        matches = [n for n in lowered_names if hint in n]
        assert matches == [], f"found future-phase implementation module(s) matching {hint!r}: {matches}"


def test_no_forbidden_imports_anywhere_in_classification_source():
    forbidden_import_roots = (
        "chromadb", "qdrant", "weaviate", "pinecone",
        "tensorflow", "openai", "google", "langchain", "llama_index",
        "torch", "transformers", "sentence_transformers", "faiss",
        "requests", "httpx", "grpc",
    )
    import_line_re = re.compile(r"^\s*(?:import|from)\s+([\w\.]+)", re.MULTILINE)
    for py_file in (SRC_DIR / "classification").glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for module in import_line_re.findall(text):
            top_level = module.split(".")[0].lower()
            assert top_level not in forbidden_import_roots, (
                f"{py_file.relative_to(REPO_ROOT)} imports forbidden module {module!r}"
            )


def test_classification_source_never_imports_retrieval_evidence_citation_or_generation():
    # Phase 11 must not call into retrieval/evidence/citation/generation
    # code itself - it only accepts an opaque evidence_state passthrough
    # value (docs Section N).
    import_line_re = re.compile(r"^\s*(?:import|from)\s+([\w\.]+)", re.MULTILINE)
    for py_file in (SRC_DIR / "classification").glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for module in import_line_re.findall(text):
            top_level = module.split(".")[0]
            if top_level in ("retrieval", "chunking", "ingestion", "evidence", "citation", "generation"):
                raise AssertionError(
                    f"{py_file.relative_to(REPO_ROOT)} imports {module!r} - Phase 11 must not call into any "
                    f"earlier retrieval/evidence/citation/generation module"
                )


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
    assert expected.issubset(declared_packages), (
        # A later phase (e.g. Phase 17's fastapi/pydantic/uvicorn/httpx) may
        # legitimately ADD dependencies beyond this phase's own baseline -
        # an exact-set check is structurally incompatible with that (the
        # same reasoning already applied when Phase 6 relaxed Phase 4/5's
        # own exact-set checks). This phase's own baseline must still be
        # present; nothing may be REMOVED from it.
        f"Phase 11 must add zero new dependencies beyond Phase 6's baseline, got: {declared_packages}"
    )


def test_no_corpus_document_files_exist_anywhere():
    doc_like_extensions = (".pdf", ".html", ".htm", ".docx", ".doc")
    found = [
        p
        for p in REPO_ROOT.rglob("*")
        if p.is_file() and p.suffix.lower() in doc_like_extensions and not is_repo_scan_excluded(p) and "frontend" not in p.parts
    ]
    assert found == [MASTER_REFERENCE_PDF], (
        f"unexpected document-like file(s) found (possible ingestion/corpus leakage): {found}"
    )


def test_no_legal_conclusion_or_jurisdiction_decision_terms_in_classification_source():
    forbidden_terms = (
        "legal_conclusion", "is_legally_valid", "legally_certain", "jurisdiction_decision",
        "corpus_selected", "index_selected", "confidence_score",
    )
    for py_file in (SRC_DIR / "classification").glob("*.py"):
        text = py_file.read_text(encoding="utf-8").lower()
        for term in forbidden_terms:
            assert term not in text, f"{py_file.relative_to(REPO_ROOT)} contains forbidden term {term!r}"


def test_no_eval_or_exec_anywhere_in_classification_source():
    for py_file in (SRC_DIR / "classification").glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        assert "eval(" not in text
        assert "exec(" not in text


# ---------------------------------------------------------------------------
# docs/PHASE_11_FORMULATION_CLASSIFICATION.md completeness
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def phase_11_doc_text() -> str:
    path = DOCS_DIR / "PHASE_11_FORMULATION_CLASSIFICATION.md"
    assert path.is_file()
    return path.read_text(encoding="utf-8")


def test_phase_11_doc_exists_and_nonempty(phase_11_doc_text: str):
    assert len(phase_11_doc_text) > 0


@pytest.mark.parametrize("section_heading", REQUIRED_DOC_SECTIONS)
def test_phase_11_doc_has_required_section(phase_11_doc_text: str, section_heading: str):
    assert section_heading in phase_11_doc_text


def test_phase_11_doc_states_phase_1_reuse(phase_11_doc_text: str):
    assert "Phase 1" in phase_11_doc_text
    assert "reused" in phase_11_doc_text.lower() or "reuse" in phase_11_doc_text.lower()


def test_phase_11_doc_states_phase_12_boundary(phase_11_doc_text: str):
    assert "Phase 12" in phase_11_doc_text
    assert "jurisdiction firewall" in phase_11_doc_text.lower()


def test_phase_11_doc_discloses_deferred_llm_assisted_classification(phase_11_doc_text: str):
    assert "[DEFERRED]" in phase_11_doc_text
    assert "llm" in phase_11_doc_text.lower()
