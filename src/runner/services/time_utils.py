from __future__ import annotations

from datetime import datetime, timezone


def utcnow_naive() -> datetime:
    """UTC-время без tzinfo, чтобы ложилось в TIMESTAMP WITHOUT TIME ZONE."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
