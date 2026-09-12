"""
Phase 13 tests: multilingual metadata preservation and the
language-is-not-safety/jurisdiction invariant
(docs/PHASE_13_CONFIDENCE_SAFETY_ABSTENTION.md Section V). No translation
exists anywhere in this phase; safety/jurisdiction is never inferred from
which script a query happens to use.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from _safety_fixtures import make_classification, make_grounded_response, make_jurisdiction

from generation.providers import FakeGenerationProvider
from safety.evaluator import evaluate_safety

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "authority_matrix.yaml").read_text(encoding="utf-8"))


def test_devanagari_query_does_not_crash(authority_matrix):
    cls = make_classification("ML1", raw_query="मेरे उत्पाद के लिए कौन सी नियामक श्रेणी लागू होती है?")
    decision = evaluate_safety("ML1D", classification_result=cls)
    assert decision.safety_status in {"SAFE_TO_PRESENT", "ABSTAIN", "ESCALATE"}


def test_tamil_query_does_not_crash(authority_matrix):
    cls = make_classification("ML2", raw_query="எனது தயாரிப்புக்கு எந்த ஒழுங்குமுறை வகை பொருந்தும்?")
    decision = evaluate_safety("ML2D", classification_result=cls)
    assert decision.safety_status in {"SAFE_TO_PRESENT", "ABSTAIN", "ESCALATE"}


def test_devanagari_query_without_jurisdiction_keyword_is_not_treated_as_india(authority_matrix):
    cls = make_classification("ML3", raw_query="आयुर्वेद औषधि पंजीकरण के लिए आवेदन आवश्यक है")
    jur = make_jurisdiction("ML3J", classification_result=cls)
    assert jur.state == "UNKNOWN"  # no explicit English "india"/"international" keyword
    # Note: Phase 1's own decision tree rule R2 (MISSING_JURISDICTION)
    # already sets classification_state=UNKNOWN whenever no jurisdiction
    # keyword is found, so Phase 13's G2 (classification, checked before
    # G4/jurisdiction in the fixed gate order) fires first here - the
    # important safety property is that this NEVER becomes SAFE_TO_PRESENT
    # regardless of which specific gate ultimately catches it.
    decision = evaluate_safety("ML3D", classification_result=cls, jurisdiction_decision=jur)
    assert decision.safety_status == "ABSTAIN"
    assert decision.reason_code in {"CLASSIFICATION_UNRESOLVED", "JURISDICTION_UNRESOLVED"}


def test_mixed_script_evidence_grounds_correctly(authority_matrix):
    pack, gr = make_grounded_response(authority_matrix, [("ML4-D1", "Ayurveda आयुर्वेद மருந்து content.")], "ML4-q")
    assert gr.grounding_status == "GROUNDED"
    decision = evaluate_safety(
        "ML4D",
        classification_result=make_classification("ML4C", raw_query="Tell me about Ministry of Ayush policy in India."),
        jurisdiction_decision=make_jurisdiction("ML4J", explicit_jurisdiction="INDIA"),
        grounded_response=gr,
    )
    assert decision.safety_status == "SAFE_TO_PRESENT"


def test_language_is_never_used_as_a_safety_signal_regression_guard(authority_matrix):
    # Identical semantic content (no jurisdiction keyword) in three
    # scripts must all abstain identically on jurisdiction grounds -
    # never differently based on script/language.
    queries = [
        "What license do I need?",
        "मुझे किस लाइसेंस की आवश्यकता है?",
        "எனக்கு எந்த உரிமம் தேவை?",
    ]
    statuses = []
    for i, q in enumerate(queries):
        cls = make_classification(f"ML5-{i}", raw_query=q)
        jur = make_jurisdiction(f"ML5J-{i}", classification_result=cls)
        decision = evaluate_safety(f"ML5D-{i}", classification_result=cls, jurisdiction_decision=jur)
        statuses.append(decision.safety_status)
    # The safety property under test: no script gets a free pass to
    # SAFE_TO_PRESENT - all three must abstain identically.
    assert statuses == ["ABSTAIN"] * 3


def test_unicode_emoji_input_does_not_crash():
    cls = make_classification("ML6", raw_query="What license do I need? 😀🙏")
    decision = evaluate_safety("ML6D", classification_result=cls)
    assert decision.safety_status in {"SAFE_TO_PRESENT", "ABSTAIN", "ESCALATE"}
