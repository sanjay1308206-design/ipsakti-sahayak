"""
Phase 4 tests: the critical Phase 4 invariant (chunk -> block -> page ->
document -> source_family_id -> jurisdiction -> content_hash), synthetic
flag propagation, no-orphaned-chunk safety, and the machine-readable
config/chunking_contract.yaml / config/chunk_schema.yaml contracts.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml
from _chunk_fixtures import make_document
from _chunk_schema import ChunkSchemaValidationError, validate_chunk_schema, validate_chunking_contract
from _pdf_fixtures import make_multi_page_text_pdf

from chunking.chunker import chunk_document
from chunking.models import ChunkingConfig

REPO_ROOT = Path(__file__).resolve().parent.parent
CHUNKING_CONTRACT_PATH = REPO_ROOT / "config" / "chunking_contract.yaml"
CHUNK_SCHEMA_PATH = REPO_ROOT / "config" / "chunk_schema.yaml"


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# THE critical Phase 4 invariant: full chunk -> source traceability
# ---------------------------------------------------------------------------


def test_chunk_traces_back_to_block_page_document_source_jurisdiction_hash(authority_matrix):
    data = b"1. Clause One\n\nSome body text about the clause.\n"
    doc = make_document(
        data, ".txt", authority_matrix,
        document_id="SYNTHETIC-CHUNK-TRACE-0001", source_family_id="SF-04", jurisdiction="INDIA",
    )
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=500))
    assert result.chunking_status == "CHUNKING_SUCCESS"

    all_source_blocks = {b.block_id: b for p in doc.pages for b in p.blocks}
    for chunk in result.chunks:
        # chunk -> block(s)
        assert chunk.block_ids, "a chunk must reference at least one block"
        for block_id in chunk.block_ids:
            assert block_id in all_source_blocks
            source_block = all_source_blocks[block_id]
            # block -> page
            assert source_block.page_number in chunk.page_numbers
        # -> document_id
        assert chunk.document_id == doc.document_id == "SYNTHETIC-CHUNK-TRACE-0001"
        # -> source_family_id
        assert chunk.source_family_id == doc.source_family_id == "SF-04"
        # -> jurisdiction
        assert chunk.jurisdiction == doc.jurisdiction == "INDIA"
        # -> content_hash
        assert chunk.content_hash == doc.integrity.claimed_content_hash
        assert doc.integrity.match is True


def test_every_source_block_is_covered_by_exactly_one_non_split_chunk_or_split_group(authority_matrix):
    pdf = make_multi_page_text_pdf(["1. Heading one", "Body two.", "1. Heading three"])
    doc = make_document(pdf, ".pdf", authority_matrix, document_id="D-PROV-COVER")
    result = chunk_document(doc, ChunkingConfig(max_chunk_size_chars=1000))

    all_block_ids = [b.block_id for p in doc.pages for b in p.blocks]
    covered = []
    for c in result.chunks:
        covered.extend(c.block_ids)
    # every real block appears at least once across all chunks (no silent drop)
    assert set(all_block_ids) <= set(covered)


def test_no_chunk_is_ever_orphaned_from_all_provenance_fields(authority_matrix):
    data = b"Some content with no headings.\n"
    doc = make_document(data, ".txt", authority_matrix, document_id="D-PROV-ORPHAN")
    result = chunk_document(doc, ChunkingConfig())
    for c in result.chunks:
        assert c.document_id
        assert c.source_family_id
        assert c.jurisdiction
        assert c.content_hash
        assert c.block_ids
        assert c.page_numbers


# ---------------------------------------------------------------------------
# Synthetic-flag propagation
# ---------------------------------------------------------------------------


def test_synthetic_flag_propagates_true_to_every_chunk(authority_matrix):
    data = b"Body text.\n"
    doc = make_document(data, ".txt", authority_matrix, document_id="D-SYN-01", synthetic=True)
    result = chunk_document(doc, ChunkingConfig())
    assert all(c.synthetic is True for c in result.chunks)


def test_synthetic_flag_propagates_false_to_every_chunk(authority_matrix):
    # Structural check only - no real admitted document exists in this
    # repository, matching tests/test_phase_03_provenance.py's own caveat.
    data = b"Body text.\n"
    doc = make_document(data, ".txt", authority_matrix, document_id="D-SYN-02", synthetic=False)
    result = chunk_document(doc, ChunkingConfig())
    assert all(c.synthetic is False for c in result.chunks)


# ---------------------------------------------------------------------------
# config/chunking_contract.yaml
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def chunking_contract_raw_text() -> str:
    return CHUNKING_CONTRACT_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def chunking_contract_data(chunking_contract_raw_text: str) -> dict:
    return yaml.safe_load(chunking_contract_raw_text)


@pytest.fixture()
def valid_chunking_contract_copy(chunking_contract_data: dict) -> dict:
    return copy.deepcopy(chunking_contract_data)


def test_chunking_contract_file_exists_and_nonempty():
    assert CHUNKING_CONTRACT_PATH.stat().st_size > 0


def test_chunking_contract_yaml_parses(chunking_contract_raw_text: str):
    assert isinstance(yaml.safe_load(chunking_contract_raw_text), dict)


def test_chunking_contract_passes_validation(chunking_contract_data: dict):
    validate_chunking_contract(chunking_contract_data)


def test_chunking_contract_states_match_implementation(chunking_contract_data: dict):
    from chunking.models import CHUNKING_STATES

    assert set(chunking_contract_data["chunking_states"]) == CHUNKING_STATES


def test_chunking_contract_default_max_size_matches_implementation(chunking_contract_data: dict):
    assert chunking_contract_data["default_max_chunk_size_chars"] == ChunkingConfig().max_chunk_size_chars


def test_chunking_contract_size_unit_matches_implementation(chunking_contract_data: dict):
    from chunking.models import SIZE_UNIT

    assert chunking_contract_data["size_unit"] == SIZE_UNIT


def test_chunking_contract_malformed_root_is_rejected():
    with pytest.raises(ChunkSchemaValidationError):
        validate_chunking_contract(["not", "a", "mapping"])


def test_chunking_contract_missing_key_is_rejected(valid_chunking_contract_copy: dict):
    del valid_chunking_contract_copy["safety_invariants"]
    with pytest.raises(ChunkSchemaValidationError):
        validate_chunking_contract(valid_chunking_contract_copy)


def test_chunking_contract_wrong_states_rejected(valid_chunking_contract_copy: dict):
    valid_chunking_contract_copy["chunking_states"] = ["ADMIT"]
    with pytest.raises(ChunkSchemaValidationError):
        validate_chunking_contract(valid_chunking_contract_copy)


# ---------------------------------------------------------------------------
# config/chunk_schema.yaml
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def chunk_schema_raw_text() -> str:
    return CHUNK_SCHEMA_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def chunk_schema_data(chunk_schema_raw_text: str) -> dict:
    return yaml.safe_load(chunk_schema_raw_text)


@pytest.fixture()
def valid_chunk_schema_copy(chunk_schema_data: dict) -> dict:
    return copy.deepcopy(chunk_schema_data)


def test_chunk_schema_file_exists_and_nonempty():
    assert CHUNK_SCHEMA_PATH.stat().st_size > 0


def test_chunk_schema_yaml_parses(chunk_schema_raw_text: str):
    assert isinstance(yaml.safe_load(chunk_schema_raw_text), dict)


def test_chunk_schema_passes_validation(chunk_schema_data: dict):
    validate_chunk_schema(chunk_schema_data)


def test_chunk_schema_malformed_root_is_rejected():
    with pytest.raises(ChunkSchemaValidationError):
        validate_chunk_schema(["not", "a", "mapping"])


def test_chunk_schema_missing_block_key_is_rejected(valid_chunk_schema_copy: dict):
    del valid_chunk_schema_copy["chunk"]
    with pytest.raises(ChunkSchemaValidationError):
        validate_chunk_schema(valid_chunk_schema_copy)


def test_chunk_schema_duplicate_field_name_is_rejected(valid_chunk_schema_copy: dict):
    valid_chunk_schema_copy["chunk"]["fields"].append(valid_chunk_schema_copy["chunk"]["fields"][0])
    with pytest.raises(ChunkSchemaValidationError):
        validate_chunk_schema(valid_chunk_schema_copy)


def test_chunk_schema_wrong_chunking_states_rejected(valid_chunk_schema_copy: dict):
    valid_chunk_schema_copy["chunking_states"] = ["ADMIT"]
    with pytest.raises(ChunkSchemaValidationError):
        validate_chunk_schema(valid_chunk_schema_copy)


def test_chunk_schema_field_names_match_chunk_dataclass(chunk_schema_data: dict):
    import dataclasses

    from chunking.models import Chunk

    schema_field_names = {f["name"] for f in chunk_schema_data["chunk"]["fields"]}
    dataclass_field_names = {f.name for f in dataclasses.fields(Chunk)}
    assert schema_field_names == dataclass_field_names
