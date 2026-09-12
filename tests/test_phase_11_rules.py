"""
Phase 11 tests: extraction keyword rules and the decision-tree evaluator
(docs/PHASE_11_FORMULATION_CLASSIFICATION.md Sections E, I). The tree
evaluator is cross-checked directly against Phase 1's own test-only
reference implementation (tests/_decision_tree_reference_impl.py) to
prove the documented duplication has not drifted.
"""

from __future__ import annotations

import itertools

import _decision_tree_reference_impl as phase1_reference

from classification.models import (
    EVIDENCE_STATE_VALUES,
    JURISDICTION_VALUES,
    REGULATORY_QUESTION_TYPE_VALUES,
    REGULATORY_TRACK_VALUES,
    USER_INTENT_VALUES,
)
from classification.rules import (
    RULE_ORDER,
    evaluate_tree,
    extract_abs_tk_relation,
    extract_ip_protection_category,
    extract_jurisdiction,
    extract_regulatory_question_type,
    extract_regulatory_track,
    extract_user_intent,
)


# ---------------------------------------------------------------------------
# Decision tree: exact cross-check against Phase 1's own reference impl
# ---------------------------------------------------------------------------


def test_rule_order_matches_phase_1_contract():
    assert RULE_ORDER == ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8")


def test_tree_evaluator_matches_phase_1_reference_impl_on_exhaustive_grid():
    # A representative grid, not the full cross-product (which would be
    # large) - covers every rule's firing condition and the default path.
    user_intents = sorted(USER_INTENT_VALUES)
    tracks = sorted(REGULATORY_TRACK_VALUES)
    jurisdictions = sorted(JURISDICTION_VALUES)
    rqs = sorted(REGULATORY_QUESTION_TYPE_VALUES) + ["TOTALLY_UNRECOGNIZED"]
    evidence_states = sorted(EVIDENCE_STATE_VALUES)

    checked = 0
    for user_intent, track, jurisdiction, rq, evidence_state in itertools.islice(
        itertools.product(user_intents, tracks, jurisdictions, rqs, evidence_states), 0, 4000
    ):
        ours = evaluate_tree(user_intent, track, jurisdiction, rq, evidence_state)
        theirs = phase1_reference.evaluate(
            phase1_reference.ClassificationInput(
                user_intent=user_intent,
                formulation_regulatory_track=track,
                jurisdiction=jurisdiction,
                regulatory_question_type=rq,
                evidence_state=evidence_state,
            )
        )
        assert ours.classification_state == theirs.classification_state, (user_intent, track, jurisdiction, rq, evidence_state)
        assert ours.rule_id == theirs.rule_id
        assert ours.reason_codes == theirs.reason_codes
        assert ours.requires_evidence == theirs.requires_evidence
        assert ours.requires_escalation == theirs.requires_escalation
        checked += 1
    assert checked > 0


def test_r1_missing_user_intent():
    result = evaluate_tree("UNDETERMINED", "CLASSICAL_AYURVEDIC_DRUG", "INDIA", "AYUSH_POLICY", "NOT_YET_EVALUATED")
    assert result.classification_state == "UNKNOWN"
    assert result.rule_id == "R1"


def test_r2_missing_jurisdiction():
    result = evaluate_tree("GENERAL_INFORMATION_REQUEST", "CLASSICAL_AYURVEDIC_DRUG", "UNSPECIFIED", "AYUSH_POLICY", "NOT_YET_EVALUATED")
    assert result.classification_state == "UNKNOWN"
    assert result.rule_id == "R2"


def test_r3_missing_formulation_info_for_evidence_requiring_intent():
    result = evaluate_tree("DETERMINE_REGULATORY_CLASSIFICATION", "UNDETERMINED", "INDIA", "AYUSH_POLICY", "NOT_YET_EVALUATED")
    assert result.classification_state == "UNKNOWN"
    assert result.rule_id == "R3"


def test_r4_conflicting_formulation_signals():
    result = evaluate_tree("GENERAL_INFORMATION_REQUEST", "CONFLICTING", "INDIA", "AYUSH_POLICY", "NOT_YET_EVALUATED")
    assert result.classification_state == "AMBIGUOUS"
    assert result.rule_id == "R4"


def test_r5_ambiguous_user_intent():
    result = evaluate_tree("AMBIGUOUS_INTENT", "COSMETIC", "INDIA", "AYUSH_POLICY", "NOT_YET_EVALUATED")
    assert result.classification_state == "AMBIGUOUS"
    assert result.rule_id == "R5"


def test_r6_unrecognized_regulatory_question_type():
    result = evaluate_tree("GENERAL_INFORMATION_REQUEST", "COSMETIC", "INDIA", "UNDETERMINED", "NOT_YET_EVALUATED")
    assert result.classification_state == "UNKNOWN"
    assert result.rule_id == "R6"


def test_r7_evidence_not_available():
    result = evaluate_tree("DETERMINE_REGULATORY_CLASSIFICATION", "COSMETIC", "INDIA", "AYUSH_POLICY", "NOT_YET_EVALUATED")
    assert result.classification_state == "NEEDS_EVIDENCE"
    assert result.rule_id == "R7"


def test_r8_default_known():
    result = evaluate_tree("GENERAL_INFORMATION_REQUEST", "COSMETIC", "INDIA", "AYUSH_POLICY", "NOT_YET_EVALUATED")
    assert result.classification_state == "KNOWN"
    assert result.rule_id == "R8"
    assert result.reason_codes == []


def test_evidence_requiring_intent_with_sufficient_evidence_reaches_known():
    result = evaluate_tree("DETERMINE_REGULATORY_CLASSIFICATION", "COSMETIC", "INDIA", "AYUSH_POLICY", "SUFFICIENT_EVIDENCE")
    assert result.classification_state == "KNOWN"


# ---------------------------------------------------------------------------
# Extraction rules
# ---------------------------------------------------------------------------


def test_extract_regulatory_track_single_match():
    result = extract_regulatory_track("this is a cosmetic product")
    assert result.value == "COSMETIC"
    assert result.state == "KNOWN"
    assert result.matched_rule_ids == ["RT-05"]


def test_extract_regulatory_track_no_match():
    result = extract_regulatory_track("nothing relevant here")
    assert result.value == "UNDETERMINED"
    assert result.state == "UNKNOWN"


def test_extract_regulatory_track_conflicting_match():
    result = extract_regulatory_track("this is a cosmetic and also a phytopharmaceutical")
    assert result.value == "CONFLICTING"
    assert result.state == "AMBIGUOUS"
    assert set(result.matched_rule_ids) == {"RT-05", "RT-06"}


def test_extract_ip_protection_category_no_conflicting_state_falls_back_to_undetermined():
    result = extract_ip_protection_category("i want a patent and also a trademark")
    assert result.value == "UNDETERMINED"
    assert result.state == "UNKNOWN"
    assert set(result.matched_rule_ids) == {"IP-01", "IP-02"}


def test_extract_ip_protection_category_single_match():
    result = extract_ip_protection_category("i want a patent")
    assert result.value == "PATENT"
    assert result.state == "KNOWN"


def test_extract_abs_tk_relation_single_match():
    result = extract_abs_tk_relation("this relates to traditional knowledge")
    assert result.value == "TRADITIONAL_KNOWLEDGE_RELATED"
    assert result.state == "KNOWN"


def test_extract_regulatory_question_type_single_match():
    result = extract_regulatory_question_type("what does fssai require")
    assert result.value == "AYURVEDA_AAHARA_FOOD_LAW"


def test_extract_jurisdiction_india_only():
    result = extract_jurisdiction("this concerns india")
    assert result.value == "INDIA"


def test_extract_jurisdiction_international_only():
    result = extract_jurisdiction("this is an international matter")
    assert result.value == "INTERNATIONAL"


def test_extract_jurisdiction_both():
    result = extract_jurisdiction("this concerns india and also international matters")
    assert result.value == "BOTH"
    assert result.state == "KNOWN"  # BOTH is a resolved value, not an unresolved conflict


def test_extract_jurisdiction_none():
    result = extract_jurisdiction("no jurisdiction mentioned")
    assert result.value == "UNSPECIFIED"
    assert result.state == "UNKNOWN"


def test_extract_user_intent_single_match():
    result = extract_user_intent("what compliance requirement applies to me", "what compliance requirement applies to me")
    assert result.value == "CHECK_COMPLIANCE_REQUIREMENT"


def test_extract_user_intent_ambiguous_multiple_matches():
    text = "how can i protect this and what compliance requirement applies"
    result = extract_user_intent(text, text)
    assert result.value == "AMBIGUOUS_INTENT"
    assert result.state == "AMBIGUOUS"


def test_extract_user_intent_defaults_to_general_information_when_nonempty():
    result = extract_user_intent("some unrelated question text", "some unrelated question text")
    assert result.value == "GENERAL_INFORMATION_REQUEST"
    assert result.state == "KNOWN"


def test_extract_user_intent_undetermined_when_empty():
    result = extract_user_intent("", "")
    assert result.value == "UNDETERMINED"
    assert result.state == "UNKNOWN"
