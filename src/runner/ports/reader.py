from __future__ import annotations

from typing import Mapping, Protocol, Sequence, Any


Row = Mapping[str, Any]


class BatchReader(Protocol):
    """Reader возвращает "сырьевые" строки из источника батчами."""

    async def fetch_batch(self, *, limit: int) -> Sequence[Row]:
        """Вернуть батч строк (может быть пустым, если данных больше нет)."""
        ...
