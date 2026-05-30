"""Time utilities.

All domain code obtains 'now' via `utcnow()` so tests can freeze time
deterministically by patching this single function.
"""
from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)