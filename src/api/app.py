"""
Phase 17 FastAPI application factory
(docs/PHASE_17_BACKEND_PRODUCTIZATION.md Sections D, E, AA, AC). This is
the only module that constructs a `FastAPI` instance. It wires the
router and exception handlers and, only if explicitly configured via the
`IPSAKTI_CORS_ALLOWED_ORIGINS` environment variable, adds CORS - never an
unrestricted wildcard by default (docs "CORS").
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from application.config import API_VERSION, BackendConfig

from .errors import register_exception_handlers
from .routes import router

APP_TITLE = "IP-SAKTI Sahayak Backend"
APP_DESCRIPTION = (
    "Backend application boundary over the existing Phase 0-16 regulatory-intelligence domain modules. "
    "This API does NOT itself decide jurisdiction, classification, evidence validity, citation validity, "
    "safety, or grounding - those decisions are made by the underlying domain modules and only reported "
    "here. This is NOT a production-ready system (see docs/PHASE_17_BACKEND_PRODUCTIZATION.md)."
)


def create_app(config: Optional[BackendConfig] = None) -> FastAPI:
    if config is None:
        config = BackendConfig.from_env()

    app = FastAPI(title=APP_TITLE, description=APP_DESCRIPTION, version=API_VERSION)
    register_exception_handlers(app)
    app.include_router(router)

    if config.environment.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(config.environment.cors_allowed_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )

    return app


app = create_app()
