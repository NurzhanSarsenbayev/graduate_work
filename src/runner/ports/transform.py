from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

Row = Mapping[str, Any]


class Transformer(Protocol):
    """Transforms source rows into sink-ready rows."""

    async def transform(self, rows: Sequence[Row]) -> Sequence[Row]: ...
