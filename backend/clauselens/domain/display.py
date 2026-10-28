"""Human-readable rendering of typed policy values."""

from __future__ import annotations

from clauselens.domain.models import Finding
from clauselens.domain.policy import FIELD_SPECS, FieldSpec, FieldStatus, Party, PolicyValue, ValueKind

_PARTY = {Party.CUSTOMER: "Customer pays", Party.MERCHANT: "Vendor pays", Party.VARIES: "Varies"}
_CHANNEL = {
    "online": "Online / self-service", "app_store": "Via app store", "email": "Email",
    "chat": "Live chat", "phone": "Phone", "mail": "Postal mail", "in_person": "In person",
    "other": "Other",
}


def display_value(kind: ValueKind, value: PolicyValue, spec: FieldSpec | None = None) -> str:
    if kind is ValueKind.DURATION and value.duration:
        return value.duration.display()
    if kind is ValueKind.FEE and value.fee:
        return value.fee.display()
    if kind is ValueKind.CHANNELS and value.channels:
        return ", ".join(_CHANNEL[c.value] for c in value.channels)
    if kind is ValueKind.BOOLEAN and value.flag is not None:
        if value.flag:
            return f"Yes, {spec.flag_meaning}" if spec and spec.flag_meaning else "Yes"
        return spec.flag_false_label if spec and spec.flag_false_label else "No"
    if kind is ValueKind.PARTY and value.party:
        return _PARTY[value.party]
    if kind is ValueKind.LIST:
        return "; ".join(value.items) if value.items else "None listed"
    return value.text or "Stated (see evidence)"


def display_finding(finding: Finding) -> str:
    spec = FIELD_SPECS[finding.field]
    match finding.status:
        case FieldStatus.FOUND:
            assert finding.value is not None
            text = display_value(spec.kind, finding.value, spec)
            if spec.kind is ValueKind.TEXT and finding.summary and not finding.value.text:
                text = finding.summary
            return text
        case FieldStatus.CONTRADICTORY:
            vals = " vs ".join(display_value(spec.kind, v, spec) for v in finding.conflicting_values)
            return f"Conflicting: {vals}"
        case FieldStatus.UNVERIFIED:
            if finding.value is None or finding.value.component_for(spec.kind) is None:
                return "Unverified clause"
            return f"Unverified: {display_value(spec.kind, finding.value, spec)}"
        case FieldStatus.AMBIGUOUS:
            return "Ambiguous wording"
        case FieldStatus.NOT_FOUND:
            return "Not stated"
        case _:
            return "Unknown"
