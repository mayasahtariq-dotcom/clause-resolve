"""Opt-in smoke tests against the REAL TinyFish and Ollama Cloud APIs.

Skipped unless RUN_LIVE_TESTS=1 and credentials are present. They spend
provider quota, so they never run in normal CI.

    RUN_LIVE_TESTS=1 TINYFISH_API_KEY=... LLM_API_KEY=... .venv/bin/pytest tests/test_live_providers.py -v
"""

from __future__ import annotations

import os

import pytest

from clauselens.adapters.llm.ollama import OllamaLLMProvider
from clauselens.adapters.research.tinyfish import TinyFishResearchProvider
from clauselens.ports.llm import LLMMessage, LLMRequest
from clauselens.ports.research import ResearchRequest
from clauselens.services.extraction import extract_policy
from tests.conftest import make_settings

LIVE = os.environ.get("RUN_LIVE_TESTS") == "1"
pytestmark = [pytest.mark.live, pytest.mark.skipif(not LIVE, reason="set RUN_LIVE_TESTS=1 to call paid providers")]


def _require(var: str) -> str:
    value = os.environ.get(var)
    if not value:
        pytest.skip(f"{var} not set")
    return value


def test_ollama_cloud_generates() -> None:
    llm = OllamaLLMProvider(make_settings(llm_provider="ollama", llm_api_key=_require("LLM_API_KEY"),
                                          llm_model=os.environ.get("LLM_MODEL", "gpt-oss:120b")))
    resp = llm.generate(LLMRequest(messages=[LLMMessage(role="user", content="Reply with the single word: ok")],
                                   max_output_tokens=200))
    assert resp.text.strip()


def test_tinyfish_then_ollama_extraction() -> None:
    research = TinyFishResearchProvider(make_settings(web_research_provider="tinyfish",
                                                      tinyfish_api_key=_require("TINYFISH_API_KEY")))
    result = research.investigate_vendor(ResearchRequest(vendor_name="Coursera", domain="coursera.org", max_pages=3))
    assert result.sources, f"no pages retrieved: {result.failures}"
    llm = OllamaLLMProvider(make_settings(llm_provider="ollama", llm_api_key=_require("LLM_API_KEY")))
    outcome = extract_policy(llm, "Coursera", result.sources, max_input_chars=40_000)
    assert outcome.meta["provider"] == "ollama"


def test_openrouter_risk_scan_live() -> None:
    """RUN_LIVE_TESTS=1 OPENROUTER_API_KEY=... OPENROUTER_MODEL=... pytest tests/test_live_providers.py -k openrouter"""
    import uuid

    from clauselens.adapters.llm.openrouter import OpenRouterLLMProvider
    from clauselens.domain.models import Vendor
    from clauselens.domain.risk import RiskAnalysisStatus
    from clauselens.services.risk_analysis import analyze_vendor_risks
    from tests.conftest import source

    llm = OpenRouterLLMProvider(make_settings(llm_provider="openrouter", openrouter_api_key=_require("OPENROUTER_API_KEY"),
                                              openrouter_model=os.environ.get("OPENROUTER_MODEL", "google/gemini-2.5-flash")))
    page = source("S1", "Your subscription renews automatically each year at the then-current price. "
                        "All fees are non-refundable. Any dispute will be resolved by binding arbitration.")
    result = analyze_vendor_risks(llm, Vendor(id=uuid.uuid4(), name="Acme"), [page],
                                  chunk_chars=12_000, max_chunks=1, max_clauses=10)
    assert result.status is RiskAnalysisStatus.COMPLETED and result.clauses
