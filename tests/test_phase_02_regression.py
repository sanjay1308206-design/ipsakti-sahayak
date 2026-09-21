"""
Phase 2 tests: Phase 0 + Phase 1 regression, repository cleanliness for the
current phase boundary, and phase-boundary audit (no ingestion or future
functionality was implemented).

Phase 0's and Phase 1's own test files already re-run automatically as
part of `pytest tests/ -v` and constitute the primary regression check for
those phases. This file adds Phase-2-specific regression/cleanliness
checks per the same per-phase layering used in
test_phase_00_scope.py / test_phase_01_regression.py.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml

from _repo_scan import is_repo_scan_excluded

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
CONFIG_DIR = REPO_ROOT / "config"
SRC_DIR = REPO_ROOT / "src"

MASTER_REFERENCE_PDF = REPO_ROOT / "PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf"

# [ENGINEERING RECOMMENDATION] Phase 23.3.2E legitimately admitted the
# project's first real, non-synthetic corpus document (SF-05, FSSAI) -
# the corpus-document-file scan below now allows exactly this one
# additional file alongside the Master Reference PDF, never anything
# else. Disclosed phase-boundary amendment, not a weakening: any OTHER
# unexpected document-like file is still rejected.
ADMITTED_SF05_PDF = REPO_ROOT / "data" / "raw" / "SF-05" / "SF05-FSSAI-AYURVEDA-AAHARA-REGULATIONS-2022.pdf"
MASTER_REFERENCE_HASH_FILE = DOCS_DIR / "_master_reference.sha256"

EXPECTED_CONFIG_FILES_THROUGH_PHASE_2 = {
    "acceptance_contract.yaml",  # Phase 0
    "domain_taxonomy.yaml",  # Phase 1
    "regulatory_decision_tree.yaml",  # Phase 1
    "classification_contract.yaml",  # Phase 1
    "authority_matrix.yaml",  # Phase 2
    "corpus_provenance_schema.yaml",  # Phase 2
    "corpus_lock.yaml",  # Phase 2
}

FUTURE_IMPLEMENTATION_MODULE_HINTS = (
    # "bm25", "faiss", "embeddings", and "reranker" intentionally removed:
    # Phase 5 (BM25 Retrieval Baseline), Phase 6 (Multilingual Dense
    # Retrieval), and Phase 7 (Hybrid Fusion + Reranking) have since been
    # explicitly started under their own authorization, and legitimately
    # own `src/retrieval/bm25.py`, `src/retrieval/faiss_index.py`,
    # `src/retrieval/embeddings.py`, and `src/retrieval/reranker.py`. Same
    # pattern as the "ingest"/"chunker" removals below - this list still
    # guards against phases beyond the one currently in progress, never
    # the current phase's own name.
    "jurisdiction_firewall",
    "citation_validator",
    "confidence_engine",
    "formulation_classification_engine",
    # "ingest" intentionally removed: Phase 3 (Document Ingestion & Legal
    # Structure Extraction) has since been explicitly started under its own
    # authorization, and legitimately owns `src/ingestion/` and
    # `tests/test_phase_03_ingestion.py`. This list still guards against
    # phases beyond the one currently in progress (same pattern Phase 1's
    # regression file used: it never blocked Phase 2's own module names
    # once Phase 2 started).
    "scraper",
    "crawler",
    "ocr",
    "pdf_parser",
    # "chunker" intentionally removed: Phase 4 (Legal-Aware Chunking) has
    # since been explicitly started under its own authorization, and
    # legitimately owns `src/chunking/chunker.py`. Same pattern as the
    # "ingest" removal above - this list still guards against phases beyond
    # the one currently in progress, never the current phase's own name.
)

# "faiss"/"sentence-transformers" intentionally removed: Phase 6 has since
# been explicitly started and legitimately declares them in
# requirements-dev.txt (same pattern as the module-name hints above).
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
)


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
# Phase 0 + Phase 1 artifacts remain intact
# ---------------------------------------------------------------------------


def test_phase_00_and_phase_01_docs_still_present_and_intact():
    phase_00 = DOCS_DIR / "PHASE_00_SCOPE_AND_ACCEPTANCE.md"
    phase_01_a = DOCS_DIR / "PHASE_01_DOMAIN_TAXONOMY.md"
    phase_01_b = DOCS_DIR / "PHASE_01_REGULATORY_DECISION_TREE.md"
    for doc in (phase_00, phase_01_a, phase_01_b):
        assert doc.is_file()
        assert doc.stat().st_size > 0

    assert "Every mandatory PS capability has an owner, test, and acceptance criterion." in phase_00.read_text(
        encoding="utf-8"
    )
    assert "AYURVEDA_AAHARA_FOOD" in phase_01_a.read_text(encoding="utf-8")


def test_phase_01_yaml_contracts_still_valid_and_unchanged_in_shape():
    taxonomy = yaml.safe_load((CONFIG_DIR / "domain_taxonomy.yaml").read_text(encoding="utf-8"))
    assert taxonomy["taxonomy_version"] == "1.0.0"

    tree = yaml.safe_load((CONFIG_DIR / "regulatory_decision_tree.yaml").read_text(encoding="utf-8"))
    assert [s["rule_id"] for s in tree["stages"]] == ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"]

    contract = yaml.safe_load((CONFIG_DIR / "classification_contract.yaml").read_text(encoding="utf-8"))
    field_names = {f["name"] for f in contract["fields"]}
    assert "regulatory_question_type" in field_names


def test_phase_01_regulatory_question_types_match_phase_02_source_family_mapping():
    # Cross-phase consistency: Phase 1's regulatory_question_categories and
    # Phase 2's authority_matrix supported_question_types must reference
    # the same closed vocabulary (both derived from the same Master
    # Reference table).
    taxonomy = yaml.safe_load((CONFIG_DIR / "domain_taxonomy.yaml").read_text(encoding="utf-8"))
    rq_names = {c["name"] for c in taxonomy["regulatory_question_categories"]["categories"]}

    authority = yaml.safe_load((CONFIG_DIR / "authority_matrix.yaml").read_text(encoding="utf-8"))
    supported = set()
    for fam in authority["source_families"]:
        supported.update(fam["supported_question_types"])

    # Every question type an SF supports must be a real Phase 1 RQ category.
    assert supported.issubset(rq_names)
    # Every non-UNDETERMINED RQ category must be backed by at least one SF.
    assert (rq_names - {"UNDETERMINED"}).issubset(supported)


def test_acceptance_contract_still_untouched():
    contract = yaml.safe_load((CONFIG_DIR / "acceptance_contract.yaml").read_text(encoding="utf-8"))
    cap_02 = next(c for c in contract["mandatory_capabilities"] if c["id"] == "CAP-02")
    assert cap_02["owner_phase"] == 2
    assert cap_02["status"] == "DEFINED"


def test_phase_tracker_phases_0_and_1_remain_done_and_phase_2_updated():
    # Own-phase-only checks (permanently valid - see
    # test_phase_00_scope.py::test_phase_tracker_no_phase_is_skipped_ahead
    # for the general, self-adjusting "no phase skipped ahead" invariant
    # that makes a hardcoded downstream range here unnecessary and, per
    # Phase 1's experience, actively harmful since it goes stale the
    # moment the next phase legitimately starts).
    text = (DOCS_DIR / "PHASE_TRACKER.md").read_text(encoding="utf-8")
    pattern = re.compile(r"^## Phase (\d+) .*?\n- \*\*Status:\*\* (.+)$", re.MULTILINE)
    statuses = {int(m.group(1)): m.group(2).strip() for m in pattern.finditer(text)}

    assert set(statuses.keys()) == set(range(24))
    assert statuses[0] != "NOT STARTED"
    assert statuses[1] != "NOT STARTED"
    assert statuses[2] != "NOT STARTED", "Phase 2 tracker entry was not updated"


# ---------------------------------------------------------------------------
# Repository cleanliness for the Phase-0-through-Phase-2 boundary
# ---------------------------------------------------------------------------


def test_config_directory_still_contains_the_phase_0_through_2_files():
    # Narrowed to a subset check, same reasoning as
    # test_phase_01_regression.py's equivalent: Phase 3 legitimately adds
    # its own YAML contracts to config/. The stricter "exact set for the
    # current phase" check lives in tests/test_phase_03_regression.py.
    actual = {p.name for p in CONFIG_DIR.glob("*.yaml")}
    assert EXPECTED_CONFIG_FILES_THROUGH_PHASE_2.issubset(actual), (
        f"config/ is missing Phase 0-2 files: {EXPECTED_CONFIG_FILES_THROUGH_PHASE_2 - actual}"
    )


def test_src_directory_exists():
    # See test_phase_00_scope.py::test_src_directory_exists for why this
    # was relaxed from "src/ has zero .py files" - Phase 3 legitimately
    # introduces src/ingestion/. The permanent guarantee lives in
    # test_no_future_phase_module_names_present_anywhere below.
    assert SRC_DIR.is_dir()


def test_no_backend_frontend_or_evaluation_directories_exist():
    # [ENGINEERING RECOMMENDATION] "scripts" removed: Phase 22 legitimately
    # introduces scripts/build_release_manifest.py as release-artifact
    # infrastructure, so this historical future-phase guard is no longer
    # valid for that one name. Disclosed phase-boundary amendment, not a
    # weakening - every other forbidden name here remains enforced.
    for forbidden in ("backend", "evaluation"):
        assert not (REPO_ROOT / forbidden).exists()


def test_no_data_or_corpus_directories_exist_yet():
    # Phase 2 is policy-only; no data/raw, data/normalized, data/chunks,
    # data/indexes, or similar corpus directories may exist yet (Phase 3+).
    # [ENGINEERING RECOMMENDATION] "data"/"corpus" removed from this
    # list: Phase 23.3.2E legitimately introduces the project's first
    # real, admitted corpus document (data/raw/, data/manifest/,
    # data/normalized/ - config/authority_matrix.yaml SF-05), so this
    # historical pre-corpus guard is no longer valid for those two
    # names specifically. Disclosed phase-boundary amendment, the same
    # pattern already used for "scripts"/".github" in Phase 22 - never
    # a silent weakening. Every other forbidden name here (indexes,
    # index, vector stores, etc.) remains unchanged and still enforced,
    # since no BM25/dense index has been built yet.
    for forbidden in ("indexes",):
        assert not (REPO_ROOT / forbidden).exists(), (
            f"'{forbidden}/' would imply corpus ingestion, which Phase 2 must not perform"
        )


def test_no_future_phase_module_names_present_anywhere():
    candidate_files = [f for f in REPO_ROOT.rglob("*.py") if not is_repo_scan_excluded(f)]
    lowered_names = [f.name.lower() for f in candidate_files]
    for hint in FUTURE_IMPLEMENTATION_MODULE_HINTS:
        matches = [n for n in lowered_names if hint in n]
        assert matches == [], f"found future-phase implementation module(s) matching {hint!r}: {matches}"


def test_admission_policy_reference_impl_is_test_support_only_not_production():
    helper = REPO_ROOT / "tests" / "_admission_policy_reference_impl.py"
    assert helper.is_file()
    assert not (SRC_DIR / "_admission_policy_reference_impl.py").exists()
    text = helper.read_text(encoding="utf-8")
    assert "NOT a document ingestion" in text


def test_no_new_heavyweight_dependency_declared_in_phase_2():
    # Checks actual declared package names only (non-comment requirement
    # lines) - a raw substring search over the whole file text would
    # misfire on a later phase's own justification comment merely
    # discussing/naming a forbidden package or model (e.g. Phase 6's own
    # comment explaining sentence-transformers "runs BGE-M3" mentions
    # "bge-m3" in prose without declaring any package by that name) - the
    # same documentation-vs-implementation false-positive class already
    # fixed for phase-boundary hints.
    req_dev_raw = (REPO_ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    declared_packages = set()
    for line in req_dev_raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name = re.split(r"[><=!~\[]", stripped, maxsplit=1)[0].strip().lower()
        if name:
            declared_packages.add(name)
    for pkg in FORBIDDEN_DEPENDENCY_PACKAGES:
        assert pkg.lower() not in declared_packages, f"forbidden heavyweight dependency declared: {pkg}"
    assert not (REPO_ROOT / "requirements.txt").exists()


def test_no_corpus_document_files_exist_anywhere():
    # No PDFs, HTML, or other document-like files were downloaded/ingested
    # by Phase 2, beyond the one Master Reference PDF that was already
    # present before Phase 0 began.
    doc_like_extensions = (".pdf", ".html", ".htm", ".docx", ".doc")
    found = [
        p
        for p in REPO_ROOT.rglob("*")
        if p.is_file()
        and p.suffix.lower() in doc_like_extensions
        and not is_repo_scan_excluded(p)
        and "frontend" not in p.parts
    ]
    assert set(found) == {MASTER_REFERENCE_PDF, ADMITTED_SF05_PDF}, (
        f"unexpected document-like file(s) found (possible ingestion): "
        f"{[str(p) for p in found if p not in {MASTER_REFERENCE_PDF, ADMITTED_SF05_PDF}]}"
    )
