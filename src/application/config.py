"""
Phase 17 backend configuration boundary
(docs/PHASE_17_BACKEND_PRODUCTIZATION.md Section U). Three explicitly
separate concerns, per instruction:

1. `EnvironmentConfig` - read from environment variables ONLY. No secret
   value is ever hard-coded as a default; a missing value is simply
   absent (`None`/empty), never silently fabricated.
2. `ApplicationConfig` - explicit, documented application-level knobs
   (input limits, API version, CORS origins). Every default is a plain,
   non-secret value.
3. Providers (`generation_provider`/`translation_provider`/
   `evidence_pack_builder`) are NOT configuration - they are explicit
   Python objects constructed by the caller (`src/api/dependencies.py`
   for the real app, a test for a fake one) and passed directly to
   `application.service.ApplicationService`, never resolved "by magic"
   from a config value (docs Section V, "PROVIDER BOUNDARIES").

No ORM, no database driver, no secrets-management system exists anywhere
in this module.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

BACKEND_CONFIG_SCHEMA_VERSION = "1.0.0"

API_VERSION = "v1"


@dataclass(frozen=True)
class EnvironmentConfig:
    """
    Environment-variable-derived configuration only. `[ENGINEERING
    RECOMMENDATION]` No API key, token, password, or credential is ever
    read, stored, or exposed by this class, by design - a real generation
    provider credential now exists at runtime (LD-1,
    `GENERATION_API_KEY`), but it is read exclusively by
    `generation.provider_factory.build_generation_provider_from_env` and
    handed straight into a provider constructor, deliberately never
    stored on this (or any other) long-lived, potentially-logged/
    serialized dataclass instance.
    """

    cors_allowed_origins: tuple = ()

    @classmethod
    def from_env(cls) -> "EnvironmentConfig":
        raw = os.environ.get("IPSAKTI_CORS_ALLOWED_ORIGINS", "")
        origins = tuple(origin.strip() for origin in raw.split(",") if origin.strip())
        return cls(cors_allowed_origins=origins)


@dataclass(frozen=True)
class ApplicationConfig:
    """Explicit, documented application-level configuration - no hidden default buried in a function body."""

    schema_version: str = BACKEND_CONFIG_SCHEMA_VERSION
    api_version: str = API_VERSION
    max_query_length: int = 4000
    max_formulation_description_length: int = 4000

    def __post_init__(self):
        if not isinstance(self.schema_version, str) or not self.schema_version.strip():
            raise ValueError("schema_version must be a non-empty string")
        if not isinstance(self.api_version, str) or not self.api_version.strip():
            raise ValueError("api_version must be a non-empty string")
        for name in ("max_query_length", "max_formulation_description_length"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer, got {value!r}")

    @property
    def signature(self) -> str:
        return f"backend-config:v{self.schema_version}:api={self.api_version}:max_query={self.max_query_length}"


@dataclass(frozen=True)
class BackendConfig:
    """The full, explicit configuration boundary passed into the FastAPI app factory."""

    environment: EnvironmentConfig = field(default_factory=EnvironmentConfig)
    application: ApplicationConfig = field(default_factory=ApplicationConfig)

    @classmethod
    def from_env(cls) -> "BackendConfig":
        return cls(environment=EnvironmentConfig.from_env(), application=ApplicationConfig())
