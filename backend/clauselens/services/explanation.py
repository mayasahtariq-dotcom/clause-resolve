"""Plain-English explanation of an already-computed comparison.

The LLM only sees validated comparison facts (never raw web content) and its
text is rejected if it introduces numbers that are not in those facts.
"""

from __future__ import annotations

import json
import logging
import re

from clauselens.domain.comparison import CRITERION_LABELS
from clauselens.domain.errors import LLMError
from clauselens.domain.models import ComparisonReport
from clauselens.domain.policy import FIELD_SPECS
from clauselens.observability import log_event, metrics
from clauselens.ports.llm import LLMMessage, LLMProvider, LLMRequest

logger = logging.getLogger(__name__)

MAX_EXPLANATION_CHARS = 1500
_NUM = re.compile(r"\d+(?:\.\d+)?")

SYSTEM = """You write short plain-English summaries of a policy comparison for consumers.
Use ONLY the facts in the JSON provided. Do not add facts, numbers, vendors or advice that are not in it.
Do not change the recommendation. Mention important unknown, unverified or conflicting information.
Do not present this as legal advice. Write at most 130 words, no headings, no lists, no markdown."""


def comparison_facts(report: ComparisonReport) -> dict[str, object]:
    names = {str(v.id): v.name for v in report.vendors}
    cells: dict[str, dict[str, str]] = {}
    for c in report.cells:
        cells.setdefault(names[str(c.vendor_id)], {})[FIELD_SPECS[c.field].label] = c.display
    rec = report.recommendation
    return {
        "vendors": list(names.values()),
        "terms": cells,
        "priorities": [CRITERION_LABELS[p.criterion] for p in report.priorities],
        "recommendation": rec.headline,
        "recommended_vendor": names.get(str(rec.vendor_id)) if rec.vendor_id else None,
        "confidence": rec.confidence,
        "reasoning": rec.rationale,
        "conflicts": report.contradictions,
        "missing": report.missing[:20],
    }


def validate_explanation(text: str, facts_json: str) -> str | None:
    """Return a rejection reason, or None if acceptable."""
    if not text.strip():
        return "empty"
    if len(text) > MAX_EXPLANATION_CHARS:
        return "too long"
    allowed = set(_NUM.findall(facts_json))
    novel = [n for n in _NUM.findall(text) if n not in allowed]
    if novel:
        return f"introduced numbers not present in the comparison: {', '.join(sorted(set(novel)))}"
    return None


def generate_explanation(llm: LLMProvider, report: ComparisonReport) -> tuple[str | None, str]:
    """Return (text, status) where status is generated | rejected | failed."""
    facts_json = json.dumps(comparison_facts(report), ensure_ascii=False)
    try:
        resp = llm.generate(LLMRequest(
            messages=[LLMMessage(role="system", content=SYSTEM),
                      LLMMessage(role="user", content=f"Comparison facts (JSON):\n{facts_json}")],
            temperature=0.2, max_output_tokens=1200, purpose="explanation",
        ))
    except LLMError as exc:
        metrics.inc("explanation_total", outcome="failed")
        log_event(logger, logging.WARNING, "explanation generation failed", failure_category=exc.category.value)
        return None, "failed"
    text = resp.text.strip()
    reason = validate_explanation(text, facts_json)
    if reason:
        metrics.inc("explanation_total", outcome="rejected")
        log_event(logger, logging.WARNING, "explanation rejected", reason=reason)
        return None, "rejected"
    metrics.inc("explanation_total", outcome="generated")
    return text, "generated"
