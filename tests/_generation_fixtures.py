"""
Phase 10 test-support module: builds real Phase 8 EvidencePack objects
(reusing tests/_evidence_fixtures.py / tests/_citation_fixtures.py) plus
deterministic FakeGenerationProvider instances, for use by
tests/test_phase_10_*.py.

SYNTHETIC TEST FIXTURE GENERATOR ONLY. Not a test module itself (no test_
prefix) - pytest will not collect it.
"""

from __future__ import annotations

from _citation_fixtures import make_pack_from_texts, make_single_chunk

from generation.providers import FakeGenerationProvider

__all__ = [
    "make_pack_from_texts",
    "make_single_chunk",
    "citing_provider",
    "fake_evidence_id_marker",
]


def citing_provider(evidence_id: str, extra_text: str = "This is the grounded answer.") -> FakeGenerationProvider:
    """A deterministic provider that always cites exactly one given evidence_id."""
    return FakeGenerationProvider(response_text=f"{extra_text} [[CITE:{evidence_id}]]")


def fake_evidence_id_marker(evidence_id: str) -> str:
    return f"[[CITE:{evidence_id}]]"
