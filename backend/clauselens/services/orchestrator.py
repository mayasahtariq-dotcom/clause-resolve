"""Investigation workflow: research -> extract -> validate -> compare -> report.

Depends only on ports and domain logic. Each phase is reflected in the
persisted investigation status and in the event log streamed to the UI, so
progress shown to the user is always the real state.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from clauselens.config import Settings
from clauselens.domain.aggregation import aggregate_claims
from clauselens.domain.comparison import compare
from clauselens.domain.errors import ClauseLensError, ErrorCategory
from clauselens.domain.models import (
    ComparisonReport,
    InvestigationStatus,
    Priority,
    RetrievedSource,
    Vendor,
    VendorInput,
    VendorPolicy,
    VendorRunStatus,
)
from clauselens.observability import log_context, log_event, metrics
from clauselens.ports.jobs import JobQueue
from clauselens.ports.llm import LLMProvider
from clauselens.ports.repository import InvestigationRecord, Repository
from clauselens.ports.research import ResearchProvider, ResearchRequest
from clauselens.ports.storage import ArtifactStorage
from clauselens.services.explanation import generate_explanation
from clauselens.services.extraction import ExtractionOutcome, extract_policy

logger = logging.getLogger(__name__)


@dataclass
class _VendorWork:
    vendor: Vendor
    sources: list[RetrievedSource] = field(default_factory=list)
    extraction: ExtractionOutcome | None = None
    error: dict[str, str | None] | None = None
    policy: VendorPolicy | None = None


def _err(exc: Exception, stage: str) -> dict[str, str | None]:
    if isinstance(exc, ClauseLensError):
        return {**exc.to_dict(), "stage": stage}
    return {"message": "Unexpected internal error", "category": ErrorCategory.INTERNAL.value,
            "provider": None, "stage": stage}


class InvestigationService:
    def __init__(self, *, settings: Settings, repository: Repository, research: ResearchProvider,
                 llm: LLMProvider, storage: ArtifactStorage) -> None:
        self.settings = settings
        self.repo = repository
        self.research = research
        self.llm = llm
        self.storage = storage

    @property
    def is_demo(self) -> bool:
        return bool(self.research.is_demo or self.llm.is_demo)

    def providers(self) -> dict[str, str]:
        return {"research": self.research.name, "llm": self.llm.name, "llm_model": self.llm.model}

    # ------------------------------------------------------------------ helpers
    def _event(self, inv_id: uuid.UUID, stage: str, message: str, *, level: str = "info",
               vendor: str | None = None, **data: Any) -> None:
        self.repo.add_event(inv_id, stage=stage, message=message, level=level, vendor_name=vendor, data=data)
        log_event(logger, logging.WARNING if level != "info" else logging.INFO, message, stage=stage,
                  vendor=vendor, **{k: v for k, v in data.items() if isinstance(v, str | int | float | bool)})

    def _phase(self, inv_id: uuid.UUID, status: InvestigationStatus, message: str, worker_id: str) -> None:
        self.repo.set_status(inv_id, status)
        self.repo.renew_lease(inv_id, worker_id=worker_id, lease_seconds=self.settings.job_lease_seconds)
        self._event(inv_id, status.value, message)

    # ----------------------------------------------------------------- phases
    def _research(self, inv_id: uuid.UUID, w: _VendorWork, domain_hint: str | None) -> None:
        name = w.vendor.name
        with log_context(investigation_id=str(inv_id), vendor=name, stage="research", provider=self.research.name):
            self.repo.set_vendor_run(inv_id, w.vendor.id, VendorRunStatus.RESEARCHING)
            self._event(inv_id, "research", f"Searching official site for {name} policy pages", vendor=name)
            started = time.perf_counter()
            try:
                result = self.research.investigate_vendor(ResearchRequest(
                    vendor_name=name, domain=domain_hint, max_pages=self.settings.research_max_pages_per_vendor))
            except Exception as exc:  # noqa: BLE001 - translated below, never swallowed silently
                w.error = _err(exc, "research")
                metrics.inc("research_failures_total", provider=self.research.name,
                            category=w.error["category"] or "internal")
                if not isinstance(exc, ClauseLensError):
                    logger.exception("unexpected research failure")
                self.repo.set_vendor_run(inv_id, w.vendor.id, VendorRunStatus.FAILED, error=w.error)
                self._event(inv_id, "research", f"Research failed: {w.error['message']}", level="error",
                            vendor=name, category=w.error["category"])
                return
            metrics.observe_duration("research", time.perf_counter() - started, provider=self.research.name)
            w.sources = result.sources
            self.repo.save_sources(inv_id, w.vendor.id, result.sources)
            if self.storage.name != "none":
                payload = json.dumps(result.model_dump(mode="json"), ensure_ascii=False).encode()
                self.storage.put(f"investigations/{inv_id}/{w.vendor.id}/research.json", payload, "application/json")
            self.repo.set_vendor_run(inv_id, w.vendor.id, VendorRunStatus.RESEARCHING, domain=result.resolved_domain,
                                     domain_source=result.domain_source, source_count=len(result.sources))
            self._event(inv_id, "research",
                        f"Retrieved {len(result.sources)} page(s) from {result.resolved_domain}"
                        + (" (domain inferred from search; verify it is the official site)"
                           if result.domain_source == "search" else ""),
                        vendor=name, domain=result.resolved_domain or "", pages=len(result.sources),
                        urls=[s.final_url or s.url for s in result.sources])
            for f in result.failures:
                self._event(inv_id, "research", f"Could not retrieve {f.url}: {f.reason}", level="warning",
                            vendor=name, reason=f.reason)
            for s in result.sources:
                if s.injection_suspected:
                    self._event(inv_id, "research",
                                f"Page {s.source_key} contains text that looks like instructions to an AI; "
                                "it is treated strictly as data", level="warning", vendor=name, source=s.source_key)
            if not result.sources:
                w.error = {"message": "No policy pages could be retrieved for this vendor",
                           "category": ErrorCategory.NOT_FOUND.value, "provider": self.research.name,
                           "stage": "research"}
                self.repo.set_vendor_run(inv_id, w.vendor.id, VendorRunStatus.FAILED, error=w.error)
                self._event(inv_id, "research", w.error["message"] or "", level="error", vendor=name)

    def _extract(self, inv_id: uuid.UUID, w: _VendorWork) -> None:
        name = w.vendor.name
        with log_context(investigation_id=str(inv_id), vendor=name, stage="extract", provider=self.llm.name):
            self.repo.set_vendor_run(inv_id, w.vendor.id, VendorRunStatus.EXTRACTING)
            self._event(inv_id, "extracting", f"Extracting policy terms from {len(w.sources)} page(s)", vendor=name)
            started = time.perf_counter()
            try:
                w.extraction = extract_policy(self.llm, name, w.sources,
                                              max_input_chars=self.settings.llm_max_input_chars)
            except Exception as exc:  # noqa: BLE001
                w.error = _err(exc, "extraction")
                metrics.inc("llm_failures_total", provider=self.llm.name, category=w.error["category"] or "internal")
                if not isinstance(exc, ClauseLensError):
                    logger.exception("unexpected extraction failure")
                self.repo.set_vendor_run(inv_id, w.vendor.id, VendorRunStatus.FAILED, error=w.error)
                self._event(inv_id, "extracting", f"Extraction failed: {w.error['message']}", level="error",
                            vendor=name, category=w.error["category"])
                return
            metrics.observe_duration("extraction", time.perf_counter() - started, provider=self.llm.name)
            self._event(inv_id, "extracting", f"Model proposed {len(w.extraction.claims)} claim(s)", vendor=name,
                        claims=len(w.extraction.claims))
            for warning in w.extraction.warnings:
                self._event(inv_id, "validating", warning, level="warning", vendor=name)

    def _validate(self, inv_id: uuid.UUID, w: _VendorWork) -> None:
        analysed = w.extraction is not None
        findings = aggregate_claims(
            w.extraction.claims if w.extraction else [], w.sources,
            extraction_meta=w.extraction.meta if w.extraction else {}, analysed=analysed)
        warnings = list(w.extraction.warnings) if w.extraction else []
        snapshot_id, findings = self.repo.save_snapshot(
            inv_id, w.vendor.id, findings, extraction_meta=w.extraction.meta if w.extraction else {},
            warnings=warnings)
        counts: dict[str, int] = {}
        for f in findings.values():
            counts[f.status.value] = counts.get(f.status.value, 0) + 1
        unverified = sum(1 for f in findings.values() for e in f.evidence if e.verification.value != "verified")
        if unverified:
            metrics.inc("evidence_unverified_total", unverified)
        w.policy = VendorPolicy(vendor=w.vendor, findings=findings, sources=w.sources, warnings=warnings,
                                snapshot_id=snapshot_id, failed=w.error is not None,
                                error=(w.error or {}).get("message"))
        if w.error is None:
            self.repo.set_vendor_run(inv_id, w.vendor.id, VendorRunStatus.COMPLETED)
            self._event(inv_id, "validating",
                        f"Validated: {counts.get('found', 0)} verified, {counts.get('contradictory', 0)} conflicting, "
                        f"{counts.get('unverified', 0)} unverified, {counts.get('not_found', 0)} not stated",
                        vendor=w.vendor.name, counts=counts)

    # ------------------------------------------------------------------- run
    def run(self, investigation_id: uuid.UUID, *, worker_id: str = "local") -> None:
        with log_context(investigation_id=str(investigation_id), worker=worker_id):
            if not self.repo.claim_investigation(investigation_id, worker_id=worker_id,
                                                 lease_seconds=self.settings.job_lease_seconds):
                log_event(logger, logging.INFO, "investigation not claimable (owned elsewhere or finished)")
                return
            record = self.repo.get_investigation(investigation_id)
            assert record is not None
            started = time.perf_counter()
            try:
                self._run(record, worker_id)
            except Exception as exc:  # noqa: BLE001 - recorded as an explicit failure
                logger.exception("investigation crashed")
                err = _err(exc, "orchestration")
                try:
                    self.repo.set_status(investigation_id, InvestigationStatus.FAILED, error=err)
                    self._event(investigation_id, "failed", f"Investigation failed: {err['message']}", level="error")
                except ClauseLensError:
                    pass
                metrics.inc("investigations_total", outcome="failed")
                if isinstance(exc, ClauseLensError) and exc.transient and exc.provider == "database":
                    raise  # let the job system retry infrastructure failures
            finally:
                metrics.observe_duration("investigation", time.perf_counter() - started)

    def _run(self, record: InvestigationRecord, worker_id: str) -> None:
        inv_id = record.id
        self._event(inv_id, "running", f"Investigating {len(record.vendors)} vendors",
                    providers=self.providers(), demo=self.is_demo)
        work = [_VendorWork(vendor=vr.vendor) for vr in record.vendors]
        pool_size = min(self.settings.research_vendor_concurrency, len(work))

        with ThreadPoolExecutor(max_workers=pool_size, thread_name_prefix="research") as pool:
            list(pool.map(lambda w: self._research(inv_id, w, w.vendor.domain), work))

        ready = [w for w in work if w.error is None]
        if ready:
            self._phase(inv_id, InvestigationStatus.EXTRACTING, "Extracting policy terms with the language model",
                        worker_id)
            with ThreadPoolExecutor(max_workers=min(self.settings.llm_max_concurrency, len(ready)),
                                    thread_name_prefix="extract") as pool:
                list(pool.map(lambda w: self._extract(inv_id, w), ready))

        self._phase(inv_id, InvestigationStatus.VALIDATING, "Verifying quotes against retrieved pages", worker_id)
        for w in work:
            self._validate(inv_id, w)

        policies = [w.policy for w in work if w.policy is not None]
        failed = [w for w in work if w.error is not None]
        if len(failed) == len(work):
            err = {"message": "Every vendor investigation failed; no report was produced.",
                   "category": ErrorCategory.UNAVAILABLE.value, "provider": None, "stage": "comparison"}
            self.repo.set_status(inv_id, InvestigationStatus.FAILED, error=err)
            self._event(inv_id, "failed", err["message"] or "", level="error")
            metrics.inc("investigations_total", outcome="failed")
            return

        self._phase(inv_id, InvestigationStatus.COMPARING, "Comparing vendors with the deterministic engine",
                    worker_id)
        report = self.build_report(policies, record.priorities, investigation_id=inv_id, explain=True)
        saved = self.repo.save_report(report)
        self.repo.set_report(inv_id, saved.id)  # type: ignore[arg-type]
        final = InvestigationStatus.PARTIAL if failed else InvestigationStatus.COMPLETED
        error = ({"message": f"{len(failed)} of {len(work)} vendors could not be investigated",
                  "category": "partial", "provider": None, "stage": "research"} if failed else None)
        self.repo.set_status(inv_id, final, error=error)
        self._event(inv_id, final.value, "Report ready" + (" (some vendors failed)" if failed else ""),
                    report_id=str(saved.id))
        metrics.inc("investigations_total", outcome=final.value)

    def build_report(self, policies: list[VendorPolicy], priorities: list[Priority], *,
                     investigation_id: uuid.UUID | None, explain: bool) -> ComparisonReport:
        report = compare(policies, priorities or None, scoring_policy=self.settings.scoring_policy())
        report = report.model_copy(update={"investigation_id": investigation_id, "is_demo": self.is_demo})
        if explain and self.settings.llm_generate_explanation and any(not p.failed for p in policies):
            text, status = generate_explanation(self.llm, report)
            report = report.model_copy(update={"explanation": text, "explanation_status": status})
        return report


class InvestigationSubmitter:
    """Create + enqueue, kept separate from execution so the API never runs pipelines."""

    def __init__(self, repo: Repository, jobs: JobQueue, service: InvestigationService) -> None:
        self.repo = repo
        self.jobs = jobs
        self.service = service

    def submit(self, vendors: list[VendorInput], priorities: list[Priority],
               idempotency_key: str | None = None) -> InvestigationRecord:
        record, created = self.repo.create_investigation(
            vendors, priorities, providers=self.service.providers(), is_demo=self.service.is_demo,
            idempotency_key=idempotency_key)
        if created:
            self.repo.add_event(record.id, stage="queued", message="Investigation queued",
                                data={"queue": self.jobs.name, "durable": self.jobs.durable})
            try:
                self.jobs.submit_investigation(record.id)
            except ClauseLensError as exc:
                self.repo.set_status(record.id, InvestigationStatus.FAILED, error=_err(exc, "queue"))
                self.repo.add_event(record.id, stage="failed", level="error",
                                    message=f"Could not start investigation: {exc.message}")
                raise
        return self.repo.get_investigation(record.id) or record
