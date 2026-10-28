"""Provider registry: configuration names -> adapter factories.

Adding a provider = write an adapter module exposing a factory, add one line
here, run the shared contract tests, then change configuration. Factories are
imported lazily so unused adapters (and their dependencies) are never loaded.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

from clauselens.domain.errors import ConfigurationError

REGISTRY: dict[str, dict[str, str]] = {
    "research": {
        "tinyfish": "clauselens.adapters.research.tinyfish:create",
        "fixture": "clauselens.adapters.research.fixture:create",
    },
    "llm": {
        "ollama": "clauselens.adapters.llm.ollama:create",
        "openai_compatible": "clauselens.adapters.llm.openai_compatible:create",
        "fixture": "clauselens.adapters.llm.fixture:create",
    },
    "persistence": {
        "sqlalchemy": "clauselens.adapters.persistence.sqlalchemy_repository:create",
        "postgres": "clauselens.adapters.persistence.sqlalchemy_repository:create",
    },
    "jobs": {
        "celery": "clauselens.adapters.jobs.celery_queue:create",
        "inline": "clauselens.adapters.jobs.local:create_inline",
        "sync": "clauselens.adapters.jobs.local:create_sync",
    },
    "storage": {
        "local": "clauselens.adapters.storage.local:create_local",
        "none": "clauselens.adapters.storage.local:create_null",
    },
}


def resolve(kind: str, name: str) -> Callable[..., Any]:
    options = REGISTRY.get(kind, {})
    target = options.get(name)
    if target is None:
        raise ConfigurationError(
            f"Unknown {kind} provider '{name}'. Available: {', '.join(sorted(options)) or 'none'}", provider=name)
    module_name, attr = target.split(":")
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise ConfigurationError(
            f"{kind} provider '{name}' is registered but its dependencies are not installed: {exc}",
            provider=name) from exc
    return getattr(module, attr)
