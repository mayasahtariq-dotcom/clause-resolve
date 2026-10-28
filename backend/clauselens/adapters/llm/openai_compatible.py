"""Adapter for any OpenAI-compatible /v1/chat/completions endpoint.

Works with Ollama Cloud's documented compatibility layer
(LLM_BASE_URL=https://ollama.com/v1) and with self-hosted servers that expose
the same contract (vLLM, llama.cpp server, LM Studio, ...). Selecting it is a
configuration change only: LLM_PROVIDER=openai_compatible.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import httpx

from clauselens.adapters.http import json_body, send_with_retries
from clauselens.config import Settings
from clauselens.domain.errors import ConfigurationError, ErrorCategory, LLMError
from clauselens.observability import metrics
from clauselens.ports.llm import LLMRequest, LLMResponse

PROVIDER = "openai_compatible"


class OpenAICompatibleLLMProvider:
    name = PROVIDER
    is_demo = False

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        base = settings.llm_base_url.rstrip("/")
        if not base.endswith("/v1"):
            raise ConfigurationError("LLM_BASE_URL for openai_compatible must end with /v1", provider=PROVIDER)
        if not settings.llm_model:
            raise ConfigurationError("LLM_MODEL is required", provider=PROVIDER)
        key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else ""
        self.model = settings.llm_model
        self._settings = settings
        self._url = f"{base}/chat/completions"
        self._headers = {"Authorization": f"Bearer {key}"} if key else {}
        self._client = client or httpx.Client(timeout=settings.llm_timeout_seconds)
        self._gate = threading.BoundedSemaphore(settings.llm_max_concurrency)

    def health_check(self) -> None:
        return None

    def generate(self, request: LLMRequest) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [m.model_dump() for m in request.messages],
            "temperature": request.temperature,
            "stream": False,
        }
        if request.max_output_tokens:
            payload["max_tokens"] = request.max_output_tokens
        mode = self._settings.llm_output_mode
        if request.json_schema is not None and mode == "json":
            payload["response_format"] = {"type": "json_object"}
        elif request.json_schema is not None and mode == "schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "output", "schema": request.json_schema},
            }
        if self._settings.llm_think in {"low", "medium", "high"}:
            payload["reasoning_effort"] = self._settings.llm_think
        started = time.perf_counter()
        with self._gate:
            resp = send_with_retries(
                lambda: self._client.post(self._url, json=payload, headers=self._headers),
                provider=PROVIDER, operation=f"chat:{request.purpose}",
                max_retries=self._settings.llm_max_retries, error_cls=LLMError,
            )
        body = json_body(resp, provider=PROVIDER, operation="chat", error_cls=LLMError)
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Chat completion response had no choices[0].message.content",
                           category=ErrorCategory.MALFORMED_OUTPUT, provider=PROVIDER) from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMError("Model returned empty content", category=ErrorCategory.MALFORMED_OUTPUT,
                           provider=PROVIDER)
        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        metrics.inc("llm_requests_total", provider=PROVIDER, outcome="ok")
        return LLMResponse(
            text=content,
            model=str(body.get("model") or self.model),
            provider=PROVIDER,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )


def create(settings: Settings) -> OpenAICompatibleLLMProvider:
    return OpenAICompatibleLLMProvider(settings)
