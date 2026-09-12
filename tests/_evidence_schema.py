"""
Phase 8 test-support module: schema validation for
config/evidence_contract.yaml and config/evidence_schema.yaml, mirroring
tests/_hybrid_schema.py's Phase 7 pattern.

Test/validation infrastructure only. Not a test module itself (no test_
prefix) - pytest will not collect it.
"""

from __future__ import annotations

from _document_schema import APPROVED_SOURCE_LABELS


class EvidenceSchemaValidationError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceSchemaValidationError(message)


def _check_fields(field_list, path):
    _require(isinstance(field_list, list) and field_list, f"{path} must be a non-empty list")
    seen_names = set()
    for idx, f in enumerate(field_list):
        _require(isinstance(f, dict), f"{path}[{idx}] is not a mapping")
        _require(f.get("name"), f"{path}[{idx}] missing non-empty 'name'")
        _require(f["name"] not in seen_names, f"duplicate field name in {path}: {f['name']!r}")
        seen_names.add(f["name"])
        _require(f.get("type"), f"{path}[{idx}] (name={f.get('name')!r}) missing non-empty 'type'")
        _require(
            "required" in f and isinstance(f["required"], bool),
            f"{path}[{idx}] (name={f.get('name')!r}) missing boolean 'required'",
        )


def _check_safety_invariants(data, path):
    invariants = data.get("safety_invariants")
    _require(isinstance(invariants, list) and invariants, f"{path}.safety_invariants must be a non-empty list")
    seen_ids = set()
    for idx, inv in enumerate(invariants):
        _require(isinstance(inv, dict), f"{path}.safety_invariants[{idx}] is not a mapping")
        _require(inv.get("id"), f"{path}.safety_invariants[{idx}] missing 'id'")
        _require(inv["id"] not in seen_ids, f"duplicate safety_invariant id: {inv['id']!r}")
        seen_ids.add(inv["id"])
        _require(inv.get("rule"), f"{path}.safety_invariants[{idx}] missing 'rule'")
        _require(
            inv.get("source_label") in APPROVED_SOURCE_LABELS,
            f"{path}.safety_invariants[{idx}] has unapproved source_label",
        )


def validate_evidence_contract(data) -> None:
    _require(isinstance(data, dict), "root must be a mapping/object")
    _require(
        isinstance(data.get("contract_version"), str) and data["contract_version"].strip(),
        "contract_version must be a non-empty string",
    )

    required_keys = (
        "evidence_schema_version",
        "pack_schema_version",
        "evidence_types",
        "evidence_id_inputs",
        "pack_id_inputs",
        "accepted_candidate_types",
        "required_candidate_attributes",
        "default_max_evidence_items",
        "deduplication_policy",
        "ordering_policy",
        "output_requirements",
        "determinism_requirements",
        "safety_invariants",
    )
    missing = [k for k in required_keys if k not in data]
    _require(not missing, f"missing top-level keys: {missing}")

    _require(data["evidence_types"] == ["CHUNK"], "evidence_types must be exactly ['CHUNK']")
    _require(
        isinstance(data["default_max_evidence_items"], int) and data["default_max_evidence_items"] > 0,
        "default_max_evidence_items must be a positive integer",
    )

    _check_safety_invariants(data, "evidence_contract")


def validate_evidence_schema(data) -> None:
    _require(isinstance(data, dict), "root must be a mapping/object")
    _require(
        isinstance(data.get("schema_version"), str) and data["schema_version"].strip(),
        "schema_version must be a non-empty string",
    )
    for key in ("evidence", "retrieval_metadata", "version_info", "citation_target", "evidence_pack"):
        _require(key in data, f"missing top-level key: {key}")
        _require(isinstance(data[key], dict) and "fields" in data[key], f"{key} must define 'fields'")
        _check_fields(data[key]["fields"], f"{key}.fields")

    _check_safety_invariants(data, "evidence_schema")
