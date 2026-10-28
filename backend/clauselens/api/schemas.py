"""HTTP request/response contracts. Kept separate from domain models so the API
can evolve (and alternative frontends can rely on it) without leaking internals."""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from clauselens.domain.models import Priority, VendorInput
from clauselens.ports.repository import EvidenceView, InvestigationRecord, SnapshotSummary, SourceView
from clauselens.security import normalize_domain

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class VendorIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    domain: str | None = Field(default=None, max_length=253)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = _CONTROL.sub("", v).strip()
        if not v:
            raise ValueError("vendor name is empty")
        return v

    @field_validator("domain")
    @classmethod
    def _domain(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        try:
            return normalize_domain(v)
        except Exception as exc:  # UnsafeURLError -> 422 with the reason
            raise ValueError(getattr(exc, "message", str(exc))) from exc


class InvestigationCreate(BaseModel):
    vendors: list[VendorIn] = Field(min_length=2, max_length=10)
    priorities: list[Priority] = Field(default_factory=list, max_length=9)

    @model_validator(mode="after")
    def _unique(self) -> InvestigationCreate:
        keys = [re.sub(r"[^a-z0-9]", "", v.name.lower()) for v in self.vendors]
        if len(set(keys)) != len(keys):
            raise ValueError("vendor names must be unique")
        crits = [p.criterion for p in self.priorities]
        if len(set(crits)) != len(crits):
            raise ValueError("each priority criterion may appear once")
        return self

    def vendor_inputs(self) -> list[VendorInput]:
        return [VendorInput(name=v.name, domain=v.domain) for v in self.vendors]


class VendorStatusOut(BaseModel):
    id: UUID
    name: str
    domain: str | None
    status: str
    error: dict[str, str | None] | None
    domain_source: str | None
    source_count: int


class InvestigationOut(BaseModel):
    id: UUID
    status: str
    is_terminal: bool
    created_at: datetime
    updated_at: datetime
    is_demo: bool
    providers: dict[str, str]
    priorities: list[Priority]
    error: dict[str, str | None] | None
    report_id: UUID | None
    vendors: list[VendorStatusOut]
    sources: list[SourceView] = Field(default_factory=list)

    @classmethod
    def from_record(cls, r: InvestigationRecord, sources: list[SourceView] | None = None) -> InvestigationOut:
        return cls(
            id=r.id, status=r.status.value, is_terminal=r.status.is_terminal, created_at=r.created_at,
            updated_at=r.updated_at, is_demo=r.is_demo, providers=r.providers, priorities=r.priorities,
            error=r.error, report_id=r.report_id, sources=sources or [],
            vendors=[VendorStatusOut(id=v.vendor.id, name=v.vendor.name, domain=v.vendor.domain,
                                     status=v.status.value, error=v.error, domain_source=v.domain_source,
                                     source_count=v.source_count) for v in r.vendors],
        )


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


class InvestigationSummary(BaseModel):
    id: UUID
    status: str
    created_at: datetime
    vendor_names: list[str]
    report_id: UUID | None
    is_demo: bool


class ComparisonCreate(BaseModel):
    vendor_ids: list[UUID] = Field(default_factory=list, max_length=10)
    snapshot_ids: list[UUID] = Field(default_factory=list, max_length=10)
    priorities: list[Priority] = Field(default_factory=list, max_length=9)
    explain: bool = False

    @model_validator(mode="after")
    def _one(self) -> ComparisonCreate:
        if bool(self.vendor_ids) == bool(self.snapshot_ids):
            raise ValueError("provide exactly one of vendor_ids or snapshot_ids")
        if len(self.vendor_ids or self.snapshot_ids) < 2:
            raise ValueError("at least two vendors are required")
        return self


class VendorPoliciesOut(BaseModel):
    vendor_id: UUID
    vendor_name: str
    domain: str | None
    items: list[SnapshotSummary]
    total: int
    limit: int
    offset: int


class EvidenceOut(BaseModel):
    report_id: UUID
    items: list[EvidenceView]


class ErrorBody(BaseModel):
    code: str
    message: str
    provider: str | None = None
    details: list[dict] | None = None


class ErrorOut(BaseModel):
    error: ErrorBody
