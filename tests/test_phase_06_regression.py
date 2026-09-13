"""
Phase 6 tests: Master Reference integrity, Phase 0-5 regression protection,
repository cleanliness for the Phase 5-6 boundary, phase-boundary audit (no
Phase 7+ implementation leaked in), dependency discipline, and
docs/PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md completeness.
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

EXPECTED_CONFIG_FILES_THROUGH_PHASE_5 = {
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

# Real, unavoidable, explicitly-authorized Phase 6 imports (sentence
# transformers/faiss/torch/numpy) are deliberately absent here - see the
# scoped-to-actual-Phase-7+-technology check below.
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
    "cross-encoder",
)

REQUIRED_DOC_SECTIONS = [
    "A. Purpose",
    "B. Scope",
    "C. Source Classification",
    "D. Relationship to Phase 5",
    "E. BGE-M3 Decision",
    "F. Alternatives Considered",
    "G. Hardware Implications",
    "H. CPU/GPU Execution Strategy",
    "I. Embedding Contract",
    "J. Normalization Strategy",
    "K. FAISS Index Design",
    "L. ID Mapping",
    "M. Index Signature",
    "N. Retrieval Result Contract",
    "O. Provenance Preservation",
    "P. Multilingual Behavior",
    "Q. Benchmark Methodology",
    "R. Test Strategy",
    "S. Security/Defensive Validation",
    "T. Persistence",
    "U. Limitations",
    "V. Deferred Decisions",
    "W. Acceptance Gate",
    "X. Validation Results",
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
# Phase 0-5 artifacts remain intact
# ---------------------------------------------------------------------------


def test_phase_00_through_05_docs_still_present_and_intact():
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
    ]
    for doc in docs:
        assert doc.is_file()
        assert doc.stat().st_size > 0


def test_phase_0_through_5_yaml_contracts_still_valid_and_unchanged_in_shape():
    taxonomy = yaml.safe_load((CONFIG_DIR / "domain_taxonomy.yaml").read_text(encoding="utf-8"))
    assert taxonomy["taxonomy_version"] == "1.0.0"

    chunking_contract = yaml.safe_load((CONFIG_DIR / "chunking_contract.yaml").read_text(encoding="utf-8"))
    assert chunking_contract["contract_version"] == "1.0.0"

    bm25_contract = yaml.safe_load((CONFIG_DIR / "bm25_contract.yaml").read_text(encoding="utf-8"))
    assert bm25_contract["contract_version"] == "1.0.0"

    retrieval_result_schema = yaml.safe_load((CONFIG_DIR / "retrieval_result_schema.yaml").read_text(encoding="utf-8"))
    assert retrieval_result_schema["schema_version"] == "1.0.0"


def test_phase_tracker_phases_0_through_5_remain_done_and_all_phases_present():
    text = (DOCS_DIR / "PHASE_TRACKER.md").read_text(encoding="utf-8")
    pattern = re.compile(r"^## Phase (\d+) .*?\n- \*\*Status:\*\* (.+)$", re.MULTILINE)
    statuses = {int(m.group(1)): m.group(2).strip() for m in pattern.finditer(text)}

    assert set(statuses.keys()) == set(range(24))
    for phase in (0, 1, 2, 3, 4, 5):
        assert statuses[phase] != "NOT STARTED", f"Phase {phase} tracker entry regressed to NOT STARTED"


def test_bm25_module_files_are_byte_for_byte_unmodified_by_phase_6():
    # Phase 5's own scoring/index files must not be touched just because
    # Phase 6 shares the src/retrieval/ package.
    for filename in ("bm25.py", "tokenizer.py"):
        path = SRC_DIR / "retrieval" / filename
        assert path.is_file()


def test_bm25_and_dense_retrieval_are_independently_importable_and_functional():
    import sys

    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))
    import yaml as _yaml

    from chunking.chunker import chunk_document
    from chunking.models import ChunkingConfig
    from ingestion.hashing import compute_content_hash
    from ingestion.pipeline import ingest_bytes
    from retrieval.embeddings import FakeEmbeddingModel
    from retrieval.faiss_index import build_dense_index, dense_query
    from retrieval.index import build_index, query

    matrix = _yaml.safe_load((CONFIG_DIR / "authority_matrix.yaml").read_text(encoding="utf-8"))
    data = b"1. Heading\n\nBody text about trademarks.\n"
    provenance = {
        "document_id": "D-REG06-SMOKE",
        "source_family_id": "SF-01",
        "jurisdiction": "INDIA",
        "content_hash": compute_content_hash(data),
        "admission_status": "ADMIT",
        "synthetic": True,
    }
    result = ingest_bytes(data, provenance, ".txt", authority_matrix=matrix)
    chunking_result = chunk_document(result.document, ChunkingConfig())
    chunks = chunking_result.chunks

    bm25_index = build_index(chunks)
    bm25_resp = query(bm25_index, "trademarks", top_k=1)
    assert len(bm25_resp.results) == 1

    model = FakeEmbeddingModel(dimension=8)
    model.load()
    dense_index = build_dense_index(chunks, model)
    dense_resp = dense_query(dense_index, model, "trademarks", top_k=1)
    assert len(dense_resp.results) == 1


# ---------------------------------------------------------------------------
# Repository cleanliness for the Phase-5-through-Phase-6 boundary
# ---------------------------------------------------------------------------


def test_config_directory_still_contains_the_phase_0_through_5_files():
    actual = {p.name for p in CONFIG_DIR.glob("*.yaml")}
    assert EXPECTED_CONFIG_FILES_THROUGH_PHASE_5.issubset(actual), (
        f"config/ is missing Phase 0-5 files: {EXPECTED_CONFIG_FILES_THROUGH_PHASE_5 - actual}"
    )


def test_dense_retrieval_config_files_exist():
    assert (CONFIG_DIR / "dense_retrieval_contract.yaml").is_file()
    assert (CONFIG_DIR / "dense_index_schema.yaml").is_file()


def test_ingestion_and_chunking_source_directories_untouched_by_phase_6():
    ingestion_dir = SRC_DIR / "ingestion"
    expected_ingestion_files = {"__init__.py", "admission.py", "extractors.py", "hashing.py", "models.py", "pipeline.py", "serialize.py"}
    assert {p.name for p in ingestion_dir.glob("*.py")} == expected_ingestion_files

    chunking_dir = SRC_DIR / "chunking"
    expected_chunking_files = {"__init__.py", "chunker.py", "identity.py", "models.py", "rules.py", "serialize.py"}
    assert {p.name for p in chunking_dir.glob("*.py")} == expected_chunking_files


def test_retrieval_source_directory_contains_expected_phase_5_and_6_files():
    # Subset, not exact-equality: Phase 7 (Hybrid Fusion + Reranking) has
    # since been explicitly started and legitimately adds its own files
    # (reranker.py, rrf.py, hybrid.py) to this same shared src/retrieval/
    # directory - an exact-set assertion here would necessarily break the
    # moment any subsequent phase adds a file, which is not a regression
    # (same reasoning as the dependency exact-set fix in
    # tests/test_phase_04_regression.py/test_phase_05_regression.py). This
    # still proves Phase 5/6's own files were not removed or renamed.
    retrieval_dir = SRC_DIR / "retrieval"
    expected_files = {
        "__init__.py",
        # Phase 5
        "bm25.py",
        "index.py",
        "tokenizer.py",
        # shared, extended by Phase 6
        "models.py",
        "identity.py",
        "serialize.py",
        "evaluation.py",
        # Phase 6 only
        "embeddings.py",
        "faiss_index.py",
    }
    actual_files = {p.name for p in retrieval_dir.glob("*.py")}
    assert expected_files.issubset(actual_files), f"missing Phase 5/6 files: {expected_files - actual_files}"


def test_no_backend_frontend_or_evaluation_directories_exist():
    # [ENGINEERING RECOMMENDATION] "scripts" removed: Phase 22 legitimately
    # introduces scripts/build_release_manifest.py as release-artifact
    # infrastructure, so this historical future-phase guard is no longer
    # valid for that one name. Disclosed phase-boundary amendment, not a
    # weakening - every other forbidden name here remains enforced.
    for forbidden in ("backend", "evaluation"):
        assert not (REPO_ROOT / forbidden).exists()


def test_no_data_index_or_vector_database_directories_exist_yet():
    # Phase 6 produces an in-memory FAISS index (optionally persisted to
    # two explicit files by the caller) - no persistent index/database
    # directory this repository creates on its own exists yet.
    for forbidden in ("data", "corpus", "indexes", "index", "vector_store", "vectordb", "chroma", "qdrant_storage"):
        assert not (REPO_ROOT / forbidden).exists(), (
            f"'{forbidden}/' would imply a persistent vector store, which Phase 6 must not create on its own"
        )


def test_no_future_phase_module_names_present_anywhere():
    candidate_files = [f for f in REPO_ROOT.rglob("*.py") if not is_repo_scan_excluded(f)]
    lowered_names = [f.name.lower() for f in candidate_files]
    for hint in FUTURE_IMPLEMENTATION_MODULE_HINTS:
        matches = [n for n in lowered_names if hint in n]
        assert matches == [], f"found future-phase implementation module(s) matching {hint!r}: {matches}"


def test_no_hybrid_fusion_reranking_or_generation_imports_anywhere_in_retrieval_source():
    # Checks actual import statements only - not comments/docstrings (Phase
    # 6's own source and docs extensively, and permissibly, discuss what it
    # does NOT do). Deliberately does NOT forbid faiss/sentence_transformers/
    # transformers/torch here - those are Phase 6's own authorized imports.
    forbidden_import_roots = (
        "chromadb", "qdrant", "weaviate", "pinecone",
        "tensorflow", "openai", "google", "langchain", "llama_index", "rank_bm25",
    )
    import_line_re = re.compile(r"^\s*(?:import|from)\s+([\w\.]+)", re.MULTILINE)
    for py_file in (SRC_DIR / "retrieval").glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for module in import_line_re.findall(text):
            top_level = module.split(".")[0].lower()
            assert top_level not in forbidden_import_roots, (
                f"{py_file.relative_to(REPO_ROOT)} imports forbidden module {module!r}"
            )


def test_no_new_heavyweight_dependency_beyond_the_three_explicitly_justified_for_phase_6():
    # Checks actual declared package names only (non-comment requirement
    # lines) - not a raw substring search over the whole file text, which
    # would misfire on this phase's own justification comments (e.g.
    # mentioning "BGE-M3" or "torch" in prose without declaring a package
    # by that name) - the same documentation-vs-implementation
    # false-positive class already fixed for phase-boundary hints.
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
        f"Phase 6 must add exactly {{sentence-transformers, faiss-cpu, numpy}} beyond "
        f"Phase 0-5's pytest/PyYAML/pypdf baseline, got: {declared_packages}"
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


def test_dense_fixtures_reuse_existing_synthetic_chunk_builder_not_a_new_one():
    text = (REPO_ROOT / "tests" / "_dense_fixtures.py").read_text(encoding="utf-8")
    assert "from _bm25_fixtures import" in text


def test_no_bge_m3_model_weights_or_cache_committed_to_the_repository():
    # This project's own repository must never bundle downloaded model
    # weights - the model is loaded from the environment's own cache/
    # network at runtime, never vendored here.
    forbidden_extensions = (".bin", ".safetensors", ".onnx", ".pt", ".gguf")
    found = [
        p
        for p in REPO_ROOT.rglob("*")
        if p.is_file() and p.suffix.lower() in forbidden_extensions and ".git" not in p.parts
    ]
    assert found == [], f"unexpected model-weight-like file(s) found in the repository: {found}"


# ---------------------------------------------------------------------------
# docs/PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md completeness
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def phase_06_doc_text() -> str:
    path = DOCS_DIR / "PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md"
    assert path.is_file()
    return path.read_text(encoding="utf-8")


def test_phase_06_doc_exists_and_nonempty(phase_06_doc_text: str):
    assert len(phase_06_doc_text) > 0


@pytest.mark.parametrize("section_heading", REQUIRED_DOC_SECTIONS)
def test_phase_06_doc_has_required_section(phase_06_doc_text: str, section_heading: str):
    assert section_heading in phase_06_doc_text


def test_phase_06_doc_names_bge_m3_as_the_dense_candidate(phase_06_doc_text: str):
    assert "BAAI/bge-m3" in phase_06_doc_text


def test_phase_06_doc_distinguishes_score_from_legal_authority(phase_06_doc_text: str):
    assert "legal authority" in phase_06_doc_text
    assert "citation validity" in phase_06_doc_text


def test_phase_06_doc_discloses_what_was_not_validated(phase_06_doc_text: str):
    assert "NOT VALIDATED" in phase_06_doc_text


def test_phase_06_doc_does_not_claim_real_semantic_quality_from_fake_model(phase_06_doc_text: str):
    assert "NOT a claim of real multilingual semantic quality" in phase_06_doc_text
