"""
Phase 2 tests: docs/PHASE_02_CORPUS_ADMISSION_POLICY.md,
docs/PHASE_02_SOURCE_CONFLICT_POLICY.md, config/corpus_lock.yaml, and the
deterministic admission-policy reference evaluator
(tests/_admission_policy_reference_impl.py).
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from _admission_policy_reference_impl import ProvenanceRecord, evaluate_admission
from _authority_matrix_schema import AuthorityMatrixValidationError, validate_corpus_lock

REPO_ROOT = Path(__file__).resolve().parent.parent
ADMISSION_DOC_PATH = REPO_ROOT / "docs" / "PHASE_02_CORPUS_ADMISSION_POLICY.md"
CONFLICT_DOC_PATH = REPO_ROOT / "docs" / "PHASE_02_SOURCE_CONFLICT_POLICY.md"
LOCK_YAML_PATH = REPO_ROOT / "config" / "corpus_lock.yaml"
AUTHORITY_YAML_PATH = REPO_ROOT / "config" / "authority_matrix.yaml"

VALID_ADMISSION_STATES = {"ADMIT", "ADMIT_WITH_RESTRICTION", "HOLD_FOR_VALIDATION", "REJECT", "SUPERSEDED"}

KNOWN_SOURCE_FAMILY_IDS = frozenset(
    {"SF-01", "SF-02", "SF-03", "SF-04", "SF-05", "SF-06", "SF-07"}
)  # SF-08 (Bhashini) intentionally excluded - never a document source
SOURCE_FAMILY_JURISDICTIONS = {
    "SF-01": "INDIA",
    "SF-02": "INDIA",
    "SF-03": "INDIA",
    "SF-04": "INDIA",
    "SF-05": "INDIA",
    "SF-06": "INTERNATIONAL",
    "SF-07": "INDIA",
}


def _record(**overrides) -> ProvenanceRecord:
    defaults = dict(
        synthetic=True,
        source_family_id="SF-01",
        jurisdiction="INDIA",
        document_id="SYNTHETIC-DOC-0001",
        content_hash="deadbeef" * 8,
        validation_status="VALIDATED",
        supersession_status="CURRENT",
        version_known=True,
        effective_date_known=True,
        conflict_status="NONE",
        known_conflicting_with=[],
    )
    defaults.update(overrides)
    return ProvenanceRecord(**defaults)


def _evaluate(**overrides):
    return evaluate_admission(
        _record(**overrides), KNOWN_SOURCE_FAMILY_IDS, SOURCE_FAMILY_JURISDICTIONS
    )


# ---------------------------------------------------------------------------
# Document structure
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def admission_doc_text() -> str:
    assert ADMISSION_DOC_PATH.is_file()
    return ADMISSION_DOC_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def conflict_doc_text() -> str:
    assert CONFLICT_DOC_PATH.is_file()
    return CONFLICT_DOC_PATH.read_text(encoding="utf-8")


def test_admission_doc_exists_and_nonempty():
    assert ADMISSION_DOC_PATH.stat().st_size > 0


def test_conflict_doc_exists_and_nonempty():
    assert CONFLICT_DOC_PATH.stat().st_size > 0


@pytest.mark.parametrize("state", sorted(VALID_ADMISSION_STATES))
def test_admission_doc_defines_every_state(admission_doc_text: str, state: str):
    assert state in admission_doc_text


def test_admission_doc_declares_no_ingestion(admission_doc_text: str):
    lowered = admission_doc_text.lower()
    assert "no document is downloaded" in lowered or "no real document is evaluated" in lowered


def test_conflict_doc_declares_no_invented_hierarchy(conflict_doc_text: str):
    lowered = conflict_doc_text.lower()
    assert "does not invent such a hierarchy" in lowered or "no invented legal hierarchy" in lowered


def test_conflict_doc_forbids_llm_choosing_convincing_document(conflict_doc_text: str):
    lowered = conflict_doc_text.lower()
    assert "never resolve" in lowered and "convincing" in lowered


# ---------------------------------------------------------------------------
# corpus_lock.yaml schema validation
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def lock_raw_text() -> str:
    return LOCK_YAML_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def lock_data(lock_raw_text: str) -> dict:
    return yaml.safe_load(lock_raw_text)


@pytest.fixture()
def valid_lock_copy(lock_data: dict) -> dict:
    return copy.deepcopy(lock_data)


def test_lock_yaml_exists_and_parses(lock_raw_text: str):
    data = yaml.safe_load(lock_raw_text)
    assert isinstance(data, dict)


def test_lock_passes_schema_validation(lock_data: dict):
    validate_corpus_lock(lock_data)  # should not raise


def test_lock_admission_states_match_evaluator_states(lock_data: dict):
    assert set(lock_data["admission_states"]) == VALID_ADMISSION_STATES


def test_lock_excludes_bhashini_from_permitted_source_families(lock_data: dict):
    assert "SF-08" not in lock_data["permitted_source_families"]
    assert "SF-08" in lock_data["registered_service_adapters"]


def test_lock_permitted_source_families_are_subset_of_authority_matrix():
    authority = yaml.safe_load(AUTHORITY_YAML_PATH.read_text(encoding="utf-8"))
    lock = yaml.safe_load(LOCK_YAML_PATH.read_text(encoding="utf-8"))
    all_ids = {f["source_family_id"] for f in authority["source_families"]}
    assert set(lock["permitted_source_families"]).issubset(all_ids)


def test_lock_expansion_policy_requires_explicit_review(lock_data: dict):
    lowered = lock_data["expansion_policy"].lower()
    assert "explicit" in lowered and "review" in lowered


def test_lock_prohibited_source_classes_cover_required_categories(lock_data: dict):
    names = {psc["name"] for psc in lock_data["prohibited_source_classes"]}
    for expected in (
        "SEARCH_ENGINE",
        "BLOG_OR_COMMERCIAL_LEGAL_SITE",
        "ENCYCLOPEDIA_OR_WIKI",
        "SOCIAL_MEDIA",
        "UNVETTED_WEBPAGE",
        "UNREGISTERED_SOURCE_FAMILY",
    ):
        assert expected in names


# ---------------------------------------------------------------------------
# Reference evaluator: one behavioral test per rule (positive cases)
# ---------------------------------------------------------------------------


def test_a1_unknown_source_family():
    result = _evaluate(source_family_id="SF-99")
    assert result.admission_status == "REJECT"
    assert result.rule_id == "A1"


def test_a2_unknown_jurisdiction():
    result = _evaluate(jurisdiction="MARS")
    assert result.admission_status == "REJECT"
    assert result.rule_id == "A2"


def test_a3_jurisdiction_mismatch_international_source_in_india_corpus():
    # Negative test #11: international source placed into INDIA corpus.
    result = _evaluate(source_family_id="SF-06", jurisdiction="INDIA")
    assert result.admission_status == "REJECT"
    assert result.rule_id == "A3"


def test_a3_jurisdiction_mismatch_india_source_in_international_corpus():
    # Negative test #12: INDIA source placed into INTERNATIONAL corpus.
    result = _evaluate(source_family_id="SF-01", jurisdiction="INTERNATIONAL")
    assert result.admission_status == "REJECT"
    assert result.rule_id == "A3"


def test_a4_missing_document_identity():
    result = _evaluate(document_id="")
    assert result.admission_status == "HOLD_FOR_VALIDATION"
    assert result.rule_id == "A4"


def test_a5_missing_content_hash():
    result = _evaluate(content_hash="")
    assert result.admission_status == "HOLD_FOR_VALIDATION"
    assert result.rule_id == "A5"


def test_a6_missing_validation_status():
    result = _evaluate(validation_status="UNVALIDATED")
    assert result.admission_status == "HOLD_FOR_VALIDATION"
    assert result.rule_id == "A6"


def test_a7_superseded_document_never_readmitted_as_current():
    # Negative test #13: superseded document incorrectly marked current
    # without validation - the evaluator must always demote to SUPERSEDED.
    result = _evaluate(supersession_status="SUPERSEDED")
    assert result.admission_status == "SUPERSEDED"
    assert result.rule_id == "A7"


def test_a8_unresolved_conflict():
    result = _evaluate(conflict_status="CONFLICTING")
    assert result.admission_status == "HOLD_FOR_VALIDATION"
    assert result.rule_id == "A8"


def test_a9_conflicting_evidence_without_conflict_status():
    # Negative test #14: conflicting evidence without conflict status.
    result = _evaluate(conflict_status=None, known_conflicting_with=["SYNTHETIC-DOC-0002"])
    assert result.admission_status == "HOLD_FOR_VALIDATION"
    assert result.rule_id == "A9"


def test_a10_missing_version_never_silently_treated_as_current():
    # Negative test #15: missing version information being silently
    # treated as current - must cap at ADMIT_WITH_RESTRICTION, never ADMIT.
    result = _evaluate(version_known=False, effective_date_known=False)
    assert result.admission_status == "ADMIT_WITH_RESTRICTION"
    assert result.rule_id == "A10"


def test_a10_partial_version_knowledge_does_not_trigger_restriction():
    # Only when BOTH version and effective_date are unknown does A10 fire.
    result = _evaluate(version_known=True, effective_date_known=False)
    assert result.rule_id != "A10"


def test_a11_supersession_status_unknown():
    result = _evaluate(supersession_status="UNKNOWN")
    assert result.admission_status == "ADMIT_WITH_RESTRICTION"
    assert result.rule_id == "A11"


def test_a12_default_admit_when_everything_clean():
    result = _evaluate()
    assert result.admission_status == "ADMIT"
    assert result.rule_id == "A12"


# ---------------------------------------------------------------------------
# Rule priority / ordering
# ---------------------------------------------------------------------------


def test_rule_priority_unknown_family_beats_everything_else():
    result = _evaluate(source_family_id="SF-99", document_id="", content_hash="")
    assert result.rule_id == "A1"


def test_every_evaluation_result_is_a_valid_admission_state():
    scenarios = [
        dict(source_family_id="SF-99"),
        dict(jurisdiction="MARS"),
        dict(source_family_id="SF-06", jurisdiction="INDIA"),
        dict(document_id=""),
        dict(content_hash=""),
        dict(validation_status="UNVALIDATED"),
        dict(supersession_status="SUPERSEDED"),
        dict(conflict_status="CONFLICTING"),
        dict(conflict_status=None, known_conflicting_with=["X"]),
        dict(version_known=False, effective_date_known=False),
        dict(supersession_status="UNKNOWN"),
        dict(),
    ]
    for kwargs in scenarios:
        result = _evaluate(**kwargs)
        assert result.admission_status in VALID_ADMISSION_STATES


# ---------------------------------------------------------------------------
# Synthetic-fixture discipline (negative test #16)
# ---------------------------------------------------------------------------


def test_evaluator_refuses_non_synthetic_records():
    non_synthetic = ProvenanceRecord(
        synthetic=False,  # would represent a "real" document
        source_family_id="SF-01",
        jurisdiction="INDIA",
        document_id="SOME-DOC",
        content_hash="abc123",
        validation_status="VALIDATED",
        supersession_status="CURRENT",
        version_known=True,
        effective_date_known=True,
    )
    with pytest.raises(AssertionError):
        evaluate_admission(non_synthetic, KNOWN_SOURCE_FAMILY_IDS, SOURCE_FAMILY_JURISDICTIONS)


def test_synthetic_fixtures_in_this_test_module_are_clearly_marked():
    # Structural self-check: every record built by _record() in this file
    # sets synthetic=True (see _record()'s defaults) and uses an id/hash
    # that is obviously not a real government document reference.
    record = _record()
    assert record.synthetic is True
    assert record.document_id.startswith("SYNTHETIC-")


# ---------------------------------------------------------------------------
# Negative tests for corpus_lock.yaml schema
# ---------------------------------------------------------------------------


def test_malformed_lock_root_is_rejected():
    with pytest.raises(AuthorityMatrixValidationError):
        validate_corpus_lock(["not", "a", "mapping"])


def test_lock_missing_top_level_key_is_rejected(valid_lock_copy: dict):
    del valid_lock_copy["prohibited_source_classes"]
    with pytest.raises(AuthorityMatrixValidationError):
        validate_corpus_lock(valid_lock_copy)


def test_lock_invalid_admission_state_set_is_rejected(valid_lock_copy: dict):
    valid_lock_copy["admission_states"] = ["ADMIT", "MAYBE"]
    with pytest.raises(AuthorityMatrixValidationError):
        validate_corpus_lock(valid_lock_copy)


def test_lock_duplicate_permitted_source_family_is_rejected(valid_lock_copy: dict):
    valid_lock_copy["permitted_source_families"].append(valid_lock_copy["permitted_source_families"][0])
    with pytest.raises(AuthorityMatrixValidationError):
        validate_corpus_lock(valid_lock_copy)


def test_lock_family_cannot_be_both_permitted_and_service_adapter(valid_lock_copy: dict):
    valid_lock_copy["registered_service_adapters"].append(valid_lock_copy["permitted_source_families"][0])
    with pytest.raises(AuthorityMatrixValidationError):
        validate_corpus_lock(valid_lock_copy)


def test_lock_duplicate_prohibited_source_class_id_is_rejected(valid_lock_copy: dict):
    valid_lock_copy["prohibited_source_classes"][1]["id"] = (
        valid_lock_copy["prohibited_source_classes"][0]["id"]
    )
    with pytest.raises(AuthorityMatrixValidationError):
        validate_corpus_lock(valid_lock_copy)


def test_lock_empty_expansion_policy_is_rejected(valid_lock_copy: dict):
    valid_lock_copy["expansion_policy"] = "   "
    with pytest.raises(AuthorityMatrixValidationError):
        validate_corpus_lock(valid_lock_copy)
