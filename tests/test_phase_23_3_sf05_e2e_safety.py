"""
Phase 23.3.5: the complete pre-generation pipeline exercised against the
first real, admitted corpus document (SF-05) -
classification -> jurisdiction -> real BM25 retrieval -> real
EvidencePack -> citation validation -> Phase 13 safety/abstention -
using Phase 11/12/9/13's real, unmodified entry points throughout.

NO GENERATION PROVIDER IS INTRODUCED ANYWHERE IN THIS FILE. `evaluate_safety`
accepts `grounded_response=None` as a first-class, already-documented input
(gate G5, `REASON_MISSING_GROUNDED_RESPONSE`) - this is the real, existing
mechanism used here to prove the safety layer correctly refuses to present
anything when no generation was ever attempted, without needing
`generation.generator.generate_grounded_response` (which requires an actual
`GenerationProvider` instance to even type-check) or any provider, real or
fake, anywhere in this file.

This suite does not duplicate the full existing Phase 9/12/13 test suites -
it focuses narrowly on their integration with REAL SF-05 evidence.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ingestion.admission import load_authority_matrix  # noqa: E402
from ingestion.pipeline import ingest_bytes  # noqa: E402
from chunking.chunker import chunk_document  # noqa: E402
from retrieval.index import build_index, query  # noqa: E402
from evidence.builder import build_evidence_pack  # noqa: E402
from evidence.validation import EvidenceIntegrityError, verify_evidence_identity  # noqa: E402
from citation.models import CitationReference  # noqa: E402
from citation.validator import validate_citation, check_evidence_pack_validity  # noqa: E402
from classification.classifier import classify  # noqa: E402
from classification.models import ClassificationInput  # noqa: E402
from jurisdiction.firewall import resolve_jurisdiction  # noqa: E402
from jurisdiction.filtering import check_evidence_compatible, filter_evidence  # noqa: E402
from safety.evaluator import evaluate_safety  # noqa: E402
from application.service import ApplicationService  # noqa: E402
from application.models import ApplicationQueryRequest, APPLICATION_SCHEMA_VERSION  # noqa: E402
from application.service import GenerationProviderNotConfiguredError  # noqa: E402

DOCUMENT_ID = "SF05-FSSAI-AYURVEDA-AAHARA-REGULATIONS-2022"
RAW_PDF_PATH = REPO_ROOT / "data" / "raw" / "SF-05" / f"{DOCUMENT_ID}.pdf"
MANIFEST_PATH = REPO_ROOT / "data" / "manifest" / "SF-05" / f"{DOCUMENT_ID}.json"

REAL_QUERY_PAIRS = [
    # (english label, real Devanagari retrieval query - the document is Hindi)
    ("Ayurveda Aahara", "आयुर्वेद आहार"),
    ("Ayurveda Aahara definition", "आयुर्वेद आहार परिभाषा"),
    ("labelling requirements", "लेबडलंग अपेक्षा"),
    ("permitted ingredients", "संोटक अनुमत"),
    ("Schedule A", "अनुसूची क"),
]


def _skip_if_not_admitted():
    if not RAW_PDF_PATH.is_file() or not MANIFEST_PATH.is_file():
        pytest.skip("real SF-05 document has not been admitted in this checkout (Phase 23.3.2E)")


@pytest.fixture(scope="module")
def real_provenance() -> dict:
    _skip_if_not_admitted()
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def authority_matrix() -> dict:
    return load_authority_matrix()


@pytest.fixture(scope="module")
def real_bm25_index(real_provenance, authority_matrix):
    data = RAW_PDF_PATH.read_bytes()
    result = ingest_bytes(data, real_provenance, ".pdf", authority_matrix)
    assert result.pipeline_state == "EXTRACTION_SUCCESS"
    chunks = chunk_document(result.document).chunks
    return build_index(chunks)


def _real_pack_for(real_bm25_index, english_label, devanagari_query, top_k=3):
    response = query(real_bm25_index, devanagari_query, top_k=top_k)
    return build_evidence_pack(response.results, devanagari_query), response


# ---------------------------------------------------------------------------
# GROUP A - real evidence happy path, all 5 required queries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("english_label,devanagari_query", REAL_QUERY_PAIRS)
def test_group_a_real_pregeneration_pipeline_per_query(real_bm25_index, english_label, devanagari_query):
    request_id = f"e2e-{english_label.replace(' ', '-')}"

    # classification (Phase 11, unmodified) - a bare topic phrase honestly
    # does not resolve to a specific formulation; UNKNOWN is a real,
    # legitimate outcome here, never forced to something else.
    classification_result = classify(ClassificationInput(input_id=request_id, raw_query=english_label))

    # jurisdiction (Phase 12, unmodified)
    jurisdiction_decision = resolve_jurisdiction(request_id, classification_result=classification_result, explicit_jurisdiction="INDIA")
    assert jurisdiction_decision.state == "KNOWN"
    assert "INDIA" in jurisdiction_decision.allowed_jurisdictions

    # real BM25 retrieval -> real EvidencePack (Phase 5/8, unmodified)
    pack, response = _real_pack_for(real_bm25_index, english_label, devanagari_query)
    assert len(response.results) > 0
    assert len(pack.evidence_items) > 0
    assert check_evidence_pack_validity(pack) is None  # real evidence, no false integrity failure

    # citation validation (Phase 9, unmodified) - EVIDENCE RETRIEVAL succeeded
    real_evidence_id = pack.evidence_items[0].evidence_id
    citation_result = validate_citation(CitationReference(evidence_id=real_evidence_id), pack)
    assert citation_result.status == "VALID"

    # safety (Phase 13, unmodified) - NO generation was attempted anywhere
    # above (no GroundedResponse exists, no provider was ever constructed
    # or called) - grounded_response=None is the honest, real input.
    safety_decision = evaluate_safety(
        request_id, classification_result=classification_result, jurisdiction_decision=jurisdiction_decision, grounded_response=None
    )

    # THE critical distinction this step exists to prove: evidence
    # retrieval succeeded (asserted above), but the system never claims a
    # final answer was generated - safety_status is never SAFE_TO_PRESENT
    # when no generation occurred, regardless of how good the evidence is.
    assert safety_decision.safety_status != "SAFE_TO_PRESENT"
    assert safety_decision.engineering_signal_band == "NOT_APPLICABLE"


# ---------------------------------------------------------------------------
# GROUP B - valid citation against each real EvidencePack
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("english_label,devanagari_query", REAL_QUERY_PAIRS)
def test_group_b_valid_citation_for_every_real_pack(real_bm25_index, english_label, devanagari_query):
    pack, _ = _real_pack_for(real_bm25_index, english_label, devanagari_query)
    for evidence in pack.evidence_items:
        result = validate_citation(CitationReference(evidence_id=evidence.evidence_id), pack)
        assert result.status == "VALID"


# ---------------------------------------------------------------------------
# GROUP C - fabricated / near-miss / malformed / cross-pack citations
# ---------------------------------------------------------------------------


def test_group_c_fabricated_evidence_id_rejected(real_bm25_index):
    pack, _ = _real_pack_for(real_bm25_index, *REAL_QUERY_PAIRS[0])
    result = validate_citation(CitationReference(evidence_id="FABRICATED-EVIDENCE-ID-0000"), pack)
    assert result.status == "UNRESOLVED"


def test_group_c_near_miss_evidence_id_rejected(real_bm25_index):
    pack, _ = _real_pack_for(real_bm25_index, *REAL_QUERY_PAIRS[0])
    real_id = pack.evidence_items[0].evidence_id
    near_miss = real_id[:-1] + ("0" if real_id[-1] != "0" else "1")
    result = validate_citation(CitationReference(evidence_id=near_miss), pack)
    assert result.status == "UNRESOLVED"


def test_group_c_malformed_citation_rejected(real_bm25_index):
    pack, _ = _real_pack_for(real_bm25_index, *REAL_QUERY_PAIRS[0])
    result = validate_citation(CitationReference(evidence_id=None), pack)
    assert result.status == "INVALID"


def test_group_c_citation_to_evidence_not_present_in_this_pack_is_unresolved(real_bm25_index):
    # An evidence item real and VALID in one pack must not be accepted
    # against a different, unrelated pack that never selected it.
    pack_a, _ = _real_pack_for(real_bm25_index, *REAL_QUERY_PAIRS[0], top_k=1)
    pack_b, _ = _real_pack_for(real_bm25_index, "Schedule A only", "अनुसूची क", top_k=1)

    foreign_evidence_id = pack_a.evidence_items[0].evidence_id
    if foreign_evidence_id in {e.evidence_id for e in pack_b.evidence_items}:
        pytest.skip("both queries happened to retrieve the same top chunk - not a useful cross-pack case")
    result = validate_citation(CitationReference(evidence_id=foreign_evidence_id), pack_b)
    assert result.status == "UNRESOLVED"


# ---------------------------------------------------------------------------
# GROUP D - safety / abstention against real evidence
# ---------------------------------------------------------------------------


def test_group_d1_real_evidence_does_not_trigger_a_false_integrity_failure(real_bm25_index):
    pack, _ = _real_pack_for(real_bm25_index, *REAL_QUERY_PAIRS[0])
    assert check_evidence_pack_validity(pack) is None
    for evidence in pack.evidence_items:
        verify_evidence_identity(evidence)  # must not raise


def test_group_d2_missing_generation_provider_is_fail_closed_at_application_service(real_bm25_index):
    call_count = {"n": 0}

    def real_evidence_builder(q: str):
        call_count["n"] += 1
        pack, _ = _real_pack_for(real_bm25_index, "n/a", "आयुर्वेद आहार")
        return pack

    service = ApplicationService(generation_provider=None, evidence_pack_builder=real_evidence_builder)
    request = ApplicationQueryRequest(
        schema_version=APPLICATION_SCHEMA_VERSION,
        request_id="e2e-no-provider",
        query="Ayurveda Aahara",
        requested_language=None,
        jurisdiction="INDIA",
        formulation_description=None,
        source_language=None,
    )
    with pytest.raises(GenerationProviderNotConfiguredError):
        service.query(request)

    # THE architectural finding for Group E: the provider check fires
    # before classification/jurisdiction/retrieval ever run - the real
    # evidence_pack_builder above is never even called.
    assert call_count["n"] == 0


def test_group_d2b_generate_grounded_response_requires_a_real_provider_type(real_bm25_index):
    from generation.generator import generate_grounded_response

    pack, _ = _real_pack_for(real_bm25_index, *REAL_QUERY_PAIRS[0])
    with pytest.raises(TypeError):
        generate_grounded_response("Ayurveda Aahara", pack, None)


def test_group_d3_empty_evidence_pack_precondition_for_abstention_is_real(real_bm25_index):
    # Empty retrieval -> genuinely empty EvidencePack -> the exact
    # precondition generation.generator.generate_grounded_response uses to
    # abstain BEFORE ever calling a provider (`not pack.evidence_items`,
    # docs Section E). generate_grounded_response itself is not invoked
    # here, since doing so requires a GenerationProvider argument, which
    # this step does not introduce, not even as an unused placeholder.
    empty_response = query(real_bm25_index, "zzz_nonexistent_query_token_zzz", top_k=5)
    assert empty_response.results == []
    empty_pack = build_evidence_pack(empty_response.results, "zzz_nonexistent_query_token_zzz")
    assert empty_pack.evidence_items == []
    assert check_evidence_pack_validity(empty_pack) is None  # structurally valid, just empty
    assert not empty_pack.evidence_items  # the exact condition that forces abstention pre-generation


def test_group_d4_invalid_citation_cannot_be_treated_as_grounded_evidence(real_bm25_index):
    pack, _ = _real_pack_for(real_bm25_index, *REAL_QUERY_PAIRS[0])
    fabricated_result = validate_citation(CitationReference(evidence_id="NOT-REAL"), pack)
    assert fabricated_result.status != "VALID"


def test_group_d5_tampered_evidence_cannot_pass_identity_validation(real_bm25_index):
    pack, _ = _real_pack_for(real_bm25_index, *REAL_QUERY_PAIRS[0], top_k=1)
    tampered = dataclasses.replace(pack.evidence_items[0], content_hash="0" * 64)
    with pytest.raises(EvidenceIntegrityError):
        verify_evidence_identity(tampered)


def test_group_d6_cross_jurisdiction_evidence_remains_rejected(real_bm25_index):
    pack, _ = _real_pack_for(real_bm25_index, *REAL_QUERY_PAIRS[0], top_k=1)
    real_india_evidence = pack.evidence_items[0]
    assert real_india_evidence.jurisdiction == "INDIA"

    # A request whose classification/jurisdiction signals resolve to
    # INTERNATIONAL only (Phase 12, unmodified) - our real India evidence
    # must be blocked, never silently allowed across the firewall.
    intl_classification = classify(ClassificationInput(input_id="e2e-intl", raw_query="Tell me about WIPO treaty provisions."))
    intl_decision = resolve_jurisdiction("e2e-intl", classification_result=intl_classification, explicit_jurisdiction="INTERNATIONAL")
    assert intl_decision.state == "KNOWN"
    assert intl_decision.allowed_jurisdictions == frozenset({"INTERNATIONAL"})

    is_allowed, reason = check_evidence_compatible(intl_decision, real_india_evidence)
    assert is_allowed is False
    assert reason == "CROSS_JURISDICTION_EVIDENCE_BLOCKED"

    filter_result = filter_evidence(intl_decision, [real_india_evidence])
    assert filter_result.allowed_evidence == []
    assert real_india_evidence.evidence_id in filter_result.blocked_evidence_ids


def test_group_d7_synthetic_evidence_cannot_masquerade_as_the_real_admitted_evidence(real_bm25_index):
    pack, response = _real_pack_for(real_bm25_index, *REAL_QUERY_PAIRS[0], top_k=1)
    real_result = response.results[0]
    synthetic_result = dataclasses.replace(real_result, synthetic=True)

    real_pack = build_evidence_pack([real_result], REAL_QUERY_PAIRS[0][1])
    synthetic_pack = build_evidence_pack([synthetic_result], REAL_QUERY_PAIRS[0][1])

    # The `synthetic` flag itself is what must never be coerced/dropped -
    # this is the actual masquerade protection, verified directly:
    assert real_pack.evidence_items[0].synthetic is False
    assert synthetic_pack.evidence_items[0].synthetic is True
    # `evidence_id` is deterministically derived from schema_version +
    # chunk_id + content_hash + document_id + source_family_id +
    # jurisdiction + block_ids + page_numbers (identity.compute_evidence_id)
    # - `synthetic` is deliberately NOT a hash input, so identical
    # provenance produces the SAME evidence_id regardless of the synthetic
    # flag. This is real, existing, disclosed Phase 8 behavior, not a
    # defect - the masquerade protection is the flag's own faithful
    # propagation (asserted above), never a change in evidence_id.
    assert real_pack.evidence_items[0].evidence_id == synthetic_pack.evidence_items[0].evidence_id


def test_group_d8_ambiguous_classification_escalates_never_presents(real_bm25_index):
    # Phase 11's own established worked example (test_phase_11_classification.py
    # Example 3) - conflicting formulation signals -> AMBIGUOUS -> Phase 13's
    # hard gate G1 fires and overrides regardless of evidence/jurisdiction.
    classification_result = classify(
        ClassificationInput(
            input_id="e2e-ambiguous",
            raw_query="What regulatory category applies in India under FSSAI rules?",
            formulation_description="This is both an Ayurveda Aahara product and a Phytopharmaceutical.",
        )
    )
    assert classification_result.classification_state == "AMBIGUOUS"
    jurisdiction_decision = resolve_jurisdiction("e2e-ambiguous", classification_result=classification_result, explicit_jurisdiction="INDIA")

    safety_decision = evaluate_safety(
        "e2e-ambiguous", classification_result=classification_result, jurisdiction_decision=jurisdiction_decision, grounded_response=None
    )
    assert safety_decision.safety_status == "ESCALATE"
    assert safety_decision.reason_code == "CLASSIFICATION_AMBIGUOUS"
    assert safety_decision.safety_status != "SAFE_TO_PRESENT"


def test_group_d8b_resolvable_classification_and_jurisdiction_still_abstain_without_generation(real_bm25_index):
    # Phase 11's own established worked example (Example 4) - a query that
    # DOES resolve to KNOWN classification and KNOWN jurisdiction - proves
    # gate G5 (MISSING_GROUNDED_RESPONSE) specifically, distinct from the
    # G1/G2 gates already exercised above.
    classification_result = classify(ClassificationInput(input_id="e2e-known", raw_query="Tell me about Ministry of Ayush policy in India."))
    assert classification_result.classification_state == "KNOWN"
    jurisdiction_decision = resolve_jurisdiction("e2e-known", classification_result=classification_result)
    assert jurisdiction_decision.state == "KNOWN"

    safety_decision = evaluate_safety(
        "e2e-known", classification_result=classification_result, jurisdiction_decision=jurisdiction_decision, grounded_response=None
    )
    assert safety_decision.safety_status == "ABSTAIN"
    assert safety_decision.reason_code == "MISSING_GROUNDED_RESPONSE"


# ---------------------------------------------------------------------------
# GROUP E - production query path integration inspection
# ---------------------------------------------------------------------------


def test_group_e_production_query_path_cannot_be_exercised_without_a_configured_provider(real_bm25_index):
    """
    ARCHITECTURAL FINDING (not a defect, not modified here):
    ApplicationService.query()'s very first check is
    `if self.generation_provider is None: raise GenerationProviderNotConfiguredError`
    - this fires BEFORE classification, jurisdiction resolution, the
    injected evidence_pack_builder, citation validation, or safety
    evaluation ever run. The existing production entrypoint therefore
    CANNOT exercise the real retrieval/EvidencePack path in isolation
    without a configured GenerationProvider, by design (Phase 17's own
    documented "fail fast on missing provider" behavior) - this is
    reported here, not routed around, and ApplicationService is not
    modified. The pipeline stages were instead exercised directly
    (Groups A-D above), which required no such provider.
    """
    calls = []

    def spy_builder(q: str):
        calls.append(q)
        pack, _ = _real_pack_for(real_bm25_index, "n/a", "आयुर्वेद आहार")
        return pack

    service = ApplicationService(generation_provider=None, evidence_pack_builder=spy_builder)
    request = ApplicationQueryRequest(
        schema_version=APPLICATION_SCHEMA_VERSION,
        request_id="e2e-group-e",
        query="Ayurveda Aahara",
        requested_language=None,
        jurisdiction="INDIA",
        formulation_description=None,
        source_language=None,
    )

    with pytest.raises(GenerationProviderNotConfiguredError):
        service.query(request)

    assert calls == []  # proves the real evidence path was never reached
