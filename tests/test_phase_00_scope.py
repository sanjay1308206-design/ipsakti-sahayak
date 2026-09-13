"""
Phase 0 tests: problem/scope contract document, repository regression
invariants, and phase-isolation (phase-boundary) checks.

These tests validate PROJECT-CONTROL ARTIFACTS (markdown/docs/repo layout),
not application behavior - Phase 0 implements no application functionality,
so there is no retrieval/classification/generation code to test yet.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
CONFIG_DIR = REPO_ROOT / "config"

PHASE_00_DOC = DOCS_DIR / "PHASE_00_SCOPE_AND_ACCEPTANCE.md"
MASTER_LOCK_DOC = DOCS_DIR / "MASTER_REFERENCE_LOCK.md"
DEV_RULES_DOC = DOCS_DIR / "DEVELOPMENT_RULES.md"
PHASE_TRACKER_DOC = DOCS_DIR / "PHASE_TRACKER.md"
MASTER_REFERENCE_PDF = REPO_ROOT / "PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf"
MASTER_REFERENCE_HASH_FILE = DOCS_DIR / "_master_reference.sha256"

SOURCE_DISCIPLINE_LABELS = (
    "[OFFICIAL PS]",
    "[OFFICIAL SOURCE]",
    "[EXTERNAL RESEARCH]",
    "[ENGINEERING RECOMMENDATION]",
    "[OUR ENHANCEMENT]",
    "[ASSUMPTION]",
    "[DEFERRED]",
)

REQUIRED_PHASE_00_SECTIONS = (
    "1. Project Identity",
    "2. Problem Definition",
    "3. System Purpose",
    "4. MVP Scope",
    "5. Out of Scope",
    "6. Core User Workflows",
    "7. System Boundaries",
    "8. Safety Boundary",
    "9. Evidence & Provenance Contract",
    "10. Non-Functional Requirements",
    "11. Hardware Constraints",
    "12. Deferred Technologies",
    "13. Acceptance Contract",
    "14. Phase Boundary",
)

# Functionality that belongs to Phase 1 or later and must NOT exist as
# actual importable Python modules anywhere in the repository yet.
# "bm25", "faiss", "embeddings", and "reranker" intentionally removed:
# Phase 5 (BM25 Retrieval Baseline), Phase 6 (Multilingual Dense
# Retrieval), and Phase 7 (Hybrid Fusion + Reranking) have since been
# explicitly started under their own authorization, and legitimately own
# src/retrieval/bm25.py, src/retrieval/faiss_index.py,
# src/retrieval/embeddings.py, and src/retrieval/reranker.py (see
# tests/test_phase_02_regression.py for the identical reasoning applied
# each time a new phase starts).
FUTURE_IMPLEMENTATION_MODULE_HINTS = (
    "jurisdiction_firewall",
    "citation_validator",
    "classification_engine",
    "confidence_engine",
)


# ---------------------------------------------------------------------------
# Control-document presence (regression: initialization artifacts intact)
# ---------------------------------------------------------------------------


def test_initialization_control_documents_still_exist():
    for doc in (MASTER_LOCK_DOC, DEV_RULES_DOC, PHASE_TRACKER_DOC):
        assert doc.is_file(), f"expected initialization control document missing: {doc}"
        assert doc.stat().st_size > 0, f"control document is empty: {doc}"


def test_master_reference_pdf_present_and_unmodified():
    assert MASTER_REFERENCE_PDF.is_file(), "Master Reference PDF must remain at repo root"
    assert MASTER_REFERENCE_HASH_FILE.is_file(), "expected recorded PDF hash baseline"

    recorded_line = MASTER_REFERENCE_HASH_FILE.read_text(encoding="utf-8").strip()
    recorded_hash = recorded_line.split()[0]

    actual_hash = hashlib.sha256(MASTER_REFERENCE_PDF.read_bytes()).hexdigest()
    assert actual_hash == recorded_hash, (
        "Master Reference PDF content changed since the Phase 0 baseline was recorded "
        "- the authoritative source must not be modified by any phase"
    )


# ---------------------------------------------------------------------------
# Phase 0 document structure
# ---------------------------------------------------------------------------


def test_phase_00_doc_exists_and_nonempty():
    assert PHASE_00_DOC.is_file(), f"missing {PHASE_00_DOC}"
    assert PHASE_00_DOC.stat().st_size > 0


@pytest.fixture(scope="module")
def phase_00_text() -> str:
    return PHASE_00_DOC.read_text(encoding="utf-8")


@pytest.mark.parametrize("section", REQUIRED_PHASE_00_SECTIONS)
def test_phase_00_doc_has_required_section(phase_00_text: str, section: str):
    assert section in phase_00_text, f"Phase 0 document missing required section: {section!r}"


@pytest.mark.parametrize("label", SOURCE_DISCIPLINE_LABELS)
def test_phase_00_doc_uses_every_source_discipline_label(phase_00_text: str, label: str):
    assert label in phase_00_text, (
        f"Phase 0 document never uses source-discipline label {label!r}; "
        f"every important claim must be labeled"
    )


def test_phase_00_doc_does_not_claim_legal_advice(phase_00_text: str):
    lowered = phase_00_text.lower()
    assert "does not provide legal advice" in lowered or "not legal advice" in lowered or (
        "legal determination" in lowered and "not" in lowered
    ), "Phase 0 document must explicitly disclaim legal advice / legal determinations"


def test_phase_00_doc_states_no_application_implementation(phase_00_text: str):
    assert "implements no application functionality" in phase_00_text or (
        "no retrieval" in phase_00_text.lower() and "no application" in phase_00_text.lower()
    )


def test_phase_00_doc_names_phase_1_as_next(phase_00_text: str):
    assert "Phase 1" in phase_00_text
    assert "Domain Taxonomy" in phase_00_text


def test_phase_00_doc_references_config_contract_path(phase_00_text: str):
    assert "config" in phase_00_text and "acceptance_contract.yaml" in phase_00_text


# ---------------------------------------------------------------------------
# Phase tracker consistency (Phase 0 in progress/complete; 1-23 untouched)
# ---------------------------------------------------------------------------


def _parse_phase_statuses(tracker_text: str) -> dict[int, str]:
    statuses: dict[int, str] = {}
    pattern = re.compile(
        r"^## Phase (\d+) .*?\n- \*\*Status:\*\* (.+)$",
        re.MULTILINE,
    )
    for match in pattern.finditer(tracker_text):
        phase_num = int(match.group(1))
        status = match.group(2).strip()
        statuses[phase_num] = status
    return statuses


@pytest.fixture(scope="module")
def phase_tracker_text() -> str:
    return PHASE_TRACKER_DOC.read_text(encoding="utf-8")


def test_phase_tracker_covers_all_24_phases(phase_tracker_text: str):
    statuses = _parse_phase_statuses(phase_tracker_text)
    assert set(statuses.keys()) == set(range(24)), (
        f"expected phases 0..23, found {sorted(statuses.keys())}"
    )


def test_phase_tracker_no_phase_is_skipped_ahead(phase_tracker_text: str):
    # Permanent, self-adjusting invariant (replaces an earlier version of
    # this test that hardcoded "phases 1-23 must be NOT STARTED", then
    # "phases 2-23", and would otherwise need editing every single future
    # phase as work progresses - see docs/PHASE_TRACKER.md history). The
    # actual guarantee this project needs is that phases are worked in
    # order: the set of phases that have moved off NOT STARTED must be a
    # contiguous prefix {0, 1, ..., k}, never skipping ahead. This holds
    # true forever and needs no further edits as later phases start.
    statuses = _parse_phase_statuses(phase_tracker_text)
    started = sorted(n for n, s in statuses.items() if s != "NOT STARTED")
    assert started == list(range(len(started))), (
        f"phases that have moved off NOT STARTED must form a contiguous prefix starting at 0; "
        f"found {started}"
    )


def test_phase_tracker_phase_0_is_no_longer_not_started(phase_tracker_text: str):
    statuses = _parse_phase_statuses(phase_tracker_text)
    assert statuses[0] != "NOT STARTED", (
        "Phase 0 tracker entry was not updated to reflect Phase 0 work"
    )


# ---------------------------------------------------------------------------
# Phase-boundary audit: no future-phase implementation exists
# ---------------------------------------------------------------------------


def test_src_directory_exists():
    # Historical note: this test previously asserted src/ contained zero
    # .py files at all. That guarantee held through Phase 2 but was always
    # necessarily temporary - the Master Reference's own Phase 3 build
    # scope explicitly calls for ingestion/extraction implementation under
    # src/ (docs/PHASE_03_DOCUMENT_INGESTION.md). The permanent version of
    # this guarantee - no FUTURE-phase functionality (retrieval, embeddings,
    # generation, etc.) appears anywhere in the repo - is enforced forever
    # by test_no_future_phase_module_names_present_anywhere below, which
    # every phase's regression suite extends with new forbidden keywords as
    # needed. This test is kept only as a minimal directory-existence check.
    src_dir = REPO_ROOT / "src"
    assert src_dir.is_dir()


def test_no_backend_or_frontend_directories_exist():
    # [ENGINEERING RECOMMENDATION] "scripts" removed: Phase 22 legitimately
    # introduces scripts/build_release_manifest.py as release-artifact
    # infrastructure, so this historical future-phase guard is no longer
    # valid for that one name. Disclosed phase-boundary amendment, not a
    # weakening - every other forbidden name here remains enforced.
    for forbidden in ("backend", "evaluation"):
        assert not (REPO_ROOT / forbidden).exists(), (
            f"'{forbidden}/' belongs to a later phase and must not exist yet"
        )


def test_no_future_phase_module_names_present_anywhere():
    candidate_files = list(REPO_ROOT.rglob("*.py"))
    candidate_files = [f for f in candidate_files if ".git" not in f.parts]
    lowered_names = [f.name.lower() for f in candidate_files]
    for hint in FUTURE_IMPLEMENTATION_MODULE_HINTS:
        matches = [n for n in lowered_names if hint in n]
        assert matches == [], f"found future-phase implementation module(s) matching {hint!r}: {matches}"


def test_no_heavyweight_ml_dependency_declared():
    # "faiss"/"sentence-transformers" intentionally removed from this list:
    # Phase 6 (Multilingual Dense Retrieval) has since been explicitly
    # started under its own authorization and legitimately declares
    # faiss-cpu and sentence-transformers in requirements-dev.txt (see
    # tests/test_phase_02_regression.py for the identical reasoning
    # applied each time a new phase starts).
    #
    # Checks actual declared package names only (non-comment requirement
    # lines) - not a raw substring search over the whole file text, which
    # would misfire on a later phase's own justification comment merely
    # discussing/naming a forbidden package or model (e.g. Phase 6's own
    # comment explaining sentence-transformers "runs BGE-M3" mentions
    # "bge-m3" in prose, without declaring any package by that name) - the
    # same documentation-vs-implementation false-positive class already
    # fixed for phase-boundary hints.
    forbidden_packages = (
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
    req_dev = REPO_ROOT / "requirements-dev.txt"
    assert req_dev.is_file()
    req_dev_raw = req_dev.read_text(encoding="utf-8")
    declared_packages = set()
    for line in req_dev_raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name = re.split(r"[><=!~\[]", stripped, maxsplit=1)[0].strip().lower()
        if name:
            declared_packages.add(name)
    for pkg in forbidden_packages:
        assert pkg.lower() not in declared_packages, f"forbidden heavyweight dependency declared: {pkg}"

    # requirements.txt (full project deps) should not exist yet either -
    # it belongs to later productization phases (17+), not Phase 0.
    assert not (REPO_ROOT / "requirements.txt").exists(), (
        "requirements.txt (full application dependency manifest) does not belong to Phase 0"
    )


def test_gitignore_and_git_present():
    assert (REPO_ROOT / ".gitignore").is_file()
    assert (REPO_ROOT / ".git").is_dir()


def test_config_directory_still_contains_the_phase_0_acceptance_contract():
    # Phase-0-specific guard only: acceptance_contract.yaml must still exist
    # and must not have been removed by later work. This intentionally does
    # NOT assert config/ contains *only* this file - later phases (starting
    # with Phase 1's own domain_taxonomy.yaml / regulatory_decision_tree.yaml
    # / classification_contract.yaml) are expected to add further contract
    # files there. The stricter "exact expected file set for the current
    # phase" cleanliness check lives in each phase's own regression test
    # (see tests/test_phase_01_regression.py for the Phase 1 version) so this
    # Phase 0 test never needs editing again as later phases legitimately add
    # files.
    config_files = {p.name for p in CONFIG_DIR.glob("*.yaml")}
    assert "acceptance_contract.yaml" in config_files
