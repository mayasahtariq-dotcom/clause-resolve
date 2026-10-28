"""In-process job execution. NOT durable: queued work is lost if the process
restarts. Intended for local development (inline) and tests (sync); production
configuration rejects both unless ALLOW_NON_DURABLE_QUEUE=true."""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from uuid import UUID

from clauselens.config import Settings

logger = logging.getLogger(__name__)
Runner = Callable[[UUID], None]


def _log_crash(future: Future[None]) -> None:
    exc = future.exception()
    if exc is not None:
        logger.error("inline job crashed", exc_info=exc)


class InlineThreadJobQueue:
    name = "inline"
    durable = False

    def __init__(self, runner: Runner, max_workers: int = 2) -> None:
        self._runner = runner
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="investigation")

    def submit_investigation(self, investigation_id: UUID) -> None:
        future = self._pool.submit(self._runner, investigation_id)
        future.add_done_callback(_log_crash)

    def health_check(self) -> None:
        return None


class SyncJobQueue:
    """Runs the job before submit returns. Deterministic; used by tests."""

    name = "sync"
    durable = False

    def __init__(self, runner: Runner) -> None:
        self._runner = runner

    def submit_investigation(self, investigation_id: UUID) -> None:
        self._runner(investigation_id)

    def health_check(self) -> None:
        return None


def create_inline(settings: Settings, runner: Runner) -> InlineThreadJobQueue:
    return InlineThreadJobQueue(runner)


def create_sync(settings: Settings, runner: Runner) -> SyncJobQueue:
    return SyncJobQueue(runner)
