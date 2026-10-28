"""Policy field catalogue and typed value models.

Everything here is pure data: no I/O, no provider types. The catalogue is the
single source of truth for which policy fields exist and what shape their
values take; the extraction prompt, validation, comparison and the frontend
(via /api/meta) are all derived from it.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PolicyField(StrEnum):
    REFUND_WINDOW = "refund_window"
    REFUND_ELIGIBILITY = "refund_eligibility"
    CANCELLATION_METHOD = "cancellation_method"
    CANCELLATION_DEADLINE = "cancellation_deadline"
    CANCELLATION_FEE = "cancellation_fee"
    RENEWAL_BEHAVIOR = "renewal_behavior"
    TRIAL_DURATION = "trial_duration"
    TRIAL_CONVERSION = "trial_conversion"
    RESTOCKING_FEE = "restocking_fee"
    RETURN_SHIPPING_LIABILITY = "return_shipping_liability"
    NON_REFUNDABLE_ITEMS = "non_refundable_items"
    EXCEPTIONS = "exceptions"


class ValueKind(StrEnum):
    DURATION = "duration"
    FEE = "fee"
    CHANNELS = "channels"
    BOOLEAN = "boolean"
    PARTY = "party"
    LIST = "list"
    TEXT = "text"


@dataclass(frozen=True)
class FieldSpec:
    key: PolicyField
    label: str
    kind: ValueKind
    description: str
    # Meaning of `flag` for BOOLEAN fields, shown to the model and the user.
    flag_meaning: str | None = None
    flag_false_label: str | None = None


FIELD_SPECS: dict[PolicyField, FieldSpec] = {
    s.key: s
    for s in [
        FieldSpec(PolicyField.REFUND_WINDOW, "Refund window", ValueKind.DURATION,
                  "How long after purchase a refund can be requested."),
        FieldSpec(PolicyField.REFUND_ELIGIBILITY, "Refund eligibility", ValueKind.TEXT,
                  "Which purchases or customers qualify for a refund, and conditions attached."),
        FieldSpec(PolicyField.CANCELLATION_METHOD, "Cancellation method", ValueKind.CHANNELS,
                  "How a subscription or order is cancelled (online, email, phone, ...)."),
        FieldSpec(PolicyField.CANCELLATION_DEADLINE, "Cancellation deadline", ValueKind.TEXT,
                  "When cancellation must happen to avoid the next charge."),
        FieldSpec(PolicyField.CANCELLATION_FEE, "Cancellation fee", ValueKind.FEE,
                  "Any fee or penalty charged for cancelling."),
        FieldSpec(PolicyField.RENEWAL_BEHAVIOR, "Renewal behavior", ValueKind.BOOLEAN,
                  "Whether subscriptions renew automatically.", flag_meaning="auto-renews",
                  flag_false_label="Does not auto-renew"),
        FieldSpec(PolicyField.TRIAL_DURATION, "Trial duration", ValueKind.DURATION,
                  "Length of any free trial."),
        FieldSpec(PolicyField.TRIAL_CONVERSION, "Trial-to-paid conversion", ValueKind.BOOLEAN,
                  "Whether a free trial converts to a paid plan automatically.",
                  flag_meaning="converts to paid automatically",
                  flag_false_label="Does not convert automatically"),
        FieldSpec(PolicyField.RESTOCKING_FEE, "Restocking fee", ValueKind.FEE,
                  "Fee deducted from refunds for returned physical goods."),
        FieldSpec(PolicyField.RETURN_SHIPPING_LIABILITY, "Return shipping", ValueKind.PARTY,
                  "Who pays to ship returned goods back."),
        FieldSpec(PolicyField.NON_REFUNDABLE_ITEMS, "Non-refundable items", ValueKind.LIST,
                  "Products or services explicitly excluded from refunds."),
        FieldSpec(PolicyField.EXCEPTIONS, "Exceptions & exclusions", ValueKind.LIST,
                  "Other notable exceptions, exclusions or conditions."),
    ]
}


class FieldStatus(StrEnum):
    """How much we know about a field for one vendor.

    FOUND          stated in a retrieved source and the supporting quote was verified
    UNVERIFIED     a value was extracted but its quote could not be matched to the source
    AMBIGUOUS      a relevant clause exists but does not determine a value
    CONTRADICTORY  verified sources state incompatible values
    NOT_FOUND      sources were retrieved and analysed but did not state this field
    UNKNOWN        the field could not be analysed at all (e.g. research or extraction failed)
    """

    FOUND = "found"
    UNVERIFIED = "unverified"
    AMBIGUOUS = "ambiguous"
    CONTRADICTORY = "contradictory"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"


class DurationUnit(StrEnum):
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


# Documented normalisation factors. Months and years are calendar-ambiguous;
# we use 30 and 365 days and say so in the UI.
DAYS_PER_UNIT: dict[DurationUnit, Decimal] = {
    DurationUnit.HOUR: Decimal(1) / Decimal(24),
    DurationUnit.DAY: Decimal(1),
    DurationUnit.WEEK: Decimal(7),
    DurationUnit.MONTH: Decimal(30),
    DurationUnit.YEAR: Decimal(365),
}


class Duration(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: Decimal = Field(ge=0)
    unit: DurationUnit

    @property
    def days(self) -> Decimal:
        return (self.value * DAYS_PER_UNIT[self.unit]).quantize(Decimal("0.01"))

    def display(self) -> str:
        v = self.value.normalize()
        text = f"{v:f}"
        return f"{text} {self.unit.value}{'' if v == 1 else 's'}"


class FeeKind(StrEnum):
    NONE = "none"  # explicitly no fee: a *known* zero
    FIXED = "fixed"
    PERCENT = "percent"


class Fee(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: FeeKind
    amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=8)
    percent: Decimal | None = Field(default=None, ge=0, le=100)

    @field_validator("currency")
    @classmethod
    def _upper(cls, v: str | None) -> str | None:
        return v.upper() if v else v

    @model_validator(mode="after")
    def _consistent(self) -> Fee:
        if self.kind is FeeKind.FIXED and self.amount is None:
            raise ValueError("fixed fee requires amount")
        if self.kind is FeeKind.PERCENT and self.percent is None:
            raise ValueError("percent fee requires percent")
        return self

    def is_zero(self) -> bool:
        return (
            self.kind is FeeKind.NONE
            or (self.kind is FeeKind.FIXED and self.amount == 0)
            or (self.kind is FeeKind.PERCENT and self.percent == 0)
        )

    def display(self) -> str:
        if self.kind is FeeKind.NONE:
            return "No fee (stated)"
        if self.kind is FeeKind.PERCENT:
            return f"{self.percent.normalize():f}%"  # type: ignore[union-attr]
        cur = f"{self.currency} " if self.currency else ""
        return f"{cur}{self.amount.normalize():f}"  # type: ignore[union-attr]


class Channel(StrEnum):
    ONLINE = "online"  # self-service account settings / web form
    APP_STORE = "app_store"  # managed by Apple / Google store
    EMAIL = "email"
    CHAT = "chat"
    PHONE = "phone"
    MAIL = "mail"
    IN_PERSON = "in_person"
    OTHER = "other"


class Party(StrEnum):
    CUSTOMER = "customer"
    MERCHANT = "merchant"
    VARIES = "varies"


class PolicyValue(BaseModel):
    """A typed value. Exactly the component matching the field's ValueKind is set."""

    model_config = ConfigDict(frozen=True)

    duration: Duration | None = None
    fee: Fee | None = None
    channels: tuple[Channel, ...] | None = None
    flag: bool | None = None
    party: Party | None = None
    items: tuple[str, ...] | None = None
    text: str | None = Field(default=None, max_length=600)

    def component_for(self, kind: ValueKind) -> object | None:
        return {
            ValueKind.DURATION: self.duration,
            ValueKind.FEE: self.fee,
            ValueKind.CHANNELS: self.channels,
            ValueKind.BOOLEAN: self.flag,
            ValueKind.PARTY: self.party,
            ValueKind.LIST: self.items,
            ValueKind.TEXT: self.text,
        }[kind]
