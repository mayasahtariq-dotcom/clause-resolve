"""Composition root: the only place that turns configuration into provider instances."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from clauselens.config import Settings
from clauselens.observability import log_event
from clauselens.ports.jobs import JobQueue
from clauselens.ports.llm import LLMProvider
from clauselens.ports.repository import Repository
from clauselens.ports.research import ResearchProvider
from clauselens.ports.storage import ArtifactStorage
from clauselens.registry import resolve
from clauselens.services.orchestrator import InvestigationService, InvestigationSubmitter

logger = logging.getLogger(__name__)


@dataclass
class Container:
    settings: Settings
    repository: Repository
    research: ResearchProvider
    llm: LLMProvider
    storage: ArtifactStorage
    service: InvestigationService
    jobs: JobQueue
    submitter: InvestigationSubmitter


def build_container(
    settings: Settings,
    *,
    repository: Repository | None = None,
    research: ResearchProvider | None = None,
    llm: LLMProvider | None = None,
    jobs: JobQueue | None = None,
    storage: ArtifactStorage | None = None,
) -> Container:
    """Build all providers from settings. Explicit instances override (tests).

    Misconfiguration raises ConfigurationError here, at startup, instead of
    surfacing later as a confusing runtime failure.
    """
    repository = repository or resolve("persistence", settings.persistence_provider)(settings)
    research = research or resolve("research", settings.web_research_provider)(settings)
    llm = llm or resolve("llm", settings.llm_provider)(settings)
    storage = storage or resolve("storage", settings.storage_provider)(settings)
    service = InvestigationService(settings=settings, repository=repository, research=research, llm=llm,
                                   storage=storage)
    if jobs is None:
        factory = resolve("jobs", settings.job_queue_provider)
        jobs = factory(settings, runner=lambda inv_id: service.run(inv_id, worker_id="inline"))
    if not jobs.durable:
        log_event(logger, logging.WARNING, "job queue is not durable; queued work is lost on restart",
                  provider=jobs.name)
    if service.is_demo:
        log_event(logger, logging.WARNING, "DEMO providers active: results are fixture data, not real research",
                  research=research.name, llm=llm.name)
    return Container(settings=settings, repository=repository, research=research, llm=llm, storage=storage,
                     service=service, jobs=jobs, submitter=InvestigationSubmitter(repository, jobs, service))
