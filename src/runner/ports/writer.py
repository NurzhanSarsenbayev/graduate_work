from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

Row = Mapping[str, Any]


class Writer(Protocol):
    """Writes a batch to the sink and returns the number of written rows."""

    async def write(self, rows: Sequence[Row]) -> int: ...
