"""SSRF protection for the website crawler.

Any URL a user submits (business website) must be validated before the
crawler is allowed to fetch it. We block:

- non-http(s) schemes
- localhost / loopback
- private / link-local / reserved IP ranges
- cloud metadata endpoints (169.254.169.254 and friends)
- credentials embedded in the URL (user:pass@host)

DNS is resolved and *every* resolved address is checked, so a hostname that
resolves to a private IP (DNS rebinding) is rejected too.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeURLError(ValueError):
    """Raised when a URL fails SSRF safety checks."""


ALLOWED_SCHEMES = {"http", "https"}

# Explicit metadata endpoints in addition to generic private-range checks.
BLOCKED_HOSTS = {
    "metadata.google.internal",
    "169.254.169.254",
}


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_public_url(url: str) -> str:
    """Validate that `url` is safe to crawl. Returns the normalized URL or raises UnsafeURLError."""
    parsed = urlparse(url.strip())

    if parsed.scheme not in ALLOWED_SCHEMES:
        raise UnsafeURLError(f"Unsupported scheme: {parsed.scheme!r}")

    if parsed.username or parsed.password:
        raise UnsafeURLError("Credentials in URL are not allowed")

    hostname = parsed.hostname
    if not hostname:
        raise UnsafeURLError("URL has no hostname")

    hostname_lower = hostname.lower()
    if hostname_lower in BLOCKED_HOSTS or hostname_lower == "localhost":
        raise UnsafeURLError(f"Blocked host: {hostname}")

    # If hostname is itself a literal IP, check directly.
    try:
        literal_ip = ipaddress.ip_address(hostname)
        if _is_blocked_ip(literal_ip):
            raise UnsafeURLError(f"Blocked IP literal: {hostname}")
        return url
    except ValueError:
        pass  # not a literal IP, fall through to DNS resolution

    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Could not resolve host: {hostname}") from exc

    if not addr_infos:
        raise UnsafeURLError(f"No addresses resolved for host: {hostname}")

    for family, _, _, _, sockaddr in addr_infos:
        ip_str = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if _is_blocked_ip(ip_obj):
            raise UnsafeURLError(
                f"Host {hostname} resolves to a blocked address: {ip_str}"
            )

    return url
