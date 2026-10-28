from decimal import Decimal

import pytest
from pydantic import ValidationError

from clauselens.domain.evidence import normalize_text, verify_quote
from clauselens.domain.models import VerificationStatus
from clauselens.domain.policy import Duration, DurationUnit, Fee, FeeKind


class TestValues:
    def test_duration_normalises_to_days(self) -> None:
        assert Duration(value=Decimal(2), unit=DurationUnit.WEEK).days == Decimal("14.00")
        assert Duration(value=Decimal(1), unit=DurationUnit.MONTH).days == Decimal("30.00")
        assert Duration(value=Decimal(1), unit=DurationUnit.YEAR).days == Decimal("365.00")
        assert Duration(value=Decimal(48), unit=DurationUnit.HOUR).days == Decimal("2.00")

    def test_duration_display(self) -> None:
        assert Duration(value=Decimal(1), unit=DurationUnit.DAY).display() == "1 day"
        assert Duration(value=Decimal("14.0"), unit=DurationUnit.DAY).display() == "14 days"

    def test_negative_duration_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Duration(value=Decimal(-1), unit=DurationUnit.DAY)

    def test_explicit_zero_fee_is_known_zero(self) -> None:
        assert Fee(kind=FeeKind.NONE).is_zero()
        assert Fee(kind=FeeKind.FIXED, amount=Decimal(0), currency="usd").is_zero()
        assert Fee(kind=FeeKind.FIXED, amount=Decimal(0), currency="usd").currency == "USD"

    def test_fixed_fee_requires_amount(self) -> None:
        with pytest.raises(ValidationError):
            Fee(kind=FeeKind.FIXED)
        with pytest.raises(ValidationError):
            Fee(kind=FeeKind.PERCENT)

    def test_percent_bounds(self) -> None:
        with pytest.raises(ValidationError):
            Fee(kind=FeeKind.PERCENT, percent=Decimal(150))


SOURCE = """# Refund Policy
You may request a **full refund** within 30 days of purchase.
Gift cards are “non-refundable” — no exceptions.
See [our terms](https://x.example/terms) for details on renewals and cancellations.
"""


class TestQuoteVerification:
    def test_exact_match(self) -> None:
        assert verify_quote("Gift cards are “non-refundable”", SOURCE) == (VerificationStatus.VERIFIED, "exact")

    def test_markdown_and_typography_are_normalised(self) -> None:
        status, method = verify_quote('You may request a full refund within 30 days of purchase.', SOURCE)
        assert status is VerificationStatus.VERIFIED and method == "normalized"
        status, _ = verify_quote('Gift cards are "non-refundable" - no exceptions.', SOURCE)
        assert status is VerificationStatus.VERIFIED

    def test_link_text_matches(self) -> None:
        assert verify_quote("See our terms for details on renewals", SOURCE)[0] is VerificationStatus.VERIFIED

    def test_ellipsis_fragments_must_appear_in_order(self) -> None:
        assert verify_quote("You may request a full refund ... Gift cards are", SOURCE)[0] is VerificationStatus.VERIFIED
        assert verify_quote("Gift cards are ... You may request a full refund", SOURCE)[0] is VerificationStatus.NOT_IN_SOURCE

    def test_paraphrase_is_not_verified(self) -> None:
        assert verify_quote("Refunds are available for one month after buying.", SOURCE)[0] is VerificationStatus.NOT_IN_SOURCE

    def test_changed_number_is_not_verified(self) -> None:
        assert verify_quote("full refund within 60 days of purchase", SOURCE)[0] is VerificationStatus.NOT_IN_SOURCE

    def test_too_short_quote_rejected(self) -> None:
        assert verify_quote("30 days", SOURCE)[0] is VerificationStatus.NOT_IN_SOURCE

    def test_missing_source(self) -> None:
        assert verify_quote("You may request a full refund", None)[0] is VerificationStatus.SOURCE_MISSING

    def test_normalize_text(self) -> None:
        assert normalize_text("  **Hello**\n\n  World’s ") == "hello world's"
