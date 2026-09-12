"""
Phase 1 tests: docs/PHASE_01_DOMAIN_TAXONOMY.md and
config/domain_taxonomy.yaml.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from _taxonomy_schema import TaxonomyValidationError, validate_domain_taxonomy

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "PHASE_01_DOMAIN_TAXONOMY.md"
YAML_PATH = REPO_ROOT / "config" / "domain_taxonomy.yaml"

SOURCE_DISCIPLINE_LABELS = (
    "[OFFICIAL PS]",
    "[OFFICIAL SOURCE]",
    "[EXTERNAL RESEARCH]",
    "[ENGINEERING RECOMMENDATION]",
    "[OUR ENHANCEMENT]",
    "[ASSUMPTION]",
    "[DEFERRED]",
)

# Labels the Phase 1 taxonomy doc is expected to actually use. [OFFICIAL PS]
# and [EXTERNAL RESEARCH] are deliberately excluded: as documented in this
# doc's own provenance note (and docs/PHASE_00_SCOPE_AND_ACCEPTANCE.md), the
# original PS artifact was never reviewed in this workspace, and no external
# research beyond the Master Reference informed Phase 1 - asserting those
# two labels must appear would pressure inventing a claim just to pass this
# test, which the project's source-discipline rules explicitly forbid.
LABELS_EXPECTED_IN_PHASE_01_TAXONOMY_DOC = (
    "[OFFICIAL SOURCE]",
    "[ENGINEERING RECOMMENDATION]",
    "[OUR ENHANCEMENT]",
    "[ASSUMPTION]",
    "[DEFERRED]",
)

REQUIRED_DOC_SECTIONS = (
    "A. Purpose",
    "B. Taxonomy Design Principles",
    "C. Product/Formulation Classification Dimensions",
    "D. Regulatory Question Taxonomy",
    "E. User Intent Taxonomy",
    "F. Jurisdiction-Sensitive Dimensions",
    "G. Evidence-Dependent Dimensions",
    "H. Unknown / Ambiguous States",
    "I. Classification Output Model",
    "J. Explainability Requirements",
    "K. Examples",
    "L. Explicit Non-Goals",
    "M. Source/Evidence Audit",
)

# Golden vocabulary: every regulatory_track / IP / ABS-TK / regulatory
# question category name that Phase 1 is allowed to introduce. This proves
# no unsupported regulatory terminology was introduced (negative test #12
# from the Phase 1 instructions and the source-discipline audit item #2).
ALLOWED_REGULATORY_TRACK_NAMES = frozenset(
    {
        "CLASSICAL_AYURVEDIC_DRUG",
        "PROPRIETARY_AYURVEDIC_DRUG",
        "NEW_AYURVEDIC_DRUG",
        "AYURVEDA_AAHARA_FOOD",
        "COSMETIC",
        "PHYTOPHARMACEUTICAL",
        "UNDETERMINED",
        "CONFLICTING",
    }
)
ALLOWED_IP_CATEGORY_NAMES = frozenset(
    {"PATENT", "TRADEMARK", "DESIGN", "GEOGRAPHICAL_INDICATION", "NONE", "UNDETERMINED"}
)
ALLOWED_REGULATORY_QUESTION_NAMES = frozenset(
    {
        "INDIA_LEGISLATIVE",
        "IP_REGISTRATION_AND_SEARCH",
        "AYUSH_POLICY",
        "TRADITIONAL_DRUG_REGULATION",
        "AYURVEDA_AAHARA_FOOD_LAW",
        "INTERNATIONAL_IP_TREATY",
        "TRADITIONAL_KNOWLEDGE_DATABASE",
        "UNDETERMINED",
    }
)


@pytest.fixture(scope="module")
def doc_text() -> str:
    assert DOC_PATH.is_file()
    return DOC_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def taxonomy_raw_text() -> str:
    assert YAML_PATH.is_file()
    return YAML_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def taxonomy_data(taxonomy_raw_text: str) -> dict:
    return yaml.safe_load(taxonomy_raw_text)


@pytest.fixture()
def valid_taxonomy_copy(taxonomy_data: dict) -> dict:
    return copy.deepcopy(taxonomy_data)


# ---------------------------------------------------------------------------
# Document structure
# ---------------------------------------------------------------------------


def test_doc_exists_and_nonempty():
    assert DOC_PATH.stat().st_size > 0


@pytest.mark.parametrize("section", REQUIRED_DOC_SECTIONS)
def test_doc_has_required_section(doc_text: str, section: str):
    assert section in doc_text


@pytest.mark.parametrize("label", LABELS_EXPECTED_IN_PHASE_01_TAXONOMY_DOC)
def test_doc_uses_every_source_discipline_label(doc_text: str, label: str):
    assert label in doc_text


def test_doc_never_fabricates_official_ps_or_external_research_claims(doc_text: str):
    # Mirror check: since [OFFICIAL PS] and [EXTERNAL RESEARCH] are not
    # expected (see LABELS_EXPECTED_IN_PHASE_01_TAXONOMY_DOC), confirm they
    # are indeed absent rather than silently present-but-untested.
    assert "[OFFICIAL PS]" not in doc_text
    assert "[EXTERNAL RESEARCH]" not in doc_text


def test_doc_preserves_master_reference_branch_granularity(doc_text: str):
    # Proves the taxonomy doc did not invent finer legal subcategories
    # beyond what the Master Reference names.
    assert "classical/proprietary/new-drug" in doc_text.lower() or (
        "CLASSICAL_AYURVEDIC_DRUG" in doc_text
        and "PROPRIETARY_AYURVEDIC_DRUG" in doc_text
        and "NEW_AYURVEDIC_DRUG" in doc_text
    )
    assert "AYURVEDA_AAHARA_FOOD" in doc_text


def test_doc_declares_no_legal_certainty_claim(doc_text: str):
    lowered = doc_text.lower()
    assert "not a legal determination" in lowered or "never a legal determination" in lowered


# ---------------------------------------------------------------------------
# YAML structure / schema validation
# ---------------------------------------------------------------------------


def test_taxonomy_yaml_file_exists_and_nonempty():
    assert YAML_PATH.stat().st_size > 0


def test_taxonomy_yaml_parses_correctly(taxonomy_raw_text: str):
    data = yaml.safe_load(taxonomy_raw_text)
    assert isinstance(data, dict)


def test_taxonomy_passes_schema_validation(taxonomy_data: dict):
    validate_domain_taxonomy(taxonomy_data)  # should not raise


def test_taxonomy_version_present(taxonomy_data: dict):
    assert taxonomy_data["taxonomy_version"] == "1.0.0"


# ---------------------------------------------------------------------------
# Unique IDs / required fields / valid status / valid source labels
# ---------------------------------------------------------------------------


def _all_categories(data: dict):
    cats = []
    for dim in data["dimensions"].values():
        cats.extend(dim["categories"])
    for key in (
        "regulatory_question_categories",
        "user_intent_categories",
        "jurisdiction_inputs",
        "evidence_states",
        "classification_states",
    ):
        cats.extend(data[key]["categories"])
    return cats


def test_all_taxonomy_ids_globally_unique(taxonomy_data: dict):
    ids = [c["id"] for c in _all_categories(taxonomy_data)]
    assert len(ids) == len(set(ids)), "duplicate taxonomy IDs found"


def test_every_category_has_required_fields(taxonomy_data: dict):
    required = {"id", "name", "description", "status", "source_label"}
    for cat in _all_categories(taxonomy_data):
        missing = required - set(cat.keys())
        assert not missing, f"{cat.get('id')} missing fields: {missing}"


def test_every_category_status_is_defined(taxonomy_data: dict):
    for cat in _all_categories(taxonomy_data):
        assert cat["status"] == "DEFINED", f"{cat['id']} has status {cat['status']!r}"


def test_every_category_source_label_is_approved(taxonomy_data: dict):
    for cat in _all_categories(taxonomy_data):
        assert cat["source_label"] in SOURCE_DISCIPLINE_LABELS, (
            f"{cat['id']} has unapproved source_label {cat['source_label']!r}"
        )


def test_every_dimension_has_an_undetermined_state(taxonomy_data: dict):
    for dim_name, dim in taxonomy_data["dimensions"].items():
        names = {c["name"] for c in dim["categories"]}
        assert "UNDETERMINED" in names, f"dimension {dim_name!r} has no UNDETERMINED state"


# ---------------------------------------------------------------------------
# No unsupported regulatory terminology (golden-set checks)
# ---------------------------------------------------------------------------


def test_regulatory_track_names_match_golden_vocabulary(taxonomy_data: dict):
    names = {c["name"] for c in taxonomy_data["dimensions"]["regulatory_track"]["categories"]}
    assert names == ALLOWED_REGULATORY_TRACK_NAMES


def test_ip_protection_category_names_match_golden_vocabulary(taxonomy_data: dict):
    names = {c["name"] for c in taxonomy_data["dimensions"]["ip_protection_category"]["categories"]}
    assert names == ALLOWED_IP_CATEGORY_NAMES


def test_regulatory_question_category_names_match_golden_vocabulary(taxonomy_data: dict):
    names = {c["name"] for c in taxonomy_data["regulatory_question_categories"]["categories"]}
    assert names == ALLOWED_REGULATORY_QUESTION_NAMES


def test_no_citation_or_statute_number_patterns_in_taxonomy(taxonomy_raw_text: str):
    # Guards against fabricated citations (e.g. "Section 5(2)(a)", "S.O. 1234(E)")
    # sneaking into descriptions. A deliberately simple/conservative check.
    import re

    suspicious = re.findall(r"\bSection\s+\d+|\bS\.O\.\s*\d+|\bAct,?\s+\d{4}\b", taxonomy_raw_text)
    assert suspicious == [], f"possible fabricated citation pattern found: {suspicious}"


# ---------------------------------------------------------------------------
# Negative tests: malformed / missing fields / duplicates / invalid states
# ---------------------------------------------------------------------------


def test_malformed_root_is_rejected():
    with pytest.raises(TaxonomyValidationError):
        validate_domain_taxonomy(["not", "a", "mapping"])


def test_missing_top_level_key_is_rejected(valid_taxonomy_copy: dict):
    del valid_taxonomy_copy["classification_states"]
    with pytest.raises(TaxonomyValidationError):
        validate_domain_taxonomy(valid_taxonomy_copy)


def test_missing_category_field_is_rejected(valid_taxonomy_copy: dict):
    del valid_taxonomy_copy["dimensions"]["regulatory_track"]["categories"][0]["description"]
    with pytest.raises(TaxonomyValidationError):
        validate_domain_taxonomy(valid_taxonomy_copy)


def test_duplicate_taxonomy_id_is_rejected(valid_taxonomy_copy: dict):
    valid_taxonomy_copy["dimensions"]["regulatory_track"]["categories"][1]["id"] = (
        valid_taxonomy_copy["dimensions"]["regulatory_track"]["categories"][0]["id"]
    )
    with pytest.raises(TaxonomyValidationError):
        validate_domain_taxonomy(valid_taxonomy_copy)


def test_invalid_source_label_is_rejected(valid_taxonomy_copy: dict):
    valid_taxonomy_copy["dimensions"]["regulatory_track"]["categories"][0]["source_label"] = (
        "[MADE UP LABEL]"
    )
    with pytest.raises(TaxonomyValidationError):
        validate_domain_taxonomy(valid_taxonomy_copy)


def test_illegal_status_value_is_rejected(valid_taxonomy_copy: dict):
    # Synthetic fixture: Phase 1 may never claim a taxonomy category is
    # further along than DEFINED (e.g. "IMPLEMENTED" would be a false claim
    # about production classifier behavior that does not exist yet).
    valid_taxonomy_copy["dimensions"]["regulatory_track"]["categories"][0]["status"] = "IMPLEMENTED"
    with pytest.raises(TaxonomyValidationError):
        validate_domain_taxonomy(valid_taxonomy_copy)


def test_empty_categories_list_is_rejected(valid_taxonomy_copy: dict):
    valid_taxonomy_copy["dimensions"]["regulatory_track"]["categories"] = []
    with pytest.raises(TaxonomyValidationError):
        validate_domain_taxonomy(valid_taxonomy_copy)


def test_unsupported_regulatory_terminology_is_caught_by_golden_set(taxonomy_data: dict):
    # Prove the golden-set test itself is sensitive: inject a fabricated,
    # unsupported category name and confirm it would be detected.
    injected = copy.deepcopy(taxonomy_data)
    injected["dimensions"]["regulatory_track"]["categories"].append(
        {
            "id": "RT-99",
            "name": "SCHEDULE_H_CONTROLLED_SUBSTANCE",  # synthetic, NOT a real claim
            "description": "Synthetic fixture only - not a real regulatory category from the Master Reference.",
            "status": "DEFINED",
            "source_label": "[ASSUMPTION]",
        }
    )
    names = {c["name"] for c in injected["dimensions"]["regulatory_track"]["categories"]}
    assert names != ALLOWED_REGULATORY_TRACK_NAMES, (
        "golden-set comparison failed to detect an injected unsupported category"
    )
