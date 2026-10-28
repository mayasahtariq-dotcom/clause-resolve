"""Web research port: discover and retrieve a vendor's policy pages."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from clauselens.domain.models import RetrievedSource


class ResearchRequest(BaseModel):
    vendor_name: str
    domain: str | None = None  # official domain if the user supplied it
    max_pages: int = Field(default=6, ge=1, le=10)
    topics: list[str] = Field(
        default_factory=lambda: [
            "refund policy",
            "cancellation policy subscription",
            "terms of service subscription renewal",
            "free trial terms",
            "returns restocking fee shipping",
        ]
    )


class SourceFailure(BaseModel):
    url: str
    reason: str  # provider-neutral code, e.g. page_not_found, bot_blocked
    message: str | None = None


class ResearchResult(BaseModel):
    vendor_name: str
    resolved_domain: str | None
    domain_source: str  # "user" | "search" | "unresolved"
    sources: list[RetrievedSource]
    failures: list[SourceFailure] = Field(default_factory=list)
    discovered_urls: list[str] = Field(default_factory=list)
    provider: str
    is_demo: bool = False


class ResearchCapabilities(BaseModel):
    asynchronous_jobs: bool = False
    cancellation: bool = False


@runtime_checkable
class ResearchProvider(Protocol):
    """Implementations must raise clauselens.domain.errors.ResearchError (never
    provider-specific exceptions) and must never fabricate sources."""

    name: str
    is_demo: bool
    capabilities: ResearchCapabilities

    def investigate_vendor(self, request: ResearchRequest) -> ResearchResult: ...

    def health_check(self) -> None:
        """Raise ConfigurationError/ResearchError if the provider cannot be used."""
        ...
