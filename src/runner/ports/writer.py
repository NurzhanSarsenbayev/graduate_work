from __future__ import annotations

from typing import Mapping, Protocol, Sequence, Any


Row = Mapping[str, Any]


class Writer(Protocol):
    """Writer пишет батч в sink и возвращает число записанных строк."""

    async def write(self, rows: Sequence[Row]) -> int:
        ...
