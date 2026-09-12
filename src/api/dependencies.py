"""
Phase 17 FastAPI dependency wiring
(docs/PHASE_17_BACKEND_PRODUCTIZATION.md Sections F, U, V). This is the
ONLY place a real `ApplicationService` is constructed for the running
app - tests override `get_application_service` via
`app.dependency_overrides` to inject fake/synthetic providers
(docs "TESTABILITY"), never touching the network, a GPU, or an API key.

HONEST DEFAULT: no live Gemini/Qwen adapter exists anywhere in this
repository (Phase 10's own [DEFERRED] boundary) - the default
`ApplicationService` therefore has `generation_provider=None`, and every
`/api/v1/query` call against the unmodified app returns HTTP 503
(`GenerationProviderNotConfiguredError`) until a real provider is wired
in by a future phase or a deployment-specific override.
"""

from __future__ import annotations

from functools import lru_cache

from application.config import BackendConfig
from application.service import ApplicationService


@lru_cache(maxsize=1)
def get_backend_config() -> BackendConfig:
    return BackendConfig.from_env()


def get_application_service() -> ApplicationService:
    config = get_backend_config()
    return ApplicationService(config=config.application)
