"""
Phase 10 orchestration (docs/PHASE_10_GROUNDED_GENERATION.md Sections D,
E, N, O). The only place in this package that ties evidence + provider +
citation validation together into one deterministic decision:

    EvidencePack --(check_evidence_pack_validity, Phase 9)--> usable?
        no  -> ABSTAINED / NO_EVIDENCE_AVAILABLE (provider never called)
        yes -> build_prompt -> provider.generate(prompt)
            provider raised / returned invalid shape / success=False
                -> GENERATION_FAILED
            success
                -> extract_citation_references(raw_text)
                -> validate_citations(references, pack)      [Phase 9, reused]
                -> zero VALID and config.require_citations
                    -> ABSTAINED / NO_VALID_CITATIONS_PRODUCED
                -> otherwise
                    -> GROUNDED

The LLM never controls: evidence content, evidence identity, citation
validity, or the final grounding_status - this function does, and it is
100% deterministic given deterministic provider output.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from citation.metrics import compute_citation_coverage
from citation.validator import check_evidence_pack_validity, validate_citations
from evidence.models import EvidencePack

from .grounding import extract_citation_references
from .models import (
    REASON_NO_EVIDENCE_AVAILABLE,
    REASON_NO_VALID_CITATIONS_PRODUCED,
    GenerationConfig,
    GenerationOutput,
    GroundedResponse,
)
from .prompts import build_prompt
from .providers import GenerationProvider


def compute_response_id(
    schema_version: str,
    query: str,
    canonical_query: Optional[str],
    pack_id: str,
    provider_name: str,
    model_identifier: str,
    grounding_status: str,
    answer_text: Optional[str],
    cited_evidence_ids: list,
) -> str:
    """
    Deterministic, backend-owned response identity (mirrors Phase 8/9's
    own SHA-256-over-canonical-fields convention) - never a random UUID,
    never derived from anything the provider could manipulate beyond the
    fields it legitimately controls (its own name/identifier/answer text).
    """
    canonical = "|".join(
        [
            "grounded-response-v1",
            schema_version,
            query,
            canonical_query or "",
            pack_id,
            provider_name,
            model_identifier,
            grounding_status,
            answer_text or "",
            ",".join(cited_evidence_ids),
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _abstain(
    *,
    schema_version: str,
    query: str,
    canonical_query: Optional[str],
    pack: EvidencePack,
    provider: GenerationProvider,
    reason: str,
    coverage,
) -> GroundedResponse:
    response_id = compute_response_id(
        schema_version, query, canonical_query, pack.pack_id, provider.provider_name, provider.model_identifier,
        "ABSTAINED", None, [],
    )
    return GroundedResponse(
        schema_version=schema_version,
        response_id=response_id,
        query=query,
        canonical_query=canonical_query,
        answer_text=None,
        cited_evidence_ids=[],
        citation_validation_summary=coverage,
        grounding_status="ABSTAINED",
        abstained=True,
        abstention_reason=reason,
        failure_reason=None,
        provider_name=provider.provider_name,
        model_identifier=provider.model_identifier,
        generation_metadata={"evidence_item_count": len(pack.evidence_items)},
        synthetic=any(e.synthetic for e in pack.evidence_items),
        evidence_pack_id=pack.pack_id,
    )


def _fail(
    *,
    schema_version: str,
    query: str,
    canonical_query: Optional[str],
    pack: EvidencePack,
    provider: GenerationProvider,
    failure_reason: str,
    coverage,
) -> GroundedResponse:
    response_id = compute_response_id(
        schema_version, query, canonical_query, pack.pack_id, provider.provider_name, provider.model_identifier,
        "GENERATION_FAILED", None, [],
    )
    return GroundedResponse(
        schema_version=schema_version,
        response_id=response_id,
        query=query,
        canonical_query=canonical_query,
        answer_text=None,
        cited_evidence_ids=[],
        citation_validation_summary=coverage,
        grounding_status="GENERATION_FAILED",
        abstained=False,
        abstention_reason=None,
        failure_reason=failure_reason,
        provider_name=provider.provider_name,
        model_identifier=provider.model_identifier,
        generation_metadata={"evidence_item_count": len(pack.evidence_items)},
        synthetic=any(e.synthetic for e in pack.evidence_items),
        evidence_pack_id=pack.pack_id,
    )


def generate_grounded_response(
    query: str,
    pack: EvidencePack,
    provider: GenerationProvider,
    config: Optional[GenerationConfig] = None,
    canonical_query: Optional[str] = None,
) -> GroundedResponse:
    """The sole Phase 10 entry point. See module docstring for the decision flow."""
    if not isinstance(query, str):
        raise TypeError(f"generate_grounded_response expects query to be a string, got {type(query).__name__}")
    if not isinstance(pack, EvidencePack):
        raise TypeError(f"generate_grounded_response expects an EvidencePack, got {type(pack).__name__}")
    if not isinstance(provider, GenerationProvider):
        raise TypeError(f"generate_grounded_response expects a GenerationProvider, got {type(provider).__name__}")
    if config is None:
        config = GenerationConfig()
    elif not isinstance(config, GenerationConfig):
        raise TypeError(f"generate_grounded_response expects a GenerationConfig or None, got {type(config).__name__}")
    if canonical_query is not None and not isinstance(canonical_query, str):
        raise TypeError(
            f"generate_grounded_response expects canonical_query to be a string or None, got {type(canonical_query).__name__}"
        )

    schema_version = config.schema_version
    empty_coverage = compute_citation_coverage([])

    # EvidencePack must itself be trustworthy (Phase 9's own pack-identity
    # gate, reused verbatim) AND non-empty - never generate against a
    # corrupted or empty pack.
    pack_error = check_evidence_pack_validity(pack)
    if pack_error is not None or not pack.evidence_items:
        return _abstain(
            schema_version=schema_version, query=query, canonical_query=canonical_query, pack=pack,
            provider=provider, reason=REASON_NO_EVIDENCE_AVAILABLE, coverage=empty_coverage,
        )

    prompt = build_prompt(query, canonical_query, pack, config)

    try:
        output = provider.generate(prompt)
    except Exception as exc:  # noqa: BLE001 - a third-party provider must never crash this orchestrator
        return _fail(
            schema_version=schema_version, query=query, canonical_query=canonical_query, pack=pack,
            provider=provider, failure_reason=f"provider raised an exception: {exc}", coverage=empty_coverage,
        )

    if not isinstance(output, GenerationOutput):
        return _fail(
            schema_version=schema_version, query=query, canonical_query=canonical_query, pack=pack,
            provider=provider, failure_reason=f"provider returned an invalid output type: {type(output).__name__}",
            coverage=empty_coverage,
        )
    if not output.success:
        return _fail(
            schema_version=schema_version, query=query, canonical_query=canonical_query, pack=pack,
            provider=provider, failure_reason=output.failure_reason, coverage=empty_coverage,
        )

    references = extract_citation_references(output.raw_text)
    validation_results = validate_citations(references, pack)
    coverage = compute_citation_coverage(validation_results)

    cited_evidence_ids = []
    seen = set()
    for result in validation_results:
        if result.status == "VALID" and result.resolved_evidence.evidence_id not in seen:
            seen.add(result.resolved_evidence.evidence_id)
            cited_evidence_ids.append(result.resolved_evidence.evidence_id)

    if config.require_citations and not cited_evidence_ids:
        return _abstain(
            schema_version=schema_version, query=query, canonical_query=canonical_query, pack=pack,
            provider=provider, reason=REASON_NO_VALID_CITATIONS_PRODUCED, coverage=coverage,
        )

    response_id = compute_response_id(
        schema_version, query, canonical_query, pack.pack_id, provider.provider_name, provider.model_identifier,
        "GROUNDED", output.raw_text, cited_evidence_ids,
    )
    return GroundedResponse(
        schema_version=schema_version,
        response_id=response_id,
        query=query,
        canonical_query=canonical_query,
        answer_text=output.raw_text,
        cited_evidence_ids=cited_evidence_ids,
        citation_validation_summary=coverage,
        grounding_status="GROUNDED",
        abstained=False,
        abstention_reason=None,
        failure_reason=None,
        provider_name=provider.provider_name,
        model_identifier=provider.model_identifier,
        generation_metadata={
            "evidence_item_count": len(pack.evidence_items),
            "citation_marker_count": len(references),
        },
        synthetic=any(e.synthetic for e in pack.evidence_items),
        evidence_pack_id=pack.pack_id,
    )
