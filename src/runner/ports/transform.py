from __future__ import annotations

from typing import Mapping, Protocol, Sequence, Any


Row = Mapping[str, Any]


class Transformer(Protocol):
    """Transforms source rows into sink-ready rows."""

    async def transform(self, rows: Sequence[Row]) -> Sequence[Row]:
        ...
