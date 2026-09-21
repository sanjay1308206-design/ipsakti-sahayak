"""
Phase 17 FastAPI dependency wiring
(docs/PHASE_17_BACKEND_PRODUCTIZATION.md Sections F, U, V), extended by
LD-1 (Production Generation Provider) and LD-3 (Production RAG Query
Path). This is the ONLY place a real `ApplicationService` is constructed
for the running app - tests override `get_application_service` via
`app.dependency_overrides` to inject fake/synthetic providers (docs
"TESTABILITY"), never touching the network, a GPU, or an API key.

PROVIDER WIRING (LD-1): `get_generation_provider` reads
`GENERATION_PROVIDER`/`GENERATION_MODEL`/`GENERATION_API_KEY` from the
environment (via `generation.provider_factory`) and constructs a real
provider, cached for the life of the process exactly like
`get_backend_config`. If that environment is entirely unset, this
resolves to `None` - the same fail-closed default Phase 17 has always
had: every `/api/v1/query` call then returns HTTP 503
(`GenerationProviderNotConfiguredError`), never a fabricated answer. If
the environment is PARTIALLY or INCORRECTLY configured (e.g.
`GENERATION_PROVIDER` set with no API key), that is logged here as an
explicit server-side error and still falls back to the same `None`/503
path - a misconfigured environment variable must never crash the whole
backend process or silently look identical to "working as intended."

RETRIEVAL WIRING (LD-3): `get_evidence_pack_builder` returns
`retrieval.production_corpus.sf05_evidence_pack_builder` (LD-2) -
unconditionally, not gated on any environment variable, because the real
SF-05 asset is either present and integrity-verified (see
`production_corpus.py`'s own fail-closed checks) or it is not; there is
no partial/degraded "retrieval configured" state analogous to the
generation provider's. This function is called lazily, per request,
exactly like `evidence_pack_builder` always was - constructing
`ApplicationService` here does NOT itself load the corpus (that only
happens inside `ApplicationService.query`, and only after the existing
`generation_provider is None` check already returns HTTP 503 first, so
`/health` and an unconfigured-provider request never touch the corpus).
If the real SF-05 asset is missing/corrupted when `evidence_pack_builder`
IS actually invoked, `production_corpus.ProductionCorpusIntegrityError`
propagates uncaught out of `ApplicationService.query` (pre-existing
behavior - `query` has never wrapped `evidence_pack_builder` in a
try/except) and is caught by this app's existing generic `Exception`
handler (`api/errors.py`), returning a safe, generic HTTP 500 - never a
fabricated answer, never a leaked traceback. This was a deliberate
LD-3 decision, not an oversight: see this phase's own implementation
report for the reasoning.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Callable, Optional

from application.config import BackendConfig
from application.service import ApplicationService
from evidence.models import EvidencePack
from generation.provider_factory import GenerationProviderConfigError, build_generation_provider_from_env
from generation.providers import GenerationProvider
from retrieval.production_corpus import sf05_evidence_pack_builder

logger = logging.getLogger("ipsakti.api")


@lru_cache(maxsize=1)
def get_backend_config() -> BackendConfig:
    return BackendConfig.from_env()


@lru_cache(maxsize=1)
def get_generation_provider() -> Optional[GenerationProvider]:
    try:
        return build_generation_provider_from_env()
    except GenerationProviderConfigError as exc:
        logger.error("generation provider misconfigured; falling back to unconfigured (HTTP 503) - %s", exc)
        return None


def get_evidence_pack_builder() -> Callable[[str], EvidencePack]:
    return sf05_evidence_pack_builder


def get_application_service() -> ApplicationService:
    config = get_backend_config()
    return ApplicationService(
        config=config.application,
        generation_provider=get_generation_provider(),
        evidence_pack_builder=get_evidence_pack_builder(),
    )
