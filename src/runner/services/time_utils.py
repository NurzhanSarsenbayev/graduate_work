from __future__ import annotations

from datetime import UTC, datetime


def utcnow_naive() -> datetime:
    """Return a naive UTC timestamp to match TIMESTAMP WITHOUT TIME ZONE."""
    return datetime.now(UTC).replace(tzinfo=None)
