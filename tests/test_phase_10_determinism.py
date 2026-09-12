"""
Phase 10 tests: deterministic orchestration
(docs/PHASE_10_GROUNDED_GENERATION.md Section T). Repeated generation with
the same query/EvidencePack/provider output/config must produce the same
response identity and serialization.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _generation_fixtures import citing_provider, make_pack_from_texts

from generation.generator import generate_grounded_response
from generation.prompts import build_prompt
from generation.serialize import grounded_response_to_json

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def test_prompt_construction_is_byte_identical_across_calls(authority_matrix):
    pack = make_pack_from_texts([("D-DET-1", "Trademark content.")], authority_matrix)
    prompts = {build_prompt("How to register?", None, pack) for _ in range(5)}
    assert len(prompts) == 1


def test_response_id_is_identical_for_identical_inputs(authority_matrix):
    pack = make_pack_from_texts([("D-DET-2", "Patent content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    response_ids = {
        generate_grounded_response("q", pack, citing_provider(real_id)).response_id for _ in range(5)
    }
    assert len(response_ids) == 1


def test_response_id_differs_for_different_queries(authority_matrix):
    pack = make_pack_from_texts([("D-DET-3", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    r1 = generate_grounded_response("query one", pack, citing_provider(real_id))
    r2 = generate_grounded_response("query two", pack, citing_provider(real_id))
    assert r1.response_id != r2.response_id


def test_serialized_json_is_byte_identical_across_repeated_generation(authority_matrix):
    pack = make_pack_from_texts([("D-DET-4", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    jsons = {grounded_response_to_json(generate_grounded_response("q", pack, citing_provider(real_id))) for _ in range(5)}
    assert len(jsons) == 1


def test_abstained_response_id_is_deterministic(authority_matrix):
    from evidence.builder import build_evidence_pack

    pack = build_evidence_pack([], "no evidence query")
    ids = {generate_grounded_response("q", pack, citing_provider("x")).response_id for _ in range(5)}
    assert len(ids) == 1


def test_generation_failed_response_id_is_deterministic(authority_matrix):
    from generation.providers import FakeGenerationProvider

    pack = make_pack_from_texts([("D-DET-5", "Content.")], authority_matrix)
    provider = FakeGenerationProvider(fail_with="deterministic failure")
    ids = {generate_grounded_response("q", pack, provider).response_id for _ in range(5)}
    assert len(ids) == 1
