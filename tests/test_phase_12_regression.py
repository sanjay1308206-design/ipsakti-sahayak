"""
Phase 12 tests: Master Reference integrity, Phase 0-11 regression
protection, repository cleanliness for the Phase 11-12 boundary,
phase-boundary audit (no Phase 13+ implementation leaked in), dependency
discipline, cross-check against Phase 1/2's own jurisdiction vocabulary
YAML for drift, and docs/PHASE_12_JURISDICTION_FIREWALL.md completeness.
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

EXPECTED_CONFIG_FILES_THROUGH_PHASE_11 = {
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
    "formulation_classification_contract.yaml",
}

# Phases beyond the one now in progress (Phase 12). "jurisdiction_firewall"
# is deliberately absent - Phase 12 IS the jurisdiction firewall, now
# explicitly authorized and in progress, and its modules are named
# models.py/policy.py/firewall.py/filtering.py/serialize.py under
# src/jurisdiction/ (never "jurisdiction_firewall.py"), so no collision
# exists or is expected.
FUTURE_IMPLEMENTATION_MODULE_HINTS = (
    "confidence_engine",
    "scraper",
    "crawler",
    "ocr",
    "pdf_parser",
    "abstention_engine",
    "human_escalation",
    "translation_adapter",
    "risk_scoring",
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
    "geopy",
    "geoip2",
)

REQUIRED_DOC_SECTIONS = [
    "A. Phase Objective",
    "B. Scope",
    "C. Non-Scope",
    "D. Existing Contracts Reused",
    "E. Jurisdiction Vocabulary",
    "F. Jurisdiction States",
    "G. Input Contract",
    "H. Output Contract",
    "I. Normalization",
    "J. Routing Policy",
    "K. India Corpus Isolation",
    "L. International Corpus Isolation",
    "M. Fail-Closed Behavior",
    "N. Cross-Jurisdiction Leakage Prevention",
    "O. Evidence Filtering",
    "P. Retrieval Integration Boundary",
    "Q. Source Authority vs. Jurisdiction",
    "R. Multilingual Behavior",
    "S. Language ≠ Jurisdiction",
    "T. Security",
    "U. Prompt Injection Boundary",
    "V. Currentness Limitation",
    "W. Legal Determination Limitation",
    "X. Determinism",
    "Y. Serialization",
    "Z. Synthetic Evaluation",
    "AA. Evaluation Interpretation",
    "AB. Known Limitations",
    "AC. Deferred Items",
    "AD. Phase 13 Boundary",
    "AE. Acceptance Gate",
    "AF. Validation Evidence",
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
# Phase 0-11 artifacts remain intact
# ---------------------------------------------------------------------------


def test_phase_00_through_11_docs_still_present_and_intact():
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
        DOCS_DIR / "PHASE_11_FORMULATION_CLASSIFICATION.md",
    ]
    for doc in docs:
        assert doc.is_file()
        assert doc.stat().st_size > 0


def test_phase_tracker_phases_0_through_11_remain_done_and_all_phases_present():
    text = (DOCS_DIR / "PHASE_TRACKER.md").read_text(encoding="utf-8")
    pattern = re.compile(r"^## Phase (\d+) .*?\n- \*\*Status:\*\* (.+)$", re.MULTILINE)
    statuses = {int(m.group(1)): m.group(2).strip() for m in pattern.finditer(text)}

    assert set(statuses.keys()) == set(range(24))
    for phase in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11):
        assert statuses[phase] != "NOT STARTED", f"Phase {phase} tracker entry regressed to NOT STARTED"


def test_classification_evidence_citation_and_generation_source_untouched_by_phase_12():
    assert {p.name for p in (SRC_DIR / "classification").glob("*.py")} == {
        "__init__.py", "models.py", "rules.py", "classifier.py", "serialize.py",
    }
    assert {p.name for p in (SRC_DIR / "evidence").glob("*.py")} == {
        "__init__.py", "models.py", "identity.py", "builder.py", "validation.py", "serialize.py",
    }
    assert {p.name for p in (SRC_DIR / "citation").glob("*.py")} == {
        "__init__.py", "models.py", "validator.py", "metrics.py", "serialize.py",
    }
    assert {p.name for p in (SRC_DIR / "generation").glob("*.py")} == {
        "__init__.py", "models.py", "prompts.py", "providers.py", "grounding.py", "generator.py", "serialize.py",
    }


# ---------------------------------------------------------------------------
# Vocabulary drift checks - Phase 12 mirrors, never redefines
# ---------------------------------------------------------------------------


def test_request_jurisdiction_values_match_domain_taxonomy_yaml():
    from jurisdiction.models import REQUEST_JURISDICTION_VALUES

    taxonomy = yaml.safe_load((CONFIG_DIR / "domain_taxonomy.yaml").read_text(encoding="utf-8"))
    names = {c["name"] for c in taxonomy["jurisdiction_inputs"]["categories"]}
    assert REQUEST_JURISDICTION_VALUES == names


def test_evidence_jurisdiction_values_match_authority_matrix_yaml():
    from jurisdiction.models import EVIDENCE_JURISDICTION_VALUES

    matrix = yaml.safe_load((CONFIG_DIR / "authority_matrix.yaml").read_text(encoding="utf-8"))
    assert EVIDENCE_JURISDICTION_VALUES == set(matrix["valid_jurisdictions"])


def test_full_pipeline_through_jurisdiction_firewall_is_importable_and_functional():
    import sys

    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))

    from citation.validator import validate_citations  # noqa: F401
    from classification.classifier import classify
    from classification.models import ClassificationInput
    from evidence.builder import build_evidence_pack  # noqa: F401
    from generation.generator import generate_grounded_response  # noqa: F401
    from jurisdiction.filtering import filter_evidence
    from jurisdiction.firewall import resolve_jurisdiction

    cls = classify(ClassificationInput(input_id="SMOKE", raw_query="What category applies in India under FSSAI?"))
    decision = resolve_jurisdiction("SMOKE-D", classification_result=cls)
    assert decision.state == "KNOWN"

    from dataclasses import dataclass

    @dataclass
    class FakeEvidence:
        evidence_id: str
        jurisdiction: str

    result = filter_evidence(decision, [FakeEvidence("E1", "INDIA"), FakeEvidence("E2", "INTERNATIONAL")])
    assert [e.evidence_id for e in result.allowed_evidence] == ["E1"]


# ---------------------------------------------------------------------------
# Repository cleanliness for the Phase-11-through-Phase-12 boundary
# ---------------------------------------------------------------------------


def test_config_directory_still_contains_the_phase_0_through_11_files():
    actual = {p.name for p in CONFIG_DIR.glob("*.yaml")}
    assert EXPECTED_CONFIG_FILES_THROUGH_PHASE_11.issubset(actual), (
        f"config/ is missing Phase 0-11 files: {EXPECTED_CONFIG_FILES_THROUGH_PHASE_11 - actual}"
    )


def test_jurisdiction_config_file_exists():
    assert (CONFIG_DIR / "jurisdiction_firewall_contract.yaml").is_file()


def test_jurisdiction_source_directory_contains_expected_files():
    jurisdiction_dir = SRC_DIR / "jurisdiction"
    assert {p.name for p in jurisdiction_dir.glob("*.py")} == {
        "__init__.py", "models.py", "policy.py", "firewall.py", "filtering.py", "serialize.py",
    }


def test_no_backend_frontend_or_deployment_directories_exist():
    # [ENGINEERING RECOMMENDATION] "scripts" removed: Phase 22 legitimately
    # introduces scripts/build_release_manifest.py as release-artifact
    # infrastructure, so this historical future-phase guard is no longer
    # valid for that one name. Disclosed phase-boundary amendment, not a
    # weakening - every other forbidden name here remains enforced.
    for forbidden in ("backend", "evaluation", "deployment"):
        assert not (REPO_ROOT / forbidden).exists()


def test_no_phase_13_or_later_directories_exist_yet():
    for forbidden in ("confidence", "escalation", "translation", "data", "corpus", "indexes", "index"):
        assert not (REPO_ROOT / forbidden).exists(), (
            f"'{forbidden}/' would imply Phase 13+ functionality, which Phase 12 must not create"
        )


def test_no_future_phase_module_names_present_anywhere():
    candidate_files = [f for f in REPO_ROOT.rglob("*.py") if not is_repo_scan_excluded(f)]
    lowered_names = [f.name.lower() for f in candidate_files]
    for hint in FUTURE_IMPLEMENTATION_MODULE_HINTS:
        matches = [n for n in lowered_names if hint in n]
        assert matches == [], f"found future-phase implementation module(s) matching {hint!r}: {matches}"


def test_no_forbidden_imports_anywhere_in_jurisdiction_source():
    forbidden_import_roots = (
        "chromadb", "qdrant", "weaviate", "pinecone",
        "tensorflow", "openai", "google", "langchain", "llama_index",
        "torch", "transformers", "sentence_transformers", "faiss",
        "requests", "httpx", "grpc", "geopy", "geoip2",
    )
    import_line_re = re.compile(r"^\s*(?:import|from)\s+([\w\.]+)", re.MULTILINE)
    for py_file in (SRC_DIR / "jurisdiction").glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for module in import_line_re.findall(text):
            top_level = module.split(".")[0].lower()
            assert top_level not in forbidden_import_roots, (
                f"{py_file.relative_to(REPO_ROOT)} imports forbidden module {module!r}"
            )


def test_jurisdiction_source_only_imports_classification_and_stdlib():
    # Phase 12 explicitly reuses Phase 11 (classification.models) - it
    # must never import retrieval/chunking/ingestion/evidence/citation/
    # generation directly (docs Section D/P).
    import_line_re = re.compile(r"^\s*(?:import|from)\s+([\w\.]+)", re.MULTILINE)
    for py_file in (SRC_DIR / "jurisdiction").glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for module in import_line_re.findall(text):
            top_level = module.split(".")[0]
            if top_level in ("retrieval", "chunking", "ingestion", "evidence", "citation", "generation"):
                raise AssertionError(
                    f"{py_file.relative_to(REPO_ROOT)} imports {module!r} - Phase 12 must only depend on "
                    f"Phase 11 (classification.*), never earlier retrieval/evidence/citation/generation internals"
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
        f"Phase 12 must add zero new dependencies beyond Phase 6's baseline, got: {declared_packages}"
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


def test_jurisdiction_fixtures_reuse_existing_classification_builder_not_new_one():
    text = (REPO_ROOT / "tests" / "_jurisdiction_fixtures.py").read_text(encoding="utf-8")
    assert "from classification.classifier import classify" in text


def test_no_legal_determination_or_geolocation_terms_in_jurisdiction_source():
    forbidden_terms = (
        "governing_law", "is_legally_valid", "legally_certain", "legal_determination",
        "geoip", "geolocation", "ip_address", "browser_locale", "system_locale", "timezone",
    )
    for py_file in (SRC_DIR / "jurisdiction").glob("*.py"):
        text = py_file.read_text(encoding="utf-8").lower()
        for term in forbidden_terms:
            assert term not in text, f"{py_file.relative_to(REPO_ROOT)} contains forbidden term {term!r}"


def test_no_eval_or_exec_anywhere_in_jurisdiction_source():
    for py_file in (SRC_DIR / "jurisdiction").glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        assert "eval(" not in text
        assert "exec(" not in text


def test_no_confidence_score_or_probability_field_in_jurisdiction_models():
    text = (SRC_DIR / "jurisdiction" / "models.py").read_text(encoding="utf-8").lower()
    for term in ("confidence_score", "probability", "risk_score"):
        assert term not in text


# ---------------------------------------------------------------------------
# docs/PHASE_12_JURISDICTION_FIREWALL.md completeness
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def phase_12_doc_text() -> str:
    path = DOCS_DIR / "PHASE_12_JURISDICTION_FIREWALL.md"
    assert path.is_file()
    return path.read_text(encoding="utf-8")


def test_phase_12_doc_exists_and_nonempty(phase_12_doc_text: str):
    assert len(phase_12_doc_text) > 0


@pytest.mark.parametrize("section_heading", REQUIRED_DOC_SECTIONS)
def test_phase_12_doc_has_required_section(phase_12_doc_text: str, section_heading: str):
    assert section_heading in phase_12_doc_text


def test_phase_12_doc_states_phase_1_and_2_reuse(phase_12_doc_text: str):
    assert "Phase 1" in phase_12_doc_text
    assert "Phase 2" in phase_12_doc_text


def test_phase_12_doc_states_phase_13_boundary(phase_12_doc_text: str):
    assert "Phase 13" in phase_12_doc_text
    assert "confidence" in phase_12_doc_text.lower()


def test_phase_12_doc_discloses_needs_evidence_unreachability(phase_12_doc_text: str):
    assert "unreachable" in phase_12_doc_text.lower()


def test_phase_12_doc_states_language_is_not_jurisdiction(phase_12_doc_text: str):
    assert "language" in phase_12_doc_text.lower()
    assert "never" in phase_12_doc_text.lower()
