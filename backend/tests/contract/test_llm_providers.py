"""Shared LLMProvider contract plus Ollama / OpenAI-compatible adapter specifics (HTTP mocked)."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest
import respx

from clauselens.adapters.llm.fixture import FixtureLLMProvider
from clauselens.adapters.llm.ollama import OllamaLLMProvider
from clauselens.adapters.llm.openai_compatible import OpenAICompatibleLLMProvider
from clauselens.domain.errors import ConfigurationError, ErrorCategory, LLMError
from clauselens.ports.llm import LLMMessage, LLMProvider, LLMRequest, LLMResponse
from clauselens.services.extraction import extract_policy
from tests.conftest import make_settings, source

OLLAMA_URL = "https://ollama.com/api/chat"
OPENAI_URL = "https://ollama.com/v1/chat/completions"
CLAIMS = json.dumps({"claims": [{"field": "refund_window", "source_id": "S1",
                                 "quote": "refund within 14 days of purchase",
                                 "value": {"duration": {"value": 14, "unit": "day"}}}]})


def ollama(**kw: object) -> OllamaLLMProvider:
    return OllamaLLMProvider(make_settings(llm_provider="ollama", llm_api_key="ol-key", llm_max_retries=1, **kw),
                             client=httpx.Client())


def openai_compat(**kw: object) -> OpenAICompatibleLLMProvider:
    return OpenAICompatibleLLMProvider(make_settings(llm_provider="openai_compatible", llm_base_url="https://ollama.com/v1",
                                                     llm_api_key="ol-key", llm_max_retries=1, **kw), client=httpx.Client())


def ollama_ok(text: str) -> httpx.Response:
    return httpx.Response(200, json={"model": "gpt-oss:120b", "created_at": "2026-10-28T00:00:00Z",
                                     "message": {"role": "assistant", "content": text, "thinking": "..."},
                                     "done": True, "done_reason": "stop", "prompt_eval_count": 120, "eval_count": 30})


def openai_ok(text: str) -> httpx.Response:
    return httpx.Response(200, json={"id": "x", "model": "gpt-oss:120b", "choices": [
        {"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20}})


CASES: dict[str, Callable[[respx.Router, str], LLMProvider]] = {
    "ollama": lambda r, t: (r.post(OLLAMA_URL).mock(return_value=ollama_ok(t)), ollama())[1],
    "openai_compatible": lambda r, t: (r.post(OPENAI_URL).mock(return_value=openai_ok(t)), openai_compat())[1],
}

REQ = LLMRequest(messages=[LLMMessage(role="system", content="s"), LLMMessage(role="user", content="u")],
                 json_schema={"type": "object"}, purpose="extraction")


@pytest.mark.parametrize("case", CASES)
def test_llm_contract_generate(case: str) -> None:
    with respx.mock() as router:
        provider = CASES[case](router, CLAIMS)
        assert isinstance(provider, LLMProvider)
        resp = provider.generate(REQ)
    assert isinstance(resp, LLMResponse)
    assert resp.text == CLAIMS and resp.provider == provider.name and resp.model
    assert resp.prompt_tokens and resp.completion_tokens


@pytest.mark.parametrize("case", CASES)
def test_llm_contract_drives_extraction_pipeline(case: str) -> None:
    """The extraction service works unchanged with any adapter."""
    with respx.mock() as router:
        provider = CASES[case](router, CLAIMS)
        outcome = extract_policy(provider, "Acme", [source("S1", "You can get a refund within 14 days of purchase.")],
                                 max_input_chars=10_000)
    assert outcome.claims[0].value.duration.days == 14  # type: ignore[union-attr]
    assert outcome.meta["provider"] == provider.name


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("status,category", [(401, ErrorCategory.AUTHENTICATION), (429, ErrorCategory.RATE_LIMITED),
                                             (500, ErrorCategory.UNAVAILABLE), (400, ErrorCategory.INVALID_REQUEST)])
def test_llm_contract_errors_translate(case: str, status: int, category: ErrorCategory,
                                      monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda s: None)
    with respx.mock() as router:
        provider = CASES[case](router, "")
        router.routes.clear()
        route = router.post(url__regex=r"https://ollama\.com/.*").mock(
            return_value=httpx.Response(status, json={"error": "model 'x' not found"}))
        with pytest.raises(LLMError) as exc:
            provider.generate(REQ)
    assert exc.value.category is category
    assert route.call_count == (2 if category in {ErrorCategory.RATE_LIMITED, ErrorCategory.UNAVAILABLE} else 1)
    assert "ol-key" not in exc.value.message


@pytest.mark.parametrize("case", CASES)
def test_llm_contract_empty_output_is_malformed(case: str) -> None:
    with respx.mock() as router:
        provider = CASES[case](router, "   ")
        with pytest.raises(LLMError) as exc:
            provider.generate(REQ)
    assert exc.value.category is ErrorCategory.MALFORMED_OUTPUT


@respx.mock
def test_ollama_payload_matches_documented_api() -> None:
    route = respx.post(OLLAMA_URL).mock(return_value=ollama_ok(CLAIMS))
    ollama().generate(REQ)
    req = route.calls[0].request
    body = json.loads(req.content)
    assert req.headers["Authorization"] == "Bearer ol-key"
    assert body["model"] == "gpt-oss:120b" and body["stream"] is False
    assert body["messages"][0] == {"role": "system", "content": "s"}
    assert "format" not in body, "cloud structured outputs unsupported: default mode sends no format"
    assert body["think"] == "low"
    assert body["options"]["temperature"] == 0.0


@pytest.mark.parametrize("mode,expected", [("json", "json"), ("schema", {"type": "object"})])
@respx.mock
def test_ollama_output_modes(mode: str, expected: object) -> None:
    route = respx.post(OLLAMA_URL).mock(return_value=ollama_ok(CLAIMS))
    ollama(llm_output_mode=mode).generate(REQ)
    assert json.loads(route.calls[0].request.content)["format"] == expected


@respx.mock
def test_openai_compatible_payload() -> None:
    route = respx.post(OPENAI_URL).mock(return_value=openai_ok(CLAIMS))
    openai_compat(llm_output_mode="json").generate(REQ)
    body = json.loads(route.calls[0].request.content)
    assert body["response_format"] == {"type": "json_object"} and body["reasoning_effort"] == "low"


def test_ollama_configuration_errors() -> None:
    with pytest.raises(ConfigurationError):
        OllamaLLMProvider(make_settings(llm_provider="ollama"))  # cloud without key
    with pytest.raises(ConfigurationError):
        OllamaLLMProvider(make_settings(llm_provider="ollama", llm_api_key="k", llm_base_url="https://ollama.com/v1"))
    assert OllamaLLMProvider(make_settings(llm_provider="ollama", llm_base_url="http://localhost:11434"))


def test_openai_compatible_requires_v1_base() -> None:
    with pytest.raises(ConfigurationError):
        OpenAICompatibleLLMProvider(make_settings(llm_base_url="https://ollama.com"))


def test_fixture_llm_is_labelled_demo() -> None:
    assert FixtureLLMProvider().is_demo
    with pytest.raises(LLMError):
        FixtureLLMProvider().generate(LLMRequest(messages=[LLMMessage(role="user", content="unknown.example")]))
