"""
Phase 0 tests: config/acceptance_contract.yaml - the machine-readable
acceptance contract required by the Phase 0 acceptance gate ("Every
mandatory PS capability has an owner, test and acceptance criterion").

Tests cover: file presence, YAML parsing, schema completeness, ID
uniqueness, valid owner-phase range, non-empty required fields, correct
handling of deferred capabilities, and rejection of malformed/incomplete/
duplicate synthetic contracts (synthetic fixtures only - no real project
facts are invented for these negative tests).
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from _contract_schema import ContractValidationError, validate_contract

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = REPO_ROOT / "config" / "acceptance_contract.yaml"

EXPECTED_CAPABILITY_COUNT = 24  # CAP-00 .. CAP-23, one per phase 0-23
EXPECTED_DEFERRED_COUNT = 9  # DEF-01 .. DEF-09


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def contract_raw_text() -> str:
    assert CONTRACT_PATH.is_file(), f"missing {CONTRACT_PATH}"
    return CONTRACT_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def contract_data(contract_raw_text: str) -> dict:
    return yaml.safe_load(contract_raw_text)


@pytest.fixture()
def valid_contract_copy(contract_data: dict) -> dict:
    """A deep copy safe for tests to mutate into deliberately-broken fixtures."""
    return copy.deepcopy(contract_data)


# ---------------------------------------------------------------------------
# 1. File exists / 2. YAML parses correctly
# ---------------------------------------------------------------------------


def test_acceptance_contract_file_exists():
    assert CONTRACT_PATH.is_file()
    assert CONTRACT_PATH.stat().st_size > 0


def test_acceptance_contract_yaml_parses_correctly(contract_raw_text: str):
    data = yaml.safe_load(contract_raw_text)
    assert isinstance(data, dict)


def test_acceptance_contract_passes_schema_validation(contract_data: dict):
    # Should not raise.
    validate_contract(contract_data)


# ---------------------------------------------------------------------------
# 3. Required top-level fields exist
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "key",
    ["project", "phase", "source_discipline_labels", "status_vocabulary", "mandatory_capabilities"],
)
def test_required_top_level_field_present(contract_data: dict, key: str):
    assert key in contract_data


def test_project_and_phase_identity(contract_data: dict):
    assert contract_data["project"]["id"] == "PS-26045"
    assert contract_data["project"]["name"] == "IP-SAKTI Sahayak"
    assert contract_data["phase"]["id"] == 0


def test_source_discipline_labels_match_the_seven_approved_labels(contract_data: dict):
    expected = {
        "[OFFICIAL PS]",
        "[OFFICIAL SOURCE]",
        "[EXTERNAL RESEARCH]",
        "[ENGINEERING RECOMMENDATION]",
        "[OUR ENHANCEMENT]",
        "[ASSUMPTION]",
        "[DEFERRED]",
    }
    assert set(contract_data["source_discipline_labels"]) == expected


# ---------------------------------------------------------------------------
# 4. Every capability has required fields
# ---------------------------------------------------------------------------


def test_every_capability_has_all_required_fields(contract_data: dict):
    required = {"id", "name", "owner_phase", "required_behavior", "test_requirement", "acceptance_criterion", "status"}
    for cap in contract_data["mandatory_capabilities"]:
        missing = required - set(cap.keys())
        assert not missing, f"capability {cap.get('id')} missing fields: {missing}"


def test_capability_count_matches_phase_count(contract_data: dict):
    assert len(contract_data["mandatory_capabilities"]) == EXPECTED_CAPABILITY_COUNT


# ---------------------------------------------------------------------------
# 5. Capability IDs are unique
# ---------------------------------------------------------------------------


def test_capability_ids_are_unique(contract_data: dict):
    ids = [cap["id"] for cap in contract_data["mandatory_capabilities"]]
    assert len(ids) == len(set(ids)), "duplicate capability IDs found in the real contract"


def test_capability_ids_follow_cap_nn_pattern_matching_owner_phase(contract_data: dict):
    for cap in contract_data["mandatory_capabilities"]:
        expected_id = f"CAP-{cap['owner_phase']:02d}"
        assert cap["id"] == expected_id, (
            f"capability id {cap['id']!r} does not match its owner_phase {cap['owner_phase']} "
            f"(expected {expected_id!r})"
        )


# ---------------------------------------------------------------------------
# 6. Owner phases are valid
# ---------------------------------------------------------------------------


def test_owner_phases_are_valid_and_cover_0_to_23_exactly_once(contract_data: dict):
    owner_phases = [cap["owner_phase"] for cap in contract_data["mandatory_capabilities"]]
    assert sorted(owner_phases) == list(range(24)), (
        "owner_phase values must cover every phase 0..23 exactly once"
    )


# ---------------------------------------------------------------------------
# 7. Acceptance criteria are non-empty / 8. Test requirements are non-empty
# ---------------------------------------------------------------------------


def test_all_acceptance_criteria_non_empty(contract_data: dict):
    for cap in contract_data["mandatory_capabilities"]:
        assert cap["acceptance_criterion"].strip(), f"{cap['id']} has an empty acceptance_criterion"


def test_all_test_requirements_non_empty(contract_data: dict):
    for cap in contract_data["mandatory_capabilities"]:
        assert cap["test_requirement"].strip(), f"{cap['id']} has an empty test_requirement"


def test_all_required_behaviors_non_empty(contract_data: dict):
    for cap in contract_data["mandatory_capabilities"]:
        assert cap["required_behavior"].strip(), f"{cap['id']} has an empty required_behavior"


# ---------------------------------------------------------------------------
# 9. No future phase is incorrectly marked complete
# ---------------------------------------------------------------------------


def test_no_capability_marked_implemented_or_validated(contract_data: dict):
    for cap in contract_data["mandatory_capabilities"]:
        assert cap["status"] not in {"IMPLEMENTED", "VALIDATED"}, (
            f"{cap['id']} is marked {cap['status']!r} but no phase has been implemented yet"
        )


def test_all_capabilities_currently_status_defined(contract_data: dict):
    # At the close of Phase 0, every capability's CONTRACT is defined but
    # none of the owning phases have been implemented, so all must read
    # DEFINED (not IN_PROGRESS/IMPLEMENTED/VALIDATED).
    for cap in contract_data["mandatory_capabilities"]:
        assert cap["status"] == "DEFINED", f"{cap['id']} unexpected status {cap['status']!r}"


# ---------------------------------------------------------------------------
# 10. Deferred capabilities are represented correctly
# ---------------------------------------------------------------------------


def test_deferred_technologies_present_and_well_formed(contract_data: dict):
    deferred = contract_data.get("deferred_technologies")
    assert deferred is not None and len(deferred) == EXPECTED_DEFERRED_COUNT
    ids = [item["id"] for item in deferred]
    assert len(ids) == len(set(ids)), "duplicate deferred_technologies ids"
    for item in deferred:
        assert item["name"].strip()


def test_deferred_technologies_do_not_overlap_mandatory_capability_ids(contract_data: dict):
    cap_ids = {cap["id"] for cap in contract_data["mandatory_capabilities"]}
    deferred_ids = {item["id"] for item in contract_data["deferred_technologies"]}
    assert cap_ids.isdisjoint(deferred_ids)


# ---------------------------------------------------------------------------
# 11. Malformed contract is rejected / 12. Missing required fields rejected /
# 13. Duplicate IDs rejected
# ---------------------------------------------------------------------------


def test_malformed_contract_root_not_a_mapping_is_rejected():
    with pytest.raises(ContractValidationError):
        validate_contract(["this", "is", "a", "list", "not", "a", "mapping"])


def test_malformed_contract_missing_top_level_key_is_rejected(valid_contract_copy: dict):
    del valid_contract_copy["mandatory_capabilities"]
    with pytest.raises(ContractValidationError):
        validate_contract(valid_contract_copy)


def test_missing_required_capability_field_is_rejected(valid_contract_copy: dict):
    # Synthetic fixture: remove acceptance_criterion from one real-looking
    # capability entry to prove the validator catches incompleteness.
    del valid_contract_copy["mandatory_capabilities"][0]["acceptance_criterion"]
    with pytest.raises(ContractValidationError):
        validate_contract(valid_contract_copy)


def test_empty_string_required_field_is_rejected(valid_contract_copy: dict):
    valid_contract_copy["mandatory_capabilities"][3]["test_requirement"] = "   "
    with pytest.raises(ContractValidationError):
        validate_contract(valid_contract_copy)


def test_duplicate_capability_ids_are_rejected(valid_contract_copy: dict):
    # Synthetic fixture: force two entries to share an id.
    valid_contract_copy["mandatory_capabilities"][1]["id"] = valid_contract_copy["mandatory_capabilities"][0]["id"]
    with pytest.raises(ContractValidationError):
        validate_contract(valid_contract_copy)


def test_owner_phase_out_of_range_is_rejected(valid_contract_copy: dict):
    valid_contract_copy["mandatory_capabilities"][0]["owner_phase"] = 99
    with pytest.raises(ContractValidationError):
        validate_contract(valid_contract_copy)


def test_owner_phase_non_integer_is_rejected(valid_contract_copy: dict):
    valid_contract_copy["mandatory_capabilities"][0]["owner_phase"] = "zero"
    with pytest.raises(ContractValidationError):
        validate_contract(valid_contract_copy)


def test_status_outside_vocabulary_is_rejected(valid_contract_copy: dict):
    valid_contract_copy["mandatory_capabilities"][0]["status"] = "TOTALLY_DONE"
    with pytest.raises(ContractValidationError):
        validate_contract(valid_contract_copy)


def test_status_implemented_is_rejected_even_if_in_vocabulary(valid_contract_copy: dict):
    # Prove the validator specifically forbids premature completion claims,
    # not just enforces vocabulary membership.
    valid_contract_copy["status_vocabulary"].append("IMPLEMENTED")
    valid_contract_copy["mandatory_capabilities"][0]["status"] = "IMPLEMENTED"
    with pytest.raises(ContractValidationError):
        validate_contract(valid_contract_copy)


def test_duplicate_deferred_ids_are_rejected(valid_contract_copy: dict):
    valid_contract_copy["deferred_technologies"][1]["id"] = valid_contract_copy["deferred_technologies"][0]["id"]
    with pytest.raises(ContractValidationError):
        validate_contract(valid_contract_copy)


def test_deferred_missing_name_is_rejected(valid_contract_copy: dict):
    del valid_contract_copy["deferred_technologies"][0]["name"]
    with pytest.raises(ContractValidationError):
        validate_contract(valid_contract_copy)


def test_empty_mandatory_capabilities_list_is_rejected(valid_contract_copy: dict):
    valid_contract_copy["mandatory_capabilities"] = []
    with pytest.raises(ContractValidationError):
        validate_contract(valid_contract_copy)


def test_capability_entry_not_a_mapping_is_rejected(valid_contract_copy: dict):
    valid_contract_copy["mandatory_capabilities"][0] = "CAP-00 as a bare string"
    with pytest.raises(ContractValidationError):
        validate_contract(valid_contract_copy)


# ---------------------------------------------------------------------------
# 14. Phase 0 contract is internally consistent
# ---------------------------------------------------------------------------


def test_phase_0_capability_acceptance_criterion_matches_master_reference_gate(contract_data: dict):
    cap_00 = next(c for c in contract_data["mandatory_capabilities"] if c["id"] == "CAP-00")
    assert cap_00["acceptance_criterion"] == (
        "Every mandatory PS capability has an owner, test, and acceptance criterion."
    )


def test_status_vocabulary_contains_defined(contract_data: dict):
    assert "DEFINED" in contract_data["status_vocabulary"]


def test_contract_is_deterministic_across_reloads(contract_raw_text: str):
    first = yaml.safe_load(contract_raw_text)
    second = yaml.safe_load(contract_raw_text)
    assert first == second
