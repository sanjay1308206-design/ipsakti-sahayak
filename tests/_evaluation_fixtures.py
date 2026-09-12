"""
Phase 16 test-support module: a thin `make_case` convenience wrapper over
`evaluation.models.BenchmarkCase`, for use by tests/test_phase_16_*.py.
Deliberately minimal - every other Phase 3-15 object needed by Phase 16's
own tests is built via the project's EXISTING tests/_*_fixtures.py
modules (never duplicated here).

SYNTHETIC TEST FIXTURE GENERATOR ONLY. Not a test module itself (no test_
prefix) - pytest will not collect it.
"""

from __future__ import annotations

from evaluation.models import BENCHMARK_SCHEMA_VERSION, BenchmarkCase

__all__ = ["make_case"]


def make_case(case_id: str, category: str, ground_truth_origin: str, input_summary: str, expected_behavior: str, **kwargs) -> BenchmarkCase:
    return BenchmarkCase(
        schema_version=BENCHMARK_SCHEMA_VERSION, case_id=case_id, category=category,
        ground_truth_origin=ground_truth_origin, input_summary=input_summary, expected_behavior=expected_behavior, **kwargs,
    )
