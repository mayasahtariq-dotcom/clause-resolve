"""FastAPI application factory. Route handlers stay thin; logic lives in services."""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from clauselens.api.deps import RateLimiter
from clauselens.api.routes import investigations, reports, system
from clauselens.config import Settings, get_settings
from clauselens.container import Container, build_container
from clauselens.domain.errors import ClauseLensError, ErrorCategory
from clauselens.observability import configure_logging, log_context, metrics

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 64 * 1024

_STATUS = {
    ErrorCategory.NOT_FOUND: 404,
    ErrorCategory.INVALID_REQUEST: 422,
    ErrorCategory.BLOCKED: 422,
    ErrorCategory.CONFIGURATION: 503,
    ErrorCategory.UNAVAILABLE: 503,
    ErrorCategory.RATE_LIMITED: 429,
    ErrorCategory.QUOTA: 503,
}


def _error(status: int, code: str, message: str, **extra: object) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message, **extra}}, status_code=status)


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or (container.settings if container else get_settings())
    configure_logging(settings.log_level, settings.log_json)
    container = container or build_container(settings)

    app = FastAPI(title="ClauseLens API", version="0.1.0",
                  description="Evidence-backed comparison of refund, cancellation and subscription policies.")
    app.state.container = container
    app.state.create_limiter = RateLimiter(limit=settings.rate_limit_investigations_per_minute, window_seconds=60)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Idempotency-Key", "Last-Event-ID"],
        allow_credentials=False,
    )

    @app.middleware("http")
    async def guard_and_trace(request: Request, call_next):  # type: ignore[no-untyped-def]
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
            return _error(413, "payload_too_large", "Request body too large")
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        with log_context(request_id=request_id):
            response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        metrics.inc("http_requests_total", method=request.method, status=str(response.status_code // 100) + "xx")
        return response

    @app.exception_handler(ClauseLensError)
    async def clauselens_error(_: Request, exc: ClauseLensError) -> JSONResponse:
        status = _STATUS.get(exc.category, 500)
        if status >= 500:
            logger.warning("request failed: %s", exc.message)
        return _error(status, exc.category.value, exc.message, provider=exc.provider)

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        code = {404: "not_found", 409: "conflict", 422: "invalid_request", 429: "rate_limited"}.get(
            exc.status_code, "error")
        return _error(exc.status_code, code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"loc": list(e.get("loc", [])), "message": e.get("msg", "")} for e in exc.errors()]
        first = details[0]["message"] if details else "Invalid request"
        return _error(422, "invalid_request", first.removeprefix("Value error, "), details=details)

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error")
        return _error(500, "internal", "Internal server error")

    app.include_router(system.router)
    app.include_router(investigations.router)
    app.include_router(reports.router)
    return app
