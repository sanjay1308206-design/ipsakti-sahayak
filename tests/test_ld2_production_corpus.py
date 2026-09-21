"""
LD-2 (Production Corpus & Retrieval) tests for
`retrieval.production_corpus`.

SCOPE (matches the module's own docstring): every test here proves
production retrieval works INDEPENDENTLY of the HTTP query path. No test
constructs the real `api.dependencies.get_application_service` or wires
`sf05_evidence_pack_builder` into it - that remains LD-3's job. Where a
test needs the full Phase 11-13 orchestration (jurisdiction/citation/
safety compatibility), it constructs `application.service.ApplicationService`
directly, in-test, with a `FakeGenerationProvider` - never a real Gemini
call (LD-2 explicitly proves retrieval only, never generation).

Every test that needs the real, admitted SF-05 asset skips (not fails) if
it is not present in this checkout, exactly like
tests/test_phase_23_3_sf05_*.py already do.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from application.models import APPLICATION_SCHEMA_VERSION, ApplicationQueryRequest  # noqa: E402
from application.service import ApplicationService  # noqa: E402
from citation.validator import check_evidence_pack_validity, validate_citations  # noqa: E402
from evidence.validation import verify_pack_integrity  # noqa: E402
from generation.generator import generate_grounded_response  # noqa: E402
from generation.providers import FakeGenerationProvider  # noqa: E402
from jurisdiction.firewall import resolve_jurisdiction  # noqa: E402
from classification.classifier import classify  # noqa: E402
from classification.models import ClassificationInput  # noqa: E402
from safety.evaluator import evaluate_safety  # noqa: E402

import retrieval.production_corpus as production_corpus  # noqa: E402

DOCUMENT_ID = production_corpus.DOCUMENT_ID
MANIFEST_PATH = production_corpus.MANIFEST_PATH
RAW_PDF_PATH = production_corpus.RAW_PDF_PATH


def _skip_if_not_admitted():
    if not RAW_PDF_PATH.is_file() or not MANIFEST_PATH.is_file():
        pytest.skip("real SF-05 document has not been admitted in this checkout")


@pytest.fixture(autouse=True)
def _clear_corpus_cache():
    # load_validated_sf05_index is a process-lifetime lru_cache singleton
    # (mirrors api/dependencies.py's own get_backend_config convention) -
    # failure-mode tests that monkeypatch module constants must not leak
    # a cached (valid OR invalid) result into a later test.
    production_corpus.load_validated_sf05_index.cache_clear()
    yield
    production_corpus.load_validated_sf05_index.cache_clear()


@pytest.fixture()
def real_asset():
    _skip_if_not_admitted()


# ---------------------------------------------------------------------------
# 1-3. Manifest / hash / non-synthetic
# ---------------------------------------------------------------------------


def test_real_sf05_manifest_loads(real_asset):
    provenance = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert provenance["document_id"] == DOCUMENT_ID


def test_real_document_hash_matches_pinned_expected_value(real_asset):
    provenance = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert provenance["content_hash"] == production_corpus.EXPECTED_CONTENT_HASH

    import hashlib

    actual = hashlib.sha256(RAW_PDF_PATH.read_bytes()).hexdigest()
    assert actual == production_corpus.EXPECTED_CONTENT_HASH


def test_corpus_is_confirmed_non_synthetic(real_asset):
    index = production_corpus.load_validated_sf05_index()
    assert all(p["synthetic"] is False for p in index.chunk_provenance)


# ---------------------------------------------------------------------------
# 4-7. Exactly 83 chunks; BM25 index loads; signature matches; correspondence
# ---------------------------------------------------------------------------


def test_exactly_83_chunks_are_available(real_asset):
    index = production_corpus.load_validated_sf05_index()
    assert index.chunk_count == 83


def test_bm25_index_loads_successfully(real_asset):
    index = production_corpus.load_validated_sf05_index()
    assert index.chunk_count > 0
    assert len(index.chunk_ids) == index.chunk_count


def test_bm25_signature_matches_the_persisted_expected_value(real_asset):
    index = production_corpus.load_validated_sf05_index()
    assert index.signature == "c75035ff9dde1e3f8afef907d5c15c2ae4b726c31dbaea423245440fbe716e6a"


def test_index_corresponds_exactly_to_the_sf05_document(real_asset):
    index = production_corpus.load_validated_sf05_index()
    for prov in index.chunk_provenance:
        assert prov["document_id"] == DOCUMENT_ID
        assert prov["source_family_id"] == "SF-05"
        assert prov["jurisdiction"] == "INDIA"
        assert prov["synthetic"] is False
        assert prov["content_hash"] == production_corpus.EXPECTED_CONTENT_HASH


# ---------------------------------------------------------------------------
# 8-9. Real query returns real chunks with correct provenance
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("query_text", ["आयुर्वेद आहार", "आयुर्वेद आहार परिभाषा"])
def test_real_query_returns_real_chunks(real_asset, query_text):
    response = production_corpus.query_sf05(query_text, top_k=5)
    assert len(response.results) > 0
    for result in response.results:
        assert result.document_id == DOCUMENT_ID
        assert result.source_family_id == "SF-05"
        assert result.jurisdiction == "INDIA"
        assert result.synthetic is False
        assert result.chunk_text.strip() != ""


def test_returned_chunks_have_correct_page_and_block_provenance(real_asset):
    response = production_corpus.query_sf05("आयुर्वेद आहार", top_k=5)
    assert len(response.results) > 0
    for result in response.results:
        assert len(result.page_numbers) > 0
        assert all(1 <= p <= 27 for p in result.page_numbers)
        assert len(result.block_ids) > 0


# ---------------------------------------------------------------------------
# 10-11. EvidencePack built from real retrieval; empty retrieval never fabricates
# ---------------------------------------------------------------------------


def test_evidence_pack_is_built_from_real_retrieved_chunks(real_asset):
    pack = production_corpus.sf05_evidence_pack_builder("आयुर्वेद आहार")
    assert len(pack.evidence_items) > 0
    verify_pack_integrity(pack)  # existing Phase 8 integrity check, unmodified
    for evidence in pack.evidence_items:
        assert evidence.document_id == DOCUMENT_ID
        assert evidence.source_family_id == "SF-05"
        assert evidence.jurisdiction == "INDIA"
        assert evidence.synthetic is False


def test_empty_retrieval_does_not_fabricate_evidence(real_asset):
    pack = production_corpus.sf05_evidence_pack_builder("zzz_totally_absent_nonsense_term_zzz_qqq")
    assert pack.evidence_items == []


# ---------------------------------------------------------------------------
# 12-15. Fail-closed behavior: missing / corrupted / mismatched assets
# ---------------------------------------------------------------------------


def test_missing_manifest_fails_safely(monkeypatch, tmp_path):
    monkeypatch.setattr(production_corpus, "MANIFEST_PATH", tmp_path / "does-not-exist.json")
    with pytest.raises(production_corpus.ProductionCorpusIntegrityError):
        production_corpus.load_validated_sf05_index()


def test_missing_raw_pdf_fails_safely(real_asset, monkeypatch, tmp_path):
    monkeypatch.setattr(production_corpus, "RAW_PDF_PATH", tmp_path / "does-not-exist.pdf")
    with pytest.raises(production_corpus.ProductionCorpusIntegrityError):
        production_corpus.load_validated_sf05_index()


def test_corrupted_manifest_json_fails_safely(monkeypatch, tmp_path):
    bad_manifest = tmp_path / "corrupt.json"
    bad_manifest.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(production_corpus, "MANIFEST_PATH", bad_manifest)
    with pytest.raises(production_corpus.ProductionCorpusIntegrityError):
        production_corpus.load_validated_sf05_index()


def test_manifest_content_hash_tampered_fails_safely(real_asset, monkeypatch, tmp_path):
    provenance = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    provenance["content_hash"] = "0" * 64
    tampered = tmp_path / "tampered_manifest.json"
    tampered.write_text(json.dumps(provenance), encoding="utf-8")
    monkeypatch.setattr(production_corpus, "MANIFEST_PATH", tampered)
    with pytest.raises(production_corpus.ProductionCorpusIntegrityError):
        production_corpus.load_validated_sf05_index()


def test_raw_pdf_bytes_tampered_fails_safely_via_real_hash_check(real_asset, monkeypatch, tmp_path):
    # The manifest correctly declares the REAL hash; the PDF bytes on
    # disk are corrupted - ingestion.pipeline.ingest_bytes's own,
    # unmodified byte-for-byte SHA-256 check must catch this.
    tampered_pdf = tmp_path / "tampered.pdf"
    original = RAW_PDF_PATH.read_bytes()
    tampered_pdf.write_bytes(original + b"TAMPERED")
    monkeypatch.setattr(production_corpus, "RAW_PDF_PATH", tampered_pdf)
    with pytest.raises(production_corpus.ProductionCorpusIntegrityError):
        production_corpus.load_validated_sf05_index()


def test_chunk_count_mismatch_fails_closed(real_asset, monkeypatch):
    monkeypatch.setattr(production_corpus, "EXPECTED_CHUNK_COUNT", 999999)
    with pytest.raises(production_corpus.ProductionCorpusIntegrityError):
        production_corpus.load_validated_sf05_index()


def test_bm25_signature_mismatch_fails_closed(real_asset, monkeypatch):
    monkeypatch.setattr(production_corpus, "EXPECTED_BM25_SIGNATURE", "0" * 64)
    with pytest.raises(production_corpus.ProductionCorpusIntegrityError):
        production_corpus.load_validated_sf05_index()


# ---------------------------------------------------------------------------
# 16. Synthetic evidence cannot silently enter the real production corpus
# ---------------------------------------------------------------------------


def test_manifest_claiming_synthetic_true_is_rejected(real_asset, monkeypatch, tmp_path):
    provenance = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    provenance["synthetic"] = True
    tampered = tmp_path / "synthetic_tampered_manifest.json"
    tampered.write_text(json.dumps(provenance), encoding="utf-8")
    monkeypatch.setattr(production_corpus, "MANIFEST_PATH", tampered)
    with pytest.raises(production_corpus.ProductionCorpusIntegrityError):
        production_corpus.load_validated_sf05_index()


def test_manifest_wrong_document_identity_is_rejected(real_asset, monkeypatch, tmp_path):
    provenance = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    provenance["document_id"] = "SOME-OTHER-DOCUMENT-ID"
    tampered = tmp_path / "wrong_identity_manifest.json"
    tampered.write_text(json.dumps(provenance), encoding="utf-8")
    monkeypatch.setattr(production_corpus, "MANIFEST_PATH", tampered)
    with pytest.raises(production_corpus.ProductionCorpusIntegrityError):
        production_corpus.load_validated_sf05_index()


# ---------------------------------------------------------------------------
# 17-19. Existing citation / jurisdiction / safety architecture intact
# ---------------------------------------------------------------------------


def test_existing_citation_validation_accepts_a_real_valid_citation(real_asset):
    pack = production_corpus.sf05_evidence_pack_builder("आयुर्वेद आहार")
    assert len(pack.evidence_items) > 0
    real_id = pack.evidence_items[0].evidence_id
    provider = FakeGenerationProvider(response_text=f"Per the regulation. [[CITE:{real_id}]]")

    response = generate_grounded_response("आयुर्वेद आहार", pack, provider)

    assert response.grounding_status == "GROUNDED"
    assert real_id in response.cited_evidence_ids


def test_existing_citation_validation_still_rejects_a_fabricated_citation_over_real_evidence(real_asset):
    pack = production_corpus.sf05_evidence_pack_builder("आयुर्वेद आहार")
    assert check_evidence_pack_validity(pack) is None
    provider = FakeGenerationProvider(response_text="Fabricated source. [[CITE:EV-DOES-NOT-EXIST-999]]")

    response = generate_grounded_response("आयुर्वेद आहार", pack, provider)

    assert response.grounding_status == "ABSTAINED"
    assert response.abstention_reason == "NO_VALID_CITATIONS_PRODUCED"
    assert response.cited_evidence_ids == []


def test_existing_jurisdiction_firewall_resolves_india_for_real_sf05_evidence(real_asset):
    classification = classify(ClassificationInput(input_id="ld2-jur-1", raw_query="Ayurveda Aahara labelling", formulation_description=None))
    decision = resolve_jurisdiction("ld2-jur-1", classification_result=classification, explicit_jurisdiction="INDIA")
    assert decision.state != "UNKNOWN"
    assert decision.normalized_jurisdiction == "INDIA"


def test_existing_safety_gates_remain_intact_end_to_end_with_real_retrieved_evidence(real_asset):
    # Full ApplicationService orchestration with the REAL SF-05 retrieval
    # service wired in as evidence_pack_builder, but a FakeGenerationProvider
    # (never a real Gemini call - LD-2 proves retrieval only). This proves
    # Phase 11-13 are unaffected by where the EvidencePack came from.
    service = ApplicationService(
        generation_provider=FakeGenerationProvider(respond_fn=lambda prompt: "See the regulation."),
        evidence_pack_builder=production_corpus.sf05_evidence_pack_builder,
    )
    request = ApplicationQueryRequest(
        schema_version=APPLICATION_SCHEMA_VERSION, request_id="ld2-e2e-1", query="आयुर्वेद आहार",
        requested_language=None, jurisdiction="INDIA", formulation_description=None, source_language=None,
    )
    result = service.query(request)

    # No answer is ever DELIVERED without a valid citation (require_citations
    # defaults True) - a provider that cites nothing must abstain, never
    # fabricate a delivered answer, regardless of how real the evidence is.
    assert result.delivery_status != "DELIVERED"
    assert result.jurisdiction.normalized_jurisdiction == "INDIA"


def test_existing_safety_gates_deliver_a_grounded_answer_when_real_evidence_is_actually_cited(real_asset):
    pack = production_corpus.sf05_evidence_pack_builder("आयुर्वेद आहार")
    assert len(pack.evidence_items) > 0
    real_id = pack.evidence_items[0].evidence_id

    service = ApplicationService(
        generation_provider=FakeGenerationProvider(response_text=f"Per the regulation. [[CITE:{real_id}]]"),
        evidence_pack_builder=lambda q: pack,
    )
    request = ApplicationQueryRequest(
        schema_version=APPLICATION_SCHEMA_VERSION, request_id="ld2-e2e-2", query="आयुर्वेद आहार",
        requested_language=None, jurisdiction="INDIA", formulation_description=None, source_language=None,
    )
    result = service.query(request)

    assert result.grounding_status == "GROUNDED"
    assert real_id in result.cited_evidence_ids


# ---------------------------------------------------------------------------
# 20. Determinism / caching sanity (supports "existing regression tests pass")
# ---------------------------------------------------------------------------


def test_load_validated_sf05_index_is_cached_across_calls(real_asset):
    index_a = production_corpus.load_validated_sf05_index()
    index_b = production_corpus.load_validated_sf05_index()
    assert index_a is index_b


def test_sf05_corpus_status_reports_validated_when_asset_is_correct(real_asset):
    assert production_corpus.sf05_corpus_status() == "VALIDATED"


def test_sf05_corpus_status_reports_unavailable_without_raising_when_asset_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(production_corpus, "MANIFEST_PATH", tmp_path / "missing.json")
    assert production_corpus.sf05_corpus_status() == "UNAVAILABLE"


def test_production_corpus_is_wired_into_the_real_application_service_by_ld3():
    # Supersedes the LD-2-era guarantee that this module was NOT wired in
    # (that was scoped to LD-2 proving retrieval independently, per its
    # own module docstring "SCOPE" note). LD-3 (Production RAG Query
    # Path) deliberately connects retrieval.production_corpus.sf05_evidence_pack_builder
    # into api/dependencies.py::get_application_service - this test now
    # asserts that connection exists, in the one file responsible for it,
    # rather than the old absence.
    dependencies_source = (SRC_DIR / "api" / "dependencies.py").read_text(encoding="utf-8")
    service_source = (SRC_DIR / "application" / "service.py").read_text(encoding="utf-8")
    assert "production_corpus" in dependencies_source
    assert "sf05_evidence_pack_builder" in dependencies_source
    # application/service.py itself still never imports production_corpus
    # directly - only referenced in its own docstring commentary, never
    # as a hard import (the wiring lives entirely in api/dependencies.py).
    import ast

    tree = ast.parse(service_source)
    imported_modules = {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    } | {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for _ in [node.module] if node.module}
    assert not any("production_corpus" in (m or "") for m in imported_modules)
