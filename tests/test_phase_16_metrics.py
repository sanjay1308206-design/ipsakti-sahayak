"""
Phase 16 tests: the zero-denominator-safe rate helpers
(docs/PHASE_16_EVALUATION_AND_RED_TEAM.md Section Z).
"""

from __future__ import annotations

import pytest

from evaluation.metrics import build_not_run_result, build_rate_result, safe_rate


def test_safe_rate_normal_division():
    assert safe_rate(3, 4) == 0.75


def test_safe_rate_zero_denominator_returns_none():
    assert safe_rate(0, 0) is None


def test_safe_rate_zero_numerator_nonzero_denominator_is_a_real_zero():
    assert safe_rate(0, 5) == 0.0


def test_safe_rate_rejects_negative_numerator():
    with pytest.raises(ValueError):
        safe_rate(-1, 5)


def test_safe_rate_rejects_numerator_exceeding_denominator():
    with pytest.raises(ValueError):
        safe_rate(6, 5)


def test_build_rate_result_applicable_case():
    result = build_rate_result(
        metric_name="X", component="CLASSIFICATION", numerator=2, denominator=4,
        explanation_if_applicable="ok", explanation_if_not_applicable="n/a", schema_version="1.0.0",
    )
    assert result.applicable is True
    assert result.value == 0.5
    assert result.explanation == "ok"


def test_build_rate_result_zero_denominator_is_not_applicable():
    result = build_rate_result(
        metric_name="X", component="CLASSIFICATION", numerator=0, denominator=0,
        explanation_if_applicable="ok", explanation_if_not_applicable="n/a", schema_version="1.0.0",
    )
    assert result.applicable is False
    assert result.value is None
    assert result.explanation == "n/a"


def test_build_not_run_result_is_never_applicable():
    result = build_not_run_result(metric_name="X", component="CLASSIFICATION", reason="real model unavailable", schema_version="1.0.0")
    assert result.applicable is False
    assert result.value is None
    assert "NOT RUN" in result.explanation
    assert "real model unavailable" in result.explanation
