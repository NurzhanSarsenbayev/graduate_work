from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.enums import PipelineStatus
from src.app.models import EtlPipeline


async def claim_run_requested(
    session: AsyncSession,
    pipeline_id: str,
) -> EtlPipeline | None:
    """Атомарно забрать пайплайн в работу: RUN_REQUESTED -> RUNNING.
    Вернёт EtlPipeline, если забрали. None, если уже забрал другой раннер.
    """
    stmt = (
        update(EtlPipeline)
        .where(EtlPipeline.id == pipeline_id)
        .where(EtlPipeline.status == PipelineStatus.RUN_REQUESTED.value)
        .values(status=PipelineStatus.RUNNING.value)
        .returning(EtlPipeline)
    )
    res = await session.execute(stmt)
    claimed = res.scalar_one_or_none()
    if claimed is not None:
        await session.commit()
    return claimed


async def apply_pause_requested(
    session: AsyncSession,
    pipeline_id: str,
) -> bool:
    """Атомарно применить паузу: PAUSE_REQUESTED -> PAUSED.
    True если применили, False если кто-то уже поменял статус.
    """
    stmt = (
        update(EtlPipeline)
        .where(EtlPipeline.id == pipeline_id)
        .where(EtlPipeline.status == PipelineStatus.PAUSE_REQUESTED.value)
        .values(status=PipelineStatus.PAUSED.value)
    )
    res = await session.execute(stmt)
    updated = res.rowcount or 0
    if updated:
        await session.commit()
        return True
    return False


async def set_status(
    session: AsyncSession,
    pipeline: EtlPipeline,
    status: str,
) -> None:
    pipeline.status = status
    await session.commit()
