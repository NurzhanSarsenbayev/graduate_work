from __future__ import annotations

from typing import Mapping, Protocol, Sequence, Any


Row = Mapping[str, Any]


class BatchReader(Protocol):
    """A reader that returns raw source rows in batches."""

    async def fetch_batch(self, *, limit: int) -> Sequence[Row]:
        """Fetch a batch of rows. Empty means EOF."""
        ...
