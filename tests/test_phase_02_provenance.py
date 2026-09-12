"""
Phase 2 tests: config/corpus_provenance_schema.yaml - the minimum
provenance contract every future corpus document must satisfy.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from _authority_matrix_schema import AuthorityMatrixValidationError, validate_provenance_schema

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "config" / "corpus_provenance_schema.yaml"

REQUIRED_CONCEPT_FIELDS = {
    "document_id",
    "source_family_id",
    "source_reference",
    "jurisdiction",
    "title",
    "document_type",
    "publication_date",
    "effective_date",
    "version",
    "retrieved_at",
    "content_hash",
    "provenance_status",
    "validation_status",
    "supersession_status",
    "admission_status",
    "restriction_reason",
    "notes",
}


@pytest.fixture(scope="module")
def raw_text() -> str:
    assert SCHEMA_PATH.is_file()
    return SCHEMA_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def schema_data(raw_text: str) -> dict:
    return yaml.safe_load(raw_text)


@pytest.fixture()
def valid_copy(schema_data: dict) -> dict:
    return copy.deepcopy(schema_data)


def test_schema_file_exists_and_nonempty():
    assert SCHEMA_PATH.stat().st_size > 0


def test_schema_yaml_parses_correctly(raw_text: str):
    data = yaml.safe_load(raw_text)
    assert isinstance(data, dict)


def test_schema_passes_validation(schema_data: dict):
    validate_provenance_schema(schema_data)  # should not raise


def test_schema_defines_every_required_concept_field(schema_data: dict):
    names = {f["name"] for f in schema_data["fields"]}
    missing = REQUIRED_CONCEPT_FIELDS - names
    assert not missing, f"corpus_provenance_schema.yaml is missing fields: {missing}"


def test_no_field_name_duplicated(schema_data: dict):
    names = [f["name"] for f in schema_data["fields"]]
    assert len(names) == len(set(names))


# ---------------------------------------------------------------------------
# Explicit-uncertainty requirements (never silently omit/default)
# ---------------------------------------------------------------------------


def test_version_known_and_effective_date_known_flags_exist_and_are_required(schema_data: dict):
    for name in ("version_known", "effective_date_known"):
        field = next(f for f in schema_data["fields"] if f["name"] == name)
        assert field["type"] == "boolean"
        assert field["required"] is True


def test_synthetic_field_is_required_boolean_defaulting_false(schema_data: dict):
    field = next(f for f in schema_data["fields"] if f["name"] == "synthetic")
    assert field["type"] == "boolean"
    assert field["required"] is True
    assert field.get("default") is False


def test_admission_status_enum_matches_corpus_lock_states(schema_data: dict):
    field = next(f for f in schema_data["fields"] if f["name"] == "admission_status")
    lock_data = yaml.safe_load((REPO_ROOT / "config" / "corpus_lock.yaml").read_text(encoding="utf-8"))
    assert set(field["allowed_values"]) == set(lock_data["admission_states"])


def test_validation_status_enum_matches_corpus_lock_required_validation_states(schema_data: dict):
    field = next(f for f in schema_data["fields"] if f["name"] == "validation_status")
    lock_data = yaml.safe_load((REPO_ROOT / "config" / "corpus_lock.yaml").read_text(encoding="utf-8"))
    assert set(field["allowed_values"]) == set(lock_data["required_validation_states"])


def test_supersession_status_never_defaults_to_current(schema_data: dict):
    field = next(f for f in schema_data["fields"] if f["name"] == "supersession_status")
    assert "UNKNOWN" in field["allowed_values"]
    assert "default" not in field  # no implicit default value at all


# ---------------------------------------------------------------------------
# Safety invariants
# ---------------------------------------------------------------------------


def test_safety_invariants_cover_synthetic_and_version_and_jurisdiction(schema_data: dict):
    rules_text = " ".join(inv["rule"] for inv in schema_data["safety_invariants"]).lower()
    assert "synthetic" in rules_text
    assert "version_known" in rules_text
    assert "jurisdiction" in rules_text


# ---------------------------------------------------------------------------
# Negative tests
# ---------------------------------------------------------------------------


def test_malformed_root_is_rejected():
    with pytest.raises(AuthorityMatrixValidationError):
        validate_provenance_schema(["not", "a", "mapping"])


def test_missing_fields_key_is_rejected(valid_copy: dict):
    del valid_copy["fields"]
    with pytest.raises(AuthorityMatrixValidationError):
        validate_provenance_schema(valid_copy)


def test_missing_document_identity_field_is_rejected(valid_copy: dict):
    # Negative test #6: missing document identity concept entirely.
    valid_copy["fields"] = [f for f in valid_copy["fields"] if f["name"] != "document_id"]
    with pytest.raises(AuthorityMatrixValidationError):
        validate_provenance_schema(valid_copy)


def test_missing_content_hash_field_is_rejected(valid_copy: dict):
    # Negative test #7: missing content hash concept entirely.
    valid_copy["fields"] = [f for f in valid_copy["fields"] if f["name"] != "content_hash"]
    with pytest.raises(AuthorityMatrixValidationError):
        validate_provenance_schema(valid_copy)


def test_missing_validation_status_concept_is_rejected(valid_copy: dict):
    # Negative test #8: missing validation status concept entirely.
    valid_copy["fields"] = [f for f in valid_copy["fields"] if f["name"] != "validation_status"]
    with pytest.raises(AuthorityMatrixValidationError):
        validate_provenance_schema(valid_copy)


def test_synthetic_field_not_boolean_is_rejected(valid_copy: dict):
    for f in valid_copy["fields"]:
        if f["name"] == "synthetic":
            f["type"] = "string"
    with pytest.raises(AuthorityMatrixValidationError):
        validate_provenance_schema(valid_copy)


def test_synthetic_field_not_required_is_rejected(valid_copy: dict):
    for f in valid_copy["fields"]:
        if f["name"] == "synthetic":
            f["required"] = False
    with pytest.raises(AuthorityMatrixValidationError):
        validate_provenance_schema(valid_copy)


def test_field_missing_type_is_rejected(valid_copy: dict):
    del valid_copy["fields"][0]["type"]
    with pytest.raises(AuthorityMatrixValidationError):
        validate_provenance_schema(valid_copy)


def test_duplicate_field_name_is_rejected(valid_copy: dict):
    valid_copy["fields"].append(dict(valid_copy["fields"][0]))
    with pytest.raises(AuthorityMatrixValidationError):
        validate_provenance_schema(valid_copy)


def test_missing_safety_invariants_is_rejected(valid_copy: dict):
    del valid_copy["safety_invariants"]
    with pytest.raises(AuthorityMatrixValidationError):
        validate_provenance_schema(valid_copy)


def test_duplicate_safety_invariant_id_is_rejected(valid_copy: dict):
    valid_copy["safety_invariants"][0]["id"] = "DUP"
    valid_copy["safety_invariants"].append(dict(valid_copy["safety_invariants"][0]))
    with pytest.raises(AuthorityMatrixValidationError):
        validate_provenance_schema(valid_copy)


# ---------------------------------------------------------------------------
# No fake example government documents
# ---------------------------------------------------------------------------


def test_schema_contains_no_example_document_data(raw_text: str):
    # The schema describes SHAPE only; it must not embed a worked example
    # that could be mistaken for a real government document record.
    lowered = raw_text.lower()
    for forbidden in ("gazette notification no.", "notification no. g.s.r", "example document:"):
        assert forbidden not in lowered
