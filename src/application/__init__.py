"""
Phase 17 - Application layer (docs/PHASE_17_BACKEND_PRODUCTIZATION.md).

Orchestrates the existing, unmodified Phase 8-15 domain modules for one
incoming query - it never re-implements classification, jurisdiction
routing, retrieval, evidence construction, citation validation, grounded
generation, safety policy, multilingual delivery, or human-review
semantics. Plain Python dataclasses only (`models.py`) plus one
orchestration class (`service.py`) - no FastAPI, no Pydantic, no HTTP
anywhere in this package, so it is fully testable without a network
server (`src/api/` is the only place HTTP concerns live).
"""
