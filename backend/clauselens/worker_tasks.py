"""Celery task registration, free of import-time side effects (testable)."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from clauselens.adapters.jobs.celery_queue import TASK_NAME
from clauselens.container import Container
from clauselens.domain.errors import ClauseLensError


def register_tasks(app, get_container: Callable[[], Container], max_retries: int):  # type: ignore[no-untyped-def]
    # shared=False: bind to this app only (Celery shares tasks across apps by default).
    @app.task(name=TASK_NAME, bind=True, max_retries=max_retries, shared=False)
    def run_investigation(self, investigation_id: str) -> None:  # type: ignore[no-untyped-def]
        try:
            # The task id is stable across retries and redeliveries, so a retried
            # task can reclaim its own lease while other workers cannot.
            get_container().service.run(UUID(investigation_id), worker_id=f"celery:{self.request.id}")
        except ClauseLensError as exc:
            if exc.transient:
                raise self.retry(exc=exc, countdown=min(60, 5 * 2 ** self.request.retries)) from exc
            raise

    return run_investigation
