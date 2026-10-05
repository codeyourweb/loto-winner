"""Hardening helpers (OWASP): HTTP headers and safe parsing.

This module centralises the application-level countermeasures recommended by
OWASP for an API exposed on the Internet:

* ``apply_security_headers``  — A05:2021 Security Misconfiguration;
* ``parse_int_arg``           — A03:2021 Injection / input validation.
"""

from __future__ import annotations

import re

from .loto_logic import ValidationError

# ---------------------------------------------------------------------------
# Security HTTP headers
# ---------------------------------------------------------------------------

# Restrictive content security policy: no external resource, no inline
# script, no framing.
DEFAULT_CSP = (
    "default-src 'self'; "
    "img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self'"
)

# Headers applied to every response. Neither the server nor its version is disclosed.
STATIC_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-Permitted-Cross-Domain-Policies": "none",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Content-Security-Policy": DEFAULT_CSP,
    # Prevents disclosure of the technology stack (Werkzeug/Flask banner).
    "Server": "Loto-Winner",
}

HSTS_VALUE = "max-age=31536000; includeSubDomains"


def apply_security_headers(response, *, hsts: bool = False):
    """Adds the security headers to a Flask response."""
    for header, value in STATIC_HEADERS.items():
        response.headers.setdefault(header, value)
    if hsts:
        response.headers.setdefault("Strict-Transport-Security", HSTS_VALUE)
    return response


# ---------------------------------------------------------------------------
# Strict parsing of query-string parameters
# ---------------------------------------------------------------------------

# Digits only: rejects "1e3", "5.0", "5_0", "+5", whitespace…
_INT_PATTERN = re.compile(r"^[0-9]{1,9}$")


def parse_int_arg(raw, *, name: str, default: int, minimum: int, maximum: int) -> int:
    """Converts a query-string parameter into a bounded integer.

    Raises ``ValidationError`` (→ HTTP 400) when the value is malformed,
    out of range, or of the wrong length, instead of producing a 500 error.
    """
    if raw is None or raw == "":
        return default

    if not isinstance(raw, str) or not _INT_PATTERN.match(raw.strip()):
        raise ValidationError(f"Le paramètre « {name} » doit être un entier positif.")

    value = int(raw.strip())
    if value < minimum or value > maximum:
        raise ValidationError(
            f"Le paramètre « {name} » doit être compris entre {minimum} et {maximum}."
        )
    return value
