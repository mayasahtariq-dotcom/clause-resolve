"""Verify that extracted quotes actually occur in retrieved source text."""

from __future__ import annotations

import re
import unicodedata

from clauselens.domain.models import VerificationStatus

MIN_QUOTE_CHARS = 12
MAX_QUOTE_CHARS = 1200

_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_MD_NOISE = re.compile(r"[*_`#>|~]+")
_WS = re.compile(r"\s+")
_ELLIPSIS = re.compile(r"\s*(?:\.\.\.|…|\[\.\.\.\])\s*")
_TRANSLATE = str.maketrans(
    {
        "‘": "'", "’": "'", "‚": "'", "‛": "'",
        "“": '"', "”": '"', "„": '"',
        "–": "-", "—": "-", "−": "-", " ": " ",
    }
)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_TRANSLATE)
    text = _MD_LINK.sub(r"\1", text)
    text = _MD_NOISE.sub(" ", text)
    return _WS.sub(" ", text).strip().lower()


def verify_quote(quote: str, source_text: str | None) -> tuple[VerificationStatus, str | None]:
    """Return (status, match_method).

    Matching is deliberately strict: after normalising whitespace, typography
    and markdown, the quote (or each "..."-separated fragment, in order) must be
    a literal substring of the source. There is no fuzzy matching, so a
    paraphrase is never reported as verified.
    """
    if source_text is None:
        return VerificationStatus.SOURCE_MISSING, None
    q = quote.strip()
    if len(q) < MIN_QUOTE_CHARS or len(q) > MAX_QUOTE_CHARS:
        return VerificationStatus.NOT_IN_SOURCE, None
    if q in source_text:
        return VerificationStatus.VERIFIED, "exact"
    haystack = normalize_text(source_text)
    needle = normalize_text(q)
    if needle and needle in haystack:
        return VerificationStatus.VERIFIED, "normalized"
    fragments = [normalize_text(f) for f in _ELLIPSIS.split(q)]
    fragments = [f for f in fragments if f]
    if len(fragments) > 1 and all(len(f) >= MIN_QUOTE_CHARS // 2 for f in fragments):
        pos = 0
        for frag in fragments:
            idx = haystack.find(frag, pos)
            if idx < 0:
                return VerificationStatus.NOT_IN_SOURCE, None
            pos = idx + len(frag)
        return VerificationStatus.VERIFIED, "fragments"
    return VerificationStatus.NOT_IN_SOURCE, None
