"""LLM port: provider-independent text generation."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class LLMMessage(BaseModel):
    role: str  # "system" | "user"
    content: str


class LLMRequest(BaseModel):
    messages: list[LLMMessage]
    json_schema: dict[str, Any] | None = None  # desired output shape (hint or constraint)
    temperature: float = 0.0
    max_output_tokens: int | None = Field(default=4096, gt=0)
    purpose: str = "generic"  # "extraction" | "explanation"; used for logs/metrics only


class LLMResponse(BaseModel):
    text: str
    model: str
    provider: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    duration_ms: float | None = None
    is_demo: bool = False


@runtime_checkable
class LLMProvider(Protocol):
    """Implementations translate provider errors into clauselens LLMError and
    handle provider differences in structured-output support internally."""

    name: str
    model: str
    is_demo: bool

    def generate(self, request: LLMRequest) -> LLMResponse: ...

    def health_check(self) -> None: ...
