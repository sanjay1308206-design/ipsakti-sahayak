"""
Phase 13 tests: the engineering-signal band computation
(docs/PHASE_13_CONFIDENCE_SAFETY_ABSTENTION.md Sections J, K). Reuses
Phase 9's own already-bounded, already-disclaimed citation-integrity
metrics verbatim - never a new score invented, never a retrieval score
combined.
"""

from __future__ import annotations

import pytest

from citation.metrics import CitationCoverageMetrics
from safety.models import SafetyPolicyConfig
from safety.policy import compute_engineering_signal_band


def _metrics(total, valid, invalid, unresolved, unique_valid, duplicates, rate):
    return CitationCoverageMetrics(
        schema_version="1.0.0", total_references=total, valid_count=valid, invalid_count=invalid,
        unresolved_count=unresolved, unique_valid_evidence_id_count=unique_valid,
        duplicate_occurrence_count=duplicates, citation_integrity_validation_rate=rate,
    )


def test_strong_band_two_clean_citations():
    metrics = _metrics(2, 2, 0, 0, 2, 0, 1.0)
    assert compute_engineering_signal_band(metrics, SafetyPolicyConfig()) == "STRONG"


def test_moderate_band_one_clean_citation():
    metrics = _metrics(1, 1, 0, 0, 1, 0, 1.0)
    assert compute_engineering_signal_band(metrics, SafetyPolicyConfig()) == "MODERATE"


def test_weak_band_one_citation_with_failed_attempts():
    metrics = _metrics(3, 1, 1, 1, 1, 0, 1 / 3)
    assert compute_engineering_signal_band(metrics, SafetyPolicyConfig()) == "WEAK"


def test_strong_band_requires_full_integrity_rate():
    # Two unique valid citations but a failed attempt alongside them ->
    # not STRONG (rate < 1.0), falls to MODERATE.
    metrics = _metrics(3, 2, 1, 0, 2, 0, 2 / 3)
    assert compute_engineering_signal_band(metrics, SafetyPolicyConfig()) == "MODERATE"


def test_band_is_configurable():
    metrics = _metrics(1, 1, 0, 0, 1, 0, 1.0)
    lenient_config = SafetyPolicyConfig(strong_min_unique_citations=1, strong_min_integrity_rate=1.0)
    assert compute_engineering_signal_band(metrics, lenient_config) == "STRONG"


def test_band_computation_rejects_wrong_types():
    with pytest.raises(TypeError):
        compute_engineering_signal_band("not metrics", SafetyPolicyConfig())
    with pytest.raises(TypeError):
        compute_engineering_signal_band(_metrics(1, 1, 0, 0, 1, 0, 1.0), "not config")


def test_band_computation_is_deterministic():
    metrics = _metrics(2, 2, 0, 0, 2, 0, 1.0)
    config = SafetyPolicyConfig()
    results = {compute_engineering_signal_band(metrics, config) for _ in range(10)}
    assert len(results) == 1


def test_band_never_labeled_as_probability_in_source():
    # The source is allowed to MENTION "probability" only to explicitly
    # disclaim it (e.g. "never a legal-correctness probability") - it must
    # never present the band computation itself as producing one.
    import inspect
    import re

    from safety import policy

    source = inspect.getsource(policy)
    for line in source.lower().splitlines():
        if "probability" in line:
            assert "never" in line or "not a" in line, f"unqualified 'probability' mention: {line!r}"
    assert not re.search(r"return\s+\w*probability", source.lower())
