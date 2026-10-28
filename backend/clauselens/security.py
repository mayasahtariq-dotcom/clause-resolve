"""URL safety and untrusted-content handling.

Retrieved web pages are untrusted. They are never executed, never used as
instructions, and are wrapped as data when shown to an LLM.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlsplit

from clauselens.domain.errors import UnsafeURLError

_HOST_RE = re.compile(r"^(?=.{1,253}$)(?!-)([a-z0-9-]{1,63}(?<!-)\.)+[a-z]{2,63}$")
_BLOCKED_SUFFIXES = (".local", ".localhost", ".internal", ".lan", ".home", ".corp", ".intranet", ".arpa")
_ALLOWED_SCHEMES = {"http", "https"}
METADATA_HOSTS = {"metadata.google.internal", "metadata", "169.254.169.254", "fd00:ec2::254"}


def _is_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
        or ip.is_reserved or ip.is_unspecified or (isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped
                                                   and not _is_public_ip(ip.ipv4_mapped))
    )


def normalize_domain(raw: str) -> str:
    """Turn user input like 'https://www.Example.com/help' into 'example.com'.

    Rejects IP literals, single-label hosts and internal suffixes. Raises
    UnsafeURLError for anything that is not a public DNS name.
    """
    text = raw.strip().lower()
    if not text:
        raise UnsafeURLError("Domain is empty")
    if "://" not in text:
        text = "https://" + text
    parts = urlsplit(text)
    if parts.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeURLError(f"Unsupported URL scheme: {parts.scheme}")
    if parts.username or parts.password:
        raise UnsafeURLError("Credentials in URLs are not allowed")
    host = (parts.hostname or "").rstrip(".")
    try:
        ipaddress.ip_address(host)
        raise UnsafeURLError("IP addresses are not accepted; enter the vendor's domain name")
    except ValueError:
        pass
    if host in METADATA_HOSTS or host == "localhost" or host.endswith(_BLOCKED_SUFFIXES):
        raise UnsafeURLError(f"Domain '{host}' is not a public website")
    if not _HOST_RE.match(host):
        raise UnsafeURLError(f"'{raw}' is not a valid public domain name")
    if host.startswith("www."):
        host = host[4:]
    return host


def host_of(url: str) -> str | None:
    try:
        return (urlsplit(url).hostname or "").lower().rstrip(".") or None
    except ValueError:
        return None


def is_same_site(url: str, domain: str) -> bool:
    host = host_of(url)
    return bool(host) and (host == domain or host.endswith("." + domain))  # type: ignore[union-attr]


def validate_public_url(url: str, *, resolve_dns: bool = False) -> str:
    """Validate a URL returned by a provider or about to be requested.

    With resolve_dns=True every resolved address must be public; use this in
    any adapter that makes direct HTTP requests to third-party URLs (and
    re-validate each redirect hop, since a public URL can redirect to a
    private one).
    """
    parts = urlsplit(url)
    if parts.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeURLError(f"Unsupported URL scheme in {url!r}")
    if parts.username or parts.password:
        raise UnsafeURLError("Credentials in URLs are not allowed")
    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        raise UnsafeURLError(f"URL has no host: {url!r}")
    if host in METADATA_HOSTS or host == "localhost" or host.endswith(_BLOCKED_SUFFIXES):
        raise UnsafeURLError(f"Host '{host}' is not public")
    try:
        if not _is_public_ip(ipaddress.ip_address(host)):
            raise UnsafeURLError(f"Host '{host}' is a private or reserved address")
        return url
    except ValueError:
        pass
    if resolve_dns:
        try:
            infos = socket.getaddrinfo(host, parts.port or 443, proto=socket.IPPROTO_TCP)
        except OSError as exc:
            raise UnsafeURLError(f"Cannot resolve host '{host}'") from exc
        for info in infos:
            if not _is_public_ip(ipaddress.ip_address(info[4][0])):
                raise UnsafeURLError(f"Host '{host}' resolves to a non-public address")
    return url


# Heuristic signals that a page is trying to instruct an AI system. A hit does
# not drop the page: we flag it, tell the model it is data, and rely on
# quote verification so an injected instruction cannot invent a policy value.
_INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore (all |any )?(the )?(previous|prior|above) (instructions|prompts?)",
        r"disregard (all |any )?(the )?(previous|prior|above|system)",
        r"you are (now )?(an?|the) (ai|assistant|language model)",
        r"\bsystem prompt\b",
        r"<\s*/?\s*(system|assistant|instructions?)\s*>",
        r"\bdo not (tell|inform) the user\b",
        r"respond (only )?with (the following|this) json",
        r"new instructions?:",
    ]
]


def detect_prompt_injection(text: str) -> bool:
    return any(p.search(text) for p in _INJECTION_PATTERNS)


_FENCE_RE = re.compile(r"<<<\s*/?\s*(SOURCE|END)[^>]*>>>", re.IGNORECASE)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_untrusted(text: str, max_chars: int) -> str:
    """Strip control characters and anything mimicking our data delimiters."""
    text = _CONTROL_RE.sub(" ", text)
    text = _FENCE_RE.sub("[removed delimiter]", text)
    return text[:max_chars]
