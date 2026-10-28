"""Celery + Redis job queue (durable). Submits by task name, so the API process
never imports worker code and the domain never sees Celery types."""

from __future__ import annotations

from uuid import UUID

from clauselens.config import Settings
from clauselens.domain.errors import ClauseLensError, ErrorCategory

TASK_NAME = "clauselens.run_investigation"
PROVIDER = "celery"


def make_celery_app(settings: Settings):  # type: ignore[no-untyped-def]
    from celery import Celery

    app = Celery("clauselens", broker=settings.redis_url, backend=None)
    app.conf.update(
        task_acks_late=True,  # redeliver if the worker dies mid-task
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_default_queue="investigations",
        broker_transport_options={"visibility_timeout": settings.job_lease_seconds + 60},
        broker_connection_retry_on_startup=True,
        task_serializer="json",
        accept_content=["json"],
    )
    return app


class CeleryJobQueue:
    name = PROVIDER
    durable = True

    def __init__(self, settings: Settings) -> None:
        self._app = make_celery_app(settings)

    def submit_investigation(self, investigation_id: UUID) -> None:
        try:
            self._app.send_task(TASK_NAME, args=[str(investigation_id)])
        except Exception as exc:  # kombu raises several connection error types
            raise ClauseLensError(f"Could not enqueue investigation: {type(exc).__name__}",
                                  category=ErrorCategory.UNAVAILABLE, provider=PROVIDER) from exc

    def health_check(self) -> None:
        try:
            with self._app.connection_for_write() as conn:
                conn.ensure_connection(max_retries=1, timeout=3)
        except Exception as exc:
            raise ClauseLensError(f"Job broker unreachable: {type(exc).__name__}",
                                  category=ErrorCategory.UNAVAILABLE, provider=PROVIDER) from exc


def create(settings: Settings, runner=None) -> CeleryJobQueue:  # type: ignore[no-untyped-def]
    return CeleryJobQueue(settings)
