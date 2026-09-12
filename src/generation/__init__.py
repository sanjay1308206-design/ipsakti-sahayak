"""
Phase 10 - Grounded Generation (docs/PHASE_10_GROUNDED_GENERATION.md).

Transforms Phase 8 EvidencePack + a provider's raw output into a
structured GroundedResponse, with every claimed citation filtered through
Phase 9's own validator. The LLM is never the source of truth - Evidence
is. Deterministic orchestration; no network access anywhere in this
package (only src/evidence and src/citation are depended on, plus a
deterministic FakeGenerationProvider for tests).
"""
