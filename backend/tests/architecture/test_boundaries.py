"""Enforce the plug-and-play boundaries mechanically."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from clauselens.config import Settings
from clauselens.container import build_container
from clauselens.domain.errors import ConfigurationError
from clauselens.registry import REGISTRY, resolve
from tests.conftest import make_settings

PKG = Path(__file__).resolve().parents[2] / "clauselens"

# Third-party or adapter modules that core layers must never import.
FORBIDDEN_IN_CORE = ("httpx", "sqlalchemy", "celery", "kombu", "redis", "fastapi", "starlette", "alembic",
                     "psycopg", "clauselens.adapters", "clauselens.api", "clauselens.container",
                     "clauselens.registry", "clauselens.worker", "tinyfish", "ollama", "openai")
CORE_LAYERS = ("domain", "ports", "services")


def imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize("layer", CORE_LAYERS)
def test_core_layers_do_not_import_providers_or_frameworks(layer: str) -> None:
    offenders = []
    for path in (PKG / layer).rglob("*.py"):
        for name in imports_of(path):
            if any(name == f or name.startswith(f + ".") for f in FORBIDDEN_IN_CORE):
                offenders.append(f"{path.relative_to(PKG)} imports {name}")
    assert not offenders, "\n".join(offenders)


def test_domain_is_pure() -> None:
    """The domain may only import the standard library, pydantic and itself."""
    allowed_prefixes = ("clauselens.domain", "pydantic", "__future__")
    stdlib = set(sys.stdlib_module_names)
    for path in (PKG / "domain").rglob("*.py"):
        for name in imports_of(path):
            root = name.split(".")[0]
            assert root in stdlib or name.startswith(allowed_prefixes), f"{path.name} imports {name}"


def test_comparison_engine_runs_without_provider_modules_loaded() -> None:
    code = (
        "import sys, json\n"
        "from clauselens.domain.comparison import compare\n"
        "from clauselens.domain.aggregation import aggregate_claims\n"
        "from clauselens.services.extraction import parse_claims\n"
        "bad = [m for m in sys.modules if m.split('.')[0] in ('httpx','sqlalchemy','celery','fastapi','redis')"
        " or m.startswith('clauselens.adapters')]\n"
        "print(json.dumps(bad))\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                         cwd=PKG.parent)
    assert json.loads(out.stdout) == []


def test_api_routes_do_not_construct_providers() -> None:
    for path in (PKG / "api").rglob("*.py"):
        for name in imports_of(path):
            assert not name.startswith("clauselens.adapters"), f"{path.name} imports adapter {name}"


@pytest.mark.parametrize("kind,name", [(k, n) for k, opts in REGISTRY.items() for n in opts])
def test_every_registered_provider_is_importable(kind: str, name: str) -> None:
    assert callable(resolve(kind, name))


def test_unknown_provider_fails_clearly() -> None:
    with pytest.raises(ConfigurationError) as exc:
        resolve("llm", "does-not-exist")
    assert "Available:" in exc.value.message and "ollama" in exc.value.message


def test_misconfigured_live_provider_fails_at_startup(tmp_path) -> None:  # type: ignore[no-untyped-def]
    settings = make_settings(database_url=f"sqlite:///{tmp_path / 'x.db'}", web_research_provider="tinyfish")
    with pytest.raises(ConfigurationError) as exc:
        build_container(settings)
    assert "TINYFISH_API_KEY" in exc.value.message


def test_demo_providers_cannot_be_selected_in_production() -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, environment="production", web_research_provider="fixture", llm_provider="ollama",
                 job_queue_provider="celery", cors_origins="https://x.example")


def test_swapping_providers_needs_only_configuration(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Same business services, different adapters, selected purely by settings."""
    db = f"sqlite:///{tmp_path / 'y.db'}"
    a = build_container(make_settings(database_url=db, llm_provider="fixture"))
    b = build_container(make_settings(database_url=db, llm_provider="ollama", llm_base_url="http://localhost:11434"))
    assert type(a.service) is type(b.service)
    assert a.llm.name == "fixture" and b.llm.name == "ollama"
    c = build_container(make_settings(database_url=db, llm_provider="openai_compatible",
                                      llm_base_url="http://localhost:8000/v1"))
    assert c.llm.name == "openai_compatible"


def test_fake_providers_can_be_injected(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from tests.unit.test_extraction import ScriptedLLM

    c = build_container(make_settings(database_url=f"sqlite:///{tmp_path / 'z.db'}"), llm=ScriptedLLM())
    assert c.service.llm.name == "scripted"
