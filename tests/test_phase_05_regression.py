"""
Phase 5 tests: Master Reference integrity, Phase 0-4 regression protection,
repository cleanliness for the Phase 4-5 boundary, phase-boundary audit (no
Phase 6+ implementation leaked in), dependency discipline, and
docs/PHASE_05_BM25_BASELINE.md completeness.
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

EXPECTED_CONFIG_FILES_THROUGH_PHASE_4 = {
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
}

# Phases beyond the one now in progress (Phase 7). "ingest", "chunker",
# "bm25", "faiss", "embeddings", and "reranker" are deliberately absent -
# Phase 3/4/5/6/7's own legitimate module names, not future-phase leakage
# (see tests/test_phase_02_regression.py).
FUTURE_IMPLEMENTATION_MODULE_HINTS = (
    "jurisdiction_firewall",
    "citation_validator",
    "confidence_engine",
    "formulation_classification_engine",
    "scraper",
    "crawler",
    "ocr",
    "pdf_parser",
)

# "faiss"/"sentence-transformers" intentionally removed: Phase 6 has since
# been explicitly started and legitimately declares them.
FORBIDDEN_DEPENDENCY_PACKAGES = (
    "langchain",
    "llama-index",
    "llamaindex",
    "bge-m3",
    "chromadb",
    "qdrant",
    "weaviate",
    "pinecone",
    "kubernetes",
    "neo4j",
    "rank-bm25",
    "rank_bm25",
    "tiktoken",
    "transformers",
)

REQUIRED_DOC_SECTIONS = [
    "A. Objective",
    "B. Input Contract",
    "C. Tokenization Policy",
    "D. Text Normalization Policy",
    "E. Stopword Policy",
    "F. Unicode Handling",
    "G. BM25 Formula/Parameters",
    "H. Index Representation",
    "I. Query Processing",
    "J. Ranking/Tie-Breaking",
    "K. Top-k Behavior",
    "L. Empty/Unknown Queries",
    "M. Provenance Preservation",
    "N. Determinism",
    "O. Security/Resource Limits",
    "P. Evaluation Methodology",
    "Q. Limitations",
    "R. Deferred Improvements",
    "S. Source/Evidence Classification",
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
# Phase 0-4 artifacts remain intact
# ---------------------------------------------------------------------------


def test_phase_00_through_04_docs_still_present_and_intact():
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
    ]
    for doc in docs:
        assert doc.is_file()
        assert doc.stat().st_size > 0


def test_phase_0_through_4_yaml_contracts_still_valid_and_unchanged_in_shape():
    taxonomy = yaml.safe_load((CONFIG_DIR / "domain_taxonomy.yaml").read_text(encoding="utf-8"))
    assert taxonomy["taxonomy_version"] == "1.0.0"

    ingestion_contract = yaml.safe_load((CONFIG_DIR / "document_ingestion_contract.yaml").read_text(encoding="utf-8"))
    assert ingestion_contract["contract_version"] == "1.0.0"

    chunking_contract = yaml.safe_load((CONFIG_DIR / "chunking_contract.yaml").read_text(encoding="utf-8"))
    assert chunking_contract["contract_version"] == "1.0.0"

    chunk_schema = yaml.safe_load((CONFIG_DIR / "chunk_schema.yaml").read_text(encoding="utf-8"))
    assert chunk_schema["schema_version"] == "1.0.0"


def test_phase_tracker_phases_0_through_4_remain_done_and_all_phases_present():
    text = (DOCS_DIR / "PHASE_TRACKER.md").read_text(encoding="utf-8")
    pattern = re.compile(r"^## Phase (\d+) .*?\n- \*\*Status:\*\* (.+)$", re.MULTILINE)
    statuses = {int(m.group(1)): m.group(2).strip() for m in pattern.finditer(text)}

    assert set(statuses.keys()) == set(range(24))
    for phase in (0, 1, 2, 3, 4):
        assert statuses[phase] != "NOT STARTED", f"Phase {phase} tracker entry regressed to NOT STARTED"


def test_ingestion_and_chunking_modules_still_importable_and_behaviorally_unchanged():
    import sys

    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))
    from chunking.chunker import chunk_document
    from chunking.models import ChunkingConfig
    from ingestion.hashing import compute_content_hash
    from ingestion.pipeline import ingest_bytes

    matrix = yaml.safe_load((CONFIG_DIR / "authority_matrix.yaml").read_text(encoding="utf-8"))
    data = b"1. Heading\n\nBody text.\n"
    provenance = {
        "document_id": "D-REG05-SMOKE",
        "source_family_id": "SF-01",
        "jurisdiction": "INDIA",
        "content_hash": compute_content_hash(data),
        "admission_status": "ADMIT",
        "synthetic": True,
    }
    result = ingest_bytes(data, provenance, ".txt", authority_matrix=matrix)
    assert result.pipeline_state == "EXTRACTION_SUCCESS"
    chunking_result = chunk_document(result.document, ChunkingConfig())
    assert chunking_result.chunking_status == "CHUNKING_SUCCESS"
    assert len(chunking_result.chunks) >= 1


# ---------------------------------------------------------------------------
# Repository cleanliness for the Phase-4-through-Phase-5 boundary
# ---------------------------------------------------------------------------


def test_config_directory_still_contains_the_phase_0_through_4_files():
    actual = {p.name for p in CONFIG_DIR.glob("*.yaml")}
    assert EXPECTED_CONFIG_FILES_THROUGH_PHASE_4.issubset(actual), (
        f"config/ is missing Phase 0-4 files: {EXPECTED_CONFIG_FILES_THROUGH_PHASE_4 - actual}"
    )


def test_retrieval_config_files_exist():
    assert (CONFIG_DIR / "bm25_contract.yaml").is_file()
    assert (CONFIG_DIR / "retrieval_result_schema.yaml").is_file()


def test_ingestion_source_directory_untouched_by_phase_5():
    ingestion_dir = SRC_DIR / "ingestion"
    expected_files = {"__init__.py", "admission.py", "extractors.py", "hashing.py", "models.py", "pipeline.py", "serialize.py"}
    actual_files = {p.name for p in ingestion_dir.glob("*.py")}
    assert actual_files == expected_files, "Phase 5 must not add/remove files inside src/ingestion/"


def test_chunking_source_directory_untouched_by_phase_5():
    chunking_dir = SRC_DIR / "chunking"
    expected_files = {"__init__.py", "chunker.py", "identity.py", "models.py", "rules.py", "serialize.py"}
    actual_files = {p.name for p in chunking_dir.glob("*.py")}
    assert actual_files == expected_files, "Phase 5 must not add/remove files inside src/chunking/"


def test_retrieval_source_directory_exists():
    assert (SRC_DIR / "retrieval").is_dir()
    assert (SRC_DIR / "retrieval" / "bm25.py").is_file()
    assert (SRC_DIR / "retrieval" / "index.py").is_file()


def test_no_backend_frontend_or_evaluation_directories_exist():
    # [ENGINEERING RECOMMENDATION] "scripts" removed: Phase 22 legitimately
    # introduces scripts/build_release_manifest.py as release-artifact
    # infrastructure, so this historical future-phase guard is no longer
    # valid for that one name. Disclosed phase-boundary amendment, not a
    # weakening - every other forbidden name here remains enforced.
    for forbidden in ("backend", "evaluation"):
        assert not (REPO_ROOT / forbidden).exists()


def test_no_data_index_or_vector_store_directories_exist_yet():
    # Phase 5's Bm25Index is an in-memory, serializable-to-JSON-if-asked
    # object only - no persistent index/database/vector-store directory
    # exists yet (Phase 6+ dense retrieval, Phase 7 hybrid fusion).
    for forbidden in ("data", "corpus", "indexes", "index", "vector_store", "vectordb"):
        assert not (REPO_ROOT / forbidden).exists(), (
            f"'{forbidden}/' would imply persistent retrieval indexing, which Phase 5 must not perform"
        )


def test_no_future_phase_module_names_present_anywhere():
    candidate_files = [f for f in REPO_ROOT.rglob("*.py") if not is_repo_scan_excluded(f)]
    lowered_names = [f.name.lower() for f in candidate_files]
    for hint in FUTURE_IMPLEMENTATION_MODULE_HINTS:
        matches = [n for n in lowered_names if hint in n]
        assert matches == [], f"found future-phase implementation module(s) matching {hint!r}: {matches}"


def test_no_dense_retrieval_or_generation_imports_in_phase_5_own_files():
    # Scoped to Phase 5's OWN files only (bm25.py, index.py, tokenizer.py) -
    # not the whole src/retrieval/ directory. Phase 6 (Multilingual Dense
    # Retrieval) has since been explicitly started and shares that same
    # directory, legitimately adding src/retrieval/embeddings.py (imports
    # sentence_transformers) and src/retrieval/faiss_index.py (imports
    # faiss); src/retrieval/serialize.py was extended by Phase 6 to import
    # faiss too for index persistence. Scanning the whole directory would
    # misfire on that authorized Phase 6 code - the same
    # documentation-vs-implementation false-positive class already fixed
    # for phase-boundary hints (tests/test_phase_02_regression.py), applied
    # here to real import statements instead of filenames. Phase 6's own
    # regression file (test_phase_06_regression.py) carries the equivalent,
    # correctly-scoped check for Phase 7+ leakage into its own files.
    forbidden_import_roots = (
        "faiss", "sentence_transformers", "transformers", "chromadb", "qdrant",
        "weaviate", "pinecone", "fastapi", "torch", "tensorflow", "openai",
        "google", "langchain", "llama_index", "rank_bm25",
    )
    phase_5_own_files = ("bm25.py", "index.py", "tokenizer.py")
    import_line_re = re.compile(r"^\s*(?:import|from)\s+([\w\.]+)", re.MULTILINE)
    for filename in phase_5_own_files:
        py_file = SRC_DIR / "retrieval" / filename
        text = py_file.read_text(encoding="utf-8")
        for module in import_line_re.findall(text):
            top_level = module.split(".")[0].lower()
            assert top_level not in forbidden_import_roots, (
                f"{py_file.relative_to(REPO_ROOT)} imports forbidden module {module!r}"
            )


def test_no_new_heavyweight_dependency_declared_in_phase_5():
    # Checks actual declared package names only (non-comment requirement
    # lines) - not a raw substring search over the whole file text, which
    # would misfire on this very phase's own justification comment naming
    # "rank_bm25" as a package deliberately NOT installed - the same
    # documentation-vs-implementation false-positive class already fixed
    # for phase-boundary hints (tests/test_phase_02_regression.py).
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
    # Subset, not exact-equality - see the identical reasoning in
    # tests/test_phase_04_regression.py: an exact-set assertion here would
    # necessarily break the moment a later phase (Phase 6) legitimately
    # adds its own real dependency, which is not a regression.
    assert {"pytest", "pyyaml", "pypdf"}.issubset(declared_packages), (
        f"Phase 0-4's baseline dependencies (pytest/PyYAML/pypdf) must remain declared, got: {declared_packages}"
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


def test_bm25_fixtures_reuse_existing_synthetic_chunk_builder_not_a_new_one():
    text = (REPO_ROOT / "tests" / "_bm25_fixtures.py").read_text(encoding="utf-8")
    assert "from _chunk_fixtures import make_document" in text


# ---------------------------------------------------------------------------
# docs/PHASE_05_BM25_BASELINE.md completeness
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def phase_05_doc_text() -> str:
    path = DOCS_DIR / "PHASE_05_BM25_BASELINE.md"
    assert path.is_file()
    return path.read_text(encoding="utf-8")


def test_phase_05_doc_exists_and_nonempty(phase_05_doc_text: str):
    assert len(phase_05_doc_text) > 0


@pytest.mark.parametrize("section_heading", REQUIRED_DOC_SECTIONS)
def test_phase_05_doc_has_required_section(phase_05_doc_text: str, section_heading: str):
    assert section_heading in phase_05_doc_text


def test_phase_05_doc_does_not_claim_final_retrieval_architecture(phase_05_doc_text: str):
    assert "not a final retrieval system" in phase_05_doc_text or "not the final retrieval architecture" in phase_05_doc_text


def test_phase_05_doc_states_exact_bm25_parameters(phase_05_doc_text: str):
    assert "k1 = 1.5" in phase_05_doc_text
    assert "b = 0.75" in phase_05_doc_text


def test_phase_05_doc_distinguishes_score_from_legal_authority(phase_05_doc_text: str):
    assert "never" in phase_05_doc_text and "legal authority" in phase_05_doc_text
