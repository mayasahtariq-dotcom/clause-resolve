"""TinyFish research adapter (Search API + Fetch API).

Verified against docs.tinyfish.ai (2026-10):
  * Search: GET https://api.search.tinyfish.ai?query=...&include_domains=...&location=..
    header X-API-Key; response {query, results:[{position, site_name, title, snippet, url}], ...}
  * Fetch:  POST https://api.fetch.tinyfish.ai {"urls": [<=10], "format": "markdown", ...}
    response {results:[{url, final_url, title, text, ...}], errors:[{url, error, status?, message?}]}
    Private IPs, localhost and metadata endpoints are rejected by TinyFish itself.
Both are synchronous, so this adapter reports no async-job/cancellation capability.
Nothing TinyFish-specific leaves this module.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

import httpx

from clauselens.adapters.http import json_body, send_with_retries
from clauselens.config import Settings
from clauselens.domain.errors import ConfigurationError, ErrorCategory, ResearchError, UnsafeURLError
from clauselens.domain.models import RetrievedSource
from clauselens.observability import log_event, metrics
from clauselens.ports.research import (
    ResearchCapabilities,
    ResearchRequest,
    ResearchResult,
    SourceFailure,
)
from clauselens.security import (
    detect_prompt_injection,
    host_of,
    is_same_site,
    normalize_domain,
    sanitize_untrusted,
    validate_public_url,
)

logger = logging.getLogger(__name__)

PROVIDER = "tinyfish"

# Hosts that are never a vendor's official site.
NON_OFFICIAL_HOSTS = (
    "wikipedia.org", "linkedin.com", "reddit.com", "facebook.com", "twitter.com", "x.com", "youtube.com",
    "instagram.com", "crunchbase.com", "trustpilot.com", "glassdoor.com", "apps.apple.com",
    "play.google.com", "g2.com", "capterra.com", "quora.com", "medium.com", "bloomberg.com",
    "forbes.com", "pcmag.com", "techradar.com", "nerdwallet.com", "bbb.org", "tiktok.com",
)
TWO_LEVEL_SUFFIXES = ("co.uk", "org.uk", "ac.uk", "com.au", "net.au", "co.in", "co.jp", "com.br", "co.nz",
                      "com.mx", "co.za", "com.sg", "com.tr", "co.kr")
POLICY_KEYWORDS = {
    "refund": 5, "cancel": 5, "return": 4, "terms": 3, "subscription": 3, "trial": 3, "billing": 3,
    "renew": 3, "policy": 2, "legal": 2, "help": 1, "support": 1, "faq": 1, "payment": 1,
}
_TOKEN_RE = re.compile(r"[^a-z0-9]")


def registrable_domain(host: str) -> str:
    labels = host.split(".")
    n = 3 if any(host.endswith("." + s) for s in TWO_LEVEL_SUFFIXES) else 2
    return ".".join(labels[-n:])


def _vendor_token(name: str) -> str:
    return _TOKEN_RE.sub("", name.lower())


def _canonical(url: str) -> str:
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip("/") or "/", "", ""))


def _relevance(url: str, title: str | None, snippet: str | None) -> int:
    hay = f"{url} {title or ''} {snippet or ''}".lower()
    return sum(w for k, w in POLICY_KEYWORDS.items() if k in hay)


class TinyFishResearchProvider:
    name = PROVIDER
    is_demo = False
    capabilities = ResearchCapabilities(asynchronous_jobs=False, cancellation=False)

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        if settings.tinyfish_api_key is None or not settings.tinyfish_api_key.get_secret_value():
            raise ConfigurationError("TINYFISH_API_KEY is required for WEB_RESEARCH_PROVIDER=tinyfish",
                                     provider=PROVIDER)
        self._settings = settings
        self._client = client or httpx.Client(timeout=settings.tinyfish_timeout_seconds)
        self._headers = {"X-API-Key": settings.tinyfish_api_key.get_secret_value()}

    # --- low-level calls -------------------------------------------------
    def _search(self, query: str, *, include_domains: str | None = None) -> list[dict]:
        params = {"query": query, "location": self._settings.tinyfish_location}
        if include_domains:
            params["include_domains"] = include_domains
        resp = send_with_retries(
            lambda: self._client.get(self._settings.tinyfish_search_url, params=params, headers=self._headers),
            provider=PROVIDER, operation="search", max_retries=self._settings.tinyfish_max_retries,
            error_cls=ResearchError,
        )
        body = json_body(resp, provider=PROVIDER, operation="search", error_cls=ResearchError)
        results = body.get("results") if isinstance(body, dict) else None
        if not isinstance(results, list):
            raise ResearchError("TinyFish search response had no results array",
                                category=ErrorCategory.MALFORMED_OUTPUT, provider=PROVIDER)
        metrics.inc("research_searches_total", provider=PROVIDER)
        return [r for r in results if isinstance(r, dict) and isinstance(r.get("url"), str)]

    def _fetch(self, urls: list[str], purpose: str) -> tuple[list[dict], list[dict]]:
        payload = {
            "urls": urls[:10],
            "format": "markdown",
            "links": False,
            "image_links": False,
            "purpose": purpose[:2000],
            "per_url_timeout_ms": 45_000,
        }
        resp = send_with_retries(
            lambda: self._client.post(self._settings.tinyfish_fetch_url, json=payload, headers=self._headers),
            provider=PROVIDER, operation="fetch", max_retries=self._settings.tinyfish_max_retries,
            error_cls=ResearchError,
        )
        body = json_body(resp, provider=PROVIDER, operation="fetch", error_cls=ResearchError)
        if not isinstance(body, dict) or not isinstance(body.get("results", []), list):
            raise ResearchError("TinyFish fetch response was malformed", category=ErrorCategory.MALFORMED_OUTPUT,
                                provider=PROVIDER)
        return list(body.get("results") or []), list(body.get("errors") or [])

    # --- port implementation --------------------------------------------
    def health_check(self) -> None:
        # Configuration-only: a live search would spend quota on every readiness probe.
        if not self._headers.get("X-API-Key"):
            raise ConfigurationError("TinyFish API key missing", provider=PROVIDER)

    def resolve_domain(self, vendor_name: str) -> str | None:
        token = _vendor_token(vendor_name)
        for r in self._search(f"{vendor_name} official website"):
            host = host_of(r["url"])
            if not host or any(host == h or host.endswith("." + h) for h in NON_OFFICIAL_HOSTS):
                continue
            domain = registrable_domain(host[4:] if host.startswith("www.") else host)
            if token and token[:6] in _vendor_token(domain):
                return domain
        return None

    def investigate_vendor(self, request: ResearchRequest) -> ResearchResult:
        if request.domain:
            try:
                domain: str | None = normalize_domain(request.domain)
            except UnsafeURLError as exc:
                raise ResearchError(exc.message, category=ErrorCategory.INVALID_REQUEST, provider=PROVIDER) from exc
            domain_source = "user"
        else:
            domain = self.resolve_domain(request.vendor_name)
            domain_source = "search" if domain else "unresolved"
        if domain is None:
            raise ResearchError(
                f"Could not identify an official website for '{request.vendor_name}'. "
                "Enter the vendor's domain (e.g. example.com) and try again.",
                category=ErrorCategory.NOT_FOUND, provider=PROVIDER,
            )

        candidates: dict[str, tuple[int, str]] = {}
        for topic in request.topics:
            for r in self._search(f"{request.vendor_name} {topic}", include_domains=domain):
                url = r["url"]
                if not is_same_site(url, domain):
                    continue
                try:
                    validate_public_url(url)
                except UnsafeURLError:
                    continue
                key = _canonical(url)
                score = _relevance(url, r.get("title"), r.get("snippet"))
                if key not in candidates or candidates[key][0] < score:
                    candidates[key] = (score, url)
        ranked = sorted(candidates.values(), key=lambda t: (-t[0], t[1]))
        selected = [u for s, u in ranked if s > 0][: request.max_pages]
        log_event(logger, logging.INFO, "policy pages discovered", provider=PROVIDER,
                  candidates=len(candidates), selected=len(selected))

        sources: list[RetrievedSource] = []
        failures: list[SourceFailure] = []
        if selected:
            results, errors = self._fetch(
                selected, purpose=f"Extract refund, cancellation, renewal and trial policy terms for {request.vendor_name}"
            )
            now = datetime.now(UTC)
            seen_hashes: set[str] = set()
            for item in results:
                url = item.get("url") if isinstance(item.get("url"), str) else None
                final_url = item.get("final_url") if isinstance(item.get("final_url"), str) else None
                text = item.get("text")
                if not url:
                    continue
                if not isinstance(text, str) or not text.strip():
                    failures.append(SourceFailure(url=url, reason="empty_content"))
                    continue
                landed = final_url or url
                try:
                    validate_public_url(landed)
                except UnsafeURLError as exc:
                    failures.append(SourceFailure(url=url, reason="unsafe_url", message=exc.message))
                    continue
                if not is_same_site(landed, domain):
                    failures.append(SourceFailure(url=url, reason="offsite_redirect",
                                                  message=f"Redirected outside {domain}"))
                    continue
                content = sanitize_untrusted(text, self._settings.max_source_chars)
                digest = hashlib.sha256(content.encode()).hexdigest()
                if digest in seen_hashes:
                    continue
                seen_hashes.add(digest)
                sources.append(RetrievedSource(
                    source_key=f"S{len(sources) + 1}",
                    url=url,
                    final_url=final_url,
                    title=item.get("title") if isinstance(item.get("title"), str) else None,
                    content=content,
                    content_hash=digest,
                    retrieved_at=now,
                    provider=PROVIDER,
                    injection_suspected=detect_prompt_injection(content),
                ))
            for err in errors:
                if isinstance(err, dict):
                    failures.append(SourceFailure(
                        url=str(err.get("url", "")),
                        reason=str(err.get("error") or "fetch_failed"),
                        message=str(err.get("message")) if err.get("message") else None,
                    ))
        metrics.inc("research_pages_retrieved_total", len(sources), provider=PROVIDER)
        metrics.inc("research_page_failures_total", len(failures), provider=PROVIDER)
        return ResearchResult(
            vendor_name=request.vendor_name,
            resolved_domain=domain,
            domain_source=domain_source,
            sources=sources,
            failures=failures,
            discovered_urls=selected,
            provider=PROVIDER,
        )


def create(settings: Settings) -> TinyFishResearchProvider:
    return TinyFishResearchProvider(settings)
