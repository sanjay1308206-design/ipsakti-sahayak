"""
Phase 3 tests: provenance traceability (the critical Phase 3 invariant:
block -> page -> document_id -> source_family_id -> jurisdiction ->
content_hash), synthetic-flag propagation, and
config/document_ingestion_contract.yaml.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from _document_schema import DocumentSchemaValidationError, validate_document_ingestion_contract
from _provenance_fixtures import make_provenance

from ingestion.hashing import compute_content_hash
from ingestion.pipeline import ingest_bytes

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = REPO_ROOT / "config" / "document_ingestion_contract.yaml"


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# THE critical Phase 3 invariant: full block -> source traceability
# ---------------------------------------------------------------------------


def test_block_traces_back_to_page_document_source_jurisdiction_hash(authority_matrix: dict):
    data = b"1. Clause One\n\nSome body text about the clause.\n"
    provenance = make_provenance(
        compute_content_hash(data),
        document_id="SYNTHETIC-TRACE-0001",
        source_family_id="SF-04",  # CDSCO
        jurisdiction="INDIA",
    )
    result = ingest_bytes(data, provenance, ".txt", authority_matrix=authority_matrix)
    assert result.pipeline_state == "EXTRACTION_SUCCESS"

    document = result.document
    for page in document.pages:
        for block in page.blocks:
            # block -> page
            assert block.page_number == page.page_number
            # (page ->) document_id
            assert document.document_id == "SYNTHETIC-TRACE-0001"
            # -> source_family_id
            assert document.source_family_id == "SF-04"
            # -> jurisdiction
            assert document.jurisdiction == "INDIA"
            # -> content_hash
            assert document.integrity.claimed_content_hash == compute_content_hash(data)
            assert document.integrity.computed_content_hash == compute_content_hash(data)
            assert document.integrity.match is True


def test_multi_page_traceability_holds_per_page():
    from _pdf_fixtures import make_multi_page_text_pdf

    data = make_multi_page_text_pdf(["Page one content", "Page two content", "Page three content"])
    matrix = yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))
    provenance = make_provenance(
        compute_content_hash(data), document_id="SYNTHETIC-TRACE-MULTI", source_family_id="SF-01"
    )
    result = ingest_bytes(data, provenance, ".pdf", authority_matrix=matrix)
    assert result.pipeline_state == "EXTRACTION_SUCCESS"

    for page in result.document.pages:
        assert len(page.blocks) >= 1
        for block in page.blocks:
            assert block.page_number == page.page_number
            assert block.block_id.startswith(f"{result.document.document_id}:p{page.page_number}:")


def test_block_id_is_globally_unique_within_document():
    from _pdf_fixtures import make_multi_page_text_pdf

    data = make_multi_page_text_pdf(["Alpha content", "Beta content"])
    matrix = yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))
    provenance = make_provenance(compute_content_hash(data))
    result = ingest_bytes(data, provenance, ".pdf", authority_matrix=matrix)

    all_ids = [b.block_id for p in result.document.pages for b in p.blocks]
    assert len(all_ids) == len(set(all_ids))


# ---------------------------------------------------------------------------
# Synthetic-flag propagation (PROV-SAFE-01/05, docs/PHASE_03_DOCUMENT_INGESTION.md Section C)
# ---------------------------------------------------------------------------


def test_synthetic_flag_propagates_true(authority_matrix: dict):
    data = b"content"
    provenance = make_provenance(compute_content_hash(data), synthetic=True)
    result = ingest_bytes(data, provenance, ".txt", authority_matrix=authority_matrix)
    assert result.document.synthetic is True


def test_synthetic_flag_propagates_false(authority_matrix: dict):
    # Structural check only - no real admitted document exists in this
    # repository, so this proves the plumbing, not a real-data claim.
    data = b"content"
    provenance = make_provenance(compute_content_hash(data), synthetic=False)
    result = ingest_bytes(data, provenance, ".txt", authority_matrix=authority_matrix)
    assert result.document.synthetic is False


def test_synthetic_flag_is_never_silently_dropped_or_flipped(authority_matrix: dict):
    data = b"content"
    for flag in (True, False):
        provenance = make_provenance(compute_content_hash(data), synthetic=flag)
        result = ingest_bytes(data, provenance, ".txt", authority_matrix=authority_matrix)
        assert result.document.synthetic == flag


def test_missing_version_is_not_silently_treated_as_current(authority_matrix: dict):
    # Phase 2's provenance schema requires version_known/effective_date_known
    # to be explicit; Phase 3's pipeline does not invent a version where the
    # provenance record does not supply one - it simply is not part of the
    # ExtractedDocument output at all (only Phase 2-governed admission
    # fields participate in the admission boundary). This test proves the
    # pipeline never fabricates a "version" attribute anywhere in its output.
    data = b"content"
    provenance = make_provenance(compute_content_hash(data))
    provenance.pop("version", None)
    provenance["version_known"] = False
    result = ingest_bytes(data, provenance, ".txt", authority_matrix=authority_matrix)
    assert result.pipeline_state != "REJECTED_INPUT"
    import dataclasses

    doc_dict = dataclasses.asdict(result.document)
    assert "version" not in doc_dict  # never fabricated


# ---------------------------------------------------------------------------
# document_ingestion_contract.yaml
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def contract_raw_text() -> str:
    return CONTRACT_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def contract_data(contract_raw_text: str) -> dict:
    return yaml.safe_load(contract_raw_text)


@pytest.fixture()
def valid_contract_copy(contract_data: dict) -> dict:
    return copy.deepcopy(contract_data)


def test_contract_file_exists_and_nonempty():
    assert CONTRACT_PATH.stat().st_size > 0


def test_contract_yaml_parses(contract_raw_text: str):
    assert isinstance(yaml.safe_load(contract_raw_text), dict)


def test_contract_passes_validation(contract_data: dict):
    validate_document_ingestion_contract(contract_data)


def test_contract_pipeline_states_match_implementation(contract_data: dict):
    from ingestion.models import PIPELINE_STATES

    assert set(contract_data["pipeline_states"]) == PIPELINE_STATES


def test_contract_accepted_input_states_match_admission_module(contract_data: dict):
    from ingestion.admission import ACCEPTED_ADMISSION_STATES

    assert set(contract_data["accepted_input_states"]) == ACCEPTED_ADMISSION_STATES


def test_contract_accepted_document_types_match_pipeline_extensions(contract_data: dict):
    from ingestion.pipeline import DOCUMENT_TYPE_BY_EXTENSION

    assert set(contract_data["accepted_document_types"]) == set(DOCUMENT_TYPE_BY_EXTENSION.values())


def test_contract_max_input_bytes_matches_pipeline_constant(contract_data: dict):
    from ingestion.pipeline import MAX_INPUT_BYTES

    assert contract_data["security_limits"]["max_input_bytes"] == MAX_INPUT_BYTES


def test_contract_malformed_root_is_rejected():
    with pytest.raises(DocumentSchemaValidationError):
        validate_document_ingestion_contract(["not", "a", "mapping"])


def test_contract_missing_key_is_rejected(valid_contract_copy: dict):
    del valid_contract_copy["quarantine_states"]
    with pytest.raises(DocumentSchemaValidationError):
        validate_document_ingestion_contract(valid_contract_copy)


def test_contract_wrong_pipeline_states_rejected(valid_contract_copy: dict):
    valid_contract_copy["pipeline_states"] = ["ADMIT"]
    with pytest.raises(DocumentSchemaValidationError):
        validate_document_ingestion_contract(valid_contract_copy)


def test_contract_accepted_input_states_cannot_include_reject(valid_contract_copy: dict):
    valid_contract_copy["accepted_input_states"] = ["ADMIT", "REJECT"]
    with pytest.raises(DocumentSchemaValidationError):
        validate_document_ingestion_contract(valid_contract_copy)
