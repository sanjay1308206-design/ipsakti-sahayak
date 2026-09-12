"""
Phase 10 tests: citation-generation rule - invalid/unresolved model
citations can never become final citations
(docs/PHASE_10_GROUNDED_GENERATION.md Sections H, J). Reuses Phase 9's
validator verbatim - these tests prove Phase 10 actually calls it, not
that Phase 9's own resolution logic works (already tested by Phase 9).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
import yaml
from _generation_fixtures import make_pack_from_texts

from generation.generator import generate_grounded_response
from generation.providers import FakeGenerationProvider

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def test_valid_model_citation_becomes_a_final_citation(authority_matrix):
    pack = make_pack_from_texts([("D-CIT-1", "Trademark content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    provider = FakeGenerationProvider(response_text=f"Answer. [[CITE:{real_id}]]")
    response = generate_grounded_response("q", pack, provider)
    assert response.cited_evidence_ids == [real_id]


def test_fabricated_model_citation_never_becomes_a_final_citation(authority_matrix):
    pack = make_pack_from_texts([("D-CIT-2", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    provider = FakeGenerationProvider(response_text=f"Answer. [[CITE:{real_id}]] and also [[CITE:totally-fake-id]]")
    response = generate_grounded_response("q", pack, provider)
    # the REAL id survives; the fabricated one is silently excluded, never
    # presented as if it were valid.
    assert response.cited_evidence_ids == [real_id]
    assert "totally-fake-id" not in response.cited_evidence_ids


def test_malformed_model_citation_never_becomes_a_final_citation(authority_matrix):
    pack = make_pack_from_texts([("D-CIT-3", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    provider = FakeGenerationProvider(response_text=f"Answer. [[CITE:{real_id}]] [[CITE:]] [[CITE:   ]]")
    response = generate_grounded_response("q", pack, provider)
    assert response.cited_evidence_ids == [real_id]


def test_citation_to_evidence_from_a_different_pack_does_not_resolve(authority_matrix):
    pack_a = make_pack_from_texts([("D-CIT-4", "Content A.")], authority_matrix)
    pack_b = make_pack_from_texts([("D-CIT-5", "Content B.")], authority_matrix)
    id_from_b = pack_b.evidence_items[0].evidence_id
    provider = FakeGenerationProvider(response_text=f"Answer. [[CITE:{id_from_b}]]")
    response = generate_grounded_response("q", pack_a, provider)
    assert response.grounding_status == "ABSTAINED"
    assert response.cited_evidence_ids == []


def test_duplicate_valid_citations_are_deduplicated_in_final_list(authority_matrix):
    pack = make_pack_from_texts([("D-CIT-6", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    provider = FakeGenerationProvider(response_text=f"[[CITE:{real_id}]] again [[CITE:{real_id}]]")
    response = generate_grounded_response("q", pack, provider)
    assert response.cited_evidence_ids == [real_id]
    assert response.citation_validation_summary.duplicate_occurrence_count == 1


def test_citation_to_tampered_evidence_never_becomes_a_final_citation(authority_matrix):
    from evidence.identity import compute_pack_id
    from evidence.models import EvidencePack

    pack = make_pack_from_texts([("D-CIT-7", "Content.")], authority_matrix)
    tampered_item = dataclasses.replace(pack.evidence_items[0], evidence_text="tampered content")
    config_signature = pack.construction_metadata["config_signature"]
    new_pack_id = compute_pack_id(pack.schema_version, pack.query, [tampered_item.evidence_id], config_signature)
    tampered_pack = EvidencePack(
        pack_id=new_pack_id, schema_version=pack.schema_version, query=pack.query,
        evidence_items=[tampered_item], construction_metadata=pack.construction_metadata,
    )
    provider = FakeGenerationProvider(response_text=f"[[CITE:{tampered_item.evidence_id}]]")
    response = generate_grounded_response("q", tampered_pack, provider)
    assert response.grounding_status == "ABSTAINED"
    assert response.citation_validation_summary.invalid_count == 1


def test_citation_coverage_reflects_mixed_valid_and_invalid_claims(authority_matrix):
    pack = make_pack_from_texts([("D-CIT-8", "Content.")], authority_matrix)
    real_id = pack.evidence_items[0].evidence_id
    provider = FakeGenerationProvider(response_text=f"[[CITE:{real_id}]] [[CITE:fake-1]] [[CITE:fake-2]]")
    response = generate_grounded_response("q", pack, provider)
    summary = response.citation_validation_summary
    assert summary.total_references == 3
    assert summary.valid_count == 1
    assert summary.unresolved_count == 2
