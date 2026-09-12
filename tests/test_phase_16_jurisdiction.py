"""
Phase 16 tests: the HIGH-PRIORITY jurisdiction-isolation benchmark
(docs/PHASE_16_EVALUATION_AND_RED_TEAM.md Section M). Calls the REAL
`jurisdiction.firewall.resolve_jurisdiction`/`jurisdiction.filtering.filter_evidence`
- never a re-derived firewall.
"""

from __future__ import annotations

from _jurisdiction_fixtures import make_evidence

from evaluation.benchmark import score_jurisdiction_leakage
from jurisdiction.filtering import filter_evidence
from jurisdiction.firewall import resolve_jurisdiction

MIXED_EVIDENCE = [
    make_evidence("E-INDIA-1", "INDIA"),
    make_evidence("E-INDIA-2", "INDIA"),
    make_evidence("E-INTL-1", "INTERNATIONAL"),
    make_evidence("E-INTL-2", "INTERNATIONAL"),
]


def _leakage(decision, evidence_items):
    result = filter_evidence(decision, evidence_items)
    prohibited_ids = {e.evidence_id for e in evidence_items if e.jurisdiction in decision.blocked_jurisdictions}
    leaked_ids = prohibited_ids & set(result.allowed_evidence and [e.evidence_id for e in result.allowed_evidence] or [])
    return result, len(prohibited_ids), len(leaked_ids)


# 1. India request -> no international-only evidence leakage
def test_india_request_has_no_international_leakage():
    decision = resolve_jurisdiction("J1", explicit_jurisdiction="INDIA")
    result, prohibited, leaked = _leakage(decision, MIXED_EVIDENCE)
    assert leaked == 0
    metric = score_jurisdiction_leakage(["J1"], prohibited, leaked)
    assert metric.applicable is True
    assert metric.value == 0.0


# 2. International request -> no India-only evidence leakage
def test_international_request_has_no_india_leakage():
    decision = resolve_jurisdiction("J2", explicit_jurisdiction="INTERNATIONAL")
    result, prohibited, leaked = _leakage(decision, MIXED_EVIDENCE)
    assert leaked == 0
    allowed_ids = {e.evidence_id for e in result.allowed_evidence}
    assert allowed_ids == {"E-INTL-1", "E-INTL-2"}


# 3. BOTH -> both permitted
def test_both_jurisdiction_permits_all_evidence():
    decision = resolve_jurisdiction("J3", explicit_jurisdiction="BOTH")
    result = filter_evidence(decision, MIXED_EVIDENCE)
    assert {e.evidence_id for e in result.allowed_evidence} == {e.evidence_id for e in MIXED_EVIDENCE}
    assert result.blocked_evidence_ids == []


# 4. UNSPECIFIED -> fail-closed
def test_unspecified_jurisdiction_fails_closed():
    decision = resolve_jurisdiction("J4", explicit_jurisdiction="UNSPECIFIED")
    result = filter_evidence(decision, MIXED_EVIDENCE)
    assert result.allowed_evidence == []
    assert len(result.blocked_evidence_ids) == len(MIXED_EVIDENCE)


# 5. malformed jurisdiction -> fail-closed
def test_malformed_jurisdiction_signal_fails_closed():
    decision = resolve_jurisdiction("J5", explicit_jurisdiction="FRANCE")
    result = filter_evidence(decision, MIXED_EVIDENCE)
    assert result.allowed_evidence == []


def test_malformed_evidence_jurisdiction_fails_closed():
    decision = resolve_jurisdiction("J5B", explicit_jurisdiction="INDIA")
    malformed_evidence = [make_evidence("E-BAD", "FRANCE")]
    result = filter_evidence(decision, malformed_evidence)
    assert result.allowed_evidence == []
    assert result.blocked_evidence_ids == ["E-BAD"]


# 6. missing jurisdiction -> fail-closed
def test_missing_jurisdiction_signal_fails_closed():
    decision = resolve_jurisdiction("J6")
    result = filter_evidence(decision, MIXED_EVIDENCE)
    assert result.allowed_evidence == []
    assert decision.state == "UNKNOWN"


# 7. language/script cannot alter jurisdiction
def test_language_and_script_cannot_alter_jurisdiction_decision():
    from multilingual.preservation import detect_script

    hindi_script = detect_script("आयुर्वेद औषधि पंजीकरण")
    assert hindi_script == "DEVANAGARI"
    # No jurisdiction API in this project accepts a script/language parameter at all.
    import inspect

    sig = inspect.signature(resolve_jurisdiction)
    assert "language" not in sig.parameters
    assert "script" not in sig.parameters


# JURISDICTION_LEAKAGE_RATE
def test_jurisdiction_leakage_rate_not_applicable_when_nothing_presented():
    metric = score_jurisdiction_leakage([], 0, 0)
    assert metric.applicable is False


def test_jurisdiction_leakage_rate_surfaces_a_single_leaked_item():
    # A deliberately malformed EvidenceFilterResult scenario cannot be
    # constructed through the real filter_evidence path (which never
    # leaks) - this proves the METRIC ITSELF correctly surfaces a single
    # leak rather than rounding it away, using a hypothetical count.
    metric = score_jurisdiction_leakage(["J-HYPOTHETICAL"], prohibited_ids_seen=4, prohibited_ids_leaked=1)
    assert metric.applicable is True
    assert metric.value == 0.25
    assert metric.numerator == 1
