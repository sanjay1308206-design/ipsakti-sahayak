"""
Phase 1 tests: config/classification_contract.yaml - the output schema
that a future classification engine (Phase 11) must conform to.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from _taxonomy_schema import TaxonomyValidationError, validate_classification_contract

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = REPO_ROOT / "config" / "classification_contract.yaml"

REQUIRED_TOP_LEVEL_FIELD_NAMES = {
    "input_id",
    "user_intent",
    "formulation_classification",
    "regulatory_question_type",
    "jurisdiction_input",
    "evidence_state",
    "classification_state",
    "reason_codes",
    "explanation",
    "requires_evidence",
    "requires_escalation",
    "basis",
    "disclaimer",
    "provenance",
}


@pytest.fixture(scope="module")
def raw_text() -> str:
    assert CONTRACT_PATH.is_file()
    return CONTRACT_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def contract_data(raw_text: str) -> dict:
    return yaml.safe_load(raw_text)


@pytest.fixture()
def valid_copy(contract_data: dict) -> dict:
    return copy.deepcopy(contract_data)


def test_contract_file_exists_and_nonempty():
    assert CONTRACT_PATH.stat().st_size > 0


def test_contract_yaml_parses_correctly(raw_text: str):
    data = yaml.safe_load(raw_text)
    assert isinstance(data, dict)


def test_contract_passes_schema_validation(contract_data: dict):
    validate_classification_contract(contract_data)  # should not raise


def test_contract_defines_every_required_top_level_field(contract_data: dict):
    names = {f["name"] for f in contract_data["fields"]}
    missing = REQUIRED_TOP_LEVEL_FIELD_NAMES - names
    assert not missing, f"classification_contract.yaml is missing fields: {missing}"


def test_formulation_classification_has_required_subfields(contract_data: dict):
    formulation = next(f for f in contract_data["fields"] if f["name"] == "formulation_classification")
    sub_names = {f["name"] for f in formulation["fields"]}
    assert sub_names == {"regulatory_track", "ip_protection_category", "abs_tk_relation"}


def test_provenance_has_required_subfields(contract_data: dict):
    provenance = next(f for f in contract_data["fields"] if f["name"] == "provenance")
    sub_names = {f["name"] for f in provenance["fields"]}
    assert sub_names == {"taxonomy_version", "decision_tree_version", "contract_version"}


# ---------------------------------------------------------------------------
# Safety: no legal-certainty claims possible
# ---------------------------------------------------------------------------


def test_disclaimer_field_is_required_with_nonempty_constant(contract_data: dict):
    disclaimer = next(f for f in contract_data["fields"] if f["name"] == "disclaimer")
    assert disclaimer["required"] is True
    assert disclaimer["constant"].strip()
    assert "not legal advice" in disclaimer["constant"].lower()


def test_no_field_asserts_legal_certainty(contract_data: dict):
    def _walk(fields):
        for f in fields:
            yield f["name"].lower()
            if f.get("type") == "object" and "fields" in f:
                yield from _walk(f["fields"])

    forbidden_fragments = ("legally_certain", "is_legally_valid", "legal_determination")
    all_names = list(_walk(contract_data["fields"]))
    for frag in forbidden_fragments:
        offenders = [n for n in all_names if frag in n]
        assert offenders == [], f"forbidden legal-certainty field found: {offenders}"


def test_safety_invariants_cover_required_topics(contract_data: dict):
    rules_text = " ".join(inv["rule"] for inv in contract_data["safety_invariants"]).lower()
    assert "disclaimer" in rules_text
    assert "legal" in rules_text
    assert "needs_evidence" in rules_text.replace(" ", "_") or "needs_evidence" in rules_text
    assert "ambiguous" in rules_text


def test_every_safety_invariant_has_a_source_label(contract_data: dict):
    approved = {
        "[OFFICIAL PS]",
        "[OFFICIAL SOURCE]",
        "[EXTERNAL RESEARCH]",
        "[ENGINEERING RECOMMENDATION]",
        "[OUR ENHANCEMENT]",
        "[ASSUMPTION]",
        "[DEFERRED]",
    }
    for inv in contract_data["safety_invariants"]:
        assert inv["source_label"] in approved


# ---------------------------------------------------------------------------
# Negative tests
# ---------------------------------------------------------------------------


def test_malformed_contract_root_is_rejected():
    with pytest.raises(TaxonomyValidationError):
        validate_classification_contract(["not", "a", "mapping"])


def test_missing_fields_key_is_rejected(valid_copy: dict):
    del valid_copy["fields"]
    with pytest.raises(TaxonomyValidationError):
        validate_classification_contract(valid_copy)


def test_missing_disclaimer_field_is_rejected(valid_copy: dict):
    valid_copy["fields"] = [f for f in valid_copy["fields"] if f["name"] != "disclaimer"]
    with pytest.raises(TaxonomyValidationError):
        validate_classification_contract(valid_copy)


def test_disclaimer_without_constant_is_rejected(valid_copy: dict):
    for f in valid_copy["fields"]:
        if f["name"] == "disclaimer":
            f["constant"] = ""
    with pytest.raises(TaxonomyValidationError):
        validate_classification_contract(valid_copy)


def test_field_missing_type_is_rejected(valid_copy: dict):
    del valid_copy["fields"][0]["type"]
    with pytest.raises(TaxonomyValidationError):
        validate_classification_contract(valid_copy)


def test_injecting_a_legal_certainty_field_is_rejected(valid_copy: dict):
    # Synthetic fixture proving the schema validator itself would catch an
    # attempt to represent an uncertain case as legally certain (negative
    # test #11), if such a field were ever added.
    valid_copy["fields"].append(
        {
            "name": "is_legally_valid",
            "type": "boolean",
            "required": False,
            "description": "SYNTHETIC FIXTURE - must be rejected by the validator.",
            "source_label": "[ASSUMPTION]",
        }
    )
    with pytest.raises(TaxonomyValidationError):
        validate_classification_contract(valid_copy)


def test_duplicate_safety_invariant_id_is_rejected(valid_copy: dict):
    valid_copy["safety_invariants"][1]["id"] = valid_copy["safety_invariants"][0]["id"]
    with pytest.raises(TaxonomyValidationError):
        validate_classification_contract(valid_copy)


def test_safety_invariant_missing_source_label_is_rejected(valid_copy: dict):
    del valid_copy["safety_invariants"][0]["source_label"]
    with pytest.raises(TaxonomyValidationError):
        validate_classification_contract(valid_copy)
