"""Deterministic comparison engine.

Inputs are validated VendorPolicy objects; output is a ComparisonReport. Only
findings with status FOUND (verified evidence, no contradiction) contribute to
scores. Unknown values are never treated as best or worst: they score nothing
and reduce the vendor's coverage, which in turn lowers recommendation
confidence. The LLM is not involved here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from clauselens.domain.display import display_finding
from clauselens.domain.models import (
    ComparisonCell,
    ComparisonReport,
    Criterion,
    CriterionScore,
    Finding,
    Priority,
    Recommendation,
    VendorPolicy,
)
from clauselens.domain.policy import (
    FIELD_SPECS,
    Channel,
    Fee,
    FeeKind,
    FieldStatus,
    Party,
    PolicyField,
)

# Used when the user gives no priorities. Documented in docs/ARCHITECTURE.md
# and overridable via SCORING_POLICY_JSON.
DEFAULT_SCORING_POLICY: dict[Criterion, float] = {
    Criterion.LONGEST_REFUND_WINDOW: 3.0,
    Criterion.EASIEST_CANCELLATION: 2.0,
    Criterion.LOWEST_CANCELLATION_FEE: 2.0,
    Criterion.NO_AUTO_TRIAL_CONVERSION: 1.0,
    Criterion.LONGEST_TRIAL: 1.0,
    Criterion.LOWEST_RESTOCKING_FEE: 1.0,
    Criterion.MERCHANT_PAYS_RETURN_SHIPPING: 1.0,
    Criterion.FEWEST_EXCLUSIONS: 1.0,
}

CHANNEL_EASE: dict[Channel, float] = {
    Channel.ONLINE: 1.0,
    Channel.APP_STORE: 0.8,
    Channel.EMAIL: 0.6,
    Channel.CHAT: 0.6,
    Channel.PHONE: 0.4,
    Channel.OTHER: 0.3,
    Channel.MAIL: 0.2,
    Channel.IN_PERSON: 0.2,
}

TIE_MARGIN = 0.02
_STATUS_PHRASE = {
    FieldStatus.NOT_FOUND: "is not stated in the retrieved pages",
    FieldStatus.UNVERIFIED: "could not be verified against the source text",
    FieldStatus.AMBIGUOUS: "is worded ambiguously",
    FieldStatus.CONTRADICTORY: "is contradictory",
    FieldStatus.UNKNOWN: "is unknown",
}
MIN_COVERAGE_TO_RECOMMEND = 0.34

CRITERION_LABELS: dict[Criterion, str] = {
    Criterion.LONGEST_REFUND_WINDOW: "Longest refund window",
    Criterion.LOWEST_CANCELLATION_FEE: "Lowest cancellation fee",
    Criterion.EASIEST_CANCELLATION: "Easiest cancellation",
    Criterion.LONGEST_TRIAL: "Longest free trial",
    Criterion.NO_AUTO_TRIAL_CONVERSION: "No automatic trial-to-paid conversion",
    Criterion.NO_AUTO_RENEWAL: "No automatic renewal",
    Criterion.LOWEST_RESTOCKING_FEE: "Lowest restocking fee",
    Criterion.MERCHANT_PAYS_RETURN_SHIPPING: "Vendor pays return shipping",
    Criterion.FEWEST_EXCLUSIONS: "Fewest stated exclusions",
}

CRITERION_FIELDS: dict[Criterion, tuple[PolicyField, ...]] = {
    Criterion.LONGEST_REFUND_WINDOW: (PolicyField.REFUND_WINDOW,),
    Criterion.LOWEST_CANCELLATION_FEE: (PolicyField.CANCELLATION_FEE,),
    Criterion.EASIEST_CANCELLATION: (PolicyField.CANCELLATION_METHOD,),
    Criterion.LONGEST_TRIAL: (PolicyField.TRIAL_DURATION,),
    Criterion.NO_AUTO_TRIAL_CONVERSION: (PolicyField.TRIAL_CONVERSION,),
    Criterion.NO_AUTO_RENEWAL: (PolicyField.RENEWAL_BEHAVIOR,),
    Criterion.LOWEST_RESTOCKING_FEE: (PolicyField.RESTOCKING_FEE,),
    Criterion.MERCHANT_PAYS_RETURN_SHIPPING: (PolicyField.RETURN_SHIPPING_LIABILITY,),
    Criterion.FEWEST_EXCLUSIONS: (PolicyField.NON_REFUNDABLE_ITEMS, PolicyField.EXCEPTIONS),
}


def _found(f: Finding | None) -> Finding | None:
    return f if f is not None and f.status is FieldStatus.FOUND and f.value is not None else None


@dataclass
class _Raw:
    """Per-vendor raw measure for a criterion (None = unknown)."""

    value: float | None
    label: str


def _relative_max(raws: dict[str, _Raw]) -> dict[str, float | None]:
    known = [r.value for r in raws.values() if r.value is not None]
    if not known:
        return {k: None for k in raws}
    top = max(known)
    return {k: (None if r.value is None else (1.0 if top == 0 else r.value / top)) for k, r in raws.items()}


def _duration_raw(field: PolicyField) -> Callable[[VendorPolicy], _Raw]:
    def fn(vp: VendorPolicy) -> _Raw:
        f = _found(vp.findings.get(field))
        if f is None or f.value.duration is None:  # type: ignore[union-attr]
            return _Raw(None, "unknown")
        d = f.value.duration  # type: ignore[union-attr]
        return _Raw(float(d.days), d.display())

    return fn


def _fee_scores(field: PolicyField, policies: list[VendorPolicy]) -> tuple[dict[str, float | None], dict[str, str]]:
    """Known zero = 1.0. Comparable non-zero fees scale within 0..0.5. Others 0.25."""
    labels: dict[str, str] = {}
    fees: dict[str, Fee | None] = {}
    for vp in policies:
        vid = str(vp.vendor.id)
        f = _found(vp.findings.get(field))
        fee = f.value.fee if f and f.value else None
        fees[vid] = fee
        labels[vid] = fee.display() if fee else "unknown"
    nonzero = [fee for fee in fees.values() if fee is not None and not fee.is_zero()]
    comparable = bool(nonzero) and len({(f.kind, f.currency) for f in nonzero}) == 1
    scores: dict[str, float | None] = {}
    for vid, fee in fees.items():
        if fee is None:
            scores[vid] = None
        elif fee.is_zero():
            scores[vid] = 1.0
        elif comparable:
            mags = [Decimal(f.percent if f.kind is FeeKind.PERCENT else f.amount) for f in nonzero]  # type: ignore[arg-type]
            mine = Decimal(fee.percent if fee.kind is FeeKind.PERCENT else fee.amount)  # type: ignore[arg-type]
            scores[vid] = float(Decimal("0.5") * (min(mags) / mine)) if mine else 1.0
        else:
            scores[vid] = 0.25
    return scores, labels


def _score_criterion(
    criterion: Criterion, policies: list[VendorPolicy]
) -> tuple[dict[str, float | None], dict[str, str], str]:
    """Return (scores 0..1 or None, per-vendor labels, rule description)."""
    scores: dict[str, float | None] = {}
    labels: dict[str, str] = {}
    raws: dict[str, _Raw] = {}
    if criterion in (Criterion.LONGEST_REFUND_WINDOW, Criterion.LONGEST_TRIAL):
        field = CRITERION_FIELDS[criterion][0]
        raws.update({str(vp.vendor.id): _duration_raw(field)(vp) for vp in policies})
        return _relative_max(raws), {k: r.label for k, r in raws.items()}, "longer is better, scored relative to the longest"
    if criterion in (Criterion.LOWEST_CANCELLATION_FEE, Criterion.LOWEST_RESTOCKING_FEE):
        s, labels = _fee_scores(CRITERION_FIELDS[criterion][0], policies)
        return s, labels, "a stated zero fee scores best; non-zero fees score lower; an unstated fee is unknown, never zero"
    if criterion is Criterion.EASIEST_CANCELLATION:
        for vp in policies:
            vid = str(vp.vendor.id)
            f = _found(vp.findings.get(PolicyField.CANCELLATION_METHOD))
            chans = f.value.channels if f and f.value else None  # type: ignore[union-attr]
            if not chans:
                scores[vid], labels[vid] = None, "unknown"
            else:
                best = max(chans, key=lambda c: CHANNEL_EASE[c])
                scores[vid], labels[vid] = CHANNEL_EASE[best], best.value.replace("_", " ")
        return scores, labels, "online self-service > app store > email/chat > phone > mail/in person"
    if criterion in (Criterion.NO_AUTO_TRIAL_CONVERSION, Criterion.NO_AUTO_RENEWAL):
        field = CRITERION_FIELDS[criterion][0]
        for vp in policies:
            vid = str(vp.vendor.id)
            f = _found(vp.findings.get(field))
            flag = f.value.flag if f and f.value else None  # type: ignore[union-attr]
            scores[vid] = None if flag is None else (0.0 if flag else 1.0)
            labels[vid] = "unknown" if flag is None else ("automatic" if flag else "not automatic")
        return scores, labels, "not automatic scores 1, automatic scores 0"
    if criterion is Criterion.MERCHANT_PAYS_RETURN_SHIPPING:
        table = {Party.MERCHANT: 1.0, Party.VARIES: 0.5, Party.CUSTOMER: 0.0}
        for vp in policies:
            vid = str(vp.vendor.id)
            f = _found(vp.findings.get(PolicyField.RETURN_SHIPPING_LIABILITY))
            party = f.value.party if f and f.value else None  # type: ignore[union-attr]
            scores[vid] = None if party is None else table[party]
            labels[vid] = "unknown" if party is None else party.value
        return scores, labels, "vendor pays 1, varies 0.5, customer pays 0"
    if criterion is Criterion.FEWEST_EXCLUSIONS:
        for vp in policies:
            vid = str(vp.vendor.id)
            found = [_found(vp.findings.get(fld)) for fld in CRITERION_FIELDS[criterion]]
            if not any(found):
                raws[vid] = _Raw(None, "unknown")
                continue
            n = sum(len(f.value.items or ()) for f in found if f and f.value)  # type: ignore[union-attr]
            raws[vid] = _Raw(1.0 / (1 + n), f"{n} listed")
        return _relative_max(raws), {k: r.label for k, r in raws.items()}, "fewer stated exclusions is better"
    raise ValueError(f"unhandled criterion {criterion}")  # pragma: no cover


def _cells(policies: list[VendorPolicy], best: dict[PolicyField, set[str]]) -> list[ComparisonCell]:
    cells: list[ComparisonCell] = []
    for vp in policies:
        vid = str(vp.vendor.id)
        for field in FIELD_SPECS:
            finding = vp.findings.get(field) or Finding(field=field, status=FieldStatus.UNKNOWN)
            normalized: dict[str, str | float | bool | list[str] | None] = {}
            v = finding.value if finding.status is FieldStatus.FOUND else None
            if v is not None:
                if v.duration:
                    normalized["days"] = float(v.duration.days)
                if v.fee:
                    normalized["fee_kind"] = v.fee.kind.value
                    normalized["fee_is_zero"] = v.fee.is_zero()
                    if v.fee.amount is not None:
                        normalized["amount"] = float(v.fee.amount)
                    if v.fee.percent is not None:
                        normalized["percent"] = float(v.fee.percent)
                    normalized["currency"] = v.fee.currency
                if v.channels:
                    normalized["channels"] = [c.value for c in v.channels]
                if v.flag is not None:
                    normalized["flag"] = v.flag
                if v.party:
                    normalized["party"] = v.party.value
                if v.items is not None:
                    normalized["count"] = float(len(v.items))
            cells.append(
                ComparisonCell(
                    vendor_id=vp.vendor.id,
                    field=field,
                    status=finding.status,
                    display=display_finding(finding),
                    normalized=normalized,
                    evidence_ids=[e.id for e in finding.evidence if e.id is not None],
                    is_best=vid in best.get(field, set()),
                )
            )
    return cells


def compare(
    policies: list[VendorPolicy],
    priorities: list[Priority] | None = None,
    *,
    scoring_policy: dict[Criterion, float] | None = None,
) -> ComparisonReport:
    if not policies:
        raise ValueError("at least one vendor policy is required")
    policy_weights = scoring_policy or DEFAULT_SCORING_POLICY
    if priorities:
        weights = {p.criterion: p.weight for p in priorities}
        effective = list(priorities)
    else:
        weights = dict(policy_weights)
        effective = [Priority(criterion=c, weight=w) for c, w in policy_weights.items()]

    usable = [vp for vp in policies if not vp.failed]
    names = {str(vp.vendor.id): vp.vendor.name for vp in policies}

    criteria: list[CriterionScore] = []
    included_weight = 0.0
    weighted: dict[str, float] = {str(vp.vendor.id): 0.0 for vp in usable}
    covered: dict[str, float] = {str(vp.vendor.id): 0.0 for vp in usable}
    best_by_field: dict[PolicyField, set[str]] = {}
    rationale: list[str] = []
    skipped: list[str] = []

    for criterion, weight in weights.items():
        if not usable:
            break
        scores, labels, rule = _score_criterion(criterion, usable)
        label = CRITERION_LABELS[criterion]
        known = {k: s for k, s in scores.items() if s is not None}
        if not known:
            skipped.append(label)
            criteria.append(CriterionScore(criterion=criterion, weight=weight, scores=scores,
                                           explanation=f"{label}: no vendor has verified data, so it was not scored."))
            continue
        included_weight += weight
        for vid, s in known.items():
            weighted[vid] += weight * s
            covered[vid] += weight
        top = max(known.values())
        winners = {vid for vid, s in known.items() if s == top}
        if len(known) > 1 and len(winners) < len(known):
            for fld in CRITERION_FIELDS[criterion]:
                best_by_field.setdefault(fld, set()).update(winners)
        parts = ", ".join(f"{names[vid]}: {labels[vid]}" for vid in scores)
        criteria.append(CriterionScore(criterion=criterion, weight=weight, scores=scores,
                                       explanation=f"{label} (weight {weight:g}; {rule}). {parts}."))
        if len(known) == 1:
            only = names[next(iter(known))]
            rationale.append(f"{label}: only {only} has verified data, so this is not a head-to-head "
                             f"comparison ({parts}).")
        elif len(winners) == len(known):
            rationale.append(f"{label}: no difference between vendors with verified data ({parts}).")
        else:
            win_names = " and ".join(names[w] for w in sorted(winners, key=lambda w: names[w]))
            rationale.append(f"{label}: {win_names} best ({parts}).")

    totals = {vid: (weighted[vid] / included_weight if included_weight else 0.0) for vid in weighted}
    coverage = {vid: (covered[vid] / included_weight if included_weight else 0.0) for vid in covered}

    contradictions: list[str] = []
    missing: list[str] = []
    priority_fields = {f for c in weights for f in CRITERION_FIELDS[c]}
    for vp in policies:
        if vp.failed:
            missing.append(f"{vp.vendor.name}: investigation failed ({vp.error or 'unknown error'}); excluded from scoring.")
            continue
        for field, finding in vp.findings.items():
            label = FIELD_SPECS[field].label
            if finding.status is FieldStatus.CONTRADICTORY:
                contradictions.append(f"{vp.vendor.name}: {label}: {display_finding(finding)}.")
            elif field in priority_fields and finding.status is not FieldStatus.FOUND:
                missing.append(f"{vp.vendor.name}: {label} {_STATUS_PHRASE[finding.status]}.")

    recommendation = _recommend(usable, totals, coverage, names, rationale, skipped, included_weight)
    return ComparisonReport(
        vendors=[vp.vendor for vp in policies],
        priorities=effective,
        cells=_cells(policies, best_by_field),
        criteria=criteria,
        recommendation=recommendation,
        contradictions=contradictions,
        missing=missing,
        scoring_policy={c.value: w for c, w in policy_weights.items()},
        snapshot_ids=[vp.snapshot_id for vp in policies if vp.snapshot_id is not None],
    )


def _recommend(
    usable: list[VendorPolicy],
    totals: dict[str, float],
    coverage: dict[str, float],
    names: dict[str, str],
    rationale: list[str],
    skipped: list[str],
    included_weight: float,
) -> Recommendation:
    notes = list(rationale)
    if skipped:
        notes.append("Not scored (no verified data for any vendor): " + ", ".join(skipped) + ".")

    def rec(vendor_id: str | None, headline: str, confidence: str) -> Recommendation:
        from uuid import UUID

        return Recommendation(
            vendor_id=UUID(vendor_id) if vendor_id else None,
            headline=headline,
            rationale=notes,
            confidence=confidence,
            coverage={k: round(v, 3) for k, v in coverage.items()},
            totals={k: round(v, 3) for k, v in totals.items()},
        )

    if not usable:
        return rec(None, "No recommendation: every vendor investigation failed.", "insufficient")
    if included_weight == 0:
        return rec(None, "No recommendation: no prioritised policy terms could be verified for any vendor.",
                   "insufficient")
    ranked = sorted(totals, key=lambda v: (-totals[v], names[v]))
    top = ranked[0]
    if coverage[top] < MIN_COVERAGE_TO_RECOMMEND:
        notes.append(f"{names[top]} scored highest but only {coverage[top]:.0%} of the weighted criteria are backed "
                     "by verified evidence, which is too little to recommend.")
        return rec(None, "No recommendation: too much information is missing.", "insufficient")
    if len(ranked) > 1 and totals[top] - totals[ranked[1]] <= TIE_MARGIN:
        tied = [v for v in ranked if totals[top] - totals[v] <= TIE_MARGIN]
        return rec(None, "No clear winner: " + " and ".join(names[v] for v in tied)
                   + " are effectively tied on your priorities.", "low")
    margin = totals[top] - (totals[ranked[1]] if len(ranked) > 1 else 0.0)
    if coverage[top] >= 0.8 and (len(ranked) == 1 or margin >= 0.1):
        confidence = "high"
    elif coverage[top] >= 0.5:
        confidence = "medium"
    else:
        confidence = "low"
    gaps = [names[v] for v in ranked if coverage[v] < 1.0]
    if gaps:
        notes.append("Missing or unverified data for " + ", ".join(gaps)
                     + " limits confidence; unknown terms were not assumed to be favourable or unfavourable.")
    return rec(top, f"{names[top]} best matches your priorities based on verified policy text.", confidence)
