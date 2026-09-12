"""
Phase 3 test-support module: schema validation for
config/document_structure_schema.yaml and
config/document_ingestion_contract.yaml.

Test/validation infrastructure only. Not a test module itself (no test_
prefix) - pytest will not collect it.
"""

from __future__ import annotations

APPROVED_SOURCE_LABELS = frozenset(
    {
        "[OFFICIAL PS]",
        "[OFFICIAL SOURCE]",
        "[EXTERNAL RESEARCH]",
        "[ENGINEERING RECOMMENDATION]",
        "[OUR ENHANCEMENT]",
        "[ASSUMPTION]",
        "[DEFERRED]",
    }
)

VALID_PIPELINE_STATES = frozenset(
    {
        "READY_FOR_INGESTION",
        "REJECTED_INPUT",
        "EXTRACTION_SUCCESS",
        "EXTRACTION_PARTIAL",
        "EXTRACTION_FAILED",
        "OCR_REQUIRED",
        "QUARANTINED",
    }
)


class DocumentSchemaValidationError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DocumentSchemaValidationError(message)


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
        if f["type"] == "object" and "fields" in f:
            _check_fields(f["fields"], f"{path}[{idx}].fields")


def validate_document_structure_schema(data) -> None:
    _require(isinstance(data, dict), "root must be a mapping/object")
    _require(
        isinstance(data.get("schema_version"), str) and data["schema_version"].strip(),
        "schema_version must be a non-empty string",
    )
    for key in ("detection_states", "block_types", "page_extraction_statuses", "table_extraction_statuses"):
        _require(key in data, f"missing top-level key: {key}")

    _require(set(data["detection_states"]) == {"DETECTED", "NOT_DETECTED", "UNKNOWN"}, "detection_states mismatch")

    for top in ("document", "page", "block"):
        _require(top in data, f"missing top-level key: {top}")
        _require(isinstance(data[top], dict) and "fields" in data[top], f"{top} must define 'fields'")
        _check_fields(data[top]["fields"], f"{top}.fields")

    _require("safety_invariants" in data, "missing top-level key: safety_invariants")
    invariants = data["safety_invariants"]
    _require(isinstance(invariants, list) and invariants, "safety_invariants must be a non-empty list")
    seen_ids = set()
    for idx, inv in enumerate(invariants):
        _require(isinstance(inv, dict), f"safety_invariants[{idx}] is not a mapping")
        _require(inv.get("id"), f"safety_invariants[{idx}] missing 'id'")
        _require(inv["id"] not in seen_ids, f"duplicate safety_invariant id: {inv['id']!r}")
        seen_ids.add(inv["id"])
        _require(inv.get("rule"), f"safety_invariants[{idx}] missing 'rule'")
        _require(
            inv.get("source_label") in APPROVED_SOURCE_LABELS,
            f"safety_invariants[{idx}] has unapproved source_label",
        )


def validate_document_ingestion_contract(data) -> None:
    _require(isinstance(data, dict), "root must be a mapping/object")
    _require(
        isinstance(data.get("contract_version"), str) and data["contract_version"].strip(),
        "contract_version must be a non-empty string",
    )

    required_keys = (
        "pipeline_states",
        "accepted_input_states",
        "accepted_document_types",
        "required_provenance_fields",
        "extraction_states",
        "structural_states",
        "failure_states",
        "quarantine_states",
        "output_requirements",
        "warning_requirements",
        "security_limits",
        "safety_invariants",
    )
    missing = [k for k in required_keys if k not in data]
    _require(not missing, f"missing top-level keys: {missing}")

    _require(
        set(data["pipeline_states"]) == VALID_PIPELINE_STATES,
        f"pipeline_states must be exactly {sorted(VALID_PIPELINE_STATES)}, got {data['pipeline_states']}",
    )
    _require(
        set(data["accepted_input_states"]).issubset({"ADMIT", "ADMIT_WITH_RESTRICTION"}),
        "accepted_input_states must be a subset of {ADMIT, ADMIT_WITH_RESTRICTION}",
    )
    _require(
        set(data["accepted_document_types"]) == {"TEXT", "HTML", "PDF"},
        "accepted_document_types must be exactly {TEXT, HTML, PDF}",
    )

    limits = data["security_limits"]
    _require(isinstance(limits, dict), "security_limits must be a mapping")
    _require(
        isinstance(limits.get("max_input_bytes"), int) and limits["max_input_bytes"] > 0,
        "security_limits.max_input_bytes must be a positive integer",
    )
    _require(
        isinstance(limits.get("allowed_extensions"), list) and limits["allowed_extensions"],
        "security_limits.allowed_extensions must be a non-empty list",
    )

    invariants = data["safety_invariants"]
    _require(isinstance(invariants, list) and invariants, "safety_invariants must be a non-empty list")
    seen_ids = set()
    for idx, inv in enumerate(invariants):
        _require(isinstance(inv, dict), f"safety_invariants[{idx}] is not a mapping")
        _require(inv.get("id"), f"safety_invariants[{idx}] missing 'id'")
        _require(inv["id"] not in seen_ids, f"duplicate safety_invariant id: {inv['id']!r}")
        seen_ids.add(inv["id"])
        _require(
            inv.get("source_label") in APPROVED_SOURCE_LABELS,
            f"safety_invariants[{idx}] has unapproved source_label",
        )
