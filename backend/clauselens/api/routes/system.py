from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, PlainTextResponse

from clauselens.api.deps import get_container
from clauselens.container import Container
from clauselens.domain.comparison import CRITERION_LABELS, DEFAULT_SCORING_POLICY
from clauselens.domain.errors import ClauseLensError
from clauselens.domain.policy import FIELD_SPECS
from clauselens.observability import metrics

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness: the process is up. Does not touch dependencies."""
    return {"status": "ok"}


@router.get("/ready")
def ready(c: Container = Depends(get_container)) -> JSONResponse:
    """Readiness: database reachable, job queue reachable, providers configured."""
    checks: dict[str, dict[str, str]] = {}
    for name, fn in (("database", c.repository.ping), ("job_queue", c.jobs.health_check),
                     ("research_provider", c.research.health_check), ("llm_provider", c.llm.health_check)):
        try:
            fn()
            checks[name] = {"status": "ok"}
        except ClauseLensError as exc:
            checks[name] = {"status": "error", "message": exc.message, "category": exc.category.value}
        except Exception as exc:  # noqa: BLE001 - reported, not hidden
            checks[name] = {"status": "error", "message": type(exc).__name__}
    ok = all(v["status"] == "ok" for v in checks.values())
    return JSONResponse({"status": "ready" if ok else "not_ready", "checks": checks}, status_code=200 if ok else 503)


@router.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics() -> str:
    return metrics.prometheus()


@router.get("/api/meta")
def meta(c: Container = Depends(get_container)) -> dict[str, object]:
    demo = c.service.is_demo
    return {
        "demo_mode": demo,
        # Only demo providers expose sample vendors; real providers have none.
        "demo_vendors": list(getattr(c.research, "demo_vendors", list)()),
        "providers": {**c.settings.public_summary(), "llm_model": c.llm.model, "job_queue_durable": c.jobs.durable},
        "max_vendors": c.settings.max_vendors_per_investigation,
        "fields": [{"key": s.key.value, "label": s.label, "kind": s.kind.value, "description": s.description}
                   for s in FIELD_SPECS.values()],
        "criteria": [{"key": k.value, "label": v,
                      "default_weight": (c.settings.scoring_policy() or DEFAULT_SCORING_POLICY).get(k, 0.0)}
                     for k, v in CRITERION_LABELS.items()],
    }
