"""Shared HTTP helpers for provider adapters: bounded retries and error translation."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from typing import Any

import httpx

from clauselens.domain.errors import ClauseLensError, ErrorCategory
from clauselens.observability import log_event, metrics

logger = logging.getLogger(__name__)

MAX_BACKOFF_SECONDS = 30.0


def category_for_status(status: int) -> ErrorCategory:
    if status == 401:
        return ErrorCategory.AUTHENTICATION
    if status in (402,):
        return ErrorCategory.QUOTA
    if status == 403:
        return ErrorCategory.BLOCKED  # forbidden: entitlement, legacy credits, or upstream refusal
    if status == 404:
        return ErrorCategory.NOT_FOUND
    if status == 408:
        return ErrorCategory.TIMEOUT
    if status == 429:
        return ErrorCategory.RATE_LIMITED
    if status >= 500:
        return ErrorCategory.UNAVAILABLE
    return ErrorCategory.INVALID_REQUEST


def error_message(response: httpx.Response) -> str:
    """Best-effort extraction of a provider error message (never includes request headers)."""
    try:
        body = response.json()
    except ValueError:
        return response.text[:300] or response.reason_phrase
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            code = err.get("code")
            msg = err.get("message") or ""
            return f"{code}: {msg}" if code else str(msg)
        if isinstance(err, str):
            return err
        if "message" in body:
            return str(body["message"])
    return str(body)[:300]


def send_with_retries(
    send: Callable[[], httpx.Response],
    *,
    provider: str,
    operation: str,
    max_retries: int,
    error_cls: type[ClauseLensError],
    sleep: Callable[[float], None] | None = None,
) -> httpx.Response:
    """Call `send` and return a 2xx response, retrying transient failures only."""
    attempt = 0
    while True:
        started = time.perf_counter()
        try:
            response = send()
        except httpx.TimeoutException as exc:
            err: ClauseLensError = error_cls(f"{provider} {operation} timed out", category=ErrorCategory.TIMEOUT,
                                             provider=provider)
            cause: Exception | None = exc
        except httpx.HTTPError as exc:
            err = error_cls(f"{provider} {operation} network error: {type(exc).__name__}",
                            category=ErrorCategory.UNAVAILABLE, provider=provider)
            cause = exc
        else:
            metrics.observe_duration("provider_request", time.perf_counter() - started,
                                     provider=provider, operation=operation)
            if response.is_success:
                return response
            retry_after = None
            if "retry-after" in response.headers:
                try:
                    retry_after = float(response.headers["retry-after"])
                except ValueError:
                    retry_after = None
            err = error_cls(
                f"{provider} {operation} failed with HTTP {response.status_code}: {error_message(response)}",
                category=category_for_status(response.status_code),
                provider=provider,
                retry_after=retry_after,
            )
            cause = None

        metrics.inc("provider_errors_total", provider=provider, operation=operation, category=err.category.value)
        if not err.transient or attempt >= max_retries:
            log_event(logger, logging.WARNING, "provider request failed", provider=provider, operation=operation,
                      failure_category=err.category.value, retry_count=attempt)
            if cause is not None:
                raise err from cause
            raise err
        delay = min(MAX_BACKOFF_SECONDS, err.retry_after or (2 ** attempt + random.uniform(0, 0.5)))
        attempt += 1
        log_event(logger, logging.INFO, "retrying provider request", provider=provider, operation=operation,
                  retry_count=attempt, delay_seconds=round(delay, 2), failure_category=err.category.value)
        (sleep or time.sleep)(delay)


def json_body(response: httpx.Response, *, provider: str, operation: str,
              error_cls: type[ClauseLensError]) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        raise error_cls(f"{provider} {operation} returned non-JSON content",
                        category=ErrorCategory.MALFORMED_OUTPUT, provider=provider) from exc
