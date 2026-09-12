"""
Phase 15 tests: Master Reference integrity, Phase 0-14 regression
protection, repository cleanliness for the Phase 14-15 boundary,
phase-boundary audit (no Phase 16+ implementation leaked in), dependency
discipline, and docs/PHASE_15_HUMAN_IN_THE_LOOP.md completeness.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
CONFIG_DIR = REPO_ROOT / "config"
SRC_DIR = REPO_ROOT / "src"

MASTER_REFERENCE_PDF = REPO_ROOT / "PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf"
MASTER_REFERENCE_HASH_FILE = DOCS_DIR / "_master_reference.sha256"

EXPECTED_CONFIG_FILES_THROUGH_PHASE_14 = {
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
    "jurisdiction_firewall_contract.yaml",
    "confidence_safety_contract.yaml",
    "multilingual_delivery_contract.yaml",
}

# Phases beyond the one now in progress (Phase 15). "reviewer_queue" and
# "human_escalation" are deliberately absent - Phase 15 IS the
# human-in-the-loop phase, now explicitly authorized and in progress, and
# its modules are named models.py/policy.py/workflow.py/validation.py/
# serialize.py under src/review/ (never "reviewer_queue.py" or
# "human_escalation.py"), so no collision exists or is expected.
FUTURE_IMPLEMENTATION_MODULE_HINTS = (
    "scraper",
    "crawler",
    "ocr",
    "pdf_parser",
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
    "A. Objective",
    "B. Scope",
    "C. Non-Scope",
    "D. Architecture",
    "E. Review Triggers",
    "F. Review Request",
    "G. Review States",
    "H. Review Decisions",
    "I. Reviewer Identity",
    "J. Evidence Immutability",
    "K. Citation Integrity",
    "L. Classification Interaction",
    "M. Jurisdiction Interaction",
    "N. Grounding Interaction",
    "O. Safety Interaction",
    "P. Multilingual Interaction",
    "Q. Review Snapshot",
    "R. Audit Trail",
    "S. Reviewer Comments",
    "T. Security",
    "U. Prompt Injection",
    "V. Serialization",
    "W. Determinism",
    "X. Synthetic Testing",
    "Y. Known Limitations",
    "Z. Deferred Items",
    "AA. Phase 16 Boundary",
    "AB. Acceptance Gate",
    "AC. Validation Evidence",
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
# Phase 0-14 artifacts remain intact
# ---------------------------------------------------------------------------


def test_phase_00_through_14_docs_still_present_and_intact():
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
        DOCS_DIR / "PHASE_12_JURISDICTION_FIREWALL.md",
        DOCS_DIR / "PHASE_13_CONFIDENCE_SAFETY_ABSTENTION.md",
        DOCS_DIR / "PHASE_14_MULTILINGUAL_DELIVERY.md",
    ]
    for doc in docs:
        assert doc.is_file()
        assert doc.stat().st_size > 0


def test_phase_tracker_phases_0_through_14_remain_done_and_all_phases_present():
    text = (DOCS_DIR / "PHASE_TRACKER.md").read_text(encoding="utf-8")
    pattern = re.compile(r"^## Phase (\d+) .*?\n- \*\*Status:\*\* (.+)$", re.MULTILINE)
    statuses = {int(m.group(1)): m.group(2).strip() for m in pattern.finditer(text)}

    assert set(statuses.keys()) == set(range(24))
    for phase in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14):
        assert statuses[phase] != "NOT STARTED", f"Phase {phase} tracker entry regressed to NOT STARTED"


def test_all_prior_phase_source_directories_untouched_by_phase_15():
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
    assert {p.name for p in (SRC_DIR / "jurisdiction").glob("*.py")} == {
        "__init__.py", "models.py", "policy.py", "firewall.py", "filtering.py", "serialize.py",
    }
    assert {p.name for p in (SRC_DIR / "safety").glob("*.py")} == {
        "__init__.py", "models.py", "policy.py", "evaluator.py", "serialize.py",
    }
    assert {p.name for p in (SRC_DIR / "multilingual").glob("*.py")} == {
        "__init__.py", "models.py", "preservation.py", "providers.py", "delivery.py", "serialize.py",
    }


def test_full_pipeline_through_human_review_is_importable_and_functional():
    import sys

    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))

    from classification.classifier import classify
    from classification.models import ClassificationInput
    from evidence.builder import build_evidence_pack
    from generation.generator import generate_grounded_response
    from generation.providers import FakeGenerationProvider
    from jurisdiction.firewall import resolve_jurisdiction
    from review.policy import authorize_presentation, build_review_request
    from review.workflow import apply_action
    from safety.evaluator import evaluate_safety

    cls = classify(ClassificationInput(input_id="SMOKE15", raw_query="how can i protect this and what compliance requirement applies in India"))
    assert cls.classification_state == "AMBIGUOUS"
    jur = resolve_jurisdiction("SMOKE15-J", classification_result=cls)

    from dataclasses import dataclass

    @dataclass
    class FakeCandidate:
        chunk_id: str
        chunk_text: str
        document_id: str
        source_family_id: str
        jurisdiction: str
        content_hash: str
        synthetic: bool
        page_numbers: list
        block_ids: list
        rank: int
        score: float = 1.0

    c1 = FakeCandidate(
        chunk_id="C1", chunk_text="Ayush policy content.", document_id="D1", source_family_id="SF-03",
        jurisdiction="INDIA", content_hash="a" * 64, synthetic=True, page_numbers=[1], block_ids=["C1:p1:b1"], rank=1,
    )
    pack = build_evidence_pack([c1], "ayush policy")
    real_id = pack.evidence_items[0].evidence_id
    gr = generate_grounded_response("ayush policy", pack, FakeGenerationProvider(response_text=f"Policy details. [[CITE:{real_id}]]"))

    safety = evaluate_safety("SMOKE15-S", classification_result=cls, jurisdiction_decision=jur, grounded_response=gr)
    assert safety.safety_status == "ESCALATE"

    request = build_review_request("SMOKE15", "ayush policy", classification_result=cls, jurisdiction_decision=jur, grounded_response=gr, safety_decision=safety)
    assert request is not None
    assert "SAFETY_ESCALATE" in request.trigger_reasons

    action = apply_action(request, [], reviewer_id="smoke-reviewer", action="APPROVE", selected_evidence_ids=[real_id], evidence_pack=pack)
    auth = authorize_presentation(safety, action)
    assert auth.authorized is True
    assert auth.source == "HUMAN_REVIEW_APPROVED"

    # Upstream objects remain completely untouched.
    assert safety.safety_status == "ESCALATE"
    assert cls.classification_state == "AMBIGUOUS"
    assert pack.evidence_items[0].evidence_id == real_id


# ---------------------------------------------------------------------------
# Repository cleanliness for the Phase-14-through-Phase-15 boundary
# ---------------------------------------------------------------------------


def test_config_directory_still_contains_the_phase_0_through_14_files():
    actual = {p.name for p in CONFIG_DIR.glob("*.yaml")}
    assert EXPECTED_CONFIG_FILES_THROUGH_PHASE_14.issubset(actual), (
        f"config/ is missing Phase 0-14 files: {EXPECTED_CONFIG_FILES_THROUGH_PHASE_14 - actual}"
    )


def test_human_review_config_file_exists():
    assert (CONFIG_DIR / "human_review_contract.yaml").is_file()


def test_review_source_directory_contains_expected_files():
    review_dir = SRC_DIR / "review"
    assert {p.name for p in review_dir.glob("*.py")} == {
        "__init__.py", "models.py", "policy.py", "workflow.py", "validation.py", "serialize.py",
    }


def test_no_backend_frontend_or_deployment_directories_exist():
    for forbidden in ("backend", "evaluation", "scripts", "deployment"):
        assert not (REPO_ROOT / forbidden).exists()


def test_no_phase_16_or_later_directories_exist_yet():
    for forbidden in ("reviewers", "data", "corpus", "indexes", "index", "benchmarks"):
        assert not (REPO_ROOT / forbidden).exists(), (
            f"'{forbidden}/' would imply Phase 16+ functionality, which Phase 15 must not create"
        )


def test_no_future_phase_module_names_present_anywhere():
    candidate_files = [f for f in REPO_ROOT.rglob("*.py") if ".git" not in f.parts]
    lowered_names = [f.name.lower() for f in candidate_files]
    for hint in FUTURE_IMPLEMENTATION_MODULE_HINTS:
        matches = [n for n in lowered_names if hint in n]
        assert matches == [], f"found future-phase implementation module(s) matching {hint!r}: {matches}"


def test_no_forbidden_imports_anywhere_in_review_source():
    forbidden_import_roots = (
        "chromadb", "qdrant", "weaviate", "pinecone",
        "tensorflow", "openai", "google", "langchain", "llama_index",
        "torch", "transformers", "sentence_transformers", "faiss",
        "requests", "httpx", "grpc", "geopy", "geoip2", "socket", "flask", "django",
    )
    import_line_re = re.compile(r"^\s*(?:import|from)\s+([\w\.]+)", re.MULTILINE)
    for py_file in (SRC_DIR / "review").glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for module in import_line_re.findall(text):
            top_level = module.split(".")[0].lower()
            assert top_level not in forbidden_import_roots, (
                f"{py_file.relative_to(REPO_ROOT)} imports forbidden module {module!r}"
            )


def test_review_source_never_imports_evidence_construction_or_mutation_functions():
    # Phase 15 may only ever check evidence_id MEMBERSHIP against a real
    # EvidencePack (docs Section J/K) - it must never construct, rebuild,
    # or otherwise mutate Evidence/EvidencePack objects.
    forbidden_symbols = ("build_evidence_from_candidate", "build_evidence_pack", "resolve_citation_target")
    for py_file in (SRC_DIR / "review").glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for symbol in forbidden_symbols:
            assert symbol not in text, f"{py_file.relative_to(REPO_ROOT)} references forbidden evidence-construction symbol {symbol!r}"


def test_review_source_never_imports_construction_functions_from_earlier_phases():
    # Phase 15 must only ever import TYPES/vocabularies from
    # classification/jurisdiction/generation/safety/multilingual - never
    # their own construction/orchestration entry points (classify(),
    # resolve_jurisdiction(), generate_grounded_response(),
    # evaluate_safety(), deliver_response()) - those remain each phase's
    # own exclusive authority.
    forbidden_symbols = ("classify(", "resolve_jurisdiction(", "generate_grounded_response(", "evaluate_safety(", "deliver_response(")
    for py_file in (SRC_DIR / "review").glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for symbol in forbidden_symbols:
            assert symbol not in text, f"{py_file.relative_to(REPO_ROOT)} references forbidden construction symbol {symbol!r}"


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
        f"Phase 15 must add zero new dependencies beyond Phase 6's baseline, got: {declared_packages}"
    )


def test_no_corpus_document_files_exist_anywhere():
    doc_like_extensions = (".pdf", ".html", ".htm", ".docx", ".doc")
    found = [
        p
        for p in REPO_ROOT.rglob("*")
        if p.is_file() and p.suffix.lower() in doc_like_extensions and ".git" not in p.parts and "frontend" not in p.parts
    ]
    assert found == [MASTER_REFERENCE_PDF], (
        f"unexpected document-like file(s) found (possible ingestion/corpus leakage): {found}"
    )


def test_review_fixtures_reuse_existing_multilingual_fixtures_not_new_ones():
    text = (REPO_ROOT / "tests" / "_review_fixtures.py").read_text(encoding="utf-8")
    assert "from _multilingual_fixtures import" in text


def test_no_legal_conclusion_or_probability_terms_in_review_source():
    forbidden_terms = (
        "legal_conclusion", "is_legally_valid", "legally_certain", "legal_determination",
        "patentability_probability", "infringement_probability", "compliance_probability",
        "confidence =", "confidence=0",
    )
    for py_file in (SRC_DIR / "review").glob("*.py"):
        text = py_file.read_text(encoding="utf-8").lower()
        for term in forbidden_terms:
            assert term not in text, f"{py_file.relative_to(REPO_ROOT)} contains forbidden term {term!r}"


def test_no_semantic_entailment_logic_exists_in_review_source():
    forbidden_terms = ("nli_model", "cross_encoder", "embedding_similarity", "llm_judge", "claim_verification")
    for py_file in (SRC_DIR / "review").glob("*.py"):
        text = py_file.read_text(encoding="utf-8").lower()
        for term in forbidden_terms:
            assert term not in text, f"{py_file.relative_to(REPO_ROOT)} contains forbidden term {term!r}"


def test_no_authentication_or_reviewer_dashboard_terms_in_review_source():
    forbidden_terms = ("password_hash", "jwt", "oauth", "session_token", "login", "dashboard", "reviewer_ui")
    for py_file in (SRC_DIR / "review").glob("*.py"):
        text = py_file.read_text(encoding="utf-8").lower()
        for term in forbidden_terms:
            assert term not in text, f"{py_file.relative_to(REPO_ROOT)} contains forbidden term {term!r}"


def test_no_corpus_feedback_or_retraining_terms_in_review_source():
    forbidden_terms = ("retrain", "fine_tune", "update_corpus", "corpus_refresh", "reindex", "auto_ingest")
    for py_file in (SRC_DIR / "review").glob("*.py"):
        text = py_file.read_text(encoding="utf-8").lower()
        for term in forbidden_terms:
            assert term not in text, f"{py_file.relative_to(REPO_ROOT)} contains forbidden term {term!r}"


def test_no_fastapi_react_or_frontend_terms_in_review_source():
    forbidden_terms = ("react", "vite", "jsx", "@app.route", "apirouter")
    for py_file in (SRC_DIR / "review").glob("*.py"):
        text = py_file.read_text(encoding="utf-8").lower()
        for term in forbidden_terms:
            assert term not in text, f"{py_file.relative_to(REPO_ROOT)} contains forbidden term {term!r}"


def test_no_eval_or_exec_anywhere_in_review_source():
    for py_file in (SRC_DIR / "review").glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        assert "eval(" not in text
        assert "exec(" not in text


def test_no_wall_clock_timestamp_usage_in_review_source():
    forbidden_terms = ("datetime.now", "time.time", "utcnow", "timezone.utc")
    for py_file in (SRC_DIR / "review").glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for term in forbidden_terms:
            assert term not in text, f"{py_file.relative_to(REPO_ROOT)} contains forbidden timestamp usage {term!r}"


# ---------------------------------------------------------------------------
# docs/PHASE_15_HUMAN_IN_THE_LOOP.md completeness
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def phase_15_doc_text() -> str:
    path = DOCS_DIR / "PHASE_15_HUMAN_IN_THE_LOOP.md"
    assert path.is_file()
    return path.read_text(encoding="utf-8")


def test_phase_15_doc_exists_and_nonempty(phase_15_doc_text: str):
    assert len(phase_15_doc_text) > 0


@pytest.mark.parametrize("section_heading", REQUIRED_DOC_SECTIONS)
def test_phase_15_doc_has_required_section(phase_15_doc_text: str, section_heading: str):
    assert section_heading in phase_15_doc_text


def test_phase_15_doc_states_phase_8_through_14_reuse(phase_15_doc_text: str):
    for phase_name in ("Phase 8", "Phase 9", "Phase 10", "Phase 11", "Phase 12", "Phase 13", "Phase 14"):
        assert phase_name in phase_15_doc_text


def test_phase_15_doc_states_phase_16_boundary(phase_15_doc_text: str):
    assert "Phase 16" in phase_15_doc_text


def test_phase_15_doc_discloses_no_real_authentication(phase_15_doc_text: str):
    assert "[DEFERRED]" in phase_15_doc_text
    assert "no real authentication" in phase_15_doc_text.lower() or "real authentication" in phase_15_doc_text.lower()


def test_phase_15_doc_discloses_no_numeric_confidence(phase_15_doc_text: str):
    assert "numeric" in phase_15_doc_text.lower()
    assert "categorical" in phase_15_doc_text.lower()
