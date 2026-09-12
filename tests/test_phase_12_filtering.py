"""
Phase 12 tests: evidence filtering
(docs/PHASE_12_JURISDICTION_FIREWALL.md Section O). The machine-checkable
invariant this phase exists to provide: no incompatible-jurisdiction
evidence survives into `allowed_evidence`.
"""

from __future__ import annotations

import pytest
from _jurisdiction_fixtures import make_evidence

from jurisdiction.filtering import check_evidence_compatible, filter_evidence
from jurisdiction.firewall import resolve_jurisdiction


def _india_decision():
    return resolve_jurisdiction("D", explicit_jurisdiction="INDIA")


def _international_decision():
    return resolve_jurisdiction("D", explicit_jurisdiction="INTERNATIONAL")


def _both_decision():
    return resolve_jurisdiction("D", explicit_jurisdiction="BOTH")


def _unknown_decision():
    return resolve_jurisdiction("D")


# ---------------------------------------------------------------------------
# check_evidence_compatible
# ---------------------------------------------------------------------------


def test_india_evidence_compatible_with_india_decision():
    decision = _india_decision()
    ok, reason = check_evidence_compatible(decision, make_evidence("E1", "INDIA"))
    assert ok is True
    assert reason is None


def test_international_evidence_incompatible_with_india_decision():
    decision = _india_decision()
    ok, reason = check_evidence_compatible(decision, make_evidence("E2", "INTERNATIONAL"))
    assert ok is False
    assert reason == "CROSS_JURISDICTION_EVIDENCE_BLOCKED"


def test_india_evidence_incompatible_with_international_decision():
    decision = _international_decision()
    ok, reason = check_evidence_compatible(decision, make_evidence("E3", "INDIA"))
    assert ok is False
    assert reason == "CROSS_JURISDICTION_EVIDENCE_BLOCKED"


def test_both_jurisdictions_evidence_compatible_with_both_decision():
    decision = _both_decision()
    ok1, _ = check_evidence_compatible(decision, make_evidence("E4", "INDIA"))
    ok2, _ = check_evidence_compatible(decision, make_evidence("E5", "INTERNATIONAL"))
    assert ok1 is True
    assert ok2 is True


def test_any_evidence_blocked_when_decision_not_known():
    decision = _unknown_decision()
    ok, reason = check_evidence_compatible(decision, make_evidence("E6", "INDIA"))
    assert ok is False
    assert reason == "CORPUS_NOT_PERMITTED"


def test_missing_jurisdiction_metadata_is_blocked():
    decision = _india_decision()
    ok, reason = check_evidence_compatible(decision, make_evidence("E7", ""))
    assert ok is False
    assert reason == "JURISDICTION_METADATA_INVALID"

    ok2, reason2 = check_evidence_compatible(decision, make_evidence("E8", None))
    assert ok2 is False
    assert reason2 == "JURISDICTION_METADATA_INVALID"


def test_unrecognized_evidence_jurisdiction_value_is_blocked():
    decision = _india_decision()
    ok, reason = check_evidence_compatible(decision, make_evidence("E9", "MARS"))
    assert ok is False
    assert reason == "JURISDICTION_METADATA_INVALID"


def test_not_applicable_evidence_never_allowed():
    decision = _both_decision()
    ok, reason = check_evidence_compatible(decision, make_evidence("E10", "NOT_APPLICABLE"))
    assert ok is False
    assert reason == "CROSS_JURISDICTION_EVIDENCE_BLOCKED"


def test_other_unspecified_evidence_never_allowed():
    decision = _both_decision()
    ok, reason = check_evidence_compatible(decision, make_evidence("E11", "OTHER_UNSPECIFIED"))
    assert ok is False
    assert reason == "CROSS_JURISDICTION_EVIDENCE_BLOCKED"


def test_check_evidence_compatible_rejects_wrong_decision_type():
    with pytest.raises(TypeError):
        check_evidence_compatible("not a decision", make_evidence("E12", "INDIA"))


def test_check_evidence_compatible_rejects_evidence_missing_required_attrs():
    decision = _india_decision()
    with pytest.raises(TypeError):
        check_evidence_compatible(decision, object())


# ---------------------------------------------------------------------------
# filter_evidence
# ---------------------------------------------------------------------------


def test_filter_evidence_partitions_correctly():
    decision = _india_decision()
    items = [make_evidence("E1", "INDIA"), make_evidence("E2", "INTERNATIONAL"), make_evidence("E3", "INDIA")]
    result = filter_evidence(decision, items)
    assert [e.evidence_id for e in result.allowed_evidence] == ["E1", "E3"]
    assert result.blocked_evidence_ids == ["E2"]
    assert result.block_reasons == {"E2": "CROSS_JURISDICTION_EVIDENCE_BLOCKED"}
    assert result.allowed_count == 2
    assert result.blocked_count == 1
    assert result.total_count == 3


def test_filter_evidence_preserves_input_order():
    decision = _both_decision()
    items = [make_evidence(f"E{i}", "INDIA" if i % 2 == 0 else "INTERNATIONAL") for i in range(10)]
    result = filter_evidence(decision, items)
    assert [e.evidence_id for e in result.allowed_evidence] == [f"E{i}" for i in range(10)]


def test_filter_evidence_zero_items():
    decision = _india_decision()
    result = filter_evidence(decision, [])
    assert result.allowed_evidence == []
    assert result.blocked_evidence_ids == []
    assert result.total_count == 0


def test_filter_evidence_all_blocked_when_unknown():
    decision = _unknown_decision()
    items = [make_evidence("E1", "INDIA"), make_evidence("E2", "INTERNATIONAL")]
    result = filter_evidence(decision, items)
    assert result.allowed_evidence == []
    assert set(result.blocked_evidence_ids) == {"E1", "E2"}
    assert all(reason == "CORPUS_NOT_PERMITTED" for reason in result.block_reasons.values())


def test_filter_evidence_mixed_valid_and_malformed_metadata():
    decision = _india_decision()
    items = [make_evidence("E1", "INDIA"), make_evidence("E2", ""), make_evidence("E3", "MARS"), make_evidence("E4", "INTERNATIONAL")]
    result = filter_evidence(decision, items)
    assert [e.evidence_id for e in result.allowed_evidence] == ["E1"]
    assert result.block_reasons["E2"] == "JURISDICTION_METADATA_INVALID"
    assert result.block_reasons["E3"] == "JURISDICTION_METADATA_INVALID"
    assert result.block_reasons["E4"] == "CROSS_JURISDICTION_EVIDENCE_BLOCKED"


def test_filter_evidence_rejects_non_list():
    decision = _india_decision()
    with pytest.raises(TypeError):
        filter_evidence(decision, "not a list")


def test_filter_evidence_never_relabels_evidence():
    decision = _india_decision()
    ev = make_evidence("E1", "INTERNATIONAL")
    result = filter_evidence(decision, [ev])
    # The blocked item is excluded, never mutated/relabeled.
    assert result.blocked_evidence_ids == ["E1"]
    assert ev.jurisdiction == "INTERNATIONAL"  # unchanged
