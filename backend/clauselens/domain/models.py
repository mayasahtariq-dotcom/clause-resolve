"""Application-level domain models shared by services, adapters and the API.

None of these types reference a provider SDK or ORM; adapters translate to and
from them at the boundary.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from clauselens.domain.policy import FieldStatus, PolicyField, PolicyValue


class InvestigationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"  # researching vendor websites
    EXTRACTING = "extracting"
    VALIDATING = "validating"
    COMPARING = "comparing"
    COMPLETED = "completed"
    PARTIAL = "partial"  # finished, but at least one vendor failed
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        return self in {InvestigationStatus.COMPLETED, InvestigationStatus.PARTIAL, InvestigationStatus.FAILED}


class VendorRunStatus(StrEnum):
    PENDING = "pending"
    RESEARCHING = "researching"
    EXTRACTING = "extracting"
    COMPLETED = "completed"
    FAILED = "failed"


class VerificationStatus(StrEnum):
    VERIFIED = "verified"  # quote found in the retrieved source text
    NOT_IN_SOURCE = "not_in_source"  # quote could not be located: treat as unverified
    SOURCE_MISSING = "source_missing"  # quote cites a source id we never retrieved


class VendorInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    domain: str | None = Field(default=None, max_length=253)


class Vendor(BaseModel):
    id: UUID
    name: str
    domain: str | None = None


class RetrievedSource(BaseModel):
    """A page retrieved by a research provider, normalised."""

    model_config = ConfigDict(frozen=True)

    source_key: str  # stable short id used in prompts and evidence, e.g. "S1"
    url: str
    final_url: str | None = None
    title: str | None = None
    content: str
    content_hash: str
    retrieved_at: datetime
    provider: str
    injection_suspected: bool = False


class Evidence(BaseModel):
    id: UUID | None = None
    field: PolicyField
    source_key: str
    source_url: str | None
    quote: str
    retrieved_at: datetime | None
    verification: VerificationStatus
    match_method: str | None = None
    extraction: dict[str, str] = Field(default_factory=dict)  # provider/model/prompt version


class Claim(BaseModel):
    """One statement extracted by the LLM, before aggregation."""

    field: PolicyField
    source_key: str
    quote: str
    value: PolicyValue
    ambiguous: bool = False
    summary: str | None = None


class Finding(BaseModel):
    """The aggregated, validated state of one field for one vendor."""

    field: PolicyField
    status: FieldStatus
    value: PolicyValue | None = None
    summary: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    conflicting_values: list[PolicyValue] = Field(default_factory=list)
    note: str | None = None


class VendorPolicy(BaseModel):
    vendor: Vendor
    findings: dict[PolicyField, Finding]
    sources: list[RetrievedSource] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    snapshot_id: UUID | None = None
    failed: bool = False
    error: str | None = None


class Criterion(StrEnum):
    LONGEST_REFUND_WINDOW = "longest_refund_window"
    LOWEST_CANCELLATION_FEE = "lowest_cancellation_fee"
    EASIEST_CANCELLATION = "easiest_cancellation"
    LONGEST_TRIAL = "longest_trial"
    NO_AUTO_TRIAL_CONVERSION = "no_auto_trial_conversion"
    NO_AUTO_RENEWAL = "no_auto_renewal"
    LOWEST_RESTOCKING_FEE = "lowest_restocking_fee"
    MERCHANT_PAYS_RETURN_SHIPPING = "merchant_pays_return_shipping"
    FEWEST_EXCLUSIONS = "fewest_exclusions"


class Priority(BaseModel):
    criterion: Criterion
    weight: float = Field(default=1.0, gt=0, le=10)


class ComparisonCell(BaseModel):
    vendor_id: UUID
    field: PolicyField
    status: FieldStatus
    display: str
    normalized: dict[str, str | float | bool | list[str] | None] = Field(default_factory=dict)
    evidence_ids: list[UUID] = Field(default_factory=list)
    is_best: bool = False


class CriterionScore(BaseModel):
    criterion: Criterion
    weight: float
    scores: dict[str, float | None]  # vendor_id -> 0..1, None when the value is unknown
    explanation: str


class Recommendation(BaseModel):
    vendor_id: UUID | None  # None when evidence is insufficient to recommend
    headline: str
    rationale: list[str]
    confidence: str  # "high" | "medium" | "low" | "insufficient"
    coverage: dict[str, float]  # vendor_id -> share of priority weight backed by verified data
    totals: dict[str, float]


class ComparisonReport(BaseModel):
    id: UUID | None = None
    investigation_id: UUID | None = None
    created_at: datetime | None = None
    vendors: list[Vendor]
    priorities: list[Priority]
    cells: list[ComparisonCell]
    criteria: list[CriterionScore]
    recommendation: Recommendation
    contradictions: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    explanation: str | None = None
    explanation_status: str = "not_requested"  # generated | rejected | failed | not_requested
    scoring_policy: dict[str, float] = Field(default_factory=dict)
    snapshot_ids: list[UUID] = Field(default_factory=list)  # policy snapshots this report compared
    is_demo: bool = False
    disclaimer: str = (
        "ClauseLens summarises publicly available policy text. It is not legal advice; "
        "always confirm terms on the vendor's site before purchasing."
    )


class InvestigationEvent(BaseModel):
    seq: int
    created_at: datetime
    stage: str
    level: str = "info"  # info | warning | error
    message: str
    vendor_name: str | None = None
    data: dict[str, object] = Field(default_factory=dict)
