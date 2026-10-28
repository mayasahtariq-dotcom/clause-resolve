"""Repository behaviour on SQLite and on PostgreSQL (schema created by Alembic migrations)."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from clauselens.adapters.persistence.sqlalchemy_repository import SqlAlchemyRepository
from clauselens.domain.aggregation import aggregate_claims
from clauselens.domain.comparison import compare
from clauselens.domain.models import (
    Claim,
    InvestigationStatus,
    Priority,
    VendorInput,
    VendorRunStatus,
)
from clauselens.domain.policy import Duration, DurationUnit, FieldStatus, PolicyField, PolicyValue
from tests.conftest import source


def create(repo: SqlAlchemyRepository, *names: str):  # type: ignore[no-untyped-def]
    record, created = repo.create_investigation([VendorInput(name=n) for n in names], [Priority(criterion="longest_refund_window")],
                                                providers={"research": "t"}, is_demo=False)
    assert created
    return record


def test_create_and_reuse_vendors(repo: SqlAlchemyRepository) -> None:
    a = create(repo, "Acme", "Beta")
    b = create(repo, "ACME", "Gamma")
    assert a.vendors[0].vendor.id == b.vendors[0].vendor.id  # same vendor, name-normalised
    assert a.status is InvestigationStatus.QUEUED and a.vendors[0].status is VendorRunStatus.PENDING


def test_claim_semantics(repo: SqlAlchemyRepository) -> None:
    inv = create(repo, "Acme", "Beta")
    assert repo.claim_investigation(inv.id, worker_id="w1", lease_seconds=600)
    assert not repo.claim_investigation(inv.id, worker_id="w2", lease_seconds=600), "leased elsewhere"
    assert repo.claim_investigation(inv.id, worker_id="w1", lease_seconds=600), "same worker may resume (retry)"
    repo.set_status(inv.id, InvestigationStatus.COMPLETED)
    assert not repo.claim_investigation(inv.id, worker_id="w1", lease_seconds=600), "terminal is never reclaimed"


def test_stale_lease_can_be_reclaimed_after_crash(repo: SqlAlchemyRepository) -> None:
    inv = create(repo, "Acme", "Beta")
    assert repo.claim_investigation(inv.id, worker_id="crashed", lease_seconds=-1)  # already expired
    assert repo.claim_investigation(inv.id, worker_id="w2", lease_seconds=600)


def test_concurrent_events_get_unique_ordered_seq(repo: SqlAlchemyRepository) -> None:
    inv = create(repo, "Acme", "Beta")
    barrier = threading.Barrier(4)

    def emit(i: int) -> None:
        barrier.wait()
        for j in range(5):
            repo.add_event(inv.id, stage="research", message=f"{i}-{j}")

    with ThreadPoolExecutor(4) as pool:
        list(pool.map(emit, range(4)))
    events = repo.list_events(inv.id)
    assert [e.seq for e in events] == list(range(1, 21))


def test_snapshot_and_report_roundtrip(repo: SqlAlchemyRepository) -> None:
    inv = create(repo, "Acme", "Beta")
    sources = [source("S1", "Refunds are available within 14 days of purchase.")]
    findings_by_vendor = {}
    for run in inv.vendors:
        repo.save_sources(inv.id, run.vendor.id, sources)
        repo.save_sources(inv.id, run.vendor.id, sources)  # idempotent on content hash
        claims = [Claim(field=PolicyField.REFUND_WINDOW, source_key="S1", quote="available within 14 days of purchase",
                        value=PolicyValue(duration=Duration(value=14, unit=DurationUnit.DAY)))]
        findings = aggregate_claims(claims, sources, extraction_meta={"provider": "t"}, analysed=True)
        snapshot_id, saved = repo.save_snapshot(inv.id, run.vendor.id, findings, extraction_meta={"provider": "t"},
                                                warnings=["w"])
        assert saved[PolicyField.REFUND_WINDOW].evidence[0].id is not None
        findings_by_vendor[run.vendor.id] = snapshot_id
    assert len(repo.list_sources(inv.id)) == 2

    policies = [repo.load_policy(sid) for sid in findings_by_vendor.values()]
    assert all(p is not None for p in policies)
    assert policies[0].findings[PolicyField.REFUND_WINDOW].status is FieldStatus.FOUND  # type: ignore[union-attr]
    assert policies[0].findings[PolicyField.REFUND_WINDOW].value.duration.days == 14  # type: ignore[union-attr]

    report = compare(policies, [Priority(criterion="longest_refund_window")])  # type: ignore[arg-type]
    report = report.model_copy(update={"investigation_id": inv.id})
    saved_report = repo.save_report(report)
    repo.set_report(inv.id, saved_report.id)  # type: ignore[arg-type]
    loaded = repo.get_report(saved_report.id)  # type: ignore[arg-type]
    assert loaded is not None
    assert loaded.model_dump(exclude={"created_at"}) == saved_report.model_dump(exclude={"created_at"})
    assert repo.get_investigation(inv.id).report_id == saved_report.id  # type: ignore[union-attr]
    evidence = repo.list_report_evidence(saved_report.id)  # type: ignore[arg-type]
    assert len(evidence) == 2 and {e.vendor_name for e in evidence} == {"Acme", "Beta"}
    assert repo.latest_snapshot_ids([r.vendor.id for r in inv.vendors]) == findings_by_vendor


def test_retried_snapshot_replaces_previous(repo: SqlAlchemyRepository) -> None:
    inv = create(repo, "Acme", "Beta")
    vid = inv.vendors[0].vendor.id
    findings = aggregate_claims([], [], extraction_meta={}, analysed=True)
    first, _ = repo.save_snapshot(inv.id, vid, findings, extraction_meta={}, warnings=[])
    second, _ = repo.save_snapshot(inv.id, vid, findings, extraction_meta={}, warnings=[])
    assert repo.load_policy(first) is None and repo.load_policy(second) is not None
    items, total = repo.list_snapshots(vid, limit=10, offset=0)
    assert total == 1


def test_idempotency_key(repo: SqlAlchemyRepository) -> None:
    kwargs = {"providers": {}, "is_demo": False, "idempotency_key": "k1"}
    a, created_a = repo.create_investigation([VendorInput(name="A"), VendorInput(name="B")], [], **kwargs)
    b, created_b = repo.create_investigation([VendorInput(name="A"), VendorInput(name="B")], [], **kwargs)
    assert created_a and not created_b and a.id == b.id
