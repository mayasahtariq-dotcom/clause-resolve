from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from clauselens.api.deps import get_container
from clauselens.api.schemas import ComparisonCreate, EvidenceOut, VendorPoliciesOut
from clauselens.container import Container
from clauselens.domain.models import ComparisonReport

router = APIRouter(tags=["reports"])


@router.post("/api/comparisons", status_code=201, response_model=ComparisonReport)
def create_comparison(body: ComparisonCreate, c: Container = Depends(get_container)) -> ComparisonReport:
    """Re-run the deterministic comparison on stored snapshots (e.g. with new priorities). No web research."""
    if body.vendor_ids:
        latest = c.repository.latest_snapshot_ids(body.vendor_ids)
        missing = [str(v) for v in body.vendor_ids if v not in latest]
        if missing:
            raise HTTPException(status_code=404, detail=f"No policy snapshot for vendor(s): {', '.join(missing)}")
        snapshot_ids = [latest[v] for v in body.vendor_ids]
    else:
        snapshot_ids = body.snapshot_ids
    policies = []
    for sid in snapshot_ids:
        policy = c.repository.load_policy(sid)
        if policy is None:
            raise HTTPException(status_code=404, detail=f"Snapshot {sid} not found")
        policies.append(policy)
    report = c.service.build_report(policies, body.priorities, investigation_id=None, explain=body.explain)
    return c.repository.save_report(report)


@router.get("/api/reports/{report_id}", response_model=ComparisonReport)
def get_report(report_id: UUID, c: Container = Depends(get_container)) -> ComparisonReport:
    report = c.repository.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("/api/reports/{report_id}/evidence", response_model=EvidenceOut)
def get_report_evidence(report_id: UUID, c: Container = Depends(get_container)) -> EvidenceOut:
    if c.repository.get_report(report_id) is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return EvidenceOut(report_id=report_id, items=c.repository.list_report_evidence(report_id))


@router.get("/api/vendors/{vendor_id}/policies", response_model=VendorPoliciesOut)
def vendor_policies(vendor_id: UUID, limit: int = Query(10, ge=1, le=50), offset: int = Query(0, ge=0),
                    c: Container = Depends(get_container)) -> VendorPoliciesOut:
    vendor = c.repository.get_vendor(vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")
    items, total = c.repository.list_snapshots(vendor_id, limit=limit, offset=offset)
    return VendorPoliciesOut(vendor_id=vendor.id, vendor_name=vendor.name, domain=vendor.domain, items=items,
                             total=total, limit=limit, offset=offset)
