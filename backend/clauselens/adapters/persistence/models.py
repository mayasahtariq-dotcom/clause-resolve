"""SQLAlchemy ORM schema. Never imported outside the persistence adapter and Alembic."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JSONType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSONType, list[Any]: JSONType}


class VendorRow(Base):
    __tablename__ = "vendors"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    name_key: Mapped[str] = mapped_column(String(120), unique=True)
    domain: Mapped[str | None] = mapped_column(String(253))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class InvestigationRow(Base):
    __tablename__ = "investigations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(20), index=True)
    priorities: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    providers: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("comparison_reports.id", use_alter=True, name="fk_investigations_report_id",
                         ondelete="SET NULL"))
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True)
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    vendor_runs: Mapped[list[InvestigationVendorRow]] = relationship(
        order_by="InvestigationVendorRow.position", cascade="all, delete-orphan", lazy="selectin")


class InvestigationVendorRow(Base):
    __tablename__ = "investigation_vendors"

    investigation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("investigations.id", ondelete="CASCADE"), primary_key=True)
    vendor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("vendors.id"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    domain_source: Mapped[str | None] = mapped_column(String(20))
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)

    vendor: Mapped[VendorRow] = relationship(lazy="joined")


class RetrievedSourceRow(Base):
    __tablename__ = "retrieved_sources"
    __table_args__ = (UniqueConstraint("investigation_id", "vendor_id", "content_hash", name="uq_source_content"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("investigations.id", ondelete="CASCADE"), index=True)
    vendor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("vendors.id"), index=True)
    source_key: Mapped[str] = mapped_column(String(10))
    url: Mapped[str] = mapped_column(Text)
    final_url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    content_length: Mapped[int] = mapped_column(Integer)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    provider: Mapped[str] = mapped_column(String(40))
    injection_suspected: Mapped[bool] = mapped_column(Boolean, default=False)


class PolicySnapshotRow(Base):
    __tablename__ = "policy_snapshots"
    __table_args__ = (
        UniqueConstraint("investigation_id", "vendor_id", name="uq_snapshot_investigation_vendor"),
        Index("ix_snapshots_vendor_created", "vendor_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("investigations.id", ondelete="CASCADE"))
    vendor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("vendors.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    extraction_meta: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    warnings: Mapped[list[Any]] = mapped_column(JSONType, default=list)

    clauses: Mapped[list[PolicyClauseRow]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class PolicyClauseRow(Base):
    __tablename__ = "policy_clauses"
    __table_args__ = (UniqueConstraint("snapshot_id", "field", name="uq_clause_snapshot_field"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("policy_snapshots.id", ondelete="CASCADE"))
    field: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20))
    value: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    conflicting_values: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    summary: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)

    evidence: Mapped[list[EvidenceRow]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class EvidenceRow(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    clause_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("policy_clauses.id", ondelete="CASCADE"), index=True)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("policy_snapshots.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("retrieved_sources.id", ondelete="SET NULL"))
    field: Mapped[str] = mapped_column(String(40))
    source_key: Mapped[str] = mapped_column(String(10))
    source_url: Mapped[str | None] = mapped_column(Text)
    quote: Mapped[str] = mapped_column(Text)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification: Mapped[str] = mapped_column(String(20))
    match_method: Mapped[str | None] = mapped_column(String(20))
    extraction: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)


class ComparisonReportRow(Base):
    __tablename__ = "comparison_reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("investigations.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType)
    snapshot_ids: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    items: Mapped[list[ComparisonItemRow]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class ComparisonItemRow(Base):
    __tablename__ = "comparison_items"
    __table_args__ = (UniqueConstraint("report_id", "vendor_id", "field", name="uq_item_report_vendor_field"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("comparison_reports.id", ondelete="CASCADE"))
    vendor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("vendors.id"))
    field: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20))
    display: Mapped[str] = mapped_column(Text)
    normalized: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    evidence_ids: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    is_best: Mapped[bool] = mapped_column(Boolean, default=False)


class InvestigationEventRow(Base):
    __tablename__ = "investigation_events"
    __table_args__ = (UniqueConstraint("investigation_id", "seq", name="uq_event_seq"),)

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True,
                                    autoincrement=True)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("investigations.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    stage: Mapped[str] = mapped_column(String(40))
    level: Mapped[str] = mapped_column(String(10))
    vendor_name: Mapped[str | None] = mapped_column(String(120))
    message: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
