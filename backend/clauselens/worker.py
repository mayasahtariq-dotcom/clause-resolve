"""Celery worker entry point.

    celery -A clauselens.worker worker --loglevel INFO --concurrency 2 -Q investigations
"""

from __future__ import annotations

from clauselens.adapters.jobs.celery_queue import make_celery_app
from clauselens.config import get_settings
from clauselens.container import Container, build_container
from clauselens.observability import configure_logging
from clauselens.worker_tasks import register_tasks

settings = get_settings()
configure_logging(settings.log_level, settings.log_json)
app = make_celery_app(settings)
_container: Container | None = None


def _get_container() -> Container:
    global _container
    if _container is None:
        _container = build_container(settings)
    return _container


run_investigation = register_tasks(app, _get_container, settings.job_max_retries)
