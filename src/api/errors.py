"""
Phase 17 HTTP error mapping (docs/PHASE_17_BACKEND_PRODUCTIZATION.md
Section M). Distinguishes 400-class client/input errors from 500-class
unexpected server failures, and from the one explicit application/domain
failure (`GenerationProviderNotConfiguredError`, mapped to 503 -
"unavailable," never a fabricated 200). No handler here ever returns
HTTP 200 for an exception, and no handler ever includes a Python
traceback, exception message with internal detail, filesystem path, or
credential in the response body.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from application.models import ApplicationSchemaError, InvalidQueryError
from application.service import GenerationProviderNotConfiguredError

logger = logging.getLogger("ipsakti.api")


def _error_body(detail: str, error_type: str) -> dict:
    return {"detail": detail, "error_type": error_type}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # FastAPI's own structured validation error - safe to summarize
        # (field names/messages), never the raw exception object.
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_error_body("request payload failed validation", "REQUEST_VALIDATION_ERROR"),
        )

    @app.exception_handler(InvalidQueryError)
    async def _invalid_query_handler(request: Request, exc: InvalidQueryError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content=_error_body(str(exc), "INVALID_QUERY"))

    @app.exception_handler(ApplicationSchemaError)
    async def _application_schema_error_handler(request: Request, exc: ApplicationSchemaError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content=_error_body("malformed application data", "APPLICATION_SCHEMA_ERROR"))

    @app.exception_handler(GenerationProviderNotConfiguredError)
    async def _provider_not_configured_handler(request: Request, exc: GenerationProviderNotConfiguredError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_error_body("a required generation provider is not configured in this environment", "GENERATION_PROVIDER_NOT_CONFIGURED"),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # [OUR ENHANCEMENT] Phase 19 fix: Starlette raises its own
        # HTTPException for framework-level body-parsing failures (invalid
        # UTF-8, a JSON structure deep enough to exhaust the parser's
        # recursion limit) BEFORE this application's own request-validation
        # handler above ever runs, and FastAPI registers a default handler
        # for it ahead of the generic Exception catch-all below - without
        # this explicit handler, that class of request returned a bare
        # Starlette body lacking `error_type`, silently violating this
        # API's one documented ErrorResponse contract (test_error_response_
        # always_matches_error_schema). Starlette's own exc.detail here is
        # already a safe, generic message (never an internal exception
        # string), so it is reused as-is - no new information is added or
        # removed, only the shape is normalized.
        detail = exc.detail if isinstance(exc.detail, str) else "request could not be processed"
        return JSONResponse(status_code=exc.status_code, content=_error_body(detail, "MALFORMED_REQUEST"))

    @app.exception_handler(Exception)
    async def _unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        # Logged server-side ONLY (never sent to the client) - no
        # traceback, no exception message, no filesystem path in the
        # response body (docs "Do NOT leak Python exception traces").
        logger.exception("unhandled exception while processing %s %s", request.method, request.url.path)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=_error_body("internal server error", "INTERNAL_SERVER_ERROR"))
