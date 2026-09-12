"""
Phase 1 test-support module: schema validation for
config/domain_taxonomy.yaml, config/regulatory_decision_tree.yaml, and
config/classification_contract.yaml.

Test/validation infrastructure only - not application implementation.
Not a test module itself (no test_ prefix) - pytest will not collect it.
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

REQUIRED_CATEGORY_FIELDS = ("id", "name", "description", "status", "source_label")

VALID_TERMINAL_STATES = frozenset({"KNOWN", "UNKNOWN", "AMBIGUOUS", "NEEDS_EVIDENCE"})


class TaxonomyValidationError(ValueError):
    """Raised when a Phase 1 config document (or a candidate document) is malformed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TaxonomyValidationError(message)


def _iter_category_lists(data: dict):
    """Yield (location_label, [category, ...]) for every known category list."""
    _require(isinstance(data, dict), "root must be a mapping/object")

    dimensions = data.get("dimensions")
    if dimensions is not None:
        _require(isinstance(dimensions, dict), "dimensions must be a mapping")
        for dim_name, dim in dimensions.items():
            _require(isinstance(dim, dict), f"dimension {dim_name!r} must be a mapping")
            cats = dim.get("categories")
            _require(
                isinstance(cats, list) and cats,
                f"dimension {dim_name!r} must have a non-empty categories list",
            )
            yield f"dimensions.{dim_name}", cats

    for key in (
        "regulatory_question_categories",
        "user_intent_categories",
        "jurisdiction_inputs",
        "evidence_states",
        "classification_states",
    ):
        block = data.get(key)
        if block is not None:
            _require(isinstance(block, dict), f"{key} must be a mapping")
            cats = block.get("categories")
            _require(
                isinstance(cats, list) and cats,
                f"{key} must have a non-empty categories list",
            )
            yield key, cats


def validate_domain_taxonomy(data) -> None:
    _require(isinstance(data, dict), "root must be a mapping/object")
    _require(
        isinstance(data.get("taxonomy_version"), str) and data["taxonomy_version"].strip(),
        "taxonomy_version must be a non-empty string",
    )

    required_top_keys = (
        "dimensions",
        "regulatory_question_categories",
        "user_intent_categories",
        "jurisdiction_inputs",
        "evidence_states",
        "classification_states",
        "explainability_requirements",
    )
    missing = [k for k in required_top_keys if k not in data]
    _require(not missing, f"missing top-level keys: {missing}")

    seen_ids: set[str] = set()
    total_categories = 0

    for location, categories in _iter_category_lists(data):
        for idx, cat in enumerate(categories):
            _require(isinstance(cat, dict), f"{location}[{idx}] is not a mapping")
            missing_fields = [f for f in REQUIRED_CATEGORY_FIELDS if f not in cat]
            _require(
                not missing_fields,
                f"{location}[{idx}] (id={cat.get('id')!r}) missing fields: {missing_fields}",
            )
            for field_name in ("id", "name", "description", "status"):
                value = cat[field_name]
                _require(
                    isinstance(value, str) and value.strip(),
                    f"{location}[{idx}] field {field_name!r} must be a non-empty string",
                )
            cat_id = cat["id"]
            _require(cat_id not in seen_ids, f"duplicate taxonomy id: {cat_id!r}")
            seen_ids.add(cat_id)
            total_categories += 1

            _require(
                cat["source_label"] in APPROVED_SOURCE_LABELS,
                f"{location}[{idx}] (id={cat_id!r}) has unapproved source_label {cat['source_label']!r}",
            )
            _require(
                cat["status"] == "DEFINED",
                f"{location}[{idx}] (id={cat_id!r}) has unexpected status {cat['status']!r} "
                f"(Phase 1 may not claim anything beyond DEFINED)",
            )

    _require(total_categories > 0, "taxonomy contains no categories at all")

    explain = data["explainability_requirements"]
    _require(isinstance(explain, list) and explain, "explainability_requirements must be non-empty")
    for idx, item in enumerate(explain):
        _require(isinstance(item, dict), f"explainability_requirements[{idx}] not a mapping")
        _require(
            item.get("requirement") and item.get("source_label") in APPROVED_SOURCE_LABELS,
            f"explainability_requirements[{idx}] missing requirement or valid source_label",
        )


def validate_decision_tree(data) -> None:
    _require(isinstance(data, dict), "root must be a mapping/object")
    _require(
        isinstance(data.get("tree_version"), str) and data["tree_version"].strip(),
        "tree_version must be a non-empty string",
    )

    for key in ("input_fields", "evidence_requiring_intents", "terminal_states", "stages"):
        _require(key in data, f"missing top-level key: {key}")

    terminal_states = data["terminal_states"]
    _require(
        set(terminal_states) == VALID_TERMINAL_STATES,
        f"terminal_states must be exactly {sorted(VALID_TERMINAL_STATES)}, got {terminal_states}",
    )

    stages = data["stages"]
    _require(isinstance(stages, list) and stages, "stages must be a non-empty list")

    seen_rule_ids: set[str] = set()
    seen_stage_numbers: set[int] = set()
    prev_stage_num = 0

    required_stage_fields = ("stage", "rule_id", "name", "condition", "result_state", "source_label")

    for idx, stage in enumerate(stages):
        _require(isinstance(stage, dict), f"stages[{idx}] is not a mapping")
        missing = [f for f in required_stage_fields if f not in stage]
        _require(not missing, f"stages[{idx}] missing fields: {missing}")

        stage_num = stage["stage"]
        _require(isinstance(stage_num, int), f"stages[{idx}] 'stage' must be an integer")
        _require(stage_num not in seen_stage_numbers, f"duplicate stage number: {stage_num}")
        _require(
            stage_num == prev_stage_num + 1,
            f"stages must be strictly ordered 1..N with no gaps; got {stage_num} after {prev_stage_num}",
        )
        seen_stage_numbers.add(stage_num)
        prev_stage_num = stage_num

        rule_id = stage["rule_id"]
        _require(rule_id not in seen_rule_ids, f"duplicate rule_id: {rule_id!r}")
        seen_rule_ids.add(rule_id)

        _require(
            stage["result_state"] in VALID_TERMINAL_STATES,
            f"stages[{idx}] (rule_id={rule_id!r}) result_state {stage['result_state']!r} "
            f"not a valid terminal state",
        )
        _require(
            stage["source_label"] in APPROVED_SOURCE_LABELS,
            f"stages[{idx}] (rule_id={rule_id!r}) has unapproved source_label",
        )
        _require(
            isinstance(stage["condition"], str) and stage["condition"].strip(),
            f"stages[{idx}] (rule_id={rule_id!r}) condition must be a non-empty string",
        )

    # Exactly one stage may be a true catch-all (condition == "otherwise"),
    # and it must be the last stage - proving the tree always terminates.
    catchalls = [s for s in stages if s["condition"].strip() == "otherwise"]
    _require(len(catchalls) == 1, "exactly one catch-all ('otherwise') stage is required")
    _require(
        catchalls[0]["stage"] == stages[-1]["stage"],
        "the catch-all stage must be the last stage in the ordered list",
    )
    _require(
        catchalls[0]["result_state"] == "KNOWN",
        "the catch-all stage must resolve to KNOWN",
    )


def validate_classification_contract(data) -> None:
    _require(isinstance(data, dict), "root must be a mapping/object")
    _require(
        isinstance(data.get("contract_version"), str) and data["contract_version"].strip(),
        "contract_version must be a non-empty string",
    )
    _require("fields" in data, "missing top-level key: fields")
    _require("safety_invariants" in data, "missing top-level key: safety_invariants")

    fields = data["fields"]
    _require(isinstance(fields, list) and fields, "fields must be a non-empty list")

    seen_names: set[str] = set()
    forbidden_field_name_fragments = ("legally_certain", "is_legally_valid", "legal_determination")

    def _check_fields(field_list, path):
        for idx, f in enumerate(field_list):
            _require(isinstance(f, dict), f"{path}[{idx}] is not a mapping")
            _require(f.get("name"), f"{path}[{idx}] missing non-empty 'name'")
            _require(f.get("type"), f"{path}[{idx}] (name={f.get('name')!r}) missing non-empty 'type'")
            _require(
                "required" in f and isinstance(f["required"], bool),
                f"{path}[{idx}] (name={f.get('name')!r}) missing boolean 'required'",
            )
            name_lower = f["name"].lower()
            for frag in forbidden_field_name_fragments:
                _require(
                    frag not in name_lower,
                    f"{path}[{idx}] field name {f['name']!r} implies legal certainty, which is forbidden",
                )
            if f["type"] == "object" and "fields" in f:
                _check_fields(f["fields"], f"{path}[{idx}].fields")

    _check_fields(fields, "fields")

    disclaimer_fields = [f for f in fields if f.get("name") == "disclaimer"]
    _require(len(disclaimer_fields) == 1, "exactly one top-level 'disclaimer' field is required")
    _require(disclaimer_fields[0].get("required") is True, "'disclaimer' field must be required")
    _require(
        bool(disclaimer_fields[0].get("constant", "").strip()),
        "'disclaimer' field must define a non-empty constant value",
    )

    invariants = data["safety_invariants"]
    _require(isinstance(invariants, list) and invariants, "safety_invariants must be a non-empty list")
    seen_invariant_ids: set[str] = set()
    for idx, inv in enumerate(invariants):
        _require(isinstance(inv, dict), f"safety_invariants[{idx}] is not a mapping")
        _require(inv.get("id"), f"safety_invariants[{idx}] missing 'id'")
        _require(inv["id"] not in seen_invariant_ids, f"duplicate safety_invariant id: {inv['id']!r}")
        seen_invariant_ids.add(inv["id"])
        _require(inv.get("rule"), f"safety_invariants[{idx}] missing 'rule'")
        _require(
            inv.get("source_label") in APPROVED_SOURCE_LABELS,
            f"safety_invariants[{idx}] has unapproved source_label",
        )
