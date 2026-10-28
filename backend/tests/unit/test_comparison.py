import uuid
from decimal import Decimal

from clauselens.domain.comparison import compare
from clauselens.domain.models import (
    Criterion,
    Evidence,
    Finding,
    Priority,
    Vendor,
    VendorPolicy,
    VerificationStatus,
)
from clauselens.domain.policy import (
    Channel,
    Duration,
    DurationUnit,
    Fee,
    FeeKind,
    FieldStatus,
    PolicyField,
    PolicyValue,
)


def vendor(name: str) -> Vendor:
    return Vendor(id=uuid.uuid5(uuid.NAMESPACE_DNS, name), name=name)


def found(field: PolicyField, value: PolicyValue) -> Finding:
    ev = Evidence(id=uuid.uuid4(), field=field, source_key="S1", source_url="https://x.example", quote="q" * 20,
                  retrieved_at=None, verification=VerificationStatus.VERIFIED)
    return Finding(field=field, status=FieldStatus.FOUND, value=value, evidence=[ev])


def policy(name: str, *findings: Finding, failed: bool = False) -> VendorPolicy:
    fs = {f: Finding(field=f, status=FieldStatus.NOT_FOUND) for f in PolicyField}
    fs.update({f.field: f for f in findings})
    return VendorPolicy(vendor=vendor(name), findings=fs, failed=failed, error="boom" if failed else None)


def refund(n: int) -> Finding:
    return found(PolicyField.REFUND_WINDOW, PolicyValue(duration=Duration(value=Decimal(n), unit=DurationUnit.DAY)))


def fee(kind: FeeKind, amount: int | None = None, percent: int | None = None) -> Finding:
    return found(PolicyField.CANCELLATION_FEE, PolicyValue(fee=Fee(kind=kind, amount=amount, currency="USD" if amount is not None else None, percent=percent)))


LONGEST = [Priority(criterion=Criterion.LONGEST_REFUND_WINDOW)]


def test_longest_refund_window_priority_is_applied_explicitly() -> None:
    a, b, c = policy("A", refund(14)), policy("B", refund(30)), policy("C", refund(14))
    report = compare([a, b, c], LONGEST)
    assert report.recommendation.vendor_id == b.vendor.id
    assert report.priorities == LONGEST
    best = [cell for cell in report.cells if cell.field is PolicyField.REFUND_WINDOW and cell.is_best]
    assert [cell.vendor_id for cell in best] == [b.vendor.id]
    assert "Longest refund window: B best" in report.recommendation.rationale[0]


def test_unknown_value_is_never_treated_as_best() -> None:
    a, b = policy("A", refund(14)), policy("B")  # B: refund window not stated
    report = compare([a, b], LONGEST)
    assert report.criteria[0].scores[str(b.vendor.id)] is None
    assert report.recommendation.vendor_id == a.vendor.id
    assert any("B: Refund window is not stated" in m for m in report.missing)


def test_tie_produces_no_recommendation() -> None:
    report = compare([policy("A", refund(30)), policy("B", refund(30))], LONGEST)
    assert report.recommendation.vendor_id is None
    assert report.recommendation.headline.startswith("No clear winner")


def test_no_verified_data_means_no_recommendation() -> None:
    report = compare([policy("A"), policy("B"), policy("C")], LONGEST)
    assert report.recommendation.vendor_id is None
    assert report.recommendation.confidence == "insufficient"


def test_low_coverage_blocks_recommendation() -> None:
    priorities = [Priority(criterion=Criterion.LONGEST_REFUND_WINDOW, weight=1),
                  Priority(criterion=Criterion.EASIEST_CANCELLATION, weight=3)]
    mail = found(PolicyField.CANCELLATION_METHOD, PolicyValue(channels=(Channel.MAIL,)))
    a, b, c = policy("A", refund(30)), policy("B", refund(10), mail), policy("C", mail)
    report = compare([a, b, c], priorities)
    # A scores highest (0.25) but only a quarter of the weight is backed by evidence.
    assert max(report.recommendation.totals, key=report.recommendation.totals.get) == str(a.vendor.id)
    assert report.recommendation.coverage[str(a.vendor.id)] == 0.25
    assert report.recommendation.vendor_id is None
    assert report.recommendation.confidence == "insufficient"


def test_failed_vendors_are_excluded_and_reported() -> None:
    ok, bad = policy("A", refund(14)), policy("B", refund(90), failed=True)
    report = compare([ok, bad], LONGEST)
    assert report.recommendation.vendor_id == ok.vendor.id
    assert str(bad.vendor.id) not in report.recommendation.totals
    assert any("investigation failed" in m for m in report.missing)


def test_stated_zero_fee_beats_nonzero_and_unknown_fee_is_unknown() -> None:
    pri = [Priority(criterion=Criterion.LOWEST_CANCELLATION_FEE)]
    zero, paid, unknown = policy("Zero", fee(FeeKind.NONE)), policy("Paid", fee(FeeKind.FIXED, amount=25)), policy("Unknown")
    report = compare([zero, paid, unknown], pri)
    scores = report.criteria[0].scores
    assert scores[str(zero.vendor.id)] == 1.0
    assert scores[str(paid.vendor.id)] == 0.5
    assert scores[str(unknown.vendor.id)] is None
    assert report.recommendation.vendor_id == zero.vendor.id


def test_incomparable_fee_kinds_get_neutral_score() -> None:
    pri = [Priority(criterion=Criterion.LOWEST_CANCELLATION_FEE)]
    report = compare([policy("Pct", fee(FeeKind.PERCENT, percent=10)), policy("Fixed", fee(FeeKind.FIXED, amount=5))], pri)
    assert set(report.criteria[0].scores.values()) == {0.25}


def test_contradictions_are_surfaced_and_not_scored() -> None:
    contra = Finding(field=PolicyField.REFUND_WINDOW, status=FieldStatus.CONTRADICTORY, conflicting_values=[
        PolicyValue(duration=Duration(value=Decimal(14), unit=DurationUnit.DAY)),
        PolicyValue(duration=Duration(value=Decimal(30), unit=DurationUnit.DAY))])
    a, b = policy("A", contra), policy("B", refund(10))
    report = compare([a, b], LONGEST)
    assert report.contradictions == ["A: Refund window: Conflicting: 14 days vs 30 days."]
    assert report.criteria[0].scores[str(a.vendor.id)] is None


def test_single_known_vendor_is_not_called_best() -> None:
    report = compare([policy("A", refund(10)), policy("B")], LONGEST)
    assert "only A has verified data" in report.recommendation.rationale[0]
    assert not any(c.is_best for c in report.cells)


def test_default_policy_used_without_priorities() -> None:
    report = compare([policy("A", refund(10)), policy("B", refund(20))])
    assert {p.criterion for p in report.priorities} >= {Criterion.LONGEST_REFUND_WINDOW, Criterion.EASIEST_CANCELLATION}
    assert report.scoring_policy["longest_refund_window"] == 3.0


def test_comparison_is_deterministic() -> None:
    ps = [policy("A", refund(10), fee(FeeKind.NONE)), policy("B", refund(20)), policy("C", fee(FeeKind.FIXED, amount=3))]
    assert compare(ps).model_dump() == compare(ps).model_dump()


def test_every_vendor_field_has_a_cell() -> None:
    report = compare([policy("A"), policy("B"), policy("C")], LONGEST)
    assert len(report.cells) == 3 * len(PolicyField)
    assert {c.display for c in report.cells} == {"Not stated"}
