"""
Phase 8 tests: evidence/pack identity - deterministic, collision-resistant,
backend-owned, independent of retrieval-position/LLM output
(docs/PHASE_08_EVIDENCE_OBJECT_AND_CITATION_ARCHITECTURE.md Section H/X).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _evidence_fixtures import make_hybrid_response, make_single_chunk

from evidence.builder import build_evidence_from_candidate, build_evidence_pack
from evidence.identity import compute_evidence_id, compute_pack_id
from evidence.models import EvidenceSelectionConfig

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# compute_evidence_id
# ---------------------------------------------------------------------------


def test_compute_evidence_id_is_deterministic():
    args = ("1.0.0", "chunk-1", "hash-1", "doc-1", "SF-01", "INDIA", ["b1"], [1])
    assert compute_evidence_id(*args) == compute_evidence_id(*args)


def test_compute_evidence_id_is_a_sha256_hex_digest():
    evidence_id = compute_evidence_id("1.0.0", "chunk-1", "hash-1", "doc-1", "SF-01", "INDIA", ["b1"], [1])
    assert len(evidence_id) == 64
    assert all(c in "0123456789abcdef" for c in evidence_id)


@pytest.mark.parametrize(
    "changed_index",
    [0, 1, 2, 3, 4, 5],
)
def test_compute_evidence_id_changes_when_any_scalar_input_changes(changed_index):
    base_args = ["1.0.0", "chunk-1", "hash-1", "doc-1", "SF-01", "INDIA"]
    base = compute_evidence_id(*base_args, ["b1"], [1])
    changed_args = list(base_args)
    changed_args[changed_index] = changed_args[changed_index] + "-CHANGED"
    changed = compute_evidence_id(*changed_args, ["b1"], [1])
    assert base != changed


def test_compute_evidence_id_changes_when_block_ids_change():
    base = compute_evidence_id("1.0.0", "chunk-1", "hash-1", "doc-1", "SF-01", "INDIA", ["b1"], [1])
    changed = compute_evidence_id("1.0.0", "chunk-1", "hash-1", "doc-1", "SF-01", "INDIA", ["b2"], [1])
    assert base != changed


def test_compute_evidence_id_changes_when_page_numbers_change():
    base = compute_evidence_id("1.0.0", "chunk-1", "hash-1", "doc-1", "SF-01", "INDIA", ["b1"], [1])
    changed = compute_evidence_id("1.0.0", "chunk-1", "hash-1", "doc-1", "SF-01", "INDIA", ["b1"], [2])
    assert base != changed


def test_compute_evidence_id_is_distinct_from_chunk_id(authority_matrix):
    chunk = make_single_chunk("Trademark registration content.", "D1", authority_matrix)
    resp = make_hybrid_response([chunk], "trademark registration", top_k=1)
    evidence = build_evidence_from_candidate(resp.results[0])
    assert evidence.evidence_id != evidence.chunk_id


def test_evidence_id_never_depends_on_retrieval_position(authority_matrix):
    # Two identical chunks retrieved in different orders (via different
    # top_k slicing) must produce the SAME evidence_id for the same
    # underlying chunk - proving evidence_id is not derived from rank/
    # array position.
    chunks = [
        make_single_chunk("Trademark registration alpha content.", "D-A", authority_matrix),
        make_single_chunk("Trademark registration beta content.", "D-B", authority_matrix),
    ]
    resp1 = make_hybrid_response(chunks, "trademark registration", top_k=2)
    resp2 = make_hybrid_response(list(reversed(chunks)), "trademark registration", top_k=2)

    ev1_by_chunk = {build_evidence_from_candidate(c).chunk_id: build_evidence_from_candidate(c) for c in resp1.results}
    ev2_by_chunk = {build_evidence_from_candidate(c).chunk_id: build_evidence_from_candidate(c) for c in resp2.results}

    common_chunk_ids = set(ev1_by_chunk) & set(ev2_by_chunk)
    assert common_chunk_ids
    for chunk_id in common_chunk_ids:
        assert ev1_by_chunk[chunk_id].evidence_id == ev2_by_chunk[chunk_id].evidence_id


# ---------------------------------------------------------------------------
# compute_pack_id
# ---------------------------------------------------------------------------


def test_compute_pack_id_is_deterministic():
    args = ("1.0.0", "query text", ["e1", "e2"], "config-sig")
    assert compute_pack_id(*args) == compute_pack_id(*args)


def test_compute_pack_id_changes_with_query():
    base = compute_pack_id("1.0.0", "query one", ["e1"], "sig")
    changed = compute_pack_id("1.0.0", "query two", ["e1"], "sig")
    assert base != changed


def test_compute_pack_id_changes_with_evidence_id_order():
    a = compute_pack_id("1.0.0", "q", ["e1", "e2"], "sig")
    b = compute_pack_id("1.0.0", "q", ["e2", "e1"], "sig")
    assert a != b


def test_compute_pack_id_changes_with_config_signature():
    a = compute_pack_id("1.0.0", "q", ["e1"], "sig-a")
    b = compute_pack_id("1.0.0", "q", ["e1"], "sig-b")
    assert a != b


def test_pack_id_changes_when_selection_config_changes(authority_matrix):
    chunks = [make_single_chunk(f"Trademark document {i}.", f"D-CFG-{i}", authority_matrix) for i in range(3)]
    resp = make_hybrid_response(chunks, "trademark", top_k=3)
    pack_a = build_evidence_pack(resp.results, "trademark", EvidenceSelectionConfig(max_evidence_items=3))
    pack_b = build_evidence_pack(resp.results, "trademark", EvidenceSelectionConfig(max_evidence_items=1))
    assert pack_a.pack_id != pack_b.pack_id


def test_evidence_id_schema_version_is_part_of_identity(authority_matrix):
    chunk = make_single_chunk("Trademark content.", "D-SCHEMA", authority_matrix)
    resp = make_hybrid_response([chunk], "trademark", top_k=1)
    candidate = resp.results[0]
    evidence_v1 = build_evidence_from_candidate(candidate, schema_version="1.0.0")
    evidence_v2 = build_evidence_from_candidate(candidate, schema_version="2.0.0")
    assert evidence_v1.evidence_id != evidence_v2.evidence_id
    assert evidence_v1.chunk_id == evidence_v2.chunk_id  # chunk_id unaffected by schema version
