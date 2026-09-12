"""
Phase 17 - HTTP/API boundary (docs/PHASE_17_BACKEND_PRODUCTIZATION.md).

FastAPI lives ONLY here. This package handles HTTP request parsing,
schema validation, response serialization, HTTP status mapping,
dependency wiring, exception translation, and OpenAPI documentation - it
never decides jurisdiction, regulatory category, evidence validity,
citation validity, safety, grounding, or reviewer authorization. Every
such decision is made by `src/application/service.ApplicationService`,
which in turn calls the existing, unmodified Phase 8-15 domain modules.
"""
