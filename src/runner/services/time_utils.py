from __future__ import annotations

from datetime import datetime, timezone


def utcnow_naive() -> datetime:
    """Return a naive UTC timestamp to match TIMESTAMP WITHOUT TIME ZONE."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
