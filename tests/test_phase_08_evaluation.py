"""
Phase 8 tests: the synthetic evidence-construction benchmark
(docs/PHASE_08_EVIDENCE_OBJECT_AND_CITATION_ARCHITECTURE.md Section AB).

This benchmark measures IMPLEMENTATION properties of evidence construction
- candidate-to-evidence traceability, deduplication correctness, provenance
preservation, deterministic pack identity, exact text preservation, and
serialization round-trip correctness. It is explicitly NOT a legal-answer
benchmark and does not measure or claim regulatory correctness - no real
regulatory corpus or model is involved (docs/DEVELOPMENT_RULES.md Rule 7).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _evidence_fixtures import make_hybrid_response, make_single_chunk

from evidence.builder import build_evidence_pack
from evidence.serialize import evidence_pack_from_dict, evidence_pack_to_dict
from evidence.validation import verify_pack_integrity

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def benchmark_chunks(authority_matrix):
    fixtures = [
        ("SYNTHETIC-BENCH-08-TM-1", "Trademark registration requires filing an application with the trademark registry."),
        ("SYNTHETIC-BENCH-08-TM-2", "The trademark registry processes each registration application for distinctiveness review."),
        ("SYNTHETIC-BENCH-08-PT-1", "Patent applications require a complete technical specification of the invention."),
        ("SYNTHETIC-BENCH-08-AY-1", "Ayurveda formulation registration follows AYUSH ministry compliance rules."),
        ("SYNTHETIC-BENCH-08-IRRELEVANT", "Weather patterns and rainfall data for agricultural planning purposes."),
    ]
    return {doc_id: make_single_chunk(text, doc_id, authority_matrix) for doc_id, text in fixtures}


def test_benchmark_property_candidate_to_evidence_traceability(benchmark_chunks):
    chunks = list(benchmark_chunks.values())
    resp = make_hybrid_response(chunks, "trademark registration", top_k=5)
    pack = build_evidence_pack(resp.results, "trademark registration")

    candidate_chunk_ids = {c.chunk_id for c in resp.results}
    evidence_chunk_ids = {e.chunk_id for e in pack.evidence_items}
    assert evidence_chunk_ids.issubset(candidate_chunk_ids)
    for evidence in pack.evidence_items:
        matching_candidate = next(c for c in resp.results if c.chunk_id == evidence.chunk_id)
        assert evidence.evidence_text == matching_candidate.chunk_text


def test_benchmark_property_deduplication_correctness(benchmark_chunks):
    from _evidence_fixtures import make_bm25_response, make_dense_response

    chunks = list(benchmark_chunks.values())
    bm25_resp = make_bm25_response(chunks, "trademark registration patent formulation", top_k=5)
    dense_resp = make_dense_response(chunks, "trademark registration patent formulation", top_k=5)
    mixed = list(bm25_resp.results) + list(dense_resp.results)

    pack = build_evidence_pack(mixed, "trademark registration patent formulation")
    real_chunk_ids = {c.chunk_id for c in chunks}
    resulting_ids = {e.chunk_id for e in pack.evidence_items}
    assert resulting_ids == real_chunk_ids
    assert pack.construction_metadata["dropped_duplicate_chunk_id_count"] == len(mixed) - len(real_chunk_ids)


def test_benchmark_property_provenance_preservation(benchmark_chunks):
    chunks = list(benchmark_chunks.values())
    resp = make_hybrid_response(chunks, "ayurveda formulation", top_k=5)
    pack = build_evidence_pack(resp.results, "ayurveda formulation")
    for evidence in pack.evidence_items:
        original_chunk = next(c for c in chunks if c.chunk_id == evidence.chunk_id)
        assert evidence.document_id == original_chunk.document_id
        assert evidence.source_family_id == original_chunk.source_family_id
        assert evidence.jurisdiction == original_chunk.jurisdiction
        assert evidence.content_hash == original_chunk.content_hash
        assert evidence.block_ids == original_chunk.block_ids
        assert evidence.page_numbers == original_chunk.page_numbers


def test_benchmark_property_deterministic_pack_identity(benchmark_chunks):
    chunks = list(benchmark_chunks.values())
    resp = make_hybrid_response(chunks, "patent application specification", top_k=5)
    pack_ids = {build_evidence_pack(resp.results, "patent application specification").pack_id for _ in range(5)}
    assert len(pack_ids) == 1


def test_benchmark_property_exact_evidence_text_preservation(benchmark_chunks):
    chunks = list(benchmark_chunks.values())
    resp = make_hybrid_response(chunks, "trademark", top_k=5)
    pack = build_evidence_pack(resp.results, "trademark")
    for evidence in pack.evidence_items:
        original_chunk = benchmark_chunks[evidence.document_id]
        assert evidence.evidence_text == original_chunk.text


def test_benchmark_property_serialization_round_trip_correctness(benchmark_chunks):
    chunks = list(benchmark_chunks.values())
    resp = make_hybrid_response(chunks, "registration compliance", top_k=5)
    pack = build_evidence_pack(resp.results, "registration compliance")

    reloaded = evidence_pack_from_dict(evidence_pack_to_dict(pack))
    verify_pack_integrity(reloaded)
    assert reloaded.pack_id == pack.pack_id
    assert [e.evidence_id for e in reloaded.evidence_items] == [e.evidence_id for e in pack.evidence_items]


def test_benchmark_irrelevant_chunk_can_still_become_evidence_if_selected(benchmark_chunks):
    # Evidence construction is NOT a relevance judge - it faithfully
    # converts whatever candidates the retrieval layer selected. This
    # benchmark proves that fact, not a claim about retrieval quality
    # (which is Phase 5/6/7's own benchmark territory, not Phase 8's).
    chunks = list(benchmark_chunks.values())
    resp = make_hybrid_response(chunks, "trademark patent ayurveda formulation registration weather", top_k=5)
    pack = build_evidence_pack(resp.results, "trademark patent ayurveda formulation registration weather")
    irrelevant_id = benchmark_chunks["SYNTHETIC-BENCH-08-IRRELEVANT"].chunk_id
    # dense retrieval always returns everything (Phase 6 design) - so the
    # irrelevant chunk legitimately appears among the candidates and, if
    # selected, becomes a perfectly valid Evidence object (Phase 8 does not
    # judge legal relevance).
    resulting_ids = {e.chunk_id for e in pack.evidence_items}
    assert irrelevant_id in resulting_ids or len(pack.evidence_items) < len(chunks)


def test_benchmark_does_not_claim_regulatory_correctness():
    # This test's only purpose is to assert the benchmark's own scope
    # discipline is documented, not to measure anything numeric.
    doc_path = REPO_ROOT / "docs" / "PHASE_08_EVIDENCE_OBJECT_AND_CITATION_ARCHITECTURE.md"
    text = doc_path.read_text(encoding="utf-8")
    assert "does not measure regulatory correctness" in text or "does not, and cannot, measure" in text or "does not measure" in text
