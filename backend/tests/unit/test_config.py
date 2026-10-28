import pytest
from pydantic import ValidationError

from clauselens.domain.errors import ConfigurationError
from clauselens.domain.models import Criterion
from tests.conftest import make_settings

PROD_OK = {
    "environment": "production", "web_research_provider": "tinyfish", "llm_provider": "ollama",
    "job_queue_provider": "celery", "database_url": "postgresql+psycopg://u:p@db/x",
    "cors_origins": "https://clauselens.example",
}


def test_valid_production_config() -> None:
    s = make_settings(**PROD_OK)
    assert s.is_production
    assert s.cors_origins == ["https://clauselens.example"]


@pytest.mark.parametrize("override,needle", [
    ({"web_research_provider": "fixture"}, "WEB_RESEARCH_PROVIDER=fixture"),
    ({"llm_provider": "fixture"}, "LLM_PROVIDER=fixture"),
    ({"job_queue_provider": "inline"}, "not durable"),
    ({"database_url": "sqlite:///x.db"}, "PostgreSQL"),
    ({"cors_origins": "*"}, "explicit origins"),
])
def test_production_rejects_unsafe_choices(override: dict, needle: str) -> None:
    with pytest.raises(ValidationError) as exc:
        make_settings(**{**PROD_OK, **override})
    assert needle in str(exc.value)


def test_non_durable_queue_can_be_allowed_deliberately() -> None:
    assert make_settings(**{**PROD_OK, "job_queue_provider": "inline", "allow_non_durable_queue": True})


def test_cors_parsing_formats() -> None:
    assert make_settings(cors_origins='["https://a.example","https://b.example"]').cors_origins == [
        "https://a.example", "https://b.example"]
    assert make_settings(cors_origins="https://a.example, https://b.example").cors_origins == [
        "https://a.example", "https://b.example"]


def test_output_mode_validated() -> None:
    with pytest.raises(ValidationError):
        make_settings(llm_output_mode="xml")


def test_scoring_policy_json() -> None:
    s = make_settings(scoring_policy_json='{"longest_refund_window": 5, "longest_trial": 0}')
    assert s.scoring_policy() == {Criterion.LONGEST_REFUND_WINDOW: 5.0}
    with pytest.raises(ConfigurationError):
        make_settings(scoring_policy_json='{"made_up": 1}').scoring_policy()


def test_public_summary_contains_no_secrets() -> None:
    s = make_settings(tinyfish_api_key="tf-secret", llm_api_key="ol-secret")
    assert "secret" not in str(s.public_summary())
    assert "tf-secret" not in repr(s)


def test_managed_postgres_urls_use_psycopg_driver() -> None:
    assert make_settings(database_url="postgres://u:p@h:5432/db").database_url == "postgresql+psycopg://u:p@h:5432/db"
    assert make_settings(database_url="postgresql://u:p@h/db").database_url == "postgresql+psycopg://u:p@h/db"
