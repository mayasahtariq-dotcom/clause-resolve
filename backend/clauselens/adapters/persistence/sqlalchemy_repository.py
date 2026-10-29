"""SQLAlchemy implementation of the Repository port (PostgreSQL in production).

Translates between ORM rows and domain models; nothing outside this package
sees a row object or a Session.
"""

from __future__ import annotations

import re
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import create_engine, func, or_, select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from clauselens.adapters.persistence.models import (
    ComparisonItemRow,
    ComparisonReportRow,
    EvidenceRow,
    InvestigationEventRow,
    InvestigationRow,
    InvestigationVendorRow,
    PolicyClauseRow,
    PolicySnapshotRow,
    RetrievedSourceRow,
    VendorRow,
)
from clauselens.config import Settings
from clauselens.domain.errors import ClauseLensError, ErrorCategory
from clauselens.domain.models import (
    ComparisonCell,
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
    VerificationStatus,
)
from clauselens.domain.policy import FieldStatus, PolicyField, PolicyValue
from clauselens.domain.risk import VendorRiskAnalysis
from clauselens.ports.repository import (
    EvidenceView,
    InvestigationRecord,
    SnapshotSummary,
    SourceView,
    VendorRun,
)

_TERMINAL = [s.value for s in InvestigationStatus if s.is_terminal]
_KEY_RE = re.compile(r"[^a-z0-9]+")


def vendor_name_key(name: str) -> str:
    return _KEY_RE.sub("", name.lower())[:120] or "vendor"


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def create_db_engine(settings: Settings) -> Engine:
    url = settings.database_url
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})
    return create_engine(url, pool_pre_ping=True, pool_size=settings.db_pool_size, max_overflow=5)


class SqlAlchemyRepository:
    name = "sqlalchemy"

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._sessions = sessionmaker(engine, expire_on_commit=False)
        self._event_lock = threading.Lock()

    @contextmanager
    def _session(self) -> Iterator[Session]:
        session = self._sessions()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as exc:
            session.rollback()
            raise ClauseLensError(f"Database error: {type(exc).__name__}", category=ErrorCategory.UNAVAILABLE,
                                  provider="database") from exc
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def ping(self) -> None:
        with self._session() as s:
            s.execute(text("SELECT 1"))

    # ------------------------------------------------------------------ mapping
    @staticmethod
    def _vendor(row: VendorRow) -> Vendor:
        return Vendor(id=row.id, name=row.name, domain=row.domain)

    def _record(self, row: InvestigationRow) -> InvestigationRecord:
        return InvestigationRecord(
            id=row.id,
            status=InvestigationStatus(row.status),
            created_at=_aware(row.created_at),  # type: ignore[arg-type]
            updated_at=_aware(row.updated_at),  # type: ignore[arg-type]
            vendors=[
                VendorRun(vendor=self._vendor(vr.vendor), position=vr.position, status=VendorRunStatus(vr.status),
                          error=vr.error, domain_source=vr.domain_source, source_count=vr.source_count,
                          snapshot_id=vr.snapshot_id)
                for vr in row.vendor_runs
            ],
            priorities=[Priority.model_validate(p) for p in row.priorities or []],
            error=row.error,
            report_id=row.report_id,
            is_demo=row.is_demo,
            providers=row.providers or {},
        )

    # ------------------------------------------------------------ investigations
    def _get_or_create_vendor(self, s: Session, v: VendorInput) -> VendorRow:
        key = vendor_name_key(v.name)
        row = s.scalar(select(VendorRow).where(VendorRow.name_key == key))
        if row is None:
            row = VendorRow(id=uuid.uuid4(), name=v.name.strip(), name_key=key, domain=v.domain)
            s.add(row)
            try:
                s.flush()
            except IntegrityError:  # created concurrently
                s.rollback()
                row = s.scalar(select(VendorRow).where(VendorRow.name_key == key))
                assert row is not None
        elif v.domain and not row.domain:
            row.domain = v.domain
        return row

    def create_investigation(self, vendors: list[VendorInput], priorities: list[Priority], *,
                             providers: dict[str, str], is_demo: bool,
                             idempotency_key: str | None = None) -> tuple[InvestigationRecord, bool]:
        with self._session() as s:
            if idempotency_key:
                existing = s.scalar(select(InvestigationRow).where(InvestigationRow.idempotency_key == idempotency_key))
                if existing is not None:
                    return self._record(existing), False
            row = InvestigationRow(
                id=uuid.uuid4(), status=InvestigationStatus.QUEUED.value,
                priorities=[p.model_dump(mode="json") for p in priorities],
                providers=providers, is_demo=is_demo, idempotency_key=idempotency_key,
            )
            s.add(row)
            for pos, v in enumerate(vendors):
                vrow = self._get_or_create_vendor(s, v)
                row.vendor_runs.append(InvestigationVendorRow(vendor_id=vrow.id, vendor=vrow, position=pos,
                                                              status=VendorRunStatus.PENDING.value))
            s.flush()
            return self._record(row), True

    def get_investigation(self, investigation_id: uuid.UUID) -> InvestigationRecord | None:
        with self._session() as s:
            row = s.get(InvestigationRow, investigation_id)
            return self._record(row) if row else None

    def list_investigations(self, *, limit: int, offset: int) -> tuple[list[InvestigationRecord], int]:
        with self._session() as s:
            total = s.scalar(select(func.count()).select_from(InvestigationRow)) or 0
            rows = s.scalars(select(InvestigationRow).order_by(InvestigationRow.created_at.desc())
                             .limit(limit).offset(offset)).all()
            return [self._record(r) for r in rows], int(total)

    def claim_investigation(self, investigation_id: uuid.UUID, *, worker_id: str, lease_seconds: int) -> bool:
        now = datetime.now(UTC)
        with self._session() as s:
            result = s.execute(
                update(InvestigationRow)
                .where(InvestigationRow.id == investigation_id)
                .where(or_(
                    InvestigationRow.status == InvestigationStatus.QUEUED.value,
                    (InvestigationRow.status.not_in(_TERMINAL)) & (InvestigationRow.lease_expires_at < now),
                    (InvestigationRow.status.not_in(_TERMINAL)) & (InvestigationRow.lease_owner == worker_id),
                ))
                .values(status=InvestigationStatus.RUNNING.value, lease_owner=worker_id,
                        lease_expires_at=now + timedelta(seconds=lease_seconds),
                        attempts=InvestigationRow.attempts + 1, updated_at=now)
                .execution_options(synchronize_session=False)
            )
            return getattr(result, "rowcount", 0) == 1

    def renew_lease(self, investigation_id: uuid.UUID, *, worker_id: str, lease_seconds: int) -> None:
        with self._session() as s:
            s.execute(update(InvestigationRow)
                      .where(InvestigationRow.id == investigation_id, InvestigationRow.lease_owner == worker_id)
                      .values(lease_expires_at=datetime.now(UTC) + timedelta(seconds=lease_seconds))
                      .execution_options(synchronize_session=False))

    def set_status(self, investigation_id: uuid.UUID, status: InvestigationStatus, *,
                   error: dict[str, str | None] | None = None) -> None:
        values: dict[str, Any] = {"status": status.value, "updated_at": datetime.now(UTC)}
        if error is not None:
            values["error"] = error
        if status.is_terminal:
            values["lease_owner"] = None
            values["lease_expires_at"] = None
        with self._session() as s:
            s.execute(update(InvestigationRow).where(InvestigationRow.id == investigation_id).values(**values)
                      .execution_options(synchronize_session=False))

    def set_vendor_run(self, investigation_id: uuid.UUID, vendor_id: uuid.UUID, status: VendorRunStatus, *,
                       error: dict[str, str | None] | None = None, domain: str | None = None,
                       domain_source: str | None = None, source_count: int | None = None) -> None:
        with self._session() as s:
            run = s.get(InvestigationVendorRow, (investigation_id, vendor_id))
            if run is None:
                raise ClauseLensError("Vendor is not part of this investigation", category=ErrorCategory.NOT_FOUND)
            run.status = status.value
            if error is not None:
                run.error = error
            if domain_source is not None:
                run.domain_source = domain_source
            if source_count is not None:
                run.source_count = source_count
            if domain:
                vendor = s.get(VendorRow, vendor_id)
                if vendor is not None:
                    vendor.domain = domain

    def add_event(self, investigation_id: uuid.UUID, *, stage: str, message: str, level: str = "info",
                  vendor_name: str | None = None, data: dict[str, object] | None = None) -> InvestigationEvent:
        with self._event_lock, self._session() as s:
            s.execute(select(InvestigationRow.id).where(InvestigationRow.id == investigation_id).with_for_update())
            seq = (s.scalar(select(func.max(InvestigationEventRow.seq))
                            .where(InvestigationEventRow.investigation_id == investigation_id)) or 0) + 1
            row = InvestigationEventRow(investigation_id=investigation_id, seq=seq, stage=stage, level=level,
                                        vendor_name=vendor_name, message=message[:2000], data=dict(data or {}),
                                        created_at=datetime.now(UTC))
            s.add(row)
            s.flush()
            return InvestigationEvent(seq=seq, created_at=row.created_at, stage=stage, level=level,
                                      message=row.message, vendor_name=vendor_name, data=row.data)

    def list_events(self, investigation_id: uuid.UUID, *, after_seq: int = 0,
                    limit: int = 500) -> list[InvestigationEvent]:
        with self._session() as s:
            rows = s.scalars(select(InvestigationEventRow)
                             .where(InvestigationEventRow.investigation_id == investigation_id,
                                    InvestigationEventRow.seq > after_seq)
                             .order_by(InvestigationEventRow.seq).limit(limit)).all()
            return [InvestigationEvent(seq=r.seq, created_at=_aware(r.created_at), stage=r.stage,  # type: ignore[arg-type]
                                       level=r.level, message=r.message, vendor_name=r.vendor_name,
                                       data=r.data or {}) for r in rows]

    # ---------------------------------------------------------------- sources
    def save_sources(self, investigation_id: uuid.UUID, vendor_id: uuid.UUID,
                     sources: list[RetrievedSource]) -> None:
        with self._session() as s:
            existing = set(s.scalars(select(RetrievedSourceRow.content_hash).where(
                RetrievedSourceRow.investigation_id == investigation_id,
                RetrievedSourceRow.vendor_id == vendor_id)).all())
            for src in sources:
                if src.content_hash in existing:
                    continue
                existing.add(src.content_hash)
                s.add(RetrievedSourceRow(
                    investigation_id=investigation_id, vendor_id=vendor_id, source_key=src.source_key,
                    url=src.url, final_url=src.final_url, title=src.title, content=src.content,
                    content_hash=src.content_hash, content_length=len(src.content),
                    retrieved_at=src.retrieved_at, provider=src.provider,
                    injection_suspected=src.injection_suspected,
                ))

    def list_sources(self, investigation_id: uuid.UUID) -> list[SourceView]:
        with self._session() as s:
            rows = s.scalars(select(RetrievedSourceRow).where(RetrievedSourceRow.investigation_id == investigation_id)
                             .order_by(RetrievedSourceRow.vendor_id, RetrievedSourceRow.source_key)).all()
            return [SourceView(id=r.id, vendor_id=r.vendor_id, source_key=r.source_key, url=r.url,
                               final_url=r.final_url, title=r.title, retrieved_at=_aware(r.retrieved_at),  # type: ignore[arg-type]
                               provider=r.provider, content_length=r.content_length,
                               injection_suspected=r.injection_suspected) for r in rows]

    # --------------------------------------------------------------- snapshots
    def save_snapshot(self, investigation_id: uuid.UUID, vendor_id: uuid.UUID,
                      findings: dict[PolicyField, Finding], *, extraction_meta: dict[str, str],
                      warnings: list[str],
                      risk: VendorRiskAnalysis | None = None) -> tuple[uuid.UUID, dict[PolicyField, Finding]]:
        with self._session() as s:
            prior = s.scalar(select(PolicySnapshotRow).where(PolicySnapshotRow.investigation_id == investigation_id,
                                                             PolicySnapshotRow.vendor_id == vendor_id))
            if prior is not None:  # a retried job replaces its own earlier snapshot
                s.delete(prior)
                s.flush()
            source_ids = {r.source_key: r.id for r in s.scalars(select(RetrievedSourceRow).where(
                RetrievedSourceRow.investigation_id == investigation_id,
                RetrievedSourceRow.vendor_id == vendor_id)).all()}
            snap = PolicySnapshotRow(id=uuid.uuid4(), investigation_id=investigation_id, vendor_id=vendor_id,
                                     extraction_meta=extraction_meta, warnings=warnings,
                                     risk_analysis=risk.model_dump(mode="json") if risk else None)
            s.add(snap)
            out: dict[PolicyField, Finding] = {}
            for field, finding in findings.items():
                clause = PolicyClauseRow(
                    id=uuid.uuid4(), field=field.value, status=finding.status.value,
                    value=finding.value.model_dump(mode="json", exclude_none=True) if finding.value else None,
                    conflicting_values=[v.model_dump(mode="json", exclude_none=True)
                                        for v in finding.conflicting_values],
                    summary=finding.summary, note=finding.note,
                )
                snap.clauses.append(clause)
                with_ids = []
                for ev in finding.evidence:
                    ev_id = uuid.uuid4()
                    clause.evidence.append(EvidenceRow(
                        id=ev_id, snapshot_id=snap.id, source_id=source_ids.get(ev.source_key),
                        field=ev.field.value, source_key=ev.source_key, source_url=ev.source_url, quote=ev.quote,
                        retrieved_at=ev.retrieved_at, verification=ev.verification.value,
                        match_method=ev.match_method, extraction=ev.extraction,
                    ))
                    with_ids.append(ev.model_copy(update={"id": ev_id}))
                out[field] = finding.model_copy(update={"evidence": with_ids})
            run = s.get(InvestigationVendorRow, (investigation_id, vendor_id))
            if run is not None:
                run.snapshot_id = snap.id
            return snap.id, out

    @staticmethod
    def _findings(snap: PolicySnapshotRow) -> dict[PolicyField, Finding]:
        out: dict[PolicyField, Finding] = {}
        for c in snap.clauses:
            field = PolicyField(c.field)
            out[field] = Finding(
                field=field, status=FieldStatus(c.status),
                value=PolicyValue.model_validate(c.value) if c.value is not None else None,
                summary=c.summary, note=c.note,
                conflicting_values=[PolicyValue.model_validate(v) for v in c.conflicting_values or []],
                evidence=[Evidence(id=e.id, field=PolicyField(e.field), source_key=e.source_key,
                                   source_url=e.source_url, quote=e.quote, retrieved_at=_aware(e.retrieved_at),
                                   verification=VerificationStatus(e.verification), match_method=e.match_method,
                                   extraction=e.extraction or {}) for e in c.evidence],
            )
        return out

    @staticmethod
    def _risk(snap: PolicySnapshotRow) -> VendorRiskAnalysis | None:
        return VendorRiskAnalysis.model_validate(snap.risk_analysis) if snap.risk_analysis else None

    def load_policy(self, snapshot_id: uuid.UUID) -> VendorPolicy | None:
        with self._session() as s:
            snap = s.get(PolicySnapshotRow, snapshot_id)
            if snap is None:
                return None
            vendor = s.get(VendorRow, snap.vendor_id)
            assert vendor is not None
            return VendorPolicy(vendor=self._vendor(vendor), findings=self._findings(snap),
                                warnings=list(snap.warnings or []), snapshot_id=snap.id,
                                risk=self._risk(snap))

    def latest_snapshot_ids(self, vendor_ids: list[uuid.UUID]) -> dict[uuid.UUID, uuid.UUID]:
        out: dict[uuid.UUID, uuid.UUID] = {}
        with self._session() as s:
            for vid in vendor_ids:
                sid = s.scalar(select(PolicySnapshotRow.id).where(PolicySnapshotRow.vendor_id == vid)
                               .order_by(PolicySnapshotRow.created_at.desc()).limit(1))
                if sid is not None:
                    out[vid] = sid
        return out

    def list_snapshots(self, vendor_id: uuid.UUID, *, limit: int,
                       offset: int) -> tuple[list[SnapshotSummary], int]:
        with self._session() as s:
            total = s.scalar(select(func.count()).select_from(PolicySnapshotRow)
                             .where(PolicySnapshotRow.vendor_id == vendor_id)) or 0
            rows = s.scalars(select(PolicySnapshotRow).where(PolicySnapshotRow.vendor_id == vendor_id)
                             .order_by(PolicySnapshotRow.created_at.desc()).limit(limit).offset(offset)).all()
            return [SnapshotSummary(id=r.id, vendor_id=r.vendor_id, investigation_id=r.investigation_id,
                                    created_at=_aware(r.created_at), findings=self._findings(r),  # type: ignore[arg-type]
                                    warnings=list(r.warnings or []), risk=self._risk(r)) for r in rows], int(total)

    def get_vendor(self, vendor_id: uuid.UUID) -> Vendor | None:
        with self._session() as s:
            row = s.get(VendorRow, vendor_id)
            return self._vendor(row) if row else None

    # ----------------------------------------------------------------- reports
    def save_report(self, report: ComparisonReport) -> ComparisonReport:
        report_id = uuid.uuid4()
        created = datetime.now(UTC)
        saved = report.model_copy(update={"id": report_id, "created_at": created})
        payload = saved.model_dump(mode="json", exclude={"cells"})
        with self._session() as s:
            row = ComparisonReportRow(id=report_id, investigation_id=report.investigation_id, created_at=created,
                                      payload=payload, is_demo=report.is_demo,
                                      snapshot_ids=[str(i) for i in report.snapshot_ids])
            for c in report.cells:
                row.items.append(ComparisonItemRow(
                    vendor_id=c.vendor_id, field=c.field.value, status=c.status.value, display=c.display,
                    normalized=c.normalized, evidence_ids=[str(e) for e in c.evidence_ids], is_best=c.is_best))
            s.add(row)
        return saved

    def set_report(self, investigation_id: uuid.UUID, report_id: uuid.UUID) -> None:
        with self._session() as s:
            s.execute(update(InvestigationRow).where(InvestigationRow.id == investigation_id)
                      .values(report_id=report_id, updated_at=datetime.now(UTC))
                      .execution_options(synchronize_session=False))

    def get_report(self, report_id: uuid.UUID) -> ComparisonReport | None:
        with self._session() as s:
            row = s.get(ComparisonReportRow, report_id)
            if row is None:
                return None
            data = dict(row.payload)
            vendor_order = {v["id"]: i for i, v in enumerate(data.get("vendors", []))}
            field_order = {f.value: i for i, f in enumerate(PolicyField)}
            items = sorted(row.items, key=lambda it: (vendor_order.get(str(it.vendor_id), 99),
                                                      field_order.get(it.field, 99)))
            data["cells"] = [ComparisonCell(vendor_id=it.vendor_id, field=PolicyField(it.field),
                                            status=FieldStatus(it.status), display=it.display,
                                            normalized=it.normalized or {},
                                            evidence_ids=[uuid.UUID(e) for e in it.evidence_ids or []],
                                            is_best=it.is_best).model_dump(mode="json") for it in items]
            return ComparisonReport.model_validate(data)

    def list_report_evidence(self, report_id: uuid.UUID) -> list[EvidenceView]:
        with self._session() as s:
            row = s.get(ComparisonReportRow, report_id)
            if row is None:
                return []
            ev_ids = {uuid.UUID(e) for it in row.items for e in (it.evidence_ids or [])}
            snap_ids = [uuid.UUID(x) for x in row.snapshot_ids or []]
            if not snap_ids and not ev_ids:
                return []
            stmt = (select(EvidenceRow, PolicySnapshotRow.vendor_id, VendorRow.name, RetrievedSourceRow.title)
                    .join(PolicySnapshotRow, EvidenceRow.snapshot_id == PolicySnapshotRow.id)
                    .join(VendorRow, VendorRow.id == PolicySnapshotRow.vendor_id)
                    .outerjoin(RetrievedSourceRow, RetrievedSourceRow.id == EvidenceRow.source_id))
            stmt = stmt.where(EvidenceRow.snapshot_id.in_(snap_ids)) if snap_ids else stmt.where(EvidenceRow.id.in_(ev_ids))
            out = []
            for ev, vendor_id, vendor_name, title in s.execute(stmt.order_by(VendorRow.name, EvidenceRow.field)).all():
                out.append(EvidenceView(
                    id=ev.id, field=PolicyField(ev.field), source_key=ev.source_key, source_url=ev.source_url,
                    quote=ev.quote, retrieved_at=_aware(ev.retrieved_at),
                    verification=VerificationStatus(ev.verification), match_method=ev.match_method,
                    extraction=ev.extraction or {}, vendor_id=vendor_id, vendor_name=vendor_name, source_title=title,
                ))
            return out


def create(settings: Settings) -> SqlAlchemyRepository:
    return SqlAlchemyRepository(create_db_engine(settings))
