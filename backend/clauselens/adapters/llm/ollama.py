"""Ollama Cloud adapter using the native chat API.

Verified against docs.ollama.com (2026-10):
  * POST https://ollama.com/api/chat, header `Authorization: Bearer $OLLAMA_API_KEY`
  * body {model, messages, stream:false, format?: "json"|<schema>, options?, think?}
  * response {model, message:{role, content, thinking?}, done, done_reason,
    prompt_eval_count, eval_count, total_duration(ns)}
  * Cloud model ids come from GET https://ollama.com/api/tags (e.g. "gpt-oss:120b").
  * docs/capabilities/structured-outputs: "Ollama's cloud currently does not support
    structured outputs", so `format` is only sent when LLM_OUTPUT_MODE asks for it;
    callers always validate the returned text.
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

PROVIDER = "ollama"


class OllamaLLMProvider:
    name = PROVIDER
    is_demo = False

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else ""
        base = settings.llm_base_url.rstrip("/")
        if base.endswith("/v1"):
            raise ConfigurationError(
                "LLM_PROVIDER=ollama uses the native API; set LLM_BASE_URL=https://ollama.com "
                "or use LLM_PROVIDER=openai_compatible for a /v1 endpoint", provider=PROVIDER)
        is_cloud = "ollama.com" in base
        if is_cloud and not key:
            raise ConfigurationError("LLM_API_KEY is required for Ollama Cloud", provider=PROVIDER)
        if not settings.llm_model:
            raise ConfigurationError("LLM_MODEL is required", provider=PROVIDER)
        self.model = settings.llm_model
        self._settings = settings
        self._url = f"{base}/api/chat"
        self._headers = {"Authorization": f"Bearer {key}"} if key else {}
        self._client = client or httpx.Client(timeout=settings.llm_timeout_seconds)
        self._gate = threading.BoundedSemaphore(settings.llm_max_concurrency)

    def health_check(self) -> None:
        if "ollama.com" in self._url and not self._headers:
            raise ConfigurationError("Ollama API key missing", provider=PROVIDER)

    def _payload(self, request: LLMRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [m.model_dump() for m in request.messages],
            "stream": False,
            "options": {"temperature": request.temperature},
        }
        if request.max_output_tokens:
            payload["options"]["num_predict"] = request.max_output_tokens
        mode = self._settings.llm_output_mode
        if request.json_schema is not None and mode == "json":
            payload["format"] = "json"
        elif request.json_schema is not None and mode == "schema":
            payload["format"] = request.json_schema
        if self._settings.llm_think is not None:
            think: Any = self._settings.llm_think
            payload["think"] = {"true": True, "false": False}.get(str(think).lower(), think)
        return payload

    def generate(self, request: LLMRequest) -> LLMResponse:
        payload = self._payload(request)
        started = time.perf_counter()
        with self._gate:
            resp = send_with_retries(
                lambda: self._client.post(self._url, json=payload, headers=self._headers),
                provider=PROVIDER, operation=f"chat:{request.purpose}",
                max_retries=self._settings.llm_max_retries, error_cls=LLMError,
            )
        body = json_body(resp, provider=PROVIDER, operation="chat", error_cls=LLMError)
        message = body.get("message") if isinstance(body, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            metrics.inc("llm_requests_total", provider=PROVIDER, outcome="empty")
            raise LLMError(f"Ollama returned an empty response (done_reason={body.get('done_reason')})",
                           category=ErrorCategory.MALFORMED_OUTPUT, provider=PROVIDER)
        prompt_tokens = body.get("prompt_eval_count")
        completion_tokens = body.get("eval_count")
        metrics.inc("llm_requests_total", provider=PROVIDER, outcome="ok")
        if isinstance(prompt_tokens, int):
            metrics.inc("llm_prompt_tokens_total", prompt_tokens, provider=PROVIDER, model=self.model)
        if isinstance(completion_tokens, int):
            metrics.inc("llm_completion_tokens_total", completion_tokens, provider=PROVIDER, model=self.model)
        return LLMResponse(
            text=content,
            model=str(body.get("model") or self.model),
            provider=PROVIDER,
            prompt_tokens=prompt_tokens if isinstance(prompt_tokens, int) else None,
            completion_tokens=completion_tokens if isinstance(completion_tokens, int) else None,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )


def create(settings: Settings) -> OllamaLLMProvider:
    return OllamaLLMProvider(settings)
