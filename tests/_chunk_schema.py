"""
Phase 4 test-support module: schema validation for
config/chunking_contract.yaml and config/chunk_schema.yaml, mirroring
tests/_document_schema.py's Phase 3 pattern.

Test/validation infrastructure only. Not a test module itself (no test_
prefix) - pytest will not collect it.
"""

from __future__ import annotations

from _document_schema import APPROVED_SOURCE_LABELS

VALID_CHUNKING_STATES = frozenset({"CHUNKING_SUCCESS", "CHUNKING_PARTIAL", "CHUNKING_SKIPPED"})


class ChunkSchemaValidationError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ChunkSchemaValidationError(message)


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


def validate_chunk_schema(data) -> None:
    _require(isinstance(data, dict), "root must be a mapping/object")
    _require(
        isinstance(data.get("schema_version"), str) and data["schema_version"].strip(),
        "schema_version must be a non-empty string",
    )
    for key in ("chunking_states", "size_units", "chunking_result", "chunk"):
        _require(key in data, f"missing top-level key: {key}")

    _require(set(data["chunking_states"]) == VALID_CHUNKING_STATES, "chunking_states mismatch")

    for top in ("chunking_result", "chunk"):
        _require(isinstance(data[top], dict) and "fields" in data[top], f"{top} must define 'fields'")
        _check_fields(data[top]["fields"], f"{top}.fields")

    _check_safety_invariants(data, "chunk_schema")


def validate_chunking_contract(data) -> None:
    _require(isinstance(data, dict), "root must be a mapping/object")
    _require(
        isinstance(data.get("contract_version"), str) and data["contract_version"].strip(),
        "contract_version must be a non-empty string",
    )

    required_keys = (
        "chunking_states",
        "accepted_input_type",
        "size_unit",
        "default_max_chunk_size_chars",
        "chunk_warning_codes",
        "document_warning_codes",
        "output_requirements",
        "warning_requirements",
        "determinism_requirements",
        "safety_invariants",
    )
    missing = [k for k in required_keys if k not in data]
    _require(not missing, f"missing top-level keys: {missing}")

    _require(
        set(data["chunking_states"]) == VALID_CHUNKING_STATES,
        f"chunking_states must be exactly {sorted(VALID_CHUNKING_STATES)}, got {data['chunking_states']}",
    )
    _require(
        isinstance(data["default_max_chunk_size_chars"], int) and data["default_max_chunk_size_chars"] > 0,
        "default_max_chunk_size_chars must be a positive integer",
    )

    _check_safety_invariants(data, "chunking_contract")
