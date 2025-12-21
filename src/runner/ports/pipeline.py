from __future__ import annotations

from typing import Protocol


class PipelineLike(Protocol):
    id: str
    name: str
    type: str          # "SQL" | "PYTHON"
    mode: str          # "full" | "incremental"
    batch_size: int

    source_query: str | None
    python_module: str | None
    target_table: str

    incremental_key: str | None
    incremental_id_key: str | None

    description: str | None
