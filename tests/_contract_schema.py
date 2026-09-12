"""
Phase 0 test-support module: schema validation for config/acceptance_contract.yaml.

This is test/validation infrastructure for the Phase 0 acceptance contract
ONLY. It is not application implementation (no retrieval, classification,
generation, etc. lives here) and it is intentionally kept out of src/ so it
is not mistaken for product code.

Not a test module itself (no test_ prefix) - pytest will not collect it.
"""

from __future__ import annotations

REQUIRED_TOP_LEVEL_KEYS = (
    "project",
    "phase",
    "source_discipline_labels",
    "status_vocabulary",
    "mandatory_capabilities",
)

REQUIRED_CAPABILITY_FIELDS = (
    "id",
    "name",
    "owner_phase",
    "required_behavior",
    "test_requirement",
    "acceptance_criterion",
    "status",
)

REQUIRED_DEFERRED_FIELDS = ("id", "name")

MIN_PHASE = 0
MAX_PHASE = 23

# Statuses that would claim a future phase's work is already done. Phase 0
# must never assign these to any capability - only DEFINED is legitimate
# until a phase is explicitly implemented.
IMPLEMENTATION_STATUSES = {"IMPLEMENTED", "VALIDATED"}


class ContractValidationError(ValueError):
    """Raised when config/acceptance_contract.yaml (or a candidate document) is malformed."""


def validate_contract(data) -> None:
    """
    Validate the structure of a parsed acceptance-contract document.

    Raises ContractValidationError on any structural problem. Returns None
    (no exception) when the document is well-formed. Does not evaluate
    truthfulness of content, only structural/schema correctness.
    """
    if not isinstance(data, dict):
        raise ContractValidationError("contract root must be a mapping/object")

    missing_top = [k for k in REQUIRED_TOP_LEVEL_KEYS if k not in data]
    if missing_top:
        raise ContractValidationError(f"missing top-level keys: {missing_top}")

    project = data["project"]
    if not isinstance(project, dict) or not project.get("id") or not project.get("name"):
        raise ContractValidationError("project must be a mapping with non-empty 'id' and 'name'")

    phase = data["phase"]
    if not isinstance(phase, dict) or "id" not in phase or not phase.get("name"):
        raise ContractValidationError("phase must be a mapping with 'id' and non-empty 'name'")
    if not isinstance(phase["id"], int):
        raise ContractValidationError("phase.id must be an integer")

    status_vocab = data["status_vocabulary"]
    if not isinstance(status_vocab, list) or not status_vocab:
        raise ContractValidationError("status_vocabulary must be a non-empty list")

    labels = data["source_discipline_labels"]
    if not isinstance(labels, list) or not labels:
        raise ContractValidationError("source_discipline_labels must be a non-empty list")

    capabilities = data["mandatory_capabilities"]
    if not isinstance(capabilities, list) or not capabilities:
        raise ContractValidationError("mandatory_capabilities must be a non-empty list")

    seen_ids = set()
    seen_owner_phases = set()

    for idx, cap in enumerate(capabilities):
        if not isinstance(cap, dict):
            raise ContractValidationError(f"capability at index {idx} is not a mapping")

        missing = [f for f in REQUIRED_CAPABILITY_FIELDS if f not in cap]
        if missing:
            raise ContractValidationError(
                f"capability at index {idx} (id={cap.get('id')!r}) missing fields: {missing}"
            )

        cap_id = cap["id"]
        if not isinstance(cap_id, str) or not cap_id.strip():
            raise ContractValidationError(f"capability at index {idx} has empty/invalid id")
        if cap_id in seen_ids:
            raise ContractValidationError(f"duplicate capability id: {cap_id!r}")
        seen_ids.add(cap_id)

        for field in ("name", "required_behavior", "test_requirement", "acceptance_criterion"):
            value = cap[field]
            if not isinstance(value, str) or not value.strip():
                raise ContractValidationError(
                    f"capability {cap_id!r} field {field!r} must be a non-empty string"
                )

        owner_phase = cap["owner_phase"]
        if not isinstance(owner_phase, int) or not (MIN_PHASE <= owner_phase <= MAX_PHASE):
            raise ContractValidationError(
                f"capability {cap_id!r} owner_phase must be an integer in "
                f"[{MIN_PHASE}, {MAX_PHASE}], got {owner_phase!r}"
            )
        seen_owner_phases.add(owner_phase)

        status = cap["status"]
        if status not in status_vocab:
            raise ContractValidationError(
                f"capability {cap_id!r} status {status!r} not in status_vocabulary {status_vocab}"
            )
        if status in IMPLEMENTATION_STATUSES:
            raise ContractValidationError(
                f"capability {cap_id!r} is marked {status!r} - Phase 0 may not claim "
                f"implementation of any future phase"
            )

    # Deferred technologies are optional at the schema level (some contract
    # revisions may have none) but if present must be well-formed and unique.
    deferred = data.get("deferred_technologies")
    if deferred is not None:
        if not isinstance(deferred, list):
            raise ContractValidationError("deferred_technologies must be a list when present")
        seen_def_ids = set()
        for idx, item in enumerate(deferred):
            if not isinstance(item, dict):
                raise ContractValidationError(f"deferred_technologies[{idx}] is not a mapping")
            missing = [f for f in REQUIRED_DEFERRED_FIELDS if not item.get(f)]
            if missing:
                raise ContractValidationError(
                    f"deferred_technologies[{idx}] missing/empty fields: {missing}"
                )
            def_id = item["id"]
            if def_id in seen_def_ids:
                raise ContractValidationError(f"duplicate deferred_technologies id: {def_id!r}")
            seen_def_ids.add(def_id)
