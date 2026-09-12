"""
Phase 13 engineering-signal policy (docs/PHASE_13_CONFIDENCE_SAFETY_ABSTENTION.md
Sections J, K, R, T). Reuses Phase 9's own already-disclaimed
citation-integrity metrics verbatim - never a new score invented, never
a retrieval score (BM25/dense/RRF/reranker) touched or combined here.

`[ASSUMPTION]` per explicit instruction: no empirically validated
threshold exists anywhere in the Master Reference or any prior-phase
contract for what makes citation coverage "strong" vs "weak". The three
coefficients below are engineering heuristics, chosen for having an
intuitive, inspectable justification (more independently-corroborating
citations, and fewer failed citation attempts, is a more defensible
grounding structure than one citation with several failed attempts
alongside it) - NOT because any calibration study was performed. They
are configurable (`SafetyPolicyConfig`) precisely because they are
disclosed guesses, not fixed constants.
"""

from __future__ import annotations

from citation.metrics import CitationCoverageMetrics

from .models import SafetyPolicyConfig


def compute_engineering_signal_band(citation_summary: CitationCoverageMetrics, config: SafetyPolicyConfig) -> str:
    """
    A CATEGORICAL engineering signal about citation-integrity structure
    only - never a legal-correctness probability (module docstring).
    Uses exactly two already-existing, already-bounded Phase 9 fields:

    - `unique_valid_evidence_id_count`: how many DISTINCT real evidence
      items are actually cited (not merely attempted) - more independent
      real citations is, all else equal, a more defensible grounding
      structure than exactly one.
    - `citation_integrity_validation_rate`: what fraction of citation
      ATTEMPTS were valid (Phase 9's own bounded [0,1] ratio) - a lower
      rate means the provider attempted citations that did not check
      out, even though at least one real one survived.

    STRONG: at least `strong_min_unique_citations` distinct valid
        citations AND an integrity rate of at least `strong_min_integrity_rate`.
    MODERATE: at least one valid citation (guaranteed true whenever this
        function is called from the evaluator, since the NO_VALID_CITATIONS
        gate already ran first) AND a rate of at least `moderate_min_integrity_rate`.
    WEAK: everything else that still reached this function.
    """
    if not isinstance(citation_summary, CitationCoverageMetrics):
        raise TypeError(f"compute_engineering_signal_band expects a CitationCoverageMetrics, got {type(citation_summary).__name__}")
    if not isinstance(config, SafetyPolicyConfig):
        raise TypeError(f"compute_engineering_signal_band expects a SafetyPolicyConfig, got {type(config).__name__}")

    count = citation_summary.unique_valid_evidence_id_count
    rate = citation_summary.citation_integrity_validation_rate

    if count >= config.strong_min_unique_citations and rate >= config.strong_min_integrity_rate:
        return "STRONG"
    if count >= 1 and rate >= config.moderate_min_integrity_rate:
        return "MODERATE"
    return "WEAK"
