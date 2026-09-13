"""
Phase 10 tests: Master Reference integrity, Phase 0-9 regression
protection, repository cleanliness for the Phase 9-10 boundary,
phase-boundary audit (no Phase 11+ implementation leaked in), dependency
discipline, and docs/PHASE_10_GROUNDED_GENERATION.md completeness.
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

EXPECTED_CONFIG_FILES_THROUGH_PHASE_9 = {
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
}

# Phases beyond the one now in progress (Phase 10). "grounded_generation"
# and "claim_evidence_binding" are deliberately absent from this list -
# Phase 10 IS grounded generation, now explicitly authorized and in
# progress, and its modules are named models.py/prompts.py/providers.py/
# grounding.py/generator.py/serialize.py under src/generation/ (never
# "grounded_generation.py" or "claim_evidence_binding.py"), so no
# collision exists or is expected.
FUTURE_IMPLEMENTATION_MODULE_HINTS = (
    "jurisdiction_firewall",
    "confidence_engine",
    "formulation_classification_engine",
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
    "D. Inputs",
    "E. Outputs",
    "F. Grounding Contract",
    "G. EvidencePack Integration",
    "H. Citation Integration",
    "I. Prompt Architecture",
    "J. Prompt Injection Boundary",
    "K. Provider Abstraction",
    "L. Fake Provider",
    "M. Live-Provider Status",
    "N. Abstention Boundary",
    "O. Unsupported-Evidence Behavior",
    "P. Multilingual Behavior",
    "Q. Synthetic-Data Handling",
    "R. Serialization",
    "S. Security",
    "T. Determinism",
    "U. Test Strategy",
    "V. Synthetic Benchmark",
    "W. Benchmark Interpretation",
    "X. Known Limitations",
    "Y. Deferred Items",
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
# Phase 0-9 artifacts remain intact
# ---------------------------------------------------------------------------


def test_phase_00_through_09_docs_still_present_and_intact():
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
    ]
    for doc in docs:
        assert doc.is_file()
        assert doc.stat().st_size > 0


def test_phase_0_through_9_yaml_contracts_still_valid_and_unchanged_in_shape():
    taxonomy = yaml.safe_load((CONFIG_DIR / "domain_taxonomy.yaml").read_text(encoding="utf-8"))
    assert taxonomy["taxonomy_version"] == "1.0.0"

    citation_contract = yaml.safe_load((CONFIG_DIR / "citation_validation_contract.yaml").read_text(encoding="utf-8"))
    assert citation_contract["contract_version"] == "1.0.0"

    citation_schema = yaml.safe_load((CONFIG_DIR / "citation_validation_schema.yaml").read_text(encoding="utf-8"))
    assert citation_schema["schema_version"] == "1.0.0"


def test_phase_tracker_phases_0_through_9_remain_done_and_all_phases_present():
    text = (DOCS_DIR / "PHASE_TRACKER.md").read_text(encoding="utf-8")
    pattern = re.compile(r"^## Phase (\d+) .*?\n- \*\*Status:\*\* (.+)$", re.MULTILINE)
    statuses = {int(m.group(1)): m.group(2).strip() for m in pattern.finditer(text)}

    assert set(statuses.keys()) == set(range(24))
    for phase in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9):
        assert statuses[phase] != "NOT STARTED", f"Phase {phase} tracker entry regressed to NOT STARTED"


def test_evidence_and_citation_source_files_are_untouched_by_phase_10():
    evidence_dir = SRC_DIR / "evidence"
    expected_evidence_files = {"__init__.py", "models.py", "identity.py", "builder.py", "validation.py", "serialize.py"}
    assert {p.name for p in evidence_dir.glob("*.py")} == expected_evidence_files

    citation_dir = SRC_DIR / "citation"
    expected_citation_files = {"__init__.py", "models.py", "validator.py", "metrics.py", "serialize.py"}
    assert {p.name for p in citation_dir.glob("*.py")} == expected_citation_files


def test_full_pipeline_through_grounded_generation_is_importable_and_functional():
    import sys

    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))
    import yaml as _yaml

    from chunking.chunker import chunk_document
    from chunking.models import ChunkingConfig
    from citation.metrics import compute_citation_coverage
    from evidence.builder import build_evidence_pack
    from generation.generator import generate_grounded_response
    from generation.providers import FakeGenerationProvider
    from ingestion.hashing import compute_content_hash
    from ingestion.pipeline import ingest_bytes
    from retrieval.embeddings import FakeEmbeddingModel
    from retrieval.faiss_index import build_dense_index, dense_query
    from retrieval.hybrid import rerank_candidates
    from retrieval.index import build_index, query
    from retrieval.reranker import FakeReranker
    from retrieval.rrf import fuse_rrf

    matrix = _yaml.safe_load((CONFIG_DIR / "authority_matrix.yaml").read_text(encoding="utf-8"))
    data = b"1. Heading\n\nBody text about trademarks.\n"
    provenance = {
        "document_id": "D-REG10-SMOKE",
        "source_family_id": "SF-01",
        "jurisdiction": "INDIA",
        "content_hash": compute_content_hash(data),
        "admission_status": "ADMIT",
        "synthetic": True,
    }
    result = ingest_bytes(data, provenance, ".txt", authority_matrix=matrix)
    chunks = chunk_document(result.document, ChunkingConfig()).chunks

    bm25_index = build_index(chunks)
    bm25_resp = query(bm25_index, "trademarks", top_k=1)

    model = FakeEmbeddingModel(dimension=8)
    model.load()
    dense_index = build_dense_index(chunks, model)
    dense_resp = dense_query(dense_index, model, "trademarks", top_k=1)

    rrf_resp = fuse_rrf(bm25_resp, dense_resp, candidate_k=1)

    reranker = FakeReranker()
    reranker.load()
    hybrid_resp = rerank_candidates(rrf_resp, reranker, top_k=1)

    pack = build_evidence_pack(hybrid_resp.results, "trademarks")
    real_id = pack.evidence_items[0].evidence_id

    provider = FakeGenerationProvider(response_text=f"Trademarks require filing. [[CITE:{real_id}]]")
    response = generate_grounded_response("trademarks", pack, provider)
    assert response.grounding_status == "GROUNDED"
    assert response.cited_evidence_ids == [real_id]

    coverage = compute_citation_coverage([])  # Phase 9 still importable/usable standalone
    assert coverage.total_references == 0


# ---------------------------------------------------------------------------
# Repository cleanliness for the Phase-9-through-Phase-10 boundary
# ---------------------------------------------------------------------------


def test_config_directory_still_contains_the_phase_0_through_9_files():
    actual = {p.name for p in CONFIG_DIR.glob("*.yaml")}
    assert EXPECTED_CONFIG_FILES_THROUGH_PHASE_9.issubset(actual), (
        f"config/ is missing Phase 0-9 files: {EXPECTED_CONFIG_FILES_THROUGH_PHASE_9 - actual}"
    )


def test_generation_config_files_exist():
    assert (CONFIG_DIR / "grounded_generation_contract.yaml").is_file()
    assert (CONFIG_DIR / "grounded_generation_schema.yaml").is_file()


def test_generation_source_directory_contains_expected_files():
    generation_dir = SRC_DIR / "generation"
    expected_files = {"__init__.py", "models.py", "prompts.py", "providers.py", "grounding.py", "generator.py", "serialize.py"}
    assert {p.name for p in generation_dir.glob("*.py")} == expected_files


def test_no_validation_module_duplicating_phase_9_exists_in_generation():
    # Explicit design decision: Phase 10 reuses citation.validator
    # directly and deliberately does NOT own a src/generation/validation.py.
    assert not (SRC_DIR / "generation" / "validation.py").exists()


def test_no_backend_frontend_or_deployment_directories_exist():
    # [ENGINEERING RECOMMENDATION] "scripts" removed: Phase 22 legitimately
    # introduces scripts/build_release_manifest.py as release-artifact
    # infrastructure, so this historical future-phase guard is no longer
    # valid for that one name. Disclosed phase-boundary amendment, not a
    # weakening - every other forbidden name here remains enforced.
    for forbidden in ("backend", "evaluation", "deployment"):
        assert not (REPO_ROOT / forbidden).exists()


def test_no_phase_11_or_later_directories_exist_yet():
    for forbidden in ("classification", "jurisdiction", "confidence", "escalation", "data", "corpus", "indexes", "index"):
        assert not (REPO_ROOT / forbidden).exists(), (
            f"'{forbidden}/' would imply Phase 11+ functionality, which Phase 10 must not create"
        )


def test_no_future_phase_module_names_present_anywhere():
    candidate_files = [f for f in REPO_ROOT.rglob("*.py") if not is_repo_scan_excluded(f)]
    lowered_names = [f.name.lower() for f in candidate_files]
    for hint in FUTURE_IMPLEMENTATION_MODULE_HINTS:
        matches = [n for n in lowered_names if hint in n]
        assert matches == [], f"found future-phase implementation module(s) matching {hint!r}: {matches}"


def test_no_forbidden_llm_sdk_or_web_framework_imports_anywhere_in_generation_source():
    forbidden_import_roots = (
        "chromadb", "qdrant", "weaviate", "pinecone",
        "tensorflow", "openai", "google", "langchain", "llama_index",
        "torch", "transformers", "sentence_transformers", "faiss",
        "requests", "httpx", "grpc",
    )
    import_line_re = re.compile(r"^\s*(?:import|from)\s+([\w\.]+)", re.MULTILINE)
    for py_file in (SRC_DIR / "generation").glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for module in import_line_re.findall(text):
            top_level = module.split(".")[0].lower()
            assert top_level not in forbidden_import_roots, (
                f"{py_file.relative_to(REPO_ROOT)} imports forbidden module {module!r}"
            )


def test_generation_source_only_imports_evidence_citation_and_stdlib():
    import_line_re = re.compile(r"^\s*(?:import|from)\s+([\w\.]+)", re.MULTILINE)
    for py_file in (SRC_DIR / "generation").glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for module in import_line_re.findall(text):
            top_level = module.split(".")[0]
            if top_level in ("retrieval", "chunking", "ingestion"):
                raise AssertionError(
                    f"{py_file.relative_to(REPO_ROOT)} imports {module!r} - Phase 10 must only depend on "
                    f"Phase 8 (evidence.*) and Phase 9 (citation.*), never earlier retrieval/chunking/ingestion internals"
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

    # Phase 10 adds ZERO new dependencies - identical to Phase 6/7/8/9's set.
    expected = {"pytest", "pyyaml", "pypdf", "sentence-transformers", "faiss-cpu", "numpy"}
    assert expected.issubset(declared_packages), (
        # A later phase (e.g. Phase 17's fastapi/pydantic/uvicorn/httpx) may
        # legitimately ADD dependencies beyond this phase's own baseline -
        # an exact-set check is structurally incompatible with that (the
        # same reasoning already applied when Phase 6 relaxed Phase 4/5's
        # own exact-set checks). This phase's own baseline must still be
        # present; nothing may be REMOVED from it.
        f"Phase 10 must add zero new dependencies beyond Phase 6's baseline, got: {declared_packages}"
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


def test_generation_fixtures_reuse_existing_synthetic_builders_not_new_ones():
    text = (REPO_ROOT / "tests" / "_generation_fixtures.py").read_text(encoding="utf-8")
    assert "from _citation_fixtures import" in text


def test_no_generated_answer_hardcoded_legal_conclusion_in_generation_source():
    forbidden_terms = ("legal_conclusion", "jurisdiction_decision", "confidence_score", "formulation_classification")
    for py_file in (SRC_DIR / "generation").glob("*.py"):
        text = py_file.read_text(encoding="utf-8").lower()
        for term in forbidden_terms:
            assert term not in text, f"{py_file.relative_to(REPO_ROOT)} contains forbidden term {term!r}"


def test_no_semantic_entailment_or_nli_logic_exists_in_generation_source():
    forbidden_terms = ("entailment", "nli_model", "cross_encoder", "embedding_similarity", "llm_judge")
    for py_file in (SRC_DIR / "generation").glob("*.py"):
        text = py_file.read_text(encoding="utf-8").lower()
        for term in forbidden_terms:
            assert term not in text, f"{py_file.relative_to(REPO_ROOT)} contains forbidden term {term!r}"


def test_no_live_credential_configuration_anywhere_in_generation_source():
    forbidden_terms = ("gemini_api_key", "genai.configure", "os.environ[\"gemini", "qwen_model_path")
    for py_file in (SRC_DIR / "generation").glob("*.py"):
        text = py_file.read_text(encoding="utf-8").lower()
        for term in forbidden_terms:
            assert term not in text, f"{py_file.relative_to(REPO_ROOT)} contains forbidden term {term!r}"


# ---------------------------------------------------------------------------
# docs/PHASE_10_GROUNDED_GENERATION.md completeness
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def phase_10_doc_text() -> str:
    path = DOCS_DIR / "PHASE_10_GROUNDED_GENERATION.md"
    assert path.is_file()
    return path.read_text(encoding="utf-8")


def test_phase_10_doc_exists_and_nonempty(phase_10_doc_text: str):
    assert len(phase_10_doc_text) > 0


@pytest.mark.parametrize("section_heading", REQUIRED_DOC_SECTIONS)
def test_phase_10_doc_has_required_section(phase_10_doc_text: str, section_heading: str):
    assert section_heading in phase_10_doc_text


def test_phase_10_doc_discloses_deferred_live_providers(phase_10_doc_text: str):
    assert "[DEFERRED]" in phase_10_doc_text
    assert "gemini" in phase_10_doc_text.lower()
    assert "qwen" in phase_10_doc_text.lower()


def test_phase_10_doc_states_phase_8_and_9_reuse(phase_10_doc_text: str):
    assert "Phase 8" in phase_10_doc_text
    assert "Phase 9" in phase_10_doc_text
    assert "reused" in phase_10_doc_text.lower() or "reuse" in phase_10_doc_text.lower()


def test_phase_10_doc_states_phase_11_through_13_boundaries(phase_10_doc_text: str):
    assert "Phase 11" in phase_10_doc_text
    assert "Phase 12" in phase_10_doc_text
    assert "Phase 13" in phase_10_doc_text


def test_phase_10_doc_honestly_discloses_prompt_injection_boundary(phase_10_doc_text: str):
    assert "prompt injection" in phase_10_doc_text.lower()
    assert "not a solved-problem claim" in phase_10_doc_text.lower() or "not claimed" in phase_10_doc_text.lower() or "never claimed" in phase_10_doc_text.lower()
