"""
Phase 5 test-support module: schema validation for
config/bm25_contract.yaml and config/retrieval_result_schema.yaml,
mirroring tests/_chunk_schema.py's Phase 4 pattern.

Test/validation infrastructure only. Not a test module itself (no test_
prefix) - pytest will not collect it.
"""

from __future__ import annotations

from _document_schema import APPROVED_SOURCE_LABELS


class Bm25SchemaValidationError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise Bm25SchemaValidationError(message)


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


def validate_bm25_contract(data) -> None:
    _require(isinstance(data, dict), "root must be a mapping/object")
    _require(
        isinstance(data.get("contract_version"), str) and data["contract_version"].strip(),
        "contract_version must be a non-empty string",
    )

    required_keys = (
        "algorithm",
        "default_parameters",
        "parameter_bounds",
        "tokenizer_policy_version",
        "size_unit",
        "accepted_input_type",
        "stopword_policy",
        "idf_formula",
        "output_requirements",
        "determinism_requirements",
        "safety_invariants",
    )
    missing = [k for k in required_keys if k not in data]
    _require(not missing, f"missing top-level keys: {missing}")

    params = data["default_parameters"]
    _require(isinstance(params, dict), "default_parameters must be a mapping")
    _require(isinstance(params.get("k1"), (int, float)) and params["k1"] >= 0, "default_parameters.k1 must be >= 0")
    _require(
        isinstance(params.get("b"), (int, float)) and 0.0 <= params["b"] <= 1.0,
        "default_parameters.b must be in [0.0, 1.0]",
    )

    _check_safety_invariants(data, "bm25_contract")


def validate_retrieval_result_schema(data) -> None:
    _require(isinstance(data, dict), "root must be a mapping/object")
    _require(
        isinstance(data.get("schema_version"), str) and data["schema_version"].strip(),
        "schema_version must be a non-empty string",
    )
    for key in ("retrieval_response", "retrieval_result"):
        _require(key in data, f"missing top-level key: {key}")
        _require(isinstance(data[key], dict) and "fields" in data[key], f"{key} must define 'fields'")
        _check_fields(data[key]["fields"], f"{key}.fields")

    _check_safety_invariants(data, "retrieval_result_schema")
