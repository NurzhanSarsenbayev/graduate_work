from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.app.models import EtlPipeline


@dataclass(frozen=True, slots=True)
class PipelineSnapshot:
    id: str
    name: str
    type: str
    mode: str
    batch_size: int
    source_query: Optional[str]
    python_module: Optional[str]
    target_table: str
    incremental_key: Optional[str]
    incremental_id_key: Optional[str]
    description: Optional[str] = None  # для legacy fallback в transformer


def snapshot_pipeline(p: EtlPipeline) -> PipelineSnapshot:
    return PipelineSnapshot(
        id=str(p.id),
        name=p.name,
        type=p.type,
        mode=p.mode,
        batch_size=int(p.batch_size or 1000),
        source_query=p.source_query,
        python_module=p.python_module,
        target_table=p.target_table,
        incremental_key=p.incremental_key,
        incremental_id_key=p.incremental_id_key,
        description=p.description,
    )
