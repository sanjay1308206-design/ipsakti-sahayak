"""
Phase 4 tests: Master Reference integrity, Phase 0-3 regression protection,
repository cleanliness for the Phase 3-4 boundary, phase-boundary audit (no
Phase 5+ implementation leaked in), dependency discipline, and
docs/PHASE_04_LEGAL_AWARE_CHUNKING.md completeness.

Phase 3 did not add its own test_phase_03_regression.py, so there is no
precedent test asserting Phase 4's own tracker entry from inside this file
(that would create an ordering paradox - docs/PHASE_TRACKER.md is only
updated AFTER this whole suite passes, per docs/DEVELOPMENT_RULES.md Rule 4).
This file follows test_phase_01/02_regression.py's pattern instead: verify
Phases 0-3 remain intact, and audit Phase 4's own scope boundary.
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

EXPECTED_CONFIG_FILES_THROUGH_PHASE_3 = {
    "acceptance_contract.yaml",
    "domain_taxonomy.yaml",
    "regulatory_decision_tree.yaml",
    "classification_contract.yaml",
    "authority_matrix.yaml",
    "corpus_provenance_schema.yaml",
    "corpus_lock.yaml",
    "document_ingestion_contract.yaml",
    "document_structure_schema.yaml",
}

# Phases beyond the one now in progress (Phase 7). "ingest", "chunker",
# "bm25", "faiss", "embeddings", and "reranker" are deliberately absent -
# they are Phase 3/4/5/6/7's own legitimate module names, not future-phase
# leakage (see tests/test_phase_02_regression.py for the identical
# reasoning applied each time a new phase starts).
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
    "A. Purpose",
    "B. Input Contract",
    "C. Output Contract",
    "D. Chunk Identity",
    "E. Structural Boundary Rules",
    "F. Section/Context Preservation",
    "G. Maximum Chunk-Size Policy",
    "H. Oversized-Block Handling",
    "I. Tables and Lists",
    "J. Page Boundaries",
    "K. Heading Hierarchy",
    "L. Provenance Preservation",
    "M. Determinism Requirements",
    "N. Synthetic Fixture Policy",
    "O. Failure Behavior",
    "P. Security Considerations",
    "Q. Explicit Non-Goals",
    "R. Source/Evidence Audit",
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
# Phase 0-3 artifacts remain intact
# ---------------------------------------------------------------------------


def test_phase_00_through_03_docs_still_present_and_intact():
    docs = [
        DOCS_DIR / "PHASE_00_SCOPE_AND_ACCEPTANCE.md",
        DOCS_DIR / "PHASE_01_DOMAIN_TAXONOMY.md",
        DOCS_DIR / "PHASE_01_REGULATORY_DECISION_TREE.md",
        DOCS_DIR / "PHASE_02_AUTHORITY_MATRIX.md",
        DOCS_DIR / "PHASE_02_CORPUS_ADMISSION_POLICY.md",
        DOCS_DIR / "PHASE_02_SOURCE_CONFLICT_POLICY.md",
        DOCS_DIR / "PHASE_03_DOCUMENT_INGESTION.md",
        DOCS_DIR / "PHASE_03_LEGAL_STRUCTURE_EXTRACTION.md",
    ]
    for doc in docs:
        assert doc.is_file()
        assert doc.stat().st_size > 0


def test_phase_0_through_3_yaml_contracts_still_valid_and_unchanged_in_shape():
    taxonomy = yaml.safe_load((CONFIG_DIR / "domain_taxonomy.yaml").read_text(encoding="utf-8"))
    assert taxonomy["taxonomy_version"] == "1.0.0"

    ingestion_contract = yaml.safe_load((CONFIG_DIR / "document_ingestion_contract.yaml").read_text(encoding="utf-8"))
    assert ingestion_contract["contract_version"] == "1.0.0"

    structure_schema = yaml.safe_load((CONFIG_DIR / "document_structure_schema.yaml").read_text(encoding="utf-8"))
    assert structure_schema["schema_version"] == "1.0.0"

    provenance_schema = yaml.safe_load((CONFIG_DIR / "corpus_provenance_schema.yaml").read_text(encoding="utf-8"))
    assert provenance_schema["schema_version"] == "1.1.0"


def test_phase_tracker_phases_0_through_3_remain_done_and_all_phases_present():
    text = (DOCS_DIR / "PHASE_TRACKER.md").read_text(encoding="utf-8")
    pattern = re.compile(r"^## Phase (\d+) .*?\n- \*\*Status:\*\* (.+)$", re.MULTILINE)
    statuses = {int(m.group(1)): m.group(2).strip() for m in pattern.finditer(text)}

    assert set(statuses.keys()) == set(range(24))
    for phase in (0, 1, 2, 3):
        assert statuses[phase] != "NOT STARTED", f"Phase {phase} tracker entry regressed to NOT STARTED"


def test_ingestion_module_still_importable_and_unmodified_in_behavior():
    # A behavioral smoke check, not a source-diff - proves Phase 4 did not
    # need to (and did not) touch Phase 3's own pipeline to work correctly.
    import sys

    sys.path.insert(0, str(SRC_DIR)) if str(SRC_DIR) not in sys.path else None
    from ingestion.hashing import compute_content_hash
    from ingestion.pipeline import ingest_bytes

    matrix = yaml.safe_load((CONFIG_DIR / "authority_matrix.yaml").read_text(encoding="utf-8"))
    data = b"content"
    provenance = {
        "document_id": "D-REG-SMOKE",
        "source_family_id": "SF-01",
        "jurisdiction": "INDIA",
        "content_hash": compute_content_hash(data),
        "admission_status": "ADMIT",
        "synthetic": True,
    }
    result = ingest_bytes(data, provenance, ".txt", authority_matrix=matrix)
    assert result.pipeline_state == "EXTRACTION_SUCCESS"


# ---------------------------------------------------------------------------
# Repository cleanliness for the Phase-3-through-Phase-4 boundary
# ---------------------------------------------------------------------------


def test_config_directory_still_contains_the_phase_0_through_3_files():
    actual = {p.name for p in CONFIG_DIR.glob("*.yaml")}
    assert EXPECTED_CONFIG_FILES_THROUGH_PHASE_3.issubset(actual), (
        f"config/ is missing Phase 0-3 files: {EXPECTED_CONFIG_FILES_THROUGH_PHASE_3 - actual}"
    )


def test_chunking_config_files_exist():
    assert (CONFIG_DIR / "chunking_contract.yaml").is_file()
    assert (CONFIG_DIR / "chunk_schema.yaml").is_file()


def test_ingestion_source_directory_untouched_by_phase_4():
    ingestion_dir = SRC_DIR / "ingestion"
    assert ingestion_dir.is_dir()
    expected_files = {"__init__.py", "admission.py", "extractors.py", "hashing.py", "models.py", "pipeline.py", "serialize.py"}
    actual_files = {p.name for p in ingestion_dir.glob("*.py")}
    assert actual_files == expected_files, "Phase 4 must not add/remove files inside src/ingestion/"


def test_chunking_source_directory_exists():
    assert (SRC_DIR / "chunking").is_dir()
    assert (SRC_DIR / "chunking" / "chunker.py").is_file()


def test_no_backend_frontend_or_evaluation_directories_exist():
    # [ENGINEERING RECOMMENDATION] "scripts" removed: Phase 22 legitimately
    # introduces scripts/build_release_manifest.py as release-artifact
    # infrastructure, so this historical future-phase guard is no longer
    # valid for that one name. Disclosed phase-boundary amendment, not a
    # weakening - every other forbidden name here remains enforced.
    for forbidden in ("backend", "evaluation"):
        assert not (REPO_ROOT / forbidden).exists()


def test_no_data_or_index_directories_exist_yet():
    # Phase 4 produces in-memory Chunk objects / serializable JSON only -
    # no persistent index, database, or corpus directory exists yet (Phase 5+).
    for forbidden in ("data", "corpus", "indexes", "index"):
        assert not (REPO_ROOT / forbidden).exists(), (
            f"'{forbidden}/' would imply retrieval indexing, which Phase 4 must not perform"
        )


def test_no_future_phase_module_names_present_anywhere():
    candidate_files = [f for f in REPO_ROOT.rglob("*.py") if not is_repo_scan_excluded(f)]
    lowered_names = [f.name.lower() for f in candidate_files]
    for hint in FUTURE_IMPLEMENTATION_MODULE_HINTS:
        matches = [n for n in lowered_names if hint in n]
        assert matches == [], f"found future-phase implementation module(s) matching {hint!r}: {matches}"


def test_no_retrieval_or_generation_imports_anywhere_in_chunking_source():
    # Checks actual import statements only - not comments/docstrings. Phase
    # 4's own source deliberately documents what it does NOT do (e.g. "Never
    # retrieves, embeds, indexes, or generates anything" in chunker.py), and
    # docs/PHASE_04_LEGAL_AWARE_CHUNKING.md Section Q explicitly names every
    # forbidden later-phase technique - a naive substring scan over file text
    # would misfire on that same permitted, encouraged documentation (see
    # docs/DEVELOPMENT_RULES.md Rule 3: "Documentation describing future
    # architecture is fine. Actual code for future-phase capability is not.").
    forbidden_import_roots = (
        "faiss", "bm25", "rank_bm25", "sentence_transformers", "transformers",
        "chromadb", "qdrant", "weaviate", "pinecone", "fastapi", "torch",
        "tensorflow", "openai", "google", "langchain", "llama_index",
    )
    import_line_re = re.compile(r"^\s*(?:import|from)\s+([\w\.]+)", re.MULTILINE)
    for py_file in (SRC_DIR / "chunking").glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for module in import_line_re.findall(text):
            top_level = module.split(".")[0].lower()
            assert top_level not in forbidden_import_roots, (
                f"{py_file.relative_to(REPO_ROOT)} imports forbidden module {module!r}"
            )


def test_no_new_heavyweight_dependency_declared_in_phase_4():
    # Checks actual declared package names only (non-comment requirement
    # lines) - not a raw substring search over the whole file text, which
    # would misfire on a later phase's own justification comment naming a
    # package it deliberately did NOT install (e.g. "rank_bm25 was
    # deliberately not installed" in Phase 5's block) - the same
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
    # Subset, not exact-equality: this proves Phase 0-3's own baseline
    # dependencies are still present (Phase 4 itself added none), without
    # forbidding a LATER phase (Phase 6) from legitimately adding its own -
    # an exact-set assertion here would necessarily break the moment any
    # subsequent phase adds a real dependency, which is not a regression.
    assert {"pytest", "pyyaml", "pypdf"}.issubset(declared_packages), (
        f"Phase 0-3's baseline dependencies (pytest/PyYAML/pypdf) must remain declared, got: {declared_packages}"
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


def test_chunk_fixtures_reuse_existing_synthetic_provenance_builder_not_a_new_one():
    # Guards against silently introducing a second, divergent synthetic-data
    # path instead of reusing tests/_provenance_fixtures.py.
    text = (REPO_ROOT / "tests" / "_chunk_fixtures.py").read_text(encoding="utf-8")
    assert "from _provenance_fixtures import make_provenance" in text


# ---------------------------------------------------------------------------
# docs/PHASE_04_LEGAL_AWARE_CHUNKING.md completeness
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def phase_04_doc_text() -> str:
    path = DOCS_DIR / "PHASE_04_LEGAL_AWARE_CHUNKING.md"
    assert path.is_file()
    return path.read_text(encoding="utf-8")


def test_phase_04_doc_exists_and_nonempty(phase_04_doc_text: str):
    assert len(phase_04_doc_text) > 0


@pytest.mark.parametrize("section_heading", REQUIRED_DOC_SECTIONS)
def test_phase_04_doc_has_required_section(phase_04_doc_text: str, section_heading: str):
    assert section_heading in phase_04_doc_text


def test_phase_04_doc_does_not_claim_legal_interpretation(phase_04_doc_text: str):
    assert "legal interpretation" in phase_04_doc_text  # discussed only as a non-goal
    assert "never asserted to be legally authoritative" in phase_04_doc_text or "not a legal fact" in phase_04_doc_text


def test_phase_04_doc_labels_chunk_id_as_non_citation(phase_04_doc_text: str):
    assert "MUST NOT be presented as" in phase_04_doc_text
    assert "Phase 8" in phase_04_doc_text
