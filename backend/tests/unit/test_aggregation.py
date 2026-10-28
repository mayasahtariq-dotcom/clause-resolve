from decimal import Decimal

from clauselens.domain.aggregation import aggregate_claims
from clauselens.domain.models import Claim, VerificationStatus
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
from tests.conftest import source

S1 = source("S1", "Refunds are available within 14 days of purchase. There is no cancellation fee. "
                   "Cancel online in your account settings. Bundles are non-refundable.")
S2 = source("S2", "Our FAQ: refunds are available within 30 days of purchase. You can also cancel by phone. "
                   "Gift cards are non-refundable. Additional charges may apply when cancelling.")
META = {"provider": "test", "model": "m", "prompt_version": "v"}


def days(n: int) -> PolicyValue:
    return PolicyValue(duration=Duration(value=Decimal(n), unit=DurationUnit.DAY))


def agg(*claims: Claim, analysed: bool = True):  # type: ignore[no-untyped-def]
    return aggregate_claims(claims, [S1, S2], extraction_meta=META, analysed=analysed)


def test_single_verified_claim_is_found() -> None:
    f = agg(Claim(field=PolicyField.REFUND_WINDOW, source_key="S1",
                  quote="Refunds are available within 14 days of purchase.", value=days(14)))[PolicyField.REFUND_WINDOW]
    assert f.status is FieldStatus.FOUND
    assert f.value == days(14)
    assert f.evidence[0].verification is VerificationStatus.VERIFIED
    assert f.evidence[0].source_url == S1.url
    assert f.evidence[0].retrieved_at == S1.retrieved_at
    assert f.evidence[0].extraction == META


def test_disagreeing_sources_are_contradictory() -> None:
    f = agg(
        Claim(field=PolicyField.REFUND_WINDOW, source_key="S1", quote="available within 14 days of purchase",
              value=days(14)),
        Claim(field=PolicyField.REFUND_WINDOW, source_key="S2", quote="available within 30 days of purchase",
              value=days(30)),
    )[PolicyField.REFUND_WINDOW]
    assert f.status is FieldStatus.CONTRADICTORY
    assert {v.duration.days for v in f.conflicting_values} == {Decimal(14), Decimal(30)}  # type: ignore[union-attr]
    assert len(f.evidence) == 2


def test_equivalent_units_do_not_conflict() -> None:
    two_weeks = PolicyValue(duration=Duration(value=Decimal(2), unit=DurationUnit.WEEK))
    f = agg(
        Claim(field=PolicyField.REFUND_WINDOW, source_key="S1", quote="available within 14 days of purchase",
              value=days(14)),
        Claim(field=PolicyField.REFUND_WINDOW, source_key="S2", quote="refunds are available within 30 days",
              value=two_weeks),
    )[PolicyField.REFUND_WINDOW]
    assert f.status is FieldStatus.FOUND


def test_hallucinated_quote_is_unverified_not_found() -> None:
    f = agg(Claim(field=PolicyField.TRIAL_DURATION, source_key="S1", quote="Enjoy a 60-day free trial on us.",
                  value=days(60)))[PolicyField.TRIAL_DURATION]
    assert f.status is FieldStatus.UNVERIFIED
    assert f.evidence[0].verification is VerificationStatus.NOT_IN_SOURCE


def test_unknown_source_key_is_source_missing() -> None:
    f = agg(Claim(field=PolicyField.TRIAL_DURATION, source_key="S7", quote="Refunds are available within 14",
                  value=days(14)))[PolicyField.TRIAL_DURATION]
    assert f.status is FieldStatus.UNVERIFIED
    assert f.evidence[0].verification is VerificationStatus.SOURCE_MISSING


def test_ambiguous_clause() -> None:
    f = agg(Claim(field=PolicyField.CANCELLATION_FEE, source_key="S2",
                  quote="Additional charges may apply when cancelling.", value=PolicyValue(), ambiguous=True)
            )[PolicyField.CANCELLATION_FEE]
    assert f.status is FieldStatus.AMBIGUOUS
    assert f.value is None


def test_explicit_zero_fee_found_but_omitted_fee_is_not_zero() -> None:
    findings = agg(Claim(field=PolicyField.CANCELLATION_FEE, source_key="S1", quote="There is no cancellation fee.",
                         value=PolicyValue(fee=Fee(kind=FeeKind.NONE))))
    assert findings[PolicyField.CANCELLATION_FEE].status is FieldStatus.FOUND
    assert findings[PolicyField.CANCELLATION_FEE].value.fee.is_zero()  # type: ignore[union-attr]
    assert findings[PolicyField.RESTOCKING_FEE].status is FieldStatus.NOT_FOUND
    assert findings[PolicyField.RESTOCKING_FEE].value is None


def test_unanalysed_vendor_fields_are_unknown() -> None:
    findings = agg(analysed=False)
    assert all(f.status is FieldStatus.UNKNOWN for f in findings.values())


def test_lists_and_channels_merge_across_sources() -> None:
    findings = agg(
        Claim(field=PolicyField.NON_REFUNDABLE_ITEMS, source_key="S1", quote="Bundles are non-refundable.",
              value=PolicyValue(items=("Bundles",))),
        Claim(field=PolicyField.NON_REFUNDABLE_ITEMS, source_key="S2", quote="Gift cards are non-refundable.",
              value=PolicyValue(items=("Gift cards", "bundles"))),
        Claim(field=PolicyField.CANCELLATION_METHOD, source_key="S1", quote="Cancel online in your account settings.",
              value=PolicyValue(channels=(Channel.ONLINE,))),
        Claim(field=PolicyField.CANCELLATION_METHOD, source_key="S2", quote="You can also cancel by phone.",
              value=PolicyValue(channels=(Channel.PHONE,))),
    )
    assert findings[PolicyField.NON_REFUNDABLE_ITEMS].value.items == ("Bundles", "Gift cards")  # type: ignore[union-attr]
    assert findings[PolicyField.CANCELLATION_METHOD].value.channels == (Channel.ONLINE, Channel.PHONE)  # type: ignore[union-attr]
    assert findings[PolicyField.CANCELLATION_METHOD].status is FieldStatus.FOUND


def test_every_field_has_a_finding() -> None:
    assert set(agg()) == set(PolicyField)
