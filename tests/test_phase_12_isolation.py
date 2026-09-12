"""
Phase 12 tests: India/international corpus isolation and cross-
jurisdiction leakage prevention
(docs/PHASE_12_JURISDICTION_FIREWALL.md Sections K, L, M, N). These are
the adversarial synthetic leakage tests explicitly required.
"""

from __future__ import annotations

from _jurisdiction_fixtures import make_evidence

from jurisdiction.filtering import filter_evidence
from jurisdiction.firewall import resolve_jurisdiction


# ---------------------------------------------------------------------------
# India corpus isolation
# ---------------------------------------------------------------------------


def test_india_request_allows_india_evidence_blocks_international():
    decision = resolve_jurisdiction("ISO1", explicit_jurisdiction="INDIA")
    items = [make_evidence("IN-1", "INDIA"), make_evidence("INTL-1", "INTERNATIONAL")]
    result = filter_evidence(decision, items)
    assert [e.evidence_id for e in result.allowed_evidence] == ["IN-1"]
    assert result.blocked_evidence_ids == ["INTL-1"]


def test_india_request_never_silently_falls_back_to_international():
    # No INDIA evidence is available at all - the firewall must NOT
    # substitute INTERNATIONAL evidence; it blocks everything.
    decision = resolve_jurisdiction("ISO2", explicit_jurisdiction="INDIA")
    items = [make_evidence("INTL-1", "INTERNATIONAL"), make_evidence("INTL-2", "INTERNATIONAL")]
    result = filter_evidence(decision, items)
    assert result.allowed_evidence == []
    assert set(result.blocked_evidence_ids) == {"INTL-1", "INTL-2"}


# ---------------------------------------------------------------------------
# International corpus isolation
# ---------------------------------------------------------------------------


def test_international_request_allows_international_evidence_blocks_india():
    decision = resolve_jurisdiction("ISO3", explicit_jurisdiction="INTERNATIONAL")
    items = [make_evidence("IN-1", "INDIA"), make_evidence("INTL-1", "INTERNATIONAL")]
    result = filter_evidence(decision, items)
    assert [e.evidence_id for e in result.allowed_evidence] == ["INTL-1"]
    assert result.blocked_evidence_ids == ["IN-1"]


def test_international_request_never_silently_falls_back_to_india():
    decision = resolve_jurisdiction("ISO4", explicit_jurisdiction="INTERNATIONAL")
    items = [make_evidence("IN-1", "INDIA"), make_evidence("IN-2", "INDIA")]
    result = filter_evidence(decision, items)
    assert result.allowed_evidence == []
    assert set(result.blocked_evidence_ids) == {"IN-1", "IN-2"}


# ---------------------------------------------------------------------------
# Cross-jurisdiction leakage prevention - mixed corpus, duplicates
# ---------------------------------------------------------------------------


def test_mixed_corpus_india_request_leaks_zero_international_evidence():
    decision = resolve_jurisdiction("ISO5", explicit_jurisdiction="INDIA")
    items = [
        make_evidence("IN-1", "INDIA"), make_evidence("INTL-1", "INTERNATIONAL"),
        make_evidence("IN-2", "INDIA"), make_evidence("INTL-2", "INTERNATIONAL"),
        make_evidence("IN-3", "INDIA"),
    ]
    result = filter_evidence(decision, items)
    assert all(e.jurisdiction == "INDIA" for e in result.allowed_evidence)
    assert len(result.allowed_evidence) == 3


def test_mixed_corpus_international_request_leaks_zero_india_evidence():
    decision = resolve_jurisdiction("ISO6", explicit_jurisdiction="INTERNATIONAL")
    items = [
        make_evidence("IN-1", "INDIA"), make_evidence("INTL-1", "INTERNATIONAL"),
        make_evidence("IN-2", "INDIA"), make_evidence("INTL-2", "INTERNATIONAL"),
    ]
    result = filter_evidence(decision, items)
    assert all(e.jurisdiction == "INTERNATIONAL" for e in result.allowed_evidence)
    assert len(result.allowed_evidence) == 2


def test_duplicate_evidence_across_jurisdictions_each_evaluated_independently():
    decision = resolve_jurisdiction("ISO7", explicit_jurisdiction="INDIA")
    # Same evidence_id appearing twice with different (impossible in
    # practice, but adversarially tested) jurisdiction tags - each
    # occurrence is still independently evaluated, never merged.
    items = [make_evidence("DUP-1", "INDIA"), make_evidence("DUP-1", "INTERNATIONAL")]
    result = filter_evidence(decision, items)
    assert len(result.allowed_evidence) == 1
    assert result.allowed_evidence[0].jurisdiction == "INDIA"
    assert result.blocked_evidence_ids == ["DUP-1"]


def test_reverse_direction_leakage_test_both_ways():
    india_decision = resolve_jurisdiction("ISO8A", explicit_jurisdiction="INDIA")
    intl_decision = resolve_jurisdiction("ISO8B", explicit_jurisdiction="INTERNATIONAL")
    items = [make_evidence("IN-1", "INDIA"), make_evidence("INTL-1", "INTERNATIONAL")]

    india_result = filter_evidence(india_decision, items)
    intl_result = filter_evidence(intl_decision, items)

    assert [e.evidence_id for e in india_result.allowed_evidence] == ["IN-1"]
    assert [e.evidence_id for e in intl_result.allowed_evidence] == ["INTL-1"]
    # Zero overlap between what each decision allows.
    india_ids = {e.evidence_id for e in india_result.allowed_evidence}
    intl_ids = {e.evidence_id for e in intl_result.allowed_evidence}
    assert india_ids.isdisjoint(intl_ids)


def test_synthetic_evidence_still_enforces_jurisdiction_isolation():
    # synthetic status and jurisdiction are separate dimensions - a
    # synthetic flag (not modeled on FakeEvidence at all here, since
    # filtering.py only ever reads jurisdiction/evidence_id) must never
    # substitute for or bypass jurisdiction enforcement.
    decision = resolve_jurisdiction("ISO9", explicit_jurisdiction="INDIA")
    items = [make_evidence("SYN-IN", "INDIA"), make_evidence("SYN-INTL", "INTERNATIONAL")]
    result = filter_evidence(decision, items)
    assert [e.evidence_id for e in result.allowed_evidence] == ["SYN-IN"]


def test_large_mixed_corpus_leakage_is_exactly_zero():
    decision = resolve_jurisdiction("ISO10", explicit_jurisdiction="INDIA")
    items = [make_evidence(f"E{i}", "INDIA" if i % 3 == 0 else "INTERNATIONAL") for i in range(300)]
    result = filter_evidence(decision, items)
    leaked_international = [e for e in result.allowed_evidence if e.jurisdiction != "INDIA"]
    assert leaked_international == []
    assert len(result.allowed_evidence) == len([i for i in range(300) if i % 3 == 0])
