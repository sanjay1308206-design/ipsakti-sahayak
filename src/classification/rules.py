"""
Phase 11 rule engine (docs/PHASE_11_FORMULATION_CLASSIFICATION.md Sections
E, I). Two distinct rule layers, never conflated:

1. EXTRACTION rules (keyword tables below): map raw/free text onto one
   Phase 1 taxonomy value per dimension. `[OUR ENHANCEMENT]` - the Master
   Reference names the CATEGORIES (e.g. "classical/proprietary/new-drug")
   but never defines the legal criteria that distinguish one from
   another (docs/PHASE_01_DOMAIN_TAXONOMY.md Section C.1's own
   `[ASSUMPTION]`/`[DEFERRED]` note). These keyword tables are therefore
   deliberately LITERAL and NARROW - they only recognize a caller
   explicitly naming a category (or an exact synonym already used by the
   Master Reference itself, e.g. "Aahara"), never an inferred legal
   conclusion from a product name, ingredient list, or general knowledge.
   Zero matches -> the dimension's own UNDETERMINED value. Multiple
   matches -> CONFLICTING/AMBIGUOUS_INTENT where the taxonomy defines
   such a state, else that dimension's own UNDETERMINED value (never an
   arbitrarily-picked match, never an invented new state).

2. The DECISION TREE evaluator (`evaluate_tree`): a production-facing,
   EXACT semantic duplicate of Phase 1's own test-only reference
   evaluator (`tests/_decision_tree_reference_impl.py`) and machine-
   readable contract (`config/regulatory_decision_tree.yaml`). Phase 1's
   own reference implementation is explicitly test-only ("NOT the Phase
   11 Formulation Classification Engine" - its own docstring); Phase 11
   needs a production-facing implementation, so this is a DOCUMENTED
   duplication, per explicit instruction, of the exact same 8 ordered
   rules (R1..R8) - never a re-derivation with different semantics.
   `tests/test_phase_11_regression.py` cross-checks this function against
   the Phase 1 reference implementation directly, on the same inputs, to
   guarantee they never drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import DimensionResult, EVIDENCE_REQUIRING_INTENTS, REGULATORY_QUESTION_TYPE_VALUES

# ---------------------------------------------------------------------------
# Extraction keyword tables - each entry: (taxonomy_id, category_name, keywords)
# ---------------------------------------------------------------------------

REGULATORY_TRACK_KEYWORDS = (
    ("RT-01", "CLASSICAL_AYURVEDIC_DRUG", ("classical ayurvedic", "classical ayurveda")),
    ("RT-02", "PROPRIETARY_AYURVEDIC_DRUG", ("proprietary ayurvedic", "proprietary ayurveda")),
    ("RT-03", "NEW_AYURVEDIC_DRUG", ("new ayurvedic drug", "new ayurveda drug")),
    ("RT-04", "AYURVEDA_AAHARA_FOOD", ("ayurveda aahara", "ayurvedic aahara", "aahara", "ayurvedic food")),
    ("RT-05", "COSMETIC", ("cosmetic",)),
    ("RT-06", "PHYTOPHARMACEUTICAL", ("phytopharmaceutical", "phytopharma")),
)
REGULATORY_TRACK_UNDETERMINED = ("RT-07", "UNDETERMINED")
REGULATORY_TRACK_CONFLICTING = ("RT-08", "CONFLICTING")

IP_PROTECTION_KEYWORDS = (
    ("IP-01", "PATENT", ("patent",)),
    ("IP-02", "TRADEMARK", ("trademark", "trade mark")),
    ("IP-03", "DESIGN", ("industrial design", "design registration", "design protection")),
    ("IP-04", "GEOGRAPHICAL_INDICATION", ("geographical indication", "gi tag", "gi registration")),
)
# IP-05 NONE is deliberately unreachable by this extractor (docs Section
# W/X): asserting "definitely not IP-related" from the mere ABSENCE of a
# keyword would itself be an unjustified inference this heuristic cannot
# safely make - absence of signal always resolves to UNDETERMINED instead.
IP_PROTECTION_UNDETERMINED = ("IP-06", "UNDETERMINED")

ABS_TK_KEYWORDS = (
    ("ATK-01", "TRADITIONAL_KNOWLEDGE_RELATED", ("traditional knowledge",)),
    ("ATK-02", "ACCESS_AND_BENEFIT_SHARING_RELATED", ("access and benefit sharing", "benefit sharing", "genetic resources")),
)
# ATK-03 NOT_RELATED is deliberately unreachable, for the same reason as IP-05 above.
ABS_TK_UNDETERMINED = ("ATK-04", "UNDETERMINED")

REGULATORY_QUESTION_TYPE_KEYWORDS = (
    ("RQ-01", "INDIA_LEGISLATIVE", ("india code", "indian statute", "legislative")),
    (
        "RQ-02",
        "IP_REGISTRATION_AND_SEARCH",
        ("ip india", "patent office", "trademark registry", "patent registration", "trademark registration", "design registration", "gi registration"),
    ),
    ("RQ-03", "AYUSH_POLICY", ("ministry of ayush", "ayush ministry", "ayush policy")),
    ("RQ-04", "TRADITIONAL_DRUG_REGULATION", ("cdsco", "drugs and cosmetics", "traditional drug regulation")),
    ("RQ-05", "AYURVEDA_AAHARA_FOOD_LAW", ("fssai", "food safety")),
    ("RQ-06", "INTERNATIONAL_IP_TREATY", ("wipo", "wipo lex", "international treaty", "patent cooperation treaty")),
    ("RQ-07", "TRADITIONAL_KNOWLEDGE_DATABASE", ("tkdl", "traditional knowledge digital library")),
)
REGULATORY_QUESTION_TYPE_UNDETERMINED = ("RQ-08", "UNDETERMINED")

JURISDICTION_INDIA_KEYWORDS = ("india", "indian")
JURISDICTION_INTERNATIONAL_KEYWORDS = ("international", "worldwide", "wipo")

USER_INTENT_KEYWORDS = (
    (
        "UI-01",
        "DETERMINE_REGULATORY_CLASSIFICATION",
        ("regulatory category", "regulatory classification", "which category does", "what category does", "classify my formulation", "classify this formulation"),
    ),
    (
        "UI-02",
        "DETERMINE_IP_PROTECTION_PATHWAY",
        ("how can i protect", "ip protection", "protect this formulation", "patent this", "trademark this"),
    ),
    (
        "UI-03",
        "CHECK_COMPLIANCE_REQUIREMENT",
        ("compliance requirement", "what requirements apply", "what rules apply", "comply with"),
    ),
    (
        "UI-04",
        "LOOKUP_AUTHORITATIVE_SOURCE",
        ("what does the act say", "what does the rule say", "what does the regulation say", "look up the", "lookup the"),
    ),
)
USER_INTENT_UNDETERMINED = ("UI-08", "UNDETERMINED")
USER_INTENT_AMBIGUOUS = ("UI-07", "AMBIGUOUS_INTENT")
# UI-06 OUT_OF_SCOPE_OR_UNSUPPORTED is deliberately unreachable by this
# extractor, for the same "never assert a negative from silence" reason
# as IP-05/ATK-03 above.
USER_INTENT_GENERAL_DEFAULT = ("UI-05", "GENERAL_INFORMATION_REQUEST")


def _find_matches(text_lower: str, table: tuple) -> list:
    return [(rule_id, name) for rule_id, name, keywords in table if any(kw in text_lower for kw in keywords)]


def _extract_closed_vocabulary_dimension(
    dimension: str, matches: list, undetermined: tuple, conflicting: tuple = None
) -> DimensionResult:
    if not matches:
        _, name = undetermined
        return DimensionResult(
            dimension=dimension, value=name, state="UNKNOWN", matched_rule_ids=[],
            reason=f"no {dimension} keyword signal found in the supplied text",
        )
    if len(matches) == 1:
        rule_id, name = matches[0]
        return DimensionResult(
            dimension=dimension, value=name, state="KNOWN", matched_rule_ids=[rule_id],
            reason=f"matched keyword signal for {name} ({rule_id})",
        )
    matched_names = [name for _, name in matches]
    matched_ids = [rule_id for rule_id, _ in matches]
    if conflicting is not None:
        _, name = conflicting
        return DimensionResult(
            dimension=dimension, value=name, state="AMBIGUOUS", matched_rule_ids=matched_ids,
            reason=f"multiple conflicting {dimension} signals matched with no deterministic tiebreak: {matched_names}",
        )
    _, name = undetermined
    return DimensionResult(
        dimension=dimension, value=name, state="UNKNOWN", matched_rule_ids=matched_ids,
        reason=(
            f"multiple candidate {dimension} signals matched ({matched_names}) but this dimension has no "
            f"deterministic-tiebreak state defined in the Phase 1 taxonomy; treated as unresolved rather than "
            f"arbitrarily choosing one"
        ),
    )


def extract_regulatory_track(combined_lower: str) -> DimensionResult:
    matches = _find_matches(combined_lower, REGULATORY_TRACK_KEYWORDS)
    return _extract_closed_vocabulary_dimension(
        "regulatory_track", matches, REGULATORY_TRACK_UNDETERMINED, REGULATORY_TRACK_CONFLICTING
    )


def extract_ip_protection_category(combined_lower: str) -> DimensionResult:
    matches = _find_matches(combined_lower, IP_PROTECTION_KEYWORDS)
    return _extract_closed_vocabulary_dimension("ip_protection_category", matches, IP_PROTECTION_UNDETERMINED)


def extract_abs_tk_relation(combined_lower: str) -> DimensionResult:
    matches = _find_matches(combined_lower, ABS_TK_KEYWORDS)
    return _extract_closed_vocabulary_dimension("abs_tk_relation", matches, ABS_TK_UNDETERMINED)


def extract_regulatory_question_type(combined_lower: str) -> DimensionResult:
    matches = _find_matches(combined_lower, REGULATORY_QUESTION_TYPE_KEYWORDS)
    return _extract_closed_vocabulary_dimension(
        "regulatory_question_type", matches, REGULATORY_QUESTION_TYPE_UNDETERMINED
    )


def extract_jurisdiction(combined_lower: str) -> DimensionResult:
    india = any(kw in combined_lower for kw in JURISDICTION_INDIA_KEYWORDS)
    international = any(kw in combined_lower for kw in JURISDICTION_INTERNATIONAL_KEYWORDS)
    if india and international:
        return DimensionResult(
            dimension="jurisdiction_input", value="BOTH", state="KNOWN", matched_rule_ids=["JX-01", "JX-02"],
            reason="matched both India and international jurisdiction signals; the question legitimately spans both",
        )
    if india:
        return DimensionResult(
            dimension="jurisdiction_input", value="INDIA", state="KNOWN", matched_rule_ids=["JX-01"],
            reason="matched an India jurisdiction keyword signal",
        )
    if international:
        return DimensionResult(
            dimension="jurisdiction_input", value="INTERNATIONAL", state="KNOWN", matched_rule_ids=["JX-02"],
            reason="matched an international jurisdiction keyword signal",
        )
    return DimensionResult(
        dimension="jurisdiction_input", value="UNSPECIFIED", state="UNKNOWN", matched_rule_ids=[],
        reason="no jurisdiction keyword signal found in the supplied text",
    )


def extract_user_intent(combined_lower: str, raw_query: str) -> DimensionResult:
    matches = _find_matches(combined_lower, USER_INTENT_KEYWORDS)
    if len(matches) >= 2:
        matched_names = [name for _, name in matches]
        matched_ids = [rule_id for rule_id, _ in matches]
        _, name = USER_INTENT_AMBIGUOUS
        return DimensionResult(
            dimension="user_intent", value=name, state="AMBIGUOUS", matched_rule_ids=matched_ids,
            reason=f"multiple conflicting user-intent signals matched with no deterministic tiebreak: {matched_names}",
        )
    if len(matches) == 1:
        rule_id, name = matches[0]
        return DimensionResult(
            dimension="user_intent", value=name, state="KNOWN", matched_rule_ids=[rule_id],
            reason=f"matched keyword signal for {name} ({rule_id})",
        )
    if raw_query.strip():
        rule_id, name = USER_INTENT_GENERAL_DEFAULT
        return DimensionResult(
            dimension="user_intent", value=name, state="KNOWN", matched_rule_ids=[rule_id],
            reason="no specific intent keyword signal found; a non-empty query defaults to the "
            "non-evidence-requiring GENERAL_INFORMATION_REQUEST category",
        )
    _, name = USER_INTENT_UNDETERMINED
    return DimensionResult(
        dimension="user_intent", value=name, state="UNKNOWN", matched_rule_ids=[],
        reason="no raw_query text was supplied; no intent signal available",
    )


# ---------------------------------------------------------------------------
# Decision tree - production-facing duplicate of Phase 1's own test-only
# reference evaluator (see module docstring for why).
# ---------------------------------------------------------------------------

RULE_ORDER = ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8")


@dataclass(frozen=True)
class TreeResult:
    classification_state: str
    rule_id: str
    reason_codes: list
    requires_evidence: bool
    requires_escalation: bool


def _tree_result(state: str, rule_id: str, reasons: list) -> TreeResult:
    return TreeResult(
        classification_state=state,
        rule_id=rule_id,
        reason_codes=list(reasons),
        requires_evidence=(state == "NEEDS_EVIDENCE"),
        requires_escalation=(state == "AMBIGUOUS"),
    )


def evaluate_tree(
    user_intent: str,
    formulation_regulatory_track: str,
    jurisdiction: str,
    regulatory_question_type: str,
    evidence_state: str,
) -> TreeResult:
    """Evaluates R1..R8 in fixed order; first match wins. Exact semantic mirror of config/regulatory_decision_tree.yaml."""
    # R1 - MISSING_USER_INTENT
    if user_intent == "UNDETERMINED":
        return _tree_result("UNKNOWN", "R1", ["MISSING_USER_INTENT"])

    # R2 - MISSING_JURISDICTION
    if jurisdiction == "UNSPECIFIED":
        return _tree_result("UNKNOWN", "R2", ["MISSING_JURISDICTION"])

    # R3 - MISSING_FORMULATION_INFO
    if user_intent in EVIDENCE_REQUIRING_INTENTS and formulation_regulatory_track == "UNDETERMINED":
        return _tree_result("UNKNOWN", "R3", ["MISSING_FORMULATION_INFO"])

    # R4 - CONFLICTING_FORMULATION_SIGNALS
    if formulation_regulatory_track == "CONFLICTING":
        return _tree_result("AMBIGUOUS", "R4", ["CONFLICTING_FORMULATION_SIGNALS"])

    # R5 - AMBIGUOUS_USER_INTENT
    if user_intent == "AMBIGUOUS_INTENT":
        return _tree_result("AMBIGUOUS", "R5", ["AMBIGUOUS_USER_INTENT"])

    # R6 - UNRECOGNIZED_REGULATORY_QUESTION_TYPE
    if regulatory_question_type == "UNDETERMINED" or regulatory_question_type not in REGULATORY_QUESTION_TYPE_VALUES:
        return _tree_result("UNKNOWN", "R6", ["UNRECOGNIZED_REGULATORY_QUESTION_TYPE"])

    # R7 - EVIDENCE_NOT_AVAILABLE
    if user_intent in EVIDENCE_REQUIRING_INTENTS and evidence_state != "SUFFICIENT_EVIDENCE":
        return _tree_result("NEEDS_EVIDENCE", "R7", ["EVIDENCE_NOT_AVAILABLE"])

    # R8 - DEFAULT_KNOWN
    return _tree_result("KNOWN", "R8", [])
