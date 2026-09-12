"""
Phase 16 - Evaluation + Red-Team Benchmark (docs/PHASE_16_EVALUATION_AND_RED_TEAM.md).

Measures the behavior of the system built in Phases 0-15 as it actually
is - it never changes retrieval algorithms, classification rules,
jurisdiction logic, citation validation, grounding logic, safety
thresholds, multilingual logic, or human-review semantics to make a
benchmark pass. If the system fails a benchmark, this package reports the
failure and identifies the responsible phase/component - it never hides
or "fixes" a failure inside the evaluator.

ARCHITECTURE: this package is the METRICS/COMPARISON/REPORTING layer, not
a duplicate pipeline orchestrator. `benchmark.py` and `redteam.py` accept
already-computed real Phase 3-15 objects (built by a caller - a test file
reusing the project's existing `tests/_*_fixtures.py` modules, exactly
like every earlier phase's own `test_phase_XX_evaluation.py` already did)
and turn them into structured, deterministic, versioned results. This
package never scrapes the internet, never fabricates a regulatory ground
truth, and never invents a benchmark result - every metric is either
computed from a real synthetic case or explicitly marked NOT_RUN /
NOT_APPLICABLE / NOT_VALIDATED.
"""
