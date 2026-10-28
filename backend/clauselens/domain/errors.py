"""Application-level errors. Adapters translate provider failures into these."""

from __future__ import annotations

from enum import StrEnum


class ErrorCategory(StrEnum):
    CONFIGURATION = "configuration"  # missing key, unsupported provider
    AUTHENTICATION = "authentication"
    QUOTA = "quota"  # out of credits / allowance
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"  # provider down / 5xx / network
    INVALID_REQUEST = "invalid_request"
    NOT_FOUND = "not_found"
    BLOCKED = "blocked"  # target site blocked, login wall, SSRF guard
    MALFORMED_OUTPUT = "malformed_output"
    INTERNAL = "internal"


TRANSIENT = {ErrorCategory.RATE_LIMITED, ErrorCategory.TIMEOUT, ErrorCategory.UNAVAILABLE}


class ClauseLensError(Exception):
    def __init__(
        self,
        message: str,
        *,
        category: ErrorCategory = ErrorCategory.INTERNAL,
        provider: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.category = category
        self.provider = provider
        self.retry_after = retry_after

    @property
    def transient(self) -> bool:
        return self.category in TRANSIENT

    def to_dict(self) -> dict[str, str | None]:
        return {"message": self.message, "category": self.category.value, "provider": self.provider}


class ConfigurationError(ClauseLensError):
    def __init__(self, message: str, *, provider: str | None = None) -> None:
        super().__init__(message, category=ErrorCategory.CONFIGURATION, provider=provider)


class ResearchError(ClauseLensError):
    pass


class LLMError(ClauseLensError):
    pass


class NotFoundError(ClauseLensError):
    def __init__(self, message: str) -> None:
        super().__init__(message, category=ErrorCategory.NOT_FOUND)


class UnsafeURLError(ClauseLensError):
    def __init__(self, message: str) -> None:
        super().__init__(message, category=ErrorCategory.BLOCKED)
