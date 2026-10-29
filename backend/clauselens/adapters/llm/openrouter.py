"""OpenRouter adapter (LLM_PROVIDER=openrouter).

Verified against openrouter.ai/docs (2026-10):
  * POST https://openrouter.ai/api/v1/chat/completions, header `Authorization: Bearer <key>`
  * optional attribution headers `HTTP-Referer` and `X-OpenRouter-Title`
  * body {model, messages, temperature, max_tokens, response_format?: {type: json_object} |
    {type: json_schema, json_schema: {name, strict, schema}}}
  * response {id, model, choices:[{message:{content}, finish_reason}], usage:{prompt_tokens, completion_tokens}}
  * errors: {error:{code, message, metadata?}} with HTTP 400/401/402/403/408/429/502/503;
    429/503 may carry Retry-After. A provider failure after the request is accepted
    arrives as HTTP 200 whose body holds an `error` object (and no choices), so the body
    is always checked. finish_reason "length" with empty content means the output
    budget was exhausted.
TinyFish is unaffected: this adapter only analyses text the research step already retrieved.
"""

from __future__ import annotations

import random
import threading
import time
from typing import Any

import httpx

from clauselens.adapters.http import category_for_status, json_body, send_with_retries
from clauselens.config import Settings
from clauselens.domain.errors import ConfigurationError, ErrorCategory, LLMError
from clauselens.observability import metrics
from clauselens.ports.llm import LLMRequest, LLMResponse

PROVIDER = "openrouter"
MAX_BACKOFF_SECONDS = 30.0


class OpenRouterLLMProvider:
    name = PROVIDER
    is_demo = False

    def __init__(self, settings: Settings, client: httpx.Client | None = None,
                 sleep: Any = None) -> None:
        key = settings.openrouter_api_key.get_secret_value() if settings.openrouter_api_key else ""
        if not key:
            raise ConfigurationError("OPENROUTER_API_KEY is required for LLM_PROVIDER=openrouter", provider=PROVIDER)
        if not settings.openrouter_model:
            raise ConfigurationError("OPENROUTER_MODEL is required (e.g. google/gemini-2.5-flash)", provider=PROVIDER)
        self.model = settings.openrouter_model
        self._settings = settings
        self._url = settings.openrouter_base_url.rstrip("/") + "/chat/completions"
        self._headers = {"Authorization": f"Bearer {key}", "X-OpenRouter-Title": settings.openrouter_app_title}
        if settings.openrouter_app_url:
            self._headers["HTTP-Referer"] = settings.openrouter_app_url
        self._client = client or httpx.Client(timeout=settings.llm_timeout_seconds)
        self._gate = threading.BoundedSemaphore(settings.llm_max_concurrency)
        self._sleep = sleep or time.sleep

    def health_check(self) -> None:
        # Configuration-only: a live call on every readiness probe would spend credits.
        if not self._headers.get("Authorization"):
            raise ConfigurationError("OpenRouter API key missing", provider=PROVIDER)

    def _payload(self, request: LLMRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [m.model_dump() for m in request.messages],
            "temperature": request.temperature,
            "stream": False,
        }
        if request.max_output_tokens:
            payload["max_tokens"] = request.max_output_tokens
        fmt = self._settings.openrouter_response_format
        if request.json_schema is not None and fmt == "json_object":
            payload["response_format"] = {"type": "json_object"}
        elif request.json_schema is not None and fmt == "json_schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": request.purpose or "output", "strict": False, "schema": request.json_schema},
            }
            # Route only to endpoints that honour response_format.
            payload["provider"] = {"require_parameters": True}
        return payload

    @staticmethod
    def _body_error(body: dict[str, Any]) -> LLMError | None:
        """Errors that arrive inside an HTTP 200 body (top level or on the choice)."""
        err = body.get("error")
        if not isinstance(err, dict):
            choices = body.get("choices")
            if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                err = choices[0].get("error") if isinstance(choices[0].get("error"), dict) else None
        if not isinstance(err, dict):
            return None
        code = err.get("code")
        status = code if isinstance(code, int) else 502
        message = str(err.get("message") or "provider error")[:300]
        return LLMError(f"OpenRouter provider error {status}: {message}", category=category_for_status(status),
                        provider=PROVIDER)

    def generate(self, request: LLMRequest) -> LLMResponse:
        payload = self._payload(request)
        started = time.perf_counter()
        attempts = self._settings.llm_max_retries + 1
        for attempt in range(attempts):
            with self._gate:
                resp = send_with_retries(
                    lambda: self._client.post(self._url, json=payload, headers=self._headers),
                    provider=PROVIDER, operation=f"chat:{request.purpose}",
                    max_retries=self._settings.llm_max_retries, error_cls=LLMError,
                )
            body = json_body(resp, provider=PROVIDER, operation="chat", error_cls=LLMError)
            if not isinstance(body, dict):
                raise LLMError("OpenRouter returned a non-object body", category=ErrorCategory.MALFORMED_OUTPUT,
                               provider=PROVIDER)
            err = self._body_error(body)
            if err is None:
                break
            metrics.inc("provider_errors_total", provider=PROVIDER, operation="chat-body", category=err.category.value)
            if not err.transient or attempt == attempts - 1:
                raise err
            self._sleep(min(MAX_BACKOFF_SECONDS, 2 ** attempt + random.uniform(0, 0.5)))

        try:
            choice = body["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("OpenRouter response had no choices[0].message.content",
                           category=ErrorCategory.MALFORMED_OUTPUT, provider=PROVIDER) from exc
        finish = choice.get("finish_reason")
        if not isinstance(content, str) or not content.strip():
            reason = ("the model used its whole output budget (finish_reason=length); raise max tokens"
                      if finish == "length" else f"empty content (finish_reason={finish})")
            metrics.inc("llm_requests_total", provider=PROVIDER, outcome="empty")
            raise LLMError(f"OpenRouter returned no text: {reason}", category=ErrorCategory.MALFORMED_OUTPUT,
                           provider=PROVIDER)
        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        prompt_tokens = usage.get("prompt_tokens") if isinstance(usage.get("prompt_tokens"), int) else None
        completion_tokens = usage.get("completion_tokens") if isinstance(usage.get("completion_tokens"), int) else None
        metrics.inc("llm_requests_total", provider=PROVIDER, outcome="ok")
        if prompt_tokens:
            metrics.inc("llm_prompt_tokens_total", prompt_tokens, provider=PROVIDER, model=self.model)
        if completion_tokens:
            metrics.inc("llm_completion_tokens_total", completion_tokens, provider=PROVIDER, model=self.model)
        if isinstance(usage.get("cost"), int | float):
            metrics.inc("llm_cost_credits_total", float(usage["cost"]), provider=PROVIDER, model=self.model)
        return LLMResponse(
            text=content,
            model=str(body.get("model") or self.model),
            provider=PROVIDER,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )


def create(settings: Settings) -> OpenRouterLLMProvider:
    return OpenRouterLLMProvider(settings)
