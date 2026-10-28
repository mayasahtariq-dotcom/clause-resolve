"""Durable path: API-side CeleryJobQueue -> Redis -> real Celery worker -> pipeline."""

from __future__ import annotations

import os
import time

import pytest

from clauselens.adapters.jobs.celery_queue import CeleryJobQueue, make_celery_app
from clauselens.adapters.persistence.models import Base
from clauselens.adapters.persistence.sqlalchemy_repository import SqlAlchemyRepository, create_db_engine
from clauselens.container import build_container
from clauselens.domain.errors import ClauseLensError
from clauselens.domain.models import InvestigationStatus, VendorInput
from tests.conftest import make_settings

REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")


def redis_available() -> bool:
    try:
        import redis

        redis.Redis.from_url(REDIS_URL, socket_connect_timeout=1).ping()
        return True
    except Exception:
        return False


pytestmark = [pytest.mark.redis, pytest.mark.skipif(not redis_available(), reason="Redis not reachable")]


def test_investigation_runs_through_real_celery_worker(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from celery.contrib.testing.worker import start_worker

    from clauselens.worker_tasks import register_tasks

    settings = make_settings(database_url=f"sqlite:///{tmp_path / 'celery.db'}", job_queue_provider="celery",
                             redis_url=REDIS_URL)
    engine = create_db_engine(settings)
    Base.metadata.create_all(engine)
    container = build_container(settings, repository=SqlAlchemyRepository(engine))
    assert isinstance(container.jobs, CeleryJobQueue) and container.jobs.durable
    container.jobs.health_check()

    worker_app = make_celery_app(settings)
    register_tasks(worker_app, lambda: container, max_retries=1)
    with start_worker(worker_app, queues=["investigations"], perform_ping_check=False, pool="solo",
                      shutdown_timeout=10):
        record = container.submitter.submit([VendorInput(name="StudyNest"), VendorInput(name="SkillForge")], [])
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            current = container.repository.get_investigation(record.id)
            if current and current.status.is_terminal:
                break
            time.sleep(0.2)
    assert current is not None and current.status is InvestigationStatus.COMPLETED
    assert current.report_id is not None
    assert any(e.data.get("queue") == "celery" for e in container.repository.list_events(record.id))


def test_unreachable_broker_fails_explicitly() -> None:
    queue = CeleryJobQueue(make_settings(redis_url="redis://127.0.0.1:1/0"))
    with pytest.raises(ClauseLensError) as exc:
        queue.health_check()
    assert exc.value.category.value == "unavailable"
