"""Centralised, validated configuration. The only place environment variables are read."""

from __future__ import annotations

import json
from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from clauselens.domain.errors import ConfigurationError


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


# Provider names that only produce clearly labelled demonstration data.
DEMO_PROVIDERS = {"fixture"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Environment = Environment.DEVELOPMENT
    log_level: str = "INFO"
    log_json: bool = True

    # --- HTTP API ---
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["http://localhost:5173"])
    max_vendors_per_investigation: int = Field(default=5, ge=2, le=10)
    rate_limit_investigations_per_minute: int = Field(default=10, ge=1)

    # --- Persistence ---
    persistence_provider: str = "sqlalchemy"
    database_url: str = "postgresql+psycopg://clauselens:clauselens@localhost:5432/clauselens"
    db_pool_size: int = 5
    max_source_chars: int = Field(default=120_000, ge=1_000)

    # --- Web research ---
    web_research_provider: str = "tinyfish"
    tinyfish_api_key: SecretStr | None = None
    tinyfish_search_url: str = "https://api.search.tinyfish.ai"
    tinyfish_fetch_url: str = "https://api.fetch.tinyfish.ai"
    tinyfish_timeout_seconds: float = 90.0
    tinyfish_max_retries: int = Field(default=2, ge=0, le=5)
    tinyfish_location: str = "US"
    research_max_pages_per_vendor: int = Field(default=6, ge=1, le=10)
    research_vendor_concurrency: int = Field(default=3, ge=1, le=10)

    # --- LLM ---
    llm_provider: str = "ollama"
    llm_base_url: str = "https://ollama.com"
    llm_api_key: SecretStr | None = None
    llm_model: str = "gpt-oss:120b"
    llm_timeout_seconds: float = 120.0
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    llm_max_concurrency: int = Field(default=4, ge=1, le=32)
    # How to ask for JSON: "prompt" (instructions only), "json" (JSON mode),
    # "schema" (JSON-schema-constrained). Ollama Cloud documents no structured
    # output support, so the default relies on prompt + strict validation.
    llm_output_mode: str = "prompt"
    llm_think: str | None = "low"
    llm_max_input_chars: int = Field(default=60_000, ge=4_000)
    llm_generate_explanation: bool = True

    # --- Background jobs ---
    job_queue_provider: str = "celery"
    redis_url: str = "redis://localhost:6379/0"
    job_lease_seconds: int = Field(default=900, ge=60)
    job_max_retries: int = Field(default=2, ge=0, le=5)
    allow_non_durable_queue: bool = False

    # --- Storage ---
    storage_provider: str = "none"
    storage_local_path: str = "./var/artifacts"

    # --- Comparison ---
    scoring_policy_json: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return json.loads(v)
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator("database_url")
    @classmethod
    def _driver(cls, v: str) -> str:
        # Managed hosts (Render, Heroku, Railway...) hand out postgres:// URLs; use the psycopg 3 driver.
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @field_validator("llm_output_mode")
    @classmethod
    def _mode(cls, v: str) -> str:
        if v not in {"prompt", "json", "schema"}:
            raise ValueError("LLM_OUTPUT_MODE must be prompt, json or schema")
        return v

    @field_validator("llm_think", mode="before")
    @classmethod
    def _think(cls, v: object) -> object:
        return None if v in ("", "none", "null", None) else v

    @model_validator(mode="after")
    def _production_rules(self) -> Settings:
        if self.environment is not Environment.PRODUCTION:
            return self
        problems: list[str] = []
        for label, provider in (("WEB_RESEARCH_PROVIDER", self.web_research_provider),
                                ("LLM_PROVIDER", self.llm_provider)):
            if provider in DEMO_PROVIDERS:
                problems.append(f"{label}={provider} produces demo data and is not allowed in production")
        if self.job_queue_provider in {"inline", "sync"} and not self.allow_non_durable_queue:
            problems.append(f"JOB_QUEUE_PROVIDER={self.job_queue_provider} is not durable; "
                            "use celery or set ALLOW_NON_DURABLE_QUEUE=true deliberately")
        if not self.database_url.startswith("postgresql"):
            problems.append("DATABASE_URL must point to PostgreSQL in production")
        if "*" in self.cors_origins:
            problems.append("CORS_ORIGINS must list explicit origins in production")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION

    def scoring_policy(self) -> dict | None:
        if not self.scoring_policy_json:
            return None
        from clauselens.domain.models import Criterion

        try:
            raw = json.loads(self.scoring_policy_json)
            return {Criterion(k): float(v) for k, v in raw.items() if float(v) > 0}
        except (ValueError, TypeError) as exc:
            raise ConfigurationError(f"SCORING_POLICY_JSON is invalid: {exc}") from exc

    def public_summary(self) -> dict[str, object]:
        """Non-secret configuration, safe to expose via /api/meta and logs."""
        return {
            "environment": self.environment.value,
            "web_research_provider": self.web_research_provider,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "job_queue_provider": self.job_queue_provider,
            "persistence_provider": self.persistence_provider,
            "storage_provider": self.storage_provider,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
