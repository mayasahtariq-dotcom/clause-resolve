"""Demo LLM provider: replays canned responses for the fixture vendors (no network)."""

from __future__ import annotations

import json

from clauselens.adapters.fixture_data import RISK_RESPONSES, find_by_domain
from clauselens.config import Settings
from clauselens.domain.errors import ErrorCategory, LLMError
from clauselens.ports.llm import LLMRequest, LLMResponse

PROVIDER = "fixture"


class FixtureLLMProvider:
    name = PROVIDER
    model = "fixture-replay"
    is_demo = True

    def health_check(self) -> None:
        return None

    def generate(self, request: LLMRequest) -> LLMResponse:
        prompt = "\n".join(m.content for m in request.messages)
        if request.purpose == "explanation":
            facts = json.loads(prompt.split("Comparison facts (JSON):\n", 1)[1])
            text = f"[Demo explanation] {facts['recommendation']}"
            if facts.get("conflicts"):
                text += " Some sources conflict, so check the flagged terms before deciding."
            return LLMResponse(text=text, model=self.model, provider=PROVIDER, is_demo=True)
        if request.purpose == "risk_analysis":
            page = prompt.split("Page: ", 1)[1].split("\n", 1)[0].strip() if "Page: " in prompt else ""
            if page not in RISK_RESPONSES:
                raise LLMError("No demo risk fixture for this page", category=ErrorCategory.NOT_FOUND,
                               provider=PROVIDER)
            return LLMResponse(text=RISK_RESPONSES[page], model=self.model, provider=PROVIDER, is_demo=True)
        fx = find_by_domain(prompt)
        if fx is None:
            raise LLMError("No demo fixture matches these sources", category=ErrorCategory.NOT_FOUND,
                           provider=PROVIDER)
        return LLMResponse(text=fx["extraction_response"], model=self.model, provider=PROVIDER, is_demo=True)


def create(settings: Settings) -> FixtureLLMProvider:
    return FixtureLLMProvider()
