"""FastAPI dependencies. Route handlers receive services, never construct providers."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from clauselens.container import Container


def get_container(request: Request) -> Container:
    return request.app.state.container


class RateLimiter:
    """Per-client sliding window. Per-process only: put a shared limiter (e.g.
    at the edge or in Redis) in front of multi-instance deployments."""

    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def __call__(self, request: Request) -> None:
        forwarded = request.headers.get("x-forwarded-for", "")
        client = forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")
        now = time.monotonic()
        with self._lock:
            q = self._hits[client]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                raise HTTPException(status_code=429, detail="Too many investigations started; try again shortly.")
            q.append(now)


def rate_limit_creates(request: Request) -> None:
    request.app.state.create_limiter(request)
