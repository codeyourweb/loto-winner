"""Shared Flask extensions (rate limiter).

The limiter lives in its own module to avoid circular imports between ``app``
and ``routes``.
"""

from __future__ import annotations

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Storage is configurable through ``RATELIMIT_STORAGE_URI`` (memory:// by
# default, Redis in production to share the counter across workers).
# ``RATELIMIT_ENABLED`` and ``RATELIMIT_DEFAULT`` are read from the Flask config.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
    strategy="fixed-window",
)
