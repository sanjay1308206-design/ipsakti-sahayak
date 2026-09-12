"""
Phase 2 test-support module: schema validation for
config/authority_matrix.yaml, config/corpus_provenance_schema.yaml, and
config/corpus_lock.yaml.

Test/validation infrastructure only - not application implementation, not
ingestion. Not a test module itself (no test_ prefix) - pytest will not
collect it.
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

REQUIRED_SOURCE_FAMILY_FIELDS = (
    "source_family_id",
    "source_family_name",
    "authority_tier",
    "authority_role",
    "jurisdiction_scope",
    "regulatory_domains",
    "supported_question_types",
    "allowed_document_types",
    "provenance_requirements",
    "version_requirements",
    "validation_requirements",
    "corpus_admission_status",
    "corpus_role",
    "conflict_policy",
    "limitations",
    "source_label",
)

VALID_ADMISSION_STATES = frozenset(
    {"ADMIT", "ADMIT_WITH_RESTRICTION", "HOLD_FOR_VALIDATION", "REJECT", "SUPERSEDED"}
)


class AuthorityMatrixValidationError(ValueError):
    """Raised when a Phase 2 config document (or a candidate document) is malformed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AuthorityMatrixValidationError(message)


# ---------------------------------------------------------------------------
# authority_matrix.yaml
# ---------------------------------------------------------------------------


def validate_authority_matrix(data) -> None:
    _require(isinstance(data, dict), "root must be a mapping/object")
    _require(
        isinstance(data.get("authority_matrix_version"), str)
        and data["authority_matrix_version"].strip(),
        "authority_matrix_version must be a non-empty string",
    )

    for key in ("source_families", "category_groupings", "valid_jurisdictions"):
        _require(key in data, f"missing top-level key: {key}")

    families = data["source_families"]
    _require(isinstance(families, list) and families, "source_families must be a non-empty list")

    seen_ids: set[str] = set()
    for idx, fam in enumerate(families):
        _require(isinstance(fam, dict), f"source_families[{idx}] is not a mapping")
        missing = [f for f in REQUIRED_SOURCE_FAMILY_FIELDS if f not in fam]
        _require(
            not missing,
            f"source_families[{idx}] (id={fam.get('source_family_id')!r}) missing fields: {missing}",
        )

        fam_id = fam["source_family_id"]
        _require(
            isinstance(fam_id, str) and fam_id.strip(),
            f"source_families[{idx}] has empty/invalid source_family_id",
        )
        _require(fam_id not in seen_ids, f"duplicate source_family_id: {fam_id!r}")
        seen_ids.add(fam_id)

        _require(
            fam["source_label"] in APPROVED_SOURCE_LABELS,
            f"{fam_id} has unapproved source_label {fam['source_label']!r}",
        )
        _require(
            fam["jurisdiction_scope"] in data["valid_jurisdictions"],
            f"{fam_id} has jurisdiction_scope {fam['jurisdiction_scope']!r} not in valid_jurisdictions",
        )
        _require(
            isinstance(fam["regulatory_domains"], list),
            f"{fam_id} regulatory_domains must be a list",
        )
        _require(
            isinstance(fam["supported_question_types"], list),
            f"{fam_id} supported_question_types must be a list",
        )
        _require(
            isinstance(fam["limitations"], list),
            f"{fam_id} limitations must be a list",
        )
        _require(
            isinstance(fam["conflict_policy"], dict) and fam["conflict_policy"].get("policy_reference"),
            f"{fam_id} conflict_policy must be a mapping with a non-empty policy_reference",
        )

    groupings = data["category_groupings"]
    _require(isinstance(groupings, dict) and groupings, "category_groupings must be a non-empty mapping")
    all_grouped_ids = {sf_id for ids in groupings.values() for sf_id in ids}
    _require(
        all_grouped_ids.issubset(seen_ids),
        f"category_groupings references unknown source_family_id(s): {all_grouped_ids - seen_ids}",
    )


# ---------------------------------------------------------------------------
# corpus_provenance_schema.yaml
# ---------------------------------------------------------------------------


def validate_provenance_schema(data) -> None:
    _require(isinstance(data, dict), "root must be a mapping/object")
    _require(
        isinstance(data.get("schema_version"), str) and data["schema_version"].strip(),
        "schema_version must be a non-empty string",
    )
    _require("fields" in data, "missing top-level key: fields")

    fields = data["fields"]
    _require(isinstance(fields, list) and fields, "fields must be a non-empty list")

    seen_names: set[str] = set()
    for idx, f in enumerate(fields):
        _require(isinstance(f, dict), f"fields[{idx}] is not a mapping")
        _require(f.get("name"), f"fields[{idx}] missing non-empty 'name'")
        _require(f.get("type"), f"fields[{idx}] (name={f.get('name')!r}) missing non-empty 'type'")
        _require(
            "required" in f and isinstance(f["required"], bool),
            f"fields[{idx}] (name={f.get('name')!r}) missing boolean 'required'",
        )
        _require(f["name"] not in seen_names, f"duplicate field name: {f['name']!r}")
        seen_names.add(f["name"])

    required_field_names = {
        "document_id",
        "source_family_id",
        "jurisdiction",
        "content_hash",
        "validation_status",
        "synthetic",
    }
    _require(
        required_field_names.issubset(seen_names),
        f"provenance schema missing required concept fields: {required_field_names - seen_names}",
    )

    synthetic_field = next(f for f in fields if f["name"] == "synthetic")
    _require(synthetic_field["type"] == "boolean", "'synthetic' field must be boolean")
    _require(synthetic_field["required"] is True, "'synthetic' field must be required")

    _require("safety_invariants" in data, "missing top-level key: safety_invariants")
    invariants = data["safety_invariants"]
    _require(isinstance(invariants, list) and invariants, "safety_invariants must be a non-empty list")
    seen_inv_ids: set[str] = set()
    for idx, inv in enumerate(invariants):
        _require(isinstance(inv, dict), f"safety_invariants[{idx}] is not a mapping")
        _require(inv.get("id"), f"safety_invariants[{idx}] missing 'id'")
        _require(inv["id"] not in seen_inv_ids, f"duplicate safety_invariant id: {inv['id']!r}")
        seen_inv_ids.add(inv["id"])
        _require(inv.get("rule"), f"safety_invariants[{idx}] missing 'rule'")
        _require(
            inv.get("source_label") in APPROVED_SOURCE_LABELS,
            f"safety_invariants[{idx}] has unapproved source_label",
        )


# ---------------------------------------------------------------------------
# corpus_lock.yaml
# ---------------------------------------------------------------------------


def validate_corpus_lock(data) -> None:
    _require(isinstance(data, dict), "root must be a mapping/object")
    _require(
        isinstance(data.get("lock_version"), str) and data["lock_version"].strip(),
        "lock_version must be a non-empty string",
    )

    required_keys = (
        "permitted_source_families",
        "registered_service_adapters",
        "permitted_jurisdictions",
        "prohibited_source_classes",
        "admission_states",
        "required_provenance_fields",
        "required_validation_states",
        "conflict_policy_reference",
        "versioning_policy_reference",
        "retrieval_boundary_requirement",
        "expansion_policy",
    )
    missing = [k for k in required_keys if k not in data]
    _require(not missing, f"missing top-level keys: {missing}")

    _require(
        isinstance(data["permitted_source_families"], list) and data["permitted_source_families"],
        "permitted_source_families must be a non-empty list",
    )
    _require(
        len(data["permitted_source_families"]) == len(set(data["permitted_source_families"])),
        "permitted_source_families contains duplicates",
    )
    _require(
        set(data["permitted_source_families"]).isdisjoint(set(data["registered_service_adapters"])),
        "a source family cannot be both a permitted evidence source and a service adapter",
    )

    _require(
        set(data["admission_states"]) == VALID_ADMISSION_STATES,
        f"admission_states must be exactly {sorted(VALID_ADMISSION_STATES)}, "
        f"got {data['admission_states']}",
    )

    _require(
        isinstance(data["prohibited_source_classes"], list) and data["prohibited_source_classes"],
        "prohibited_source_classes must be a non-empty list",
    )
    seen_psc_ids: set[str] = set()
    for idx, psc in enumerate(data["prohibited_source_classes"]):
        _require(isinstance(psc, dict), f"prohibited_source_classes[{idx}] is not a mapping")
        _require(psc.get("id"), f"prohibited_source_classes[{idx}] missing 'id'")
        _require(psc["id"] not in seen_psc_ids, f"duplicate prohibited_source_classes id: {psc['id']!r}")
        seen_psc_ids.add(psc["id"])
        _require(psc.get("name"), f"prohibited_source_classes[{idx}] missing 'name'")
        _require(psc.get("description"), f"prohibited_source_classes[{idx}] missing 'description'")

    _require(
        isinstance(data["expansion_policy"], str) and data["expansion_policy"].strip(),
        "expansion_policy must be a non-empty string",
    )
    _require(
        isinstance(data["retrieval_boundary_requirement"], str)
        and data["retrieval_boundary_requirement"].strip(),
        "retrieval_boundary_requirement must be a non-empty string",
    )
