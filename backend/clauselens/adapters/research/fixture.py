"""Demo research provider backed by clearly labelled fixtures (no network)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from clauselens.adapters.fixture_data import FIXTURES, fixture_key
from clauselens.config import Settings
from clauselens.domain.errors import ErrorCategory, ResearchError
from clauselens.domain.models import RetrievedSource
from clauselens.ports.research import (
    ResearchCapabilities,
    ResearchRequest,
    ResearchResult,
    SourceFailure,
)
from clauselens.security import detect_prompt_injection

PROVIDER = "fixture"


class FixtureResearchProvider:
    name = PROVIDER
    is_demo = True
    capabilities = ResearchCapabilities()

    def health_check(self) -> None:
        return None

    def demo_vendors(self) -> list[dict[str, str]]:
        return [{"name": f["name"], "domain": f["domain"]} for f in FIXTURES.values()]

    def investigate_vendor(self, request: ResearchRequest) -> ResearchResult:
        fx = FIXTURES.get(fixture_key(request.vendor_name))
        if fx is None:
            raise ResearchError(
                f"Demo mode only knows the fixture vendors ({', '.join(f['name'] for f in FIXTURES.values())}); "
                f"'{request.vendor_name}' is not one of them.",
                category=ErrorCategory.NOT_FOUND, provider=PROVIDER,
            )
        now = datetime.now(UTC)
        sources: list[RetrievedSource] = []
        failures: list[SourceFailure] = []
        for page in fx["pages"][: request.max_pages]:
            if "error" in page:
                failures.append(SourceFailure(url=page["url"], reason=page["error"]))
                continue
            sources.append(RetrievedSource(
                source_key=f"S{len(sources) + 1}",
                url=page["url"],
                final_url=page["url"],
                title=f"[DEMO] {page['title']}",
                content=page["text"],
                content_hash=hashlib.sha256(page["text"].encode()).hexdigest(),
                retrieved_at=now,
                provider=PROVIDER,
                injection_suspected=detect_prompt_injection(page["text"]),
            ))
        return ResearchResult(
            vendor_name=fx["name"],
            resolved_domain=fx["domain"],
            domain_source="fixture",
            sources=sources,
            failures=failures,
            discovered_urls=[p["url"] for p in fx["pages"]],
            provider=PROVIDER,
            is_demo=True,
        )


def create(settings: Settings) -> FixtureResearchProvider:
    return FixtureResearchProvider()
