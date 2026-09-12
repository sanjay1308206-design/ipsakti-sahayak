"""
Phase 10 tests: grounding primitives - citation-marker extraction and
EvidencePack-context reading (docs/PHASE_10_GROUNDED_GENERATION.md
Sections F, G, J).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _generation_fixtures import make_pack_from_texts

from citation.models import CitationReference
from generation.grounding import allowed_evidence_ids, evidence_context_items, extract_citation_references

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# extract_citation_references
# ---------------------------------------------------------------------------


def test_extracts_zero_markers_from_plain_text():
    assert extract_citation_references("A plain answer with no citations.") == []


def test_extracts_one_marker():
    refs = extract_citation_references("Answer. [[CITE:abc123]]")
    assert len(refs) == 1
    assert isinstance(refs[0], CitationReference)
    assert refs[0].evidence_id == "abc123"


def test_extracts_multiple_markers_in_order():
    refs = extract_citation_references("First [[CITE:id-1]] then [[CITE:id-2]] then [[CITE:id-3]]")
    assert [r.evidence_id for r in refs] == ["id-1", "id-2", "id-3"]


def test_extracts_duplicate_markers_as_separate_references():
    refs = extract_citation_references("[[CITE:same-id]] and again [[CITE:same-id]]")
    assert [r.evidence_id for r in refs] == ["same-id", "same-id"]


def test_empty_marker_is_extracted_as_empty_string_not_crashed():
    refs = extract_citation_references("[[CITE:]]")
    assert len(refs) == 1
    assert refs[0].evidence_id == ""


def test_marker_content_is_never_executed_or_interpreted():
    refs = extract_citation_references("[[CITE:'; DROP TABLE evidence; --]]")
    assert refs[0].evidence_id == "'; DROP TABLE evidence; --"


def test_marker_cannot_span_a_closing_bracket():
    # A stray `]` inside a marker (before the terminating `]]`) means the
    # negated-character-class pattern can never complete a match at all -
    # the malformed marker is safely ignored entirely, never partially
    # or incorrectly parsed as "abc".
    refs = extract_citation_references("[[CITE:abc]def]]")
    assert refs == []


def test_extract_citation_references_rejects_non_string():
    with pytest.raises(TypeError):
        extract_citation_references(12345)


def test_large_number_of_markers_does_not_crash():
    text = " ".join(f"[[CITE:id-{i}]]" for i in range(2000))
    refs = extract_citation_references(text)
    assert len(refs) == 2000


# ---------------------------------------------------------------------------
# allowed_evidence_ids / evidence_context_items
# ---------------------------------------------------------------------------


def test_allowed_evidence_ids_matches_pack_contents(authority_matrix):
    pack = make_pack_from_texts(
        [("D-GR-1", "Trademark content."), ("D-GR-2", "Patent content.")], authority_matrix
    )
    ids = allowed_evidence_ids(pack)
    assert ids == {e.evidence_id for e in pack.evidence_items}


def test_allowed_evidence_ids_rejects_non_pack():
    with pytest.raises(TypeError):
        allowed_evidence_ids("not a pack")


def test_evidence_context_items_preserves_pack_order(authority_matrix):
    pack = make_pack_from_texts(
        [("D-GR-3", "Trademark content."), ("D-GR-4", "Patent content."), ("D-GR-5", "Ayurveda content.")],
        authority_matrix,
    )
    items = evidence_context_items(pack)
    assert [e.evidence_id for e in items] == [e.evidence_id for e in pack.evidence_items]


def test_evidence_context_items_respects_max_items(authority_matrix):
    pack = make_pack_from_texts(
        [("D-GR-6", "Trademark content."), ("D-GR-7", "Patent content.")], authority_matrix
    )
    items = evidence_context_items(pack, max_items=1)
    assert len(items) == 1
    assert items[0].evidence_id == pack.evidence_items[0].evidence_id


def test_evidence_context_items_rejects_non_pack():
    with pytest.raises(TypeError):
        evidence_context_items("not a pack")
