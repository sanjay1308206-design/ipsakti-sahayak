"""
Phase 12 tests: deterministic decisions
(docs/PHASE_12_JURISDICTION_FIREWALL.md Section X). Identical input,
classification result, and configuration must produce identical decision,
decision identity, and serialized JSON.
"""

from __future__ import annotations

from _jurisdiction_fixtures import classify_query, make_evidence

from jurisdiction.filtering import filter_evidence
from jurisdiction.firewall import resolve_jurisdiction
from jurisdiction.serialize import jurisdiction_decision_to_json


def test_repeated_resolution_is_identical():
    decisions = [resolve_jurisdiction("DET1", explicit_jurisdiction="INDIA") for _ in range(10)]
    assert all(d == decisions[0] for d in decisions)


def test_repeated_resolution_decision_id_is_identical():
    ids = {resolve_jurisdiction("DET2", explicit_jurisdiction="INDIA").decision_id for _ in range(10)}
    assert len(ids) == 1


def test_repeated_resolution_json_is_byte_identical():
    jsons = {jurisdiction_decision_to_json(resolve_jurisdiction("DET3", explicit_jurisdiction="INDIA")) for _ in range(10)}
    assert len(jsons) == 1


def test_decision_id_differs_for_different_requested_jurisdictions():
    d1 = resolve_jurisdiction("DET4", explicit_jurisdiction="INDIA")
    d2 = resolve_jurisdiction("DET4", explicit_jurisdiction="INTERNATIONAL")
    assert d1.decision_id != d2.decision_id


def test_decision_id_differs_for_different_input_ids():
    d1 = resolve_jurisdiction("DET5A", explicit_jurisdiction="INDIA")
    d2 = resolve_jurisdiction("DET5B", explicit_jurisdiction="INDIA")
    assert d1.decision_id != d2.decision_id
    assert d1.state == d2.state == "KNOWN"


def test_classification_driven_decision_is_deterministic():
    decisions = []
    for _ in range(5):
        cls = classify_query("DET6", "What category applies in India under FSSAI?")
        decisions.append(resolve_jurisdiction("DET6D", classification_result=cls))
    assert all(d == decisions[0] for d in decisions)


def test_filter_evidence_result_is_deterministic():
    decision = resolve_jurisdiction("DET7", explicit_jurisdiction="INDIA")
    items = [make_evidence("E1", "INDIA"), make_evidence("E2", "INTERNATIONAL"), make_evidence("E3", "MARS")]
    results = [filter_evidence(decision, items) for _ in range(5)]
    first = results[0]
    for r in results[1:]:
        assert [e.evidence_id for e in r.allowed_evidence] == [e.evidence_id for e in first.allowed_evidence]
        assert r.blocked_evidence_ids == first.blocked_evidence_ids
        assert r.block_reasons == first.block_reasons


def test_ambiguous_decision_is_deterministic():
    def build():
        cls = classify_query("DET8", "What category applies in India under FSSAI?")
        return resolve_jurisdiction("DET8D", classification_result=cls, explicit_jurisdiction="INTERNATIONAL")

    decisions = [build() for _ in range(5)]
    assert all(d == decisions[0] for d in decisions)
    assert decisions[0].state == "AMBIGUOUS"
