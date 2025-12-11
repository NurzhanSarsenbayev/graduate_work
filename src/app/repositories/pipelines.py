from __future__ import annotations

from typing import Sequence, Optional, TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.models import EtlPipeline, EtlRun

if TYPE_CHECKING:
    # Чтобы не ловить циклический импорт в рантайме
    from src.app.api.pipelines import PipelineCreate


ALLOWED_TARGET_TABLES = {
    "analytics.film_dim",
    "analytics.film_rating_agg",
}


async def list_pipelines(session: AsyncSession) -> Sequence[EtlPipeline]:
    """Вернуть все пайплайны (пока без пагинации/фильтров)."""
    stmt = select(EtlPipeline).order_by(EtlPipeline.name)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_pipeline(session: AsyncSession, pipeline_id: str) -> Optional[EtlPipeline]:
    """Вернуть один пайплайн по id или None."""
    stmt = select(EtlPipeline).where(EtlPipeline.id == pipeline_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_pipeline(session: AsyncSession, payload: "PipelineCreate") -> EtlPipeline:
    """Создать новый ETL-пайплайн (без задач, только основной конфиг)."""

    if payload.target_table not in ALLOWED_TARGET_TABLES:
        raise ValueError(f"target_table '{payload.target_table}' is not allowed")

    # id можем не задавать (gen_random_uuid в БД),
    # но для наглядности сгенерируем сами
    pipeline = EtlPipeline(
        id=str(uuid4()),
        name=payload.name,
        description=payload.description,
        type=payload.type,
        mode=payload.mode,
        enabled=payload.enabled,
        batch_size=payload.batch_size,
        target_table=payload.target_table,
        source_query=payload.source_query,
        # incremental_key пока не используем
    )

    session.add(pipeline)
    await session.commit()
    await session.refresh(pipeline)

    return pipeline

async def update_pipeline_status(
    session: AsyncSession,
    pipeline_id: str,
    new_status: str,
) -> Optional[EtlPipeline]:
    """Обновить статус пайплайна без лишней логики."""

    pipeline = await get_pipeline(session, pipeline_id)
    if pipeline is None:
        return None

    pipeline.status = new_status
    await session.commit()
    await session.refresh(pipeline)

    return pipeline

async def update_pipeline(
    session: AsyncSession,
    pipeline_id: str,
    data: dict,
) -> Optional[EtlPipeline]:
    """Частично обновить пайплайн.

    data — словарь только с теми полями, которые реально нужно поменять.
    """
    pipeline = await get_pipeline(session, pipeline_id)
    if pipeline is None:
        return None

    for field, value in data.items():
        setattr(pipeline, field, value)

    await session.commit()
    await session.refresh(pipeline)
    return pipeline

async def list_pipeline_runs(
    session: AsyncSession,
    pipeline_id: str,
    limit: int = 50,
) -> Sequence[EtlRun]:
    """Вернуть историю запусков для заданного пайплайна.

    Сортируем по времени старта (сначала свежие).
    """
    stmt = (
        select(EtlRun)
        .where(EtlRun.pipeline_id == pipeline_id)
        .order_by(EtlRun.started_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return result.scalars().all()