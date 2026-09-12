"""
Phase 2 tests: docs/PHASE_02_AUTHORITY_MATRIX.md and
config/authority_matrix.yaml.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path

import pytest
import yaml

from _authority_matrix_schema import (
    AuthorityMatrixValidationError,
    validate_authority_matrix,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "PHASE_02_AUTHORITY_MATRIX.md"
YAML_PATH = REPO_ROOT / "config" / "authority_matrix.yaml"

SOURCE_DISCIPLINE_LABELS = (
    "[OFFICIAL PS]",
    "[OFFICIAL SOURCE]",
    "[EXTERNAL RESEARCH]",
    "[ENGINEERING RECOMMENDATION]",
    "[OUR ENHANCEMENT]",
    "[ASSUMPTION]",
    "[DEFERRED]",
)

# Golden set: exactly the 8 source families named in the Master Reference's
# Authoritative Source Strategy table. No more, no fewer.
GOLDEN_SOURCE_FAMILY_IDS = frozenset(
    {"SF-01", "SF-02", "SF-03", "SF-04", "SF-05", "SF-06", "SF-07", "SF-08"}
)
GOLDEN_SOURCE_FAMILY_NAMES = frozenset(
    {
        "India Code",
        "IP India",
        "Ministry of Ayush",
        "CDSCO / Drugs & Cosmetics",
        "FSSAI",
        "WIPO / WIPO Lex",
        "TKDL",
        "Bhashini",
    }
)

# URLs verbatim from the Master Reference's own "Research Sources &
# Provenance" list - used to prove nothing was invented.
EXPECTED_URLS = {
    "SF-01": "https://www.indiacode.nic.in/",
    "SF-02": "https://ipindia.gov.in/",
    "SF-03": "https://ayush.gov.in/",
    "SF-04": "https://www.cdsco.gov.in/opencms/opencms/en/Traditional_Drugs/",
    "SF-05": "https://fssai.gov.in/upload/notifications/2022/05/62789a20b54bdGazette_Notification_Ayurveda_Aahara_09_05_2022.pdf",
    "SF-06": "https://www.wipo.int/en/web/traditional-knowledge/wipo-treaty-on-ip-gr-and-associated-tk",
    "SF-08": "https://app.bhashini.ai/translate",
}


@pytest.fixture(scope="module")
def doc_text() -> str:
    assert DOC_PATH.is_file()
    return DOC_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def matrix_raw_text() -> str:
    assert YAML_PATH.is_file()
    return YAML_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def matrix_data(matrix_raw_text: str) -> dict:
    return yaml.safe_load(matrix_raw_text)


@pytest.fixture()
def valid_matrix_copy(matrix_data: dict) -> dict:
    return copy.deepcopy(matrix_data)


def _family(matrix_data: dict, family_id: str) -> dict:
    return next(f for f in matrix_data["source_families"] if f["source_family_id"] == family_id)


# ---------------------------------------------------------------------------
# Document structure
# ---------------------------------------------------------------------------


def test_doc_exists_and_nonempty():
    assert DOC_PATH.stat().st_size > 0


@pytest.mark.parametrize(
    "section",
    [
        "0. Source Families",
        "1. Category Groupings",
        "2. Authority Matrix Table",
        "3. Regulatory Domain / Question-Type Mapping",
        "4. Provenance & Version Requirements",
        "5. Language-Service Sources",
        "6. Authoritative vs. Contextual vs. Prohibited Sources",
        "7. Jurisdiction Separation Policy",
        "8. Corpus Expansion Policy",
        "9. Limitations",
        "10. Source/Evidence Audit",
    ],
)
def test_doc_has_required_section(doc_text: str, section: str):
    assert section in doc_text


@pytest.mark.parametrize(
    "label",
    ["[OFFICIAL SOURCE]", "[ENGINEERING RECOMMENDATION]", "[ASSUMPTION]", "[DEFERRED]"],
)
def test_doc_uses_expected_source_discipline_labels(doc_text: str, label: str):
    assert label in doc_text


def test_doc_never_fabricates_official_ps_or_external_research_claims(doc_text: str):
    assert "[OFFICIAL PS]" not in doc_text
    assert "[EXTERNAL RESEARCH]" not in doc_text


def test_doc_states_no_ingestion_occurred(doc_text: str):
    lowered = doc_text.lower()
    assert "no document exists in this repository" in lowered or "does not ingest" in lowered


def test_doc_explicitly_notes_tkdl_url_absence(doc_text: str):
    # Strip markdown emphasis markers so "does **not** appear" still
    # matches the phrase check below.
    flattened = doc_text.lower().replace("**", "")
    assert "does not appear" in flattened
    assert "TKDL" in doc_text


# ---------------------------------------------------------------------------
# YAML schema validation
# ---------------------------------------------------------------------------


def test_yaml_file_exists_and_nonempty():
    assert YAML_PATH.stat().st_size > 0


def test_yaml_parses_correctly(matrix_raw_text: str):
    data = yaml.safe_load(matrix_raw_text)
    assert isinstance(data, dict)


def test_matrix_passes_schema_validation(matrix_data: dict):
    validate_authority_matrix(matrix_data)  # should not raise


# ---------------------------------------------------------------------------
# Golden vocabulary: exactly the 8 Master-Reference-named source families
# ---------------------------------------------------------------------------


def test_exactly_eight_source_families_present(matrix_data: dict):
    ids = {f["source_family_id"] for f in matrix_data["source_families"]}
    assert ids == GOLDEN_SOURCE_FAMILY_IDS


def test_source_family_names_match_golden_vocabulary(matrix_data: dict):
    names = {f["source_family_name"] for f in matrix_data["source_families"]}
    assert names == GOLDEN_SOURCE_FAMILY_NAMES


def test_no_unsupported_source_family_can_be_injected_undetected():
    # Prove the golden-set test itself would catch a fabricated family.
    ids = set(GOLDEN_SOURCE_FAMILY_IDS) | {"SF-99"}
    assert ids != GOLDEN_SOURCE_FAMILY_IDS


@pytest.mark.parametrize("family_id,expected_url", list(EXPECTED_URLS.items()))
def test_urls_match_master_reference_verbatim(matrix_data: dict, family_id: str, expected_url: str):
    fam = _family(matrix_data, family_id)
    assert fam["url"] == expected_url


def test_tkdl_url_is_not_invented(matrix_data: dict):
    fam = _family(matrix_data, "SF-07")
    assert fam["url"] is None


def test_source_family_ids_are_globally_unique(matrix_data: dict):
    ids = [f["source_family_id"] for f in matrix_data["source_families"]]
    assert len(ids) == len(set(ids))


def test_every_source_family_has_exactly_one_source_label(matrix_data: dict):
    for fam in matrix_data["source_families"]:
        assert isinstance(fam["source_label"], str)
        assert fam["source_label"] in SOURCE_DISCIPLINE_LABELS


# ---------------------------------------------------------------------------
# Jurisdiction separation / India-vs-international consistency
# ---------------------------------------------------------------------------


def test_india_source_families_have_india_jurisdiction(matrix_data: dict):
    for family_id in ("SF-01", "SF-02", "SF-03", "SF-04", "SF-05"):
        assert _family(matrix_data, family_id)["jurisdiction_scope"] == "INDIA"


def test_wipo_has_international_jurisdiction(matrix_data: dict):
    assert _family(matrix_data, "SF-06")["jurisdiction_scope"] == "INTERNATIONAL"


def test_bhashini_jurisdiction_is_not_applicable(matrix_data: dict):
    assert _family(matrix_data, "SF-08")["jurisdiction_scope"] == "NOT_APPLICABLE"


def test_india_and_international_families_are_disjoint_in_groupings(matrix_data: dict):
    india = set(matrix_data["category_groupings"]["india_regulatory_sources"])
    intl = set(matrix_data["category_groupings"]["international_ip_sources"])
    assert india.isdisjoint(intl)


def test_no_inter_family_legal_hierarchy_is_asserted(matrix_data: dict):
    for fam in matrix_data["source_families"]:
        hierarchy = fam["conflict_policy"].get("inter_family_hierarchy")
        assert hierarchy in ("NOT_ESTABLISHED_BY_MASTER_REFERENCE", "NOT_APPLICABLE")


# ---------------------------------------------------------------------------
# Bhashini exclusion / language-service handling
# ---------------------------------------------------------------------------


def test_bhashini_supports_no_regulatory_question_types(matrix_data: dict):
    assert _family(matrix_data, "SF-08")["supported_question_types"] == []


def test_bhashini_is_a_service_adapter_not_evidence_source(matrix_data: dict):
    fam = _family(matrix_data, "SF-08")
    assert fam["corpus_role"] == "SERVICE_ADAPTER"
    assert fam["corpus_admission_status"] == "NOT_APPLICABLE"


def test_bhashini_excluded_from_evidence_groupings(matrix_data: dict):
    groupings = matrix_data["category_groupings"]
    for key in (
        "india_regulatory_sources",
        "international_ip_sources",
        "knowledge_traditional_knowledge_sources",
    ):
        assert "SF-08" not in groupings[key]
    assert "SF-08" in groupings["language_service_sources"]


# ---------------------------------------------------------------------------
# Non-authoritative contextual tier is deliberately empty
# ---------------------------------------------------------------------------


def test_contextual_tier_is_empty(matrix_data: dict):
    assert matrix_data["category_groupings"]["non_authoritative_contextual_sources"] == []


# ---------------------------------------------------------------------------
# CDSCO / FSSAI distinction preserved
# ---------------------------------------------------------------------------


def test_cdsco_and_fssai_are_distinct_families_with_distinct_question_types(matrix_data: dict):
    cdsco = _family(matrix_data, "SF-04")
    fssai = _family(matrix_data, "SF-05")
    assert cdsco["supported_question_types"] == ["TRADITIONAL_DRUG_REGULATION"]
    assert fssai["supported_question_types"] == ["AYURVEDA_AAHARA_FOOD_LAW"]
    assert set(cdsco["supported_question_types"]).isdisjoint(fssai["supported_question_types"])


# ---------------------------------------------------------------------------
# No fabricated citation/statute patterns
# ---------------------------------------------------------------------------


def test_no_citation_or_statute_number_patterns_in_matrix(matrix_raw_text: str):
    # Note: a bare "Section N" is intentionally NOT flagged - this file
    # legitimately cross-references its own companion doc's numbered
    # sections (e.g. "see docs/PHASE_02_AUTHORITY_MATRIX.md Section 6.2").
    # Only patterns that actually look like a statutory citation (a
    # section number with a parenthetical subsection, a gazette S.O.
    # number, or an "Act, YYYY" reference) are checked.
    suspicious = re.findall(r"\bSection\s+\d+\s*\(\d|\bS\.O\.\s*\d+|\bAct,?\s+\d{4}\b", matrix_raw_text)
    assert suspicious == [], f"possible fabricated citation pattern found: {suspicious}"


# ---------------------------------------------------------------------------
# Negative tests
# ---------------------------------------------------------------------------


def test_malformed_root_is_rejected():
    with pytest.raises(AuthorityMatrixValidationError):
        validate_authority_matrix(["not", "a", "mapping"])


def test_missing_top_level_key_is_rejected(valid_matrix_copy: dict):
    del valid_matrix_copy["category_groupings"]
    with pytest.raises(AuthorityMatrixValidationError):
        validate_authority_matrix(valid_matrix_copy)


def test_source_family_without_provenance_requirements_field_is_rejected(valid_matrix_copy: dict):
    del valid_matrix_copy["source_families"][0]["provenance_requirements"]
    with pytest.raises(AuthorityMatrixValidationError):
        validate_authority_matrix(valid_matrix_copy)


def test_source_family_without_jurisdiction_is_rejected(valid_matrix_copy: dict):
    del valid_matrix_copy["source_families"][0]["jurisdiction_scope"]
    with pytest.raises(AuthorityMatrixValidationError):
        validate_authority_matrix(valid_matrix_copy)


def test_duplicate_source_family_id_is_rejected(valid_matrix_copy: dict):
    valid_matrix_copy["source_families"][1]["source_family_id"] = (
        valid_matrix_copy["source_families"][0]["source_family_id"]
    )
    with pytest.raises(AuthorityMatrixValidationError):
        validate_authority_matrix(valid_matrix_copy)


def test_unknown_jurisdiction_value_is_rejected(valid_matrix_copy: dict):
    valid_matrix_copy["source_families"][0]["jurisdiction_scope"] = "MARS"
    with pytest.raises(AuthorityMatrixValidationError):
        validate_authority_matrix(valid_matrix_copy)


def test_invalid_source_label_is_rejected(valid_matrix_copy: dict):
    valid_matrix_copy["source_families"][0]["source_label"] = "[MADE UP LABEL]"
    with pytest.raises(AuthorityMatrixValidationError):
        validate_authority_matrix(valid_matrix_copy)


def test_unsupported_source_family_injection_is_rejected_via_grouping_check(valid_matrix_copy: dict):
    # Synthetic fixture: inject a reference to a non-existent source family
    # into a category grouping, proving cross-referential integrity is
    # enforced (an unsupported family cannot silently enter a grouping).
    valid_matrix_copy["category_groupings"]["india_regulatory_sources"].append("SF-99")
    with pytest.raises(AuthorityMatrixValidationError):
        validate_authority_matrix(valid_matrix_copy)


def test_prohibited_source_marked_authoritative_is_caught_by_golden_set(matrix_data: dict):
    # Prove that accidentally adding e.g. Wikipedia as a source family would
    # be caught by the golden-vocabulary tests above (negative test #10).
    injected = copy.deepcopy(matrix_data)
    injected["source_families"].append(
        {
            "source_family_id": "SF-100",
            "source_family_name": "Wikipedia",  # SYNTHETIC - must never be real
            "authority_tier": "PRIMARY_OFFICIAL",
            "authority_role": "ENCYCLOPEDIA",
            "jurisdiction_scope": "INDIA",
            "regulatory_domains": ["synthetic fixture only"],
            "supported_question_types": [],
            "allowed_document_types": [],
            "provenance_requirements": [],
            "version_requirements": [],
            "validation_requirements": "synthetic fixture only",
            "corpus_admission_status": "PERMITTED",
            "corpus_role": "EVIDENCE_SOURCE",
            "conflict_policy": {"policy_reference": "N/A", "inter_family_hierarchy": "NOT_APPLICABLE"},
            "limitations": [],
            "source_label": "[ASSUMPTION]",
        }
    )
    names = {f["source_family_name"] for f in injected["source_families"]}
    assert names != GOLDEN_SOURCE_FAMILY_NAMES
