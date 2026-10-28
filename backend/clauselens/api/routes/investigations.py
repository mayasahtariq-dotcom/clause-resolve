from __future__ import annotations

import json
import time
from collections.abc import Iterator
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from clauselens.api.deps import get_container, rate_limit_creates
from clauselens.api.schemas import InvestigationCreate, InvestigationOut, InvestigationSummary, Page
from clauselens.container import Container
from clauselens.domain.models import InvestigationEvent

router = APIRouter(prefix="/api/investigations", tags=["investigations"])

SSE_POLL_SECONDS = 1.0
SSE_HEARTBEAT_SECONDS = 15.0
SSE_MAX_SECONDS = 30 * 60


def _record_or_404(c: Container, investigation_id: UUID):  # type: ignore[no-untyped-def]
    record = c.repository.get_investigation(investigation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return record


@router.post("", status_code=202, response_model=InvestigationOut, dependencies=[Depends(rate_limit_creates)])
def create_investigation(body: InvestigationCreate, c: Container = Depends(get_container),
                         idempotency_key: str | None = Header(default=None, max_length=100)) -> InvestigationOut:
    if len(body.vendors) > c.settings.max_vendors_per_investigation:
        raise HTTPException(status_code=422,
                            detail=f"At most {c.settings.max_vendors_per_investigation} vendors per investigation")
    record = c.submitter.submit(body.vendor_inputs(), body.priorities, idempotency_key=idempotency_key)
    return InvestigationOut.from_record(record)


@router.get("", response_model=Page[InvestigationSummary])
def list_investigations(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                        c: Container = Depends(get_container)) -> Page[InvestigationSummary]:
    records, total = c.repository.list_investigations(limit=limit, offset=offset)
    items = [InvestigationSummary(id=r.id, status=r.status.value, created_at=r.created_at,
                                  vendor_names=[v.vendor.name for v in r.vendors], report_id=r.report_id,
                                  is_demo=r.is_demo) for r in records]
    return Page[InvestigationSummary](items=items, total=total, limit=limit, offset=offset)


@router.get("/{investigation_id}", response_model=InvestigationOut)
def get_investigation(investigation_id: UUID, c: Container = Depends(get_container)) -> InvestigationOut:
    record = _record_or_404(c, investigation_id)
    return InvestigationOut.from_record(record, c.repository.list_sources(investigation_id))


def _sse(event: str, data: object, event_id: int | None = None) -> str:
    head = f"id: {event_id}\n" if event_id is not None else ""
    return f"{head}event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.get("/{investigation_id}/events", response_model=None)
def investigation_events(
    investigation_id: UUID,
    request: Request,
    after: int = Query(0, ge=0, description="Return events with seq greater than this"),
    stream: bool = Query(True, description="false returns a JSON list (polling fallback)"),
    last_event_id: str | None = Header(default=None),
    c: Container = Depends(get_container),
) -> StreamingResponse | list[InvestigationEvent]:
    _record_or_404(c, investigation_id)
    start_after = after
    if last_event_id and last_event_id.isdigit():
        start_after = max(start_after, int(last_event_id))
    if not stream:
        return c.repository.list_events(investigation_id, after_seq=start_after)

    def generate() -> Iterator[str]:
        cursor = start_after
        last_status = None
        started = last_beat = time.monotonic()
        yield "retry: 3000\n\n"
        while time.monotonic() - started < SSE_MAX_SECONDS:
            for ev in c.repository.list_events(investigation_id, after_seq=cursor):
                cursor = ev.seq
                yield _sse("progress", ev.model_dump(mode="json"), ev.seq)
            record = c.repository.get_investigation(investigation_id)
            if record is None:
                return
            if record.status != last_status:
                last_status = record.status
                yield _sse("status", {"status": record.status.value, "report_id": record.report_id,
                                      "is_terminal": record.status.is_terminal})
            if record.status.is_terminal:
                return
            if time.monotonic() - last_beat > SSE_HEARTBEAT_SECONDS:
                last_beat = time.monotonic()
                yield ": keep-alive\n\n"
            time.sleep(SSE_POLL_SECONDS)

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
