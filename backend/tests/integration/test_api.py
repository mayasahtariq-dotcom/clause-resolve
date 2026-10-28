"""End-to-end API tests with deterministic fixture providers and synchronous jobs."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from clauselens.adapters.persistence.models import Base
from clauselens.adapters.persistence.sqlalchemy_repository import SqlAlchemyRepository, create_db_engine
from clauselens.api.app import create_app
from clauselens.container import build_container
from tests.conftest import make_settings

THREE = [{"name": "StudyNest"}, {"name": "CourseCove"}, {"name": "SkillForge"}]


@pytest.fixture
def client(tmp_path) -> TestClient:  # type: ignore[no-untyped-def]
    settings = make_settings(database_url=f"sqlite:///{tmp_path / 'api.db'}",
                             cors_origins="https://app.example", rate_limit_investigations_per_minute=1000)
    engine = create_db_engine(settings)
    Base.metadata.create_all(engine)
    container = build_container(settings, repository=SqlAlchemyRepository(engine))
    return TestClient(create_app(settings, container))


def run(client: TestClient, vendors: list[dict], **extra: object) -> dict:
    r = client.post("/api/investigations", json={"vendors": vendors, **extra})
    assert r.status_code == 202, r.text
    return client.get(f"/api/investigations/{r.json()['id']}").json()


def cells(report: dict) -> dict[tuple[str, str], dict]:
    names = {v["id"]: v["name"] for v in report["vendors"]}
    return {(names[c["vendor_id"]], c["field"]): c for c in report["cells"]}


def test_full_lifecycle_three_vendors(client: TestClient) -> None:
    inv = run(client, THREE)
    assert inv["status"] == "completed"
    assert inv["is_demo"] is True
    assert [v["status"] for v in inv["vendors"]] == ["completed"] * 3
    assert len(inv["sources"]) == 6 and all(s["url"].startswith("https://") for s in inv["sources"])
    report = client.get(f"/api/reports/{inv['report_id']}").json()
    assert report["is_demo"] and report["disclaimer"]
    c = cells(report)
    assert c[("StudyNest", "refund_window")]["display"] == "30 days"
    assert c[("StudyNest", "cancellation_fee")]["normalized"]["fee_is_zero"] is True
    assert c[("CourseCove", "cancellation_fee")]["status"] == "not_found"  # omitted fee is NOT zero
    assert c[("CourseCove", "refund_window")]["status"] == "contradictory"
    assert c[("CourseCove", "trial_duration")]["status"] == "unverified"  # hallucinated quote caught
    assert c[("SkillForge", "renewal_behavior")]["status"] == "not_found"  # cited non-existent source
    assert report["recommendation"]["vendor_id"] == next(v["id"] for v in report["vendors"] if v["name"] == "StudyNest")
    assert report["contradictions"] == ["CourseCove: Refund window: Conflicting: 14 days vs 30 days."]
    assert report["explanation_status"] == "generated"


def test_prompt_injection_does_not_change_values(client: TestClient) -> None:
    inv = run(client, [{"name": "SkillForge"}, {"name": "StudyNest"}])
    report = client.get(f"/api/reports/{inv['report_id']}").json()
    assert cells(report)[("SkillForge", "refund_window")]["display"] == "7 days"
    assert any(s["injection_suspected"] for s in inv["sources"])
    events = client.get(f"/api/investigations/{inv['id']}/events", params={"stream": "false"}).json()
    assert any("instructions to an AI" in e["message"] for e in events)


def test_every_found_claim_links_to_verified_evidence(client: TestClient) -> None:
    inv = run(client, THREE)
    report = client.get(f"/api/reports/{inv['report_id']}").json()
    evidence = {e["id"]: e for e in client.get(f"/api/reports/{inv['report_id']}/evidence").json()["items"]}
    for cell in report["cells"]:
        if cell["status"] == "found":
            assert cell["evidence_ids"], cell
            linked = [evidence[i] for i in cell["evidence_ids"]]
            assert any(e["verification"] == "verified" for e in linked)
            for e in linked:
                assert e["source_url"].startswith("https://") and e["quote"] and e["retrieved_at"]
                assert e["extraction"]["prompt_version"] == "extract-v1"


def test_partial_failure_malformed_model_output(client: TestClient) -> None:
    inv = run(client, [*THREE[:2], {"name": "GarbledAI"}])
    assert inv["status"] == "partial"
    garbled = next(v for v in inv["vendors"] if v["name"] == "GarbledAI")
    assert garbled["status"] == "failed" and garbled["error"]["category"] == "malformed_output"
    report = client.get(f"/api/reports/{inv['report_id']}").json()
    assert all(c["status"] == "unknown" for (n, _), c in cells(report).items() if n == "GarbledAI")
    assert any("GarbledAI: investigation failed" in m for m in report["missing"])


def test_inaccessible_pages_and_unknown_vendor(client: TestClient) -> None:
    inv = run(client, [{"name": "StudyNest"}, {"name": "OfflineCo"}, {"name": "Not A Fixture"}])
    assert inv["status"] == "partial"
    by = {v["name"]: v for v in inv["vendors"]}
    assert by["OfflineCo"]["error"]["message"] == "No policy pages could be retrieved for this vendor"
    assert by["Not A Fixture"]["error"]["category"] == "not_found"


def test_all_vendors_failing_yields_failed_without_report(client: TestClient) -> None:
    inv = run(client, [{"name": "OfflineCo"}, {"name": "GarbledAI"}])
    assert inv["status"] == "failed" and inv["report_id"] is None
    assert "Every vendor investigation failed" in inv["error"]["message"]


def test_events_are_ordered_and_reflect_real_stages(client: TestClient) -> None:
    inv = run(client, THREE)
    events = client.get(f"/api/investigations/{inv['id']}/events", params={"stream": "false"}).json()
    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs) == list(range(1, len(seqs) + 1))
    stages = [e["stage"] for e in events]
    for stage in ("queued", "running", "research", "extracting", "validating", "comparing", "completed"):
        assert stage in stages
    assert stages.index("extracting") < stages.index("comparing") < stages.index("completed")
    later = client.get(f"/api/investigations/{inv['id']}/events", params={"stream": "false", "after": seqs[-2]}).json()
    assert [e["seq"] for e in later] == [seqs[-1]]


def test_sse_stream_replays_and_terminates(client: TestClient) -> None:
    inv = run(client, THREE[:2])
    with client.stream("GET", f"/api/investigations/{inv['id']}/events") as resp:
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = "".join(resp.iter_text())
    assert "event: progress" in body and "event: status" in body
    assert '"is_terminal": true' in body
    with client.stream("GET", f"/api/investigations/{inv['id']}/events", headers={"Last-Event-ID": "999"}) as resp:
        tail = "".join(resp.iter_text())
    assert "event: progress" not in tail


def test_recompare_with_new_priorities_without_research(client: TestClient) -> None:
    inv = run(client, THREE)
    vendor_ids = [v["id"] for v in inv["vendors"]]
    r = client.post("/api/comparisons", json={"vendor_ids": vendor_ids,
                                              "priorities": [{"criterion": "lowest_cancellation_fee", "weight": 1}]})
    assert r.status_code == 201, r.text
    report = r.json()
    assert report["investigation_id"] is None and len(report["snapshot_ids"]) == 3
    assert report["explanation_status"] == "not_requested"
    assert report["priorities"] == [{"criterion": "lowest_cancellation_fee", "weight": 1.0}]
    assert client.get(f"/api/reports/{report['id']}").json()["recommendation"] == report["recommendation"]


def test_vendor_policy_history(client: TestClient) -> None:
    first = run(client, THREE[:2])
    run(client, THREE[:2])
    vid = first["vendors"][0]["id"]
    history = client.get(f"/api/vendors/{vid}/policies", params={"limit": 1}).json()
    assert history["total"] == 2 and len(history["items"]) == 1
    assert history["vendor_name"] == "StudyNest" and history["domain"] == "studynest.example"
    assert history["items"][0]["findings"]["refund_window"]["status"] == "found"


def test_list_investigations_paginates(client: TestClient) -> None:
    for _ in range(3):
        run(client, THREE[:2])
    page = client.get("/api/investigations", params={"limit": 2, "offset": 1}).json()
    assert page["total"] == 3 and len(page["items"]) == 2


def test_idempotency_key_returns_same_investigation(client: TestClient) -> None:
    h = {"Idempotency-Key": "abc-123"}
    a = client.post("/api/investigations", json={"vendors": THREE[:2]}, headers=h).json()
    b = client.post("/api/investigations", json={"vendors": THREE[:2]}, headers=h).json()
    assert a["id"] == b["id"]
    events = client.get(f"/api/investigations/{a['id']}/events", params={"stream": "false"}).json()
    assert sum(e["stage"] == "queued" for e in events) == 1


@pytest.mark.parametrize("body,needle", [
    ({"vendors": [{"name": "Only"}]}, "at least 2"),
    ({"vendors": [{"name": "A"}, {"name": "a"}]}, "unique"),
    ({"vendors": [{"name": "A", "domain": "localhost"}, {"name": "B"}]}, "not a public website"),
    ({"vendors": [{"name": "A", "domain": "http://10.0.0.1"}, {"name": "B"}]}, "IP addresses"),
    ({"vendors": [{"name": "A"}, {"name": "B"}], "priorities": [{"criterion": "nonsense"}]}, "criterion"),
    ({"vendors": [{"name": "  "}, {"name": "B"}]}, "empty"),
])
def test_validation_errors(client: TestClient, body: dict, needle: str) -> None:
    r = client.post("/api/investigations", json=body)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_request"
    assert needle in r.text


def test_too_many_vendors(client: TestClient) -> None:
    r = client.post("/api/investigations", json={"vendors": [{"name": f"V{i}"} for i in range(6)]})
    assert r.status_code == 422 and "At most 5" in r.json()["error"]["message"]


def test_oversized_body_rejected(client: TestClient) -> None:
    r = client.post("/api/investigations", content=b"x" * 70_000, headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_not_found_shapes(client: TestClient) -> None:
    zero = "00000000-0000-0000-0000-000000000000"
    for path in (f"/api/investigations/{zero}", f"/api/reports/{zero}", f"/api/reports/{zero}/evidence",
                 f"/api/vendors/{zero}/policies", f"/api/investigations/{zero}/events"):
        r = client.get(path)
        assert r.status_code == 404 and r.json()["error"]["code"] == "not_found", path


def test_system_endpoints(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    ready = client.get("/ready")
    assert ready.status_code == 200 and ready.json()["checks"]["database"]["status"] == "ok"
    meta = client.get("/api/meta").json()
    assert meta["demo_mode"] is True and len(meta["demo_vendors"]) == 5
    assert {f["key"] for f in meta["fields"]} >= {"refund_window", "cancellation_fee"}
    assert "llm_api_key" not in str(meta)
    run(client, THREE[:2])
    assert "clauselens_investigations_total" in client.get("/metrics").text


def test_cors_allows_only_configured_origin(client: TestClient) -> None:
    ok = client.options("/api/meta", headers={"Origin": "https://app.example", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "https://app.example"
    bad = client.options("/api/meta", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers


def test_security_headers(client: TestClient) -> None:
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-request-id"]


def test_rate_limit(tmp_path) -> None:  # type: ignore[no-untyped-def]
    settings = make_settings(database_url=f"sqlite:///{tmp_path / 'rl.db'}", rate_limit_investigations_per_minute=2)
    Base.metadata.create_all(create_db_engine(settings))
    c = TestClient(create_app(settings, build_container(settings)))
    codes = [c.post("/api/investigations", json={"vendors": THREE[:2]}).status_code for _ in range(3)]
    assert codes == [202, 202, 429]
