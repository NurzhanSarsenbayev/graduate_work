from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.models import EtlPipeline
from src.app.models import EtlPipelineTask


@dataclass(frozen=True, slots=True)
class TaskSnapshot:
    id: str
    order_index: int
    task_type: str
    body: str
    target_table: str | None


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
    description: Optional[str] = None  # legacy fallback in transformer
    tasks: tuple[TaskSnapshot, ...] = ()


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


async def snapshot_pipeline_with_tasks(
        session: AsyncSession,
        p: EtlPipeline) -> PipelineSnapshot:
    stmt = (
        select(EtlPipelineTask)
        .where(EtlPipelineTask.pipeline_id == p.id)
        .order_by(EtlPipelineTask.order_index)
    )
    res = await session.execute(stmt)
    tasks = tuple(
        TaskSnapshot(
            id=str(t.id),
            order_index=int(t.order_index),
            task_type=str(t.task_type),
            body=str(t.body),
            target_table=t.target_table,
        )
        for t in res.scalars().all()
    )

    base = snapshot_pipeline(p)
    return replace(base, tasks=tasks)
