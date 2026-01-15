from __future__ import annotations

from typing import Mapping, Protocol, Sequence, Any


Row = Mapping[str, Any]


class Writer(Protocol):
    """Writes a batch to the sink and returns the number of written rows."""

    async def write(self, rows: Sequence[Row]) -> int:
        ...
