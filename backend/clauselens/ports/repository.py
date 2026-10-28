"""Persistence port. SQL/ORM details live only in the adapter."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, Field

from clauselens.domain.models import (
    ComparisonReport,
    Evidence,
    Finding,
    InvestigationEvent,
    InvestigationStatus,
    Priority,
    RetrievedSource,
    Vendor,
    VendorInput,
    VendorPolicy,
    VendorRunStatus,
)
from clauselens.domain.policy import PolicyField


class VendorRun(BaseModel):
    vendor: Vendor
    position: int
    status: VendorRunStatus
    error: dict[str, str | None] | None = None
    domain_source: str | None = None
    source_count: int = 0
    snapshot_id: UUID | None = None


class InvestigationRecord(BaseModel):
    id: UUID
    status: InvestigationStatus
    created_at: datetime
    updated_at: datetime
    vendors: list[VendorRun]
    priorities: list[Priority]
    error: dict[str, str | None] | None = None
    report_id: UUID | None = None
    is_demo: bool = False
    providers: dict[str, str] = Field(default_factory=dict)


class SourceView(BaseModel):
    id: UUID
    vendor_id: UUID
    source_key: str
    url: str
    final_url: str | None
    title: str | None
    retrieved_at: datetime
    provider: str
    content_length: int
    injection_suspected: bool


class EvidenceView(Evidence):
    vendor_id: UUID
    vendor_name: str
    source_title: str | None = None


class SnapshotSummary(BaseModel):
    id: UUID
    vendor_id: UUID
    investigation_id: UUID
    created_at: datetime
    findings: dict[PolicyField, Finding]
    warnings: list[str] = Field(default_factory=list)


@runtime_checkable
class Repository(Protocol):
    def ping(self) -> None: ...

    # investigations
    def create_investigation(
        self,
        vendors: list[VendorInput],
        priorities: list[Priority],
        *,
        providers: dict[str, str],
        is_demo: bool,
        idempotency_key: str | None = None,
    ) -> tuple[InvestigationRecord, bool]:
        """Return (record, created). An existing idempotency_key returns the earlier record with created=False."""
        ...

    def get_investigation(self, investigation_id: UUID) -> InvestigationRecord | None: ...

    def list_investigations(self, *, limit: int, offset: int) -> tuple[list[InvestigationRecord], int]: ...

    def claim_investigation(self, investigation_id: UUID, *, worker_id: str, lease_seconds: int) -> bool:
        """Atomically mark a queued (or stale-leased) investigation as owned by
        this worker. Returns False if another worker owns it or it is terminal."""
        ...

    def renew_lease(self, investigation_id: UUID, *, worker_id: str, lease_seconds: int) -> None: ...

    def set_status(
        self, investigation_id: UUID, status: InvestigationStatus, *, error: dict[str, str | None] | None = None
    ) -> None: ...

    def set_vendor_run(
        self,
        investigation_id: UUID,
        vendor_id: UUID,
        status: VendorRunStatus,
        *,
        error: dict[str, str | None] | None = None,
        domain: str | None = None,
        domain_source: str | None = None,
        source_count: int | None = None,
    ) -> None: ...

    def add_event(
        self,
        investigation_id: UUID,
        *,
        stage: str,
        message: str,
        level: str = "info",
        vendor_name: str | None = None,
        data: dict[str, object] | None = None,
    ) -> InvestigationEvent: ...

    def list_events(self, investigation_id: UUID, *, after_seq: int = 0, limit: int = 500) -> list[InvestigationEvent]: ...

    # sources, snapshots, evidence
    def save_sources(self, investigation_id: UUID, vendor_id: UUID, sources: list[RetrievedSource]) -> None: ...

    def list_sources(self, investigation_id: UUID) -> list[SourceView]: ...

    def save_snapshot(
        self,
        investigation_id: UUID,
        vendor_id: UUID,
        findings: dict[PolicyField, Finding],
        *,
        extraction_meta: dict[str, str],
        warnings: list[str],
    ) -> tuple[UUID, dict[PolicyField, Finding]]:
        """Persist a policy snapshot; return its id and findings with evidence ids assigned."""
        ...

    def load_policy(self, snapshot_id: UUID) -> VendorPolicy | None: ...

    def latest_snapshot_ids(self, vendor_ids: list[UUID]) -> dict[UUID, UUID]: ...

    def list_snapshots(self, vendor_id: UUID, *, limit: int, offset: int) -> tuple[list[SnapshotSummary], int]: ...

    def get_vendor(self, vendor_id: UUID) -> Vendor | None: ...

    # reports
    def save_report(self, report: ComparisonReport) -> ComparisonReport: ...

    def set_report(self, investigation_id: UUID, report_id: UUID) -> None: ...

    def get_report(self, report_id: UUID) -> ComparisonReport | None: ...

    def list_report_evidence(self, report_id: UUID) -> list[EvidenceView]: ...
