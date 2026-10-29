"""Risky-clause analysis results (provider-independent)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from clauselens.domain.models import VerificationStatus


class RiskLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


RISK_ORDER = {RiskLevel.HIGH: 0, RiskLevel.MEDIUM: 1, RiskLevel.LOW: 2}


class RiskEvidence(BaseModel):
    quote: str
    source_key: str
    source_url: str | None = None
    source_title: str | None = None
    retrieved_at: datetime | None = None
    verification: VerificationStatus
    match_method: str | None = None


class RiskClause(BaseModel):
    clause: str = Field(max_length=200)  # short name, e.g. "Automatic renewal"
    risk_level: RiskLevel
    explanation: str = Field(max_length=600)  # plain-English meaning
    reason: str = Field(max_length=600)  # why it is risky for the consumer
    category: str | None = Field(default=None, max_length=60)
    evidence: RiskEvidence


class RiskAnalysisStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"  # some chunks failed or the document was truncated
    FAILED = "failed"
    SKIPPED = "skipped"  # no retrieved text, or analysis disabled


class VendorRiskAnalysis(BaseModel):
    vendor_id: UUID
    vendor_name: str
    status: RiskAnalysisStatus
    clauses: list[RiskClause] = Field(default_factory=list)
    chunks_analyzed: int = 0
    chunks_total: int = 0
    warnings: list[str] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None
    error: str | None = None

    def counts(self) -> dict[str, int]:
        out = {lvl.value: 0 for lvl in RiskLevel}
        for c in self.clauses:
            out[c.risk_level.value] += 1
        return out
