"""Turn raw extracted claims into validated per-field findings.

This is where unknown / ambiguous / contradictory states are decided, using
deterministic rules only.
"""

from __future__ import annotations

from collections.abc import Iterable

from clauselens.domain.evidence import verify_quote
from clauselens.domain.models import Claim, Evidence, Finding, RetrievedSource, VerificationStatus
from clauselens.domain.policy import (
    FIELD_SPECS,
    FieldStatus,
    PolicyField,
    PolicyValue,
    ValueKind,
)

# Kinds where two different verified values mean the sources disagree.
_CONFLICT_KINDS = {ValueKind.DURATION, ValueKind.FEE, ValueKind.BOOLEAN, ValueKind.PARTY}
# Kinds where several verified values are naturally combined.
_MERGE_KINDS = {ValueKind.LIST, ValueKind.CHANNELS}


def value_key(kind: ValueKind, value: PolicyValue) -> object:
    """A hashable, normalised key used to decide whether two values agree."""
    if kind is ValueKind.DURATION and value.duration is not None:
        return ("days", value.duration.days)
    if kind is ValueKind.FEE and value.fee is not None:
        fee = value.fee
        if fee.is_zero():
            return ("zero",)
        if fee.kind.value == "percent":
            return ("percent", fee.percent)
        return ("fixed", fee.amount, fee.currency)
    if kind is ValueKind.BOOLEAN:
        return ("flag", value.flag)
    if kind is ValueKind.PARTY:
        return ("party", value.party)
    return ("other", value.model_dump_json())


def _merge(kind: ValueKind, claims: list[Claim]) -> PolicyValue:
    if kind is ValueKind.CHANNELS:
        seen: list = []
        for c in claims:
            for ch in c.value.channels or ():
                if ch not in seen:
                    seen.append(ch)
        return PolicyValue(channels=tuple(seen))
    items: list[str] = []
    lowered: set[str] = set()
    for c in claims:
        for it in c.value.items or ():
            key = it.strip().lower()
            if key and key not in lowered:
                lowered.add(key)
                items.append(it.strip())
    return PolicyValue(items=tuple(items))


def build_evidence(
    claim: Claim, sources: dict[str, RetrievedSource], extraction_meta: dict[str, str]
) -> Evidence:
    src = sources.get(claim.source_key)
    status, method = verify_quote(claim.quote, src.content if src else None)
    return Evidence(
        field=claim.field,
        source_key=claim.source_key,
        source_url=(src.final_url or src.url) if src else None,
        quote=claim.quote.strip(),
        retrieved_at=src.retrieved_at if src else None,
        verification=status,
        match_method=method,
        extraction=extraction_meta,
    )


def aggregate_claims(
    claims: Iterable[Claim],
    sources: list[RetrievedSource],
    *,
    extraction_meta: dict[str, str],
    analysed: bool,
) -> dict[PolicyField, Finding]:
    """Aggregate claims into one Finding per catalogued field.

    `analysed` is False when extraction never ran (research or LLM failure), in
    which case missing fields are UNKNOWN rather than NOT_FOUND.
    """
    by_key = {s.source_key: s for s in sources}
    claims = list(claims)
    findings: dict[PolicyField, Finding] = {}

    for field, spec in FIELD_SPECS.items():
        field_claims = [c for c in claims if c.field is field]
        if not field_claims:
            findings[field] = Finding(
                field=field,
                status=FieldStatus.NOT_FOUND if analysed else FieldStatus.UNKNOWN,
                note=(
                    "Not stated in any retrieved source."
                    if analysed
                    else "Could not be analysed; see investigation errors."
                ),
            )
            continue

        evidence = [build_evidence(c, by_key, extraction_meta) for c in field_claims]
        verified = [
            (c, e) for c, e in zip(field_claims, evidence, strict=True)
            if e.verification is VerificationStatus.VERIFIED
        ]
        definite = [(c, e) for c, e in verified if not c.ambiguous]

        if not verified:
            first = field_claims[0]
            findings[field] = Finding(
                field=field,
                status=FieldStatus.UNVERIFIED,
                value=first.value,
                summary=first.summary,
                evidence=evidence,
                note="The extracted quote could not be found in the retrieved page text.",
            )
            continue

        if not definite:
            findings[field] = Finding(
                field=field,
                status=FieldStatus.AMBIGUOUS,
                summary=verified[0][0].summary,
                evidence=evidence,
                note="A relevant clause exists but does not state a definite value.",
            )
            continue

        definite_claims = [c for c, _ in definite]
        if spec.kind in _MERGE_KINDS:
            value = _merge(spec.kind, definite_claims)
            findings[field] = Finding(
                field=field, status=FieldStatus.FOUND, value=value,
                summary=definite_claims[0].summary, evidence=evidence,
            )
            continue

        distinct: dict[object, PolicyValue] = {}
        for c in definite_claims:
            distinct.setdefault(value_key(spec.kind, c.value), c.value)

        if spec.kind in _CONFLICT_KINDS and len(distinct) > 1:
            findings[field] = Finding(
                field=field,
                status=FieldStatus.CONTRADICTORY,
                summary="Sources state different values.",
                evidence=evidence,
                conflicting_values=list(distinct.values()),
                note="Verified sources disagree; check each quote before relying on this.",
            )
            continue

        findings[field] = Finding(
            field=field,
            status=FieldStatus.FOUND,
            value=definite_claims[0].value,
            summary=definite_claims[0].summary,
            evidence=evidence,
        )
    return findings
