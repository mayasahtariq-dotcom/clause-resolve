"""Structured logging and lightweight in-process metrics.

Log records are JSON with investigation_id / vendor / stage / provider context
taken from contextvars, so a failing subsystem can be found by filtering on
`stage` and `failure_category`. Metrics are per-process counters exposed at
/metrics in Prometheus text format; a worker process keeps its own counters.
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
import sys
import threading
import time
from collections import defaultdict
from collections.abc import Iterator
from contextvars import ContextVar
from typing import Any

_ctx: ContextVar[dict[str, Any]] = ContextVar("clauselens_log_ctx", default={})  # noqa: B039

_SECRET_RE = re.compile(r"(?i)(api[_-]?key|authorization|bearer|x-api-key|password|secret)([\"'=:\s]+)([^\s\"',]+)")


def redact(text: str) -> str:
    return _SECRET_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", text)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": round(record.created, 3),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": redact(record.getMessage()),
        }
        payload.update(_ctx.get())
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO", json_logs: bool = True) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if json_logs else logging.Formatter("%(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)
    root.setLevel(level.upper())
    # httpx logs full URLs at INFO; keep it quiet so query strings never leak.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


@contextlib.contextmanager
def log_context(**fields: Any) -> Iterator[None]:
    token = _ctx.set({**_ctx.get(), **{k: v for k, v in fields.items() if v is not None}})
    try:
        yield
    finally:
        _ctx.reset(token)


def log_event(logger: logging.Logger, level: int, msg: str, **fields: Any) -> None:
    logger.log(level, msg, extra={"fields": fields})


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)

    def inc(self, name: str, value: float = 1.0, **labels: str) -> None:
        key = (name, tuple(sorted((k, str(v)) for k, v in labels.items())))
        with self._lock:
            self._counters[key] += value

    def observe_duration(self, name: str, seconds: float, **labels: str) -> None:
        self.inc(f"{name}_seconds_sum", seconds, **labels)
        self.inc(f"{name}_seconds_count", 1, **labels)

    @contextlib.contextmanager
    def timer(self, name: str, **labels: str) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self.observe_duration(name, time.perf_counter() - start, **labels)

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            return {
                name + ("{" + ",".join(f'{k}="{v}"' for k, v in labels) + "}" if labels else ""): v
                for (name, labels), v in self._counters.items()
            }

    def prometheus(self) -> str:
        return "".join(f"clauselens_{k} {v}\n" for k, v in sorted(self.snapshot().items()))

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()


metrics = Metrics()
