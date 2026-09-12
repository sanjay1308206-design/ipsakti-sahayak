"""
Phase 8 tests: evidence text integrity, tamper detection (evidence_id,
evidence_text_hash, pack_id), and structural validation failures
(docs/PHASE_08_EVIDENCE_OBJECT_AND_CITATION_ARCHITECTURE.md Section I/X/Y).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
import yaml
from _evidence_fixtures import make_hybrid_response, make_single_chunk

from evidence.builder import build_evidence_pack, resolve_citation_target
from evidence.models import (
    CitationTarget,
    Evidence,
    EvidenceIntegrityError,
    EvidenceNotFoundError,
    EvidencePack,
    RetrievalMetadata,
    VersionInfo,
)
from evidence.validation import (
    verify_evidence_identity,
    verify_evidence_text_integrity,
    verify_pack_identity,
    verify_pack_integrity,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def _sample_pack(authority_matrix):
    chunk = make_single_chunk("Trademark registration evidence integrity content.", "D-INTEGRITY", authority_matrix)
    resp = make_hybrid_response([chunk], "trademark registration", top_k=1)
    return build_evidence_pack(resp.results, "trademark registration")


# ---------------------------------------------------------------------------
# Text integrity (exact equality + hash)
# ---------------------------------------------------------------------------


def test_evidence_text_exactly_equals_candidate_chunk_text(authority_matrix):
    chunk = make_single_chunk("Exact text equality must be preserved verbatim here.", "D-EXACT", authority_matrix)
    resp = make_hybrid_response([chunk], "exact text equality", top_k=1)
    pack = build_evidence_pack(resp.results, "exact text equality")
    assert pack.evidence_items[0].evidence_text == resp.results[0].chunk_text


def test_evidence_text_hash_is_correct(authority_matrix):
    import hashlib

    pack = _sample_pack(authority_matrix)
    evidence = pack.evidence_items[0]
    assert evidence.evidence_text_hash == hashlib.sha256(evidence.evidence_text.encode("utf-8")).hexdigest()


def test_verify_evidence_text_integrity_passes_for_untampered_evidence(authority_matrix):
    pack = _sample_pack(authority_matrix)
    verify_evidence_text_integrity(pack.evidence_items[0])  # must not raise


def test_verify_evidence_text_integrity_detects_tampered_text(authority_matrix):
    pack = _sample_pack(authority_matrix)
    evidence = pack.evidence_items[0]
    tampered = dataclasses.replace(evidence, evidence_text="This text was tampered with after construction.")
    with pytest.raises(EvidenceIntegrityError):
        verify_evidence_text_integrity(tampered)


def test_verify_evidence_identity_detects_tampered_evidence_id(authority_matrix):
    pack = _sample_pack(authority_matrix)
    evidence = pack.evidence_items[0]
    tampered = dataclasses.replace(evidence, evidence_id="0" * 64)
    with pytest.raises(EvidenceIntegrityError):
        verify_evidence_identity(tampered)


def test_verify_evidence_identity_detects_tampered_provenance(authority_matrix):
    pack = _sample_pack(authority_matrix)
    evidence = pack.evidence_items[0]
    # evidence_id unchanged, but document_id changed underneath it -
    # identity no longer matches its own recomputed value.
    tampered = dataclasses.replace(evidence, document_id="A-DIFFERENT-DOCUMENT")
    with pytest.raises(EvidenceIntegrityError):
        verify_evidence_identity(tampered)


def test_verify_pack_identity_detects_tampered_pack_id(authority_matrix):
    pack = _sample_pack(authority_matrix)
    tampered = dataclasses.replace(pack, pack_id="0" * 64)
    with pytest.raises(EvidenceIntegrityError):
        verify_pack_identity(tampered)


def test_verify_pack_identity_requires_config_signature_in_metadata(authority_matrix):
    pack = _sample_pack(authority_matrix)
    stripped_metadata = dict(pack.construction_metadata)
    del stripped_metadata["config_signature"]
    tampered = dataclasses.replace(pack, construction_metadata=stripped_metadata)
    with pytest.raises(EvidenceIntegrityError):
        verify_pack_identity(tampered)


def test_verify_pack_integrity_passes_for_untampered_pack(authority_matrix):
    pack = _sample_pack(authority_matrix)
    verify_pack_integrity(pack)  # must not raise


def test_verify_pack_integrity_detects_tampering_in_any_item(authority_matrix):
    chunks = [
        make_single_chunk("First trademark content.", "D-MULTI-1", authority_matrix),
        make_single_chunk("Second trademark content.", "D-MULTI-2", authority_matrix),
    ]
    resp = make_hybrid_response(chunks, "trademark", top_k=2)
    pack = build_evidence_pack(resp.results, "trademark")
    items = list(pack.evidence_items)
    items[1] = dataclasses.replace(items[1], evidence_text="Tampered second item text.")
    tampered_pack = dataclasses.replace(pack, evidence_items=items)
    with pytest.raises(EvidenceIntegrityError):
        verify_pack_integrity(tampered_pack)


def test_verify_pack_integrity_rejects_non_pack_input():
    with pytest.raises(TypeError):
        verify_pack_integrity("not a pack")


# ---------------------------------------------------------------------------
# Structural validation (fails at construction time, in __post_init__)
# ---------------------------------------------------------------------------


def _valid_evidence_kwargs():
    return dict(
        evidence_id="a" * 64,
        evidence_schema_version="1.0.0",
        evidence_type="CHUNK",
        evidence_text="Some evidence text.",
        evidence_text_hash="b" * 64,
        chunk_id="chunk-1",
        document_id="doc-1",
        source_family_id="SF-01",
        jurisdiction="INDIA",
        content_hash="c" * 64,
        synthetic=True,
        page_numbers=[1],
        block_ids=["chunk-1:p1:b1"],
        retrieval_metadata=RetrievalMetadata(rank=1),
        version_info=VersionInfo(),
    )


def test_evidence_rejects_missing_evidence_id():
    kwargs = _valid_evidence_kwargs()
    kwargs["evidence_id"] = ""
    with pytest.raises(ValueError):
        Evidence(**kwargs)


def test_evidence_rejects_empty_evidence_text():
    kwargs = _valid_evidence_kwargs()
    kwargs["evidence_text"] = "   "
    with pytest.raises(ValueError):
        Evidence(**kwargs)


def test_evidence_rejects_invalid_chunk_id():
    kwargs = _valid_evidence_kwargs()
    kwargs["chunk_id"] = ""
    with pytest.raises(ValueError):
        Evidence(**kwargs)


def test_evidence_rejects_missing_page_numbers():
    kwargs = _valid_evidence_kwargs()
    kwargs["page_numbers"] = []
    with pytest.raises(ValueError):
        Evidence(**kwargs)


def test_evidence_rejects_malformed_block_ids():
    kwargs = _valid_evidence_kwargs()
    kwargs["block_ids"] = []
    with pytest.raises(ValueError):
        Evidence(**kwargs)


def test_evidence_rejects_invalid_jurisdiction():
    kwargs = _valid_evidence_kwargs()
    kwargs["jurisdiction"] = ""
    with pytest.raises(ValueError):
        Evidence(**kwargs)


def test_evidence_rejects_invalid_synthetic_flag():
    kwargs = _valid_evidence_kwargs()
    kwargs["synthetic"] = "true"
    with pytest.raises(ValueError):
        Evidence(**kwargs)


def test_evidence_rejects_invalid_content_hash_shape():
    kwargs = _valid_evidence_kwargs()
    kwargs["content_hash"] = "not-a-valid-hash"
    with pytest.raises(ValueError):
        Evidence(**kwargs)


def test_evidence_rejects_invalid_evidence_type():
    kwargs = _valid_evidence_kwargs()
    kwargs["evidence_type"] = "GENERATED_ANSWER"
    with pytest.raises(ValueError):
        Evidence(**kwargs)


def test_evidence_pack_rejects_duplicate_evidence_ids():
    kwargs = _valid_evidence_kwargs()
    e1 = Evidence(**kwargs)
    e2 = Evidence(**{**kwargs, "chunk_id": "chunk-2", "block_ids": ["chunk-2:p1:b1"]})
    # force a duplicate evidence_id despite different chunk_id, to prove
    # EvidencePack itself rejects it even if identity computation were bypassed
    e2 = dataclasses.replace(e2, evidence_id=e1.evidence_id)
    with pytest.raises(ValueError):
        EvidencePack(pack_id="p" * 64, schema_version="1.0.0", query="q", evidence_items=[e1, e2], construction_metadata={})


def test_evidence_pack_rejects_duplicate_underlying_chunk_ids():
    kwargs = _valid_evidence_kwargs()
    e1 = Evidence(**kwargs)
    e2 = dataclasses.replace(e1, evidence_id="f" * 64)  # same chunk_id, different evidence_id
    with pytest.raises(ValueError):
        EvidencePack(pack_id="p" * 64, schema_version="1.0.0", query="q", evidence_items=[e1, e2], construction_metadata={})


# ---------------------------------------------------------------------------
# CitationTarget resolution against fabricated evidence IDs
# ---------------------------------------------------------------------------


def test_resolve_citation_target_finds_real_evidence(authority_matrix):
    pack = _sample_pack(authority_matrix)
    target = CitationTarget(evidence_id=pack.evidence_items[0].evidence_id)
    resolved = resolve_citation_target(target, pack)
    assert resolved.evidence_id == pack.evidence_items[0].evidence_id


def test_resolve_citation_target_rejects_fabricated_evidence_id(authority_matrix):
    pack = _sample_pack(authority_matrix)
    fake_target = CitationTarget(evidence_id="f" * 64)
    with pytest.raises(EvidenceNotFoundError):
        resolve_citation_target(fake_target, pack)


def test_resolve_citation_target_rejects_wrong_types(authority_matrix):
    pack = _sample_pack(authority_matrix)
    with pytest.raises(TypeError):
        resolve_citation_target("not a citation target", pack)
    with pytest.raises(TypeError):
        resolve_citation_target(CitationTarget(evidence_id="x" * 64), "not a pack")
