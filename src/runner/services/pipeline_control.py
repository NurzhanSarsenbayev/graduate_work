from __future__ import annotations

from sqlalchemy import update, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.enums import PipelineStatus, RunStatus
from src.app.models import EtlPipeline, EtlRun
from src.runner.services.time_utils import utcnow_naive


async def recover_stuck_running_on_startup(session: AsyncSession) -> int:
    res = await session.execute(
        select(EtlPipeline.id).where(EtlPipeline.status == PipelineStatus.RUNNING.value)
    )
    pipeline_ids = [row[0] for row in res.all()]
    if not pipeline_ids:
        return 0

    await session.execute(
        update(EtlPipeline)
        .where(EtlPipeline.id.in_(pipeline_ids))
        .where(EtlPipeline.status == PipelineStatus.RUNNING.value)
        .values(status=PipelineStatus.FAILED.value)
    )

    await session.execute(
        update(EtlRun)
        .where(EtlRun.pipeline_id.in_(pipeline_ids))
        .where(EtlRun.status == RunStatus.RUNNING.value)
        .values(
            status=RunStatus.FAILED.value,
            finished_at=utcnow_naive(),
            error_message="recovered after runner crash",
        )
    )

    await session.commit()
    return len(pipeline_ids)

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


async def set_status(session: AsyncSession, pipeline_id: str, status: str) -> None:
    stmt = (
        update(EtlPipeline)
        .where(EtlPipeline.id == pipeline_id)
        .values(status=status)
    )
    await session.execute(stmt)
    await session.commit()
