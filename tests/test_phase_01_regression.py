"""
Phase 1 tests: Phase 0 regression, repository cleanliness for the current
phase boundary, and phase-boundary audit (no functionality beyond Phase 1
was implemented).

Phase 0's own test files (test_phase_00_scope.py,
test_phase_00_acceptance_contract.py) already re-run automatically as part
of `pytest tests/ -v` and constitute the primary Phase 0 regression check.
This file adds Phase-1-specific regression/cleanliness checks that would be
inappropriate to bake into the Phase 0 test files themselves (per-phase
layering - see the comment in test_phase_00_scope.py).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
CONFIG_DIR = REPO_ROOT / "config"
SRC_DIR = REPO_ROOT / "src"

MASTER_REFERENCE_PDF = REPO_ROOT / "PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf"
MASTER_REFERENCE_HASH_FILE = DOCS_DIR / "_master_reference.sha256"

EXPECTED_CONFIG_FILES_THROUGH_PHASE_1 = {
    "acceptance_contract.yaml",  # Phase 0
    "domain_taxonomy.yaml",  # Phase 1
    "regulatory_decision_tree.yaml",  # Phase 1
    "classification_contract.yaml",  # Phase 1
}

# Same future-phase hints Phase 0 checked, plus Phase-1-adjacent terms that
# would indicate the real (Phase 11) classification engine was built early.
# "bm25", "faiss", "embeddings", and "reranker" intentionally removed:
# Phase 5, Phase 6, and Phase 7 have since been explicitly started and
# legitimately own those names (see tests/test_phase_02_regression.py).
FUTURE_IMPLEMENTATION_MODULE_HINTS = (
    "jurisdiction_firewall",
    "citation_validator",
    "confidence_engine",
    "formulation_classification_engine",
)


# ---------------------------------------------------------------------------
# Master Reference integrity (byte-for-byte unchanged)
# ---------------------------------------------------------------------------


def test_master_reference_pdf_still_byte_for_byte_unchanged():
    assert MASTER_REFERENCE_PDF.is_file()
    assert MASTER_REFERENCE_HASH_FILE.is_file()
    recorded_hash = MASTER_REFERENCE_HASH_FILE.read_text(encoding="utf-8").strip().split()[0]
    actual_hash = hashlib.sha256(MASTER_REFERENCE_PDF.read_bytes()).hexdigest()
    assert actual_hash == recorded_hash


# ---------------------------------------------------------------------------
# Phase 0 artifacts remain intact and compatible
# ---------------------------------------------------------------------------


def test_phase_00_scope_doc_still_present_and_intact():
    doc = DOCS_DIR / "PHASE_00_SCOPE_AND_ACCEPTANCE.md"
    assert doc.is_file()
    text = doc.read_text(encoding="utf-8")
    # Spot-check a few load-bearing phrases rather than a full hash, since
    # Phase 0's own test suite already exhaustively validates this file's
    # structure; this is a lightweight "did Phase 1 corrupt it" tripwire.
    assert "14. Phase Boundary" in text
    assert "Every mandatory PS capability has an owner, test, and acceptance criterion." in text


def test_acceptance_contract_yaml_still_valid_and_phase_0_untouched():
    contract = yaml.safe_load(
        (CONFIG_DIR / "acceptance_contract.yaml").read_text(encoding="utf-8")
    )
    assert contract["phase"]["id"] == 0
    cap_00 = next(c for c in contract["mandatory_capabilities"] if c["id"] == "CAP-00")
    assert cap_00["status"] == "DEFINED"
    cap_01 = next(c for c in contract["mandatory_capabilities"] if c["id"] == "CAP-01")
    assert cap_01["owner_phase"] == 1  # unchanged mapping from Phase 0


def test_phase_tracker_phase_0_remains_done():
    # Own-phase-only check (permanently valid, never needs editing as later
    # phases start). The general "no phase is skipped ahead" invariant is
    # covered permanently by test_phase_00_scope.py::
    # test_phase_tracker_no_phase_is_skipped_ahead, which re-runs every
    # time `pytest tests/` runs - no per-phase downstream range check is
    # duplicated here anymore (an earlier version of this test hardcoded
    # "phases 2-23 must be NOT STARTED", which went stale the moment
    # Phase 2 legitimately started; see that test's docstring for why the
    # contiguous-prefix invariant replaced range-based checks project-wide).
    text = (DOCS_DIR / "PHASE_TRACKER.md").read_text(encoding="utf-8")
    pattern = re.compile(r"^## Phase (\d+) .*?\n- \*\*Status:\*\* (.+)$", re.MULTILINE)
    statuses = {int(m.group(1)): m.group(2).strip() for m in pattern.finditer(text)}

    assert set(statuses.keys()) == set(range(24))
    assert statuses[0] != "NOT STARTED", "Phase 0 status must remain recorded as done, not reverted"
    assert statuses[1] != "NOT STARTED", "Phase 1 tracker entry was not updated"


# ---------------------------------------------------------------------------
# Repository cleanliness for the Phase-0-through-Phase-1 boundary
# ---------------------------------------------------------------------------


def test_config_directory_still_contains_the_phase_0_and_1_files():
    # Narrowed to a subset check for the same reason as
    # test_phase_00_scope.py's config test: Phase 2 legitimately adds its
    # own YAML contracts to config/. The stricter "exact set for the
    # current phase" check lives in tests/test_phase_02_regression.py.
    actual = {p.name for p in CONFIG_DIR.glob("*.yaml")}
    assert EXPECTED_CONFIG_FILES_THROUGH_PHASE_1.issubset(actual), (
        f"config/ is missing Phase 0/1 files: {EXPECTED_CONFIG_FILES_THROUGH_PHASE_1 - actual}"
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


def test_no_future_phase_module_names_present_anywhere():
    candidate_files = [f for f in REPO_ROOT.rglob("*.py") if ".git" not in f.parts]
    lowered_names = [f.name.lower() for f in candidate_files]
    for hint in FUTURE_IMPLEMENTATION_MODULE_HINTS:
        matches = [n for n in lowered_names if hint in n]
        assert matches == [], f"found future-phase implementation module(s) matching {hint!r}: {matches}"


def test_decision_tree_reference_impl_is_test_support_only_not_production():
    # Structural guard: the reference evaluator must live under tests/ (not
    # src/), confirming it is test-support infrastructure and not being
    # mistaken for / substituted as the Phase 11 production engine.
    helper = REPO_ROOT / "tests" / "_decision_tree_reference_impl.py"
    assert helper.is_file()
    assert not (SRC_DIR / "_decision_tree_reference_impl.py").exists()
    text = helper.read_text(encoding="utf-8")
    assert "NOT the Phase 11" in text


def test_no_new_heavyweight_dependency_declared_in_phase_1():
    # "faiss"/"sentence-transformers" intentionally removed: Phase 6 has
    # since been explicitly started and legitimately declares them (see
    # tests/test_phase_02_regression.py for the identical reasoning).
    #
    # Checks actual declared package names only (non-comment requirement
    # lines) - a raw substring search over the whole file text would
    # misfire on a later phase's own justification comment merely
    # discussing/naming a forbidden package or model (e.g. Phase 6's own
    # comment explaining sentence-transformers "runs BGE-M3" mentions
    # "bge-m3" in prose without declaring any package by that name).
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
    req_dev_raw = (REPO_ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
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
    assert not (REPO_ROOT / "requirements.txt").exists()
