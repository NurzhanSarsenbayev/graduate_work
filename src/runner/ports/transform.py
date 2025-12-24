from __future__ import annotations

from typing import Mapping, Protocol, Sequence, Any


Row = Mapping[str, Any]


class Transformer(Protocol):
    """Transformer преобразует строки (нормализация/обогащение/маппинг)."""

    async def transform(self, rows: Sequence[Row]) -> Sequence[Row]:
        ...
